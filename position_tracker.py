#!/usr/bin/env python3
"""
WEBSOCKET POSITION TRACKER for Just.Trades
Real-time position and order tracking via Tradovate websocket.

Features:
- Track positions instantly (no API calls)
- Track working orders (TPs, SLs)
- Detect orphaned positions (no TP)
- Flip protection (block opposite signals)

All detection is INSTANT via websocket memory lookups.
"""

import asyncio
import websockets
import json
import logging
import ssl
import certifi
import os
from datetime import datetime, timezone
from typing import Dict, Optional, List
import threading
import time

# PostgreSQL support for Railway
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# SQLite fallback for local dev
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CONNECTION - PostgreSQL on Railway, SQLite locally
# ============================================================================

def _get_db_connection():
    """Get database connection - PostgreSQL on Railway, SQLite locally"""
    database_url = os.environ.get('DATABASE_URL')

    if database_url and PSYCOPG2_AVAILABLE:
        try:
            conn = psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
            return conn, 'postgres'
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return None, None
    else:
        try:
            conn = sqlite3.connect('just_trades.db')
            conn.row_factory = sqlite3.Row
            return conn, 'sqlite'
        except Exception as e:
            logger.error(f"SQLite connection failed: {e}")
            return None, None

# ============================================================================
# FUTURES SPECS - Tick sizes for calculations
# ============================================================================

FUTURES_SPECS = {
    'MES': {'tick_size': 0.25, 'tick_value': 1.25},
    'ES': {'tick_size': 0.25, 'tick_value': 12.5},
    'MNQ': {'tick_size': 0.25, 'tick_value': 0.5},
    'NQ': {'tick_size': 0.25, 'tick_value': 5.0},
    'MYM': {'tick_size': 1.0, 'tick_value': 0.5},
    'YM': {'tick_size': 1.0, 'tick_value': 5.0},
    'M2K': {'tick_size': 0.1, 'tick_value': 0.5},
    'RTY': {'tick_size': 0.1, 'tick_value': 5.0},
    'GC': {'tick_size': 0.1, 'tick_value': 10.0},
    'MGC': {'tick_size': 0.1, 'tick_value': 1.0},
    'SI': {'tick_size': 0.005, 'tick_value': 25.0},
    'CL': {'tick_size': 0.01, 'tick_value': 10.0},
    'MCL': {'tick_size': 0.01, 'tick_value': 1.0},
    'NG': {'tick_size': 0.001, 'tick_value': 10.0},
}

def get_tick_size(symbol: str) -> float:
    """Get tick size for a symbol"""
    base = ''.join(c for c in symbol.upper() if c.isalpha())
    return FUTURES_SPECS.get(base, {}).get('tick_size', 0.25)

# ============================================================================
# GLOBAL STATE - Updated in real-time by websocket
# ============================================================================

# Positions: (account_id, symbol) -> {net_pos, avg_price, side, contract_id, updated_at}
POSITIONS: Dict[tuple, dict] = {}

# Working orders: (account_id, symbol) -> [order_dict, ...]
WORKING_ORDERS: Dict[tuple, list] = {}

# When positions went flat: (account_id, symbol) -> timestamp
POSITION_CLOSED_AT: Dict[tuple, datetime] = {}

# Thread lock for safe access
_lock = threading.Lock()

# ============================================================================
# POSITION LOOKUPS - Instant, no API calls
# ============================================================================

def get_position(account_id: int, symbol: str) -> int:
    """Get current position size instantly (memory lookup)"""
    with _lock:
        key = (int(account_id), symbol.upper().replace('!', ''))
        base_symbol = ''.join(c for c in symbol.upper() if c.isalpha())

        # Exact match
        if key in POSITIONS:
            pos_data = POSITIONS[key]
            return pos_data.get('net_pos', 0) if isinstance(pos_data, dict) else 0

        # Base symbol match (MNQZ5 -> MNQ)
        for (acc, sym), pos_data in POSITIONS.items():
            if acc == int(account_id):
                sym_base = ''.join(c for c in sym if c.isalpha())
                if sym_base == base_symbol or sym.startswith(base_symbol):
                    return pos_data.get('net_pos', 0) if isinstance(pos_data, dict) else 0

        return 0


