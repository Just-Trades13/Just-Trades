#!/usr/bin/env python3
"""
Standalone Recorder Backend Service - Production Ready
Runs independently to handle recorder operations (start/stop recording, poll positions)
Designed for multi-user production deployment with proper authentication and resource management
"""

import sqlite3
import logging
import asyncio
import threading
import time
import argparse
import sys
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, g
from functools import wraps
from typing import Dict, List, Optional, Any
from threading import Lock
from queue import Queue
import atexit

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import Tradovate integration
try:
    from phantom_scraper.tradovate_integration import TradovateIntegration
    TRADOVATE_AVAILABLE = True
except ImportError:
    print("Warning: Tradovate integration not found. Some features may not work.")
    TRADOVATE_AVAILABLE = False

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[
        logging.FileHandler('recorder_backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Database path
DB_PATH = os.getenv('DB_PATH', 'just_trades.db')

# API Authentication
API_KEY_HEADER = 'X-API-Key'
API_KEY_ENV = os.getenv('RECORDER_API_KEY', None)

# Production settings
MAX_RECORDINGS_PER_USER = int(os.getenv('MAX_RECORDINGS_PER_USER', '10'))
MAX_CONCURRENT_RECORDINGS = int(os.getenv('MAX_CONCURRENT_RECORDINGS', '100'))
POLL_INTERVAL_MIN = int(os.getenv('POLL_INTERVAL_MIN', '10'))  # Minimum 10 seconds
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))

# Global recorder state with thread safety
recorder_state = {
    'active_recordings': {},  # strategy_id -> {'thread': thread, 'user_id': user_id, 'started_at': datetime}
    'running': True,
    'lock': Lock(),  # Thread lock for state modifications
    'user_recordings': {}  # user_id -> set of strategy_ids
}

# Database connection pool (simple implementation)
db_pool = Queue(maxsize=DB_POOL_SIZE)
db_pool_lock = Lock()


def get_db_connection():
    """Get database connection (with simple connection pooling)"""
    try:
        conn = db_pool.get_nowait()
        # Test if connection is still valid
        try:
            conn.execute('SELECT 1').fetchone()
        except sqlite3.ProgrammingError:
            # Connection is closed, create new one
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
    except:
        # Pool is empty or connection invalid, create new one
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
    
    return conn


def return_db_connection(conn):
    """Return connection to pool"""
    try:
        db_pool.put_nowait(conn)
    except:
        # Pool is full, close connection
        conn.close()


def init_db_pool():
    """Initialize database connection pool"""
    for _ in range(min(DB_POOL_SIZE, 5)):  # Start with 5 connections
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        db_pool.put(conn)
    logger.info(f"Initialized database connection pool with {db_pool.qsize()} connections")


