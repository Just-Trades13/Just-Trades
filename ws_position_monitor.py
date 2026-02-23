"""
WebSocket Position Monitor — Real-Time Broker Sync for All Accounts
====================================================================
Monitors ALL active recorder accounts via Tradovate WebSocket for position,
fill, and order events. Keeps DB (recorder_positions, recorded_trades) in
perfect sync with broker state in real-time.

Architecture: ONE WebSocket per TOKEN (not per account).
- JADVIX has 7 accounts sharing ONE Tradovate token
- user/syncrequest accepts an 'accounts' array — subscribe to ALL on one socket
- Result: 1 connection instead of 7, minimal rate limit impact (Rule 16)

Based on proven patterns from ws_leader_monitor.py (production-verified Feb 23).
WebSocket is for MONITORING only — all orders use REST (Rule 10).

Usage:
    from ws_position_monitor import start_position_monitor
    start_position_monitor()
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List

logger = logging.getLogger('position_monitor')

# Try to import websockets
try:
    import websockets
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets library not installed — position monitor disabled")

# Tick sizes for price matching (Rule 15: 2-letter symbols handled)
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
    """Extract symbol root (Rule 15: tries 3-char first, then 2-char)."""
    alpha = ''.join(c for c in symbol if c.isalpha()).upper()
    root3 = alpha[:3]
    if root3 in TICK_SIZES:
        return root3
    root2 = alpha[:2]
    if root2 in TICK_SIZES:
        return root2
    return root3


def _get_tick_size(symbol: str) -> float:
    """Get tick size for a symbol. Default 0.25."""
    root = _get_symbol_root(symbol)
    return TICK_SIZES.get(root, 0.25)


# Global state
_monitor_running = False
_monitor_thread = None
_token_connections: Dict[str, Any] = {}  # token_hash -> AccountGroupConnection
_sub_to_recorders: Dict[int, List[int]] = {}  # subaccount_id -> [recorder_ids]


class AccountGroupConnection:
    """WebSocket connection to Tradovate monitoring multiple accounts on one token.

    One token may have multiple subaccounts. We subscribe to ALL subaccounts
    on a single WebSocket via user/syncrequest with accounts=[...] array.
    """

    def __init__(self, token_key: str, access_token: str, is_demo: bool,
                 account_ids: List[int], subaccount_ids: List[int],
                 account_db_ids: List[int]):
        self.token_key = token_key  # Short hash for logging
        self.access_token = access_token
        self.is_demo = is_demo
        self.account_ids = account_ids  # accounts table IDs (for fresh token lookup)
        self.subaccount_ids = subaccount_ids  # Tradovate subaccount IDs
        self.account_db_ids = account_db_ids  # For DB lookups

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
        self._connection_time = None

        # Contract ID cache (contractId -> symbol name)
        self._contract_cache: Dict[int, str] = {}

        # Dead-subscription detection
        self._zero_data_windows = 0

        # Max connection: 70 min (before 85-min token expiry)
        self._max_connection_seconds = 4200

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def connect(self) -> bool:
        """Connect and authenticate to Tradovate WebSocket."""
        if not WEBSOCKETS_AVAILABLE:
            return False

        try:
            logger.info(f"[{self.token_key}] Connecting to Tradovate "
                        f"({len(self.subaccount_ids)} accounts, "
                        f"{'demo' if self.is_demo else 'live'})")

            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=5
            )
            self.connected = True
            self._connection_time = datetime.now(timezone.utc)

            # Wait for 'o' (open) frame
            open_frame = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            logger.debug(f"[{self.token_key}] Open frame: {open_frame[:50] if open_frame else 'empty'}")

            # Authenticate with request ID 0
            auth_msg = f"authorize\n0\n\n{self.access_token}"
            await self.websocket.send(auth_msg)

            # Wait for auth response
            auth_success = False
            for _ in range(10):
                response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
                if not response or response in ('o', 'h', '[]'):
                    continue

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
                logger.info(f"[{self.token_key}] Authenticated")
                await self._subscribe_sync()
                return True
            else:
                logger.error(f"[{self.token_key}] Auth failed — no s:200 response")
                return False

        except Exception as e:
            logger.error(f"[{self.token_key}] Connection error: {e}")
            return False

    async def _subscribe_sync(self):
        """Subscribe to user/syncrequest for ALL accounts on this token."""
        try:
            req_id = self._next_request_id()
            sync_body = json.dumps({
                "accounts": [int(sid) for sid in self.subaccount_ids],
                "entityTypes": ["order", "fill", "position"]
            })
            sync_msg = f"user/syncrequest\n{req_id}\n\n{sync_body}"
            await self.websocket.send(sync_msg)
            logger.info(f"[{self.token_key}] Subscribed to sync for accounts "
                        f"{self.subaccount_ids}")

            # Wait for subscription response
            for _ in range(5):
                response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
                if response and response not in ('o', 'h', '[]'):
                    logger.debug(f"[{self.token_key}] Sync response: "
                                 f"{response[:300] if response else 'empty'}")
                    break
        except Exception as e:
            logger.error(f"[{self.token_key}] Failed to subscribe: {e}")

    async def run(self):
        """Main monitoring loop."""
        self._running = True
        self._last_server_msg = time.time()
        self._msg_count = 0
        self._data_msg_count = 0
        self._last_stats_log = time.time()

        while self._running and self.connected:
            try:
                now = time.time()

                # Heartbeat every 2.5s
                if now - self._last_heartbeat > 2.5:
                    await self.websocket.send("[]")
                    self._last_heartbeat = now

                # Server timeout: 10s no message = dead
                if now - self._last_server_msg > 10.0:
                    logger.warning(f"[{self.token_key}] Server timeout — no message in 10s")
                    self.connected = False
                    break

                # Proactive reconnect before token expiry (70 min)
                if self._connection_time:
                    age_seconds = (datetime.now(timezone.utc) - self._connection_time).total_seconds()
                    if age_seconds > self._max_connection_seconds:
                        logger.info(f"[{self.token_key}] Proactive reconnect "
                                    f"(age {int(age_seconds)}s > {self._max_connection_seconds}s)")
                        self.connected = False
                        break

                # Stats + dead-subscription detection every 30s
                if now - self._last_stats_log > 30.0:
                    logger.info(f"[{self.token_key}] WS stats: {self._msg_count} msgs "
                                f"({self._data_msg_count} data) in 30s")

                    if self._data_msg_count == 0:
                        self._zero_data_windows += 1
                        if self._zero_data_windows >= 3:
                            logger.warning(f"[{self.token_key}] No data for "
                                           f"{self._zero_data_windows * 30}s — forcing reconnect")
                            self.connected = False
                            break
                    else:
                        self._zero_data_windows = 0

                    self._msg_count = 0
                    self._data_msg_count = 0
                    self._last_stats_log = now

                # Receive messages
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    self._last_server_msg = time.time()
                    self._msg_count += 1
                    await self._handle_message(message)
                except asyncio.TimeoutError:
                    continue

            except ConnectionClosed:
                logger.warning(f"[{self.token_key}] WebSocket closed")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"[{self.token_key}] Monitor loop error: {e}")

        self._running = False

    async def _handle_message(self, raw_message: str):
        """Handle incoming WebSocket message."""
        if not raw_message or raw_message in ('o', 'h', '[]'):
            return

        self._data_msg_count += 1

        try:
            items = []

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
                if data.get('e') == 'props':
                    d = data.get('d', {})
                    entity_type = d.get('entityType')
                    entity = d.get('entity') or d

                    if entity_type == 'position' and isinstance(entity, dict):
                        await self._handle_position_event(entity)
                    elif entity_type == 'fill' and isinstance(entity, dict):
                        if d.get('eventType') == 'Created':
                            await self._handle_fill_event(entity)
                    elif entity_type == 'order' and isinstance(entity, dict):
                        await self._handle_order_event(entity)

                # Bulk sync response
                if 'd' in data:
                    d = data['d']
                    if isinstance(d, dict):
                        for pos in d.get('positions', []):
                            if isinstance(pos, dict):
                                await self._handle_position_event(pos)
                        for fill in d.get('fills', []):
                            if isinstance(fill, dict):
                                await self._handle_fill_event(fill)
                        for order in d.get('orders', []):
                            if isinstance(order, dict):
                                await self._handle_order_event(order)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"[{self.token_key}] Message parse error: {e}")

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
                            logger.debug(f"Resolved contractId {contract_id} -> {symbol}")
                        return symbol
        except Exception as e:
            logger.warning(f"Failed to resolve contractId {contract_id}: {e}")
        return ''

    # ========================================================================
    # EVENT HANDLERS — DB writes are idempotent (safe to receive same event twice)
    # ========================================================================

    async def _handle_position_event(self, entity: dict):
        """Sync position netPos/netPrice with recorder_positions table."""
        account_id = entity.get('accountId')
        if not account_id:
            return

        net_pos = entity.get('netPos', 0)
        net_price = entity.get('netPrice')
        contract_id = entity.get('contractId')

        if not contract_id:
            return

        symbol = await self._resolve_symbol(contract_id)
        if not symbol:
            return

        symbol_root = _get_symbol_root(symbol)
        recorder_ids = _get_recorder_ids_for_subaccount(account_id)
        if not recorder_ids:
            return

        logger.info(f"[{self.token_key}] Position event: account={account_id} "
                     f"symbol={symbol} netPos={net_pos} netPrice={net_price}")

        try:
            conn = _get_pg_connection()
            if not conn:
                return
            cursor = conn.cursor()

            for recorder_id in recorder_ids:
                if net_pos == 0:
                    # Broker flat — close DB position
                    cursor.execute('''
                        UPDATE recorder_positions
                        SET total_quantity = 0, avg_entry_price = NULL, status = 'closed'
                        WHERE recorder_id = %s AND status = 'open'
                    ''', (recorder_id,))
                else:
                    # Update position to match broker
                    cursor.execute('''
                        UPDATE recorder_positions
                        SET total_quantity = %s, avg_entry_price = %s
                        WHERE recorder_id = %s AND status = 'open'
                    ''', (abs(net_pos), net_price, recorder_id))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[{self.token_key}] Position DB update error: {e}")

    async def _handle_fill_event(self, entity: dict):
        """Detect TP/SL fills and close recorded_trades accordingly."""
        account_id = entity.get('accountId')
        if not account_id:
            return

        contract_id = entity.get('contractId')
        action = entity.get('action', '')  # Buy or Sell
        qty = entity.get('qty', 0)
        price = entity.get('price', 0)
        order_id = entity.get('orderId')

        symbol = await self._resolve_symbol(contract_id) if contract_id else ''
        symbol_root = _get_symbol_root(symbol) if symbol else ''

        recorder_ids = _get_recorder_ids_for_subaccount(account_id)
        if not recorder_ids:
            return

        logger.info(f"[{self.token_key}] Fill event: account={account_id} "
                     f"symbol={symbol} action={action} qty={qty} price={price} "
                     f"orderId={order_id}")

        try:
            conn = _get_pg_connection()
            if not conn:
                return
            cursor = conn.cursor()

            for recorder_id in recorder_ids:
                # Check if this fill matches a TP order
                cursor.execute('''
                    SELECT id, side, tp_order_id, tp_price, quantity
                    FROM recorded_trades
                    WHERE recorder_id = %s AND status = 'open'
                    ORDER BY id DESC LIMIT 1
                ''', (recorder_id,))
                trade = cursor.fetchone()
                if not trade:
                    continue

                trade_id = trade[0]
                trade_side = trade[1]
                tp_order_id = trade[2]
                tp_price = trade[3]
                trade_qty = trade[4]

                # Determine if this fill is a TP/SL (opposite direction to position)
                is_tp_fill = False
                if trade_side == 'LONG' and action == 'Sell':
                    is_tp_fill = True
                elif trade_side == 'SHORT' and action == 'Buy':
                    is_tp_fill = True

                if is_tp_fill:
                    # Check if it's the TP order specifically
                    is_tp_order_match = False
                    if tp_order_id and order_id and str(tp_order_id) == str(order_id):
                        is_tp_order_match = True

                    # Or if fill price matches TP price (within 1 tick tolerance)
                    if tp_price and price:
                        tick = _get_tick_size(symbol)
                        if abs(float(price) - float(tp_price)) <= tick * 2:
                            is_tp_order_match = True

                    if is_tp_order_match:
                        exit_reason = 'tp_filled_ws'
                    else:
                        exit_reason = 'sl_filled_ws'

                    # Full exit: close the trade
                    if qty >= trade_qty:
                        cursor.execute('''
                            UPDATE recorded_trades
                            SET status = 'closed', exit_reason = %s,
                                exit_price = %s, exit_time = NOW(), updated_at = NOW()
                            WHERE id = %s AND status = 'open'
                        ''', (exit_reason, price, trade_id))

                        cursor.execute('''
                            UPDATE recorder_positions
                            SET total_quantity = 0, avg_entry_price = NULL, status = 'closed'
                            WHERE recorder_id = %s AND status = 'open'
                        ''', (recorder_id,))

                        logger.info(f"[{self.token_key}] Closed trade {trade_id}: "
                                     f"{exit_reason} @ {price}")
                    else:
                        # Partial exit: reduce quantity
                        new_qty = trade_qty - qty
                        cursor.execute('''
                            UPDATE recorded_trades
                            SET quantity = %s, updated_at = NOW()
                            WHERE id = %s AND status = 'open'
                        ''', (new_qty, trade_id))

                        cursor.execute('''
                            UPDATE recorder_positions
                            SET total_quantity = %s
                            WHERE recorder_id = %s AND status = 'open'
                        ''', (new_qty, recorder_id))

                        logger.info(f"[{self.token_key}] Partial fill on trade {trade_id}: "
                                     f"-{qty} -> {new_qty} remaining")

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[{self.token_key}] Fill DB update error: {e}")

    async def _handle_order_event(self, entity: dict):
        """Track TP order IDs and detect cancellations."""
        account_id = entity.get('accountId')
        if not account_id:
            return

        order_id = entity.get('id') or entity.get('orderId')
        order_status = entity.get('ordStatus', '') or ''
        order_type = entity.get('ordType') or entity.get('orderType') or ''
        order_action = entity.get('action', '')
        order_price = entity.get('price')
        contract_id = entity.get('contractId')

        # Only care about limit orders (potential TPs)
        if 'limit' not in order_type.lower():
            return

        recorder_ids = _get_recorder_ids_for_subaccount(account_id)
        if not recorder_ids:
            return

        # If order is being accepted/working, check if it's a TP and store the ID
        if order_status in ['Working', 'New', 'Accepted'] and order_price and order_id:
            try:
                conn = _get_pg_connection()
                if not conn:
                    return
                cursor = conn.cursor()

                for recorder_id in recorder_ids:
                    # Check if this matches the expected TP price
                    cursor.execute('''
                        SELECT id, tp_price, side, tp_order_id
                        FROM recorded_trades
                        WHERE recorder_id = %s AND status = 'open'
                        ORDER BY id DESC LIMIT 1
                    ''', (recorder_id,))
                    trade = cursor.fetchone()
                    if not trade:
                        continue

                    trade_id = trade[0]
                    tp_price = trade[1]
                    trade_side = trade[2]
                    existing_tp_id = trade[3]

                    # Match: opposite-direction limit at TP price
                    is_tp_match = False
                    if tp_price and order_price:
                        tick = _get_tick_size(str(contract_id))
                        if abs(float(order_price) - float(tp_price)) <= tick * 2:
                            if (trade_side == 'LONG' and order_action == 'Sell') or \
                               (trade_side == 'SHORT' and order_action == 'Buy'):
                                is_tp_match = True

                    if is_tp_match and (not existing_tp_id or str(existing_tp_id) != str(order_id)):
                        cursor.execute('''
                            UPDATE recorded_trades
                            SET tp_order_id = %s, updated_at = NOW()
                            WHERE id = %s
                        ''', (str(order_id), trade_id))
                        logger.info(f"[{self.token_key}] Tracked TP order {order_id} "
                                     f"for trade {trade_id}")

                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"[{self.token_key}] Order tracking error: {e}")

        # If TP order was cancelled, clear it from DB
        elif order_status in ['Cancelled', 'Rejected', 'Expired'] and order_id:
            try:
                conn = _get_pg_connection()
                if not conn:
                    return
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE recorded_trades
                    SET tp_order_id = NULL, updated_at = NOW()
                    WHERE tp_order_id = %s AND status = 'open'
                ''', (str(order_id),))

                if cursor.rowcount > 0:
                    logger.info(f"[{self.token_key}] Cleared cancelled TP order {order_id}")

                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"[{self.token_key}] Order cancel tracking error: {e}")

    async def close(self):
        """Close the WebSocket connection."""
        self._running = False
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
        self.connected = False


# ============================================================================
# DATABASE HELPERS — Direct PostgreSQL (production only)
# ============================================================================

def _get_pg_connection():
    """Get a PostgreSQL connection. Returns None on failure."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return None
    try:
        import psycopg2
        db_url = database_url.replace('postgres://', 'postgresql://', 1)
        conn = psycopg2.connect(db_url, connect_timeout=5)
        conn.autocommit = False
        return conn
    except Exception as e:
        logger.error(f"PostgreSQL connection error: {e}")
        return None