def get_position_details(account_id: int, symbol: str) -> Optional[dict]:
    """Get full position details including avg_price"""
    with _lock:
        key = (int(account_id), symbol.upper().replace('!', ''))
        base_symbol = ''.join(c for c in symbol.upper() if c.isalpha())

        if key in POSITIONS:
            return POSITIONS[key].copy()

        for (acc, sym), pos_data in POSITIONS.items():
            if acc == int(account_id):
                sym_base = ''.join(c for c in sym if c.isalpha())
                if sym_base == base_symbol or sym.startswith(base_symbol):
                    return pos_data.copy()

        return None


def is_flat(account_id: int, symbol: str) -> bool:
    """Check if position is flat"""
    return get_position(account_id, symbol) == 0


def recently_closed(account_id: int, symbol: str, seconds: float = 3.0) -> bool:
    """Check if position was closed within last N seconds (queued signal protection)"""
    with _lock:
        key = (int(account_id), symbol.upper())
        base_symbol = ''.join(c for c in symbol.upper() if c.isalpha())
        now = datetime.now(timezone.utc)

        # Check exact match
        if key in POSITION_CLOSED_AT:
            elapsed = (now - POSITION_CLOSED_AT[key]).total_seconds()
            if elapsed < seconds:
                return True

        # Check base symbol match
        for (acc, sym), closed_at in POSITION_CLOSED_AT.items():
            if acc == int(account_id):
                sym_base = ''.join(c for c in sym if c.isalpha())
                if sym_base == base_symbol:
                    elapsed = (now - closed_at).total_seconds()
                    if elapsed < seconds:
                        return True

        return False


def check_can_trade(account_id: int, symbol: str, side: str, quantity: int) -> tuple:
    """
    MAIN FUNCTION - Call before every order
    Returns: (allowed: bool, reason: str, adjusted_quantity: int)

    - Blocks orders if position just closed (queued signal protection)
    - Caps orders that would flip position
    """
    account_id = int(account_id)
    symbol_clean = symbol.upper().replace('!', '')
    side_upper = side.upper()

    # 1. Check if recently closed (block queued signals)
    if recently_closed(account_id, symbol_clean, seconds=3.0):
        return False, "Position just closed - blocking queued signal", 0

    # 2. Get current position
    net_pos = get_position(account_id, symbol_clean)

    # 3. Check if order would flip
    if net_pos > 0 and side_upper == 'SELL':
        if quantity > net_pos:
            return True, f"Capped sell to prevent flip ({quantity} -> {net_pos})", net_pos

    elif net_pos < 0 and side_upper == 'BUY':
        if quantity > abs(net_pos):
            return True, f"Capped buy to prevent flip ({quantity} -> {abs(net_pos)})", abs(net_pos)

    return True, "OK", quantity

# ============================================================================
# ORDER LOOKUPS - Instant, no API calls
# ============================================================================

def get_working_orders(account_id: int, symbol: str) -> list:
    """Get all working orders for a symbol"""
    with _lock:
        key = (int(account_id), symbol.upper().replace('!', ''))
        base_symbol = ''.join(c for c in symbol.upper() if c.isalpha())

        if key in WORKING_ORDERS:
            return WORKING_ORDERS[key].copy()

        for (acc, sym), orders in WORKING_ORDERS.items():
            if acc == int(account_id):
                sym_base = ''.join(c for c in sym if c.isalpha())
                if sym_base == base_symbol or sym.startswith(base_symbol):
                    return orders.copy()

        return []


def get_working_tp(account_id: int, symbol: str) -> Optional[dict]:
    """Get working TP order for a position (Limit order opposite to position)"""
    orders = get_working_orders(account_id, symbol)
    pos = get_position(account_id, symbol)

    if pos == 0:
        return None

    tp_side = 'Sell' if pos > 0 else 'Buy'

    for order in orders:
        order_type = (order.get('orderType') or order.get('ordType') or '').lower()
        order_side = order.get('action') or order.get('side') or ''

        if order_type == 'limit' and order_side.lower() == tp_side.lower():
            return order

    return None


def has_valid_tp(account_id: int, symbol: str) -> bool:
    """Check if position has a working TP order"""
    return get_working_tp(account_id, symbol) is not None