def init_database():
    """Initialize database tables if they don't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create strategies table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            account_id INTEGER,
            demo_account_id INTEGER,
            name TEXT NOT NULL,
            symbol TEXT,
            recording_enabled INTEGER DEFAULT 1,
            take_profit REAL,
            stop_loss REAL,
            tpsl_units TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create accounts table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            username TEXT,
            password TEXT,
            client_id TEXT,
            client_secret TEXT,
            tradovate_token TEXT,
            tradovate_refresh_token TEXT,
            token_expires_at TIMESTAMP,
            enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create recorded_positions table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorded_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            entry_price REAL NOT NULL,
            entry_timestamp TIMESTAMP NOT NULL,
            exit_price REAL,
            exit_timestamp TIMESTAMP,
            exit_reason TEXT,
            pnl REAL,
            pnl_percent REAL,
            stop_loss_price REAL,
            take_profit_price REAL,
            tradovate_position_id TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    ''')
    
    # Create strategy_logs table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            log_type TEXT NOT NULL,
            message TEXT NOT NULL,
            data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


async def get_positions_from_tradovate(tradovate_account_spec: str, db_account_id: int = None) -> List[Dict[str, Any]]:
    """
    Get positions from Tradovate for an account using OAuth tokens
    Uses stored OAuth tokens from database (bypasses CAPTCHA)
    Automatically refreshes tokens if expired
    
    Args:
        tradovate_account_spec: Tradovate account spec (e.g., "TAKEPROFITPRO776831105")
        db_account_id: Database account ID (optional, will look up if not provided)
    """
    if not TRADOVATE_AVAILABLE:
        logger.error("Tradovate integration not available")
        return []
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # If db_account_id not provided, we need to find it from strategies table
        # (This is a workaround - ideally we'd store account_id with demo_account_id)
        if not db_account_id:
            cursor.execute("""
                SELECT account_id FROM strategies
                WHERE demo_account_id = ? AND recording_enabled = 1
                LIMIT 1
            """, (tradovate_account_spec,))
            result = cursor.fetchone()
            if result:
                db_account_id = result['account_id']
            else:
                logger.error(f"Could not find database account_id for Tradovate account {tradovate_account_spec}")
                return []
        
        # Get account credentials and OAuth tokens
        cursor.execute("""
            SELECT username, password, client_id, client_secret,
                   tradovate_token, tradovate_refresh_token, token_expires_at
            FROM accounts
            WHERE id = ? AND enabled = 1
        """, (db_account_id,))
        
        account = cursor.fetchone()
    
        if not account:
            logger.error(f"Account {db_account_id} not found or disabled")
            return []
    
        token = account['tradovate_token']
        refresh_token = account['tradovate_refresh_token']
        token_expires = account['token_expires_at']
    finally:
        return_db_connection(conn)
    
    # Check if we have OAuth tokens
    if not token:
        logger.warning(f"Account {db_account_id} has no OAuth token. User should authenticate through web interface first.")
        return []
    
    try:
        # Determine if demo or live based on token (or default to demo)
        # You can add a column to accounts table to track this if needed
        is_demo = True  # Default to demo, can be made configurable
        
        async with TradovateIntegration(demo=is_demo) as tradovate:
            # Set OAuth tokens
            expires_dt = None
                if token_expires:
                if isinstance(token_expires, str):
                    expires_dt = datetime.fromisoformat(token_expires.replace('Z', '+00:00'))
                    else:
                    expires_dt = token_expires
            
            tradovate.set_oauth_tokens(token, refresh_token, expires_dt)
            
            # Check if token needs refresh
            if not tradovate.is_token_valid() and refresh_token:
                logger.info(f"Token expired for account {db_account_id}, attempting refresh...")
                refresh_result = await tradovate.refresh_access_token(refresh_token)
                
                if refresh_result.get('success'):
                    # Update tokens in database
                    new_token = refresh_result['access_token']
                    new_refresh_token = refresh_result.get('refresh_token', refresh_token)
                    new_expires = datetime.fromisoformat(refresh_result['expires_at'].replace('Z', '+00:00'))
                    
                    conn = get_db_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE accounts
                            SET tradovate_token = ?, tradovate_refresh_token = ?, token_expires_at = ?
                            WHERE id = ?
                        """, (new_token, new_refresh_token, new_expires.isoformat(), db_account_id))
                        conn.commit()
                        logger.info(f"Tokens refreshed and updated in database for account {db_account_id}")
                    finally:
                        return_db_connection(conn)
                    
                    # Update local token
                    tradovate.set_oauth_tokens(new_token, new_refresh_token, new_expires)
                else:
                    logger.error(f"Failed to refresh token for account {db_account_id}: {refresh_result.get('error')}")
                    logger.warning(f"User should re-authenticate through web interface")
                    return []
            
            # Get positions using OAuth token (use Tradovate account spec, not database ID)
                try:
                positions = await tradovate.get_positions(tradovate_account_spec)
                    if positions is not None:
                    logger.info(f"Successfully retrieved {len(positions)} positions for account {tradovate_account_spec} using OAuth token")
                        return positions if positions else []
                else:
                    logger.warning(f"No positions returned for account {tradovate_account_spec}")
                    return []
                except Exception as e:
                logger.error(f"Error getting positions with OAuth token for account {tradovate_account_spec}: {e}")
                # If token is invalid, try refresh one more time
                if refresh_token and ("401" in str(e) or "Unauthorized" in str(e)):
                    logger.info("Token appears invalid, attempting refresh...")
                    refresh_result = await tradovate.refresh_access_token(refresh_token)
                    if refresh_result.get('success'):
                        # Update database and retry
                        new_token = refresh_result['access_token']
                        new_refresh_token = refresh_result.get('refresh_token', refresh_token)
                        new_expires = datetime.fromisoformat(refresh_result['expires_at'].replace('Z', '+00:00'))
                        
                        conn = get_db_connection()
                        try:
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE accounts
                                SET tradovate_token = ?, tradovate_refresh_token = ?, token_expires_at = ?
                                WHERE id = ?
                            """, (new_token, new_refresh_token, new_expires.isoformat(), db_account_id))
                            conn.commit()
                        finally:
                            return_db_connection(conn)
                        
                        tradovate.set_oauth_tokens(new_token, new_refresh_token, new_expires)
                        # Retry getting positions
                        positions = await tradovate.get_positions(tradovate_account_spec)
            return positions if positions else []
                
                return []
            
    except Exception as e:
        logger.error(f"Error getting positions from Tradovate for account {tradovate_account_spec}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return []


def record_position_entry(strategy_id: int, account_id: int, symbol: str, 
                         side: str, quantity: int, position_data: Dict):
    """Record a new position entry"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        entry_price = position_data.get('averagePrice', position_data.get('price', 0))
        entry_timestamp = datetime.now()
        
        # Get strategy TP/SL
        cursor.execute("""
            SELECT take_profit, stop_loss, tpsl_units
            FROM strategies
            WHERE id = ?
        """, (strategy_id,))
        
        strategy = cursor.fetchone()
        take_profit = strategy['take_profit'] if strategy else None
        stop_loss = strategy['stop_loss'] if strategy else None
        tpsl_units = strategy['tpsl_units'] if strategy else 'Ticks'
        
        # Calculate stop loss and take profit prices
        stop_loss_price = None
        take_profit_price = None
        
        if stop_loss and tpsl_units == 'Ticks':
            tick_value = 0.25  # NQ contract assumption
            if side == 'long':
                stop_loss_price = entry_price - (stop_loss * tick_value)
                if take_profit:
                    take_profit_price = entry_price + (take_profit * tick_value)
            else:  # short
                stop_loss_price = entry_price + (stop_loss * tick_value)
                if take_profit:
                    take_profit_price = entry_price - (take_profit * tick_value)
        
        cursor.execute("""
            INSERT INTO recorded_positions (
                strategy_id, account_id, symbol, side, quantity,
                entry_price, entry_timestamp, stop_loss_price, take_profit_price,
                tradovate_position_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_id, account_id, symbol, side, quantity,
            entry_price, entry_timestamp, stop_loss_price, take_profit_price,
            position_data.get('id'), 'open'
        ))
        
        position_record_id = cursor.lastrowid
        
        # Log entry
        cursor.execute("""
            INSERT INTO strategy_logs (strategy_id, log_type, message, data)
            VALUES (?, ?, ?, ?)
        """, (
            strategy_id,
            'position_entry',
            f'Position opened: {side} {quantity} {symbol} @ {entry_price}',
            str(position_data)
        ))
        
        conn.commit()
        logger.info(f"Recorded position entry for strategy {strategy_id}: {side} {quantity} {symbol} @ {entry_price}")
        return position_record_id
    except Exception as e:
        logger.error(f"Error recording position entry: {e}")
        conn.rollback()
        return None
    finally:
        return_db_connection(conn)


def record_position_exit(strategy_id: int, position_id: str, position_data: Dict):
    """Record a position exit"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Find the open position
        cursor.execute("""
            SELECT id, entry_price, quantity, side
            FROM recorded_positions
            WHERE strategy_id = ? AND tradovate_position_id = ? AND status = 'open'
            ORDER BY entry_timestamp DESC
            LIMIT 1
        """, (strategy_id, position_id))
        
        position = cursor.fetchone()
        if not position:
            logger.warning(f"Could not find open position for strategy {strategy_id}, position {position_id}")
            return
        
        record_id = position['id']
        entry_price = position['entry_price']
        quantity = position['quantity']
        side = position['side']
        exit_price = position_data.get('averagePrice', position_data.get('price', entry_price))
        exit_timestamp = datetime.now()
        
        # Calculate PnL
        if side == 'long':
            pnl = (exit_price - entry_price) * quantity
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        else:  # short
            pnl = (entry_price - exit_price) * quantity
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100 if entry_price > 0 else 0
        
        # Update position record
        cursor.execute("""
            UPDATE recorded_positions
            SET exit_price = ?, exit_timestamp = ?, exit_reason = 'closed',
                pnl = ?, pnl_percent = ?, status = 'closed'
            WHERE id = ?
        """, (exit_price, exit_timestamp, pnl, pnl_percent, record_id))
        
        # Log exit
        cursor.execute("""
            INSERT INTO strategy_logs (strategy_id, log_type, message, data)
            VALUES (?, ?, ?, ?)
        """, (
            strategy_id,
            'position_exit',
            f'Position closed: {side} {quantity} @ {exit_price}, PnL: ${pnl:.2f} ({pnl_percent:.2f}%)',
            str(position_data)
        ))
        
        conn.commit()
        logger.info(f"Recorded position exit for strategy {strategy_id}: PnL ${pnl:.2f}")
    except Exception as e:
        logger.error(f"Error recording position exit: {e}")
        conn.rollback()
    finally:
        return_db_connection(conn)


def recording_loop(strategy_id: int, user_id: int, poll_interval: int = 30):
    """Main recording loop for a strategy"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get strategy details
        cursor.execute("""
            SELECT demo_account_id, symbol, account_id
            FROM strategies
            WHERE id = ? AND recording_enabled = 1 AND user_id = ?
        """, (strategy_id, user_id))
        
        strategy = cursor.fetchone()
        if not strategy:
            logger.error(f"Strategy {strategy_id} not found, recording disabled, or user mismatch")
            return
        
        demo_account_id = strategy['demo_account_id']
        symbol = strategy['symbol']
        account_id = strategy['account_id']
        
        if not demo_account_id:
            logger.error(f"Strategy {strategy_id} has no demo account configured")
            return
    finally:
        return_db_connection(conn)
    
    # Track known positions
    known_positions = {}  # position_id -> position data
    
    logger.info(f"Starting recording loop for strategy {strategy_id} (polling every {poll_interval}s)")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while recorder_state['running']:
        # Check if still active (with lock)
        with recorder_state['lock']:
            if strategy_id not in recorder_state['active_recordings']:
                logger.info(f"Recording stopped for strategy {strategy_id}")
                break
        
        try:
            # Get positions from Tradovate (pass both Tradovate account spec and database account_id)
            positions = asyncio.run(get_positions_from_tradovate(demo_account_id, account_id))
            
            # Filter positions for this strategy's symbol
            symbol_positions = [
                p for p in positions 
                if p.get('symbol') == symbol or symbol is None
            ]
            
            # Process each position
            for pos in symbol_positions:
                position_id = str(pos.get('id', ''))
                quantity = pos.get('quantity', 0)
                side = 'long' if quantity > 0 else 'short' if quantity < 0 else 'flat'
                
                # Check if this is a new position
                if position_id not in known_positions:
                    if quantity != 0:  # New open position
                        record_position_entry(
                            strategy_id, account_id, symbol or pos.get('symbol', 'UNKNOWN'),
                            side, abs(quantity), pos
                        )
                        known_positions[position_id] = pos
                else:
                    # Check if position changed or closed
                    old_pos = known_positions[position_id]
                    old_quantity = old_pos.get('quantity', 0)
                    
                    if quantity == 0 and old_quantity != 0:
                        # Position closed
                        record_position_exit(strategy_id, position_id, pos)
                        del known_positions[position_id]
                    elif quantity != old_quantity:
                        # Position size changed
                        known_positions[position_id] = pos
                        logger.debug(f"Position {position_id} size changed: {old_quantity} -> {quantity}")
            
        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Error in recording loop for strategy {strategy_id}: {e} (error {consecutive_errors}/{max_consecutive_errors})")
            
            # Stop recording if too many consecutive errors
            if consecutive_errors >= max_consecutive_errors:
                logger.error(f"Too many consecutive errors for strategy {strategy_id}, stopping recording")
                with recorder_state['lock']:
                    if strategy_id in recorder_state['active_recordings']:
                        del recorder_state['active_recordings'][strategy_id]
                    if user_id in recorder_state['user_recordings']:
                        recorder_state['user_recordings'][user_id].discard(strategy_id)
                break
        else:
            # Reset error counter on success
            consecutive_errors = 0
        
        # Wait before next poll
        time.sleep(poll_interval)
    
    logger.info(f"Recording loop stopped for strategy {strategy_id} (user {user_id})")


# Authentication and Authorization

def verify_api_key():
    """Verify API key from request header"""
    if not API_KEY_ENV:
        logger.warning("No API key configured - allowing all requests (NOT RECOMMENDED FOR PRODUCTION)")
        return True
    
    api_key = request.headers.get(API_KEY_HEADER)
    if not api_key:
        return False
    
    # Simple comparison (in production, use proper key hashing)
    return api_key == API_KEY_ENV


def require_auth(f):
    """Decorator to require API authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not verify_api_key():
            return jsonify({'error': 'Unauthorized - Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_user_id_from_request() -> Optional[int]:
    """Extract user_id from request (from API key or session)"""
    # Option 1: From request JSON
    if request.is_json:
        user_id = request.json.get('user_id')
        if user_id:
            return int(user_id)
    
    # Option 2: From query parameter
    user_id = request.args.get('user_id')
    if user_id:
        return int(user_id)
    
    # Option 3: From header
    user_id = request.headers.get('X-User-ID')
    if user_id:
        return int(user_id)
    
    return None


def verify_user_owns_strategy(user_id: int, strategy_id: int) -> bool:
    """Verify that user owns the strategy"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id FROM strategies WHERE id = ?
        """, (strategy_id))
        result = cursor.fetchone()
        if not result:
            return False
        return result['user_id'] == user_id
    finally:
        return_db_connection(conn)


def check_user_recording_limit(user_id: int) -> tuple[bool, str]:
    """Check if user has reached recording limit"""
    with recorder_state['lock']:
        user_recordings = recorder_state['user_recordings'].get(user_id, set())
        if len(user_recordings) >= MAX_RECORDINGS_PER_USER:
            return False, f"User has reached maximum recording limit ({MAX_RECORDINGS_PER_USER})"
        return True, ""


# API Endpoints

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint (no auth required)"""
    with recorder_state['lock']:
        active_count = len(recorder_state['active_recordings'])
        user_count = len(recorder_state['user_recordings'])
    
    return jsonify({
        'status': 'healthy',
        'active_recordings': active_count,
        'active_users': user_count,
        'tradovate_available': TRADOVATE_AVAILABLE,
        'max_concurrent': MAX_CONCURRENT_RECORDINGS,
        'max_per_user': MAX_RECORDINGS_PER_USER
    })


@app.route('/api/recorders/start/<int:strategy_id>', methods=['POST'])
@require_auth
def start_recording(strategy_id):
    """Start recording positions for a strategy (requires authentication)"""
    # Get user_id from request
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'user_id required in request body, query parameter, or X-User-ID header'
        }), 400
    
    # Check global limit
    with recorder_state['lock']:
        if len(recorder_state['active_recordings']) >= MAX_CONCURRENT_RECORDINGS:
            return jsonify({
                'success': False,
                'error': f'Maximum concurrent recordings reached ({MAX_CONCURRENT_RECORDINGS})'
            }), 503
        
        # Check if already recording
        if strategy_id in recorder_state['active_recordings']:
            return jsonify({
                'success': False,
                'error': f'Recording already active for strategy {strategy_id}'
            }), 400
    
    # Verify user owns strategy
    if not verify_user_owns_strategy(user_id, strategy_id):
        return jsonify({
            'success': False,
            'error': 'Strategy not found or access denied'
        }), 403
    
    # Check user recording limit
    can_record, error_msg = check_user_recording_limit(user_id)
    if not can_record:
        return jsonify({
            'success': False,
            'error': error_msg
        }), 429
    
    # Verify strategy exists and has recording enabled
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, demo_account_id, recording_enabled, user_id
            FROM strategies
            WHERE id = ? AND active = 1
        """, (strategy_id,))
        
        strategy = cursor.fetchone()
        
        if not strategy:
            return jsonify({
                'success': False,
                'error': f'Strategy {strategy_id} not found or inactive'
            }), 404
        
        if not strategy['recording_enabled']:
            return jsonify({
                'success': False,
                'error': f'Recording not enabled for strategy {strategy_id}'
            }), 400
        
        if not strategy['demo_account_id']:
            return jsonify({
                'success': False,
                'error': f'Strategy {strategy_id} has no demo account configured'
            }), 400
        
        # Get poll interval (with minimum limit)
        poll_interval = int(request.json.get('poll_interval', 30)) if request.is_json else 30
        poll_interval = max(poll_interval, POLL_INTERVAL_MIN)
        
        # Start recording thread
        thread = threading.Thread(
            target=recording_loop,
            args=(strategy_id, user_id, poll_interval),
            daemon=True,
            name=f"Recorder-{strategy_id}"
        )
        thread.start()
        
        # Update state with thread safety
        with recorder_state['lock']:
            recorder_state['active_recordings'][strategy_id] = {
                'thread': thread,
                'user_id': user_id,
                'started_at': datetime.now(),
                'poll_interval': poll_interval
            }
            
            # Track user's recordings
            if user_id not in recorder_state['user_recordings']:
                recorder_state['user_recordings'][user_id] = set()
            recorder_state['user_recordings'][user_id].add(strategy_id)
        
        logger.info(f"Started recording for strategy {strategy_id} (user {user_id}, poll interval: {poll_interval}s)")
        
        return jsonify({
            'success': True,
            'message': f'Recording started for strategy {strategy_id}',
            'strategy_id': strategy_id,
            'user_id': user_id,
            'poll_interval': poll_interval
        })
    finally:
        return_db_connection(conn)


@app.route('/api/recorders/stop/<int:strategy_id>', methods=['POST'])
@require_auth
def stop_recording(strategy_id):
    """Stop recording positions for a strategy (requires authentication)"""
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'user_id required'
        }), 400
    
    # Verify user owns strategy
    if not verify_user_owns_strategy(user_id, strategy_id):
        return jsonify({
            'success': False,
            'error': 'Strategy not found or access denied'
        }), 403
    
    with recorder_state['lock']:
        if strategy_id not in recorder_state['active_recordings']:
            return jsonify({
                'success': False,
                'error': f'Recording not active for strategy {strategy_id}'
            }), 400
        
        recording_info = recorder_state['active_recordings'][strategy_id]
        if recording_info['user_id'] != user_id:
            return jsonify({
                'success': False,
                'error': 'Access denied - you do not own this recording'
            }), 403
        
        # Remove from active recordings (thread will stop on next loop check)
        del recorder_state['active_recordings'][strategy_id]
        
        # Remove from user's recordings
        if user_id in recorder_state['user_recordings']:
            recorder_state['user_recordings'][user_id].discard(strategy_id)
            if not recorder_state['user_recordings'][user_id]:
                del recorder_state['user_recordings'][user_id]
    
    logger.info(f"Stopped recording for strategy {strategy_id} (user {user_id})")
    
    return jsonify({
        'success': True,
        'message': f'Recording stopped for strategy {strategy_id}'
    })


