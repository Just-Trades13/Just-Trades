#!/usr/bin/env python3
"""
🎯 Recorder Service - Event-Driven Trade Recording Engine

This service handles all trade recording functionality separately from the main server.
It provides:
1. Webhook endpoint for TradingView signals
2. Real-time price streaming via TradingView WebSocket
3. Event-driven drawdown tracking (updates on EVERY price tick)
4. TP/SL monitoring with instant execution
5. Position management with DCA support

Architecture:
- Runs on port 8083 (main server on 8082)
- Shares just_trades.db with main server
- Event-driven design for scalability (no polling)
- In-memory position index for O(1) lookups

Created: December 4, 2025
Backup: backups/WORKING_STATE_DEC4_2025_PRE_RECORDER_SERVICE/
"""

from __future__ import annotations
import sqlite3
import logging
import asyncio
import json
import time
import threading
import os
from datetime import datetime
from typing import Optional, Dict, List, Set, Any
from flask import Flask, request, jsonify

# ============================================================================
# Configuration
# ============================================================================

# Service configuration
SERVICE_PORT = 8083
DATABASE_PATH = 'just_trades.db'
LOG_LEVEL = logging.INFO

# Contract specifications for futures
CONTRACT_MULTIPLIERS = {
    'MES': 5.0,    # Micro E-mini S&P 500: $5 per point
    'MNQ': 2.0,    # Micro E-mini Nasdaq: $2 per point
    'ES': 50.0,    # E-mini S&P 500: $50 per point
    'NQ': 20.0,    # E-mini Nasdaq: $20 per point
    'MYM': 5.0,    # Micro E-mini Dow: $5 per point
    'YM': 5.0,     # E-mini Dow: $5 per point
    'M2K': 5.0,    # Micro E-mini Russell 2000: $5 per point
    'RTY': 50.0,   # E-mini Russell 2000: $50 per point
}

TICK_SIZES = {
    'MES': 0.25,
    'MNQ': 0.25,
    'ES': 0.25,
    'NQ': 0.25,
    'MYM': 1.0,
    'YM': 1.0,
    'M2K': 0.10,
    'RTY': 0.10,
}

TICK_VALUES = {
    'MES': 1.25,   # $1.25 per tick
    'MNQ': 0.50,   # $0.50 per tick
    'ES': 12.50,   # $12.50 per tick
    'NQ': 5.00,    # $5.00 per tick
    'MYM': 5.0,
    'YM': 5.0,
    'M2K': 0.50,
    'RTY': 5.00,
}

# ============================================================================
# Logging Setup
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

# Position index for O(1) lookup: {"MNQ": [pos_id_1, pos_id_2], "MES": [pos_id_3]}
_open_positions_by_symbol: Dict[str, List[int]] = {}

# Trade index for O(1) lookup: {"MNQ": [trade_id_1, trade_id_2], ...}
_open_trades_by_symbol: Dict[str, List[int]] = {}

# Lock for thread-safe index updates
_index_lock = threading.Lock()

# TradingView WebSocket state
_tradingview_ws = None
_tradingview_ws_thread = None
_tradingview_subscribed_symbols: Set[str] = set()

# WebSocket availability
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets library not installed. Install with: pip install websockets")


# ============================================================================
# Section 2: Database Helpers
# ============================================================================

def get_db_connection() -> sqlite3.Connection:
    """
    Get database connection with WAL mode for better concurrent access.
    Both main server and recorder service can read/write simultaneously.
    """
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')  # Better concurrency
    conn.execute('PRAGMA busy_timeout=30000')  # Wait up to 30s if locked
    conn.row_factory = sqlite3.Row
    return conn


def dict_from_row(row) -> Optional[Dict]:
    """Convert sqlite3.Row to dictionary"""
    if row is None:
        return None
    return dict(row)


# ============================================================================
# Section 3: Price Utilities
# ============================================================================

def extract_symbol_root(ticker: str) -> str:
    """
    Extract the root symbol from various ticker formats.
    Examples: MNQ1! -> MNQ, CME_MINI:MNQ1! -> MNQ, MNQZ24 -> MNQ
    """
    if not ticker:
        return ''
    
    # Remove exchange prefix
    if ':' in ticker:
        ticker = ticker.split(':')[-1]
    
    # Remove expiration suffix (1!, Z24, etc.)
    ticker = ticker.upper().replace('1!', '').replace('!', '')
    
    # Remove month/year codes (last 3-4 chars if they look like expiry)
    if len(ticker) > 3:
        # Check for patterns like MNQ Z24, MNQ H25
        base = ticker[:3]
        if base in CONTRACT_MULTIPLIERS:
            return base
        base = ticker[:2]
        if base in CONTRACT_MULTIPLIERS:
            return base
    
    # Try 3-char then 2-char prefix
    if ticker[:3] in CONTRACT_MULTIPLIERS:
        return ticker[:3]
    if ticker[:2] in CONTRACT_MULTIPLIERS:
        return ticker[:2]
    
    return ticker


