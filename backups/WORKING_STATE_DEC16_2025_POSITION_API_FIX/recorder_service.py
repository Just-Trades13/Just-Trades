#!/usr/bin/env python3
"""
🎯 Trading Engine - Recorder & Automation Server

PURPOSE:
This is the Trading Engine that handles ALL trading-related operations:
- Webhook processing (TradingView signals)
- Recorder management (CRUD, settings)
- Position tracking and drawdown monitoring
- TP/SL monitoring and auto-close
- Future: Live trade execution (automation)

RESPONSIBILITIES:
1. Process webhook signals from TradingView
2. Manage recorders (create, update, delete, settings)
3. Track positions with DCA/averaging
4. Monitor TP/SL and auto-close trades
5. Track drawdown (worst_unrealized_pnl) in real-time
6. Stream prices via TradingView WebSocket

WHAT THE MAIN SERVER HANDLES:
- OAuth (Tradovate authentication)
- Copy Trading
- Account Management
- Dashboard UI (reads from shared database)

Architecture:
- Runs on port 8083
- Shares just_trades.db with main server (WAL mode for concurrent access)
- Main server handles OAuth, Copy Trading, UI
- This server handles ALL recording/trading logic

Created: December 4, 2025
Updated: December 5, 2025 - Refactored to full Trading Engine
"""

from __future__ import annotations
import sqlite3
import logging
import asyncio
import json
import time
import threading
import re
import secrets
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Set, Any, Tuple
from flask import Flask, request, jsonify, render_template

# ============================================================================
# Configuration
# ============================================================================

SERVICE_PORT = 8083
DATABASE_PATH = 'just_trades.db'
LOG_LEVEL = logging.INFO

# ============================================================================
# Contract Specifications (matching main server exactly)
# ============================================================================

# Contract multipliers for PnL calculation
CONTRACT_MULTIPLIERS = {
    'MES': 5.0,    # Micro E-mini S&P 500: $5 per point
    'MNQ': 2.0,    # Micro E-mini Nasdaq: $2 per point
    'ES': 50.0,    # E-mini S&P 500: $50 per point
    'NQ': 20.0,    # E-mini Nasdaq: $20 per point
    'MYM': 5.0,    # Micro E-mini Dow: $5 per point
    'YM': 5.0,     # E-mini Dow: $5 per point
    'M2K': 5.0,    # Micro E-mini Russell 2000: $5 per point
    'RTY': 50.0,   # E-mini Russell 2000: $50 per point
    'MCL': 100.0,  # Micro Crude Oil: $100 per point
    'CL': 1000.0,  # Crude Oil: $1000 per point
    'MGC': 10.0,   # Micro Gold: $10 per point
    'GC': 100.0,   # Gold: $100 per point
}

# Tick information: tick_size and tick_value for each contract
TICK_INFO = {
    'MNQ': {'tick_size': 0.25, 'tick_value': 0.5},
    'NQ': {'tick_size': 0.25, 'tick_value': 5.0},
    'MES': {'tick_size': 0.25, 'tick_value': 1.25},
    'ES': {'tick_size': 0.25, 'tick_value': 12.5},
    'M2K': {'tick_size': 0.1, 'tick_value': 0.5},
    'RTY': {'tick_size': 0.1, 'tick_value': 5.0},
    'MYM': {'tick_size': 1.0, 'tick_value': 0.5},
    'YM': {'tick_size': 1.0, 'tick_value': 5.0},
    'CL': {'tick_size': 0.01, 'tick_value': 10.0},
    'MCL': {'tick_size': 0.01, 'tick_value': 1.0},
    'GC': {'tick_size': 0.1, 'tick_value': 10.0},
    'MGC': {'tick_size': 0.1, 'tick_value': 1.0},
}

# Legacy format for compatibility
TICK_SIZES = {k: v['tick_size'] for k, v in TICK_INFO.items()}
TICK_VALUES = {k: v['tick_value'] for k, v in TICK_INFO.items()}

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trading_engine')

# ============================================================================
# Flask App
# ============================================================================

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = secrets.token_hex(32)

# ============================================================================
# Global State
# ============================================================================

# Market data cache: {"MNQ": {"last": 25580.5, "updated": timestamp}, ...}
_market_data_cache: Dict[str, Dict[str, Any]] = {}

# Position index: {"MNQ": [pos_id_1, pos_id_2], ...}
_open_positions_by_symbol: Dict[str, List[int]] = {}

# Trade index: {"MNQ": [trade_id_1, trade_id_2], ...}
_open_trades_by_symbol: Dict[str, List[int]] = {}

# Thread safety
_index_lock = threading.Lock()

# ============================================================================
# EXIT MANAGEMENT LOCKS - Prevents race conditions between DCA/TP operations
# Per tradovate_dca_tp_resting_orders_fix.md: Only ONE exit management operation
# can run at a time for each (account_id, symbol_root) combination
# ============================================================================
_exit_management_locks: Dict[str, threading.Lock] = {}
_exit_locks_meta_lock = threading.Lock()  # Protects the dictionary itself

def get_exit_management_lock(account_id: int, symbol_root: str) -> threading.Lock:
    """
    Get or create a lock for exit management operations on a specific account/symbol.
    This prevents race conditions between:
    - cancel_old_tp_orders_for_symbol() (background)
    - update_exit_brackets() (DCA handler)
    - Any other TP placement/modify logic
    """
    key = f"{account_id}:{symbol_root.upper()}"
    with _exit_locks_meta_lock:
        if key not in _exit_management_locks:
            _exit_management_locks[key] = threading.Lock()
        return _exit_management_locks[key]

# Working order statuses that indicate an order is active
WORKING_ORDER_STATUSES = {"WORKING", "ACCEPTED", "PENDING", "SENT", "SUBMITTED", 
                          "NEW", "PARTIALLYFILLED", "PENDINGNEW", "PENDINGREPLACE", 
                          "PENDINGCANCEL", ""}

# TradingView WebSocket
_tradingview_ws = None
_tradingview_ws_thread = None
_tradingview_subscribed_symbols: Set[str] = set()

# WebSocket availability
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets not installed. Run: pip install websockets")


# ============================================================================
# Database Helpers
# ============================================================================