def _get_recorder_ids_for_subaccount(subaccount_id: int) -> List[int]:
    """Look up recorder IDs for a given Tradovate subaccount ID."""
    return _sub_to_recorders.get(int(subaccount_id), [])


def _build_sub_to_recorders_map():
    """Build the subaccount_id -> [recorder_ids] mapping from DB."""
    global _sub_to_recorders
    try:
        conn = _get_pg_connection()
        if not conn:
            return
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT t.subaccount_id, t.recorder_id
            FROM traders t
            WHERE t.enabled = TRUE
              AND t.subaccount_id IS NOT NULL
        ''')

        new_map: Dict[int, List[int]] = {}
        for row in cursor.fetchall():
            sub_id = int(row[0])
            rec_id = int(row[1])
            if sub_id not in new_map:
                new_map[sub_id] = []
            if rec_id not in new_map[sub_id]:
                new_map[sub_id].append(rec_id)

        _sub_to_recorders = new_map
        conn.close()
        logger.info(f"Built subaccount->recorder map: {len(new_map)} subaccounts, "
                     f"{sum(len(v) for v in new_map.values())} recorder mappings")
    except Exception as e:
        logger.error(f"Error building sub-to-recorder map: {e}")


# ============================================================================
# LOAD ACTIVE ACCOUNT GROUPS (grouped by token)
# ============================================================================

def _load_account_groups() -> List[Dict]:
    """Load active accounts grouped by Tradovate token.

    Returns list of dicts, each representing one token group:
    {
        'token_key': str (last 8 chars for logging),
        'access_token': str,
        'is_demo': bool,
        'account_ids': [int, ...],       # accounts.id
        'subaccount_ids': [int, ...],     # traders.subaccount_id
    }
    """
    try:
        conn = _get_pg_connection()
        if not conn:
            return []
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT
                a.id as account_id,
                t.subaccount_id,
                a.tradovate_token,
                a.environment
            FROM traders t
            INNER JOIN accounts a ON t.account_id = a.id
            WHERE t.enabled = TRUE
              AND a.tradovate_token IS NOT NULL
              AND a.tradovate_token != ''
              AND t.subaccount_id IS NOT NULL
              AND a.broker IN ('tradovate', 'ninjatrader')
        ''')

        # Group by token
        token_groups: Dict[str, Dict] = {}
        for row in cursor.fetchall():
            account_id = row[0]
            subaccount_id = int(row[1])
            token = row[2]
            env = (row[3] or 'demo').lower()
            is_demo = env != 'live'

            if token not in token_groups:
                token_groups[token] = {
                    'token_key': f"...{token[-8:]}" if len(token) > 8 else token,
                    'access_token': token,
                    'is_demo': is_demo,
                    'account_ids': [],
                    'subaccount_ids': [],
                    'account_db_ids': [],
                }

            group = token_groups[token]
            if account_id not in group['account_ids']:
                group['account_ids'].append(account_id)
            if subaccount_id not in group['subaccount_ids']:
                group['subaccount_ids'].append(subaccount_id)
            if account_id not in group['account_db_ids']:
                group['account_db_ids'].append(account_id)

        conn.close()
        return list(token_groups.values())

    except Exception as e:
        logger.error(f"Error loading account groups: {e}")
        return []