def get_tick_size(ticker: str) -> float:
    """Get tick size for a symbol"""
    root = extract_symbol_root(ticker)
    return TICK_SIZES.get(root, 0.25)


def get_tick_value(ticker: str) -> float:
    """Get tick value ($ per tick) for a symbol"""
    root = extract_symbol_root(ticker)
    return TICK_VALUES.get(root, 0.50)


def get_contract_multiplier(ticker: str) -> float:
    """Get contract multiplier for a symbol"""
    root = extract_symbol_root(ticker)
    return CONTRACT_MULTIPLIERS.get(root, 1.0)


# ============================================================================
# Section 4: Position Index (In-Memory for O(1) Lookups)
# ============================================================================

def rebuild_position_index():
    """
    Rebuild the in-memory position index from database.
    Called on startup and after major changes.
    """
    global _open_positions_by_symbol, _open_trades_by_symbol
    
    with _index_lock:
        _open_positions_by_symbol.clear()
        _open_trades_by_symbol.clear()
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Index open positions
            cursor.execute('''
                SELECT id, ticker FROM recorder_positions WHERE status = 'open'
            ''')
            for row in cursor.fetchall():
                pos_id = row['id']
                ticker = row['ticker']
                root = extract_symbol_root(ticker)
                
                if root not in _open_positions_by_symbol:
                    _open_positions_by_symbol[root] = []
                _open_positions_by_symbol[root].append(pos_id)
            
            # Index open trades
            cursor.execute('''
                SELECT id, ticker FROM recorded_trades WHERE status = 'open'
            ''')
            for row in cursor.fetchall():
                trade_id = row['id']
                ticker = row['ticker']
                root = extract_symbol_root(ticker)
                
                if root not in _open_trades_by_symbol:
                    _open_trades_by_symbol[root] = []
                _open_trades_by_symbol[root].append(trade_id)
            
            conn.close()
            
            total_positions = sum(len(v) for v in _open_positions_by_symbol.values())
            total_trades = sum(len(v) for v in _open_trades_by_symbol.values())
            logger.info(f"📊 Position index rebuilt: {total_positions} positions, {total_trades} trades")
            
        except Exception as e:
            logger.error(f"Error rebuilding position index: {e}")


def add_position_to_index(symbol: str, position_id: int):
    """Add a position to the in-memory index"""
    root = extract_symbol_root(symbol)
    with _index_lock:
        if root not in _open_positions_by_symbol:
            _open_positions_by_symbol[root] = []
        if position_id not in _open_positions_by_symbol[root]:
            _open_positions_by_symbol[root].append(position_id)


def remove_position_from_index(symbol: str, position_id: int):
    """Remove a position from the in-memory index"""
    root = extract_symbol_root(symbol)
    with _index_lock:
        if root in _open_positions_by_symbol:
            if position_id in _open_positions_by_symbol[root]:
                _open_positions_by_symbol[root].remove(position_id)


def add_trade_to_index(symbol: str, trade_id: int):
    """Add a trade to the in-memory index"""
    root = extract_symbol_root(symbol)
    with _index_lock:
        if root not in _open_trades_by_symbol:
            _open_trades_by_symbol[root] = []
        if trade_id not in _open_trades_by_symbol[root]:
            _open_trades_by_symbol[root].append(trade_id)


def remove_trade_from_index(symbol: str, trade_id: int):
    """Remove a trade from the in-memory index"""
    root = extract_symbol_root(symbol)
    with _index_lock:
        if root in _open_trades_by_symbol:
            if trade_id in _open_trades_by_symbol[root]:
                _open_trades_by_symbol[root].remove(trade_id)


def get_positions_for_symbol(symbol: str) -> List[int]:
    """Get list of position IDs for a symbol (O(1) lookup)"""
    root = extract_symbol_root(symbol)
    with _index_lock:
        return _open_positions_by_symbol.get(root, []).copy()


def get_trades_for_symbol(symbol: str) -> List[int]:
    """Get list of trade IDs for a symbol (O(1) lookup)"""
    root = extract_symbol_root(symbol)
    with _index_lock:
        return _open_trades_by_symbol.get(root, []).copy()