# ============================================================================
# ORPHAN DETECTION
# ============================================================================

def get_orphaned_positions() -> List[dict]:
    """Find positions WITHOUT a working TP order"""
    orphaned = []

    with _lock:
        for key, pos_data in POSITIONS.items():
            account_id, symbol = key
            net_pos = pos_data.get('net_pos', 0) if isinstance(pos_data, dict) else 0

            if net_pos == 0:
                continue

            tp = get_working_tp(account_id, symbol)
            if tp is None:
                orphaned.append({
                    'account_id': account_id,
                    'symbol': symbol,
                    'net_pos': net_pos,
                    'avg_price': pos_data.get('avg_price'),
                    'side': 'LONG' if net_pos > 0 else 'SHORT',
                    'issue': 'NO_TP'
                })

    return orphaned


def get_all_positions() -> List[dict]:
    """Get all current positions from memory"""
    positions = []

    with _lock:
        for key, pos_data in POSITIONS.items():
            account_id, symbol = key
            net_pos = pos_data.get('net_pos', 0) if isinstance(pos_data, dict) else 0

            if net_pos != 0:
                positions.append({
                    'account_id': account_id,
                    'symbol': symbol,
                    'net_pos': net_pos,
                    'avg_price': pos_data.get('avg_price'),
                    'side': 'LONG' if net_pos > 0 else 'SHORT',
                    'updated_at': pos_data.get('updated_at')
                })

    return positions


def verify_tp_price(account_id: int, symbol: str, expected_tp_ticks: int) -> Optional[dict]:
    """
    Verify TP order has correct price based on current avg entry.
    Returns None if TP is correct, or dict with details if wrong.

    Used after DCA to detect when TP needs updating.
    """
    if expected_tp_ticks <= 0:
        return None  # No TP expected

    pos = get_position_details(account_id, symbol)
    if not pos or pos.get('net_pos', 0) == 0:
        return None  # No position

    tp = get_working_tp(account_id, symbol)
    if not tp:
        return None  # No TP to verify (orphan detection handles this)

    avg_price = pos.get('avg_price')
    if not avg_price:
        return None  # Can't calculate without avg price

    net_pos = pos.get('net_pos', 0)
    tick_size = get_tick_size(symbol)

    # Calculate expected TP price
    if net_pos > 0:  # LONG - TP is above entry
        expected_tp_price = avg_price + (expected_tp_ticks * tick_size)
    else:  # SHORT - TP is below entry
        expected_tp_price = avg_price - (expected_tp_ticks * tick_size)

    # Get actual TP price
    actual_tp_price = tp.get('price') or tp.get('limitPrice')
    if not actual_tp_price:
        return None

    # Allow 1 tick tolerance
    price_diff = abs(actual_tp_price - expected_tp_price)
    if price_diff <= tick_size:
        return None  # TP is correct (within 1 tick)

    # TP is wrong!
    ticks_off = round(price_diff / tick_size)
    return {
        'account_id': account_id,
        'symbol': symbol,
        'net_pos': net_pos,
        'side': 'LONG' if net_pos > 0 else 'SHORT',
        'avg_price': avg_price,
        'expected_tp_price': round(expected_tp_price, 4),
        'actual_tp_price': actual_tp_price,
        'price_diff': round(price_diff, 4),
        'ticks_off': ticks_off,
        'tp_order_id': tp.get('id') or tp.get('orderId'),
        'issue': 'WRONG_TP_PRICE'
    }


# ============================================================================
# INTERNAL STATE UPDATES (called by websocket)
# ============================================================================