def _get_fresh_token(account_id: int) -> Optional[str]:
    """Read latest Tradovate token from accounts table."""
    try:
        conn = _get_pg_connection()
        if not conn:
            return None
        cursor = conn.cursor()
        cursor.execute('SELECT tradovate_token FROM accounts WHERE id = %s', (account_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        logger.warning(f"Error reading fresh token for account {account_id}: {e}")
        return None


# ============================================================================
# MAIN ASYNC LOOP
# ============================================================================

async def _run_position_monitor():
    """Main async loop for position monitoring."""
    global _token_connections, _monitor_running

    _monitor_running = True
    logger.info("Starting Position WebSocket Monitor...")

    while _monitor_running:
        try:
            # Rebuild subaccount -> recorder mapping
            _build_sub_to_recorders_map()

            groups = _load_account_groups()

            if not groups:
                logger.info("No active Tradovate accounts for position monitoring — retrying in 30s")
                await asyncio.sleep(30)
                continue

            logger.info(f"Position monitor: {len(groups)} token group(s), "
                        f"{sum(len(g['subaccount_ids']) for g in groups)} total accounts")

            # Create connections for each token group
            tasks = []
            for group in groups:
                token_key = group['token_key']

                # Skip if already connected
                if token_key in _token_connections:
                    existing = _token_connections[token_key]
                    if existing.connected:
                        continue

                conn = AccountGroupConnection(
                    token_key=token_key,
                    access_token=group['access_token'],
                    is_demo=group['is_demo'],
                    account_ids=group['account_ids'],
                    subaccount_ids=group['subaccount_ids'],
                    account_db_ids=group['account_db_ids'],
                )

                _token_connections[token_key] = conn
                tasks.append(asyncio.create_task(_monitor_group(conn)))

            if tasks:
                # Wait for any task to complete (connection drop)
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    try:
                        task.result()
                    except Exception as e:
                        logger.error(f"Position monitor task error: {e}")
            else:
                await asyncio.sleep(15)

            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Position monitor main loop error: {e}")
            await asyncio.sleep(10)


async def _monitor_group(conn: AccountGroupConnection):
    """Monitor one token group with reconnection and exponential backoff."""
    backoff = 1
    max_backoff = 60

    while _monitor_running:
        try:
            # Refresh token from DB before each reconnect
            if conn.account_ids:
                fresh_token = _get_fresh_token(conn.account_ids[0])
                if fresh_token:
                    if fresh_token != conn.access_token:
                        logger.info(f"[{conn.token_key}] Refreshed token from DB")
                    conn.access_token = fresh_token

            success = await conn.connect()
            if success:
                backoff = 1
                conn._zero_data_windows = 0
                await conn.run()

            await conn.close()

            if not _monitor_running:
                break

            logger.info(f"[{conn.token_key}] Reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

        except Exception as e:
            logger.error(f"[{conn.token_key}] Monitor error: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


# ============================================================================
# PUBLIC API
# ============================================================================

def start_position_monitor():
    """Start the position monitor in a background daemon thread."""
    global _monitor_thread, _monitor_running

    if _monitor_running:
        logger.info("Position monitor already running")
        return

    def _thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_position_monitor())
        except Exception as e:
            logger.error(f"Position monitor thread error: {e}")
        finally:
            loop.close()

    _monitor_thread = threading.Thread(target=_thread_target, daemon=True,
                                       name="position-ws-monitor")
    _monitor_thread.start()
    logger.info("Position WebSocket monitor daemon thread started")


def stop_position_monitor():
    """Stop the position monitor."""
    global _monitor_running
    _monitor_running = False
    logger.info("Position monitor stopping...")


def get_position_monitor_status() -> Dict:
    """Get the current status of the position monitor."""
    status = {
        'running': _monitor_running,
        'connections': {},
        'subaccount_recorder_mappings': len(_sub_to_recorders),
    }
    for key, conn in _token_connections.items():
        status['connections'][key] = {
            'connected': conn.connected,
            'authenticated': conn.authenticated,
            'is_demo': conn.is_demo,
            'subaccount_ids': conn.subaccount_ids,
            'num_accounts': len(conn.subaccount_ids),
        }
    return status


def is_position_ws_connected(recorder_id: int) -> bool:
    """Check if a recorder's account has an active WS position monitor.

    Used by reconciliation daemon to skip auto-TP when WS is handling it.
    """
    # Find which subaccount this recorder maps to
    for sub_id, rec_ids in _sub_to_recorders.items():
        if recorder_id in rec_ids:
            # Check if any connection covers this subaccount
            for conn in _token_connections.values():
                if sub_id in conn.subaccount_ids and conn.connected and conn.authenticated:
                    return True
    return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Position Monitor Status:")
    print(f"  WebSockets available: {WEBSOCKETS_AVAILABLE}")
    print(f"  Monitor running: {_monitor_running}")
    print("\nTo start: from ws_position_monitor import start_position_monitor; start_position_monitor()")
