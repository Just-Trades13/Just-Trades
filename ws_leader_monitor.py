"""
WebSocket Leader Monitor for Pro Copy Trader
=============================================
Monitors leader accounts via Tradovate WebSocket for fill events.
When a fill is detected on a leader account, copies the trade to all enabled followers.

Follows the same pattern as live_max_loss_monitor.py (proven WebSocket code).

Key safety features:
- Loop prevention: clOrdId prefix 'JT_COPY_' — ignores fills from copied orders
- 4pm CT replay filter: rejects fills that occurred before WebSocket connection time
- Reconnection with exponential backoff
- Per-leader asyncio.Lock prevents duplicate copies

Usage:
    from ws_leader_monitor import start_leader_monitor
    start_leader_monitor()
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List

logger = logging.getLogger('leader_monitor')

# Try to import websockets
try:
    import websockets
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets library not installed. pip install websockets")

# Tick sizes for TP/SL delta calculation (Rule 15: 2-letter symbols handled)
TICK_SIZES = {
    'ES': 0.25, 'NQ': 0.25, 'RTY': 0.10, 'YM': 1.0,
    'MES': 0.25, 'MNQ': 0.25, 'M2K': 0.10, 'MYM': 1.0,
    'GC': 0.10, 'SI': 0.005, 'HG': 0.0005, 'PL': 0.10,
    'MGC': 0.10, 'SIL': 0.005,
    'CL': 0.01, 'NG': 0.001, 'HO': 0.0001, 'RB': 0.0001,
    'MCL': 0.01,
    'ZB': 0.03125, 'ZN': 0.015625, 'ZF': 0.0078125, 'ZT': 0.00390625,
    'DX': 0.005,
    'KC': 0.05, 'CT': 0.01, 'SB': 0.01,
    '6E': 0.00005, '6J': 0.0000005, '6B': 0.0001, '6A': 0.0001,
}


def _get_symbol_root(symbol: str) -> str:
    """Extract symbol root from futures contract name (e.g. GCJ6 -> GC, MNQH6 -> MNQ).
    Rule 15 compliant: tries 3-char first, then 2-char."""
    alpha = ''.join(c for c in symbol if c.isalpha()).upper()
    # Try 3-char root first (e.g. MNQ, MGC, MES)
    root3 = alpha[:3]
    if root3 in TICK_SIZES:
        return root3
    # Try 2-char root (e.g. GC, CL, NQ, ES)
    root2 = alpha[:2]
    if root2 in TICK_SIZES:
        return root2
    # Fallback: return 3-char (might match in future)
    return root3


def _get_tick_size(symbol: str) -> float:
    """Get tick size for a symbol. Default 0.25."""
    root = _get_symbol_root(symbol)
    return TICK_SIZES.get(root, 0.25)


# Global state
_monitor_running = False
_monitor_thread = None
_leader_connections: Dict[int, Any] = {}  # leader_id -> LeaderConnection
_copy_locks: Dict[int, asyncio.Lock] = {}  # leader_id -> Lock (prevents duplicate copies)

# Copy order prefix for loop prevention
COPY_ORDER_PREFIX = 'JT_COPY_'

# Reload signal — set by trigger_leader_reload() to refresh active leaders
_leader_reload_event = threading.Event()


def trigger_leader_reload():
    """Signal the leader monitor to reload active leaders from DB."""
    _leader_reload_event.set()


class LeaderConnection:
    """WebSocket connection to Tradovate for monitoring a leader's fills."""

    def __init__(self, leader_id: int, account_id: int, subaccount_id: str,
                 access_token: str, is_demo: bool = True, user_id: int = None):
        self.leader_id = leader_id
        self.account_id = account_id
        self.subaccount_id = subaccount_id
        self.access_token = access_token
        self.is_demo = is_demo
        self.user_id = user_id

        # WebSocket URL
        self.ws_url = ("wss://demo.tradovateapi.com/v1/websocket"
                       if is_demo else "wss://live.tradovateapi.com/v1/websocket")

        # Connection state
        self.websocket = None
        self.connected = False
        self.authenticated = False
        self._running = False
        self._last_heartbeat = 0
        self._request_id = 0
        self._connection_time = None  # When we connected — for replay filter

        # Position state tracking (Phase 2)
        self._positions: Dict[str, dict] = {}  # symbol -> {side: 'Long'|'Short', qty: int}
        self._contract_cache: Dict[int, str] = {}  # contractId -> symbol name

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def connect(self) -> bool:
        """Connect and authenticate to Tradovate WebSocket."""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets not available")
            return False

        try:
            logger.info(f"Connecting to Tradovate for leader {self.leader_id} "
                        f"(account {self.subaccount_id})")

            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=5
            )
            self.connected = True
            self._connection_time = datetime.now(timezone.utc)

            # Wait for 'o' (open) frame before authenticating
            open_frame = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            logger.debug(f"Leader {self.leader_id} open frame: {open_frame[:50] if open_frame else 'empty'}")

            # Authenticate with request ID 0 (reserved for auth per Tradovate spec)
            auth_msg = f"authorize\n0\n\n{self.access_token}"
            await self.websocket.send(auth_msg)

            # Wait for auth response — loop until we get the auth reply (skip heartbeats)
            auth_success = False
            for _ in range(10):  # Max 10 messages to find auth response
                response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
                logger.debug(f"Leader {self.leader_id} auth recv: {response[:200] if response else 'empty'}")

                if not response or response in ('o', 'h', '[]'):
                    continue

                # Parse a[...] response looking for {"i":0,"s":200}
                if response.startswith('a['):
                    try:
                        array = json.loads(response[1:])
                        for item in array:
                            if isinstance(item, dict) and item.get('i') == 0 and item.get('s') == 200:
                                auth_success = True
                                break
                            elif isinstance(item, str):
                                parsed = json.loads(item)
                                if isinstance(parsed, dict) and parsed.get('i') == 0 and parsed.get('s') == 200:
                                    auth_success = True
                                    break
                    except (json.JSONDecodeError, TypeError):
                        pass

                if auth_success:
                    break

            if auth_success:
                self.authenticated = True
                logger.info(f"Authenticated for leader {self.leader_id}")

                # Subscribe to user/syncrequest for fill events
                await self._subscribe_sync()
                return True
            else:
                logger.error(f"Auth failed for leader {self.leader_id} — no s:200 response")
                return False

        except Exception as e:
            logger.error(f"Connection error for leader {self.leader_id}: {e}")
            return False

    async def _subscribe_sync(self):
        """Subscribe to user/syncrequest for real-time fill events."""
        try:
            sync_msg = f"user/syncrequest\n{self._next_request_id()}\n\n{{}}"
            await self.websocket.send(sync_msg)
            logger.info(f"Subscribed to sync updates for leader {self.leader_id}")
        except Exception as e:
            logger.error(f"Failed to subscribe sync for leader {self.leader_id}: {e}")

    async def run(self, fill_callback):
        """Run the monitoring loop."""
        self._running = True
        self._last_server_msg = time.time()

        while self._running and self.connected:
            try:
                # Send heartbeat every 2.5 seconds
                now = time.time()
                if now - self._last_heartbeat > 2.5:
                    await self.websocket.send("[]")
                    self._last_heartbeat = now

                # Server timeout: if no message in 10s, connection is dead
                if now - self._last_server_msg > 10.0:
                    logger.warning(f"Server timeout for leader {self.leader_id} — no message in 10s")
                    self.connected = False
                    break

                # Receive messages
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    self._last_server_msg = time.time()
                    await self._handle_message(message, fill_callback)
                except asyncio.TimeoutError:
                    continue

            except ConnectionClosed:
                logger.warning(f"WebSocket closed for leader {self.leader_id}")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"Error in leader monitor loop {self.leader_id}: {e}")

        self._running = False

    async def _handle_message(self, raw_message: str, fill_callback):
        """Handle incoming WebSocket message — look for fill events."""
        if not raw_message or raw_message in ('o', 'h', '[]'):
            return

        try:
            items = []

            # Parse a[...] format — Tradovate wraps messages in a JSON array prefixed with 'a'
            if raw_message.startswith('a['):
                array = json.loads(raw_message[1:])
                for element in array:
                    if isinstance(element, dict):
                        items.append(element)
                    elif isinstance(element, str):
                        try:
                            parsed = json.loads(element)
                            if isinstance(parsed, dict):
                                items.append(parsed)
                        except (json.JSONDecodeError, TypeError):
                            pass
            elif '{' in raw_message:
                json_start = raw_message.find('{')
                parsed = json.loads(raw_message[json_start:])
                if isinstance(parsed, dict):
                    items.append(parsed)

            for data in items:
                await self._check_for_fills(data, fill_callback)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"Message parse error (leader {self.leader_id}): {e}")

    async def _check_for_fills(self, data: dict, fill_callback):
        """Check for fill events in the WebSocket data."""
        fills = []

        # Props event: {e: "props", d: {entityType: "fill", entity: {...}, eventType: "Created"}}
        if data.get('e') == 'props':
            d = data.get('d', {})
            if d.get('entityType') == 'fill' and d.get('eventType') == 'Created':
                # The actual fill fields are inside d['entity'], not d itself
                entity = d.get('entity') or d
                if isinstance(entity, dict):
                    fills.append(entity)

        # Bulk sync response with fills array nested in 'd'
        if 'd' in data and not fills:
            d = data['d']
            if isinstance(d, dict) and 'fills' in d:
                for f in d.get('fills', []):
                    if isinstance(f, dict):
                        fills.append(f)

        # Direct fills array at top level
        if 'fills' in data and not fills:
            for f in data.get('fills', []):
                if isinstance(f, dict):
                    fills.append(f)

        for fill in fills:
            await self._process_fill(fill, fill_callback)

    async def _resolve_symbol(self, contract_id: int) -> str:
        """Resolve contractId to symbol name via REST API with caching."""
        if not contract_id:
            return ''
        if contract_id in self._contract_cache:
            return self._contract_cache[contract_id]
        try:
            import aiohttp
            base_url = ("https://demo.tradovateapi.com/v1" if self.is_demo
                        else "https://live.tradovateapi.com/v1")
            headers = {'Authorization': f'Bearer {self.access_token}',
                       'Content-Type': 'application/json'}
            async with aiohttp.ClientSession() as http:
                async with http.get(f"{base_url}/contract/item",
                                    params={'id': contract_id},
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        symbol = data.get('name', '') or ''
                        if symbol:
                            self._contract_cache[contract_id] = symbol
                            logger.debug(f"Resolved contractId {contract_id} → {symbol}")
                        return symbol
        except Exception as e:
            logger.warning(f"Failed to resolve contractId {contract_id}: {e}")
        return ''

    def _classify_fill(self, symbol: str, action: str, qty: int) -> str:
        """Classify a fill based on current position state.

        Returns: 'entry', 'partial_exit', 'full_exit', or 'reversal'
        """
        pos = self._positions.get(symbol)
        if not pos or pos.get('qty', 0) == 0:
            return 'entry'  # Flat — any fill is an entry

        pos_side = pos.get('side', '')
        pos_qty = pos.get('qty', 0)

        # Determine if fill is same-direction or opposite
        fill_is_buy = action.lower() == 'buy'
        same_direction = (fill_is_buy and pos_side == 'Long') or (not fill_is_buy and pos_side == 'Short')

        if same_direction:
            return 'entry'  # Adding to position (scale-in)

        # Opposite direction
        if qty < pos_qty:
            return 'partial_exit'
        elif qty == pos_qty:
            return 'full_exit'
        else:
            return 'reversal'  # qty > pos_qty — flip

    def _update_position(self, symbol: str, action: str, qty: int, fill_type: str):
        """Update tracked position state after a classified fill."""
        fill_is_buy = action.lower() == 'buy'
        new_side = 'Long' if fill_is_buy else 'Short'

        if fill_type == 'entry':
            pos = self._positions.get(symbol, {'side': new_side, 'qty': 0})
            pos['side'] = new_side
            pos['qty'] = pos.get('qty', 0) + qty
            self._positions[symbol] = pos
        elif fill_type == 'partial_exit':
            pos = self._positions.get(symbol)
            if pos:
                pos['qty'] = max(0, pos['qty'] - qty)
                if pos['qty'] == 0:
                    del self._positions[symbol]
        elif fill_type == 'full_exit':
            self._positions.pop(symbol, None)
        elif fill_type == 'reversal':
            pos = self._positions.get(symbol, {'side': '', 'qty': 0})
            remainder = qty - pos.get('qty', 0)
            self._positions[symbol] = {'side': new_side, 'qty': remainder}

    async def _get_leader_risk_config(self, symbol: str, entry_price: float) -> dict:
        """Extract TP/SL from leader's working orders after an entry fill.

        Returns risk_config dict compatible with /api/manual-trade:
          {take_profit: [{gain_ticks, trim_percent: 100}], stop_loss: {loss_ticks, type: 'fixed'}}
        Returns {} if no TP/SL found on leader.
        """
        try:
            import aiohttp
            base_url = ("https://demo.tradovateapi.com/v1" if self.is_demo
                        else "https://live.tradovateapi.com/v1")
            headers = {'Authorization': f'Bearer {self.access_token}',
                       'Content-Type': 'application/json'}

            tick_size = _get_tick_size(symbol)
            symbol_root = _get_symbol_root(symbol)
            risk_config = {}

            async with aiohttp.ClientSession() as http:
                async with http.get(f"{base_url}/order/list",
                                    headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        logger.warning(f"Leader order/list returned {resp.status}")
                        return {}
                    orders = await resp.json()

            # Filter to working orders for this symbol
            for order in orders:
                ord_status = (order.get('ordStatus') or '').lower()
                if ord_status not in ('working', 'accepted'):
                    continue
                # Match by symbol root in the order's contract
                ord_name = (order.get('contractName') or order.get('name') or '').upper()
                if symbol_root not in ord_name and symbol.upper() not in ord_name:
                    # Try contractId match
                    continue

                ord_type = (order.get('ordType') or '').lower()
                ord_price = order.get('price', 0)

                if ord_type == 'limit' and ord_price > 0:
                    # Limit order = likely TP
                    tp_ticks = abs(ord_price - entry_price) / tick_size
                    tp_ticks = round(tp_ticks)
                    if tp_ticks > 0:
                        risk_config['take_profit'] = [{'gain_ticks': tp_ticks, 'trim_percent': 100}]
                        logger.info(f"Leader TP found: {ord_price} ({tp_ticks} ticks from {entry_price})")

                elif ord_type in ('stop', 'stopmarket', 'stoplimit', 'stoporder') and ord_price > 0:
                    # Stop order = likely SL
                    sl_ticks = abs(entry_price - ord_price) / tick_size
                    sl_ticks = round(sl_ticks)
                    if sl_ticks > 0:
                        risk_config['stop_loss'] = {'loss_ticks': sl_ticks, 'type': 'fixed'}
                        logger.info(f"Leader SL found: {ord_price} ({sl_ticks} ticks from {entry_price})")

                elif ord_type == 'trailingstoporder':
                    # Trailing stop — extract trail offset
                    trail_offset = order.get('trailPrice') or order.get('pegOffset')
                    if trail_offset:
                        trail_ticks = round(abs(trail_offset) / tick_size)
                        if trail_ticks > 0:
                            risk_config['stop_loss'] = {'loss_ticks': trail_ticks, 'type': 'fixed'}
                            logger.info(f"Leader trailing SL found: offset={trail_offset} ({trail_ticks} ticks)")

            if not risk_config:
                logger.info(f"No TP/SL found on leader for {symbol} — followers get naked entry")

            return risk_config

        except Exception as e:
            logger.error(f"Error getting leader risk config: {e}")
            return {}

    async def _process_fill(self, fill: dict, fill_callback):
        """Process a single fill event — classify and copy to followers."""
        fill_id = fill.get('id')
        order_id = fill.get('orderId')
        contract_id = fill.get('contractId')
        qty = fill.get('qty', 0)
        price = fill.get('price', 0)
        action = fill.get('action', '')  # Buy or Sell
        timestamp_str = fill.get('timestamp', '')

        # --- LOOP PREVENTION ---
        # Check clOrdId for our copy prefix
        cl_ord_id = fill.get('clOrdId', '') or ''
        if cl_ord_id.startswith(COPY_ORDER_PREFIX):
            logger.debug(f"Skipping copied order fill (clOrdId={cl_ord_id})")
            return

        # --- REPLAY FILTER ---
        # Reject fills that occurred before we connected (4pm CT sync replay)
        if timestamp_str and self._connection_time:
            try:
                fill_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if fill_time < self._connection_time:
                    logger.debug(f"Skipping pre-connection fill (fill_time={fill_time}, "
                                 f"connected_at={self._connection_time})")
                    return
            except (ValueError, TypeError):
                pass  # If we can't parse, let it through

        if not action or qty == 0:
            return

        # Resolve symbol from contractId if not in fill data
        symbol = fill.get('symbol', '') or ''
        if not symbol and contract_id:
            symbol = await self._resolve_symbol(contract_id)
        if not symbol:
            logger.warning(f"Cannot resolve symbol for fill (contractId={contract_id}), skipping")
            return

        qty = abs(qty)

        # Classify the fill
        fill_type = self._classify_fill(symbol, action, qty)

        logger.info(f"FILL detected on leader {self.leader_id}: "
                    f"{action} {qty} {symbol} @ {price} — type={fill_type}")

        # Update position state
        self._update_position(symbol, action, qty, fill_type)
        logger.debug(f"Leader {self.leader_id} positions: {self._positions}")

        # Pass to callback with fill_type
        if fill_callback:
            try:
                await fill_callback(
                    leader_id=self.leader_id,
                    fill_data={
                        'fill_id': fill_id,
                        'order_id': order_id,
                        'contract_id': contract_id,
                        'symbol': symbol,
                        'action': action,
                        'qty': qty,
                        'price': price,
                        'timestamp': timestamp_str,
                        'fill_type': fill_type,
                    }
                )
            except Exception as e:
                logger.error(f"Fill callback error for leader {self.leader_id}: {e}")

    async def close(self):
        """Close the connection."""
        self._running = False
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
        self.connected = False


# ============================================================================
# FILL CALLBACK — COPY TO FOLLOWERS
# ============================================================================
async def _copy_fill_to_followers(leader_id: int, fill_data: dict):
    """Copy a leader's fill to all enabled followers — smart routing by fill_type."""
    global _copy_locks

    # Per-leader lock prevents duplicate copies
    if leader_id not in _copy_locks:
        _copy_locks[leader_id] = asyncio.Lock()

    async with _copy_locks[leader_id]:
        try:
            from copy_trader_models import (
                get_followers_for_leader, log_copy_trade, update_copy_trade_log
            )

            followers = get_followers_for_leader(leader_id)
            if not followers:
                logger.debug(f"No enabled followers for leader {leader_id}")
                return

            action = fill_data.get('action', '')
            qty = fill_data.get('qty', 1)
            symbol = fill_data.get('symbol', '')
            price = fill_data.get('price', 0)
            fill_type = fill_data.get('fill_type', 'entry')

            # For entries, get leader's TP/SL as risk_config
            risk_config = {}
            if fill_type == 'entry':
                leader_conn = _leader_connections.get(leader_id)
                if leader_conn and price > 0:
                    risk_config = await leader_conn._get_leader_risk_config(symbol, price)

            logger.info(f"Copying {fill_type} {action} {qty} {symbol} from leader {leader_id} "
                        f"to {len(followers)} followers (risk={bool(risk_config)})")

            for follower in followers:
                follower_id = follower['id']
                multiplier = follower.get('multiplier', 1.0) or 1.0
                max_pos = follower.get('max_position_size', 0) or 0
                follower_qty = max(1, int(round(qty * multiplier)))

                # Apply max_position_size cap (Step 5)
                if max_pos and max_pos > 0 and fill_type == 'entry':
                    follower_qty = min(follower_qty, max_pos)

                # Determine follower risk — respect copy_tp / copy_sl toggles
                follower_risk = {}
                if risk_config and fill_type == 'entry':
                    copy_tp = follower.get('copy_tp', True)
                    copy_sl = follower.get('copy_sl', True)
                    if copy_tp and 'take_profit' in risk_config:
                        follower_risk['take_profit'] = risk_config['take_profit']
                    if copy_sl and 'stop_loss' in risk_config:
                        follower_risk['stop_loss'] = risk_config['stop_loss']

                # Log the pending copy
                log_side = 'close' if fill_type in ('full_exit', 'reversal') else action
                log_id = log_copy_trade(
                    leader_id=leader_id,
                    follower_id=follower_id,
                    symbol=symbol,
                    side=f"{log_side} ({fill_type})",
                    leader_quantity=qty,
                    follower_quantity=follower_qty,
                    leader_price=price,
                    status='pending'
                )

                start_time = time.time()

                try:
                    account_subaccount = f"{follower['account_id']}:{follower['subaccount_id']}"

                    if fill_type == 'entry':
                        result = await _execute_follower_entry(
                            account_subaccount, symbol, action, follower_qty,
                            risk_config=follower_risk
                        )
                    elif fill_type == 'partial_exit':
                        # Trim: opposite-side market order, no risk
                        opposite_side = 'Sell' if action.lower() == 'buy' else 'Buy'
                        result = await _execute_follower_entry(
                            account_subaccount, symbol, opposite_side, follower_qty,
                            risk_config={}
                        )
                    elif fill_type == 'full_exit':
                        result = await _execute_follower_close(account_subaccount, symbol)
                    elif fill_type == 'reversal':
                        # Close first, then open new entry
                        close_result = await _execute_follower_close(account_subaccount, symbol)
                        if close_result and close_result.get('success'):
                            logger.info(f"  Reversal close done for follower {follower_id}, now entering")
                        # New entry in opposite direction
                        result = await _execute_follower_entry(
                            account_subaccount, symbol, action, follower_qty,
                            risk_config=follower_risk
                        )
                    else:
                        # Unknown fill type — fall back to naked entry
                        result = await _execute_follower_entry(
                            account_subaccount, symbol, action, follower_qty,
                            risk_config={}
                        )

                    latency_ms = int((time.time() - start_time) * 1000)

                    if result and result.get('success'):
                        risk_desc = ''
                        if follower_risk:
                            tp = follower_risk.get('take_profit', [{}])
                            sl = follower_risk.get('stop_loss', {})
                            tp_t = tp[0].get('gain_ticks', 0) if tp else 0
                            sl_t = sl.get('loss_ticks', 0) if sl else 0
                            risk_desc = f" TP={tp_t}t SL={sl_t}t"
                        if log_id:
                            update_copy_trade_log(
                                log_id, status='filled',
                                follower_order_id=result.get('order_id'),
                                latency_ms=latency_ms
                            )
                        logger.info(f"  Copied {fill_type} to follower {follower_id}: "
                                    f"{action} {follower_qty} {symbol}{risk_desc} ({latency_ms}ms)")
                    else:
                        error_msg = (result.get('error') or 'Unknown error') if result else 'No result'
                        if log_id:
                            update_copy_trade_log(
                                log_id, status='error',
                                error_message=error_msg,
                                latency_ms=latency_ms
                            )
                        logger.warning(f"  Failed {fill_type} for follower {follower_id}: {error_msg}")

                except Exception as e:
                    latency_ms = int((time.time() - start_time) * 1000)
                    if log_id:
                        update_copy_trade_log(
                            log_id, status='error',
                            error_message=str(e),
                            latency_ms=latency_ms
                        )
                    logger.error(f"  Error copying to follower {follower_id}: {e}")

        except Exception as e:
            logger.error(f"Error in copy_fill_to_followers for leader {leader_id}: {e}")


async def _execute_follower_entry(account_subaccount: str, symbol: str,
                                   side: str, quantity: int,
                                   risk_config: dict = None) -> dict:
    """Execute an entry trade on a follower account with optional TP/SL."""
    import aiohttp
    import uuid

    platform_url = os.environ.get('PLATFORM_URL') or f"http://127.0.0.1:{os.environ.get('PORT', '5000')}"
    url = f"{platform_url}/api/manual-trade"
    cl_ord_id = f"{COPY_ORDER_PREFIX}{uuid.uuid4().hex[:12]}"

    payload = {
        'account_subaccount': account_subaccount,
        'symbol': symbol,
        'side': side,
        'quantity': quantity,
        'risk': risk_config or {},
        'cl_ord_id': cl_ord_id,
    }

    try:
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                result = await resp.json()
                return result
    except Exception as e:
        logger.error(f"Error executing follower entry: {e}")
        return {'success': False, 'error': str(e)}


async def _execute_follower_close(account_subaccount: str, symbol: str) -> dict:
    """Close/flatten a follower's position via /api/manual-trade with side='close'."""
    import aiohttp
    import uuid

    platform_url = os.environ.get('PLATFORM_URL') or f"http://127.0.0.1:{os.environ.get('PORT', '5000')}"
    url = f"{platform_url}/api/manual-trade"
    cl_ord_id = f"{COPY_ORDER_PREFIX}{uuid.uuid4().hex[:12]}"

    payload = {
        'account_subaccount': account_subaccount,
        'symbol': symbol,
        'side': 'close',
        'quantity': 1,  # Not used for close — liquidateposition handles qty
        'risk': {},
        'cl_ord_id': cl_ord_id,
    }

    try:
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                result = await resp.json()
                return result
    except Exception as e:
        logger.error(f"Error executing follower close: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================================
# LOAD ACTIVE LEADERS FROM DB
# ============================================================================
def _load_active_leaders() -> List[Dict]:
    """Load leader accounts that have auto_copy_enabled and at least one follower."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return []

    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT
                la.id as leader_id,
                la.account_id,
                la.subaccount_id,
                la.user_id,
                a.tradovate_token,
                a.environment
            FROM leader_accounts la
            INNER JOIN follower_accounts fa ON la.id = fa.leader_id
            INNER JOIN accounts a ON la.account_id = a.id
            WHERE la.is_active = TRUE
              AND la.auto_copy_enabled = TRUE
              AND fa.is_enabled = TRUE
              AND a.tradovate_token IS NOT NULL
        ''')

        leaders = []
        for row in cursor.fetchall():
            leaders.append({
                'leader_id': row[0],
                'account_id': row[1],
                'subaccount_id': str(row[2]),
                'user_id': row[3],
                'access_token': row[4],
                'is_demo': row[5] != 'live',
            })

        conn.close()
        return leaders

    except Exception as e:
        logger.error(f"Error loading active leaders: {e}")
        return []


# ============================================================================
# MAIN ASYNC LOOP
# ============================================================================
async def _run_leader_monitor():
    """Main async loop for leader monitoring."""
    global _leader_connections, _monitor_running

    _monitor_running = True
    logger.info("Starting Pro Copy Trader leader monitor...")

    while _monitor_running:
        try:
            # Clear reload event before loading (so any signal during load triggers next cycle)
            _leader_reload_event.clear()

            leaders = _load_active_leaders()

            if not leaders:
                logger.debug("No active leaders with auto_copy_enabled")
                # Disconnect any previously-connected leaders that are no longer active
                for lid in list(_leader_connections.keys()):
                    old_conn = _leader_connections.pop(lid)
                    if old_conn.connected:
                        try:
                            await old_conn.close()
                        except Exception:
                            pass
                    logger.info(f"Leader monitor: disconnected disabled leader {lid}")
                await asyncio.sleep(15)
                continue

            logger.info(f"Monitoring {len(leaders)} active leader(s)")

            # Disconnect leaders no longer in the active list
            active_ids = {l['leader_id'] for l in leaders}
            for lid in list(_leader_connections.keys()):
                if lid not in active_ids:
                    old_conn = _leader_connections.pop(lid)
                    if old_conn.connected:
                        try:
                            await old_conn.close()
                        except Exception:
                            pass
                    logger.info(f"Leader monitor: disconnected disabled leader {lid}")

            # Create connections for new leaders
            tasks = []
            for leader_info in leaders:
                lid = leader_info['leader_id']
                conn_key = lid

                # Skip if already connected
                if conn_key in _leader_connections:
                    existing = _leader_connections[conn_key]
                    if existing.connected:
                        continue

                # Create new connection
                conn = LeaderConnection(
                    leader_id=lid,
                    account_id=leader_info['account_id'],
                    subaccount_id=leader_info['subaccount_id'],
                    access_token=leader_info['access_token'],
                    is_demo=leader_info['is_demo'],
                    user_id=leader_info['user_id']
                )

                _leader_connections[conn_key] = conn
                tasks.append(asyncio.create_task(_monitor_leader(conn)))

            # Wait for any connection to drop OR reload signal, then refresh
            if tasks:
                # Check reload event every 5 seconds to pick up newly enabled/disabled leaders
                while True:
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=5.0)
                    if _leader_reload_event.is_set():
                        logger.info("Leader monitor: reload triggered, refreshing active leaders")
                        for task in pending:
                            task.cancel()
                        break
                    if done:
                        # A connection dropped — existing reconnect logic handles it
                        # Clean up completed tasks
                        for task in done:
                            try:
                                task.result()
                            except Exception as e:
                                logger.error(f"Leader monitor task error: {e}")
                        break
            else:
                # No new tasks — wait briefly or until reload signal
                await asyncio.sleep(5)

            # Reconnection delay with backoff
            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error in leader monitor main loop: {e}")
            await asyncio.sleep(10)


async def _monitor_leader(conn: LeaderConnection):
    """Monitor a single leader with reconnection and exponential backoff."""
    backoff = 1
    max_backoff = 60

    while _monitor_running:
        try:
            success = await conn.connect()
            if success:
                backoff = 1  # Reset on successful connection
                await conn.run(fill_callback=_copy_fill_to_followers)

            # Connection lost or failed
            await conn.close()

            if not _monitor_running:
                break

            logger.info(f"Reconnecting leader {conn.leader_id} in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

        except Exception as e:
            logger.error(f"Leader monitor error for {conn.leader_id}: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


# ============================================================================
# PUBLIC API
# ============================================================================
def start_leader_monitor():
    """Start the leader monitor in a background daemon thread."""
    global _monitor_thread, _monitor_running

    if _monitor_running:
        logger.info("Leader monitor already running")
        return

    def _thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_leader_monitor())
        except Exception as e:
            logger.error(f"Leader monitor thread error: {e}")
        finally:
            loop.close()

    _monitor_thread = threading.Thread(target=_thread_target, daemon=True, name="leader-monitor")
    _monitor_thread.start()
    logger.info("Leader monitor daemon thread started")


def stop_leader_monitor():
    """Stop the leader monitor."""
    global _monitor_running
    _monitor_running = False
    logger.info("Leader monitor stopping...")


def get_leader_monitor_status() -> Dict:
    """Get the current status of the leader monitor."""
    status = {
        'running': _monitor_running,
        'connections': {}
    }
    for lid, conn in _leader_connections.items():
        status['connections'][lid] = {
            'leader_id': conn.leader_id,
            'connected': conn.connected,
            'authenticated': conn.authenticated,
            'subaccount_id': conn.subaccount_id,
            'is_demo': conn.is_demo,
        }
    return status


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Leader Monitor Status:")
    print(f"  WebSockets available: {WEBSOCKETS_AVAILABLE}")
    print(f"  Copy order prefix: {COPY_ORDER_PREFIX}")
    print(f"  Monitor running: {_monitor_running}")
    print("\nTo start: from ws_leader_monitor import start_leader_monitor; start_leader_monitor()")