def _update_position(account_id: int, symbol: str, net_pos: int, avg_price: float = None, contract_id: int = None):
    """Update position from websocket data"""
    with _lock:
        key = (int(account_id), symbol.upper())
        old_data = POSITIONS.get(key, {})
        old_pos = old_data.get('net_pos', 0) if isinstance(old_data, dict) else 0

        if old_pos != net_pos or (avg_price and old_data.get('avg_price') != avg_price):
            POSITIONS[key] = {
                'net_pos': net_pos,
                'avg_price': avg_price,
                'side': 'LONG' if net_pos > 0 else 'SHORT' if net_pos < 0 else 'FLAT',
                'contract_id': contract_id,
                'symbol': symbol.upper(),
                'updated_at': datetime.now(timezone.utc)
            }

            if net_pos == 0 and old_pos != 0:
                POSITION_CLOSED_AT[key] = datetime.now(timezone.utc)
                if key in WORKING_ORDERS:
                    del WORKING_ORDERS[key]
                logger.info(f"WS POSITION CLOSED: {symbol} on {account_id} (was {old_pos})")
            elif net_pos != old_pos:
                logger.info(f"WS POSITION UPDATE: {symbol} on {account_id}: {old_pos} -> {net_pos} @ {avg_price}")


def _update_order(account_id: int, symbol: str, order: dict):
    """Update working order from websocket data"""
    with _lock:
        key = (int(account_id), symbol.upper())
        order_id = order.get('id') or order.get('orderId')
        status = (order.get('status') or order.get('ordStatus') or '').upper()

        if key not in WORKING_ORDERS:
            WORKING_ORDERS[key] = []

        # Remove old version
        WORKING_ORDERS[key] = [o for o in WORKING_ORDERS[key]
                               if o.get('id') != order_id and o.get('orderId') != order_id]

        # Add if still working
        if status in ['WORKING', 'NEW', 'PENDINGNEW', 'PENDING', 'ACCEPTED']:
            order['updated_at'] = datetime.now(timezone.utc)
            WORKING_ORDERS[key].append(order)

# ============================================================================
# TRADOVATE WEBSOCKET CONNECTION
# ============================================================================

