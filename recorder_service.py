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

def check_broker_position_exists(recorder_id: int, ticker: str) -> bool:
    """
    Check if broker still has an open position for this symbol.
    Used to prevent sending redundant close orders when TP limit already filled.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.subaccount_id, t.is_demo, a.tradovate_token
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
        
        if not access_token or not tradovate_account_id:
            return False
        
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        import asyncio
        
        async def check_position():
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


def convert_ticker_to_tradovate(ticker: str) -> str:
    """Convert TradingView ticker to Tradovate format (e.g., MNQ1! -> MNQZ5)"""
    clean_ticker = ticker.strip().upper()
    if '!' in clean_ticker:
        match = re.match(r'^([A-Z]+)\d*!$', clean_ticker)
        if match:
            root = match.group(1)
            # Use Z5 for December 2025 (current front month)
            return f"{root}Z5"
        return clean_ticker.replace('!', '')
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
        
        # Find enabled trader
        cursor.execute('''
            SELECT 
                t.subaccount_id, t.subaccount_name, t.is_demo,
                a.name as account_name, a.tradovate_token,
                a.tradovate_refresh_token, a.md_access_token
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = ? AND t.enabled = 1
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        conn.close()
        
        if not trader:
            logger.info(f"📝 No enabled trader - recording only")
            result['success'] = True
            return result
        
        trader = dict(trader)
        tradovate_account_id = trader.get('subaccount_id')
        tradovate_account_spec = trader.get('subaccount_name')
        is_demo = bool(trader.get('is_demo'))
        access_token = trader.get('tradovate_token')
        
        if not access_token or not tradovate_account_id:
            result['error'] = "Missing credentials"
            return result
        
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        order_action = 'Buy' if action == 'BUY' else 'Sell'
        
        logger.info(f"📤 {order_action} {quantity} {tradovate_symbol}")
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        import asyncio
        
        async def execute_simple():
            async with TradovateIntegration(demo=is_demo) as tradovate:
                tradovate.access_token = access_token
                tradovate.refresh_token = trader.get('tradovate_refresh_token')
                tradovate.md_access_token = trader.get('md_access_token')
                
                # STEP 1: Place market order
                order_data = tradovate.create_market_order(
                    tradovate_account_spec,
                    tradovate_symbol,
                    order_action,
                    quantity,
                    tradovate_account_id
                )
                
                order_result = await tradovate.place_order(order_data)
                
                if not order_result or not order_result.get('success'):
                    error = order_result.get('error', 'Order failed') if order_result else 'No response'
                    return {'success': False, 'error': error}
                
                order_id = order_result.get('orderId') or order_result.get('id')
                logger.info(f"✅ Market order filled: {order_id}")
                
                # STEP 2: Get position to confirm fill price
                await asyncio.sleep(0.3)  # Brief wait for fill to settle
                positions = await tradovate.get_positions(account_id=tradovate_account_id)
                
                broker_pos = None
                for pos in positions:
                    pos_symbol = pos.get('symbol', '')
                    if tradovate_symbol[:3] in pos_symbol:
                        broker_pos = pos
                        break
                
                fill_price = broker_pos.get('netPrice') if broker_pos else None
                net_pos = broker_pos.get('netPos', 0) if broker_pos else 0
                
                logger.info(f"📊 Position: {net_pos} @ {fill_price}")
                
                # STEP 3: Place TP limit order (if not closing and TP specified)
                tp_order_id = None
                if tp_ticks and action != 'CLOSE' and fill_price:
                    symbol_root = extract_symbol_root(ticker)
                    tick_size = TICK_SIZES.get(symbol_root, 0.25)
                    
                    # Calculate TP price
                    if action == 'BUY':  # LONG position
                        tp_price = fill_price + (tp_ticks * tick_size)
                        tp_side = 'Sell'
                    else:  # SHORT position
                        tp_price = fill_price - (tp_ticks * tick_size)
                        tp_side = 'Buy'
                    
                    # Determine total quantity for TP (use broker's position size)
                    tp_qty = abs(net_pos) if net_pos else quantity
                    
                    logger.info(f"📊 Placing TP: {tp_side} {tp_qty} @ {tp_price}")
                    
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
                        logger.info(f"✅ TP order placed: {tp_order_id} @ {tp_price}")
                    else:
                        logger.warning(f"⚠️ TP order failed: {tp_result}")
                
                return {
                    'success': True,
                    'order_id': str(order_id) if order_id else None,
                    'tp_order_id': str(tp_order_id) if tp_order_id else None,
                    'fill_price': fill_price,
                    'broker_position': broker_pos
                }
        
        exec_result = asyncio.run(execute_simple())
        
        if exec_result.get('success'):
            result['success'] = True
            result['fill_price'] = exec_result.get('fill_price')
            result['order_id'] = exec_result.get('order_id')
            result['tp_order_id'] = exec_result.get('tp_order_id')
            result['broker_position'] = exec_result.get('broker_position')
            logger.info(f"✅ CONFIRMED: {action} {quantity} {ticker} @ {result['fill_price']}")
        else:
            result['error'] = exec_result.get('error', 'Failed')
            logger.error(f"❌ REJECTED: {result['error']}")
            
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"❌ Error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return result


def update_exit_brackets(recorder_id: int, ticker: str, side: str, 
                         total_quantity: int, tp_price: float, sl_price: float = None) -> Dict[str, Any]:
    """
    Cancel ALL working limit/stop orders for this symbol, then place new TP.
    Simple and reliable approach for DCA updates.
    """
    result = {'success': False, 'order_id': None, 'cancelled': 0, 'error': None}
    
    logger.info(f"🔄 UPDATE TP: {side} {total_quantity} {ticker} @ {tp_price}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.subaccount_id, t.subaccount_name, t.is_demo,
                   a.tradovate_token, a.tradovate_refresh_token, a.md_access_token
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
        
        if not access_token:
            result['error'] = "No token"
            return result
        
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        exit_side = 'Sell' if side == 'LONG' else 'Buy'
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        import asyncio
        
        async def cancel_and_place():
            async with TradovateIntegration(demo=is_demo) as tradovate:
                tradovate.access_token = access_token
                tradovate.refresh_token = trader.get('tradovate_refresh_token')
                tradovate.md_access_token = trader.get('md_access_token')
                
                cancelled = 0
                
                # STEP 1: Cancel ALL working orders for this symbol
                try:
                    orders = await tradovate.get_orders(account_id=str(tradovate_account_id))
                    
                    for order in orders:
                        order_id = order.get('id')
                        order_symbol = order.get('symbol', '') or ''
                        order_status = order.get('ordStatus', '') or ''
                        
                        # Match symbol (first 3 chars)
                        if tradovate_symbol[:3] in order_symbol:
                            # Cancel if working
                            if order_status in ['Working', 'Accepted', 'PendingNew', 'New', '']:
                                logger.info(f"📛 Cancel {order_id}: {order_symbol} {order_status}")
                                if await tradovate.cancel_order(order_id):
                                    cancelled += 1
                except Exception as e:
                    logger.warning(f"⚠️ Cancel error: {e}")
                
                logger.info(f"📛 Cancelled {cancelled} orders")
                await asyncio.sleep(0.2)
                
                # STEP 2: Place new TP limit order
                logger.info(f"📊 New TP: {exit_side} {total_quantity} @ {tp_price}")
                
                tp_order = {
                    "accountId": tradovate_account_id,
                    "accountSpec": tradovate_account_spec,
                    "symbol": tradovate_symbol,
                    "action": exit_side,
                    "orderQty": total_quantity,
                    "orderType": "Limit",
                    "price": tp_price,
                    "timeInForce": "GTC",
                    "isAutomated": True
                }
                
                tp_result = await tradovate.place_order(tp_order)
                
                if tp_result and tp_result.get('success'):
                    order_id = tp_result.get('orderId') or tp_result.get('id')
                    logger.info(f"✅ TP placed: {order_id} @ {tp_price}")
                    return {'success': True, 'order_id': order_id, 'cancelled': cancelled}
                else:
                    return {'success': False, 'error': tp_result.get('error') if tp_result else 'Failed'}
        
        res = asyncio.run(cancel_and_place())
        
        result['success'] = res.get('success', False)
        result['order_id'] = res.get('order_id')
        result['cancelled'] = res.get('cancelled', 0)
        result['error'] = res.get('error')
        
        if result['success']:
            logger.info(f"✅ TP updated: {result['cancelled']} cancelled, new @ {tp_price}")
            
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"❌ Update error: {e}")
    
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
        # SKIP broker-managed positions - Tradovate's bracket orders handle those
        cursor.execute('''
            SELECT t.*, r.name as recorder_name 
            FROM recorded_trades t
            JOIN recorders r ON t.recorder_id = r.id
            WHERE t.status = 'open' 
            AND (t.tp_price IS NOT NULL OR t.sl_price IS NOT NULL)
            AND COALESCE(t.broker_managed_tp_sl, 0) = 0
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
            
            if side == 'LONG':
                # LONG: TP hit if price >= tp_price, SL hit if price <= sl_price
                logger.debug(f"LONG check: price={current_price}, tp={tp_price}, sl={sl_price}")
                if tp_price and current_price >= tp_price:
                    hit_type = 'tp'
                    exit_price = tp_price
                elif sl_price and current_price <= sl_price:
                    hit_type = 'sl'
                    exit_price = sl_price
            else:  # SHORT
                # SHORT: TP hit if price <= tp_price, SL hit if price >= sl_price
                logger.info(f"📍 SHORT check: price={current_price} vs TP={tp_price} (need price <= TP)")
                if tp_price and current_price <= tp_price:
                    hit_type = 'tp'
                    exit_price = tp_price
                    logger.info(f"🎯 TP CONDITION MET! {current_price} <= {tp_price}")
                elif sl_price and current_price >= sl_price:
                    hit_type = 'sl'
                    exit_price = sl_price
            
            if hit_type and exit_price:
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
                
                # CHECK BROKER FIRST - only send close if broker still has position
                # The TP limit order may have already filled on broker
                broker_has_position = check_broker_position_exists(trade['recorder_id'], ticker)
                
                if broker_has_position:
                    # EXECUTE CLOSING TRADE ON BROKER
                    # LONG position closes with SELL, SHORT position closes with BUY
                    close_action = 'SELL' if side == 'LONG' else 'BUY'
                    logger.info(f"📤 Executing {hit_type.upper()} exit: {close_action} {quantity} {ticker} on broker")
                    execute_live_trade_with_bracket(
                        recorder_id=trade['recorder_id'],
                        action=close_action,  # Pass actual action, not 'CLOSE'
                        ticker=ticker,
                        quantity=quantity,
                        tp_ticks=None,
                        sl_ticks=None,
                        is_dca=True
                    )
                else:
                    logger.info(f"✅ Broker position already closed (TP limit filled) - skipping redundant close")
        
        conn.close()
        
    except Exception as e:
        logger.warning(f"Error checking TP/SL: {e}")


# ============================================================================
# TP/SL Polling Fallback (when WebSocket not available)
# ============================================================================

_tp_sl_polling_thread = None

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
            
            # Get trades with broker-managed TP/SL that are still open in DB
            cursor.execute('''
                SELECT t.id, t.recorder_id, t.ticker, t.side, t.entry_price, 
                       t.quantity, t.tp_price, t.sl_price, t.broker_strategy_id,
                       r.name as recorder_name
                FROM recorded_trades t
                JOIN recorders r ON t.recorder_id = r.id
                WHERE t.status = 'open' AND t.broker_managed_tp_sl = 1
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
            
            # Check each recorder's broker positions
            for recorder_id, trades in by_recorder.items():
                try:
                    # Sync with broker - this will detect if position closed
                    ticker = trades[0]['ticker']  # Use first trade's ticker
                    sync_result = sync_position_from_broker(recorder_id, ticker)
                    
                    if sync_result.get('success'):
                        broker_pos = sync_result.get('broker_position')
                        
                        # If broker has no position but DB does, bracket must have filled
                        if not broker_pos or broker_pos.get('netPos', 0) == 0:
                            # Position closed on broker - update DB
                            for trade in trades:
                                trade_ticker = trade['ticker']
                                trade_root = extract_symbol_root(trade_ticker)
                                
                                # Fetch current price to estimate exit
                                current_price = get_price_from_tradingview_api(trade_ticker)
                                
                                if not current_price:
                                    # Use TP or SL as exit price estimate
                                    if trade['side'] == 'LONG':
                                        # If price above entry, likely hit TP
                                        current_price = trade.get('tp_price') or trade.get('entry_price')
                                    else:
                                        current_price = trade.get('tp_price') or trade.get('entry_price')
                                
                                # Determine if TP or SL hit based on price
                                side = trade['side']
                                tp_price = trade.get('tp_price')
                                sl_price = trade.get('sl_price')
                                entry_price = trade['entry_price']
                                
                                if side == 'LONG':
                                    if tp_price and current_price >= tp_price:
                                        exit_reason = 'tp'
                                        exit_price = tp_price
                                    elif sl_price and current_price <= sl_price:
                                        exit_reason = 'sl'
                                        exit_price = sl_price
                                    else:
                                        exit_reason = 'broker_closed'
                                        exit_price = current_price
                                else:  # SHORT
                                    if tp_price and current_price <= tp_price:
                                        exit_reason = 'tp'
                                        exit_price = tp_price
                                    elif sl_price and current_price >= sl_price:
                                        exit_reason = 'sl'
                                        exit_price = sl_price
                                    else:
                                        exit_reason = 'broker_closed'
                                        exit_price = current_price
                                
                                # Calculate PnL
                                tick_size = get_tick_size(trade_ticker)
                                tick_value = get_tick_value(trade_ticker)
                                quantity = trade['quantity'] or 1
                                
                                if side == 'LONG':
                                    pnl_ticks = (exit_price - entry_price) / tick_size
                                else:
                                    pnl_ticks = (entry_price - exit_price) / tick_size
                                
                                pnl = pnl_ticks * tick_value * quantity
                                
                                # Update DB
                                conn2 = get_db_connection()
                                cursor2 = conn2.cursor()
                                
                                cursor2.execute('''
                                    UPDATE recorded_trades 
                                    SET exit_price = ?, exit_time = CURRENT_TIMESTAMP,
                                        pnl = ?, pnl_ticks = ?, status = 'closed',
                                        exit_reason = ?, updated_at = CURRENT_TIMESTAMP
                                    WHERE id = ?
                                ''', (exit_price, pnl, pnl_ticks, exit_reason, trade['id']))
                                
                                # Close position record
                                cursor2.execute('''
                                    UPDATE recorder_positions 
                                    SET status = 'closed'
                                    WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                                ''', (recorder_id, trade_ticker))
                                
                                conn2.commit()
                                conn2.close()
                                
                                # Rebuild index
                                rebuild_index()
                                
                                logger.info(f"🎯 BRACKET {exit_reason.upper()} detected for '{trade.get('recorder_name')}': "
                                           f"{side} {trade_ticker} | Entry: {entry_price:.2f} | Exit: {exit_price:.2f} | "
                                           f"PnL: ${pnl:.2f} ({pnl_ticks:.1f} ticks)")
                        
                        elif sync_result.get('db_updated'):
                            # Position synced (quantities/avg updated) 
                            logger.debug(f"📊 Position synced for recorder {recorder_id}")
                
                except Exception as e:
                    logger.warning(f"⚠️ Error checking recorder {recorder_id}: {e}")
            
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
        
        # Record the signal
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
        
        # Get position size from recorder settings or signal
        quantity = int(position_size) if position_size else recorder.get('initial_position_size', 1)
        
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
            if open_trade:
                if open_trade['side'] == 'LONG':
                    pnl_ticks = (current_price - open_trade['entry_price']) / tick_size
                else:
                    pnl_ticks = (open_trade['entry_price'] - current_price) / tick_size
                
                pnl, _ = close_trade_helper(cursor, open_trade, current_price, pnl_ticks, tick_value, 'signal')
                
                trade_result = {
                    'action': 'closed', 'trade_id': open_trade['id'], 'side': open_trade['side'],
                    'entry_price': open_trade['entry_price'], 'exit_price': current_price,
                    'pnl': pnl, 'pnl_ticks': pnl_ticks, 'exit_reason': 'SIGNAL'
                }
                logger.info(f"📊 Trade CLOSED by signal for '{recorder_name}': {open_trade['side']} {ticker} | PnL: ${pnl:.2f}")
            
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
                
                if broker_result.get('success') and broker_result.get('broker_position'):
                    # Use broker's data for DB update
                    broker_pos = broker_result['broker_position']
                    broker_qty = abs(broker_pos.get('netPos', 0))
                    broker_avg = broker_pos.get('netPrice', current_price)
                    
                    logger.info(f"📊 BROKER CONFIRMED DCA: {broker_qty} contracts @ avg {broker_avg}")
                    
                    # Calculate new TP based on broker's average price
                    new_tp_price, new_sl_price = calculate_tp_sl_prices(
                        broker_avg, 'LONG', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )
                    
                    # Update DB with broker's confirmed data
                    cursor.execute('''
                        UPDATE recorded_trades 
                        SET entry_price = ?, quantity = ?, tp_price = ?, sl_price = ?,
                            broker_fill_price = ?, broker_order_id = ?
                        WHERE id = ?
                    ''', (broker_avg, broker_qty, new_tp_price, new_sl_price,
                          broker_result.get('fill_price'), broker_result.get('order_id'),
                          open_trade['id']))
                    
                    # Update position tracking with broker data
                    cursor.execute('''
                        UPDATE recorder_positions 
                        SET total_quantity = ?, avg_entry_price = ?
                        WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                    ''', (broker_qty, broker_avg, recorder_id, ticker))
                    
                    trade_result = {
                        'action': 'dca', 'trade_id': open_trade['id'], 'side': 'LONG',
                        'dca_price': broker_result.get('fill_price', current_price),
                        'avg_entry_price': broker_avg,
                        'quantity': quantity, 'total_quantity': broker_qty,
                        'tp_price': new_tp_price, 'sl_price': new_sl_price,
                        'broker_confirmed': True
                    }
                    logger.info(f"📈 DCA LONG CONFIRMED for '{recorder_name}': {ticker} | Broker: {broker_qty} @ {broker_avg:.2f} | TP: {new_tp_price}")
                    
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
                    logger.info(f"📊 BROKER CONFIRMED: Filled @ {fill_price}, brackets={broker_managed}")

                    # Calculate TP/SL based on actual fill price
                    tp_price, sl_price = calculate_tp_sl_prices(
                        fill_price, 'LONG', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )

                    # Insert trade with broker data
                    cursor.execute('''
                        INSERT INTO recorded_trades
                        (recorder_id, signal_id, ticker, action, side, entry_price, entry_time,
                         quantity, status, tp_price, sl_price,
                         broker_order_id, broker_strategy_id, broker_fill_price, broker_managed_tp_sl)
                        VALUES (?, ?, ?, 'BUY', 'LONG', ?, CURRENT_TIMESTAMP, ?, 'open', ?, ?,
                                ?, ?, ?, ?)
                    ''', (recorder_id, signal_id, ticker, fill_price, quantity, tp_price, sl_price,
                          broker_result.get('order_id'), broker_result.get('strategy_id'),
                          broker_result.get('fill_price'), 1 if broker_managed else 0))

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
                
                if broker_result.get('success') and broker_result.get('broker_position'):
                    # Use broker's data for DB update
                    broker_pos = broker_result['broker_position']
                    broker_qty = abs(broker_pos.get('netPos', 0))
                    broker_avg = broker_pos.get('netPrice', current_price)
                    
                    logger.info(f"📊 BROKER CONFIRMED DCA: {broker_qty} contracts @ avg {broker_avg}")
                    
                    # Calculate new TP based on broker's average price
                    new_tp_price, new_sl_price = calculate_tp_sl_prices(
                        broker_avg, 'SHORT', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )
                    
                    # Update DB with broker's confirmed data
                    cursor.execute('''
                        UPDATE recorded_trades 
                        SET entry_price = ?, quantity = ?, tp_price = ?, sl_price = ?,
                            broker_fill_price = ?, broker_order_id = ?
                        WHERE id = ?
                    ''', (broker_avg, broker_qty, new_tp_price, new_sl_price,
                          broker_result.get('fill_price'), broker_result.get('order_id'),
                          open_trade['id']))
                    
                    # Update position tracking with broker data
                    cursor.execute('''
                        UPDATE recorder_positions 
                        SET total_quantity = ?, avg_entry_price = ?
                        WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                    ''', (broker_qty, broker_avg, recorder_id, ticker))
                    
                    trade_result = {
                        'action': 'dca', 'trade_id': open_trade['id'], 'side': 'SHORT',
                        'dca_price': broker_result.get('fill_price', current_price),
                        'avg_entry_price': broker_avg,
                        'quantity': quantity, 'total_quantity': broker_qty,
                        'tp_price': new_tp_price, 'sl_price': new_sl_price,
                        'broker_confirmed': True
                    }
                    logger.info(f"📉 DCA SHORT CONFIRMED for '{recorder_name}': {ticker} | Broker: {broker_qty} @ {broker_avg:.2f} | TP: {new_tp_price}")
                    
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
                    tp_price, sl_price = calculate_tp_sl_prices(
                        fill_price, 'SHORT', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                    )

                    # Insert trade with broker data
                    cursor.execute('''
                        INSERT INTO recorded_trades
                        (recorder_id, signal_id, ticker, action, side, entry_price, entry_time,
                         quantity, status, tp_price, sl_price,
                         broker_order_id, broker_strategy_id, broker_fill_price, broker_managed_tp_sl)
                        VALUES (?, ?, ?, 'SELL', 'SHORT', ?, CURRENT_TIMESTAMP, ?, 'open', ?, ?,
                                ?, ?, ?, ?)
                    ''', (recorder_id, signal_id, ticker, fill_price, quantity, tp_price, sl_price,
                          broker_result.get('order_id'), broker_result.get('strategy_id'),
                          broker_result.get('fill_price'), 1 if broker_managed else 0))

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