@app.route('/api/recorders/status', methods=['GET'])
@require_auth
def get_recording_status():
    """Get status of active recordings (requires authentication)"""
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({
            'error': 'user_id required'
        }), 400
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        active_strategies = []
        with recorder_state['lock']:
            # Only return recordings for this user
            user_recordings = recorder_state['user_recordings'].get(user_id, set())
            
            for strategy_id in user_recordings:
                if strategy_id in recorder_state['active_recordings']:
                    recording_info = recorder_state['active_recordings'][strategy_id]
                    cursor.execute("""
                        SELECT id, name, symbol, demo_account_id
                        FROM strategies
                        WHERE id = ?
                    """, (strategy_id,))
                    
                    strategy = cursor.fetchone()
                    if strategy:
                        active_strategies.append({
                            'strategy_id': strategy['id'],
                            'name': strategy['name'],
                            'symbol': strategy['symbol'],
                            'demo_account_id': strategy['demo_account_id'],
                            'started_at': recording_info['started_at'].isoformat(),
                            'poll_interval': recording_info['poll_interval']
                        })
        
        return jsonify({
            'user_id': user_id,
            'active_recordings': len(active_strategies),
            'strategies': active_strategies
        })
    finally:
        return_db_connection(conn)


@app.route('/api/recorders/positions/<int:strategy_id>', methods=['GET'])
@require_auth
def get_recorded_positions(strategy_id):
    """Get recorded positions for a strategy (requires authentication)"""
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({
            'error': 'user_id required'
        }), 400
    
    # Verify user owns strategy
    if not verify_user_owns_strategy(user_id, strategy_id):
        return jsonify({
            'error': 'Strategy not found or access denied'
        }), 403
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get limit from query params
        limit = int(request.args.get('limit', 100))
        limit = min(limit, 1000)  # Max 1000
        
        cursor.execute("""
            SELECT id, symbol, side, quantity, entry_price, entry_timestamp,
                   exit_price, exit_timestamp, exit_reason, pnl, pnl_percent,
                   stop_loss_price, take_profit_price, status
            FROM recorded_positions
            WHERE strategy_id = ?
            ORDER BY entry_timestamp DESC
            LIMIT ?
        """, (strategy_id, limit))
        
        positions = []
        for row in cursor.fetchall():
            positions.append({
                'id': row['id'],
                'symbol': row['symbol'],
                'side': row['side'],
                'quantity': row['quantity'],
                'entry_price': row['entry_price'],
                'entry_timestamp': row['entry_timestamp'],
                'exit_price': row['exit_price'],
                'exit_timestamp': row['exit_timestamp'],
                'exit_reason': row['exit_reason'],
                'pnl': row['pnl'],
                'pnl_percent': row['pnl_percent'],
                'stop_loss_price': row['stop_loss_price'],
                'take_profit_price': row['take_profit_price'],
                'status': row['status']
            })
        
        return jsonify({
            'strategy_id': strategy_id,
            'user_id': user_id,
            'positions': positions,
            'count': len(positions)
        })
    finally:
        return_db_connection(conn)