class TradovatePositionWebsocket:
    """Persistent websocket for real-time position/order updates"""

    def __init__(self, access_token: str, account_id: int, demo: bool = True):
        self.access_token = access_token
        self.account_id = account_id
        self.demo = demo

        base = "demo" if demo else "live"
        self.ws_url = f"wss://{base}.tradovateapi.com/v1/websocket"

        self.ws = None
        self.running = False
        self.connected = False
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        self._contract_symbols: Dict[int, str] = {}

    async def connect(self) -> bool:
        """Connect and authorize"""
        try:
            logger.info(f"Connecting to {self.ws_url} for account {self.account_id}...")

            self.ws = await websockets.connect(
                self.ws_url,
                ssl=self.ssl_context,
                ping_interval=25,
                ping_timeout=10,
                close_timeout=5
            )
            self.connected = True

            # Wait for open frame
            await asyncio.wait_for(self.ws.recv(), timeout=10)

            # Authorize
            auth_msg = f"authorize\n1\n\n{self.access_token}"
            await self.ws.send(auth_msg)

            # Check auth response
            for _ in range(5):
                response = await asyncio.wait_for(self.ws.recv(), timeout=10)
                if response and ('"s":200' in response or '"i":1' in response):
                    logger.info(f"Websocket authorized for account {self.account_id}")
                    return True
                elif '"s":40' in response or 'error' in response.lower():
                    logger.error(f"Auth rejected for {self.account_id}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Connect error for account {self.account_id}: {e}")
            self.connected = False
            return False

    async def subscribe(self):
        """Subscribe to position/order updates"""
        try:
            sync_msg = f"user/syncrequest\n1\n\n{{\"accounts\":[{self.account_id}]}}"
            await self.ws.send(sync_msg)
            logger.info(f"Subscribed to updates for account {self.account_id}")
        except Exception as e:
            logger.error(f"Subscribe error: {e}")

    async def run(self):
        """Main loop"""
        self.running = True
        reconnect_delay = 1

        while self.running:
            try:
                if not self.connected or not self.ws:
                    if await self.connect():
                        await self.subscribe()
                        reconnect_delay = 1
                    else:
                        await asyncio.sleep(reconnect_delay)
                        reconnect_delay = min(reconnect_delay * 2, 30)
                        continue

                try:
                    msg = await asyncio.wait_for(self.ws.recv(), timeout=30)
                    await self._handle_message(msg)
                except asyncio.TimeoutError:
                    await self.ws.send("[]")  # Heartbeat

            except websockets.ConnectionClosed:
                logger.warning(f"Connection closed for {self.account_id}, reconnecting...")
                self.connected = False
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30)
            except Exception as e:
                logger.error(f"Error in run loop: {e}")
                self.connected = False
                await asyncio.sleep(5)

    async def _handle_message(self, msg: str):
        """Process incoming message"""
        if not msg or msg == "[]":
            return

        try:
            # Find JSON
            start = msg.find('[') if msg.find('[') != -1 else msg.find('{')
            if start == -1:
                return

            data = json.loads(msg[start:])

            # Debug: log message types we receive
            if isinstance(data, dict) and 'd' in data:
                d = data['d']
                if 'positions' in d:
                    logger.info(f"📨 WS received {len(d['positions'])} positions for account {self.account_id}")
                if 'orders' in d:
                    logger.info(f"📨 WS received {len(d['orders'])} orders for account {self.account_id}")

            await self._process_data(data)
        except json.JSONDecodeError:
            pass

    async def _process_data(self, data):
        """Process parsed data"""
        # Handle Tradovate sync response format: {"d": {"positions": [...], "orders": [...]}}
        if isinstance(data, dict):
            if 'd' in data:
                d = data['d']
                # Process positions array
                if 'positions' in d and isinstance(d['positions'], list):
                    for pos in d['positions']:
                        await self._process_item(pos)
                # Process orders array
                if 'orders' in d and isinstance(d['orders'], list):
                    for order in d['orders']:
                        await self._process_item(order)
                # Process contracts for symbol mapping
                if 'contracts' in d and isinstance(d['contracts'], list):
                    for contract in d['contracts']:
                        cid = contract.get('id')
                        name = contract.get('name')
                        if cid and name:
                            self._contract_symbols[cid] = name
                return

        # Handle flat array format
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    await self._process_item(item)
        elif isinstance(data, dict):
            await self._process_item(data)

    async def _process_item(self, item: dict):
        """Process single item - position or order"""
        entity_type = item.get('entityType', '').lower()

        # Position update - check multiple field names Tradovate uses
        if entity_type == 'position' or 'netPos' in item or 'netPosition' in item:
            account_id = item.get('accountId', self.account_id)
            net_pos = item.get('netPos') or item.get('netPosition') or 0
            avg_price = item.get('netPrice') or item.get('avgPrice') or item.get('averagePrice')
            contract_id = item.get('contractId')

            symbol = item.get('symbol') or item.get('contractSymbol') or item.get('name')
            if not symbol and contract_id:
                symbol = self._contract_symbols.get(contract_id)
                if not symbol:
                    # Contract ID format sometimes includes symbol
                    symbol = f"CONTRACT_{contract_id}"

            if symbol and net_pos != 0:
                logger.info(f"📊 Position update: {account_id} {symbol} = {net_pos} @ {avg_price}")

            if symbol:
                _update_position(account_id, symbol, int(net_pos), avg_price, contract_id)

        # Order update
        elif entity_type == 'order' or 'orderId' in item:
            account_id = item.get('accountId', self.account_id)
            contract_id = item.get('contractId')

            symbol = item.get('symbol') or item.get('contractSymbol')
            if not symbol and contract_id:
                symbol = self._contract_symbols.get(contract_id, f"C{contract_id}")

            if symbol:
                order_data = {
                    'id': item.get('id') or item.get('orderId'),
                    'orderId': item.get('orderId') or item.get('id'),
                    'accountId': account_id,
                    'symbol': symbol,
                    'orderType': item.get('orderType') or item.get('ordType'),
                    'action': item.get('action') or item.get('side'),
                    'price': item.get('price') or item.get('limitPrice'),
                    'quantity': item.get('qty') or item.get('quantity'),
                    'status': item.get('status') or item.get('ordStatus')
                }
                _update_order(account_id, symbol, order_data)

        # Contract info (cache symbol)
        elif entity_type == 'contract' or 'contractMaturityId' in item:
            contract_id = item.get('id') or item.get('contractId')
            symbol = item.get('name') or item.get('symbol')
            if contract_id and symbol:
                self._contract_symbols[contract_id] = symbol

    async def close(self):
        """Close connection"""
        self.running = False
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
        self.connected = False

# ============================================================================
# TRACKER MANAGER
# ============================================================================