# ============================================================================
# Section 5: Position Management
# ============================================================================

def get_position(position_id: int) -> Optional[Dict]:
    """Get position by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recorder_positions WHERE id = ?', (position_id,))
        row = cursor.fetchone()
        conn.close()
        return dict_from_row(row)
    except Exception as e:
        logger.error(f"Error getting position {position_id}: {e}")
        return None


def open_position(recorder_id: int, ticker: str, side: str, price: float, quantity: int = 1) -> int:
    """
    Open a new position or add to existing (DCA).
    Returns position_id.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check for existing open position
        cursor.execute('''
            SELECT id, total_quantity, avg_entry_price, entries, side
            FROM recorder_positions
            WHERE recorder_id = ? AND ticker = ? AND status = 'open'
        ''', (recorder_id, ticker))
        existing = cursor.fetchone()
        
        if existing:
            pos_id = existing['id']
            existing_side = existing['side']
            
            if existing_side == side:
                # Same side: Add to position (DCA)
                total_qty = existing['total_quantity']
                avg_entry = existing['avg_entry_price']
                entries = json.loads(existing['entries'] or '[]')
                
                new_qty = total_qty + quantity
                new_avg = ((avg_entry * total_qty) + (price * quantity)) / new_qty
                entries.append({
                    'price': price,
                    'qty': quantity,
                    'time': datetime.now().isoformat()
                })
                
                cursor.execute('''
                    UPDATE recorder_positions
                    SET total_quantity = ?, avg_entry_price = ?, entries = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (new_qty, new_avg, json.dumps(entries), pos_id))
                conn.commit()
                conn.close()
                
                logger.info(f"📈 Position DCA: {side} {ticker} +{quantity} @ {price} | "
                           f"Total: {new_qty} @ avg {new_avg:.2f}")
                return pos_id
            else:
                # Opposite side: Close existing position first
                close_position(pos_id, price, 'reversal')
                # Fall through to create new position
        
        # Create new position
        entries = json.dumps([{
            'price': price,
            'qty': quantity,
            'time': datetime.now().isoformat()
        }])
        
        cursor.execute('''
            INSERT INTO recorder_positions 
            (recorder_id, ticker, side, total_quantity, avg_entry_price, entries,
             current_price, unrealized_pnl, worst_unrealized_pnl, best_unrealized_pnl,
             status, opened_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 'open', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (recorder_id, ticker, side, quantity, price, entries, price))
        
        conn.commit()
        pos_id = cursor.lastrowid
        conn.close()
        
        # Add to index
        add_position_to_index(ticker, pos_id)
        
        logger.info(f"📊 New position opened: {side} {ticker} x{quantity} @ {price} (ID: {pos_id})")
        return pos_id
        
    except Exception as e:
        logger.error(f"Error opening position: {e}")
        return -1


def close_position(position_id: int, exit_price: float, reason: str = 'signal') -> Optional[float]:
    """
    Close a position and calculate final PnL.
    Returns realized PnL.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM recorder_positions WHERE id = ?', (position_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        pos = dict(row)
        
        if pos['status'] != 'open':
            conn.close()
            return None
        
        ticker = pos['ticker']
        side = pos['side']
        avg_entry = pos['avg_entry_price']
        total_qty = pos['total_quantity']
        
        tick_size = get_tick_size(ticker)
        tick_value = get_tick_value(ticker)
        
        # Calculate PnL
        if side == 'LONG':
            pnl_ticks = (exit_price - avg_entry) / tick_size
        else:  # SHORT
            pnl_ticks = (avg_entry - exit_price) / tick_size
        
        realized_pnl = pnl_ticks * tick_value * total_qty
        
        cursor.execute('''
            UPDATE recorder_positions
            SET status = 'closed',
                exit_price = ?,
                realized_pnl = ?,
                closed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (exit_price, realized_pnl, position_id))
        
        conn.commit()
        conn.close()
        
        # Remove from index
        remove_position_from_index(ticker, position_id)
        
        logger.info(f"📊 Position closed: {side} {ticker} x{total_qty} | "
                   f"Entry: {avg_entry:.2f} → Exit: {exit_price:.2f} | "
                   f"PnL: ${realized_pnl:.2f} ({reason})")
        
        return realized_pnl
        
    except Exception as e:
        logger.error(f"Error closing position {position_id}: {e}")
        return None


def update_position_drawdown(position_id: int, current_price: float) -> bool:
    """
    Update position's unrealized PnL and drawdown (worst_unrealized_pnl).
    This is called on EVERY price tick - the key to accurate drawdown tracking.
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
        
        # Calculate current unrealized P&L
        if side == 'LONG':
            pnl_ticks = (current_price - avg_entry) / tick_size
        else:  # SHORT
            pnl_ticks = (avg_entry - current_price) / tick_size
        
        unrealized_pnl = pnl_ticks * tick_value * total_qty
        
        # Update worst/best unrealized P&L
        current_worst = pos['worst_unrealized_pnl'] or 0
        current_best = pos['best_unrealized_pnl'] or 0
        
        new_worst = min(current_worst, unrealized_pnl)  # Most negative
        new_best = max(current_best, unrealized_pnl)    # Most positive
        
        # Only update if values changed (reduces DB writes)
        if (new_worst != current_worst or 
            new_best != current_best or 
            pos['current_price'] != current_price):
            
            cursor.execute('''
                UPDATE recorder_positions
                SET current_price = ?,
                    unrealized_pnl = ?,
                    worst_unrealized_pnl = ?,
                    best_unrealized_pnl = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (current_price, unrealized_pnl, new_worst, new_best, position_id))
            
            conn.commit()
            
            # Log significant drawdown changes
            if new_worst < current_worst:
                logger.debug(f"📉 Drawdown update: Position {position_id} | "
                            f"Worst: ${abs(new_worst):.2f}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error updating position drawdown: {e}")
        return False


# ============================================================================
# Section 6: Trade Management
# ============================================================================

def get_trade(trade_id: int) -> Optional[Dict]:
    """Get trade by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recorded_trades WHERE id = ?', (trade_id,))
        row = cursor.fetchone()
        conn.close()
        return dict_from_row(row)
    except Exception as e:
        logger.error(f"Error getting trade {trade_id}: {e}")
        return None


def open_trade(recorder_id: int, signal_id: int, ticker: str, side: str, 
               price: float, quantity: int, tp_price: float = None, 
               sl_price: float = None, tp_ticks: float = None, 
               sl_ticks: float = None) -> int:
    """Open a new trade. Returns trade_id."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        action = 'BUY' if side == 'LONG' else 'SELL'
        
        cursor.execute('''
            INSERT INTO recorded_trades 
            (recorder_id, signal_id, ticker, action, side, entry_price, entry_time,
             quantity, status, tp_price, sl_price, tp_ticks, sl_ticks,
             max_favorable, max_adverse, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 'open', ?, ?, ?, ?, 0, 0,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (recorder_id, signal_id, ticker, action, side, price, quantity,
              tp_price, sl_price, tp_ticks, sl_ticks))
        
        conn.commit()
        trade_id = cursor.lastrowid
        conn.close()
        
        # Add to index
        add_trade_to_index(ticker, trade_id)
        
        logger.info(f"📈 Trade opened: {side} {ticker} x{quantity} @ {price} | "
                   f"TP: {tp_price} | SL: {sl_price} (ID: {trade_id})")
        return trade_id
        
    except Exception as e:
        logger.error(f"Error opening trade: {e}")
        return -1


def close_trade(trade_id: int, exit_price: float, reason: str = 'signal') -> Optional[float]:
    """Close a trade and calculate PnL. Returns PnL."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM recorded_trades WHERE id = ?', (trade_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        trade = dict(row)
        
        if trade['status'] != 'open':
            conn.close()
            return None
        
        ticker = trade['ticker']
        side = trade['side']
        entry_price = trade['entry_price']
        quantity = trade['quantity']
        
        tick_size = get_tick_size(ticker)
        tick_value = get_tick_value(ticker)
        
        # Calculate PnL
        if side == 'LONG':
            pnl_ticks = (exit_price - entry_price) / tick_size
        else:  # SHORT
            pnl_ticks = (entry_price - exit_price) / tick_size
        
        pnl = pnl_ticks * tick_value * quantity
        
        cursor.execute('''
            UPDATE recorded_trades 
            SET exit_price = ?, exit_time = CURRENT_TIMESTAMP, 
                pnl = ?, pnl_ticks = ?, status = 'closed', 
                exit_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (exit_price, pnl, pnl_ticks, reason, trade_id))
        
        conn.commit()
        conn.close()
        
        # Remove from index
        remove_trade_from_index(ticker, trade_id)
        
        logger.info(f"📊 Trade closed: {side} {ticker} x{quantity} | "
                   f"Entry: {entry_price:.2f} → Exit: {exit_price:.2f} | "
                   f"PnL: ${pnl:.2f} ({pnl_ticks:.1f} ticks) [{reason}]")
        
        return pnl
        
    except Exception as e:
        logger.error(f"Error closing trade {trade_id}: {e}")
        return None


def update_trade_mfe_mae(trade_id: int, current_price: float) -> bool:
    """Update trade's MFE (Max Favorable) and MAE (Max Adverse) excursions."""
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
        
        # Calculate excursions
        if side == 'LONG':
            favorable = max(0, current_price - entry_price)
            adverse = max(0, entry_price - current_price)
        else:  # SHORT
            favorable = max(0, entry_price - current_price)
            adverse = max(0, current_price - entry_price)
        
        new_mfe = max(current_mfe, favorable)
        new_mae = max(current_mae, adverse)
        
        # Only update if changed
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
# Section 7: Price Event Handler (THE KEY TO ACCURATE DRAWDOWN)
# ============================================================================

def on_price_update(symbol: str, price: float):
    """
    Called on EVERY price tick from TradingView WebSocket.
    
    This is the heart of the event-driven system:
    1. Get all positions for this symbol (O(1) lookup)
    2. Update drawdown for each position
    3. Check TP/SL and close if hit
    4. Update MFE/MAE for trades
    
    This ensures we NEVER miss a drawdown value, even for fast trades.
    """
    global _market_data_cache
    
    # Update cache
    root = extract_symbol_root(symbol)
    if root not in _market_data_cache:
        _market_data_cache[root] = {}
    _market_data_cache[root]['last'] = price
    _market_data_cache[root]['updated'] = time.time()
    
    # Get positions for this symbol (O(1) lookup)
    position_ids = get_positions_for_symbol(symbol)
    
    for pos_id in position_ids:
        # Update drawdown
        update_position_drawdown(pos_id, price)
        
        # Check TP/SL
        check_position_tp_sl(pos_id, price)
    
    # Get trades for this symbol (O(1) lookup)
    trade_ids = get_trades_for_symbol(symbol)
    
    for trade_id in trade_ids:
        # Update MFE/MAE
        update_trade_mfe_mae(trade_id, price)
        
        # Check TP/SL
        check_trade_tp_sl(trade_id, price)


def check_position_tp_sl(position_id: int, current_price: float):
    """Check if position hit TP or SL based on underlying trades."""
    # Positions don't have direct TP/SL - they close when trades close
    # This is handled by check_trade_tp_sl
    pass


def check_trade_tp_sl(trade_id: int, current_price: float):
    """Check if trade hit TP or SL and close if so."""
    try:
        trade = get_trade(trade_id)
        if not trade or trade['status'] != 'open':
            return
        
        side = trade['side']
        tp_price = trade.get('tp_price')
        sl_price = trade.get('sl_price')
        ticker = trade['ticker']
        recorder_id = trade['recorder_id']
        
        hit_type = None
        exit_price = None
        
        if side == 'LONG':
            if tp_price and current_price >= tp_price:
                hit_type = 'tp'
                exit_price = tp_price
            elif sl_price and current_price <= sl_price:
                hit_type = 'sl'
                exit_price = sl_price
        else:  # SHORT
            if tp_price and current_price <= tp_price:
                hit_type = 'tp'
                exit_price = tp_price
            elif sl_price and current_price >= sl_price:
                hit_type = 'sl'
                exit_price = sl_price
        
        if hit_type and exit_price:
            # Close the trade
            pnl = close_trade(trade_id, exit_price, hit_type)
            
            # Also close the corresponding position
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM recorder_positions 
                WHERE recorder_id = ? AND ticker = ? AND status = 'open'
            ''', (recorder_id, ticker))
            pos_row = cursor.fetchone()
            conn.close()
            
            if pos_row:
                close_position(pos_row['id'], exit_price, hit_type)
            
            logger.info(f"🎯 {hit_type.upper()} HIT: Trade {trade_id} | "
                       f"Exit: {exit_price} | PnL: ${pnl:.2f}")
            
    except Exception as e:
        logger.error(f"Error checking trade TP/SL: {e}")


# ============================================================================
# Section 8: Webhook Handler
# ============================================================================

@app.route('/webhook/<webhook_token>', methods=['POST'])
def receive_webhook(webhook_token: str):
    """
    Receive webhook from TradingView alerts/strategies.
    
    Expected JSON:
    {
        "recorder": "STRATEGY_NAME",
        "action": "buy" | "sell" | "close" | "tp_hit" | "sl_hit",
        "ticker": "MNQ1!",
        "price": "25580.50",
        "position_size": "2",  (optional)
        "market_position": "long" | "short" | "flat"  (optional)
    }
    """
    try:
        # Find recorder by webhook token
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM recorders WHERE webhook_token = ? AND recording_enabled = 1
        ''', (webhook_token,))
        recorder_row = cursor.fetchone()
        
        if not recorder_row:
            logger.warning(f"Webhook for unknown/disabled token: {webhook_token[:8]}...")
            conn.close()
            return jsonify({'success': False, 'error': 'Invalid webhook'}), 404
        
        recorder = dict(recorder_row)
        recorder_id = recorder['id']
        recorder_name = recorder['name']
        
        # Parse incoming data
        if request.is_json:
            data = request.get_json()
        else:
            try:
                data = json.loads(request.data.decode('utf-8'))
            except:
                data = request.form.to_dict()
        
        if not data:
            conn.close()
            return jsonify({'success': False, 'error': 'No data'}), 400
        
        logger.info(f"📨 Webhook received for '{recorder_name}': {data}")
        
        # Extract signal data
        action = str(data.get('action', '')).lower().strip()
        ticker = data.get('ticker', data.get('symbol', ''))
        price_str = data.get('price', data.get('close', 0))
        current_price = float(price_str) if price_str else 0
        
        position_size = data.get('position_size', data.get('contracts'))
        market_position = data.get('market_position', '')
        
        # Validate action
        valid_actions = ['buy', 'sell', 'long', 'short', 'close', 'flat', 'exit',
                        'tp_hit', 'sl_hit', 'take_profit', 'stop_loss']
        if action not in valid_actions:
            conn.close()
            return jsonify({'success': False, 'error': f'Invalid action: {action}'}), 400
        
        # Normalize action
        if action in ['tp_hit', 'take_profit']:
            normalized_action = 'TP_HIT'
        elif action in ['sl_hit', 'stop_loss']:
            normalized_action = 'SL_HIT'
        elif action in ['long', 'buy']:
            normalized_action = 'BUY'
        elif action in ['short', 'sell']:
            normalized_action = 'SELL'
        else:
            normalized_action = 'CLOSE'
        
        # Get quantity
        quantity = int(position_size) if position_size else recorder.get('initial_position_size', 1)
        
        # Get TP/SL settings
        sl_enabled = recorder.get('sl_enabled', 0)
        sl_amount = recorder.get('sl_amount', 0) or 0
        
        tp_targets_raw = recorder.get('tp_targets', '[]')
        try:
            tp_targets = json.loads(tp_targets_raw) if isinstance(tp_targets_raw, str) else tp_targets_raw or []
        except:
            tp_targets = []
        tp_ticks = tp_targets[0].get('value', 0) if tp_targets else 0
        
        tick_size = get_tick_size(ticker)
        tick_value = get_tick_value(ticker)
        
        # Record signal
        cursor.execute('''
            INSERT INTO recorded_signals 
            (recorder_id, action, ticker, price, position_size, market_position, 
             signal_type, raw_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (recorder_id, normalized_action, ticker, current_price,
              str(position_size) if position_size else None, market_position,
              'strategy' if position_size else 'alert', json.dumps(data)))
        signal_id = cursor.lastrowid
        conn.commit()
        
        # Check for existing open trade
        cursor.execute('''
            SELECT * FROM recorded_trades 
            WHERE recorder_id = ? AND status = 'open' 
            ORDER BY entry_time DESC LIMIT 1
        ''', (recorder_id,))
        open_trade_row = cursor.fetchone()
        existing_trade = dict(open_trade_row) if open_trade_row else None
        
        trade_result = None
        
        # Calculate TP/SL prices helper
        def calc_tp_sl(entry, side, tp_t, sl_t, ts):
            if side == 'LONG':
                tp_p = entry + (tp_t * ts) if tp_t else None
                sl_p = entry - (sl_t * ts) if sl_t else None
            else:
                tp_p = entry - (tp_t * ts) if tp_t else None
                sl_p = entry + (sl_t * ts) if sl_t else None
            return tp_p, sl_p
        
        # Process signal
        if normalized_action in ['TP_HIT', 'SL_HIT']:
            if existing_trade:
                exit_p = existing_trade.get('tp_price' if normalized_action == 'TP_HIT' else 'sl_price') or current_price
                pnl = close_trade(existing_trade['id'], exit_p, normalized_action.lower().replace('_hit', ''))
                
                # Close position too
                cursor.execute('''
                    SELECT id FROM recorder_positions 
                    WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                ''', (recorder_id, ticker))
                pos = cursor.fetchone()
                if pos:
                    close_position(pos['id'], exit_p, normalized_action.lower().replace('_hit', ''))
                
                trade_result = {'action': 'closed', 'pnl': pnl, 'reason': normalized_action}
        
        elif normalized_action == 'CLOSE' or market_position == 'flat':
            if existing_trade:
                side = existing_trade['side']
                entry = existing_trade['entry_price']
                pnl = close_trade(existing_trade['id'], current_price, 'signal')
                
                # Close position too
                cursor.execute('''
                    SELECT id FROM recorder_positions 
                    WHERE recorder_id = ? AND ticker = ? AND status = 'open'
                ''', (recorder_id, ticker))
                pos = cursor.fetchone()
                if pos:
                    close_position(pos['id'], current_price, 'signal')
                
                trade_result = {'action': 'closed', 'pnl': pnl, 'reason': 'signal'}
        
        elif normalized_action == 'BUY':
            # Close any SHORT first
            if existing_trade and existing_trade['side'] == 'SHORT':
                pnl = close_trade(existing_trade['id'], current_price, 'reversal')
                existing_trade = None
            
            if not existing_trade:
                # Calculate TP/SL
                tp_price, sl_price = calc_tp_sl(
                    current_price, 'LONG', tp_ticks, 
                    sl_amount if sl_enabled else 0, tick_size
                )
                
                # Open trade
                new_trade_id = open_trade(recorder_id, signal_id, ticker, 'LONG',
                                     current_price, quantity, tp_price, sl_price,
                                     tp_ticks, sl_amount if sl_enabled else None)
                
                # Open/update position
                pos_id = open_position(recorder_id, ticker, 'LONG', current_price, quantity)
                
                trade_result = {
                    'action': 'opened',
                    'trade_id': new_trade_id,
                    'position_id': pos_id,
                    'side': 'LONG',
                    'price': current_price
                }
        
        elif normalized_action == 'SELL':
            # Close any LONG first
            if existing_trade and existing_trade['side'] == 'LONG':
                pnl = close_trade(existing_trade['id'], current_price, 'reversal')
                existing_trade = None
            
            if not existing_trade:
                # Calculate TP/SL
                tp_price, sl_price = calc_tp_sl(
                    current_price, 'SHORT', tp_ticks,
                    sl_amount if sl_enabled else 0, tick_size
                )
                
                # Open trade
                new_trade_id = open_trade(recorder_id, signal_id, ticker, 'SHORT',
                                     current_price, quantity, tp_price, sl_price,
                                     tp_ticks, sl_amount if sl_enabled else None)
                
                # Open/update position
                pos_id = open_position(recorder_id, ticker, 'SHORT', current_price, quantity)
                
                trade_result = {
                    'action': 'opened',
                    'trade_id': new_trade_id,
                    'position_id': pos_id,
                    'side': 'SHORT',
                    'price': current_price
                }
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'signal_id': signal_id,
            'recorder': recorder_name,
            'action': normalized_action,
            'trade': trade_result
        })
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Section 9: TradingView WebSocket
# ============================================================================

def get_tradingview_session() -> Optional[Dict]:
    """Get TradingView session cookies from database"""
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
        logger.error("websockets library not available")
        return
    
    session = get_tradingview_session()
    if not session or not session.get('sessionid'):
        logger.warning("No TradingView session. Configure via main server.")
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
                auth_msg = json.dumps({
                    "m": "set_auth_token",
                    "p": ["unauthorized_user_token"]
                })
                await ws.send(f"~m~{len(auth_msg)}~m~{auth_msg}")
                
                # Create quote session
                quote_session = f"qs_{int(time.time())}"
                create_msg = json.dumps({
                    "m": "quote_create_session",
                    "p": [quote_session]
                })
                await ws.send(f"~m~{len(create_msg)}~m~{create_msg}")
                
                # Subscribe to symbols
                await subscribe_tradingview_symbols(ws, quote_session)
                
                # Listen for messages
                async for message in ws:
                    try:
                        if message.startswith('~h~'):
                            await ws.send(message)
                            continue
                        
                        await process_tradingview_message(message)
                        
                    except Exception as e:
                        logger.warning(f"Error processing message: {e}")
                        
        except Exception as e:
            logger.warning(f"TradingView WebSocket error: {e}. Reconnecting in 10s...")
            await asyncio.sleep(10)


async def subscribe_tradingview_symbols(ws, quote_session: str):
    """Subscribe to symbols for real-time quotes"""
    global _tradingview_subscribed_symbols
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT ticker FROM recorded_trades 
            WHERE status = 'open' AND ticker IS NOT NULL
        ''')
        
        symbols = set()
        for row in cursor.fetchall():
            ticker = row['ticker']
            if ticker:
                root = extract_symbol_root(ticker)
                tv_symbol = f"CME_MINI:{root}1!" if root in ['MNQ', 'MES', 'M2K'] else f"CME:{root}1!"
                symbols.add(tv_symbol)
        conn.close()
        
        # Add default symbols
        default_symbols = ['CME_MINI:MNQ1!', 'CME_MINI:MES1!', 'CME:NQ1!', 'CME:ES1!']
        symbols.update(default_symbols)
        
        for symbol in symbols:
            if symbol not in _tradingview_subscribed_symbols:
                add_msg = json.dumps({
                    "m": "quote_add_symbols",
                    "p": [quote_session, symbol]
                })
                await ws.send(f"~m~{len(add_msg)}~m~{add_msg}")
                _tradingview_subscribed_symbols.add(symbol)
                logger.info(f"📈 Subscribed to: {symbol}")
                
    except Exception as e:
        logger.error(f"Error subscribing to symbols: {e}")


async def process_tradingview_message(message: str):
    """Process incoming TradingView message and call on_price_update"""
    global _market_data_cache
    
    try:
        if not message or message.startswith('~h~') or not message.startswith('~m~'):
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
                                price = float(last_price)
                                
                                logger.debug(f"💰 Price: {root} = {price}")
                                
                                # THE KEY CALL - this updates drawdown on every tick
                                on_price_update(root, price)
                                
            except json.JSONDecodeError:
                continue
                
    except Exception as e:
        logger.debug(f"Error processing TradingView message: {e}")


def start_tradingview_websocket():
    """Start TradingView WebSocket in background thread"""
    global _tradingview_ws_thread
    
    if _tradingview_ws_thread and _tradingview_ws_thread.is_alive():
        logger.info("TradingView WebSocket already running")
        return
    
    def run_websocket():
        asyncio.run(connect_tradingview_websocket())
    
    _tradingview_ws_thread = threading.Thread(target=run_websocket, daemon=True)
    _tradingview_ws_thread.start()
    logger.info("✅ TradingView WebSocket thread started")


# ============================================================================
# Section 10: Health & Status Endpoints
# ============================================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'service': 'recorder_service',
        'timestamp': datetime.now().isoformat()
    })