def cleanup_on_exit():
    """Cleanup function called on exit"""
    logger.info("Cleaning up recorder backend...")
    recorder_state['running'] = False
    
    # Close all database connections in pool
    while not db_pool.empty():
        try:
            conn = db_pool.get_nowait()
            conn.close()
        except:
            pass


# Register cleanup function
atexit.register(cleanup_on_exit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Recorder Backend Service - Production Ready')
    parser.add_argument('--port', type=int, default=8083, help='Port to run on (default: 8083)')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to (default: 127.0.0.1, use 0.0.0.0 for production)')
    parser.add_argument('--db', type=str, default=DB_PATH, help='Database path')
    parser.add_argument('--init-db', action='store_true', help='Initialize database tables')
    parser.add_argument('--production', action='store_true', help='Run in production mode (use gunicorn)')
    
    args = parser.parse_args()
    
    DB_PATH = args.db
    
    if args.init_db:
        init_database()
    
    # Initialize database connection pool
    init_db_pool()
    
    logger.info("=" * 60)
    logger.info("Recorder Backend Service - Production Ready")
    logger.info("=" * 60)
    logger.info(f"Host: {args.host}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Tradovate available: {TRADOVATE_AVAILABLE}")
    logger.info(f"Max concurrent recordings: {MAX_CONCURRENT_RECORDINGS}")
    logger.info(f"Max recordings per user: {MAX_RECORDINGS_PER_USER}")
    logger.info(f"API Key configured: {'Yes' if API_KEY_ENV else 'No (WARNING: Not secure!)'}")
    
    if args.production:
        logger.info("Production mode: Use gunicorn to run this service")
        logger.info("Example: gunicorn -w 4 -b 0.0.0.0:8083 recorder_backend:app")
        sys.exit(0)
    
    try:
        app.run(host=args.host, port=args.port, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Shutting down Recorder Backend Service...")
        cleanup_on_exit()
        sys.exit(0)