class PositionTrackerManager:
    """Manages websocket connections for multiple accounts"""

    def __init__(self):
        self.trackers: Dict[int, TradovatePositionWebsocket] = {}
        self.tasks: Dict[int, asyncio.Task] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self.running = False

    def start(self, accounts: List[dict]):
        """Start tracking (NON-BLOCKING)"""
        if self.running:
            return

        self.running = True

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def main():
                tasks = []
                for acc in accounts:
                    account_id = acc['id']
                    token = acc['token']
                    demo = acc.get('demo', True)

                    tracker = TradovatePositionWebsocket(token, account_id, demo)
                    self.trackers[account_id] = tracker

                    task = asyncio.create_task(tracker.run())
                    self.tasks[account_id] = task
                    tasks.append(task)

                    logger.info(f"Started tracker for account {account_id}")

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            self._loop.run_until_complete(main())

        self._thread = threading.Thread(target=run_loop, daemon=True, name="PositionTracker")
        self._thread.start()
        logger.info(f"Position tracker started for {len(accounts)} accounts")

    def stop(self):
        """Stop all trackers"""
        self.running = False
        for tracker in self.trackers.values():
            if self._loop:
                asyncio.run_coroutine_threadsafe(tracker.close(), self._loop)
        self.trackers.clear()
        self.tasks.clear()

# ============================================================================
# REST SYNC (Initial load only - websocket for live updates)
# ============================================================================

