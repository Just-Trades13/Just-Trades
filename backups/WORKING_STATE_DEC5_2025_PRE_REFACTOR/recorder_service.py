#!/usr/bin/env python3
"""
🎯 Recorder Service - Event-Driven Drawdown Tracking

PURPOSE:
This service ONLY handles real-time drawdown tracking via price streaming.
All webhook processing and trade logic stays in the main server.

RESPONSIBILITIES:
1. Stream prices via TradingView WebSocket
2. Update position drawdown (worst_unrealized_pnl) on every price tick
3. Update trade MFE/MAE on every price tick
4. Provide API for main server to refresh position index

WHAT THIS DOES NOT DO:
- Process webhooks (main server does this)
- Create/close trades (main server does this)
- Handle recorder settings (main server does this)

Architecture:
- Runs on port 8083
- Shares just_trades.db with main server
- Main server handles ALL business logic
- This service ONLY tracks drawdown in real-time

Created: December 4, 2025
"""

from __future__ import annotations
import sqlite3
import logging
import asyncio
import json
import time
import threading
from datetime import datetime
from typing import Optional, Dict, List, Set, Any
from flask import Flask, request, jsonify

# ============================================================================
# Configuration
# ============================================================================

SERVICE_PORT = 8083
DATABASE_PATH = 'just_trades.db'
LOG_LEVEL = logging.INFO

# Contract specifications
CONTRACT_MULTIPLIERS = {
    'MES': 5.0, 'MNQ': 2.0, 'ES': 50.0, 'NQ': 20.0,
    'MYM': 5.0, 'YM': 5.0, 'M2K': 5.0, 'RTY': 50.0,
}

TICK_SIZES = {
    'MES': 0.25, 'MNQ': 0.25, 'ES': 0.25, 'NQ': 0.25,
    'MYM': 1.0, 'YM': 1.0, 'M2K': 0.10, 'RTY': 0.10,
}

TICK_VALUES = {
    'MES': 1.25, 'MNQ': 0.50, 'ES': 12.50, 'NQ': 5.00,
    'MYM': 5.0, 'YM': 5.0, 'M2K': 0.50, 'RTY': 5.00,
}

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('recorder_service')

# ============================================================================
# Flask App
# ============================================================================

app = Flask(__name__)

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


# ============================================================================
# Price Utilities
# ============================================================================

def extract_symbol_root(ticker: str) -> str:
    """Extract root symbol: MNQ1! -> MNQ, CME_MINI:MNQ1! -> MNQ"""
    if not ticker:
        return ''
    if ':' in ticker:
        ticker = ticker.split(':')[-1]
    ticker = ticker.upper().replace('1!', '').replace('!', '')
    if len(ticker) > 3:
        base = ticker[:3]
        if base in CONTRACT_MULTIPLIERS:
            return base
    if ticker[:3] in CONTRACT_MULTIPLIERS:
        return ticker[:3]
    if ticker[:2] in CONTRACT_MULTIPLIERS:
        return ticker[:2]
    return ticker


def get_tick_size(ticker: str) -> float:
    return TICK_SIZES.get(extract_symbol_root(ticker), 0.25)


def get_tick_value(ticker: str) -> float:
    return TICK_VALUES.get(extract_symbol_root(ticker), 0.50)


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
    
    # Update trades
    for trade_id in get_trades_for_symbol(symbol):
        update_trade_mfe_mae(trade_id, price)


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
    
    session = get_tradingview_session()
    if not session or not session.get('sessionid'):
        logger.warning("No TradingView session configured")
        return
    
    import websockets
    
    sessionid = session.get('sessionid')
    sessionid_sign = session.get('sessionid_sign', '')
    ws_url = "wss://data.tradingview.com/socket.io/websocket"
    
    while True:
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
                        await process_message(message)
                    except Exception as e:
                        logger.warning(f"Error processing message: {e}")
                        
        except Exception as e:
            logger.warning(f"TradingView WebSocket error: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)


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
        'service': 'recorder_service',
        'purpose': 'drawdown_tracking_only',
        'timestamp': datetime.now().isoformat()
    })


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
# Startup
# ============================================================================

def initialize():
    """Initialize the service"""
    logger.info("=" * 60)
    logger.info("🎯 Recorder Service - Drawdown Tracking Only")
    logger.info("=" * 60)
    logger.info("This service ONLY tracks drawdown in real-time.")
    logger.info("All webhook/trade logic is handled by main server.")
    logger.info("=" * 60)
    
    # Build index
    rebuild_index()
    
    # Start TradingView WebSocket
    try:
        session = get_tradingview_session()
        if session and session.get('sessionid'):
            start_tradingview_websocket()
        else:
            logger.info("ℹ️ TradingView session not configured")
    except Exception as e:
        logger.warning(f"Could not start WebSocket: {e}")
    
    logger.info(f"✅ Service ready on port {SERVICE_PORT}")
    logger.info("=" * 60)


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    initialize()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=False, threaded=True)