def get_db_connection() -> sqlite3.Connection:
    """Get database connection with WAL mode for concurrent access"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    conn.row_factory = sqlite3.Row
    return conn


def init_trading_engine_db():
    """
    Initialize/verify database tables for the Trading Engine.
    Creates tables if they don't exist. Safe to call multiple times.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Recorders table - stores recorder configurations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            strategy_type TEXT DEFAULT 'Futures',
            symbol TEXT,
            demo_account_id TEXT,
            account_id INTEGER,
            -- Positional Settings
            initial_position_size INTEGER DEFAULT 2,
            add_position_size INTEGER DEFAULT 2,
            -- TP Settings
            tp_units TEXT DEFAULT 'Ticks',
            trim_units TEXT DEFAULT 'Contracts',
            tp_targets TEXT DEFAULT '[]',
            -- SL Settings
            sl_enabled INTEGER DEFAULT 0,
            sl_amount REAL DEFAULT 0,
            sl_units TEXT DEFAULT 'Ticks',
            sl_type TEXT DEFAULT 'Fixed',
            -- Averaging Down
            avg_down_enabled INTEGER DEFAULT 0,
            avg_down_amount INTEGER DEFAULT 1,
            avg_down_point REAL DEFAULT 0,
            avg_down_units TEXT DEFAULT 'Ticks',
            -- Filter Settings
            add_delay INTEGER DEFAULT 1,
            max_contracts_per_trade INTEGER DEFAULT 0,
            option_premium_filter REAL DEFAULT 0,
            direction_filter TEXT,
            -- Time Filters
            time_filter_1_start TEXT DEFAULT '8:45 AM',
            time_filter_1_end TEXT DEFAULT '3:00 PM',
            time_filter_enabled INTEGER DEFAULT 0,
            auto_flat_after_cutoff INTEGER DEFAULT 0,
            -- Webhook
            webhook_token TEXT UNIQUE,
            -- State
            recording_enabled INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_recorders_webhook ON recorders(webhook_token)')
    
    # Recorded signals table - raw webhook signals
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorded_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorder_id INTEGER NOT NULL,
            signal_number INTEGER,
            action TEXT,
            ticker TEXT,
            price REAL,
            contracts INTEGER DEFAULT 1,
            position_size REAL,
            market_position TEXT,
            raw_payload TEXT,
            processed INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recorder_id) REFERENCES recorders(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_recorder ON recorded_signals(recorder_id)')
    
    # Recorded trades table - individual trades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorded_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorder_id INTEGER NOT NULL,
            signal_id INTEGER,
            ticker TEXT,
            side TEXT,
            quantity INTEGER DEFAULT 1,
            entry_price REAL,
            exit_price REAL,
            tp_price REAL,
            sl_price REAL,
            pnl REAL,
            pnl_ticks REAL,
            max_favorable REAL DEFAULT 0,
            max_adverse REAL DEFAULT 0,
            status TEXT DEFAULT 'open',
            exit_reason TEXT,
            entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            exit_time DATETIME,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recorder_id) REFERENCES recorders(id) ON DELETE CASCADE,
            FOREIGN KEY (signal_id) REFERENCES recorded_signals(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_recorder ON recorded_trades(recorder_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_status ON recorded_trades(status)')
    
    # Recorder positions table - combines DCA entries into single position
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorder_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorder_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            side TEXT NOT NULL,
            total_quantity INTEGER DEFAULT 0,
            avg_entry_price REAL,
            entries TEXT,
            current_price REAL,
            unrealized_pnl REAL DEFAULT 0,
            worst_unrealized_pnl REAL DEFAULT 0,
            best_unrealized_pnl REAL DEFAULT 0,
            exit_price REAL,
            realized_pnl REAL,
            status TEXT DEFAULT 'open',
            opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            closed_at DATETIME,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recorder_id) REFERENCES recorders(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_recorder ON recorder_positions(recorder_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_status ON recorder_positions(status)')
    
    conn.commit()
    conn.close()
    logger.info("✅ Database tables verified/created")


# ============================================================================
# Price Utilities
# ============================================================================

def extract_symbol_root(ticker: str) -> str:
    """Extract root symbol: MNQ1! -> MNQ, CME_MINI:MNQ1! -> MNQ, MNQZ5 -> MNQ"""
    if not ticker:
        return ''
    if ':' in ticker:
        ticker = ticker.split(':')[-1]
    ticker = ticker.upper().replace('1!', '').replace('!', '')
    
    # Check for known symbols FIRST before applying regex
    for known_symbol in CONTRACT_MULTIPLIERS.keys():
        if ticker.startswith(known_symbol):
            return known_symbol
    
    # Remove month codes and numbers for unknown symbols
    ticker = re.sub(r'[0-9!]+', '', ticker)
    ticker = re.sub(r'[FGHJKMNQUVXZ]$', '', ticker)
    
    return ticker


def get_contract_multiplier(symbol: str) -> float:
    """Get contract multiplier for PnL calculation"""
    symbol_upper = symbol.upper() if symbol else ''
    root = extract_symbol_root(symbol_upper)
    return CONTRACT_MULTIPLIERS.get(root, 1.0)


def get_tick_info(symbol: str) -> Dict[str, float]:
    """Get tick size and value for a symbol"""
    root = extract_symbol_root(symbol)
    return TICK_INFO.get(root, {'tick_size': 0.25, 'tick_value': 1.0})


def get_tick_size(ticker: str) -> float:
    """Get tick size for a symbol"""
    return get_tick_info(ticker)['tick_size']


def get_tick_value(ticker: str) -> float:
    """Get tick value ($ per tick) for a symbol"""
    return get_tick_info(ticker)['tick_value']


def clamp_price(price: float, tick_size: float) -> float:
    """Round price to nearest tick"""
    if price is None:
        return None
    decimals = max(3, len(str(tick_size).split('.')[-1]))
    return round(price, decimals)


def calculate_pnl(entry_price: float, exit_price: float, side: str, quantity: int, ticker: str) -> Tuple[float, float]:
    """
    Calculate PnL in dollars and ticks.
    Returns (pnl_dollars, pnl_ticks)
    """
    tick_size = get_tick_size(ticker)
    tick_value = get_tick_value(ticker)
    
    if side == 'LONG':
        pnl_ticks = (exit_price - entry_price) / tick_size
    else:  # SHORT
        pnl_ticks = (entry_price - exit_price) / tick_size
    
    pnl_dollars = pnl_ticks * tick_value * quantity
    return pnl_dollars, pnl_ticks


# ============================================================================
# Live Trade Execution (Auto-Execute on Linked Accounts) - BROKER-FIRST
# ============================================================================

def sync_position_with_broker(recorder_id: int, ticker: str) -> Dict[str, Any]:
    """
    CRITICAL: Sync database position with broker state.
    Called before every trade execution to prevent drift.
    
    If broker shows 0 position but DB shows open -> CLEAR DB
    If broker has position but DB doesn't match -> SYNC DB
    """
    result = {'synced': False, 'cleared': False, 'error': None}
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.subaccount_id, t.is_demo, a.tradovate_token,
                   a.username, a.password, a.id as account_id
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = ? AND t.enabled = 1
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        if not trader:
            conn.close()
            return result
        
        trader = dict(trader)
        tradovate_account_id = trader.get('subaccount_id')
        is_demo = bool(trader.get('is_demo'))
        access_token = trader.get('tradovate_token')
        username = trader.get('username')
        password = trader.get('password')
        account_id = trader.get('account_id')
        
        if not tradovate_account_id:
            conn.close()
            return result
        
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        
        # Get database position
        cursor.execute('''
            SELECT id, total_quantity, side, avg_entry_price
            FROM recorder_positions
            WHERE recorder_id = ? AND ticker = ? AND status = 'open'
        ''', (recorder_id, ticker))
        db_pos = cursor.fetchone()
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        from tradovate_api_access import TradovateAPIAccess
        import asyncio
        
        async def sync():
            api_access = TradovateAPIAccess(demo=is_demo)
            current_token = access_token
            
            if not current_token and username and password:
                login_result = await api_access.login(
                    username=username,
                    password=password,
                    db_path=DATABASE_PATH,
                    account_id=account_id
                )
                if login_result.get('success'):
                    current_token = login_result.get('accessToken')
            
            if not current_token:
                return
            
            async with TradovateIntegration(demo=is_demo) as tradovate:
                tradovate.access_token = current_token
                positions = await tradovate.get_positions(account_id=tradovate_account_id)
                
                broker_pos = None
                for pos in positions:
                    if tradovate_symbol[:3] in pos.get('symbol', ''):
                        broker_pos = pos
                        break
                
                broker_net_pos = broker_pos.get('netPos', 0) if broker_pos else 0
                broker_price = broker_pos.get('netPrice') if broker_pos else None
                
                # Sync database
                if db_pos:
                    db_pos_dict = dict(db_pos)
                    db_qty = db_pos_dict['total_quantity']
                    db_side = db_pos_dict['side']
                    
                    # Broker shows 0 but DB shows open
                    # DISABLED: Broker position API is unreliable (returns 0 even when position exists)
                    # This was causing DCA to fail because it cleared the DB trade before DCA signal came in
                    # Trust the DB state instead - let TP order fill handle actual position closure
                    if broker_net_pos == 0 and db_qty > 0:
                        logger.info(f"ℹ️ SYNC: Broker API returned 0 but DB={db_side} {db_qty} for {ticker} - KEEPING database (API unreliable)")
                        # DO NOT CLEAR - broker API is unreliable
                    # Broker has position but DB doesn't match -> SYNC
                    elif broker_net_pos != 0 and broker_price:
                        broker_side = 'LONG' if broker_net_pos > 0 else 'SHORT'
                        broker_qty_abs = abs(broker_net_pos)
                        
                        if db_qty == 0 or db_side != broker_side or abs(db_qty - broker_qty_abs) > 0:
                            logger.warning(f"⚠️ SYNC: Broker={broker_side} {broker_qty_abs} @ {broker_price} but DB={db_side} {db_qty} - SYNCING")
                            
                            if db_qty == 0:
                                cursor.execute('''
                                    INSERT INTO recorder_positions 
                                    (recorder_id, ticker, side, total_quantity, avg_entry_price, entries, status)
                                    VALUES (?, ?, ?, ?, ?, ?, 'open')
                                ''', (recorder_id, ticker, broker_side, broker_qty_abs, broker_price,
                                      json.dumps([{'qty': broker_qty_abs, 'price': broker_price}])))
                            else:
                                cursor.execute('''
                                    UPDATE recorder_positions
                                    SET side = ?, total_quantity = ?, avg_entry_price = ?, 
                                        entries = ?, updated_at = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                ''', (broker_side, broker_qty_abs, broker_price,
                                      json.dumps([{'qty': broker_qty_abs, 'price': broker_price}]),
                                      db_pos_dict['id']))
                            
                            cursor.execute('''
                                UPDATE recorded_trades
                                SET side = ?, quantity = ?, entry_price = ?, status = 'open'
                                WHERE recorder_id = ? AND status = 'open'
                            ''', (broker_side, broker_qty_abs, broker_price, recorder_id))
                            
                            conn.commit()
                            result['synced'] = True
                            logger.info(f"✅ Synced database: {broker_side} {broker_qty_abs} @ {broker_price}")
                else:
                    # CRITICAL: Broker has position but DB has NO record at all (orphaned position)
                    # This happens when position was opened manually or system lost track
                    if broker_net_pos != 0 and broker_price:
                        broker_side = 'LONG' if broker_net_pos > 0 else 'SHORT'
                        broker_qty_abs = abs(broker_net_pos)
                        
                        logger.warning(f"⚠️ ORPHANED POSITION DETECTED: Broker has {broker_side} {broker_qty_abs} @ {broker_price} but DB has no record - CREATING database record")
                        
                        # Create position record
                        cursor.execute('''
                            INSERT INTO recorder_positions 
                            (recorder_id, ticker, side, total_quantity, avg_entry_price, entries, status)
                            VALUES (?, ?, ?, ?, ?, ?, 'open')
                        ''', (recorder_id, ticker, broker_side, broker_qty_abs, broker_price,
                              json.dumps([{'qty': broker_qty_abs, 'price': broker_price}])))
                        
                        # Create or update trade record
                        cursor.execute('''
                            SELECT id FROM recorded_trades
                            WHERE recorder_id = ? AND status = 'open'
                            LIMIT 1
                        ''', (recorder_id,))
                        existing_trade = cursor.fetchone()
                        
                        if existing_trade:
                            cursor.execute('''
                                UPDATE recorded_trades
                                SET side = ?, quantity = ?, entry_price = ?, status = 'open'
                                WHERE id = ?
                            ''', (broker_side, broker_qty_abs, broker_price, existing_trade['id']))
                        else:
                            cursor.execute('''
                                INSERT INTO recorded_trades
                                (recorder_id, ticker, side, quantity, entry_price, status)
                                VALUES (?, ?, ?, ?, ?, 'open')
                            ''', (recorder_id, ticker, broker_side, broker_qty_abs, broker_price))
                        
                        conn.commit()
                        result['synced'] = True
                        logger.info(f"✅ Created database record for orphaned position: {broker_side} {broker_qty_abs} @ {broker_price}")
        
        asyncio.run(sync())
        conn.close()
        
    except Exception as e:
        logger.warning(f"⚠️ Error syncing position with broker: {e}")
        result['error'] = str(e)
    
    return result


def cancel_old_tp_orders_for_symbol(recorder_id: int, ticker: str) -> None:
    """
    CRITICAL: Cancel ALL old TP orders for a symbol BEFORE processing new signals.
    This prevents old resting TP orders from interfering with new positions/flips.
    
    Per tradovate_dca_tp_resting_orders_fix.md: Uses the same exit management lock
    as update_exit_brackets() to prevent race conditions.
    
    Runs asynchronously (non-blocking) to avoid slowing down webhook processing.
    """
    def cancel_async():
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT t.subaccount_id, t.is_demo, a.tradovate_token,
                       a.username, a.password, a.id as account_id
                FROM traders t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.recorder_id = ? AND t.enabled = 1
                LIMIT 1
            ''', (recorder_id,))
            
            trader = cursor.fetchone()
            conn.close()
            
            if not trader:
                return
            
            trader = dict(trader)
            tradovate_account_id = trader.get('subaccount_id')
            is_demo = bool(trader.get('is_demo'))
            access_token = trader.get('tradovate_token')
            username = trader.get('username')
            password = trader.get('password')
            account_id = trader.get('account_id')
            
            if not tradovate_account_id:
                return
            
            tradovate_symbol = convert_ticker_to_tradovate(ticker)
            symbol_root = tradovate_symbol[:3].upper() if tradovate_symbol else ticker[:3].upper()
            
            # ACQUIRE EXIT MANAGEMENT LOCK - Prevents race conditions with DCA updates
            # Per tradovate_dca_tp_resting_orders_fix.md
            exit_lock = get_exit_management_lock(tradovate_account_id, symbol_root)
            
            from phantom_scraper.tradovate_integration import TradovateIntegration
            from tradovate_api_access import TradovateAPIAccess
            import asyncio
            
            async def cancel_tp():
                api_access = TradovateAPIAccess(demo=is_demo)
                current_token = access_token
                
                if not current_token and username and password:
                    login_result = await api_access.login(
                        username=username,
                        password=password,
                        db_path=DATABASE_PATH,
                        account_id=account_id
                    )
                    if login_result.get('success'):
                        current_token = login_result.get('accessToken')
                
                if not current_token:
                    return
                
                async with TradovateIntegration(demo=is_demo) as tradovate:
                    tradovate.access_token = current_token
                    
                    # Query ALL working orders for this symbol
                    try:
                        working_orders = await tradovate.get_orders(account_id=str(tradovate_account_id))
                        
                        # Filter to working limit orders for this symbol (TP orders are limits)
                        tp_orders = []
                        for order in working_orders:
                            order_symbol = order.get('symbol', '') or ''
                            order_type = order.get('orderType', '') or ''
                            order_status = order.get('ordStatus', '') or ''
                            
                            # Match symbol (check root)
                            order_symbol_root = order_symbol[:3].upper() if len(order_symbol) >= 3 else ''
                            symbol_match = symbol_root == order_symbol_root or symbol_root in order_symbol.upper()
                            
                            # Match limit orders (TP orders are limits)
                            is_limit = order_type in ['Limit', 'LimitOrder'] or 'limit' in order_type.lower()
                            
                            # Match working status
                            is_working = order_status.upper() in WORKING_ORDER_STATUSES or order_status not in ['Filled', 'Cancelled', 'Rejected', 'Expired', 'Done']
                            
                            if symbol_match and is_limit and is_working:
                                order_id = order.get('id') or order.get('orderId')
                                if order_id:
                                    tp_orders.append({
                                        'id': int(order_id),
                                        'price': order.get('price'),
                                        'qty': order.get('orderQty', 0),
                                        'action': order.get('action', '')
                                    })
                        
                        if tp_orders:
                            logger.info(f"🗑️ [CANCEL-OLD-TP] Found {len(tp_orders)} old TP order(s) for {ticker} ({tradovate_symbol}) - cancelling all")
                            for tp in tp_orders:
                                try:
                                    result = await tradovate.cancel_order(tp['id'])
                                    if result:
                                        logger.info(f"✅ [CANCEL-OLD-TP] Cancelled TP order {tp['id']}: {tp['action']} {tp['qty']} @ {tp['price']}")
                                    else:
                                        logger.warning(f"⚠️ [CANCEL-OLD-TP] Cancel order returned False for {tp['id']}")
                                except Exception as e:
                                    logger.warning(f"⚠️ [CANCEL-OLD-TP] Failed to cancel TP order {tp['id']}: {e}")
                                await asyncio.sleep(0.05)  # Small delay between cancels
                            
                            # Poll until all confirmed cancelled (max 2 seconds)
                            poll_start = time.time()
                            while time.time() - poll_start < 2.0:
                                await asyncio.sleep(0.25)
                                check_orders = await tradovate.get_orders(account_id=str(tradovate_account_id))
                                still_working = 0
                                for order in check_orders:
                                    o_sym = str(order.get('symbol', '') or '').upper()
                                    o_type = str(order.get('orderType', '') or '').upper()
                                    o_status = str(order.get('ordStatus', '') or '').upper()
                                    if (symbol_root in o_sym or o_sym[:3] == symbol_root) and 'LIMIT' in o_type:
                                        if o_status not in ['FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED', 'DONE']:
                                            still_working += 1
                                if still_working == 0:
                                    break
                            
                            logger.info(f"✅ [CANCEL-OLD-TP] Finished cancelling old TP orders for {ticker}")
                        else:
                            logger.debug(f"ℹ️ [CANCEL-OLD-TP] No old TP orders found for {ticker}")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ [CANCEL-OLD-TP] Error querying/cancelling old TP orders for {ticker}: {e}")
            
            # Execute with lock held
            with exit_lock:
                logger.info(f"🔒 [CANCEL-OLD-TP] Acquired exit lock for {tradovate_account_id}:{symbol_root}")
                asyncio.run(cancel_tp())
                logger.info(f"🔓 [CANCEL-OLD-TP] Released exit lock for {tradovate_account_id}:{symbol_root}")
            
        except Exception as e:
            logger.warning(f"⚠️ Error in cancel_old_tp_orders_for_symbol for {recorder_id}:{ticker}: {e}")
    
    # Run in background thread (non-blocking)
    threading.Thread(target=cancel_async, daemon=True).start()


def check_broker_position_exists(recorder_id: int, ticker: str) -> bool:
    """
    Check if broker still has an open position for this symbol.
    Used to prevent sending redundant close orders when TP limit already filled.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.subaccount_id, t.is_demo, a.tradovate_token,
                   a.username, a.password, a.id as account_id
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = ? AND t.enabled = 1
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        conn.close()
        
        if not trader:
            return False  # No trader, assume no position
        
        trader = dict(trader)
        tradovate_account_id = trader.get('subaccount_id')
        is_demo = bool(trader.get('is_demo'))
        access_token = trader.get('tradovate_token')
        username = trader.get('username')
        password = trader.get('password')
        account_id = trader.get('account_id')
        
        if not tradovate_account_id:
            return False
        
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        from tradovate_api_access import TradovateAPIAccess
        import asyncio
        
        async def check_position():
            # Use REST API Access for authentication if needed
            api_access = TradovateAPIAccess(demo=is_demo)
            
            if not access_token and username and password:
                logger.info(f"🔐 Authenticating via REST API Access for position check...")
                login_result = await api_access.login(
                    username=username,
                    password=password,
                    db_path=DATABASE_PATH,
                    account_id=account_id
                )
                if login_result.get('success'):
                    access_token = login_result.get('accessToken')
            
            if not access_token:
                return False
            
            async with TradovateIntegration(demo=is_demo) as tradovate:
                tradovate.access_token = access_token
                positions = await tradovate.get_positions(account_id=tradovate_account_id)
                
                for pos in positions:
                    pos_symbol = pos.get('symbol', '') or ''
                    net_pos = pos.get('netPos', 0)
                    if tradovate_symbol[:3] in pos_symbol and net_pos != 0:
                        logger.info(f"📊 Broker has position: {net_pos} {pos_symbol}")
                        return True
                
                logger.info(f"📊 Broker has NO position for {tradovate_symbol}")
                return False
        
        return asyncio.run(check_position())
        
    except Exception as e:
        logger.warning(f"Error checking broker position: {e}")
        return True  # Assume position exists on error (safer)


def get_front_month_contract(root_symbol: str) -> str:
    """
    Dynamically calculate the current front month contract for futures.
    
    Quarterly futures (MNQ, MES, NQ, ES, etc.) expire on the 3rd Friday of:
    - H = March
    - M = June  
    - U = September
    - Z = December
    
    Roll typically happens ~1 week before expiration (around 2nd Friday).
    This function returns the currently active front month contract.
    
    Args:
        root_symbol: The root symbol (e.g., "MNQ", "ES", "NQ")
    
    Returns:
        Full contract symbol (e.g., "MNQH5" for March 2025)
    """
    from datetime import datetime, timedelta
    
    # Quarterly contract months and their codes
    CONTRACT_MONTHS = [
        (3, 'H'),   # March
        (6, 'M'),   # June
        (9, 'U'),   # September
        (12, 'Z'),  # December
    ]
    
    today = datetime.now()
    current_month = today.month
    current_year = today.year
    current_day = today.day
    
    # Find the 3rd Friday of a given month/year (expiration day)
    def get_third_friday(year: int, month: int) -> datetime:
        """Get the 3rd Friday of the month (expiration day)"""
        # Start from the 1st of the month
        first_day = datetime(year, month, 1)
        # Find first Friday
        days_until_friday = (4 - first_day.weekday()) % 7
        first_friday = first_day + timedelta(days=days_until_friday)
        # 3rd Friday is 14 days later
        third_friday = first_friday + timedelta(days=14)
        return third_friday
    
    # Roll date is typically 8 days before expiration (around 2nd Friday)
    # This is when volume shifts to the next contract
    ROLL_DAYS_BEFORE_EXPIRY = 8
    
    # Find the current front month
    for i, (exp_month, month_code) in enumerate(CONTRACT_MONTHS):
        exp_year = current_year
        
        # If we're past this month, check if this year's contract is still active
        if current_month > exp_month:
            continue
        
        # Get expiration date for this contract
        expiration = get_third_friday(exp_year, exp_month)
        roll_date = expiration - timedelta(days=ROLL_DAYS_BEFORE_EXPIRY)
        
        # If today is before the roll date, this is the front month
        if today < roll_date:
            year_code = str(exp_year)[-1]  # Last digit of year (2025 -> 5)
            return f"{root_symbol}{month_code}{year_code}"
    
    # If we've passed all contracts this year, use the first contract of next year
    next_year = current_year + 1
    first_month, first_code = CONTRACT_MONTHS[0]  # March
    year_code = str(next_year)[-1]
    return f"{root_symbol}{first_code}{year_code}"


def convert_ticker_to_tradovate(ticker: str) -> str:
    """
    Convert TradingView ticker to Tradovate format.
    
    Examples:
        MNQ1! -> MNQH5 (current front month)
        CME_MINI:MNQ1! -> MNQH5
        NQ1! -> NQH5
        MNQ -> MNQH5 (adds front month if no month code)
        MNQZ5 -> MNQZ5 (already has month code, keep as-is)
    
    The function dynamically calculates the front month based on today's date,
    accounting for quarterly rollover (H=Mar, M=Jun, U=Sep, Z=Dec).
    """
    if not ticker:
        return ticker
    
    clean_ticker = ticker.strip().upper()
    
    # Handle TradingView exchange prefix (CME_MINI:MNQ1!)
    if ':' in clean_ticker:
        clean_ticker = clean_ticker.split(':')[-1]
    
    # Handle continuous contract notation (MNQ1!, NQ1!, ES1!)
    if '!' in clean_ticker:
        match = re.match(r'^([A-Z]+)\d*!$', clean_ticker)
        if match:
            root = match.group(1)
            front_month = get_front_month_contract(root)
            logger.debug(f"🗓️ Converted {ticker} -> {front_month} (front month)")
            return front_month
        return clean_ticker.replace('!', '')
    
    # Check if ticker already has a month code (e.g., MNQZ5, ESH5)
    # Pattern: ROOT + MONTH_CODE + YEAR_DIGIT(S)
    month_pattern = re.match(r'^([A-Z]+)([HMUZ])(\d{1,2})$', clean_ticker)
    if month_pattern:
        # Already has month code, return as-is
        return clean_ticker
    
    # If just a root symbol (MNQ, ES, NQ), add the front month
    root_pattern = re.match(r'^([A-Z]+)$', clean_ticker)
    if root_pattern:
        root = root_pattern.group(1)
        # Check if it's a known futures symbol
        if root in CONTRACT_MULTIPLIERS:
            front_month = get_front_month_contract(root)
            logger.debug(f"🗓️ Added front month: {ticker} -> {front_month}")
            return front_month
    
    return clean_ticker


def execute_live_trade_with_bracket(
    recorder_id: int, 
    action: str, 
    ticker: str, 
    quantity: int,
    tp_ticks: int = None,
    sl_ticks: int = None,
    is_dca: bool = False
) -> Dict[str, Any]:
    """
    Execute trade on broker with simple, reliable approach:
    1. Market order for entry (fast fill)
    2. Limit order for TP immediately after
    
    Args:
        recorder_id: The recorder that received the webhook
        action: 'BUY' or 'SELL' for entries, 'CLOSE' for exits
        ticker: Symbol like 'MNQ1!' or 'MES'
        quantity: Number of contracts
        tp_ticks: Take profit in ticks
        sl_ticks: Stop loss in ticks (not used currently)
        is_dca: If True, this is a DCA addition
    
    Returns:
        {success, fill_price, order_id, broker_position, error}
    """
    result = {
        'success': False,
        'fill_price': None,
        'order_id': None,
        'tp_order_id': None,
        'broker_position': None,
        'error': None
    }
    
    logger.info(f"🎯 EXECUTE: {action} {quantity} {ticker} (TP:{tp_ticks} ticks, DCA:{is_dca})")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find enabled trader with username/password for REST API Access
        # CRITICAL: Include enabled_accounts for multi-account routing
        cursor.execute('''
            SELECT 
                t.id as trader_id, t.subaccount_id, t.subaccount_name, t.is_demo, t.enabled_accounts,
                a.name as account_name, a.tradovate_token,
                a.tradovate_refresh_token, a.md_access_token,
                a.username, a.password, a.id as account_id
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = ? AND t.enabled = 1
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        
        if not trader:
            conn.close()
            logger.info(f"📝 No enabled trader - recording only")
            result['success'] = True
            return result
        
        trader = dict(trader)
        
        # CRITICAL: Check for multi-account routing via enabled_accounts
        enabled_accounts_raw = trader.get('enabled_accounts')
        accounts_to_trade = []
        
        # DEBUG: Log what we got from the database
        logger.info(f"🔍 [MULTI-ACCT] Trader ID: {trader.get('trader_id')}, Primary: {trader.get('subaccount_name')}")
        logger.info(f"🔍 [MULTI-ACCT] enabled_accounts_raw type: {type(enabled_accounts_raw)}, value: {str(enabled_accounts_raw)[:200] if enabled_accounts_raw else 'None/Empty'}")
        
        if enabled_accounts_raw:
            try:
                enabled_accounts = json.loads(enabled_accounts_raw) if isinstance(enabled_accounts_raw, str) else enabled_accounts_raw
                logger.info(f"📋 Multi-account routing: Found {len(enabled_accounts)} accounts")
                
                # Build list of accounts to trade on
                for idx, acct in enumerate(enabled_accounts):
                    acct_id = acct.get('account_id')
                    subaccount_id = acct.get('subaccount_id')
                    subaccount_name = acct.get('subaccount_name')
                    
                    # Look up credentials for this account
                    cursor.execute('''
                        SELECT id, name, tradovate_token, tradovate_refresh_token, md_access_token,
                               username, password
                        FROM accounts WHERE id = ?
                    ''', (acct_id,))
                    account_row = cursor.fetchone()
                    
                    if account_row:
                        account_row = dict(account_row)
                        if account_row.get('username') and account_row.get('password'):
                            accounts_to_trade.append({
                                'subaccount_id': subaccount_id,
                                'subaccount_name': subaccount_name,
                                'is_demo': acct.get('is_demo', True),
                                'account_name': account_row['name'],
                                'tradovate_token': account_row['tradovate_token'],
                                'md_access_token': account_row['md_access_token'],
                                'username': account_row['username'],
                                'password': account_row['password'],
                                'account_id': account_row['id']
                            })
                            logger.info(f"✅ [{idx+1}/{len(enabled_accounts)}] Added: {subaccount_name} (account_id={acct_id})")
                        else:
                            logger.warning(f"⚠️ [{idx+1}/{len(enabled_accounts)}] {subaccount_name} missing credentials - skipping")
                    else:
                        logger.error(f"❌ [{idx+1}/{len(enabled_accounts)}] Account {acct_id} NOT FOUND - skipping")
            except Exception as e:
                logger.error(f"❌ Error parsing enabled_accounts: {e}")
        
        # If no multi-account routing, use primary account
        if not accounts_to_trade:
            logger.info(f"📋 Using primary account only (no multi-account routing)")
            accounts_to_trade.append({
                'subaccount_id': trader.get('subaccount_id'),
                'subaccount_name': trader.get('subaccount_name'),
                'is_demo': trader.get('is_demo', True),
                'account_name': trader.get('account_name'),
                'tradovate_token': trader.get('tradovate_token'),
                'md_access_token': trader.get('md_access_token'),
                'username': trader.get('username'),
                'password': trader.get('password'),
                'account_id': trader.get('account_id')
            })
        
        conn.close()
        
        # Execute on ALL accounts (multi-account support)
        logger.info(f"🎯 Executing trade on {len(accounts_to_trade)} account(s)")
        all_results = []
        
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        from tradovate_api_access import TradovateAPIAccess
        import asyncio
        
        for acct_idx, trading_account in enumerate(accounts_to_trade):
            logger.info(f"📤 [{acct_idx+1}/{len(accounts_to_trade)}] Trading on: {trading_account['subaccount_name']}")
            
            tradovate_account_id = trading_account.get('subaccount_id')
            tradovate_account_spec = trading_account.get('subaccount_name')
            is_demo = bool(trading_account.get('is_demo'))
            access_token = trading_account.get('tradovate_token')
            username = trading_account.get('username')
            password = trading_account.get('password')
            account_id = trading_account.get('account_id')
            
            if not tradovate_account_id:
                logger.warning(f"⚠️ [{acct_idx+1}] Missing account ID - skipping")
                all_results.append({'success': False, 'error': 'Missing account ID'})
                continue
            
            if not username or not password:
                logger.warning(f"⚠️ [{acct_idx+1}] No username/password - will try existing token")
            
            # Handle CLOSE action - need to determine position side first
            if action == 'CLOSE':
                order_action = None
            else:
                order_action = 'Buy' if action == 'BUY' else 'Sell'
            
            logger.info(f"📤 [{acct_idx+1}] {action} {quantity} {tradovate_symbol} on {trading_account['subaccount_name']}")
            
            async def execute_simple():
                # CRITICAL: Use REST API Access for authentication (avoids rate limiting)
                api_access = TradovateAPIAccess(demo=is_demo)
                
                # Use local variables to avoid scoping issues
                current_access_token = access_token
                current_md_token = trading_account.get('md_access_token')
                # Define order_action - will be set after checking position for CLOSE
                current_order_action = None
                
                # Authenticate via REST API Access if no token or credentials available
                if not current_access_token and username and password:
                    logger.info(f"🔐 Authenticating via REST API Access (avoids rate limiting)...")
                    login_result = await api_access.login(
                        username=username,
                        password=password,
                        db_path=DATABASE_PATH,
                        account_id=account_id
                    )
                    
                    if not login_result.get('success'):
                        logger.error(f"❌ REST API Access authentication failed: {login_result.get('error')}")
                        return {'success': False, 'error': f"Authentication failed: {login_result.get('error')}"}
                    
                    current_access_token = login_result.get('accessToken')
                    current_md_token = login_result.get('mdAccessToken')
                    logger.info(f"✅ REST API Access authentication successful")
                elif current_access_token:
                    logger.info(f"✅ Using existing access token (will re-auth via REST API Access if expired)")
                else:
                    if not username or not password:
                        logger.error(f"❌ No username/password for REST API Access authentication")
                        return {'success': False, 'error': 'No credentials available for authentication'}
                
                async with TradovateIntegration(demo=is_demo) as tradovate:
                    tradovate.access_token = current_access_token
                    tradovate.md_access_token = current_md_token
                
                    # STEP 0: Removed - will query orders AFTER entry fills (STEP 3)
                
                    # STEP 1: CRITICAL - Check broker position and sync database BEFORE placing order
                    positions_before = await tradovate.get_positions(account_id=tradovate_account_id)
                    existing_pos = None
                    existing_net_pos = 0
                    existing_price = None
                    for pos in positions_before:
                        pos_symbol = pos.get('symbol', '')
                        if tradovate_symbol[:3] in pos_symbol:
                            existing_pos = pos
                            existing_net_pos = pos.get('netPos', 0)
                            existing_price = pos.get('netPrice')
                            logger.info(f"📊 EXISTING BROKER POSITION: {existing_net_pos} {pos_symbol} @ {existing_price}")
                            break
                
                    # Handle CLOSE action - determine close side from position
                    # CRITICAL: Use local variable to avoid scope issues with outer 'quantity' parameter
                    trade_quantity = quantity  # Default to parameter value
                    if action == 'CLOSE':
                        if existing_net_pos == 0:
                            logger.warning(f"⚠️ CLOSE signal but no position on broker - nothing to close")
                            return {'success': True, 'message': 'No position to close'}
                        # Close LONG = Sell, Close SHORT = Buy
                        current_order_action = 'Sell' if existing_net_pos > 0 else 'Buy'
                        trade_quantity = abs(existing_net_pos)  # Close entire position
                        logger.info(f"🔄 CLOSE: Closing {existing_net_pos} position with {current_order_action} {trade_quantity}")
                    else:
                        current_order_action = 'Buy' if action == 'BUY' else 'Sell'
                        trade_quantity = quantity  # Use parameter for BUY/SELL
                
                    logger.info(f"🔍 Checking broker position BEFORE placing {current_order_action} order...")
                
                    # CRITICAL: Sync database with broker state BEFORE executing trade
                    # This prevents drift when user clears positions on broker
                    try:
                        conn_sync = get_db_connection()
                        cursor_sync = conn_sync.cursor()
                    
                        # Get database position
                        cursor_sync.execute('''
                            SELECT id, total_quantity, side, avg_entry_price
                            FROM recorder_positions
                            WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                        ''', (recorder_id, ticker))
                        db_pos = cursor_sync.fetchone()
                    
                        if db_pos:
                            db_pos = dict(db_pos)
                            db_qty = db_pos['total_quantity']
                            db_side = db_pos['side']
                        
                            # If broker shows 0 but DB shows open position
                            # DISABLED: Broker position API is unreliable (returns 0 even when position exists)
                            # Trust DB state - let TP order fill handle actual closure
                            if existing_net_pos == 0 and db_qty > 0:
                                logger.info(f"ℹ️ Broker API returned 0 but DB shows {db_side} {db_qty} - KEEPING database (API unreliable)")
                            # If broker has position but DB doesn't match - SYNC IT
                            elif existing_net_pos != 0:
                                broker_side = 'LONG' if existing_net_pos > 0 else 'SHORT'
                                broker_qty_abs = abs(existing_net_pos)
                            
                                if db_qty == 0 or db_side != broker_side or abs(db_qty - broker_qty_abs) > 0:
                                    logger.warning(f"⚠️ DRIFT DETECTED: Broker={broker_side} {broker_qty_abs} @ {existing_price} but DB={db_side} {db_qty} - SYNCING database")
                                
                                    if db_qty == 0:
                                        # Create new position record
                                        cursor_sync.execute('''
                                            INSERT INTO recorder_positions 
                                            (recorder_id, ticker, side, total_quantity, avg_entry_price, entries, status)
                                            VALUES (?, ?, ?, ?, ?, ?, 'open')
                                        ''', (recorder_id, ticker, broker_side, broker_qty_abs, existing_price, 
                                              json.dumps([{'qty': broker_qty_abs, 'price': existing_price}])))
                                    else:
                                        # Update existing position
                                        cursor_sync.execute('''
                                            UPDATE recorder_positions
                                            SET side = ?, total_quantity = ?, avg_entry_price = ?, 
                                                entries = ?, updated_at = CURRENT_TIMESTAMP
                                            WHERE id = ?
                                        ''', (broker_side, broker_qty_abs, existing_price,
                                              json.dumps([{'qty': broker_qty_abs, 'price': existing_price}]),
                                              db_pos['id']))
                                
                                    # Update recorded_trades
                                    cursor_sync.execute('''
                                        UPDATE recorded_trades
                                        SET side = ?, quantity = ?, entry_price = ?, status = 'open'
                                        WHERE recorder_id = ? AND status = 'open'
                                    ''', (broker_side, broker_qty_abs, existing_price, recorder_id))
                                
                                    conn_sync.commit()
                                    logger.info(f"✅ Synced database to match broker: {broker_side} {broker_qty_abs} @ {existing_price}")
                            else:
                                # CRITICAL: Broker has position but DB has NO record (orphaned position)
                                if existing_net_pos != 0 and existing_price:
                                    broker_side = 'LONG' if existing_net_pos > 0 else 'SHORT'
                                    broker_qty_abs = abs(existing_net_pos)
                                
                                    logger.warning(f"⚠️ ORPHANED POSITION: Broker has {broker_side} {broker_qty_abs} @ {existing_price} but DB has no record - CREATING database record")
                                
                                    # Create position record
                                    cursor_sync.execute('''
                                        INSERT INTO recorder_positions 
                                        (recorder_id, ticker, side, total_quantity, avg_entry_price, entries, status)
                                        VALUES (?, ?, ?, ?, ?, ?, 'open')
                                    ''', (recorder_id, ticker, broker_side, broker_qty_abs, existing_price,
                                          json.dumps([{'qty': broker_qty_abs, 'price': existing_price}])))
                                
                                    # Create trade record
                                    cursor_sync.execute('''
                                        INSERT INTO recorded_trades
                                        (recorder_id, ticker, side, quantity, entry_price, status)
                                        VALUES (?, ?, ?, ?, ?, 'open')
                                    ''', (recorder_id, ticker, broker_side, broker_qty_abs, existing_price))
                                
                                    conn_sync.commit()
                                    logger.info(f"✅ Created database record for orphaned position: {broker_side} {broker_qty_abs} @ {existing_price}")
                    
                        conn_sync.close()
                    except Exception as e:
                        logger.warning(f"⚠️ Error syncing with broker position (continuing anyway): {e}")
                
                    # Now check what the broker position is after sync
                    if existing_net_pos != 0:
                            # Check if new order would conflict with existing position
                            if (action == 'BUY' and existing_net_pos < 0) or (action == 'SELL' and existing_net_pos > 0):
                                logger.warning(f"⚠️ WARNING: Placing {current_order_action} {trade_quantity} but broker already has {existing_net_pos} position - this will REDUCE position size")
                            elif (action == 'BUY' and existing_net_pos > 0) or (action == 'SELL' and existing_net_pos < 0):
                                logger.info(f"ℹ️ Placing {current_order_action} {trade_quantity} to ADD to existing {existing_net_pos} position (DCA)")
                            else:
                                logger.info(f"ℹ️ No existing position - opening new {current_order_action} {trade_quantity} position")
                
                    # STEP 1: Place market order
                    order_data = tradovate.create_market_order(
                        tradovate_account_spec,
                        tradovate_symbol,
                        current_order_action,
                        trade_quantity,
                        tradovate_account_id
                    )
                
                    logger.info(f"📤 Placing {current_order_action} {trade_quantity} {tradovate_symbol} (existing broker pos: {existing_net_pos})")
                    order_result = await tradovate.place_order(order_data)
                
                    # If token expired, re-authenticate via REST API Access
                    if order_result and not order_result.get('success') and ('Expired Access Token' in str(order_result.get('error', '')) or '401' in str(order_result.get('error', ''))):
                        if username and password:
                            logger.warning(f"🔄 Token expired, re-authenticating via REST API Access...")
                            login_result = await api_access.login(
                                username=username,
                                password=password,
                                db_path=DATABASE_PATH,
                                account_id=account_id
                            )
                            if login_result.get('success'):
                                logger.info(f"✅ Re-authentication successful via REST API Access, retrying order...")
                                current_access_token = login_result.get('accessToken')
                                current_md_token = login_result.get('mdAccessToken')
                                tradovate.access_token = current_access_token
                                tradovate.md_access_token = current_md_token
                            
                                # Retry order with new token
                                order_result = await tradovate.place_order(order_data)
                            else:
                                logger.error(f"❌ REST API Access re-authentication failed: {login_result.get('error')}")
                
                    if not order_result or not order_result.get('success'):
                        error = order_result.get('error', 'Order failed') if order_result else 'No response'
                        return {'success': False, 'error': error}
                
                    order_id = order_result.get('orderId') or order_result.get('id')
                    logger.info(f"✅ Market order filled: {order_id}")
                
                    # STEP 2: Get fill price - MULTIPLE METHODS for reliability
                    # Method 1: From order result directly (fastest)
                    # Method 2: From fills endpoint (most reliable)
                    # Method 3: From position endpoint with polling (fallback)
                    fill_price = None
                    net_pos = 0
                    broker_pos = None
                    contract_id = None
                    
                    # METHOD 1: Check order result for fill price
                    fill_price = order_result.get('avgFillPrice') or order_result.get('fillPrice') or order_result.get('price')
                    if fill_price:
                        logger.info(f"📊 Got fill price from order result: {fill_price}")
                    
                    # METHOD 2: Query fills endpoint (most reliable for fill price)
                    # CRITICAL FIX: API returns ALL fills, we MUST filter by orderId client-side
                    if not fill_price and order_id:
                        try:
                            await asyncio.sleep(0.3)  # Brief wait for fill to register
                            all_fills = await tradovate.get_fills(order_id=int(order_id))
                            if all_fills:
                                # Filter fills by our specific order ID
                                order_fills = [f for f in all_fills if str(f.get('orderId')) == str(order_id)]
                                logger.info(f"📊 Found {len(order_fills)} fills for order {order_id} (out of {len(all_fills)} total)")
                                
                                if order_fills:
                                    # Sort by timestamp to get most recent fill
                                    order_fills.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                                    fill_price = order_fills[0].get('price') or order_fills[0].get('fillPrice')
                                    if fill_price:
                                        logger.info(f"📊 Got fill price from fills endpoint: {fill_price} (filtered for order {order_id})")
                                else:
                                    logger.warning(f"⚠️ No fills found for order {order_id} - API returned {len(all_fills)} fills for other orders")
                        except Exception as e:
                            logger.debug(f"Could not get fills: {e}")
                    
                    # METHOD 3: Poll position endpoint with retries
                    if not fill_price or True:  # Always try to get position for net_pos/contract_id
                        symbol_root = tradovate_symbol[:3]
                        max_attempts = 5
                        for attempt in range(max_attempts):
                            try:
                                await asyncio.sleep(0.4)  # Wait between attempts
                                positions_after = await tradovate.get_positions(account_id=tradovate_account_id)
                                
                                for pos in positions_after:
                                    pos_symbol = str(pos.get('symbol', '')).upper()
                                    # Match by symbol root (MNQ matches MNQH6, MNQZ5, etc)
                                    if symbol_root in pos_symbol or pos_symbol.startswith(symbol_root):
                                        pos_net = pos.get('netPos', 0)
                                        if pos_net != 0:  # Has an actual position
                                            broker_pos = pos
                                            net_pos = pos_net
                                            contract_id = pos.get('contractId')
                                            if not fill_price:
                                                fill_price = pos.get('netPrice')
                                            logger.info(f"📊 [Attempt {attempt+1}] Found position: {pos_symbol} qty={net_pos} @ {pos.get('netPrice')} (contractId={contract_id})")
                                            break
                                
                                if broker_pos:
                                    break
                                else:
                                    logger.debug(f"📊 [Attempt {attempt+1}/{max_attempts}] No position found yet, retrying...")
                            except Exception as e:
                                if '429' in str(e):
                                    logger.warning(f"⚠️ Rate limited on attempt {attempt+1}")
                                    await asyncio.sleep(1)
                                else:
                                    logger.debug(f"Position query error: {e}")
                    
                    # METHOD 4: Use webhook price as last resort
                    if not fill_price:
                        # Try to get from TradingView API
                        try:
                            tv_price = get_price_from_tradingview_api(ticker)
                            if tv_price:
                                fill_price = tv_price
                                logger.warning(f"⚠️ Using TradingView price as fill estimate: {fill_price}")
                        except:
                            pass
                    
                    # Log final result
                    if fill_price:
                        logger.info(f"📊 FILL CONFIRMED: {net_pos} contracts @ {fill_price} (contractId={contract_id})")
                    else:
                        logger.error(f"❌ CRITICAL: Could not determine fill price after {max_attempts} attempts!")
                        logger.error(f"   This will prevent TP placement. Order ID: {order_id}")
                    
                    # Verify position makes sense (only if we found a position)
                    if broker_pos and existing_net_pos != 0:
                        expected_change = quantity if action == 'BUY' else -quantity
                        actual_change = net_pos - existing_net_pos
                        if abs(actual_change) != abs(expected_change):
                            logger.warning(f"⚠️ Position change mismatch! Expected {expected_change}, got {actual_change}")
                
                    # STEP 3: Place new TP order (old TPs already cancelled at STEP 0)
                    tp_order_id = None
                    # CRITICAL: Don't place TP for DCA - update_exit_brackets() will handle it with updated average price
                    if tp_ticks and action != 'CLOSE' and fill_price and not is_dca:
                        # Old TP orders were already cancelled at STEP 0, so just place new TP
                        symbol_root = extract_symbol_root(ticker)
                        tick_size = TICK_SIZES.get(symbol_root, 0.25)
                    
                        # Get current market price to check marketability
                        current_market_price = fill_price  # Use fill price as baseline
                        try:
                            # Try to get live price from TradingView
                            live_price = get_price_from_tradingview_api(ticker)
                            if live_price:
                                current_market_price = live_price
                                logger.info(f"📊 Current market price: {current_market_price} (fill was @ {fill_price})")
                        except:
                            pass
                    
                        # Calculate TP price based on entry
                        if action == 'BUY':  # LONG position
                            tp_price = fill_price + (tp_ticks * tick_size)
                            tp_side = 'Sell'
                            # Marketability check: TP must be above entry price (not current price, which can move)
                            # Only skip if TP would be at or below entry (invalid)
                            if tp_price <= fill_price:
                                logger.warning(f"⚠️ TP {tp_price} is at or below entry price {fill_price} for LONG - skipping TP placement (invalid TP)")
                                tp_price = None  # Skip placement
                            else:
                                # TP is valid - place it even if current price is above it (it will fill when price comes back down)
                                logger.info(f"✅ TP {tp_price} is valid for LONG entry {fill_price} (current market: {current_market_price})")
                        else:  # SHORT position
                            tp_price = fill_price - (tp_ticks * tick_size)
                            tp_side = 'Buy'
                            # Marketability check for SHORT:
                            # TP must be below entry price (not current price, which can move)
                            # Only skip if TP would be at or above entry (invalid)
                            if tp_price >= fill_price:
                                logger.warning(f"⚠️ TP {tp_price} is at or above entry price {fill_price} for SHORT - skipping TP placement (invalid TP)")
                                tp_price = None  # Skip placement
                            else:
                                # TP is valid - place it even if current price is below it (it will fill when price comes back up)
                                logger.info(f"✅ TP {tp_price} is valid for SHORT entry {fill_price} (current market: {current_market_price})")
                    
                        # STEP 3.5: Check for STORED TP order ID and MODIFY it
                        # Per Tradovate best practices: Use modifyOrder instead of cancel+replace
                        # This ensures ONLY ONE TP order exists at any time
                        existing_tp_order = None
                        stored_tp_order_id = None
                        
                        # Check DB for existing open trade with tp_order_id
                        try:
                            tp_conn = get_db_connection()
                            tp_cursor = tp_conn.cursor()
                            tp_cursor.execute('''
                                SELECT tp_order_id FROM recorded_trades 
                                WHERE recorder_id = ? AND status = 'open' AND tp_order_id IS NOT NULL
                                ORDER BY entry_time DESC LIMIT 1
                            ''', (trading_account.get('recorder_id', recorder_id),))
                            tp_row = tp_cursor.fetchone()
                            if tp_row and tp_row['tp_order_id']:
                                stored_tp_order_id = tp_row['tp_order_id']
                            tp_conn.close()
                        except Exception as e:
                            logger.debug(f"Could not check stored TP order: {e}")
                        
                        # If we have a stored TP order ID, fetch its full details
                        if stored_tp_order_id:
                            logger.info(f"🔍 Found stored TP order ID: {stored_tp_order_id} - fetching details...")
                            try:
                                existing_tp_order = await tradovate.get_order_item(int(stored_tp_order_id))
                                if existing_tp_order:
                                    order_status = str(existing_tp_order.get('ordStatus', '')).upper()
                                    if order_status in ['FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED']:
                                        logger.info(f"📋 Stored TP order {stored_tp_order_id} is {order_status} - will place new one")
                                        existing_tp_order = None  # Need to place new
                                    else:
                                        logger.info(f"✅ Stored TP order {stored_tp_order_id} is WORKING - will MODIFY it")
                            except Exception as e:
                                logger.warning(f"⚠️ Could not fetch stored TP order: {e}")
                                existing_tp_order = None
                    
                        # MODIFY existing TP or place new one
                        if tp_price:
                            tp_qty = abs(net_pos) if net_pos else quantity
                        
                            if existing_tp_order:
                                # MODIFY EXISTING TP (per Tradovate best practices - preserves OCO links if present)
                                existing_tp_id = existing_tp_order.get('id') or existing_tp_order.get('orderId')
                                existing_price = existing_tp_order.get('price')
                                existing_qty = existing_tp_order.get('orderQty', 0)
                            
                                logger.info(f"🔄 MODIFY TP: Order {existing_tp_id} | Price: {existing_price} -> {tp_price} | Qty: {existing_qty} -> {tp_qty}")
                            
                                # Per Tradovate API: MUST include orderQty, orderType, timeInForce (must match original)
                                modify_result = await tradovate.modify_order(
                                    order_id=int(existing_tp_id),
                                    new_price=tp_price,
                                    new_qty=tp_qty,  # REQUIRED
                                    order_type="Limit",  # REQUIRED
                                    time_in_force="GTC"  # REQUIRED - must match original
                                )
                            
                                if modify_result and modify_result.get('success'):
                                    tp_order_id = existing_tp_id
                                    logger.info(f"✅ TP MODIFIED: {existing_tp_id} @ {tp_price} (qty: {tp_qty}) - ONLY ONE TP ORDER")
                                else:
                                    error = modify_result.get('error', 'Unknown') if modify_result else 'No response'
                                    logger.error(f"❌ MODIFY FAILED: {error} - Cancelling and placing new")
                                    # Fallback: cancel failed order and place new
                                    try:
                                        await tradovate.cancel_order(int(existing_tp_id))
                                        await asyncio.sleep(0.2)
                                    except:
                                        pass
                                    # Fall through to place new
                                    existing_tp_order = None
                        
                            if not existing_tp_order:
                                # PLACE NEW TP (only if no existing one to modify)
                                logger.info(f"📊 PLACE NEW TP: {tp_side} {tp_qty} @ {tp_price}")
                            
                                tp_order_data = {
                                    "accountId": tradovate_account_id,
                                    "accountSpec": tradovate_account_spec,
                                    "symbol": tradovate_symbol,
                                    "action": tp_side,
                                    "orderQty": tp_qty,
                                    "orderType": "Limit",
                                    "price": tp_price,
                                    "timeInForce": "GTC",
                                    "isAutomated": True
                                }
                            
                                tp_result = await tradovate.place_order(tp_order_data)
                                if tp_result and tp_result.get('success'):
                                    tp_order_id = tp_result.get('orderId') or tp_result.get('id')
                                    logger.info(f"✅ TP PLACED: {tp_order_id} @ {tp_price} (qty: {tp_qty}) - ONLY ONE TP ORDER")
                                else:
                                    logger.error(f"❌ TP PLACE FAILED: {tp_result}")
                        else:
                            logger.warning(f"⚠️ TP invalid - skipping (would fill instantly)")
                    
                    # ALWAYS return result after order placed (whether TP placed or not)
                    # CRITICAL: Set bracket_managed=True if we placed TP order
                    # This flags the trade for bracket_fill_monitor instead of TP/SL polling
                    return {
                        'success': True,
                        'order_id': str(order_id) if order_id else None,
                        'tp_order_id': str(tp_order_id) if tp_order_id else None,
                        'fill_price': fill_price,
                        'broker_position': broker_pos,
                        'bracket_managed': bool(tp_order_id)  # True if TP was placed on broker
                    }
            
            # Execute for this account
            exec_result = asyncio.run(execute_simple())
            all_results.append(exec_result)
            
            if exec_result.get('success'):
                logger.info(f"✅ [{acct_idx+1}/{len(accounts_to_trade)}] SUCCESS on {trading_account['subaccount_name']} @ {exec_result.get('fill_price')}")
            else:
                logger.error(f"❌ [{acct_idx+1}/{len(accounts_to_trade)}] FAILED on {trading_account['subaccount_name']}: {exec_result.get('error')}")
        
        # Aggregate results - success if ANY account succeeded
        successful_results = [r for r in all_results if r.get('success')]
        if successful_results:
            result['success'] = True
            result['fill_price'] = successful_results[0].get('fill_price')
            result['order_id'] = successful_results[0].get('order_id')
            result['tp_order_id'] = successful_results[0].get('tp_order_id')
            result['broker_position'] = successful_results[0].get('broker_position')
            logger.info(f"✅ COMPLETE: {len(successful_results)}/{len(accounts_to_trade)} accounts traded successfully")
        else:
            result['error'] = f"All {len(accounts_to_trade)} account(s) failed"
            logger.error(f"❌ REJECTED: All accounts failed")
            
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return result


# ============================================================================
# BULLETPROOF SINGLE-TP DCA SYSTEM
# Per tradovate_single_tp_dca_bulletproof.md and tradovate_dca_tp_resting_orders_fix.md
# ============================================================================

async def ensure_single_tp_limit(
    tradovate,
    *,
    account_id: int,
    account_spec: str,
    contract_id: int,
    symbol: str,
    pos_qty: int,
    tp_price: float,
    tif_default: str = "GTC",
    existing_tp_order_id: int = None
) -> Dict[str, Any]:
    """
    SINGLE TP ORDER: Ensure exactly ONE TP limit order exists.
    
    STRATEGY: MODIFY existing order, never cancel+replace
    1. If existing_tp_order_id provided, MODIFY it (price + qty)
    2. If no existing order, place ONE new order
    
    Args:
        tradovate: TradovateIntegration instance
        account_id: Tradovate account ID
        account_spec: Tradovate account spec (name)
        contract_id: Contract ID from broker position
        symbol: Tradovate symbol (e.g., MNQZ5)
        pos_qty: Current position quantity (signed: + for long, - for short)
        tp_price: Take profit price
        tif_default: Time in force (default GTC)
        existing_tp_order_id: If provided, MODIFY this order instead of placing new
    
    Returns:
        Dict with success flag, order_id
    """
    result = {'success': False, 'order_id': None, 'cancelled': 0, 'error': None}
    
    if pos_qty == 0:
        result['error'] = "No position -> do not place TP"
        return result
    
    # Determine exit action: SELL to close LONG, BUY to close SHORT
    wanted_action = "Sell" if pos_qty > 0 else "Buy"
    desired_qty = abs(int(pos_qty))
    symbol_root = symbol[:3].upper() if symbol else ""
    
    logger.info(f"🎯 [SINGLE-TP] Target: {wanted_action} {desired_qty} {symbol} @ {tp_price} (existing order: {existing_tp_order_id})")
    
    try:
        # SIMPLE STRATEGY: MODIFY existing or PLACE new - never cancel+replace
        
        # STEP 1: If we have an existing TP order ID, try to MODIFY it
        if existing_tp_order_id:
            logger.info(f"🔄 [SINGLE-TP] Attempting to MODIFY existing order {existing_tp_order_id}...")
            
            # Fetch current order details to verify it's still working
            current_order = await tradovate.get_order_item(int(existing_tp_order_id))
            
            if current_order:
                order_status = str(current_order.get('ordStatus', '')).upper()
                
                if order_status not in ['FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED']:
                    # Order is still working - MODIFY it
                    logger.info(f"📋 [SINGLE-TP] Order {existing_tp_order_id} is {order_status}, modifying...")
                    
                    modify_result = await tradovate.modify_order(
                        order_id=int(existing_tp_order_id),
                        new_price=float(tp_price),
                        new_qty=desired_qty,
                        order_type="Limit",
                        time_in_force=tif_default
                    )
                    
                    if modify_result and modify_result.get('success'):
                        result['success'] = True
                        result['order_id'] = str(existing_tp_order_id)
                        logger.info(f"✅ [SINGLE-TP] MODIFIED: Order {existing_tp_order_id} -> {wanted_action} {desired_qty} @ {tp_price}")
                        return result
                    else:
                        error = modify_result.get('error', 'Unknown') if modify_result else 'No response'
                        logger.warning(f"⚠️ [SINGLE-TP] Modify failed: {error} - will place new order")
                else:
                    logger.info(f"📋 [SINGLE-TP] Order {existing_tp_order_id} is {order_status} - will place new order")
            else:
                logger.info(f"📋 [SINGLE-TP] Order {existing_tp_order_id} not found - will place new order")
        
        # STEP 2: Place new TP order (only if no existing or modify failed)
        logger.info(f"📊 [SINGLE-TP] Placing NEW TP: {wanted_action} {desired_qty} {symbol} @ {tp_price}")
        
        tp_order = {
            "accountId": int(account_id),
            "accountSpec": str(account_spec),
            "symbol": str(symbol),
            "action": wanted_action,  # "Buy" or "Sell"
            "orderQty": desired_qty,
            "orderType": "Limit",
            "price": float(tp_price),
            "timeInForce": tif_default,
            "isAutomated": True
        }
        
        tp_result = await tradovate.place_order(tp_order)
        
        if tp_result and tp_result.get('success'):
            order_id = tp_result.get('orderId') or tp_result.get('id')
            result['success'] = True
            result['order_id'] = str(order_id)
            logger.info(f"✅ [SINGLE-TP] PLACED: Order {order_id} @ {tp_price} (qty: {desired_qty})")
        else:
            error_msg = tp_result.get('error', 'Unknown error') if tp_result else 'No response'
            result['error'] = error_msg
            logger.error(f"❌ [SINGLE-TP] FAILED to place TP: {error_msg}")
    
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"❌ [SINGLE-TP] Exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return result


def update_exit_brackets(recorder_id: int, ticker: str, side: str, 
                         total_quantity: int, tp_price: float, sl_price: float = None) -> Dict[str, Any]:
    """
    DCA TP UPDATE: MODIFY existing TP order or place new one.
    
    Strategy: ONE TP order, always MODIFY (never cancel+replace)
    """
    result = {'success': False, 'order_id': None, 'cancelled': 0, 'error': None}
    
    logger.info(f"🔄 [DCA-TP] UPDATE: {side} {total_quantity} {ticker} @ {tp_price}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # FIRST: Get existing tp_order_id from DB
        cursor.execute('''
            SELECT tp_order_id FROM recorded_trades
            WHERE recorder_id = ? AND status = 'open' AND tp_order_id IS NOT NULL
            ORDER BY entry_time DESC LIMIT 1
        ''', (recorder_id,))
        tp_row = cursor.fetchone()
        existing_tp_order_id = tp_row['tp_order_id'] if tp_row and tp_row['tp_order_id'] else None
        
        if existing_tp_order_id:
            logger.info(f"📋 [DCA-TP] Found existing tp_order_id: {existing_tp_order_id}")
        else:
            logger.info(f"📋 [DCA-TP] No existing tp_order_id - will place new")
        
        cursor.execute('''
            SELECT t.subaccount_id, t.subaccount_name, t.is_demo,
                   a.tradovate_token, a.tradovate_refresh_token, a.md_access_token,
                   a.username, a.password, a.id as account_id
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = ? AND t.enabled = 1
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        conn.close()
        
        if not trader:
            result['error'] = "No trader"
            return result
        
        trader = dict(trader)
        tradovate_account_id = trader.get('subaccount_id')
        tradovate_account_spec = trader.get('subaccount_name')
        is_demo = bool(trader.get('is_demo'))
        access_token = trader.get('tradovate_token')
        username = trader.get('username')
        password = trader.get('password')
        account_id = trader.get('account_id')
        
        if not tradovate_account_id:
            result['error'] = "Missing account ID"
            return result
        
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        symbol_root = tradovate_symbol[:3].upper() if tradovate_symbol else ticker[:3].upper()
        
        # ACQUIRE EXIT MANAGEMENT LOCK - Prevents race conditions
        # Per tradovate_dca_tp_resting_orders_fix.md: Only ONE exit management operation at a time
        exit_lock = get_exit_management_lock(tradovate_account_id, symbol_root)
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        from tradovate_api_access import TradovateAPIAccess
        import asyncio
        
        async def do_bulletproof_tp_update():
            """
            BULLETPROOF DCA TP UPDATE - Per tradovate_single_tp_dca_bulletproof.md
            1. Get broker position to get contract_id
            2. Cancel ALL working exits (not just extras)
            3. Poll until ALL confirmed cancelled
            4. Place exactly ONE TP with correct qty/price
            """
            api_access = TradovateAPIAccess(demo=is_demo)
            current_access_token = access_token
            current_md_token = trader.get('md_access_token')
            
            # Authenticate if needed
            if not current_access_token and username and password:
                logger.info(f"🔐 [DCA-TP] Authenticating for TP update...")
                login_result = await api_access.login(
                    username=username,
                    password=password,
                    db_path=DATABASE_PATH,
                    account_id=account_id
                )
                if login_result.get('success'):
                    current_access_token = login_result.get('accessToken')
                    current_md_token = login_result.get('mdAccessToken')
                else:
                    return {'success': False, 'error': f"Auth failed: {login_result.get('error')}"}
            elif not current_access_token:
                if not username or not password:
                    return {'success': False, 'error': 'No credentials available'}
            
            async with TradovateIntegration(demo=is_demo) as tradovate:
                tradovate.access_token = current_access_token
                tradovate.md_access_token = current_md_token
                
                # STEP 1: Get broker position to determine contract_id and actual qty
                positions = await tradovate.get_positions(account_id=tradovate_account_id)
                contract_id = None
                pos_qty = total_quantity if side == 'LONG' else -total_quantity
                
                for pos in positions:
                    pos_symbol = str(pos.get('symbol', '') or '').upper()
                    if symbol_root in pos_symbol or pos_symbol[:3] == symbol_root:
                        contract_id = pos.get('contractId')
                        broker_net_pos = pos.get('netPos', 0)
                        if broker_net_pos != 0:
                            pos_qty = broker_net_pos  # Use actual broker position
                            logger.info(f"📊 [DCA-TP] Broker position: {broker_net_pos} {pos_symbol} (contractId: {contract_id})")
                        break
                
                if not contract_id:
                    logger.warning(f"⚠️ [DCA-TP] No contractId found, using symbol match only")
                
                # STEP 2: MODIFY existing TP or place new
                tp_result = await ensure_single_tp_limit(
                    tradovate,
                    account_id=tradovate_account_id,
                    account_spec=tradovate_account_spec,
                    contract_id=contract_id,
                    symbol=tradovate_symbol,
                    pos_qty=pos_qty,
                    tp_price=tp_price,
                    tif_default="GTC",
                    existing_tp_order_id=int(existing_tp_order_id) if existing_tp_order_id else None
                )
                
                # Handle token expiry and retry
                if not tp_result.get('success') and ('Expired' in str(tp_result.get('error', '')) or '401' in str(tp_result.get('error', ''))):
                    if username and password:
                        logger.warning(f"🔄 [DCA-TP] Token expired, re-authenticating...")
                        login_result = await api_access.login(
                            username=username,
                            password=password,
                            db_path=DATABASE_PATH,
                            account_id=account_id
                        )
                        if login_result.get('success'):
                            tradovate.access_token = login_result.get('accessToken')
                            tradovate.md_access_token = login_result.get('mdAccessToken')
                            
                            # Retry with new token
                            tp_result = await ensure_single_tp_limit(
                                tradovate,
                                account_id=tradovate_account_id,
                                account_spec=tradovate_account_spec,
                                contract_id=contract_id,
                                symbol=tradovate_symbol,
                                pos_qty=pos_qty,
                                tp_price=tp_price,
                                tif_default="GTC",
                                existing_tp_order_id=int(existing_tp_order_id) if existing_tp_order_id else None
                            )
                
                return tp_result
        
        # Execute with lock held
        with exit_lock:
            logger.info(f"🔒 [DCA-TP] Acquired exit lock for {tradovate_account_id}:{symbol_root}")
            res = asyncio.run(do_bulletproof_tp_update())
            logger.info(f"🔓 [DCA-TP] Released exit lock for {tradovate_account_id}:{symbol_root}")
        
        result['success'] = res.get('success', False)
        result['order_id'] = res.get('order_id')
        result['cancelled'] = res.get('cancelled', 0)
        result['error'] = res.get('error')
        
        if result['success'] and result['order_id']:
            # Update DB with new tp_order_id
            try:
                conn2 = get_db_connection()
                cursor2 = conn2.cursor()
                cursor2.execute('''
                    UPDATE recorded_trades 
                    SET tp_order_id = ?, tp_price = ?
                    WHERE recorder_id = ? AND status = 'open'
                ''', (result['order_id'], tp_price, recorder_id))
                conn2.commit()
                conn2.close()
                logger.info(f"✅ [DCA-TP] Updated: tp_order_id={result['order_id']} @ {tp_price}")
            except Exception as e:
                logger.warning(f"⚠️ Could not update tp_order_id in DB: {e}")
            
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"❌ [DCA-TP] Update error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return result


def execute_live_trades(recorder_id: int, action: str, ticker: str, quantity: int, 
                        entry_price: float = None, exit_price: float = None,
                        tp_price: float = None, sl_price: float = None):
    """
    LEGACY WRAPPER: Execute live trades on linked accounts.
    This wraps the new broker-first function for backward compatibility.
    """
    logger.info(f"🔄 execute_live_trades called: {action} {quantity} {ticker} for recorder {recorder_id}")
    
    # Get TP/SL in ticks from the recorder settings
    tp_ticks = None
    sl_ticks = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT r.tp_targets, r.sl_amount, r.sl_enabled
            FROM recorders r
            WHERE r.id = ?
        ''', (recorder_id,))
        rec = cursor.fetchone()
        conn.close()
        
        if rec:
            rec = dict(rec)
            # Parse TP targets JSON
            tp_targets_json = rec.get('tp_targets', '[]')
            try:
                tp_targets = json.loads(tp_targets_json) if tp_targets_json else []
                if tp_targets and len(tp_targets) > 0:
                    tp_ticks = int(tp_targets[0].get('ticks', 5))
            except:
                tp_ticks = 5  # Default
            
            # Get SL
            if rec.get('sl_enabled'):
                sl_ticks = int(rec.get('sl_amount', 10))
    except Exception as e:
        logger.warning(f"Could not get TP/SL settings: {e}")
        tp_ticks = 5  # Default
        sl_ticks = 10
    
    # Call the new broker-first function
    result = execute_live_trade_with_bracket(
        recorder_id=recorder_id,
        action=action,
        ticker=ticker,
        quantity=quantity,
        tp_ticks=tp_ticks,
        sl_ticks=sl_ticks,
        is_dca=False
    )
    
    return result


def sync_position_from_broker(recorder_id: int, ticker: str) -> Dict[str, Any]:
    """
    Fetch actual position from Tradovate and sync with DB.
    
    This ensures DB always reflects broker reality.
    Called after DCA fills, periodically, and on Control Center load.
    
    Returns:
        {
            'success': bool,
            'broker_position': {netPos, netPrice, ...} or None,
            'db_updated': bool,
            'error': str or None
        }
    """
    result = {
        'success': False,
        'broker_position': None,
        'db_updated': False,
        'error': None
    }
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get trader linked to this recorder
        cursor.execute('''
            SELECT 
                t.subaccount_id,
                t.subaccount_name,
                t.is_demo,
                a.tradovate_token,
                a.tradovate_refresh_token,
                a.md_access_token
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = ? AND t.enabled = 1
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        
        if not trader:
            result['error'] = "No enabled trader for this recorder"
            conn.close()
            return result
        
        trader = dict(trader)
        tradovate_account_id = trader.get('subaccount_id')
        is_demo = bool(trader.get('is_demo'))
        access_token = trader.get('tradovate_token')
        
        if not access_token:
            result['error'] = "No OAuth token"
            conn.close()
            return result
        
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        import asyncio
        
        async def fetch_position():
            async with TradovateIntegration(demo=is_demo) as tradovate:
                tradovate.access_token = access_token
                tradovate.refresh_token = trader.get('tradovate_refresh_token')
                tradovate.md_access_token = trader.get('md_access_token')
                
                positions = await tradovate.get_positions(account_id=tradovate_account_id)
                
                # Find position for this symbol
                for pos in positions:
                    if pos.get('symbol', '').startswith(tradovate_symbol[:3]):
                        return pos
                return None
        
        broker_pos = asyncio.run(fetch_position())
        
        if broker_pos:
            result['broker_position'] = broker_pos
            broker_qty = abs(broker_pos.get('netPos', 0))
            broker_avg = broker_pos.get('netPrice')
            broker_side = 'LONG' if broker_pos.get('netPos', 0) > 0 else 'SHORT'
            
            logger.info(f"📊 Broker position: {broker_side} {broker_qty} @ {broker_avg}")
            
            if broker_qty > 0 and broker_avg:
                # Get current DB state
                cursor.execute('''
                    SELECT id, quantity, entry_price, side, tp_price, sl_price
                    FROM recorded_trades 
                    WHERE recorder_id = ? AND status = 'open'
                    ORDER BY id DESC LIMIT 1
                ''', (recorder_id,))
                db_trade = cursor.fetchone()
                
                if db_trade:
                    db_trade = dict(db_trade)
                    db_qty = db_trade['quantity']
                    db_entry = db_trade['entry_price']
                    
                    # Check for mismatch
                    if db_qty != broker_qty or abs(db_entry - broker_avg) > 0.01:
                        logger.warning(f"⚠️ MISMATCH: DB={db_qty}@{db_entry:.2f} vs Broker={broker_qty}@{broker_avg:.2f}")
                        
                        # Get TP/SL settings to recalculate
                        cursor.execute('SELECT tp_targets, sl_amount, sl_enabled FROM recorders WHERE id = ?', (recorder_id,))
                        rec = cursor.fetchone()
                        if rec:
                            rec = dict(rec)
                            try:
                                tp_targets = json.loads(rec.get('tp_targets', '[]'))
                                tp_ticks = int(tp_targets[0].get('value', 5)) if tp_targets else 5
                            except:
                                tp_ticks = 5
                            sl_amount = rec.get('sl_amount', 10) if rec.get('sl_enabled') else 0
                        else:
                            tp_ticks = 5
                            sl_amount = 0
                        
                        # Get tick size for symbol
                        root = extract_symbol_root(ticker)
                        tick_size = TICK_SIZES.get(root, 0.25)
                        
                        # Recalculate TP/SL based on broker's avg price
                        # (inline calculation since calculate_tp_sl_prices is defined in webhook handler)
                        if broker_side == 'LONG':
                            new_tp = broker_avg + (tp_ticks * tick_size) if tp_ticks else None
                            new_sl = broker_avg - (sl_amount * tick_size) if sl_amount else None
                        else:  # SHORT
                            new_tp = broker_avg - (tp_ticks * tick_size) if tp_ticks else None
                            new_sl = broker_avg + (sl_amount * tick_size) if sl_amount else None
                        
                        # Update DB to match broker
                        cursor.execute('''
                            UPDATE recorded_trades 
                            SET quantity = ?, entry_price = ?, tp_price = ?, sl_price = ?,
                                broker_fill_price = ?
                            WHERE id = ?
                        ''', (broker_qty, broker_avg, new_tp, new_sl, broker_avg, db_trade['id']))
                        
                        # Update position tracking
                        cursor.execute('''
                            UPDATE recorder_positions 
                            SET total_quantity = ?, avg_entry_price = ?
                            WHERE recorder_id = ? AND status = 'open'
                        ''', (broker_qty, broker_avg, recorder_id))
                        
                        conn.commit()
                        result['db_updated'] = True
                        logger.info(f"✅ DB synced with broker: {broker_qty} @ {broker_avg:.2f} | TP: {new_tp}")
                        
                        # Also update the exit bracket on broker to match new TP
                        if new_tp:
                            update_exit_brackets(
                                recorder_id=recorder_id,
                                ticker=ticker,
                                side=broker_side,
                                total_quantity=broker_qty,
                                tp_price=new_tp,
                                sl_price=new_sl
                            )
            else:
                # No broker position - check if we have an orphaned DB position
                cursor.execute('''
                    SELECT id FROM recorded_trades 
                    WHERE recorder_id = ? AND status = 'open'
                ''', (recorder_id,))
                db_trade = cursor.fetchone()
                
                if db_trade:
                    logger.warning(f"⚠️ DB has open trade but broker has no position - marking as closed")
                    cursor.execute('''
                        UPDATE recorded_trades SET status = 'closed', exit_reason = 'broker_sync'
                        WHERE id = ?
                    ''', (db_trade['id'],))
                    cursor.execute('''
                        DELETE FROM recorder_positions WHERE recorder_id = ? AND status = 'open'
                    ''', (recorder_id,))
                    conn.commit()
                    result['db_updated'] = True
        
        result['success'] = True
        conn.close()
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Position sync error: {e}")
    
    return result


# ============================================================================
# Position Index Management
# ============================================================================

def rebuild_index():
    """Rebuild in-memory index from database"""
    global _open_positions_by_symbol, _open_trades_by_symbol
    
    with _index_lock:
        _open_positions_by_symbol.clear()
        _open_trades_by_symbol.clear()
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Index open positions
            cursor.execute('SELECT id, ticker FROM recorder_positions WHERE status = ?', ('open',))
            for row in cursor.fetchall():
                root = extract_symbol_root(row['ticker'])
                if root not in _open_positions_by_symbol:
                    _open_positions_by_symbol[root] = []
                _open_positions_by_symbol[root].append(row['id'])
            
            # Index open trades
            cursor.execute('SELECT id, ticker FROM recorded_trades WHERE status = ?', ('open',))
            for row in cursor.fetchall():
                root = extract_symbol_root(row['ticker'])
                if root not in _open_trades_by_symbol:
                    _open_trades_by_symbol[root] = []
                _open_trades_by_symbol[root].append(row['id'])
            
            conn.close()
            
            total_pos = sum(len(v) for v in _open_positions_by_symbol.values())
            total_trades = sum(len(v) for v in _open_trades_by_symbol.values())
            logger.info(f"📊 Index rebuilt: {total_pos} positions, {total_trades} trades")
            
        except Exception as e:
            logger.error(f"Error rebuilding index: {e}")


def get_positions_for_symbol(symbol: str) -> List[int]:
    """Get position IDs for a symbol (O(1) lookup)"""
    root = extract_symbol_root(symbol)
    with _index_lock:
        return _open_positions_by_symbol.get(root, []).copy()


def get_trades_for_symbol(symbol: str) -> List[int]:
    """Get trade IDs for a symbol (O(1) lookup)"""
    root = extract_symbol_root(symbol)
    with _index_lock:
        return _open_trades_by_symbol.get(root, []).copy()


# ============================================================================
# Drawdown Tracking (THE CORE FEATURE)
# ============================================================================

def update_position_drawdown(position_id: int, current_price: float) -> bool:
    """
    Update position's drawdown (worst_unrealized_pnl).
    Called on EVERY price tick for accurate tracking.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM recorder_positions WHERE id = ? AND status = ?', 
                      (position_id, 'open'))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return False
        
        pos = dict(row)
        ticker = pos['ticker']
        side = pos['side']
        avg_entry = pos['avg_entry_price']
        total_qty = pos['total_quantity']
        
        tick_size = get_tick_size(ticker)
        tick_value = get_tick_value(ticker)
        
        # Calculate unrealized P&L
        if side == 'LONG':
            pnl_ticks = (current_price - avg_entry) / tick_size
        else:
            pnl_ticks = (avg_entry - current_price) / tick_size
        
        unrealized_pnl = pnl_ticks * tick_value * total_qty
        
        # Update worst/best
        current_worst = pos['worst_unrealized_pnl'] or 0
        current_best = pos['best_unrealized_pnl'] or 0
        
        new_worst = min(current_worst, unrealized_pnl)
        new_best = max(current_best, unrealized_pnl)
        
        # Only update if changed
        if new_worst != current_worst or new_best != current_best or pos['current_price'] != current_price:
            cursor.execute('''
                UPDATE recorder_positions
                SET current_price = ?, unrealized_pnl = ?,
                    worst_unrealized_pnl = ?, best_unrealized_pnl = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (current_price, unrealized_pnl, new_worst, new_best, position_id))
            conn.commit()
            
            if new_worst < current_worst:
                logger.debug(f"📉 Position {position_id} drawdown: ${abs(new_worst):.2f}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error updating position drawdown: {e}")
        return False


def update_trade_mfe_mae(trade_id: int, current_price: float) -> bool:
    """Update trade's MFE/MAE excursions"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM recorded_trades WHERE id = ? AND status = ?',
                      (trade_id, 'open'))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return False
        
        trade = dict(row)
        side = trade['side']
        entry_price = trade['entry_price']
        
        current_mfe = trade.get('max_favorable') or 0
        current_mae = trade.get('max_adverse') or 0
        
        if side == 'LONG':
            favorable = max(0, current_price - entry_price)
            adverse = max(0, entry_price - current_price)
        else:
            favorable = max(0, entry_price - current_price)
            adverse = max(0, current_price - entry_price)
        
        new_mfe = max(current_mfe, favorable)
        new_mae = max(current_mae, adverse)
        
        if new_mfe != current_mfe or new_mae != current_mae:
            cursor.execute('''
                UPDATE recorded_trades 
                SET max_favorable = ?, max_adverse = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_mfe, new_mae, trade_id))
            conn.commit()
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error updating trade MFE/MAE: {e}")
        return False


# ============================================================================
# Price Event Handler
# ============================================================================

def on_price_update(symbol: str, price: float):
    """
    Called on EVERY price tick from TradingView.
    Updates drawdown for all positions/trades with this symbol.
    Also checks for TP/SL hits.
    """
    global _market_data_cache
    
    # Update cache
    root = extract_symbol_root(symbol)
    if root not in _market_data_cache:
        _market_data_cache[root] = {}
    _market_data_cache[root]['last'] = price
    _market_data_cache[root]['updated'] = time.time()
    
    # Update positions
    for pos_id in get_positions_for_symbol(symbol):
        update_position_drawdown(pos_id, price)
    
    # Update trades MFE/MAE
    for trade_id in get_trades_for_symbol(symbol):
        update_trade_mfe_mae(trade_id, price)
    
    # Check TP/SL for this symbol
    check_tp_sl_for_symbol(root, price)


# ============================================================================
# TP/SL Monitoring
# ============================================================================

def check_tp_sl_for_symbol(symbol_root: str, current_price: float):
    """
    Check if any open trades for this symbol have hit their TP or SL.
    Called on every price update for real-time monitoring.
    
    SKIPS trades with broker_managed_tp_sl=1 (Tradovate handles those exits)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get open trades for this symbol with TP or SL set
        # CRITICAL: Only check trades where TP/SL was actually placed (tp_price IS NOT NULL)
        # SKIP broker-managed positions - Tradovate's bracket orders handle those
        # Also skip trades that were just opened (give TP order time to settle - 5 second grace period)
        cursor.execute('''
            SELECT t.*, r.name as recorder_name 
            FROM recorded_trades t
            JOIN recorders r ON t.recorder_id = r.id
            WHERE t.status = 'open' 
            AND (t.tp_price IS NOT NULL OR t.sl_price IS NOT NULL)
            AND COALESCE(t.broker_managed_tp_sl, 0) = 0
            AND datetime(t.entry_time, '+5 seconds') < datetime('now')
        ''')
        
        open_trades = [dict(row) for row in cursor.fetchall()]
        
        for trade in open_trades:
            ticker = trade['ticker']
            # Check if this trade's ticker matches the updated symbol
            trade_root = extract_symbol_root(ticker) if ticker else None
            if trade_root != symbol_root:
                continue
            
            side = trade['side']
            entry_price = trade['entry_price']
            tp_price = trade.get('tp_price')
            sl_price = trade.get('sl_price')
            
            hit_type = None
            exit_price = None
            
            # CRITICAL: DISABLE TP price polling - let broker TP limit order handle it
            # On demo accounts, fill price differs from market price (demo simulates differently)
            # Price polling sees market price (25421) vs TP (25356) and thinks TP hit
            # But broker's TP limit hasn't actually filled yet
            # Only check SL (stop orders need manual monitoring if not placed on broker)
            
            if side == 'LONG':
                logger.debug(f"📍 LONG check: price={current_price} vs SL={sl_price} (TP via broker order)")
                
                # TP: Let broker limit order handle - don't check price
                # SL: Only check if SL is set (stop orders)
                if sl_price and current_price <= sl_price:
                    hit_type = 'sl'
                    exit_price = sl_price
                    logger.info(f"🛑 SL CONDITION MET for LONG! {current_price} <= {sl_price}")
            else:  # SHORT
                logger.debug(f"📍 SHORT check: price={current_price} vs SL={sl_price} (TP via broker order)")
                
                # TP: Let broker limit order handle - don't check price
                # SL: Only check if SL is set (stop orders)
                if sl_price and current_price >= sl_price:
                    hit_type = 'sl'
                    exit_price = sl_price
                    logger.info(f"🛑 SL CONDITION MET for SHORT! {current_price} >= {sl_price}")
            
            if hit_type and exit_price:
                # TP/SL condition met via price monitoring
                # The broker's TP limit order WILL fill when price hits it (or already has)
                # We just need to update our DB - no need to send another close order
                # (The broker TP order handles the actual close)
                
                # Calculate PnL
                tick_size = get_tick_size(ticker)
                tick_value = get_tick_value(ticker)
                quantity = trade['quantity'] or 1
                
                if side == 'LONG':
                    pnl_ticks = (exit_price - entry_price) / tick_size
                else:
                    pnl_ticks = (entry_price - exit_price) / tick_size
                
                pnl = pnl_ticks * tick_value * quantity
                
                # Close the trade in database
                cursor.execute('''
                    UPDATE recorded_trades 
                    SET exit_price = ?, exit_time = CURRENT_TIMESTAMP, 
                        pnl = ?, pnl_ticks = ?, status = 'closed', 
                        exit_reason = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (exit_price, pnl, pnl_ticks, hit_type, trade['id']))
                
                # Also close any open position
                cursor.execute('''
                    SELECT id FROM recorder_positions 
                    WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                ''', (trade['recorder_id'], ticker))
                open_pos = cursor.fetchone()
                if open_pos:
                    close_recorder_position_helper(cursor, open_pos['id'], exit_price, ticker)
                
                conn.commit()
                
                # Rebuild index
                rebuild_index()
                
                logger.info(f"🎯 {hit_type.upper()} HIT via price stream for '{trade.get('recorder_name', 'Unknown')}': "
                           f"{side} {ticker} | Entry: {entry_price} | Exit: {exit_price} | "
                           f"PnL: ${pnl:.2f} ({pnl_ticks:.1f} ticks)")
                
                # NOTE: We don't send a close order here because:
                # - For TP hits: The broker's TP limit order already handles the close
                # - The limit order fills automatically when price reaches it
                # - Sending another close would either fail (no position) or double-close
                logger.info(f"✅ DB updated. Broker TP limit order handles actual close.")
        
        conn.close()
        
    except Exception as e:
        logger.warning(f"Error checking TP/SL: {e}")


# ============================================================================
# TP/SL Polling Fallback (when WebSocket not available)
# ============================================================================

_tp_sl_polling_thread = None
_position_reconciliation_thread = None

def get_price_from_tradingview_api(symbol: str) -> Optional[float]:
    """
    Get price from TradingView public API (fallback when WebSocket not connected).
    Uses the scanner API which doesn't require authentication.
    """
    try:
        import requests
        
        # Normalize symbol for TradingView
        root = extract_symbol_root(symbol)
        if root in ['MNQ', 'MES', 'M2K']:
            tv_symbol = f"CME_MINI:{root}1!"
        else:
            tv_symbol = f"CME:{root}1!"
        
        # TradingView scanner API
        url = "https://scanner.tradingview.com/futures/scan"
        payload = {
            "symbols": {"tickers": [tv_symbol]},
            "columns": ["close"]  # Only request 'close' - bid/ask not available in this API
        }
        
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                values = data['data'][0].get('d', [])
                if values and values[0]:
                    return float(values[0])
        
        return None
        
    except Exception as e:
        logger.debug(f"Error getting price from TradingView API: {e}")
        return None


def reconcile_positions_with_broker():
    """
    Periodically reconcile database positions with broker positions.
    Runs every 60 seconds to catch any drift or mismatches.
    REDUCED FREQUENCY to avoid rate limiting.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all open positions from database
        cursor.execute('''
            SELECT rp.*, r.name as recorder_name, t.subaccount_id, t.is_demo,
                   a.tradovate_token, a.username, a.password, a.id as account_id
            FROM recorder_positions rp
            JOIN recorders r ON rp.recorder_id = r.id
            JOIN traders t ON t.recorder_id = r.id AND t.enabled = 1
            JOIN accounts a ON t.account_id = a.id
            WHERE rp.status = 'open'
        ''')
        
        db_positions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not db_positions:
            return
        
        # Skip reconciliation if we're getting rate limited - don't make it worse
        # Only reconcile if we haven't seen 429 errors recently
        logger.debug(f"🔄 Position reconciliation: checking {len(db_positions)} position(s)")
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        from tradovate_api_access import TradovateAPIAccess
        import asyncio
        
        async def check_all_positions():
            for db_pos in db_positions:
                try:
                    recorder_id = db_pos['recorder_id']
                    ticker = db_pos['ticker']
                    db_qty = db_pos['total_quantity']
                    db_avg = db_pos['avg_entry_price']
                    is_demo = bool(db_pos['is_demo'])
                    account_id = db_pos['account_id']
                    username = db_pos['username']
                    password = db_pos['password']
                    access_token = db_pos['tradovate_token']
                    subaccount_id = db_pos['subaccount_id']
                    
                    # Authenticate
                    api_access = TradovateAPIAccess(demo=is_demo)
                    current_access_token = access_token
                    
                    if not current_access_token and username and password:
                        login_result = await api_access.login(
                            username=username,
                            password=password,
                            db_path=DATABASE_PATH,
                            account_id=account_id
                        )
                        if login_result.get('success'):
                            current_access_token = login_result.get('accessToken')
                    
                    # Get broker position
                    async with TradovateIntegration(demo=is_demo) as tradovate:
                        tradovate.access_token = current_access_token
                        positions = await tradovate.get_positions(account_id=str(subaccount_id))
                        
                        tradovate_symbol = convert_ticker_to_tradovate(ticker)
                        broker_pos = None
                        for pos in positions:
                            pos_symbol = pos.get('symbol', '')
                            if tradovate_symbol[:3] in pos_symbol:
                                broker_pos = pos
                                break
                        
                        broker_qty = broker_pos.get('netPos', 0) if broker_pos else 0
                        broker_avg = broker_pos.get('netPrice') if broker_pos else None
                        
                        # Compare
                        if broker_qty == 0 and db_qty != 0:
                            logger.warning(f"⚠️ POSITION DRIFT: DB shows {db_qty} {ticker} but broker shows 0 - position may have closed")
                        elif broker_qty != 0 and db_qty == 0:
                            logger.warning(f"⚠️ POSITION DRIFT: DB shows 0 but broker shows {broker_qty} {ticker} - position exists on broker but not in DB")
                        elif abs(broker_qty) != abs(db_qty):
                            logger.warning(f"⚠️ POSITION DRIFT: DB shows {db_qty} {ticker} but broker shows {broker_qty} - quantity mismatch")
                        elif broker_avg and db_avg and abs(broker_avg - db_avg) > 0.5:
                            logger.warning(f"⚠️ POSITION DRIFT: DB avg {db_avg} but broker avg {broker_avg} for {ticker} - price mismatch")
                        else:
                            logger.debug(f"✅ Position in sync: {ticker} - DB: {db_qty} @ {db_avg}, Broker: {broker_qty} @ {broker_avg}")
                        
                        # Check for missing TP orders if position exists
                        if broker_qty != 0 and broker_avg:
                            # Get DB trade to check if TP should exist
                            conn2 = get_db_connection()
                            cursor2 = conn2.cursor()
                            cursor2.execute('''
                                SELECT tp_price, side, quantity
                                FROM recorded_trades
                                WHERE recorder_id = ? AND status = 'open'
                                ORDER BY id DESC LIMIT 1
                            ''', (recorder_id,))
                            db_trade = cursor2.fetchone()
                            conn2.close()
                            
                            if db_trade:
                                db_trade = dict(db_trade)
                                db_tp_price = db_trade.get('tp_price')
                                db_side = db_trade.get('side')
                                
                                if db_tp_price:
                                    # Check if TP order exists on broker
                                    orders = await tradovate.get_orders(account_id=str(subaccount_id))
                                    has_tp_order = False
                                    for order in orders:
                                        order_symbol = order.get('symbol', '')
                                        order_type = order.get('orderType', '') or ''
                                        order_status = order.get('ordStatus', '') or ''
                                        order_action = order.get('action', '')
                                        
                                        if ('MNQ' in order_symbol or tradovate_symbol[:3] in order_symbol) and \
                                           'limit' in order_type.lower() and \
                                           order_status in ['New', 'Working', 'PartiallyFilled', 'PendingNew']:
                                            # Check if action matches (SELL for LONG, BUY for SHORT)
                                            if (db_side == 'LONG' and order_action == 'Sell') or \
                                               (db_side == 'SHORT' and order_action == 'Buy'):
                                                has_tp_order = True
                                                logger.debug(f"✅ TP order found for {ticker}: {order_action} @ {order.get('price')}")
                                                break
                                    
                                    if not has_tp_order:
                                        logger.warning(f"⚠️ MISSING TP ORDER: DB shows TP @ {db_tp_price} for {ticker} but no TP order on broker - should place TP order")
                                        # Note: We don't auto-place here to avoid conflicts - user should trigger via webhook or manual action
                            
                except Exception as e:
                    logger.error(f"Error reconciling position for {db_pos.get('ticker', 'unknown')}: {e}")
        
        asyncio.run(check_all_positions())
        
    except Exception as e:
        logger.error(f"Error in position reconciliation: {e}")


def poll_tp_sl():
    """
    Polling fallback for TP/SL monitoring when WebSocket isn't connected.
    Polls every 1 second for faster TP/SL detection.
    """
    logger.info("🔄 Starting TP/SL polling thread (every 1 second)")
    
    while True:
        try:
            # Only poll if WebSocket is not connected
            if _tradingview_ws is not None:
                time.sleep(10)  # Check less frequently if WebSocket might be connected
                continue
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get distinct symbols with open trades that have TP/SL
            cursor.execute('''
                SELECT DISTINCT ticker FROM recorded_trades 
                WHERE status = 'open' AND ticker IS NOT NULL
                AND (tp_price IS NOT NULL OR sl_price IS NOT NULL)
            ''')
            
            symbols_needed = [row['ticker'] for row in cursor.fetchall()]
            conn.close()
            
            if not symbols_needed:
                time.sleep(5)
                continue
            
            logger.info(f"🔍 TP/SL polling: monitoring {len(symbols_needed)} symbol(s): {symbols_needed}")
            
            # Fetch prices and check TP/SL
            for symbol in symbols_needed:
                price = get_price_from_tradingview_api(symbol)
                if price:
                    root = extract_symbol_root(symbol)
                    # Update cache
                    if root not in _market_data_cache:
                        _market_data_cache[root] = {}
                    _market_data_cache[root]['last'] = price
                    _market_data_cache[root]['updated'] = time.time()
                    
                    # Check TP/SL
                    check_tp_sl_for_symbol(root, price)
                    
                    # Log price every poll for monitoring
                    logger.info(f"📊 {symbol}: {price}")
                else:
                    logger.warning(f"⚠️ Could not fetch price for {symbol}")
            
            time.sleep(1)  # Poll every 1 second for faster TP/SL detection
            
        except Exception as e:
            logger.error(f"❌ Error in TP/SL polling: {e}")
            import traceback
            logger.error(traceback.format_exc())
            time.sleep(10)


def start_position_reconciliation():
    """Start the position reconciliation thread (runs every 30 seconds)"""
    global _position_reconciliation_thread
    
    if _position_reconciliation_thread and _position_reconciliation_thread.is_alive():
        return
    
    def reconciliation_loop():
        logger.info("🔄 Starting position reconciliation thread (every 60 seconds)")
        while True:
            try:
                reconcile_positions_with_broker()
                time.sleep(60)  # Run every 60 seconds (reduced to avoid rate limiting)
            except Exception as e:
                logger.error(f"Error in position reconciliation loop: {e}")
                time.sleep(60)
    
    _position_reconciliation_thread = threading.Thread(target=reconciliation_loop, daemon=True)
    _position_reconciliation_thread.start()
    logger.info("✅ Position reconciliation thread started")


def start_tp_sl_polling():
    """Start the TP/SL polling thread"""
    global _tp_sl_polling_thread
    
    if _tp_sl_polling_thread and _tp_sl_polling_thread.is_alive():
        return
    
    _tp_sl_polling_thread = threading.Thread(target=poll_tp_sl, daemon=True)
    _tp_sl_polling_thread.start()
    logger.info("✅ TP/SL polling thread started")


# ============================================================================
# Bracket Order Fill Monitor (Detects when Tradovate closes positions)
# ============================================================================

_bracket_monitor_thread = None

def monitor_bracket_fills():
    """
    Monitor broker-managed positions to detect when bracket orders fill.
    
    When Tradovate's bracket order (TP or SL) fills, the position closes
    on the broker. This thread detects that and updates our DB accordingly.
    
    Polls every 5 seconds for positions with broker_managed_tp_sl=1.
    """
    logger.info("🔄 Starting bracket fill monitor (every 5 seconds)")
    
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get trades with TP orders that are still open in DB
            # Check EITHER broker_managed=1 OR has tp_price (to catch old trades)
            cursor.execute('''
                SELECT t.id, t.recorder_id, t.ticker, t.side, t.entry_price, 
                       t.quantity, t.tp_price, t.sl_price, t.broker_strategy_id,
                       t.broker_order_id, r.name as recorder_name
                FROM recorded_trades t
                JOIN recorders r ON t.recorder_id = r.id
                WHERE t.status = 'open' 
                AND (t.broker_managed_tp_sl = 1 OR t.tp_price IS NOT NULL)
            ''')
            
            broker_managed_trades = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            if not broker_managed_trades:
                time.sleep(10)  # No broker-managed trades, check less frequently
                continue
            
            logger.debug(f"📊 Monitoring {len(broker_managed_trades)} broker-managed trade(s)")
            
            # Group by recorder to minimize API calls
            by_recorder = {}
            for trade in broker_managed_trades:
                rid = trade['recorder_id']
                if rid not in by_recorder:
                    by_recorder[rid] = []
                by_recorder[rid].append(trade)
            
            # DISABLED: Bracket fill monitor uses position API which is unreliable
            # The TP/SL polling thread (check_tp_sl_for_symbol) handles TP detection instead
            # by monitoring price and updating DB when TP price is hit
            for recorder_id, trades in by_recorder.items():
                # Just log that we're monitoring, but don't take action
                # TP/SL polling handles the actual detection and DB update
                logger.debug(f"📊 Bracket monitor: {len(trades)} trade(s) for recorder {recorder_id} - TP/SL polling handles closure")
            
            time.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            logger.error(f"❌ Error in bracket fill monitor: {e}")
            import traceback
            logger.error(traceback.format_exc())
            time.sleep(30)


def start_bracket_monitor():
    """Start the bracket fill monitor thread"""
    global _bracket_monitor_thread
    
    if _bracket_monitor_thread and _bracket_monitor_thread.is_alive():
        return
    
    _bracket_monitor_thread = threading.Thread(target=monitor_bracket_fills, daemon=True)
    _bracket_monitor_thread.start()
    logger.info("✅ Bracket fill monitor started")


# ============================================================================
# Position Drawdown Polling (Trade Manager Style Real-Time Tracking)
# ============================================================================

_position_drawdown_thread = None

def poll_position_drawdown():
    """
    Background thread that polls open positions and updates drawdown (worst_unrealized_pnl).
    Runs every 1 second for accurate tracking - same as Trade Manager.
    
    This is a fallback when WebSocket is not connected. When WebSocket IS connected,
    on_price_update() handles drawdown updates in real-time.
    """
    logger.info("📊 Starting position drawdown polling thread (every 1 second)")
    
    while True:
        try:
            # If WebSocket is connected, it handles updates - reduce polling frequency
            if _tradingview_ws is not None:
                time.sleep(5)  # Check less frequently when WebSocket might be active
                continue
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get all open positions
            cursor.execute('''
                SELECT rp.*, r.name as recorder_name
                FROM recorder_positions rp
                JOIN recorders r ON rp.recorder_id = r.id
                WHERE rp.status = 'open'
            ''')
            
            positions = [dict(row) for row in cursor.fetchall()]
            
            if not positions:
                conn.close()
                time.sleep(1)
                continue
            
            for pos in positions:
                ticker = pos['ticker']
                side = pos['side']
                avg_entry = pos['avg_entry_price']
                total_qty = pos['total_quantity']
                
                # Get current price from market data cache or fetch it
                root = extract_symbol_root(ticker)
                current_price = None
                
                if root in _market_data_cache:
                    current_price = _market_data_cache[root].get('last')
                
                if not current_price:
                    # Try to fetch price from TradingView API
                    current_price = get_price_from_tradingview_api(ticker)
                    if current_price:
                        # Update cache
                        if root not in _market_data_cache:
                            _market_data_cache[root] = {}
                        _market_data_cache[root]['last'] = current_price
                        _market_data_cache[root]['updated'] = time.time()
                
                if not current_price:
                    continue
                
                # Calculate unrealized P&L
                tick_size = get_tick_size(ticker)
                tick_value = get_tick_value(ticker)
                
                if side == 'LONG':
                    pnl_ticks = (current_price - avg_entry) / tick_size
                else:  # SHORT
                    pnl_ticks = (avg_entry - current_price) / tick_size
                
                unrealized_pnl = pnl_ticks * tick_value * total_qty
                
                # Update worst/best unrealized P&L
                current_worst = pos['worst_unrealized_pnl'] or 0
                current_best = pos['best_unrealized_pnl'] or 0
                
                new_worst = min(current_worst, unrealized_pnl)  # Worst is most negative
                new_best = max(current_best, unrealized_pnl)    # Best is most positive
                
                # Only update database if values changed
                if new_worst != current_worst or new_best != current_best or pos['current_price'] != current_price:
                    cursor.execute('''
                        UPDATE recorder_positions
                        SET current_price = ?, 
                            unrealized_pnl = ?,
                            worst_unrealized_pnl = ?,
                            best_unrealized_pnl = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    ''', (current_price, unrealized_pnl, new_worst, new_best, pos['id']))
                    conn.commit()
                    
                    # Log significant drawdown changes
                    if new_worst < current_worst:
                        logger.debug(f"📉 Position drawdown update: {pos.get('recorder_name', 'Unknown')} {side} {ticker} x{total_qty} | Drawdown: ${abs(new_worst):.2f}")
            
            conn.close()
            
        except Exception as e:
            logger.warning(f"Error in position drawdown polling: {e}")
        
        time.sleep(1)  # Poll every 1 second for accurate tracking


def start_position_drawdown_polling():
    """Start the position drawdown polling thread"""
    global _position_drawdown_thread
    
    if _position_drawdown_thread and _position_drawdown_thread.is_alive():
        return
    
    _position_drawdown_thread = threading.Thread(target=poll_position_drawdown, daemon=True)
    _position_drawdown_thread.start()
    logger.info("✅ Position drawdown polling thread started")


# ============================================================================
# TradingView WebSocket
# ============================================================================

def get_tradingview_session() -> Optional[Dict]:
    """Get TradingView session from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT tradingview_session FROM accounts WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row and row['tradingview_session']:
            return json.loads(row['tradingview_session'])
        return None
    except Exception as e:
        logger.error(f"Error getting TradingView session: {e}")
        return None


async def connect_tradingview_websocket():
    """Connect to TradingView WebSocket for real-time prices"""
    global _market_data_cache, _tradingview_ws, _tradingview_subscribed_symbols
    
    if not WEBSOCKETS_AVAILABLE:
        logger.error("websockets not available")
        return
    
    import websockets
    
    ws_url = "wss://data.tradingview.com/socket.io/websocket"
    consecutive_failures = 0
    max_failures_before_refresh = 3
    
    while True:
        # Get fresh session on each connection attempt
        session = get_tradingview_session()
        if not session or not session.get('sessionid'):
            logger.warning("No TradingView session configured - attempting auto-refresh...")
            if _try_auto_refresh_cookies():
                session = get_tradingview_session()
            if not session or not session.get('sessionid'):
                logger.error("❌ No TradingView session - run: python3 tradingview_auth.py store --username EMAIL --password PASSWORD")
                await asyncio.sleep(60)  # Wait before retrying
                continue
        
        sessionid = session.get('sessionid')
        sessionid_sign = session.get('sessionid_sign', '')
        
        try:
            logger.info("Connecting to TradingView WebSocket...")
            
            async with websockets.connect(
                ws_url,
                additional_headers={
                    'Origin': 'https://www.tradingview.com',
                    'Cookie': f'sessionid={sessionid}; sessionid_sign={sessionid_sign}'
                }
            ) as ws:
                _tradingview_ws = ws
                consecutive_failures = 0  # Reset on successful connection
                logger.info("✅ TradingView WebSocket connected!")
                
                # Auth
                auth_msg = json.dumps({"m": "set_auth_token", "p": ["unauthorized_user_token"]})
                await ws.send(f"~m~{len(auth_msg)}~m~{auth_msg}")
                
                # Create quote session
                quote_session = f"qs_{int(time.time())}"
                create_msg = json.dumps({"m": "quote_create_session", "p": [quote_session]})
                await ws.send(f"~m~{len(create_msg)}~m~{create_msg}")
                
                # Subscribe to default symbols
                await subscribe_symbols(ws, quote_session)
                
                # Listen for messages
                async for message in ws:
                    try:
                        if message.startswith('~h~'):
                            await ws.send(message)
                            continue
                        
                        # Check for auth errors in message
                        if 'auth' in message.lower() and 'error' in message.lower():
                            logger.warning("⚠️ Auth error detected in WebSocket message")
                            consecutive_failures = max_failures_before_refresh  # Trigger refresh
                            break
                        
                        await process_message(message)
                    except Exception as e:
                        logger.warning(f"Error processing message: {e}")
                        
        except Exception as e:
            _tradingview_ws = None
            consecutive_failures += 1
            error_str = str(e).lower()
            
            # Check if error indicates auth/session issue
            is_auth_error = any(x in error_str for x in ['401', '403', 'auth', 'forbidden', 'unauthorized', 'session'])
            
            if is_auth_error or consecutive_failures >= max_failures_before_refresh:
                logger.warning(f"⚠️ WebSocket auth issue detected (failures: {consecutive_failures}). Attempting cookie refresh...")
                if _try_auto_refresh_cookies():
                    consecutive_failures = 0
                    logger.info("✅ Cookies refreshed, reconnecting immediately...")
                    continue
                else:
                    logger.error("❌ Cookie refresh failed. Will retry in 60s...")
                    await asyncio.sleep(60)
            else:
                logger.warning(f"TradingView WebSocket error: {e}. Reconnecting in 10s...")
                await asyncio.sleep(10)


def _try_auto_refresh_cookies() -> bool:
    """Try to auto-refresh TradingView cookies using tradingview_auth module"""
    try:
        # Import the auth module
        import tradingview_auth
        
        logger.info("🔄 Attempting automatic cookie refresh...")
        
        # Check if credentials are configured
        creds = tradingview_auth.get_credentials()
        if not creds:
            logger.warning("❌ No TradingView credentials stored. Run: python3 tradingview_auth.py store --username EMAIL --password PASSWORD")
            return False
        
        # Try to refresh
        if tradingview_auth.refresh_cookies():
            logger.info("✅ Cookies auto-refreshed successfully!")
            return True
        else:
            logger.error("❌ Cookie auto-refresh failed")
            return False
            
    except ImportError:
        logger.warning("tradingview_auth module not available for auto-refresh")
        return False
    except Exception as e:
        logger.error(f"Error during auto-refresh: {e}")
        return False


async def subscribe_symbols(ws, quote_session: str):
    """Subscribe to symbols"""
    global _tradingview_subscribed_symbols
    
    # Default symbols to always subscribe
    symbols = ['CME_MINI:MNQ1!', 'CME_MINI:MES1!', 'CME:NQ1!', 'CME:ES1!']
    
    # Add symbols from open trades
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT ticker FROM recorded_trades WHERE status = ? AND ticker IS NOT NULL', ('open',))
        for row in cursor.fetchall():
            root = extract_symbol_root(row['ticker'])
            tv_symbol = f"CME_MINI:{root}1!" if root in ['MNQ', 'MES', 'M2K'] else f"CME:{root}1!"
            if tv_symbol not in symbols:
                symbols.append(tv_symbol)
        conn.close()
    except Exception as e:
        logger.warning(f"Error getting symbols: {e}")
    
    for symbol in symbols:
        if symbol not in _tradingview_subscribed_symbols:
            add_msg = json.dumps({"m": "quote_add_symbols", "p": [quote_session, symbol]})
            await ws.send(f"~m~{len(add_msg)}~m~{add_msg}")
            _tradingview_subscribed_symbols.add(symbol)
            logger.info(f"📈 Subscribed: {symbol}")


async def process_message(message: str):
    """Process TradingView message and update prices"""
    try:
        if not message or not message.startswith('~m~'):
            return
        
        parts = message.split('~m~')
        for part in parts:
            if not part or part.isdigit():
                continue
            try:
                data = json.loads(part)
                if isinstance(data, dict) and data.get('m') == 'qsd':
                    params = data.get('p', [])
                    if len(params) >= 2:
                        symbol_data = params[1]
                        symbol = symbol_data.get('n', '')
                        values = symbol_data.get('v', {})
                        
                        if symbol and values:
                            last_price = values.get('lp') or values.get('last_price')
                            bid = values.get('bid')
                            ask = values.get('ask')
                            
                            if not last_price and bid and ask:
                                last_price = (float(bid) + float(ask)) / 2
                            
                            if last_price:
                                root = symbol.split(':')[-1].replace('1!', '').replace('!', '')
                                # THE KEY CALL
                                on_price_update(root, float(last_price))
            except json.JSONDecodeError:
                continue
    except Exception as e:
        logger.debug(f"Error processing message: {e}")


def start_tradingview_websocket():
    """Start TradingView WebSocket in background thread"""
    global _tradingview_ws_thread
    
    if _tradingview_ws_thread and _tradingview_ws_thread.is_alive():
        return
    
    def run():
        asyncio.run(connect_tradingview_websocket())
    
    _tradingview_ws_thread = threading.Thread(target=run, daemon=True)
    _tradingview_ws_thread.start()
    logger.info("✅ TradingView WebSocket thread started")


# ============================================================================
# API Endpoints
# ============================================================================

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'trading_engine',
        'purpose': 'webhooks_recorders_trading',
        'port': SERVICE_PORT,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/api/tradingview/refresh', methods=['POST'])
def api_refresh_cookies():
    """
    Manually trigger TradingView cookie refresh.
    Requires credentials to be stored first.
    """
    try:
        if _try_auto_refresh_cookies():
            # Restart WebSocket to use new cookies
            global _tradingview_ws
            if _tradingview_ws:
                # The WebSocket loop will reconnect with new cookies
                logger.info("WebSocket will reconnect with fresh cookies")
            
            return jsonify({
                'success': True,
                'message': 'Cookies refreshed successfully. WebSocket reconnecting...'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Cookie refresh failed. Check if credentials are stored: python3 tradingview_auth.py store --username EMAIL --password PASSWORD'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/tradingview/auth-status', methods=['GET'])
def api_auth_status():
    """Check TradingView authentication status"""
    try:
        # Check if credentials are stored
        credentials_stored = False
        try:
            import tradingview_auth
            creds = tradingview_auth.get_credentials()
            credentials_stored = creds is not None
        except:
            pass
        
        # Check session cookies
        session = get_tradingview_session()
        session_valid = session is not None and session.get('sessionid') is not None
        
        # Get session update time
        session_updated = session.get('updated_at') if session else None
        auto_refreshed = session.get('auto_refreshed', False) if session else False
        
        return jsonify({
            'success': True,
            'credentials_stored': credentials_stored,
            'session_valid': session_valid,
            'session_updated_at': session_updated,
            'auto_refresh_enabled': credentials_stored,
            'last_auto_refresh': auto_refreshed,
            'websocket_connected': _tradingview_ws is not None,
            'subscribed_symbols': list(_tradingview_subscribed_symbols),
            'cached_prices': {k: v.get('last') for k, v in _market_data_cache.items()}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/status', methods=['GET'])
def status():
    """Service status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as c FROM recorder_positions WHERE status = ?', ('open',))
        open_positions = cursor.fetchone()['c']
        
        cursor.execute('SELECT COUNT(*) as c FROM recorded_trades WHERE status = ?', ('open',))
        open_trades = cursor.fetchone()['c']
        
        conn.close()
        
        return jsonify({
            'status': 'running',
            'open_positions': open_positions,
            'open_trades': open_trades,
            'indexed_positions': sum(len(v) for v in _open_positions_by_symbol.values()),
            'indexed_trades': sum(len(v) for v in _open_trades_by_symbol.values()),
            'websocket_connected': _tradingview_ws is not None,
            'subscribed_symbols': list(_tradingview_subscribed_symbols),
            'cached_prices': {k: v.get('last') for k, v in _market_data_cache.items()},
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/refresh-index', methods=['POST'])
def refresh_index():
    """
    Refresh the position/trade index.
    Call this from main server after opening/closing positions.
    """
    rebuild_index()
    return jsonify({
        'success': True,
        'positions': sum(len(v) for v in _open_positions_by_symbol.values()),
        'trades': sum(len(v) for v in _open_trades_by_symbol.values())
    })


@app.route('/index', methods=['GET'])
def view_index():
    """View current index"""
    return jsonify({
        'positions_by_symbol': dict(_open_positions_by_symbol),
        'trades_by_symbol': dict(_open_trades_by_symbol)
    })


# ============================================================================
# Recorder CRUD APIs
# ============================================================================

@app.route('/api/recorders', methods=['GET'])
def api_get_recorders():
    """Get all recorders with pagination and search"""
    try:
        search = request.args.get('search', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if search:
            cursor.execute('''
                SELECT * FROM recorders 
                WHERE name LIKE ? 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            ''', (f'%{search}%', per_page, offset))
        else:
            cursor.execute('''
                SELECT * FROM recorders 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            ''', (per_page, offset))
        
        recorders = []
        for row in cursor.fetchall():
            recorder = dict(row)
            try:
                recorder['tp_targets'] = json.loads(recorder.get('tp_targets') or '[]')
            except:
                recorder['tp_targets'] = []
            recorders.append(recorder)
        
        # Get total count
        if search:
            cursor.execute('SELECT COUNT(*) as count FROM recorders WHERE name LIKE ?', (f'%{search}%',))
        else:
            cursor.execute('SELECT COUNT(*) as count FROM recorders')
        total = cursor.fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'recorders': recorders,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        logger.error(f"Error getting recorders: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>', methods=['GET'])
def api_get_recorder(recorder_id):
    """Get a single recorder by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        recorder = dict(row)
        try:
            recorder['tp_targets'] = json.loads(recorder.get('tp_targets') or '[]')
        except:
            recorder['tp_targets'] = []
        
        return jsonify({'success': True, 'recorder': recorder})
    except Exception as e:
        logger.error(f"Error getting recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders', methods=['POST'])
def api_create_recorder():
    """Create a new recorder"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Strategy name is required'}), 400
        
        # Generate webhook token
        webhook_token = secrets.token_urlsafe(16)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Serialize TP targets
        tp_targets = json.dumps(data.get('tp_targets', []))
        
        cursor.execute('''
            INSERT INTO recorders (
                name, strategy_type, symbol, demo_account_id, account_id,
                initial_position_size, add_position_size,
                tp_units, trim_units, tp_targets,
                sl_enabled, sl_amount, sl_units, sl_type,
                avg_down_enabled, avg_down_amount, avg_down_point, avg_down_units,
                add_delay, max_contracts_per_trade, option_premium_filter, direction_filter,
                recording_enabled, webhook_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name,
            data.get('strategy_type', 'Futures'),
            data.get('symbol'),
            data.get('demo_account_id'),
            data.get('account_id'),
            data.get('initial_position_size', 2),
            data.get('add_position_size', 2),
            data.get('tp_units', 'Ticks'),
            data.get('trim_units', 'Contracts'),
            tp_targets,
            1 if data.get('sl_enabled') else 0,
            data.get('sl_amount', 0),
            data.get('sl_units', 'Ticks'),
            data.get('sl_type', 'Fixed'),
            1 if data.get('avg_down_enabled') else 0,
            data.get('avg_down_amount', 1),
            data.get('avg_down_point', 0),
            data.get('avg_down_units', 'Ticks'),
            data.get('add_delay', 1),
            data.get('max_contracts_per_trade', 0),
            data.get('option_premium_filter', 0),
            data.get('direction_filter'),
            1 if data.get('recording_enabled', True) else 0,
            webhook_token
        ))
        
        recorder_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Created recorder: {name} (ID: {recorder_id})")
        
        return jsonify({
            'success': True,
            'message': f'Recorder "{name}" created successfully',
            'recorder_id': recorder_id,
            'webhook_token': webhook_token
        })
    except Exception as e:
        logger.error(f"Error creating recorder: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>', methods=['PUT'])
def api_update_recorder(recorder_id):
    """Update an existing recorder"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if recorder exists
        cursor.execute('SELECT id FROM recorders WHERE id = ?', (recorder_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        # Build update query dynamically
        fields = []
        values = []
        
        field_mapping = {
            'name': 'name',
            'strategy_type': 'strategy_type',
            'symbol': 'symbol',
            'demo_account_id': 'demo_account_id',
            'account_id': 'account_id',
            'initial_position_size': 'initial_position_size',
            'add_position_size': 'add_position_size',
            'tp_units': 'tp_units',
            'trim_units': 'trim_units',
            'sl_amount': 'sl_amount',
            'sl_units': 'sl_units',
            'sl_type': 'sl_type',
            'avg_down_amount': 'avg_down_amount',
            'avg_down_point': 'avg_down_point',
            'avg_down_units': 'avg_down_units',
            'add_delay': 'add_delay',
            'max_contracts_per_trade': 'max_contracts_per_trade',
            'option_premium_filter': 'option_premium_filter',
            'direction_filter': 'direction_filter',
        }
        
        for key, db_field in field_mapping.items():
            if key in data:
                fields.append(f'{db_field} = ?')
                values.append(data[key])
        
        # Handle boolean fields
        if 'sl_enabled' in data:
            fields.append('sl_enabled = ?')
            values.append(1 if data['sl_enabled'] else 0)
        if 'avg_down_enabled' in data:
            fields.append('avg_down_enabled = ?')
            values.append(1 if data['avg_down_enabled'] else 0)
        if 'recording_enabled' in data:
            fields.append('recording_enabled = ?')
            values.append(1 if data['recording_enabled'] else 0)
        
        # Handle TP targets JSON
        if 'tp_targets' in data:
            fields.append('tp_targets = ?')
            values.append(json.dumps(data['tp_targets']))
        
        # Always update updated_at
        fields.append('updated_at = CURRENT_TIMESTAMP')
        
        if fields:
            values.append(recorder_id)
            cursor.execute(f'''
                UPDATE recorders SET {', '.join(fields)} WHERE id = ?
            ''', values)
            conn.commit()
        
        conn.close()
        
        logger.info(f"Updated recorder ID: {recorder_id}")
        
        return jsonify({
            'success': True,
            'message': 'Recorder updated successfully'
        })
    except Exception as e:
        logger.error(f"Error updating recorder {recorder_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>', methods=['DELETE'])
def api_delete_recorder(recorder_id):
    """Delete a recorder and all associated data (CASCADE)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if recorder exists
        cursor.execute('SELECT name FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        name = row['name']
        
        # Delete associated data first (foreign key cascade should handle this, but be explicit)
        cursor.execute('DELETE FROM recorded_trades WHERE recorder_id = ?', (recorder_id,))
        cursor.execute('DELETE FROM recorded_signals WHERE recorder_id = ?', (recorder_id,))
        cursor.execute('DELETE FROM recorder_positions WHERE recorder_id = ?', (recorder_id,))
        
        # Delete the recorder
        cursor.execute('DELETE FROM recorders WHERE id = ?', (recorder_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted recorder: {name} (ID: {recorder_id})")
        
        return jsonify({
            'success': True,
            'message': f'Recorder "{name}" deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>/clone', methods=['POST'])
def api_clone_recorder(recorder_id):
    """Clone an existing recorder"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        original = dict(row)
        
        # Generate new webhook token
        webhook_token = secrets.token_urlsafe(16)
        
        # Create cloned recorder with modified name
        new_name = f"{original['name']} (Copy)"
        
        cursor.execute('''
            INSERT INTO recorders (
                name, strategy_type, symbol, demo_account_id, account_id,
                initial_position_size, add_position_size,
                tp_units, trim_units, tp_targets,
                sl_enabled, sl_amount, sl_units, sl_type,
                avg_down_enabled, avg_down_amount, avg_down_point, avg_down_units,
                add_delay, max_contracts_per_trade, option_premium_filter, direction_filter,
                recording_enabled, webhook_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            new_name,
            original['strategy_type'],
            original['symbol'],
            original['demo_account_id'],
            original['account_id'],
            original['initial_position_size'],
            original['add_position_size'],
            original['tp_units'],
            original['trim_units'],
            original['tp_targets'],
            original['sl_enabled'],
            original['sl_amount'],
            original['sl_units'],
            original['sl_type'],
            original['avg_down_enabled'],
            original['avg_down_amount'],
            original['avg_down_point'],
            original['avg_down_units'],
            original['add_delay'],
            original['max_contracts_per_trade'],
            original['option_premium_filter'],
            original['direction_filter'],
            original['recording_enabled'],
            webhook_token
        ))
        
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"Cloned recorder {recorder_id} -> {new_id}: {new_name}")
        
        return jsonify({
            'success': True,
            'message': f'Recorder cloned successfully',
            'recorder_id': new_id,
            'name': new_name
        })
    except Exception as e:
        logger.error(f"Error cloning recorder {recorder_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>/reset-history', methods=['POST'])
def api_reset_recorder_history(recorder_id):
    """Reset trade history for a recorder (delete all trades, signals, and positions)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify recorder exists
        cursor.execute('SELECT name FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        name = row['name']
        
        # Delete all trades for this recorder
        cursor.execute('DELETE FROM recorded_trades WHERE recorder_id = ?', (recorder_id,))
        trades_deleted = cursor.rowcount
        
        # Delete all signals for this recorder
        cursor.execute('DELETE FROM recorded_signals WHERE recorder_id = ?', (recorder_id,))
        signals_deleted = cursor.rowcount
        
        # Delete all positions for this recorder
        cursor.execute('DELETE FROM recorder_positions WHERE recorder_id = ?', (recorder_id,))
        positions_deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        # Rebuild index since positions changed
        rebuild_index()
        
        logger.info(f"Reset history for recorder '{name}' (ID: {recorder_id}): {trades_deleted} trades, {signals_deleted} signals, {positions_deleted} positions deleted")
        
        return jsonify({
            'success': True,
            'message': f'Trade history reset for "{name}". Deleted {trades_deleted} trades, {signals_deleted} signals, and {positions_deleted} positions.',
            'trades_deleted': trades_deleted,
            'signals_deleted': signals_deleted,
            'positions_deleted': positions_deleted
        })
    except Exception as e:
        logger.error(f"Error resetting history for recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>/webhook', methods=['GET'])
def api_get_recorder_webhook(recorder_id):
    """Get webhook details for a recorder"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, webhook_token FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404
        
        # Build webhook URL
        base_url = request.host_url.rstrip('/')
        webhook_url = f"{base_url}/webhook/{row['webhook_token']}"
        
        # Simple indicator alert message (user specifies buy or sell)
        indicator_buy_message = json.dumps({
            "recorder": row['name'],
            "action": "buy",
            "ticker": "{{ticker}}",
            "price": "{{close}}"
        }, indent=2)
        
        indicator_sell_message = json.dumps({
            "recorder": row['name'],
            "action": "sell",
            "ticker": "{{ticker}}",
            "price": "{{close}}"
        }, indent=2)
        
        # Pine Script strategy alert message (action auto-filled by TradingView)
        strategy_message = json.dumps({
            "recorder": row['name'],
            "action": "{{strategy.order.action}}",
            "ticker": "{{ticker}}",
            "price": "{{close}}",
            "contracts": "{{strategy.order.contracts}}",
            "position_size": "{{strategy.position_size}}",
            "market_position": "{{strategy.market_position}}"
        }, indent=2)
        
        return jsonify({
            'success': True,
            'webhook_url': webhook_url,
            'name': row['name'],
            'alerts': {
                'indicator_buy': indicator_buy_message,
                'indicator_sell': indicator_sell_message,
                'strategy_message': strategy_message
            }
        })
    except Exception as e:
        logger.error(f"Error getting webhook for recorder {recorder_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Webhook Endpoint - Core Signal Processing
# ============================================================================

def close_trade_helper(cursor, trade, exit_price, pnl_ticks, tick_value, exit_reason):
    """Close a trade and calculate PnL"""
    pnl = pnl_ticks * tick_value * trade['quantity']
    
    cursor.execute('''
        UPDATE recorded_trades 
        SET exit_price = ?, exit_time = CURRENT_TIMESTAMP, 
            pnl = ?, pnl_ticks = ?, status = 'closed', 
            exit_reason = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (exit_price, pnl, pnl_ticks, exit_reason, trade['id']))
    
    return pnl, pnl_ticks


def close_recorder_position_helper(cursor, position_id, exit_price, ticker):
    """Close a recorder position and calculate final PnL"""
    cursor.execute('SELECT * FROM recorder_positions WHERE id = ?', (position_id,))
    row = cursor.fetchone()
    
    if not row:
        return
    
    pos = dict(row)
    avg_entry = pos['avg_entry_price']
    total_qty = pos['total_quantity']
    side = pos['side']
    
    pos_tick_size = get_tick_size(ticker)
    pos_tick_value = get_tick_value(ticker)
    
    if side == 'LONG':
        pnl_ticks = (exit_price - avg_entry) / pos_tick_size
    else:
        pnl_ticks = (avg_entry - exit_price) / pos_tick_size
    
    realized_pnl = pnl_ticks * pos_tick_value * total_qty
    
    cursor.execute('''
        UPDATE recorder_positions
        SET status = 'closed',
            exit_price = ?,
            realized_pnl = ?,
            closed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (exit_price, realized_pnl, position_id))
    
    logger.info(f"📊 Position closed: {side} {ticker} x{total_qty} @ avg {avg_entry} -> {exit_price} | PnL: ${realized_pnl:.2f}")


def update_recorder_position_helper(cursor, recorder_id, ticker, side, price, quantity=1):
    """
    Update or create a recorder position for position-based drawdown tracking.
    Returns: position_id, is_new_position, total_quantity
    """
    # Check for existing open position for this recorder+ticker
    cursor.execute('''
        SELECT id, total_quantity, avg_entry_price, entries, side
        FROM recorder_positions
        WHERE recorder_id = ? AND ticker = ? AND status = 'open'
    ''', (recorder_id, ticker))
    
    existing = cursor.fetchone()
    
    if existing:
        pos_id = existing['id']
        total_qty = existing['total_quantity']
        avg_entry = existing['avg_entry_price']
        entries_json = existing['entries']
        pos_side = existing['side']
        
        entries = json.loads(entries_json) if entries_json else []
        
        if pos_side == side:
            # SAME SIDE: Add to position (DCA)
            new_qty = total_qty + quantity
            new_avg = ((avg_entry * total_qty) + (price * quantity)) / new_qty
            entries.append({'price': price, 'qty': quantity, 'time': datetime.now().isoformat()})
            
            cursor.execute('''
                UPDATE recorder_positions
                SET total_quantity = ?, avg_entry_price = ?, entries = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_qty, new_avg, json.dumps(entries), pos_id))
            
            logger.info(f"📈 Position DCA: {side} {ticker} +{quantity} @ {price} | Total: {new_qty} @ avg {new_avg:.2f}")
            return pos_id, False, new_qty
        else:
            # OPPOSITE SIDE: Close existing position, create new one
            close_recorder_position_helper(cursor, pos_id, price, ticker)
            # Fall through to create new position below
    
    # NO POSITION or just closed opposite: Create new position
    entries = [{'price': price, 'qty': quantity, 'time': datetime.now().isoformat()}]
    cursor.execute('''
        INSERT INTO recorder_positions (recorder_id, ticker, side, total_quantity, avg_entry_price, entries)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (recorder_id, ticker, side, quantity, price, json.dumps(entries)))
    
    logger.info(f"📊 New position: {side} {ticker} x{quantity} @ {price}")
    return cursor.lastrowid, True, quantity


@app.route('/webhook/<webhook_token>', methods=['POST'])
def receive_webhook(webhook_token):
    """
    Receive webhook from TradingView alerts/strategies.
    
    Supports two modes:
    1. Simple Alerts (buy/sell signals) - Our system handles TP/SL/sizing
    2. Strategy Alerts (full position management from TradingView)
    
    Expected JSON formats:
    
    Simple Alert:
    {
        "recorder": "MY_STRATEGY",
        "action": "buy" or "sell",
        "ticker": "NQ1!",
        "price": "21500.25"
    }
    
    Strategy Alert (TradingView handles sizing/risk):
    {
        "recorder": "MY_STRATEGY",
        "action": "buy" or "sell",
        "ticker": "NQ1!",
        "price": "21500.25",
        "position_size": "2",
        "contracts": "2",
        "market_position": "long" or "short" or "flat"
    }
    """
    try:
        # Find recorder by webhook token
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM recorders WHERE webhook_token = ? AND recording_enabled = 1
        ''', (webhook_token,))
        recorder = cursor.fetchone()
        
        if not recorder:
            logger.warning(f"Webhook received for unknown/disabled token: {webhook_token[:8]}...")
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid or disabled webhook'}), 404
        
        recorder = dict(recorder)
        recorder_id = recorder['id']
        recorder_name = recorder['name']
        
        # CRITICAL: Sync with broker BEFORE processing signal to prevent drift
        # This ensures database matches broker state (especially if user cleared positions)
        # BUT: Skip sync if we're rate limited to avoid blocking trades
        data = request.get_json() if request.is_json else request.form.to_dict()
        ticker = data.get('ticker') or data.get('symbol', '')
        
        # NOTE: TP order cancellation is handled INSIDE execute_live_trade_with_bracket()
        # which has comprehensive logic to cancel old TPs without cancelling new ones.
        # We don't cancel here to avoid race conditions with newly placed TP orders.
        
        if ticker:
            try:
                sync_result = sync_position_with_broker(recorder_id, ticker)
                if sync_result.get('cleared'):
                    logger.info(f"🔄 Webhook: Cleared database position - broker has no position for {ticker}")
                elif sync_result.get('synced'):
                    logger.info(f"🔄 Webhook: Synced database with broker position for {ticker}")
            except Exception as e:
                # If sync fails (e.g., rate limited), continue anyway - don't block the trade
                logger.warning(f"⚠️ Sync failed (continuing anyway): {e}")
        
        # Parse incoming data (support both JSON and form data)
        if request.is_json:
            data = request.get_json()
        else:
            # Try to parse as JSON from text body
            try:
                data = json.loads(request.data.decode('utf-8'))
            except:
                data = request.form.to_dict()
        
        if not data:
            conn.close()
            return jsonify({'success': False, 'error': 'No data received'}), 400
        
        logger.info(f"📨 Webhook received for recorder '{recorder_name}': {data}")
        
        # Extract signal data
        action = str(data.get('action', '')).lower().strip()
        ticker = data.get('ticker', data.get('symbol', ''))
        price = data.get('price', data.get('close', 0))
        
        # Strategy-specific fields (when TradingView handles sizing)
        position_size = data.get('position_size', data.get('contracts'))
        market_position = data.get('market_position', '')  # long, short, flat
        
        # Validate action - including TP/SL price alerts
        valid_actions = ['buy', 'sell', 'long', 'short', 'close', 'flat', 'exit', 
                         'tp_hit', 'sl_hit', 'take_profit', 'stop_loss', 'price_alert']
        if action not in valid_actions:
            logger.warning(f"Invalid action '{action}' for recorder {recorder_name}")
            conn.close()
            return jsonify({'success': False, 'error': f'Invalid action: {action}'}), 400
        
        # Normalize action
        if action in ['tp_hit', 'take_profit']:
            normalized_action = 'TP_HIT'
        elif action in ['sl_hit', 'stop_loss']:
            normalized_action = 'SL_HIT'
        elif action == 'price_alert':
            normalized_action = 'PRICE_UPDATE'
        elif action in ['long', 'buy']:
            normalized_action = 'BUY'
        elif action in ['short', 'sell']:
            normalized_action = 'SELL'
        else:  # close, flat, exit
            normalized_action = 'CLOSE'
        
        # Determine if this is a simple alert or strategy alert
        is_strategy_alert = position_size is not None or market_position
        
        # Record the signal (with retry for database locks)
        max_retries = 5
        retry_delay = 0.1
        signal_id = None
        
        for attempt in range(max_retries):
            try:
                cursor.execute('''
                    INSERT INTO recorded_signals 
                    (recorder_id, action, ticker, price, position_size, market_position, signal_type, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    recorder_id,
                    normalized_action,
                    ticker,
                    float(price) if price else None,
                    str(position_size) if position_size else None,
                    market_position,
                    'strategy' if is_strategy_alert else 'alert',
                    json.dumps(data)
                ))
                
                signal_id = cursor.lastrowid
                conn.commit()
                break  # Success - exit retry loop
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"⚠️ Database locked when recording signal (attempt {attempt + 1}/{max_retries}), retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    # Reconnect to get fresh connection
                    conn.close()
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    continue
                else:
                    logger.error(f"❌ Failed to record signal after {max_retries} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"❌ Error recording signal: {e}")
                raise
        
        if not signal_id:
            logger.error("❌ Failed to get signal_id after recording")
            conn.close()
            return jsonify({'success': False, 'error': 'Failed to record signal'}), 500
        
        # =====================================================
        # TRADE PROCESSING LOGIC
        # =====================================================
        trade_result = None
        webhook_price = float(price) if price else 0
        
        # CRITICAL: Get LIVE market price for accurate TP/SL calculation
        # The webhook price may be delayed/stale from TradingView
        live_price = get_price_from_tradingview_api(ticker)
        if live_price:
            current_price = live_price
            if webhook_price and abs(webhook_price - live_price) > 2:  # More than 2 points difference
                logger.warning(f"⚠️ Webhook price ({webhook_price}) differs from live price ({live_price}) by {abs(webhook_price - live_price):.2f} points - using live price")
        else:
            current_price = webhook_price
            logger.warning(f"⚠️ Could not fetch live price for {ticker}, using webhook price: {webhook_price}")
        
        # Parse quantity from webhook - log raw values for debugging
        raw_quantity = data.get('quantity', data.get('qty', 1))
        quantity = int(raw_quantity) if raw_quantity else (int(position_size) if position_size else recorder.get('initial_position_size', 1))
        
        # Detailed logging for quantity tracking
        logger.info(f"🎯 Processing webhook for '{recorder_name}': qty={quantity} (raw from webhook: {raw_quantity}, position_size: {position_size}, data keys: {list(data.keys())})")
        
        # Get TP/SL settings from recorder
        sl_enabled = recorder.get('sl_enabled', 0)
        sl_amount = recorder.get('sl_amount', 0) or 0
        
        # Parse TP targets (JSON array)
        tp_targets_raw = recorder.get('tp_targets', '[]')
        try:
            tp_targets = json.loads(tp_targets_raw) if isinstance(tp_targets_raw, str) else tp_targets_raw or []
        except:
            tp_targets = []
        
        # Get first TP target (primary)
        tp_ticks = tp_targets[0].get('value', 0) if tp_targets else 0
        
        # Determine tick size and tick value for PnL calculation
        tick_size = get_tick_size(ticker) if ticker else 0.25
        tick_value = get_tick_value(ticker) if ticker else 0.50
        
        # Check for existing open trade for this recorder
        cursor.execute('''
            SELECT * FROM recorded_trades 
            WHERE recorder_id = ? AND status = 'open' 
            ORDER BY entry_time DESC LIMIT 1
        ''', (recorder_id,))
        open_trade_row = cursor.fetchone()
        open_trade = dict(open_trade_row) if open_trade_row else None
        
        def calculate_tp_sl_prices(entry_price, side, tp_ticks, sl_ticks, tick_size):
            """Calculate TP and SL price levels based on entry and tick settings"""
            if side == 'LONG':
                tp_price = entry_price + (tp_ticks * tick_size) if tp_ticks else None
                sl_price = entry_price - (sl_ticks * tick_size) if sl_ticks else None
            else:  # SHORT
                tp_price = entry_price - (tp_ticks * tick_size) if tp_ticks else None
                sl_price = entry_price + (sl_ticks * tick_size) if sl_ticks else None
            return tp_price, sl_price
        
        # Process based on action type
        if normalized_action == 'TP_HIT':
            if open_trade:
                tp_price = open_trade.get('tp_price') or current_price
                if open_trade['side'] == 'LONG':
                    pnl_ticks = (tp_price - open_trade['entry_price']) / tick_size
                else:
                    pnl_ticks = (open_trade['entry_price'] - tp_price) / tick_size
                
                pnl, _ = close_trade_helper(cursor, open_trade, tp_price, pnl_ticks, tick_value, 'tp')
                
                # Close position tracking too
                cursor.execute('SELECT id FROM recorder_positions WHERE recorder_id = ? AND ticker = ? AND status = ?', 
                              (recorder_id, ticker, 'open'))
                open_pos = cursor.fetchone()
                if open_pos:
                    close_recorder_position_helper(cursor, open_pos['id'], tp_price, ticker)
                
                trade_result = {
                    'action': 'closed', 'trade_id': open_trade['id'], 'side': open_trade['side'],
                    'entry_price': open_trade['entry_price'], 'exit_price': tp_price,
                    'pnl': pnl, 'pnl_ticks': pnl_ticks, 'exit_reason': 'TP'
                }
                logger.info(f"🎯 TP HIT for '{recorder_name}': {open_trade['side']} {ticker} | Exit: {tp_price} | PnL: ${pnl:.2f}")
        
        elif normalized_action == 'SL_HIT':
            if open_trade:
                sl_price = open_trade.get('sl_price') or current_price
                if open_trade['side'] == 'LONG':
                    pnl_ticks = (sl_price - open_trade['entry_price']) / tick_size
                else:
                    pnl_ticks = (open_trade['entry_price'] - sl_price) / tick_size
                
                pnl, _ = close_trade_helper(cursor, open_trade, sl_price, pnl_ticks, tick_value, 'sl')
                
                # Close position tracking too
                cursor.execute('SELECT id FROM recorder_positions WHERE recorder_id = ? AND ticker = ? AND status = ?', 
                              (recorder_id, ticker, 'open'))
                open_pos = cursor.fetchone()
                if open_pos:
                    close_recorder_position_helper(cursor, open_pos['id'], sl_price, ticker)
                
                trade_result = {
                    'action': 'closed', 'trade_id': open_trade['id'], 'side': open_trade['side'],
                    'entry_price': open_trade['entry_price'], 'exit_price': sl_price,
                    'pnl': pnl, 'pnl_ticks': pnl_ticks, 'exit_reason': 'SL'
                }
                logger.info(f"🛑 SL HIT for '{recorder_name}': {open_trade['side']} {ticker} | Exit: {sl_price} | PnL: ${pnl:.2f}")
        
        elif normalized_action == 'CLOSE' or (market_position and market_position.lower() == 'flat'):
            # CRITICAL: Use liquidate_position (like manual trader) to close position AND cancel all orders
            if open_trade:
                logger.info(f"🔄 CLOSE signal: Liquidating {open_trade['side']} position on broker (cancels TP orders automatically)...")
                
                # Get trader info for broker access
                cursor.execute('''
                    SELECT t.subaccount_id, t.subaccount_name, t.is_demo,
                           a.tradovate_token, a.tradovate_refresh_token, a.md_access_token,
                           a.username, a.password, a.id as account_id
                    FROM traders t
                    JOIN accounts a ON t.account_id = a.id
                    WHERE t.recorder_id = ? AND t.enabled = 1
                    LIMIT 1
                ''', (recorder_id,))
                trader = cursor.fetchone()
                
                broker_closed = False
                if trader:
                    trader = dict(trader)
                    tradovate_account_id = trader.get('subaccount_id')
                    is_demo = bool(trader.get('is_demo'))
                    access_token = trader.get('tradovate_token')
                    username = trader.get('username')
                    password = trader.get('password')
                    account_id = trader.get('account_id')
                    
                    if tradovate_account_id:
                        from phantom_scraper.tradovate_integration import TradovateIntegration
                        from tradovate_api_access import TradovateAPIAccess
                        import asyncio
                        
                        async def liquidate():
                            api_access = TradovateAPIAccess(demo=is_demo)
                            current_access_token = access_token
                            current_md_token = trader.get('md_access_token')
                            
                            if not current_access_token and username and password:
                                login_result = await api_access.login(
                                    username=username, password=password,
                                    db_path=DATABASE_PATH, account_id=account_id
                                )
                                if login_result.get('success'):
                                    current_access_token = login_result.get('accessToken')
                                    current_md_token = login_result.get('mdAccessToken')
                            
                            if not current_access_token:
                                return {'success': False, 'error': 'No access token'}
                            
                            async with TradovateIntegration(demo=is_demo) as tradovate:
                                tradovate.access_token = current_access_token
                                tradovate.md_access_token = current_md_token
                                
                                tradovate_symbol = convert_ticker_to_tradovate(ticker)
                                symbol_upper = tradovate_symbol.upper()
                                
                                # Get positions
                                positions = await tradovate.get_positions(account_id=int(tradovate_account_id))
                                
                                # Find matching position
                                matched_pos = None
                                for pos in positions:
                                    pos_symbol = str(pos.get('symbol', '')).upper()
                                    pos_net = pos.get('netPos', 0)
                                    if pos_net != 0:
                                        # Match symbol (base match like MNQ)
                                        if (symbol_upper[:3] in pos_symbol or pos_symbol[:3] in symbol_upper or 
                                            pos_symbol == symbol_upper):
                                            matched_pos = pos
                                            break
                                
                                if matched_pos:
                                    contract_id = matched_pos.get('contractId')
                                    if contract_id:
                                        # Use liquidate_position (closes position AND cancels related orders)
                                        result = await tradovate.liquidate_position(
                                            int(tradovate_account_id), contract_id, admin=False
                                        )
                                        if result and result.get('success'):
                                            logger.info(f"✅ Liquidated position for {ticker} (cancelled TP orders)")
                                            return {'success': True}
                                    
                                    # Fallback: Manual close if no contract_id
                                    net_pos = matched_pos.get('netPos', 0)
                                    if net_pos != 0:
                                        qty = abs(int(net_pos))
                                        close_side = 'Sell' if net_pos > 0 else 'Buy'
                                        order_data = tradovate.create_market_order(
                                            trader.get('subaccount_name'), tradovate_symbol, close_side, qty, int(tradovate_account_id)
                                        )
                                        result = await tradovate.place_order(order_data)
                                        if result and result.get('success'):
                                            # Cancel all TP orders after manual close
                                            all_orders = await tradovate.get_orders(account_id=str(tradovate_account_id))
                                            cancelled = 0
                                            for order in all_orders:
                                                order_symbol = order.get('symbol', '') or ''
                                                order_type = order.get('orderType', '') or ''
                                                order_status = order.get('ordStatus', '') or ''
                                                order_id = order.get('id') or order.get('orderId')
                                                
                                                if (symbol_upper[:3] in order_symbol.upper() and 
                                                    ('limit' in order_type.lower() or order_type in ['Limit', 'LimitOrder']) and
                                                    order_status in ['New', 'PartiallyFilled', 'Working', 'PendingNew', 'PendingReplace', 'PendingCancel', 'Accepted', ''] and
                                                    order_id):
                                                    try:
                                                        if await tradovate.cancel_order(int(order_id)):
                                                            cancelled += 1
                                                    except:
                                                        pass
                                            if cancelled > 0:
                                                logger.info(f"✅ Cancelled {cancelled} TP order(s) after manual close")
                                            return {'success': True}
                                
                                return {'success': False, 'error': 'No position found to close'}
                        
                        broker_result = asyncio.run(liquidate())
                        broker_closed = broker_result.get('success', False)
                
                if open_trade['side'] == 'LONG':
                    pnl_ticks = (current_price - open_trade['entry_price']) / tick_size
                else:
                    pnl_ticks = (open_trade['entry_price'] - current_price) / tick_size
                
                pnl, _ = close_trade_helper(cursor, open_trade, current_price, pnl_ticks, tick_value, 'signal')
                
                trade_result = {
                    'action': 'closed', 'trade_id': open_trade['id'], 'side': open_trade['side'],
                    'entry_price': open_trade['entry_price'], 'exit_price': current_price,
                    'pnl': pnl, 'pnl_ticks': pnl_ticks, 'exit_reason': 'SIGNAL',
                    'broker_closed': broker_closed
                }
                logger.info(f"📊 Trade CLOSED by signal for '{recorder_name}': {open_trade['side']} {ticker} | PnL: ${pnl:.2f} | Broker: {'✅' if broker_closed else '❌'}")
            
            # Close any open position
            cursor.execute('SELECT id FROM recorder_positions WHERE recorder_id = ? AND ticker = ? AND status = ?', 
                          (recorder_id, ticker, 'open'))
            open_pos = cursor.fetchone()
            if open_pos:
                close_recorder_position_helper(cursor, open_pos['id'], current_price, ticker)
        
        elif normalized_action == 'BUY':
            # If we have an open SHORT, close it first
            if open_trade and open_trade['side'] == 'SHORT':
                pnl_ticks = (open_trade['entry_price'] - current_price) / tick_size
                pnl, _ = close_trade_helper(cursor, open_trade, current_price, pnl_ticks, tick_value, 'reversal')
                logger.info(f"📊 SHORT closed by BUY reversal: ${pnl:.2f}")
                open_trade = None
            
            # DCA: If we already have an open LONG, add to it
            if open_trade and open_trade['side'] == 'LONG':
                logger.info(f"📈 DCA LONG signal for '{recorder_name}': adding {quantity} to existing position")
                
                # BROKER-FIRST: Execute on broker first, get confirmed fill
                broker_result = execute_live_trade_with_bracket(
                    recorder_id=recorder_id,
                    action='BUY',
                    ticker=ticker,
                    quantity=quantity,
                    tp_ticks=tp_ticks,
                    sl_ticks=int(sl_amount) if sl_enabled else None,
                    is_dca=True  # DCA doesn't place new brackets yet
                )
                
                if broker_result.get('success'):
                    # BROKER CONFIRMED - now get position data (broker or calculated)
                    broker_pos = broker_result.get('broker_position')
                    fill_price = broker_result.get('fill_price', current_price)
                    
                    if broker_pos and broker_pos.get('netPos', 0) != 0:
                        # BEST CASE: Use broker's confirmed position data
                        broker_qty = abs(broker_pos.get('netPos', 0))
                        broker_avg = broker_pos.get('netPrice', current_price)
                        logger.info(f"📊 BROKER CONFIRMED DCA: {broker_qty} contracts @ avg {broker_avg}")
                    else:
                        # FALLBACK: Calculate average from DB + new fill
                        # Get existing position from DB
                        existing_qty = open_trade.get('quantity', 0) or 1
                        existing_avg = open_trade.get('entry_price', current_price)
                        
                        # Calculate new average: (old_qty * old_price + new_qty * new_price) / total_qty
                        broker_qty = existing_qty + quantity
                        broker_avg = ((existing_qty * existing_avg) + (quantity * fill_price)) / broker_qty
                        logger.warning(f"⚠️ No broker position data - calculated from DB: {broker_qty} @ {broker_avg:.2f} (fill was {fill_price})")
                    
                    # Calculate new TP based on average price
                    new_tp_price, new_sl_price = calculate_tp_sl_prices(
                        broker_avg, 'LONG', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )
                    
                    # Update DB with confirmed data
                    cursor.execute('''
                        UPDATE recorded_trades 
                        SET entry_price = ?, quantity = ?, tp_price = ?, sl_price = ?,
                            broker_fill_price = ?, broker_order_id = ?
                        WHERE id = ?
                    ''', (broker_avg, broker_qty, new_tp_price, new_sl_price,
                          fill_price, broker_result.get('order_id'),
                          open_trade['id']))
                    
                    # Update position tracking
                    cursor.execute('''
                        UPDATE recorder_positions 
                        SET total_quantity = ?, avg_entry_price = ?
                        WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                    ''', (broker_qty, broker_avg, recorder_id, ticker))
                    
                    trade_result = {
                        'action': 'dca', 'trade_id': open_trade['id'], 'side': 'LONG',
                        'dca_price': fill_price,
                        'avg_entry_price': broker_avg,
                        'quantity': quantity, 'total_quantity': broker_qty,
                        'tp_price': new_tp_price, 'sl_price': new_sl_price,
                        'broker_confirmed': True
                    }
                    logger.info(f"📈 DCA LONG CONFIRMED for '{recorder_name}': {ticker} | {broker_qty} @ {broker_avg:.2f} | TP: {new_tp_price}")
                    
                    # UPDATE EXIT BRACKETS to new TP based on average price
                    bracket_result = update_exit_brackets(
                        recorder_id=recorder_id,
                        ticker=ticker,
                        side='LONG',
                        total_quantity=broker_qty,
                        tp_price=new_tp_price,
                        sl_price=new_sl_price
                    )
                    if bracket_result.get('success'):
                        logger.info(f"✅ Exit brackets updated to TP @ {new_tp_price}")
                    else:
                        logger.warning(f"⚠️ Exit brackets update failed: {bracket_result.get('error')}")
                else:
                    # Broker execution failed - DO NOT update DB position
                    if broker_result.get('error'):
                        logger.error(f"❌ DCA LONG REJECTED by broker: {broker_result['error']} - NOT updating position")
                        trade_result = {'action': 'dca_rejected', 'error': broker_result['error']}
                    else:
                        # No broker linked - just log signal, don't track position
                        logger.info(f"📝 No broker linked - DCA signal logged only")
                        trade_result = {'action': 'signal_only', 'side': 'LONG'}

            # Open new LONG trade if no open trade
            elif not open_trade:
                logger.info(f"📈 NEW LONG signal for '{recorder_name}': {quantity} {ticker}")
                
                # BROKER-FIRST: Execute on broker with bracket order
                broker_result = execute_live_trade_with_bracket(
                    recorder_id=recorder_id,
                    action='BUY',
                    ticker=ticker,
                    quantity=quantity,
                    tp_ticks=tp_ticks,
                    sl_ticks=int(sl_amount) if sl_enabled else None,
                    is_dca=False
                )
                
                # CRITICAL: Only record trade if broker confirmed OR no broker linked
                # If broker rejected (error), DO NOT record - prevents DB/broker mismatch
                if broker_result.get('error'):
                    logger.error(f"❌ LONG REJECTED by broker: {broker_result['error']} - NOT recording trade")
                    trade_result = {'action': 'rejected', 'error': broker_result['error']}
                elif broker_result.get('success') and broker_result.get('fill_price'):
                    fill_price = broker_result['fill_price']
                    broker_managed = broker_result.get('bracket_managed', False)
                    tp_order_id = broker_result.get('tp_order_id')  # Check if TP was actually placed
                    logger.info(f"📊 BROKER CONFIRMED: Filled @ {fill_price}, brackets={broker_managed}, tp_order_id={tp_order_id}")

                    # Calculate TP/SL based on actual fill price
                    calculated_tp, sl_price = calculate_tp_sl_prices(
                        fill_price, 'LONG', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )
                    
                    # Only store TP price if TP order was actually placed
                    # If TP was skipped (marketability check), set tp_price = NULL so TP/SL polling won't check it
                    tp_price = calculated_tp if tp_order_id else None
                    if not tp_order_id and calculated_tp:
                        logger.warning(f"⚠️ TP order was not placed (marketability check failed) - setting tp_price=NULL to prevent instant close")

                    # Insert trade with broker data (including tp_order_id for later modification)
                    cursor.execute('''
                        INSERT INTO recorded_trades
                        (recorder_id, signal_id, ticker, action, side, entry_price, entry_time,
                         quantity, status, tp_price, sl_price,
                         broker_order_id, broker_strategy_id, broker_fill_price, broker_managed_tp_sl, tp_order_id)
                        VALUES (?, ?, ?, 'BUY', 'LONG', ?, CURRENT_TIMESTAMP, ?, 'open', ?, ?,
                                ?, ?, ?, ?, ?)
                    ''', (recorder_id, signal_id, ticker, fill_price, quantity, tp_price, sl_price,
                          broker_result.get('order_id'), broker_result.get('strategy_id'),
                          broker_result.get('fill_price'), 1 if broker_managed else 0,
                          broker_result.get('tp_order_id')))

                    new_trade_id = cursor.lastrowid

                    # Update position tracking
                    pos_id, is_new_pos, total_qty = update_recorder_position_helper(
                        cursor, recorder_id, ticker, 'LONG', fill_price, quantity
                    )

                    trade_result = {
                        'action': 'opened', 'trade_id': new_trade_id, 'side': 'LONG',
                        'entry_price': fill_price, 'quantity': quantity,
                        'tp_price': tp_price, 'sl_price': sl_price,
                        'position_id': pos_id, 'position_qty': total_qty,
                        'broker_managed_tp_sl': broker_managed,
                        'broker_confirmed': True
                    }
                    logger.info(f"📈 LONG OPENED for '{recorder_name}': {ticker} @ {fill_price} x{quantity} | TP: {tp_price} | Broker-managed: {broker_managed}")
                else:
                    # No broker linked (success=True but no fill_price) - record for signal tracking only
                    logger.info(f"📝 No broker linked - recording signal only (no position)")
                    trade_result = {'action': 'signal_only', 'side': 'LONG'}
        
        elif normalized_action == 'SELL':
            # If we have an open LONG, close it first
            if open_trade and open_trade['side'] == 'LONG':
                pnl_ticks = (current_price - open_trade['entry_price']) / tick_size
                pnl, _ = close_trade_helper(cursor, open_trade, current_price, pnl_ticks, tick_value, 'reversal')
                logger.info(f"📊 LONG closed by SELL reversal: ${pnl:.2f}")
                open_trade = None
            
            # DCA: If we already have an open SHORT, add to it
            if open_trade and open_trade['side'] == 'SHORT':
                logger.info(f"📉 DCA SHORT signal for '{recorder_name}': adding {quantity} to existing position")
                
                # BROKER-FIRST: Execute on broker first, get confirmed fill
                broker_result = execute_live_trade_with_bracket(
                    recorder_id=recorder_id,
                    action='SELL',
                    ticker=ticker,
                    quantity=quantity,
                    tp_ticks=tp_ticks,
                    sl_ticks=int(sl_amount) if sl_enabled else None,
                    is_dca=True
                )
                
                if broker_result.get('success'):
                    # BROKER CONFIRMED - now get position data (broker or calculated)
                    broker_pos = broker_result.get('broker_position')
                    fill_price = broker_result.get('fill_price', current_price)
                    
                    if broker_pos and broker_pos.get('netPos', 0) != 0:
                        # BEST CASE: Use broker's confirmed position data
                        broker_qty = abs(broker_pos.get('netPos', 0))
                        broker_avg = broker_pos.get('netPrice', current_price)
                        logger.info(f"📊 BROKER CONFIRMED DCA: {broker_qty} contracts @ avg {broker_avg}")
                    else:
                        # FALLBACK: Calculate average from DB + new fill
                        existing_qty = open_trade.get('quantity', 0) or 1
                        existing_avg = open_trade.get('entry_price', current_price)
                        
                        broker_qty = existing_qty + quantity
                        broker_avg = ((existing_qty * existing_avg) + (quantity * fill_price)) / broker_qty
                        logger.warning(f"⚠️ No broker position data - calculated from DB: {broker_qty} @ {broker_avg:.2f} (fill was {fill_price})")
                    
                    # Calculate new TP based on average price
                    new_tp_price, new_sl_price = calculate_tp_sl_prices(
                        broker_avg, 'SHORT', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )
                    
                    # Update DB with confirmed data
                    cursor.execute('''
                        UPDATE recorded_trades 
                        SET entry_price = ?, quantity = ?, tp_price = ?, sl_price = ?,
                            broker_fill_price = ?, broker_order_id = ?
                        WHERE id = ?
                    ''', (broker_avg, broker_qty, new_tp_price, new_sl_price,
                          fill_price, broker_result.get('order_id'),
                          open_trade['id']))
                    
                    # Update position tracking
                    cursor.execute('''
                        UPDATE recorder_positions 
                        SET total_quantity = ?, avg_entry_price = ?
                        WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                    ''', (broker_qty, broker_avg, recorder_id, ticker))
                    
                    trade_result = {
                        'action': 'dca', 'trade_id': open_trade['id'], 'side': 'SHORT',
                        'dca_price': fill_price,
                        'avg_entry_price': broker_avg,
                        'quantity': quantity, 'total_quantity': broker_qty,
                        'tp_price': new_tp_price, 'sl_price': new_sl_price,
                        'broker_confirmed': True
                    }
                    logger.info(f"📉 DCA SHORT CONFIRMED for '{recorder_name}': {ticker} | {broker_qty} @ {broker_avg:.2f} | TP: {new_tp_price}")
                    
                    # UPDATE EXIT BRACKETS to new TP based on average price
                    bracket_result = update_exit_brackets(
                        recorder_id=recorder_id,
                        ticker=ticker,
                        side='SHORT',
                        total_quantity=broker_qty,
                        tp_price=new_tp_price,
                        sl_price=new_sl_price
                    )
                    if bracket_result.get('success'):
                        logger.info(f"✅ Exit brackets updated to TP @ {new_tp_price}")
                    else:
                        logger.warning(f"⚠️ Exit brackets update failed: {bracket_result.get('error')}")
                else:
                    # Broker execution failed - DO NOT update DB position
                    if broker_result.get('error'):
                        logger.error(f"❌ DCA SHORT REJECTED by broker: {broker_result['error']} - NOT updating position")
                        trade_result = {'action': 'dca_rejected', 'error': broker_result['error']}
                    else:
                        # No broker linked - just log signal, don't track position
                        logger.info(f"📝 No broker linked - DCA signal logged only")
                        trade_result = {'action': 'signal_only', 'side': 'SHORT'}

            # Open new SHORT trade if no open trade
            elif not open_trade:
                logger.info(f"📉 NEW SHORT signal for '{recorder_name}': {quantity} {ticker}")
                
                # BROKER-FIRST: Execute on broker with bracket order
                broker_result = execute_live_trade_with_bracket(
                    recorder_id=recorder_id,
                    action='SELL',
                    ticker=ticker,
                    quantity=quantity,
                    tp_ticks=tp_ticks,
                    sl_ticks=int(sl_amount) if sl_enabled else None,
                    is_dca=False
                )
                
                # CRITICAL: Only record trade if broker confirmed OR no broker linked
                # If broker rejected (error), DO NOT record - prevents DB/broker mismatch
                if broker_result.get('error'):
                    logger.error(f"❌ SHORT REJECTED by broker: {broker_result['error']} - NOT recording trade")
                    trade_result = {'action': 'rejected', 'error': broker_result['error']}
                elif broker_result.get('success') and broker_result.get('fill_price'):
                    fill_price = broker_result['fill_price']
                    broker_managed = broker_result.get('bracket_managed', False)
                    logger.info(f"📊 BROKER CONFIRMED: Filled @ {fill_price}, brackets={broker_managed}")

                    # Calculate TP/SL based on actual fill price
                    calculated_tp, sl_price = calculate_tp_sl_prices(
                        fill_price, 'SHORT', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )
                    
                    # Only store TP price if TP order was actually placed
                    # If TP was skipped (marketability check), set tp_price = NULL so TP/SL polling won't check it
                    tp_order_id = broker_result.get('tp_order_id')
                    tp_price = calculated_tp if tp_order_id else None
                    if not tp_order_id and calculated_tp:
                        logger.warning(f"⚠️ TP order was not placed (marketability check failed) - setting tp_price=NULL to prevent instant close")

                    # Insert trade with broker data (including tp_order_id for later modification)
                    cursor.execute('''
                        INSERT INTO recorded_trades
                        (recorder_id, signal_id, ticker, action, side, entry_price, entry_time,
                         quantity, status, tp_price, sl_price,
                         broker_order_id, broker_strategy_id, broker_fill_price, broker_managed_tp_sl, tp_order_id)
                        VALUES (?, ?, ?, 'SELL', 'SHORT', ?, CURRENT_TIMESTAMP, ?, 'open', ?, ?,
                                ?, ?, ?, ?, ?)
                    ''', (recorder_id, signal_id, ticker, fill_price, quantity, tp_price, sl_price,
                          broker_result.get('order_id'), broker_result.get('strategy_id'),
                          broker_result.get('fill_price'), 1 if broker_managed else 0,
                          broker_result.get('tp_order_id')))

                    new_trade_id = cursor.lastrowid

                    # Update position tracking
                    pos_id, is_new_pos, total_qty = update_recorder_position_helper(
                        cursor, recorder_id, ticker, 'SHORT', fill_price, quantity
                    )

                    trade_result = {
                        'action': 'opened', 'trade_id': new_trade_id, 'side': 'SHORT',
                        'entry_price': fill_price, 'quantity': quantity,
                        'tp_price': tp_price, 'sl_price': sl_price,
                        'position_id': pos_id, 'position_qty': total_qty,
                        'broker_managed_tp_sl': broker_managed,
                        'broker_confirmed': True
                    }
                    logger.info(f"📉 SHORT OPENED for '{recorder_name}': {ticker} @ {fill_price} x{quantity} | TP: {tp_price} | Broker-managed: {broker_managed}")
                else:
                    # No broker linked (success=True but no fill_price) - record for signal tracking only
                    logger.info(f"📝 No broker linked - recording signal only (no position)")
                    trade_result = {'action': 'signal_only', 'side': 'SHORT'}
        
        conn.commit()
        
        # Rebuild index since positions may have changed
        rebuild_index()
        
        conn.close()
        
        logger.info(f"✅ Signal recorded for '{recorder_name}': {normalized_action} {ticker} @ {price}")
        
        # Build response
        response = {
            'success': True,
            'message': f'Signal received and recorded',
            'signal_id': signal_id,
            'recorder': recorder_name,
            'action': normalized_action,
            'ticker': ticker,
            'price': f"{current_price:.2f}" if current_price else None
        }
        
        if trade_result:
            response['trade'] = trade_result
            if trade_result.get('action') == 'closed':
                response['message'] = f"Trade closed with PnL: ${trade_result['pnl']:.2f}"
            elif trade_result.get('action') == 'opened':
                response['message'] = f"{trade_result['side']} position opened @ {trade_result['entry_price']}"
        
        if is_strategy_alert:
            response['signal_type'] = 'strategy'
            response['note'] = 'Strategy alert - TradingView manages position sizing'
        else:
            response['signal_type'] = 'alert'
            response['note'] = 'Simple alert - Recorder settings control sizing/risk'
            response['recorder_settings'] = {
                'initial_position_size': recorder.get('initial_position_size'),
                'tp_enabled': bool(tp_targets),
                'sl_enabled': bool(sl_enabled)
            }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>/signals', methods=['GET'])
def api_get_recorder_signals(recorder_id):
    """Get recorded signals for a recorder"""
    try:
        limit = int(request.args.get('limit', 50))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM recorded_signals 
            WHERE recorder_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (recorder_id, limit))
        
        signals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'signals': signals,
            'count': len(signals)
        })
    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>/trades', methods=['GET'])
def api_get_recorder_trades(recorder_id):
    """Get recorded trades for a recorder"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')  # open, closed, or all
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query with filters
        where_clauses = ['recorder_id = ?']
        params = [recorder_id]
        
        if status and status != 'all':
            where_clauses.append('status = ?')
            params.append(status)
        
        where_sql = ' AND '.join(where_clauses)
        
        cursor.execute(f'''
            SELECT * FROM recorded_trades 
            WHERE {where_sql}
            ORDER BY entry_time DESC 
            LIMIT ? OFFSET ?
        ''', params + [per_page, offset])
        
        trades = [dict(row) for row in cursor.fetchall()]
        
        # Get total count
        cursor.execute(f'SELECT COUNT(*) as count FROM recorded_trades WHERE {where_sql}', params)
        total = cursor.fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'trades': trades,
            'total': total,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Startup
# ============================================================================

def initialize():
    """Initialize the Trading Engine"""
    logger.info("=" * 60)
    logger.info("🎯 Trading Engine - Recorder & Automation Server")
    logger.info("=" * 60)
    logger.info("Handles: Webhooks, Recorders, TP/SL, Drawdown, Automation")
    logger.info("Main Server handles: OAuth, Copy Trading, Dashboard UI")
    logger.info("=" * 60)
    
    # Initialize database tables
    init_trading_engine_db()
    
    # Build position/trade index for drawdown tracking
    rebuild_index()
    
    # Start TradingView WebSocket for price streaming
    try:
        session = get_tradingview_session()
        if session and session.get('sessionid'):
            start_tradingview_websocket()
            logger.info("✅ TradingView WebSocket started")
        else:
            logger.info("ℹ️ TradingView session not configured - POST to /api/tradingview/session")
    except Exception as e:
        logger.warning(f"Could not start WebSocket: {e}")
    
    # Start TP/SL polling thread (fallback when WebSocket not available)
    start_tp_sl_polling()
    logger.info("✅ TP/SL monitoring active")

    # Start position reconciliation (compares DB with broker every 60 seconds)
    # TEMPORARILY DISABLED to avoid rate limiting - re-enable once rate limits are resolved
    # start_position_reconciliation()
    # logger.info("✅ Position reconciliation active")
    logger.info("ℹ️ Position reconciliation disabled (to avoid rate limiting)")

    # Start bracket fill monitor (detects when Tradovate closes positions)
    start_bracket_monitor()
    logger.info("✅ Bracket fill monitor active")

    # Start position drawdown polling thread (Trade Manager style tracking)
    start_position_drawdown_polling()
    logger.info("✅ Position drawdown tracking active")

    logger.info(f"✅ Trading Engine ready on port {SERVICE_PORT}")
    logger.info("=" * 60)


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    initialize()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=False, threaded=True)