async def _rest_sync_positions(accounts: List[dict]):
    """One-time REST sync for initial position load"""
    import aiohttp

    logger.info(f"🔄 Initial REST sync for {len(accounts)} accounts...")
    synced = 0

    for acc in accounts:
        account_id = acc['id']
        token = acc['token']
        is_demo = acc.get('demo', True)

        base_url = "https://demo.tradovateapi.com/v1" if is_demo else "https://live.tradovateapi.com/v1"

        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {token}"}

                # Get positions
                async with session.get(f"{base_url}/position/list", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        positions = await resp.json()
                        for pos in positions:
                            contract_id = pos.get('contractId')
                            net_pos = pos.get('netPos', 0)
                            avg_price = pos.get('netPrice')
                            acc_id = pos.get('accountId', account_id)

                            if net_pos != 0 and contract_id:
                                # Get contract symbol
                                async with session.get(f"{base_url}/contract/item?id={contract_id}", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as cresp:
                                    if cresp.status == 200:
                                        contract = await cresp.json()
                                        symbol = contract.get('name')
                                        if symbol:
                                            _update_position(acc_id, symbol, net_pos, avg_price, contract_id)
                                            logger.info(f"📊 Initial sync: {acc_id} {symbol} = {net_pos} @ {avg_price}")
                                            synced += 1

                # Get working orders
                async with session.get(f"{base_url}/order/list", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        orders = await resp.json()
                        for order in orders:
                            status = (order.get('ordStatus') or '').upper()
                            if status in ['WORKING', 'ACCEPTED']:
                                contract_id = order.get('contractId')
                                acc_id = order.get('accountId', account_id)

                                if contract_id:
                                    async with session.get(f"{base_url}/contract/item?id={contract_id}", headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as cresp:
                                        if cresp.status == 200:
                                            contract = await cresp.json()
                                            symbol = contract.get('name')
                                            if symbol:
                                                order_data = {
                                                    'id': order.get('id'),
                                                    'orderId': order.get('id'),
                                                    'accountId': acc_id,
                                                    'symbol': symbol,
                                                    'orderType': order.get('ordType'),
                                                    'action': order.get('action'),
                                                    'price': order.get('price'),
                                                    'quantity': order.get('qty'),
                                                    'status': status
                                                }
                                                _update_order(acc_id, symbol, order_data)
        except Exception as e:
            logger.debug(f"REST sync skipped for {account_id}: {e}")

    logger.info(f"✅ Initial REST sync complete: {synced} positions loaded")


def sync_positions_now():
    """Trigger REST sync (non-blocking, runs in background)"""
    global _manager
    if _manager and _manager._loop:
        accounts = _load_accounts_from_db()
        # Fire and forget - don't block waiting for result
        asyncio.run_coroutine_threadsafe(_rest_sync_positions(accounts), _manager._loop)
        return True
    return False


# ============================================================================
# STARTUP
# ============================================================================

_manager: Optional[PositionTrackerManager] = None

def start_position_tracker(accounts: List[dict] = None):
    """Start position tracking (NON-BLOCKING - runs in background thread)"""
    global _manager

    if _manager and _manager.running:
        logger.info("Position tracker already running")
        return _manager

    def _start_background():
        global _manager
        try:
            accts = accounts
            if not accts:
                accts = _load_accounts_from_db()

            if not accts:
                logger.warning("No accounts to track")
                return

            _manager = PositionTrackerManager()
            _manager.start(accts)

            # Initial REST sync after websockets start (gets current state)
            import time
            time.sleep(2)  # Give websockets time to initialize
            if _manager and _manager._loop:
                asyncio.run_coroutine_threadsafe(_rest_sync_positions(accts), _manager._loop)
        except Exception as e:
            logger.error(f"Position tracker startup failed: {e}")

    # Non-blocking startup
    thread = threading.Thread(target=_start_background, daemon=True)
    thread.start()
    logger.info("Position tracker startup initiated (background)")

    return None


def stop_position_tracker():
    """Stop position tracking"""
    global _manager
    if _manager:
        _manager.stop()
        _manager = None


def _load_accounts_from_db() -> List[dict]:
    """Load accounts with Tradovate tokens from database"""
    accounts = []

    try:
        conn, db_type = _get_db_connection()
        if not conn:
            return accounts

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, tradovate_token, tradovate_accounts, subaccounts
            FROM accounts
            WHERE tradovate_token IS NOT NULL
        """)

        for row in cursor.fetchall():
            token = row['tradovate_token']
            if not token:
                continue

            # Get subaccounts
            tradovate_accounts = []
            try:
                if row['tradovate_accounts']:
                    tradovate_accounts = json.loads(row['tradovate_accounts'])
            except:
                pass

            if not tradovate_accounts:
                try:
                    if row['subaccounts']:
                        tradovate_accounts = json.loads(row['subaccounts'])
                except:
                    pass

            for acc in tradovate_accounts:
                acc_id = acc.get('id')
                is_demo = acc.get('is_demo', True)
                if acc.get('environment'):
                    is_demo = acc['environment'].lower() == 'demo'

                if acc_id:
                    accounts.append({
                        'id': int(acc_id),
                        'token': token,
                        'demo': is_demo
                    })

        conn.close()
        logger.info(f"Loaded {len(accounts)} accounts for position tracking")

    except Exception as e:
        logger.error(f"Error loading accounts: {e}")

    return accounts


def get_tracker_status() -> dict:
    """Get tracker status for debugging"""
    global _manager

    positions_summary = {}
    for key, pos_data in POSITIONS.items():
        account_id, symbol = key
        net_pos = pos_data.get('net_pos', 0) if isinstance(pos_data, dict) else 0
        if net_pos != 0:
            tp = get_working_tp(account_id, symbol)
            positions_summary[str(key)] = {
                'net_pos': net_pos,
                'avg_price': pos_data.get('avg_price'),
                'side': pos_data.get('side'),
                'has_tp': tp is not None,
                'tp_price': tp.get('price') if tp else None
            }

    # Get connection status for each tracker
    connection_status = {}
    if _manager and _manager.trackers:
        for acc_id, tracker in _manager.trackers.items():
            connection_status[acc_id] = {
                'connected': tracker.connected if hasattr(tracker, 'connected') else False,
                'running': tracker.running if hasattr(tracker, 'running') else False
            }

    connected_count = sum(1 for s in connection_status.values() if s.get('connected'))

    return {
        'running': _manager.running if _manager else False,
        'accounts_tracked': list(_manager.trackers.keys()) if _manager else [],
        'accounts_connected': connected_count,
        'connection_status': connection_status,
        'positions': positions_summary,
        'working_orders': {str(k): v for k, v in WORKING_ORDERS.items()},
        'recent_closes': {str(k): v.isoformat() for k, v in POSITION_CLOSED_AT.items()}
    }


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("Position Tracker Module")
    print("=" * 50)
    print("This module provides websocket-based position tracking.")
    print("Import and call start_position_tracker() to begin.")