@app.route('/status', methods=['GET'])
def status():
    """Get service status and stats"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as count FROM recorder_positions WHERE status = ?', ('open',))
        open_positions = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM recorded_trades WHERE status = ?', ('open',))
        open_trades = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM recorders WHERE recording_enabled = 1')
        active_recorders = cursor.fetchone()['count']
        
        conn.close()
        
        return jsonify({
            'status': 'running',
            'open_positions': open_positions,
            'open_trades': open_trades,
            'active_recorders': active_recorders,
            'websocket_connected': _tradingview_ws is not None,
            'subscribed_symbols': list(_tradingview_subscribed_symbols),
            'cached_prices': {k: v.get('last') for k, v in _market_data_cache.items()},
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/index', methods=['GET'])
def view_index():
    """View the in-memory position/trade index"""
    return jsonify({
        'positions_by_symbol': {k: v for k, v in _open_positions_by_symbol.items()},
        'trades_by_symbol': {k: v for k, v in _open_trades_by_symbol.items()}
    })


# ============================================================================
# Section 11: Startup
# ============================================================================

def initialize():
    """Initialize the recorder service"""
    logger.info("=" * 60)
    logger.info("🚀 Recorder Service Starting...")
    logger.info("=" * 60)
    
    # Rebuild position index from database
    rebuild_position_index()
    
    # Start TradingView WebSocket if session configured
    try:
        session = get_tradingview_session()
        if session and session.get('sessionid'):
            start_tradingview_websocket()
            logger.info("✅ TradingView WebSocket started")
        else:
            logger.info("ℹ️ TradingView session not configured")
    except Exception as e:
        logger.warning(f"Could not start TradingView WebSocket: {e}")
    
    logger.info("=" * 60)
    logger.info(f"✅ Recorder Service ready on port {SERVICE_PORT}")
    logger.info("=" * 60)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    initialize()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=False, threaded=True)
