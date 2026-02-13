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
try:
    from zoneinfo import ZoneInfo
    DEFAULT_USER_TZ = ZoneInfo('America/Chicago')
except ImportError:
    import pytz
    DEFAULT_USER_TZ = pytz.timezone('America/Chicago')
from flask import Flask, request, jsonify, render_template
from async_utils import run_async  # Safe async execution - avoids "Event loop is closed" errors

# ============================================================================
# Configuration
# ============================================================================
import os

# TEST MODE: Signal-based tracking (disable broker sync when enabled)
# Set via environment variable: SIGNAL_BASED_TEST=true
SIGNAL_BASED_TEST_MODE = os.getenv('SIGNAL_BASED_TEST', 'false').lower() == 'true'
if SIGNAL_BASED_TEST_MODE:
    print("🧪 TEST MODE ENABLED: Signal-based tracking (broker sync disabled)")

SERVICE_PORT = 8083
DATABASE_PATH = 'just_trades.db'
LOG_LEVEL = logging.INFO

# ============================================================================
# Token Cache - Prevents re-authentication on every trade (avoids rate limiting)
# ============================================================================
# Structure: {account_id: {'token': str, 'expires': datetime, 'md_token': str}}
_TOKEN_CACHE: Dict[int, Dict] = {}
_TOKEN_CACHE_LOCK = threading.Lock()

# ============================================================================
# 🚀 SCALABILITY CONFIG - HIVE MIND for 500+ accounts
# ============================================================================
# Tradovate rate limits are PER ACCOUNT (80 req/min, 5000 req/hour)
# Each account has its own rate limit - no global throttling needed!
# Signal comes in = ALL accounts execute INSTANTLY in parallel

BATCH_SIZE = 1000  # Process ALL accounts in parallel (no batching)
BATCH_DELAY_SECONDS = 0  # No delay - 100% parallel execution
MAX_CONCURRENT_CONNECTIONS = 500  # Support 500 simultaneous account executions
API_CALLS_PER_MINUTE_LIMIT = 5000  # Effectively disabled - rate limits are per-account

# Rate limit tracking
_API_CALL_TIMES: List[float] = []
_API_CALL_LOCK = threading.Lock()

# ============================================================================
# Paper Trading Redis Publisher (fire-and-forget)
# ============================================================================
_paper_redis = None
try:
    import redis as _redis_module
    _paper_redis_url = os.environ.get('REDIS_URL')
    if _paper_redis_url:
        _paper_redis = _redis_module.from_url(_paper_redis_url, decode_responses=True)
        _paper_redis.ping()
        logging.getLogger('RecorderService').info("Paper trading Redis publisher connected")
except Exception as _redis_err:
    _paper_redis = None
    logging.getLogger('RecorderService').info(f"Paper trading Redis not available (paper signals disabled): {_redis_err}")

def check_rate_limit() -> bool:
    """Check if we're under rate limit. Returns True if safe to proceed."""
    with _API_CALL_LOCK:
        now = time.time()
        # Remove calls older than 60 seconds
        _API_CALL_TIMES[:] = [t for t in _API_CALL_TIMES if now - t < 60]
        return len(_API_CALL_TIMES) < API_CALLS_PER_MINUTE_LIMIT

def record_api_call():
    """Record an API call for rate limiting."""
    with _API_CALL_LOCK:
        _API_CALL_TIMES.append(time.time())

async def wait_for_rate_limit():
    """Wait until rate limit allows more calls."""
    while not check_rate_limit():
        await asyncio.sleep(0.5)
        logger.debug("⏳ Waiting for rate limit...")

def get_cached_token(account_id: int) -> Optional[str]:
    """Get cached token if still valid (with 5 minute buffer)."""
    with _TOKEN_CACHE_LOCK:
        cached = _TOKEN_CACHE.get(account_id)
        if cached:
            # Check if token expires in more than 5 minutes
            expires = cached.get('expires')
            if expires and isinstance(expires, datetime):
                from datetime import timedelta
                if datetime.utcnow() + timedelta(minutes=5) < expires:
                    return cached.get('token')
    return None

def cache_token(account_id: int, token: str, expires: datetime, md_token: str = None):
    """Cache a token for an account."""
    with _TOKEN_CACHE_LOCK:
        _TOKEN_CACHE[account_id] = {
            'token': token,
            'expires': expires,
            'md_token': md_token
        }

def clear_cached_token(account_id: int):
    """Clear cached token for an account."""
    with _TOKEN_CACHE_LOCK:
        _TOKEN_CACHE.pop(account_id, None)

def clear_all_cached_tokens():
    """Clear all cached tokens - useful when re-enabling strategies after being away."""
    with _TOKEN_CACHE_LOCK:
        _TOKEN_CACHE.clear()
        logger.info("🧹 Cleared all cached tokens")

# ============================================================================
# WebSocket Connection Pool - Keep persistent connections (TradeManager's secret)
# ============================================================================
# Structure: {subaccount_id: TradovateIntegration instance with active WebSocket}
_WS_POOL: Dict[int, Any] = {}
_WS_POOL_LOCK = asyncio.Lock()  # ASYNC lock - doesn't block event loop!

async def get_pooled_connection(subaccount_id: int, is_demo: bool, access_token: str):
    """Get or create a pooled WebSocket connection for an account. INSTANT if pooled."""
    from phantom_scraper.tradovate_integration import TradovateIntegration

    # Fast path - check without lock first (read is safe)
    if subaccount_id in _WS_POOL:
        conn = _WS_POOL[subaccount_id]
        if conn and getattr(conn, 'ws_connected', False):
            return conn

    # Need to create/update - use async lock
    async with _WS_POOL_LOCK:
        # Double-check after acquiring lock
        if subaccount_id in _WS_POOL:
            conn = _WS_POOL[subaccount_id]
            if conn and getattr(conn, 'ws_connected', False):
                return conn
            # Connection dead, remove it
            _WS_POOL.pop(subaccount_id, None)

        # Create new connection
        conn = TradovateIntegration(demo=is_demo)
        await conn.__aenter__()
        conn.access_token = access_token

        # Establish WebSocket connection
        ws_connected = await conn._ensure_websocket_connected()
        if ws_connected:
            _WS_POOL[subaccount_id] = conn
            logger.info(f"🔌 WebSocket pool: Added connection for account {subaccount_id}")
            return conn
        else:
            await conn.__aexit__(None, None, None)
            return None

def close_pooled_connection(subaccount_id: int):
    """Close and remove a pooled connection."""
    # Direct dict access is safe for removal
    conn = _WS_POOL.pop(subaccount_id, None)
    if conn:
        try:
            asyncio.create_task(conn.__aexit__(None, None, None))
        except:
            pass

async def prewarm_websocket_connections():
    """
    Pre-warm WebSocket connections for all active trading accounts.
    Called at startup for INSTANT execution on first trade.
    """
    logger.info("🔥 PRE-WARMING WebSocket connections for instant execution...")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()

        # Get all unique subaccounts from enabled traders with valid tokens
        cursor.execute(f'''
            SELECT DISTINCT t.subaccount_id, a.tradovate_token, a.environment
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.enabled = {'TRUE' if is_postgres else '1'}
            AND t.subaccount_id IS NOT NULL
            AND a.tradovate_token IS NOT NULL
        ''')

        accounts = cursor.fetchall()
        conn.close()

        if not accounts:
            logger.info("🔥 No accounts to pre-warm")
            return

        logger.info(f"🔥 Pre-warming {len(accounts)} WebSocket connections...")

        # Warm up connections in parallel (batches of 50 to avoid overwhelming)
        batch_size = 50
        warmed = 0
        failed = 0

        for i in range(0, len(accounts), batch_size):
            batch = accounts[i:i+batch_size]
            tasks = []

            for row in batch:
                subaccount_id = row[0] if isinstance(row, tuple) else row.get('subaccount_id')
                token = row[1] if isinstance(row, tuple) else row.get('tradovate_token')
                env = row[2] if isinstance(row, tuple) else row.get('environment', 'demo')
                is_demo = env != 'live'

                if subaccount_id and token:
                    tasks.append(get_pooled_connection(subaccount_id, is_demo, token))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    failed += 1
                elif r:
                    warmed += 1
                else:
                    failed += 1

        logger.info(f"🔥 WebSocket pre-warm complete: {warmed} connected, {failed} failed")
        logger.info(f"🔥 Pool size: {len(_WS_POOL)} connections ready for INSTANT execution")

    except Exception as e:
        logger.error(f"❌ WebSocket pre-warm failed: {e}")

def start_websocket_prewarm():
    """Start WebSocket pre-warming in background."""
    def run_prewarm():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(prewarm_websocket_connections())
            loop.close()
        except Exception as e:
            logger.error(f"❌ Prewarm thread error: {e}")

    thread = threading.Thread(target=run_prewarm, daemon=True, name="WebSocket-Prewarm")
    thread.start()
    logger.info("🔥 WebSocket pre-warm thread started")

# ============================================================================
# 🛡️ BULLETPROOF TOKEN MANAGEMENT - Auto-refresh before expiry
# ============================================================================
# Tracks accounts that need re-authentication (OAuth expired and refresh failed)
_ACCOUNTS_NEED_REAUTH: Set[int] = set()
_TOKEN_REFRESH_RUNNING = False

def start_token_refresh_daemon():
    """
    Start background daemon that proactively refreshes tokens before they expire.
    This is how TradeManager avoids auth failures during trading.
    """
    global _TOKEN_REFRESH_RUNNING
    if _TOKEN_REFRESH_RUNNING:
        return
    _TOKEN_REFRESH_RUNNING = True
    
    def refresh_loop():
        import requests
        from datetime import timedelta
        
        logger.info("🛡️ Token refresh daemon started - will auto-refresh tokens before expiry")
        
        while _TOKEN_REFRESH_RUNNING:
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get all accounts with tokens
                cursor.execute('''
                    SELECT id, name, tradovate_token, tradovate_refresh_token, 
                           token_expires_at, environment, username, password
                    FROM accounts 
                    WHERE tradovate_token IS NOT NULL AND tradovate_token != ''
                ''')
                accounts = cursor.fetchall()
                
                now = datetime.utcnow()
                
                for acct in accounts:
                    acct_id = acct['id']
                    acct_name = acct['name']
                    refresh_token = acct['tradovate_refresh_token']
                    expires_str = acct['token_expires_at']
                    env = acct['environment'] or 'demo'
                    username = acct['username']
                    password = acct['password']
                    
                    # Parse expiry time
                    expires = None
                    if expires_str:
                        try:
                            # Try multiple formats
                            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z']:
                                try:
                                    expires = datetime.strptime(expires_str.split('+')[0].split('Z')[0], fmt.replace('%z', ''))
                                    break
                                except:
                                    continue
                        except:
                            pass
                    
                    if not expires:
                        continue
                    
                    # Check if token expires within 30 minutes
                    time_until_expiry = expires - now
                    
                    if time_until_expiry < timedelta(minutes=30):
                        logger.info(f"🔄 [{acct_name}] Token expires in {time_until_expiry}, refreshing...")
                        
                        base_url = 'https://demo.tradovateapi.com/v1' if env == 'demo' else 'https://live.tradovateapi.com/v1'
                        refreshed = False
                        
                        # METHOD 1: Try refresh token
                        if refresh_token and not refreshed:
                            try:
                                response = requests.post(
                                    f'{base_url}/auth/renewaccesstoken',
                                    headers={'Authorization': f'Bearer {refresh_token}', 'Content-Type': 'application/json'},
                                    timeout=10
                                )
                                if response.status_code == 200:
                                    data = response.json()
                                    new_token = data.get('accessToken')
                                    new_expiry = data.get('expirationTime')
                                    if new_token:
                                        cursor.execute('''
                                            UPDATE accounts 
                                            SET tradovate_token = ?, token_expires_at = ?
                                            WHERE id = ?
                                        ''', (new_token, new_expiry, acct_id))
                                        conn.commit()
                                        # Update cache
                                        try:
                                            from dateutil.parser import parse as parse_date
                                            cache_token(acct_id, new_token, parse_date(new_expiry))
                                        except:
                                            pass
                                        logger.info(f"✅ [{acct_name}] Token refreshed via refresh_token! Expires: {new_expiry}")
                                        refreshed = True
                                        _ACCOUNTS_NEED_REAUTH.discard(acct_id)
                            except Exception as e:
                                logger.warning(f"⚠️ [{acct_name}] Refresh token failed: {e}")
                        
                        # METHOD 2: Try API Access with username/password
                        if username and password and not refreshed:
                            try:
                                from tradovate_api_access import TradovateAPIAccess
                                import asyncio
                                
                                async def do_api_access():
                                    api = TradovateAPIAccess(demo=(env == 'demo'))
                                    return await api.login(username, password, DATABASE_PATH, acct_id)
                                
                                # Run async in sync context
                                loop = asyncio.new_event_loop()
                                result = loop.run_until_complete(do_api_access())
                                loop.close()
                                
                                if result.get('success'):
                                    new_token = result.get('accessToken')
                                    new_expiry = result.get('expirationTime')
                                    # Token already saved by api.login()
                                    try:
                                        from dateutil.parser import parse as parse_date
                                        cache_token(acct_id, new_token, parse_date(new_expiry))
                                    except:
                                        pass
                                    logger.info(f"✅ [{acct_name}] Token refreshed via API Access!")
                                    refreshed = True
                                    _ACCOUNTS_NEED_REAUTH.discard(acct_id)
                            except Exception as e:
                                logger.warning(f"⚠️ [{acct_name}] API Access failed: {e}")
                        
                        # METHOD 3: Check if account has credentials (trading will still work)
                        if not refreshed:
                            if username and password:
                                # Has credentials - trades will work via API Access during execution
                                logger.warning(f"⚠️ [{acct_name}] Token refresh failed but has credentials - trades will work")
                                _ACCOUNTS_NEED_REAUTH.discard(acct_id)  # Don't mark as needing reauth
                            else:
                                logger.error(f"❌ [{acct_name}] ALL REFRESH METHODS FAILED and no credentials - needs OAuth!")
                                _ACCOUNTS_NEED_REAUTH.add(acct_id)
                    
                    elif acct_id in _ACCOUNTS_NEED_REAUTH and time_until_expiry > timedelta(hours=1):
                        # Token was manually refreshed (OAuth re-done)
                        _ACCOUNTS_NEED_REAUTH.discard(acct_id)
                        logger.info(f"✅ [{acct_name}] Token is valid again - removed from re-auth list")
                
                conn.close()
                
            except Exception as e:
                logger.error(f"❌ Token refresh daemon error: {e}")
            
            # Check every 5 minutes
            time.sleep(300)
    
    thread = threading.Thread(target=refresh_loop, daemon=True, name="TokenRefreshDaemon")
    thread.start()
    logger.info("🛡️ Token refresh daemon thread started")

def get_accounts_needing_reauth() -> List[int]:
    """Get list of account IDs that need manual OAuth re-authentication."""
    return list(_ACCOUNTS_NEED_REAUTH)

def is_account_auth_valid(account_id: int) -> bool:
    """Check if an account's authentication is valid (not in re-auth list)."""
    return account_id not in _ACCOUNTS_NEED_REAUTH

# Auto-start the token refresh daemon when module is imported
# This ensures it runs whether this file is run directly or imported
def _auto_start_daemon():
    """Auto-start daemon on module load."""
    global _TOKEN_REFRESH_RUNNING
    if not _TOKEN_REFRESH_RUNNING:
        try:
            start_token_refresh_daemon()
        except Exception as e:
            print(f"Warning: Could not start token refresh daemon: {e}")

# Delay daemon start slightly to allow imports to complete
threading.Timer(2.0, _auto_start_daemon).start()

# ============================================================================
# DATABASE CONNECTION - Supports both SQLite and PostgreSQL
# ============================================================================
DATABASE_URL = os.getenv('DATABASE_URL')
# CRITICAL FIX: Don't assume PostgreSQL just because DATABASE_URL is set
# We must verify the connection actually works before using %s placeholders
# Previously: is_postgres = bool(DATABASE_URL and ...) caused SQL errors when
# PostgreSQL was configured but not working, sending %s to SQLite
_pg_pool = None
_is_postgres_verified = False  # Only True after successful PostgreSQL connection
is_postgres = False  # Will be set True only after verified connection

# ============================================================================
# Contract Specifications (matching main server exactly)
# ============================================================================

# Contract multipliers for PnL calculation
CONTRACT_MULTIPLIERS = {
    # === INDEX FUTURES (Quarterly: H, M, U, Z) ===
    'MES': 5.0,      # Micro E-mini S&P 500: $5 per point
    'ES': 50.0,      # E-mini S&P 500: $50 per point
    'MNQ': 2.0,      # Micro E-mini Nasdaq: $2 per point
    'NQ': 20.0,      # E-mini Nasdaq: $20 per point
    'MYM': 0.5,      # Micro E-mini Dow: $0.50 per point
    'YM': 5.0,       # E-mini Dow: $5 per point
    'M2K': 5.0,      # Micro E-mini Russell 2000: $5 per point
    'RTY': 50.0,     # E-mini Russell 2000: $50 per point

    # === METALS (Bimonthly: G, J, M, Q, V, Z) ===
    'GC': 100.0,     # Gold: $100 per point
    'MGC': 10.0,     # Micro Gold: $10 per point
    'SI': 5000.0,    # Silver: $5000 per point (5000 oz * $1)
    'SIL': 1000.0,   # Micro Silver: $1000 per point
    'HG': 25000.0,   # Copper: $25000 per point
    'PL': 50.0,      # Platinum: $50 per point

    # === ENERGIES (Monthly: all 12 months) ===
    'CL': 1000.0,    # Crude Oil: $1000 per point
    'MCL': 100.0,    # Micro Crude Oil: $100 per point
    'NG': 10000.0,   # Natural Gas: $10000 per point
    'HO': 42000.0,   # Heating Oil: $42000 per point
    'RB': 42000.0,   # RBOB Gasoline: $42000 per point

    # === TREASURIES (Quarterly: H, M, U, Z) ===
    'ZB': 1000.0,    # 30-Year Bond: $1000 per point
    'ZN': 1000.0,    # 10-Year Note: $1000 per point
    'ZF': 1000.0,    # 5-Year Note: $1000 per point
    'ZT': 2000.0,    # 2-Year Note: $2000 per point

    # === CURRENCIES (Quarterly: H, M, U, Z) ===
    '6E': 125000.0,  # Euro FX: $125000 per point
    '6J': 12500000.0,# Japanese Yen: $12.5M per point (quoted in 0.0000xx)
    '6B': 62500.0,   # British Pound: $62500 per point
    '6A': 100000.0,  # Australian Dollar: $100000 per point
    '6C': 100000.0,  # Canadian Dollar: $100000 per point
    '6S': 125000.0,  # Swiss Franc: $125000 per point
    '6N': 100000.0,  # New Zealand Dollar: $100000 per point
    '6M': 500000.0,  # Mexican Peso: $500000 per point
    'DX': 1000.0,    # US Dollar Index: $1000 per point

    # === CRYPTO (Monthly) ===
    'BTC': 5.0,      # Bitcoin: $5 per point (CME)
    'MBT': 0.1,      # Micro Bitcoin: $0.10 per point
    'ETH': 50.0,     # Ether: $50 per point (CME)
    'MET': 0.1,      # Micro Ether: $0.10 per point

    # === GRAINS (Monthly: F, H, K, N, U, Z for most) ===
    'ZC': 50.0,      # Corn: $50 per point
    'ZS': 50.0,      # Soybeans: $50 per point
    'ZW': 50.0,      # Wheat: $50 per point
    'ZM': 100.0,     # Soybean Meal: $100 per point
    'ZL': 600.0,     # Soybean Oil: $600 per point

    # === SOFTS ===
    'KC': 37500.0,   # Coffee: $37500 per point
    'CT': 50000.0,   # Cotton: $50000 per point
    'SB': 112000.0,  # Sugar: $112000 per point
}

# Tick information: tick_size and tick_value for each contract
TICK_INFO = {
    # === INDEX FUTURES ===
    'MES': {'tick_size': 0.25, 'tick_value': 1.25},
    'ES': {'tick_size': 0.25, 'tick_value': 12.5},
    'MNQ': {'tick_size': 0.25, 'tick_value': 0.5},
    'NQ': {'tick_size': 0.25, 'tick_value': 5.0},
    'MYM': {'tick_size': 1.0, 'tick_value': 0.5},
    'YM': {'tick_size': 1.0, 'tick_value': 5.0},
    'M2K': {'tick_size': 0.1, 'tick_value': 0.5},
    'RTY': {'tick_size': 0.1, 'tick_value': 5.0},

    # === METALS ===
    'GC': {'tick_size': 0.1, 'tick_value': 10.0},
    'MGC': {'tick_size': 0.1, 'tick_value': 1.0},
    'SI': {'tick_size': 0.005, 'tick_value': 25.0},
    'SIL': {'tick_size': 0.005, 'tick_value': 5.0},
    'HG': {'tick_size': 0.0005, 'tick_value': 12.5},
    'PL': {'tick_size': 0.1, 'tick_value': 5.0},

    # === ENERGIES ===
    'CL': {'tick_size': 0.01, 'tick_value': 10.0},
    'MCL': {'tick_size': 0.01, 'tick_value': 1.0},
    'NG': {'tick_size': 0.001, 'tick_value': 10.0},
    'HO': {'tick_size': 0.0001, 'tick_value': 4.2},
    'RB': {'tick_size': 0.0001, 'tick_value': 4.2},

    # === TREASURIES ===
    'ZB': {'tick_size': 0.03125, 'tick_value': 31.25},  # 1/32
    'ZN': {'tick_size': 0.015625, 'tick_value': 15.625}, # 1/64
    'ZF': {'tick_size': 0.0078125, 'tick_value': 7.8125}, # 1/128
    'ZT': {'tick_size': 0.0078125, 'tick_value': 15.625}, # 1/128

    # === CURRENCIES ===
    '6E': {'tick_size': 0.00005, 'tick_value': 6.25},
    '6J': {'tick_size': 0.0000005, 'tick_value': 6.25},
    '6B': {'tick_size': 0.0001, 'tick_value': 6.25},
    '6A': {'tick_size': 0.0001, 'tick_value': 10.0},
    '6C': {'tick_size': 0.00005, 'tick_value': 5.0},
    '6S': {'tick_size': 0.0001, 'tick_value': 12.5},
    '6N': {'tick_size': 0.0001, 'tick_value': 10.0},
    '6M': {'tick_size': 0.00001, 'tick_value': 5.0},
    'DX': {'tick_size': 0.005, 'tick_value': 5.0},

    # === CRYPTO ===
    'BTC': {'tick_size': 5.0, 'tick_value': 25.0},
    'MBT': {'tick_size': 5.0, 'tick_value': 0.5},
    'ETH': {'tick_size': 0.25, 'tick_value': 12.5},
    'MET': {'tick_size': 0.25, 'tick_value': 0.025},

    # === GRAINS ===
    'ZC': {'tick_size': 0.25, 'tick_value': 12.5},
    'ZS': {'tick_size': 0.25, 'tick_value': 12.5},
    'ZW': {'tick_size': 0.25, 'tick_value': 12.5},
    'ZM': {'tick_size': 0.1, 'tick_value': 10.0},
    'ZL': {'tick_size': 0.01, 'tick_value': 6.0},

    # === SOFTS ===
    'KC': {'tick_size': 0.05, 'tick_value': 18.75},
    'CT': {'tick_size': 0.01, 'tick_value': 5.0},
    'SB': {'tick_size': 0.01, 'tick_value': 11.2},
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
# Database Helpers - PostgreSQL + SQLite Support
# ============================================================================

class PostgresCursorWrapper:
    """Wrapper to auto-convert SQLite ? to PostgreSQL %s."""
    def __init__(self, cursor):
        self._cursor = cursor
        self._keys = None
    
    def execute(self, sql, params=None):
        # Convert SQLite ? placeholders to PostgreSQL %s
        # Also convert SQLite boolean 1/0 to PostgreSQL true/false
        sql = sql.replace('?', '%s')
        # Handle both with and without table prefix (t.enabled, enabled)
        sql = sql.replace('t.enabled = 1', 't.enabled = true')
        sql = sql.replace('t.enabled = 0', 't.enabled = false')
        sql = sql.replace('enabled = 1', 'enabled = true')
        sql = sql.replace('enabled = 0', 'enabled = false')
        sql = sql.replace('recording_enabled = 1', 'recording_enabled = true')
        sql = sql.replace('recording_enabled = 0', 'recording_enabled = false')
        sql = sql.replace('r.recording_enabled = 1', 'r.recording_enabled = true')
        sql = sql.replace('r.recording_enabled = 0', 'r.recording_enabled = false')
        if params:
            self._cursor.execute(sql, params)
        else:
            self._cursor.execute(sql)
        if self._cursor.description:
            self._keys = [desc[0] for desc in self._cursor.description]
        return self
    
    def fetchone(self):
        return self._cursor.fetchone()
    
    def fetchall(self):
        return self._cursor.fetchall()
    
    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size) if size else self._cursor.fetchmany()
    
    @property
    def lastrowid(self):
        return None
    
    @property
    def rowcount(self):
        return self._cursor.rowcount
    
    @property
    def description(self):
        return self._cursor.description
    
    def close(self):
        self._cursor.close()


class PostgresConnectionWrapper:
    """Wrapper to make PostgreSQL connection behave like SQLite."""
    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool
        self._closed = False

    def cursor(self):
        # Return wrapped cursor that auto-converts ? to %s
        return PostgresCursorWrapper(self._conn.cursor())

    def execute(self, sql, params=None):
        sql = sql.replace('?', '%s')
        cursor = self._conn.cursor()
        cursor.execute(sql, params or ())
        return PostgresCursorWrapper(cursor)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._conn.rollback()  # Clear any pending transaction
        except:
            pass
        try:
            self._pool.putconn(self._conn)
        except:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        """Safety net: if connection is garbage collected without close(), return to pool cleanly."""
        if not self._closed:
            self.close()

def get_db_connection():
    """Get database connection - PostgreSQL if DATABASE_URL set, else SQLite"""
    global _pg_pool, is_postgres, _is_postgres_verified
    
    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        try:
            import psycopg2
            import psycopg2.pool
            from psycopg2.extras import RealDictCursor
            
            db_url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
            
            if _pg_pool is None:
                # HIVE MIND: Pool sized for 5000+ users with concurrent account executions
                _pg_pool = psycopg2.pool.ThreadedConnectionPool(20, 200, dsn=db_url)
                logger.info("✅ recorder_service: PostgreSQL pool initialized (20-200 connections) - HIVE MIND ready")
            
            conn = _pg_pool.getconn()
            conn.cursor_factory = RealDictCursor

            # Clear any aborted transaction state (no round-trip query needed)
            try:
                conn.rollback()
            except Exception:
                # Connection is truly dead — discard and get fresh one
                try:
                    _pg_pool.putconn(conn, close=True)
                except:
                    pass
                conn = psycopg2.connect(db_url, connect_timeout=5)
                conn.cursor_factory = RealDictCursor

            # CRITICAL: Only set is_postgres=True AFTER successful connection
            # This ensures we use correct placeholder (? vs %s)
            if not _is_postgres_verified:
                is_postgres = True
                _is_postgres_verified = True
                logger.info("✅ recorder_service: PostgreSQL verified, using %s placeholders")

            return PostgresConnectionWrapper(conn, _pg_pool)
        except ImportError:
            logger.warning("⚠️ psycopg2 not installed, using SQLite")
            is_postgres = False  # CRITICAL: Reset so SQL uses ? placeholders
        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL failed: {e}, using SQLite")
            is_postgres = False  # CRITICAL: Reset so SQL uses ? placeholders
    
    # SQLite fallback - ensure is_postgres is False
    is_postgres = False  # ALWAYS set to False when using SQLite
    if not _is_postgres_verified:
        _is_postgres_verified = True
        logger.info("✅ recorder_service: Using SQLite, using ? placeholders")
    
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# SIMPLE TRADE EXECUTION - The Formula (Multi-Account Support)
# ============================================================================

def execute_trade_simple(
    recorder_id: int,
    action: str,  # 'BUY' or 'SELL'
    ticker: str,
    quantity: int,
    tp_ticks: int = 0,  # 0 = no TP (TradingView strategy may handle it)
    sl_ticks: int = 0,  # 0 = no SL (TradingView strategy may handle it)
    risk_config: dict = None  # NEW: Full risk_config for trailing stop/break-even
) -> Dict[str, Any]:
    """
    SIMPLE TRADE EXECUTION WITH TP/SL - Executes on ALL linked accounts.
    
    The Formula:
    1. Place market order for entry (or bracket if TP/SL configured)
    2. Get broker's position (netPrice = average, netPos = quantity)
    3. Calculate TP = average +/- (tp_ticks * tick_size)
    4. Calculate SL = average -/+ (sl_ticks * tick_size) if sl_ticks > 0
    5. Place or modify TP/SL orders
    
    NOTE: sl_ticks=0 means NO stop loss order will be placed.
    This allows TradingView strategies to manage their own exits.
    """
    from phantom_scraper.tradovate_integration import TradovateIntegration
    from tradovate_api_access import TradovateAPIAccess
    import asyncio
    
    result = {
        'success': False,
        'fill_price': None,
        'broker_avg': None,
        'broker_qty': None,
        'tp_price': None,
        'tp_order_id': None,
        'sl_price': None,
        'sl_order_id': None,
        'accounts_traded': 0,
        'error': None
    }
    
    sl_info = f", SL: {sl_ticks} ticks" if sl_ticks > 0 else " (no SL)"
    logger.info(f"🎯 SIMPLE EXECUTE: {action} {quantity} {ticker} (TP: {tp_ticks} ticks{sl_info})")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholder = '%s' if is_postgres else '?'
        
        # Get ALL traders linked to this recorder (multi-user support)
        # CRITICAL: Include a.environment - this is the source of truth for demo vs live
        cursor.execute(f'''
            SELECT t.id, t.enabled_accounts, t.subaccount_id, t.subaccount_name, t.is_demo,
                   a.tradovate_token, a.username, a.password, a.id as account_id, a.environment
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = {placeholder} AND t.enabled = {'true' if is_postgres else '1'}
        ''', (recorder_id,))
        trader_rows = cursor.fetchall()
        
        if not trader_rows:
            conn.close()
            result['error'] = 'No trader linked'
            logger.error(f"❌ No trader linked to recorder {recorder_id}")
            logger.error(f"   Check: 1) Is there a trader record? 2) Is trader.enabled = true? 3) Is recorder_id correct?")
            return result
        
        # Get recorder settings to check avg_down_enabled
        cursor.execute(f'SELECT avg_down_enabled FROM recorders WHERE id = {placeholder}', (recorder_id,))
        recorder_row = cursor.fetchone()
        avg_down_enabled = bool(recorder_row['avg_down_enabled']) if recorder_row else False
        logger.info(f"📊 Recorder {recorder_id}: avg_down_enabled = {avg_down_enabled}")
        
        # Build list of ALL accounts to trade on from ALL traders
        traders = []
        seen_subaccounts = set()  # Prevent duplicates
        skipped_duplicates = []  # Track duplicates for logging

        # Log how many traders are linked to this recorder
        logger.info(f"📋 Found {len(list(trader_rows))} trader(s) linked to recorder {recorder_id}")

        # Reset cursor - OPTIMIZED QUERY: Only fetch traders with VALID accounts
        # This filters at DB level for fastest execution (no wasted loops)
        if is_postgres:
            cursor.execute(f'''
                SELECT * FROM traders
                WHERE recorder_id = {placeholder}
                AND enabled = TRUE
                AND (
                    (enabled_accounts IS NOT NULL AND enabled_accounts != '[]' AND enabled_accounts != 'null' AND LENGTH(enabled_accounts) > 2)
                    OR (subaccount_id IS NOT NULL AND account_id IS NOT NULL)
                )
            ''', (recorder_id,))
        else:
            cursor.execute(f'''
                SELECT * FROM traders
                WHERE recorder_id = {placeholder}
                AND enabled = 1
                AND (
                    (enabled_accounts IS NOT NULL AND enabled_accounts != '[]' AND enabled_accounts != 'null' AND LENGTH(enabled_accounts) > 2)
                    OR (subaccount_id IS NOT NULL AND account_id IS NOT NULL)
                )
            ''', (recorder_id,))
        trader_rows = cursor.fetchall()
        logger.info(f"📋 {len(trader_rows)} trader(s) with valid accounts ready for execution")

        # --- BATCH PRE-FETCH: Avoid repeated identical queries inside the trader loop ---
        # 1) Pre-fetch daily P&L for this recorder (max_daily_loss filter queries this per-trader but it's the same result)
        _cached_daily_pnl = None
        try:
            if is_postgres:
                cursor.execute('''
                    SELECT COALESCE(SUM(pnl), 0) FROM recorded_trades
                    WHERE recorder_id = %s AND exit_time::date = CURRENT_DATE AND status = 'closed'
                ''', (recorder_id,))
            else:
                cursor.execute('''
                    SELECT COALESCE(SUM(pnl), 0) FROM recorded_trades
                    WHERE recorder_id = ? AND DATE(exit_time) = DATE('now') AND status = 'closed'
                ''', (recorder_id,))
            _cached_daily_pnl = cursor.fetchone()[0] or 0
        except Exception:
            pass  # Will fall back to per-trader query

        # 2) Pre-fetch ALL account credentials in one query (avoid N+1 queries per account)
        _cached_account_creds = {}
        try:
            all_acct_ids = set()
            for _tr in trader_rows:
                _trd = dict(_tr)
                _ea_raw = _trd.get('enabled_accounts')
                if _ea_raw and _ea_raw != '[]':
                    try:
                        _ea_list = json.loads(_ea_raw) if isinstance(_ea_raw, str) else _ea_raw
                        for _a in (_ea_list if isinstance(_ea_list, list) else []):
                            _aid = _a.get('account_id')
                            if _aid:
                                all_acct_ids.add(_aid)
                    except:
                        pass
                _legacy_aid = _trd.get('account_id')
                if _legacy_aid:
                    all_acct_ids.add(_legacy_aid)
            if all_acct_ids:
                id_list = ','.join(str(int(x)) for x in all_acct_ids)
                cursor.execute(f'SELECT id, tradovate_token, username, password, broker, api_key, environment, projectx_username, projectx_api_key, projectx_prop_firm, tradovate_refresh_token, token_expires_at FROM accounts WHERE id IN ({id_list})')
                for _row in cursor.fetchall():
                    _cached_account_creds[dict(_row)['id']] = dict(_row)
                logger.info(f"⚡ Pre-fetched {len(_cached_account_creds)} account credentials in 1 query")
        except Exception as _pf_err:
            logger.warning(f"⚠️ Account pre-fetch failed, will query per-account: {_pf_err}")

        # 3) Pre-fetch user timezone for time filter (1 query)
        _cached_user_tz = DEFAULT_USER_TZ
        try:
            cursor.execute(f'SELECT u.settings_json FROM recorders r JOIN users u ON r.user_id = u.id WHERE r.id = {placeholder}', (recorder_id,))
            _tz_row = cursor.fetchone()
            if _tz_row:
                _tz_json = _tz_row['settings_json'] if hasattr(_tz_row, 'keys') else _tz_row[0]
                if _tz_json:
                    _tz_settings = json.loads(_tz_json) if isinstance(_tz_json, str) else _tz_json
                    _tz_name = _tz_settings.get('timezone')
                    if _tz_name:
                        _cached_user_tz = ZoneInfo(_tz_name)
        except Exception:
            pass  # Default to Chicago

        for trader_idx, trader_row in enumerate(trader_rows):
            trader_dict = dict(trader_row)
            trader_id = trader_dict.get('id')
            enabled_accounts_raw = trader_dict.get('enabled_accounts')
            subaccount_id = trader_dict.get('subaccount_id')
            acct_id = trader_dict.get('account_id')
            logger.info(f"📋 Processing Trader #{trader_idx + 1}: ID={trader_id}, Name={trader_dict.get('name', 'unnamed')}")

            # --- CLOSE/EXIT signals BYPASS ALL filters ---
            # A CLOSE must always go through to protect the user's capital.
            # Filters only apply to new entries (BUY/SELL).
            is_close_signal = action.upper() in ('CLOSE', 'FLATTEN', 'EXIT', 'FLAT')
            if is_close_signal:
                logger.info(f"🚨 Trader {trader_id}: CLOSE signal — bypassing all filters")

            # --- TRADER-LEVEL DELAY FILTER (Nth Signal) ---
            trader_add_delay = int(trader_dict.get('add_delay', 1) or 1)
            if not is_close_signal and trader_add_delay > 1:
                # Get and increment signal count for this trader
                trader_signal_count = int(trader_dict.get('signal_count', 0) or 0) + 1
                # Update the signal count in database and commit immediately
                try:
                    cursor.execute(f'UPDATE traders SET signal_count = {placeholder} WHERE id = {placeholder}', (trader_signal_count, trader_id))
                    conn.commit()  # Persist immediately so counter is accurate
                except Exception as cnt_err:
                    logger.warning(f"⚠️ Could not update signal_count for trader {trader_id}: {cnt_err}")

                # Check if we should skip this signal
                if trader_signal_count % trader_add_delay != 0:
                    logger.info(f"⏭️ Trader {trader_id} signal delay SKIPPED: Signal #{trader_signal_count} (executing every {trader_add_delay})")
                    continue
                else:
                    logger.info(f"✅ Trader {trader_id} signal delay PASSED: Signal #{trader_signal_count} (every {trader_add_delay})")

            # --- TRADER-LEVEL SIGNAL COOLDOWN FILTER ---
            trader_cooldown = int(trader_dict.get('signal_cooldown', 0) or 0)
            if not is_close_signal and trader_cooldown > 0:
                last_trade_str = trader_dict.get('last_trade_time')
                if last_trade_str:
                    try:
                        last_trade_dt = datetime.fromisoformat(last_trade_str)
                        elapsed = (datetime.utcnow() - last_trade_dt).total_seconds()
                        if elapsed < trader_cooldown:
                            logger.info(f"⏭️ Trader {trader_id} cooldown SKIPPED: {elapsed:.0f}s / {trader_cooldown}s")
                            continue
                        logger.info(f"✅ Trader {trader_id} cooldown passed: {elapsed:.0f}s / {trader_cooldown}s")
                    except Exception as cool_err:
                        logger.warning(f"⚠️ Trader cooldown parse failed: {cool_err}")
                else:
                    logger.info(f"✅ Trader {trader_id} cooldown passed: no previous trade")

            # --- TRADER-LEVEL MAX SIGNALS PER SESSION FILTER ---
            trader_max_signals = int(trader_dict.get('max_signals_per_session', 0) or 0)
            if not is_close_signal and trader_max_signals > 0:
                today_str = datetime.utcnow().strftime('%Y-%m-%d')
                trader_today_date = trader_dict.get('today_signal_date', '') or ''
                if trader_today_date == today_str:
                    today_count = int(trader_dict.get('today_signal_count', 0) or 0)
                else:
                    today_count = 0  # New day, count resets
                if today_count >= trader_max_signals:
                    logger.info(f"⏭️ Trader {trader_id} max signals SKIPPED: {today_count}/{trader_max_signals} today")
                    continue
                logger.info(f"✅ Trader {trader_id} max signals passed: {today_count}/{trader_max_signals}")

            # --- RECORDER-LEVEL MAX DAILY LOSS FILTER (intentionally shared — strategy circuit breaker) ---
            trader_max_loss = float(trader_dict.get('max_daily_loss', 0) or 0)
            if not is_close_signal and trader_max_loss > 0:
                try:
                    # Use pre-fetched daily P&L if available (avoids repeated identical query)
                    if _cached_daily_pnl is not None:
                        daily_pnl = _cached_daily_pnl
                    elif is_postgres:
                        cursor.execute('''
                            SELECT COALESCE(SUM(pnl), 0) FROM recorded_trades
                            WHERE recorder_id = %s AND exit_time::date = CURRENT_DATE AND status = 'closed'
                        ''', (recorder_id,))
                        daily_pnl = cursor.fetchone()[0] or 0
                    else:
                        cursor.execute('''
                            SELECT COALESCE(SUM(pnl), 0) FROM recorded_trades
                            WHERE recorder_id = ? AND DATE(exit_time) = DATE('now') AND status = 'closed'
                        ''', (recorder_id,))
                        daily_pnl = cursor.fetchone()[0] or 0
                    if daily_pnl <= -trader_max_loss:
                        logger.info(f"⏭️ Trader {trader_id} max daily loss SKIPPED: ${daily_pnl:.2f} (limit: -${trader_max_loss})")
                        continue
                    logger.info(f"✅ Trader {trader_id} max daily loss passed: ${daily_pnl:.2f} / -${trader_max_loss}")
                except Exception as loss_err:
                    logger.warning(f"⚠️ Trader max daily loss check failed: {loss_err}")

            # --- TRADER-LEVEL TIME FILTER ---
            trader_time_1_enabled = trader_dict.get('time_filter_1_enabled', False)
            trader_time_1_start = trader_dict.get('time_filter_1_start', '')
            trader_time_1_stop = trader_dict.get('time_filter_1_stop', '')
            trader_time_2_enabled = trader_dict.get('time_filter_2_enabled', False)
            trader_time_2_start = trader_dict.get('time_filter_2_start', '')
            trader_time_2_stop = trader_dict.get('time_filter_2_stop', '')

            has_trader_time_1 = trader_time_1_enabled and trader_time_1_start and trader_time_1_stop
            has_trader_time_2 = trader_time_2_enabled and trader_time_2_start and trader_time_2_stop

            if not is_close_signal and (has_trader_time_1 or has_trader_time_2):
                from datetime import datetime
                try:
                    now = datetime.now(_cached_user_tz)
                    current_time = now.time()

                    def parse_time_str(t_str):
                        if not t_str:
                            return None
                        t_str = t_str.strip()
                        try:
                            if 'AM' in t_str.upper() or 'PM' in t_str.upper():
                                return datetime.strptime(t_str.upper(), '%I:%M %p').time()
                            return datetime.strptime(t_str, '%H:%M').time()
                        except:
                            return None

                    def in_window(start_str, stop_str):
                        start = parse_time_str(start_str)
                        stop = parse_time_str(stop_str)
                        if not start or not stop:
                            return True
                        if start <= stop:
                            return start <= current_time <= stop
                        else:
                            return current_time >= start or current_time <= stop

                    in_window_1 = in_window(trader_time_1_start, trader_time_1_stop) if has_trader_time_1 else False
                    in_window_2 = in_window(trader_time_2_start, trader_time_2_stop) if has_trader_time_2 else False

                    if not in_window_1 and not in_window_2:
                        logger.info(f"⏭️ Trader {trader_id} time filter SKIPPED: {now.strftime('%I:%M %p')} not in trading window")
                        continue
                    logger.info(f"✅ Trader {trader_id} time filter passed: {now.strftime('%I:%M %p')}")
                except Exception as time_err:
                    logger.warning(f"⚠️ Trader time filter check failed: {time_err}")

            # --- UPDATE PER-TRADER TRACKING (cooldown + daily signal count) ---
            try:
                now_utc = datetime.utcnow().isoformat()
                today_str = datetime.utcnow().strftime('%Y-%m-%d')
                trader_today_date = trader_dict.get('today_signal_date', '') or ''
                if trader_today_date == today_str:
                    new_count = int(trader_dict.get('today_signal_count', 0) or 0) + 1
                else:
                    new_count = 1
                cursor.execute(f'UPDATE traders SET last_trade_time = {placeholder}, today_signal_count = {placeholder}, today_signal_date = {placeholder} WHERE id = {placeholder}',
                               (now_utc, new_count, today_str, trader_id))
                conn.commit()
            except Exception as track_err:
                logger.warning(f"⚠️ Could not update trader tracking: {track_err}")

            # enabled_accounts_raw already extracted at top of loop (early exit check)

            # Check if this trader has enabled_accounts JSON (multi-account feature)
            if enabled_accounts_raw and enabled_accounts_raw != '[]':
                try:
                    enabled_accounts = json.loads(enabled_accounts_raw) if isinstance(enabled_accounts_raw, str) else enabled_accounts_raw
                    
                    if not isinstance(enabled_accounts, list) or len(enabled_accounts) == 0:
                        logger.warning(f"⚠️ Trader {trader_dict.get('id')} has enabled_accounts but it's empty or invalid: {enabled_accounts_raw[:100]}")
                        continue
                    
                    logger.info(f"📋 Processing {len(enabled_accounts)} enabled account(s) for trader {trader_dict.get('id')}")
                    
                    for acct in enabled_accounts:
                        acct_id = acct.get('account_id')
                        subaccount_id = acct.get('subaccount_id')
                        subaccount_name = acct.get('subaccount_name') or acct.get('account_name')
                        # NOTE: Don't use acct.get('is_demo') here - it's stale/cached
                        # We'll get the correct value from accounts.environment below
                        multiplier = float(acct.get('multiplier', 1.0))  # Extract multiplier from account settings
                        
                        # Skip duplicates - CRITICAL: Prevent same account trading twice
                        if subaccount_id in seen_subaccounts:
                            skipped_duplicates.append(f"{subaccount_name} (ID:{subaccount_id})")
                            logger.warning(f"⚠️ DUPLICATE SKIPPED: {subaccount_name} (ID:{subaccount_id}) already added from another trader")
                            continue
                        seen_subaccounts.add(subaccount_id)
                        
                        # Get credentials from accounts table (includes broker type for routing)
                        # CRITICAL: Include environment - source of truth for demo vs live
                        # Include ProjectX-specific fields for TopstepX/Apex routing
                        # Use pre-fetched cache if available (avoids N+1 queries)
                        if acct_id in _cached_account_creds:
                            creds_row = _cached_account_creds[acct_id]
                        else:
                            placeholder = '%s' if is_postgres else '?'
                            cursor.execute(f'SELECT tradovate_token, username, password, broker, api_key, environment, projectx_username, projectx_api_key, projectx_prop_firm FROM accounts WHERE id = {placeholder}', (acct_id,))
                            creds_row = cursor.fetchone()
                        
                        if not creds_row:
                            logger.warning(f"⚠️ Account {acct_id} not found in accounts table - skipping {subaccount_name}")
                            continue
                        
                        if creds_row:
                            creds = dict(creds_row)
                            broker_type = creds.get('broker', 'Tradovate')  # Default to Tradovate for existing accounts
                            
                            # CRITICAL FIX: Detect demo vs live PER-SUBACCOUNT (not account level!)
                            # Priority: 1) acct.environment, 2) acct.is_demo, 3) subaccount name pattern, 4) account.environment
                            is_demo_from_env = True  # Default to demo for safety
                            detected_from = 'default'
                            if acct.get('environment'):
                                is_demo_from_env = acct['environment'].lower() != 'live'
                                detected_from = f"acct.environment={acct.get('environment')}"
                            elif 'is_demo' in acct:
                                is_demo_from_env = bool(acct.get('is_demo'))
                                detected_from = f"acct.is_demo={acct.get('is_demo')}"
                            elif subaccount_name and ('DEMO' in subaccount_name.upper()):
                                is_demo_from_env = True  # Name contains DEMO = demo account
                                detected_from = f"name contains DEMO"
                            elif subaccount_name and subaccount_name.replace('-', '').isdigit():
                                is_demo_from_env = False  # Numeric-only name = likely live account
                                detected_from = f"numeric name = LIVE"
                            else:
                                # Fallback to account-level environment
                                env = (creds.get('environment') or 'demo').lower()
                                is_demo_from_env = env != 'live'
                                detected_from = f"account.environment={env}"
                            
                            env_label = 'DEMO' if is_demo_from_env else 'LIVE'
                            logger.info(f"  🔍 [{subaccount_name}] is_demo={is_demo_from_env} ({detected_from}) → {env_label}")
                            
                            traders.append({
                                'subaccount_id': subaccount_id,
                                'subaccount_name': subaccount_name,
                                'is_demo': is_demo_from_env,
                                'environment': 'demo' if is_demo_from_env else 'live',
                                'tradovate_token': creds.get('tradovate_token'),
                                'username': creds.get('username'),
                                'password': creds.get('password'),
                                'api_key': creds.get('api_key'),
                                'broker': broker_type,  # 'Tradovate' or 'ProjectX'
                                'account_id': acct_id,
                                'multiplier': multiplier,
                                # ProjectX-specific fields for TopstepX/Apex
                                'projectx_username': creds.get('projectx_username'),
                                'projectx_api_key': creds.get('projectx_api_key'),
                                'projectx_prop_firm': creds.get('projectx_prop_firm'),
                                # Risk settings (trailing stop, break-even, TP targets)
                                'sl_type': trader_dict.get('sl_type'),
                                'sl_amount': trader_dict.get('sl_amount'),
                                'sl_enabled': trader_dict.get('sl_enabled'),
                                'trail_trigger': trader_dict.get('trail_trigger'),
                                'trail_freq': trader_dict.get('trail_freq'),
                                'tp_targets': trader_dict.get('tp_targets'),
                                'break_even_enabled': trader_dict.get('break_even_enabled'),
                                'break_even_ticks': trader_dict.get('break_even_ticks'),
                                'break_even_offset': trader_dict.get('break_even_offset'),
                                # Position sizes (trader overrides)
                                'initial_position_size': trader_dict.get('initial_position_size'),
                                'add_position_size': trader_dict.get('add_position_size'),
                                'recorder_id': trader_dict.get('recorder_id'),
                                # DCA and filter settings
                                'dca_enabled': trader_dict.get('dca_enabled'),
                                'avg_down_amount': trader_dict.get('avg_down_amount'),
                                'avg_down_point': trader_dict.get('avg_down_point'),
                                'avg_down_units': trader_dict.get('avg_down_units'),
                                'trim_units': trader_dict.get('trim_units'),
                                'tp_units': trader_dict.get('tp_units'),
                                'max_contracts': trader_dict.get('max_contracts'),
                                'custom_ticker': trader_dict.get('custom_ticker'),
                                'add_delay': trader_dict.get('add_delay'),
                                'signal_cooldown': trader_dict.get('signal_cooldown'),
                                'max_signals_per_session': trader_dict.get('max_signals_per_session'),
                                'max_daily_loss': trader_dict.get('max_daily_loss'),
                                'signal_count': trader_dict.get('signal_count'),
                                # Time filter settings
                                'time_filter_1_enabled': trader_dict.get('time_filter_1_enabled'),
                                'time_filter_1_start': trader_dict.get('time_filter_1_start'),
                                'time_filter_1_stop': trader_dict.get('time_filter_1_stop'),
                                'time_filter_2_enabled': trader_dict.get('time_filter_2_enabled'),
                                'time_filter_2_start': trader_dict.get('time_filter_2_start'),
                                'time_filter_2_stop': trader_dict.get('time_filter_2_stop'),
                            })
                            logger.info(f"  ✅ Added from enabled_accounts: {subaccount_name} (ID: {subaccount_id}, Multiplier: {multiplier}x, Broker: {broker_type}, Env: {env})")
                except Exception as e:
                    logger.error(f"❌ Error parsing enabled_accounts: {e}")
            else:
                # Use the trader's own subaccount (legacy single-account mode)
                # CRITICAL FIX: Must fetch credentials from accounts table!
                subaccount_id = trader_dict.get('subaccount_id')
                acct_id = trader_dict.get('account_id')
                if subaccount_id and subaccount_id not in seen_subaccounts and acct_id:
                    # Fetch credentials from accounts table (same as enabled_accounts mode)
                    # Use pre-fetched cache if available (avoids N+1 queries)
                    if acct_id in _cached_account_creds:
                        creds_row = _cached_account_creds[acct_id]
                    else:
                        placeholder = '%s' if is_postgres else '?'
                        cursor.execute(f'SELECT tradovate_token, username, password, broker, api_key, environment, projectx_username, projectx_api_key, projectx_prop_firm, tradovate_refresh_token, token_expires_at FROM accounts WHERE id = {placeholder}', (acct_id,))
                        creds_row = cursor.fetchone()

                    if creds_row:
                        creds = dict(creds_row)
                        # Merge credentials into trader_dict
                        trader_dict['tradovate_token'] = creds.get('tradovate_token')
                        trader_dict['tradovate_refresh_token'] = creds.get('tradovate_refresh_token')
                        trader_dict['token_expires'] = creds.get('token_expires_at')
                        trader_dict['username'] = creds.get('username')
                        trader_dict['password'] = creds.get('password')
                        trader_dict['api_key'] = creds.get('api_key')
                        trader_dict['broker'] = creds.get('broker', 'Tradovate')
                        trader_dict['projectx_username'] = creds.get('projectx_username')
                        trader_dict['projectx_api_key'] = creds.get('projectx_api_key')
                        trader_dict['projectx_prop_firm'] = creds.get('projectx_prop_firm')

                        # Determine environment (demo vs live)
                        env = (creds.get('environment') or 'demo').lower()
                        trader_dict['environment'] = env
                        trader_dict['is_demo'] = env != 'live'

                        seen_subaccounts.add(subaccount_id)
                        traders.append(trader_dict)
                        has_token = 'YES' if creds.get('tradovate_token') else 'NO'
                        logger.info(f"  ✅ Added trader (legacy): {trader_dict.get('subaccount_name')} (ID: {subaccount_id}, Token: {has_token}, Env: {env})")
                    else:
                        logger.warning(f"  ⚠️ Skipped trader {trader_id}: Account {acct_id} not found in accounts table")
        
        conn.close()
        logger.info(f"📋 Found {len(traders)} account(s) to trade on")

        # Log any duplicates that were skipped
        if skipped_duplicates:
            logger.warning(f"⚠️ DUPLICATE ACCOUNTS SKIPPED ({len(skipped_duplicates)}): {', '.join(skipped_duplicates)}")
            logger.warning(f"⚠️ This usually means the same account is enabled on multiple traders for this recorder")
            logger.warning(f"⚠️ FIX: Remove duplicate account assignments from your traders")
        
        # CRITICAL: If no traders found, return error immediately
        if len(traders) == 0:
            # Get more details for debugging
            conn = get_db_connection()
            cursor = conn.cursor()
            placeholder = '%s' if is_postgres else '?'
            enabled_value = 'true' if is_postgres else '1'
            cursor.execute(f'SELECT COUNT(*) FROM traders WHERE recorder_id = {placeholder} AND enabled = {enabled_value}', (recorder_id,))
            enabled_trader_count = cursor.fetchone()[0] if cursor.rowcount > 0 else 0
            cursor.execute(f'SELECT id, enabled, enabled_accounts FROM traders WHERE recorder_id = {placeholder}', (recorder_id,))
            all_traders = cursor.fetchall()
            conn.close()
            
            logger.error(f"   DEBUG: Enabled traders for recorder {recorder_id}: {enabled_trader_count}")
            for trader_row in all_traders:
                trader_dict = dict(trader_row) if hasattr(trader_row, 'keys') else {'id': trader_row[0], 'enabled': trader_row[1], 'enabled_accounts': trader_row[2]}
                enabled_accts = trader_dict.get('enabled_accounts')
                logger.error(f"   DEBUG: Trader {trader_dict.get('id')}: enabled={trader_dict.get('enabled')}, enabled_accounts={str(enabled_accts)[:100] if enabled_accts else 'None'}")
            result['error'] = 'No accounts to trade on - check enabled_accounts or trader.enabled'
            logger.error(f"❌ No accounts to trade on for recorder {recorder_id}")
            logger.error(f"   Possible causes:")
            logger.error(f"   1. No trader linked to recorder {recorder_id}")
            logger.error(f"   2. Trader.enabled = false")
            logger.error(f"   3. enabled_accounts is empty or invalid")
            logger.error(f"   4. No accounts in enabled_accounts match any subaccounts")
            return result
        
        # Get tick size for this symbol
        symbol_root = ticker[:3].upper() if ticker else 'MNQ'
        tick_size = TICK_SIZES.get(symbol_root, 0.25)
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        
        # Execute on ALL accounts IN PARALLEL
        accounts_traded = 0
        last_result = None
        
        # ============================================================
        # ProjectX Trade Execution (Added Jan 2026)
        # ============================================================
        async def do_trade_projectx(trader, trader_idx, adjusted_quantity):
            """Execute trade on ProjectX broker (TopstepX, Apex, etc.)"""
            from phantom_scraper.projectx_integration import ProjectXIntegration

            acct_name = trader.get('subaccount_name', 'Unknown')
            username = trader.get('username') or trader.get('projectx_username')
            password = trader.get('password')  # FREE auth method (like Trade Manager)
            api_key = trader.get('api_key') or trader.get('projectx_api_key')  # Paid API key method
            prop_firm = trader.get('projectx_prop_firm', 'default')  # TopstepX, Apex, etc.
            # CRITICAL FIX: Use environment as source of truth for demo vs live
            env = (trader.get('environment') or 'demo').lower()
            is_demo = env != 'live'
            subaccount_id = trader.get('subaccount_id')  # This is the ProjectX account ID

            logger.info(f"🚀 [{acct_name}] ProjectX ({prop_firm}) execution: {action} {adjusted_quantity} {ticker}")

            if not username:
                logger.error(f"❌ [{acct_name}] ProjectX username missing")
                return {'success': False, 'error': 'ProjectX username missing'}

            if not password and not api_key:
                logger.error(f"❌ [{acct_name}] ProjectX credentials missing (need password or api_key)")
                return {'success': False, 'error': 'ProjectX credentials missing'}

            try:
                async with ProjectXIntegration(demo=is_demo, prop_firm=prop_firm) as projectx:
                    # Smart authenticate - tries password (FREE) first, then API key
                    if not await projectx.login(username, password=password, api_key=api_key):
                        logger.error(f"❌ [{acct_name}] ProjectX authentication failed")
                        return {'success': False, 'error': 'ProjectX authentication failed'}
                    
                    logger.info(f"✅ [{acct_name}] ProjectX authenticated via {projectx.auth_method or 'unknown'} method")
                    
                    logger.info(f"✅ [{acct_name}] ProjectX authenticated successfully")
                    
                    # Get contracts — use extract_symbol_root() for proper symbol handling
                    symbol_root = extract_symbol_root(ticker) if ticker else 'MNQ'
                    symbol_upper = ticker.strip().upper() if ticker else ''

                    # Try Contract/search first (works on TopStepX), fallback to available
                    contracts = await projectx.search_contracts(symbol_root)
                    if not contracts:
                        contracts = await projectx.get_available_contracts()

                    logger.info(f"📋 [{acct_name}] Looking for symbol_root='{symbol_root}' full='{symbol_upper}' in {len(contracts)} contracts")

                    contract_id = None
                    for contract in contracts:
                        c_name = (contract.get('name') or contract.get('symbol') or '').upper()
                        c_id_str = str(contract.get('id') or '').upper()
                        # Strategy 1: Full symbol match (MNQH6 in CON.F.US.MNQH6.H26)
                        if symbol_upper and (symbol_upper in c_name or symbol_upper in c_id_str):
                            contract_id = contract.get('id')
                            logger.info(f"📋 [{acct_name}] Found contract (full match): {c_name} (ID: {contract_id})")
                            break
                        # Strategy 2: Root symbol match (MNQ in contract)
                        if symbol_root and (symbol_root in c_name or symbol_root in c_id_str):
                            contract_id = contract.get('id')
                            logger.info(f"📋 [{acct_name}] Found contract (root match): {c_name} (ID: {contract_id})")
                            break

                    if not contract_id:
                        contract_names = [f"{c.get('name') or c.get('symbol') or 'N/A'} (id={c.get('id')})" for c in contracts[:20]]
                        logger.error(f"❌ [{acct_name}] Contract not found for {ticker} (root='{symbol_root}'). Available: {contract_names}")
                        return {'success': False, 'error': f'Contract not found for {ticker}'}
                    
                    # Determine order side
                    # ProjectX: 0=Buy, 1=Sell
                    side = "Buy" if action.upper() == "BUY" else "Sell"
                    
                    # Place market order WITH TP/SL brackets (ProjectX native support!)
                    # ProjectX brackets are attached directly to the order - much cleaner than Tradovate
                    order_data = projectx.create_market_order_with_brackets(
                        account_id=int(subaccount_id),
                        contract_id=contract_id,
                        side=side,
                        quantity=adjusted_quantity,
                        tp_ticks=tp_ticks if tp_ticks > 0 else None,
                        sl_ticks=sl_ticks if sl_ticks > 0 else None
                    )
                    
                    sl_info = f", SL: {sl_ticks}t" if sl_ticks > 0 else ""
                    logger.info(f"📤 [{acct_name}] Placing ProjectX bracket order: {side} {adjusted_quantity}, TP: {tp_ticks}t{sl_info}")
                    order_result = await projectx.place_order(order_data)
                    
                    if order_result and order_result.get('success'):
                        order_id = order_result.get('orderId')
                        logger.info(f"✅ [{acct_name}] ProjectX bracket order placed: ID={order_id}")
                        logger.info(f"   TP/SL brackets attached automatically by ProjectX (OCO)")
                        
                        return {
                            'success': True,
                            'order_id': order_id,
                            'broker': 'ProjectX',
                            'account': acct_name,
                            'tp_ticks': tp_ticks,
                            'sl_ticks': sl_ticks
                        }
                    else:
                        error = order_result.get('error', 'Unknown error') if order_result else 'No response'
                        logger.error(f"❌ [{acct_name}] ProjectX order failed: {error}")
                        return {'success': False, 'error': error}
                        
            except Exception as e:
                logger.error(f"❌ [{acct_name}] ProjectX execution error: {e}")
                import traceback
                traceback.print_exc()
                return {'success': False, 'error': str(e)}
        
        # ============================================================
        # Tradovate Trade Execution (Original)
        # ============================================================
        async def do_trade_for_account(trader, trader_idx):
            """Execute trade for a single account - runs in parallel with others"""
            acct_name = trader.get('subaccount_name', 'Unknown')
            acct_id = trader.get('account_id')
            account_multiplier = float(trader.get('multiplier', 1.0))  # Get multiplier for this account
            adjusted_quantity = max(1, int(quantity * account_multiplier))  # Apply multiplier to quantity
            broker_type = trader.get('broker', 'Tradovate')  # Default to Tradovate
            is_dca_local = False  # Track if this is a DCA add (set True when same direction as existing position)

            # ============================================================
            # CUSTOM TICKER OVERRIDE - Trade different instrument than signal
            # If trader has custom_ticker set, use that instead of signal ticker
            # Example: Signal is MNQ but trader wants to trade ES instead
            # ============================================================
            custom_ticker = (trader.get('custom_ticker') or '').strip()
            if custom_ticker:
                logger.info(f"🔄 [{acct_name}] CUSTOM TICKER: {ticker} → {custom_ticker}")
                effective_ticker = custom_ticker
            else:
                effective_ticker = ticker

            # Recalculate symbol info for effective_ticker (may differ from signal ticker)
            local_symbol_root = effective_ticker[:3].upper() if effective_ticker else 'MNQ'
            local_tick_size = TICK_SIZES.get(local_symbol_root, 0.25)
            local_tradovate_symbol = convert_ticker_to_tradovate(effective_ticker)

            # NOTE: Don't check is_account_auth_valid upfront - let auth logic handle it
            # The account might work via cached token, API Access, or OAuth fallback
            # If ALL methods fail, auth logic will return the appropriate error

            logger.info(f"📤 [{trader_idx+1}/{len(traders)}] Trading on: {acct_name} (Broker: {broker_type}, Symbol: {local_tradovate_symbol})")
            
            # ============================================================
            # BROKER ROUTING - ProjectX vs Tradovate (Added Jan 2026)
            # ============================================================
            if broker_type == 'ProjectX':
                return await do_trade_projectx(trader, trader_idx, adjusted_quantity)
            # Default: Continue with Tradovate execution below
            
            tradovate_account_id = trader['subaccount_id']
            tradovate_account_spec = trader['subaccount_name']
            # CRITICAL FIX: Determine demo vs live correctly
            # Priority: 1) trader.is_demo field (most specific), 2) subaccount name pattern, 3) account environment
            # NOTE: Account-level environment can be wrong when account has BOTH demo and live subaccounts
            if 'is_demo' in trader and trader.get('is_demo') is not None:
                is_demo = bool(trader.get('is_demo'))
            elif tradovate_account_spec and tradovate_account_spec.replace('-', '').isdigit():
                # Numeric-only subaccount name = live account
                is_demo = False
            elif tradovate_account_spec and 'DEMO' in tradovate_account_spec.upper():
                # Name contains DEMO = demo account
                is_demo = True
            else:
                # Fallback to account-level environment
                env = trader.get('environment')
                is_demo = (env or 'demo').lower() != 'live'
            logger.info(f"🔍 [{acct_name}] is_demo={is_demo} (trader.is_demo={trader.get('is_demo')}, name={tradovate_account_spec}, env={trader.get('environment')})")
            username = trader.get('username')
            password = trader.get('password')
            
            try:
                # ============================================================
                # 🚀 SCALABLE AUTH - OAuth First (like TradersPost/TradeManager)
                # ============================================================
                # Priority order:
                # 1. Token cache (instant, no API call)
                # 2. OAuth token from DB (no rate limit, no captcha)
                # 3. API Access only as LAST RESORT (triggers captcha/rate limit)
                # ============================================================
                
                account_id = trader['account_id']
                access_token = None
                auth_method = None
                
                # PRIORITY 1: Check token cache (instant, no API call)
                access_token = get_cached_token(account_id)
                if access_token:
                    auth_method = "CACHED"
                    logger.info(f"⚡ [{acct_name}] Using CACHED token (no API call)")
                
                # PRIORITY 2: Use OAuth token from database (like TradersPost)
                # This is the scalable approach - tokens obtained via OAuth never trigger captcha
                # BUT we must check if token is expired first!
                if not access_token:
                    oauth_token = trader.get('tradovate_token')
                    token_expires = trader.get('token_expires')
                    
                    # Check if token is expired
                    token_is_valid = False
                    if oauth_token and token_expires:
                        try:
                            from dateutil.parser import parse as parse_date
                            from datetime import datetime, timedelta
                            expiry = parse_date(token_expires) if isinstance(token_expires, str) else token_expires
                            # Make timezone-naive for comparison
                            if expiry.tzinfo:
                                expiry = expiry.replace(tzinfo=None)
                            # Token is valid if it expires more than 2 minutes from now
                            if expiry > datetime.utcnow() + timedelta(minutes=2):
                                token_is_valid = True
                                cache_token(account_id, oauth_token, expiry)
                            else:
                                logger.warning(f"⚠️ [{acct_name}] OAuth token expired (expires: {expiry})")
                        except Exception as e:
                            # If we can't parse expiry, assume token might be valid
                            logger.warning(f"⚠️ [{acct_name}] Could not check token expiry: {e}")
                            token_is_valid = True  # Try it anyway
                    elif oauth_token:
                        # No expiry info, assume token might be valid
                        token_is_valid = True
                    
                    if oauth_token and token_is_valid:
                        access_token = oauth_token
                        auth_method = "OAUTH"
                        logger.info(f"🔑 [{acct_name}] Using OAuth token (scalable - no rate limit)")
                
                # PRIORITY 3: Try to refresh OAuth token if expired
                if not access_token:
                    oauth_token = trader.get('tradovate_token')
                    refresh_token = trader.get('tradovate_refresh_token')
                    
                    if oauth_token and refresh_token:
                        logger.info(f"🔄 [{acct_name}] Attempting token refresh...")
                        try:
                            # Try to refresh the token
                            tradovate_temp = TradovateIntegration(demo=is_demo)
                            await tradovate_temp.__aenter__()
                            tradovate_temp.access_token = oauth_token
                            tradovate_temp.refresh_token = refresh_token
                            
                            refresh_result = await tradovate_temp.refresh_access_token()
                            if refresh_result.get('success'):
                                access_token = refresh_result.get('access_token')
                                auth_method = "OAUTH_REFRESHED"
                                # Update token in database
                                try:
                                    conn_refresh = get_db_connection()
                                    cursor_refresh = conn_refresh.cursor()
                                    placeholder_refresh = '%s' if is_postgres else '?'
                                    cursor_refresh.execute(f'''
                                        UPDATE accounts 
                                        SET tradovate_token = {placeholder_refresh}, 
                                            token_expires_at = {placeholder_refresh}
                                        WHERE id = {placeholder_refresh}
                                    ''', (access_token, refresh_result.get('expires_at'), account_id))
                                    conn_refresh.commit()
                                    conn_refresh.close()
                                    cache_token(account_id, access_token, refresh_result.get('expires_at'))
                                    logger.info(f"✅ [{acct_name}] Token refreshed successfully")
                                except Exception as update_err:
                                    logger.warning(f"⚠️ [{acct_name}] Could not update token in DB: {update_err}")
                            await tradovate_temp.__aexit__(None, None, None)
                        except Exception as refresh_err:
                            logger.warning(f"⚠️ [{acct_name}] Token refresh failed: {refresh_err}")
                
                # PRIORITY 4: API Access - ONLY if no OAuth token (last resort)
                # This can trigger captcha and rate limiting - avoid for scale!
                if not access_token and username and password:
                    logger.warning(f"⚠️ [{acct_name}] No OAuth token - trying API Access (not scalable)")
                    await wait_for_rate_limit()  # Respect rate limits
                    record_api_call()
                    
                    # Try API Access with retries
                    for api_attempt in range(3):
                        try:
                            api_access = TradovateAPIAccess(demo=is_demo)
                            login_result = await api_access.login(
                                username=username, password=password,
                                db_path=DATABASE_PATH, account_id=account_id
                            )
                            if login_result.get('success'):
                                access_token = login_result['accessToken']
                                auth_method = "API_ACCESS"
                                # Cache the token
                                expiry_str = login_result.get('expirationTime', '')
                                try:
                                    from dateutil.parser import parse as parse_date
                                    expiry = parse_date(expiry_str)
                                    cache_token(account_id, access_token, expiry, login_result.get('mdAccessToken'))
                                except:
                                    pass
                                logger.info(f"✅ [{acct_name}] API Access successful (cached)")
                                break
                            else:
                                error_msg = login_result.get('error', 'Unknown error')
                                if api_attempt < 2:
                                    logger.warning(f"⚠️ [{acct_name}] API Access attempt {api_attempt + 1} failed, retrying...")
                                    await asyncio.sleep(2)
                                else:
                                    logger.error(f"❌ [{acct_name}] API Access failed after 3 attempts: {error_msg}")
                        except Exception as api_err:
                            if api_attempt < 2:
                                logger.warning(f"⚠️ [{acct_name}] API Access exception, retrying: {api_err}")
                                await asyncio.sleep(2)
                            else:
                                logger.error(f"❌ [{acct_name}] API Access exception after 3 attempts: {api_err}")
                
                # CRITICAL: If still no access token, try one more time with fresh DB lookup
                if not access_token:
                    logger.warning(f"⚠️ [{acct_name}] All auth methods failed, trying fresh DB lookup...")
                    try:
                        conn_fresh = get_db_connection()
                        cursor_fresh = conn_fresh.cursor()
                        placeholder_fresh = '%s' if is_postgres else '?'
                        cursor_fresh.execute(f'''
                            SELECT tradovate_token, tradovate_refresh_token, username, password
                            FROM accounts WHERE id = {placeholder_fresh}
                        ''', (account_id,))
                        fresh_row = cursor_fresh.fetchone()
                        conn_fresh.close()
                        
                        if fresh_row:
                            fresh_creds = dict(fresh_row)
                            fresh_token = fresh_creds.get('tradovate_token')
                            if fresh_token:
                                access_token = fresh_token
                                auth_method = "FRESH_DB_LOOKUP"
                                logger.info(f"✅ [{acct_name}] Got token from fresh DB lookup")
                    except Exception as fresh_err:
                        logger.warning(f"⚠️ [{acct_name}] Fresh DB lookup failed: {fresh_err}")
                
                # FINAL FALLBACK: If still no token, return error (will be retried by worker)
                if not access_token:
                    error_msg = 'No OAuth token or credentials available - will retry with token refresh'
                    logger.error(f"❌ [{acct_name}] {error_msg}")
                    return {'success': False, 'error': error_msg, 'retry_recommended': True}
                
                # ============================================================
                # 🚀 SCALABLE CONNECTIONS - Reuse WebSocket connections when possible
                # ============================================================
                # Try to get pooled connection first (faster, less overhead)
                # Fall back to creating new connection if needed
                # ============================================================
                
                tradovate = None
                pooled_conn = None
                try:
                    # Try to get pooled WebSocket connection
                    pooled_conn = await get_pooled_connection(tradovate_account_id, is_demo, access_token)
                    if pooled_conn:
                        tradovate = pooled_conn
                        logger.debug(f"⚡ [{acct_name}] Using POOLED WebSocket connection")
                    else:
                        # Create new connection (will be closed after trade)
                        tradovate = TradovateIntegration(demo=is_demo)
                        await tradovate.__aenter__()
                        tradovate.access_token = access_token
                        logger.debug(f"🔌 [{acct_name}] Created new connection")
                except Exception as pool_err:
                    logger.warning(f"⚠️ [{acct_name}] Pool error, creating new connection: {pool_err}")
                    tradovate = TradovateIntegration(demo=is_demo)
                    await tradovate.__aenter__()
                    tradovate.access_token = access_token
                
                try:
                    # STEP 0: Check if this is a new entry or DCA (adding to position)
                    order_action = 'Buy' if action == 'BUY' else 'Sell'
                    record_api_call()  # Track API calls for rate limiting
                    
                    # Log multiplier application
                    if account_multiplier != 1.0:
                        logger.info(f"📊 [{acct_name}] Applying multiplier: {quantity} × {account_multiplier} = {adjusted_quantity} contracts")
                    
                    # Check existing position first
                    existing_positions = await tradovate.get_positions(account_id=tradovate_account_id)
                    has_existing_position = False
                    existing_position_side = None
                    existing_position_qty = 0
                    for pos in existing_positions:
                        pos_symbol = str(pos.get('symbol', '')).upper()
                        net_pos = pos.get('netPos', 0)
                        if local_symbol_root in pos_symbol and net_pos != 0:
                            has_existing_position = True
                            existing_position_side = 'LONG' if net_pos > 0 else 'SHORT'
                            existing_position_qty = abs(net_pos)
                            break
                    
                    # CRITICAL POSITION CHECKS - UNIVERSAL DCA LOGIC (Jan 27, 2026)
                    # Same direction = ALWAYS add to position (DCA)
                    # Opposite direction = CLOSE position (for strategy exits) OR BLOCK (if avg_down_enabled)
                    if has_existing_position:
                        signal_side = 'LONG' if action == 'BUY' else 'SHORT'

                        if signal_side == existing_position_side:
                            # SAME DIRECTION - Check if trader has DCA enabled
                            # If trader.dca_enabled is None (not explicitly set), inherit from recorder.avg_down_enabled
                            raw_dca = trader.get('dca_enabled')
                            trader_dca_enabled = bool(raw_dca) if raw_dca is not None else avg_down_enabled
                            if trader_dca_enabled:
                                # DCA MODE ON: Cancel+replace TP, get new avg from broker
                                logger.info(f"📈 [{acct_name}] DCA ADD - Adding to {existing_position_side} {existing_position_qty} (dca_enabled=ON)")
                                is_dca_local = True  # PROTECTED: Triggers cancel+replace TP logic
                            else:
                                # DCA MODE OFF: Add to position but use standard TP handling
                                logger.info(f"📈 [{acct_name}] Same direction - Adding to {existing_position_side} {existing_position_qty} (dca_enabled=OFF, standard TP)")
                            # Continue to execute - will add to position
                        else:
                            # OPPOSITE DIRECTION - Check if DCA mode blocks opposite signals
                            # Block if EITHER trader.dca_enabled OR recorder.avg_down_enabled is True
                            trader_dca_enabled = bool(trader.get('dca_enabled', False))
                            should_block_opposite = trader_dca_enabled or avg_down_enabled

                            if should_block_opposite:
                                # Block opposite signals - system TP or manual exit expected
                                mode_name = "dca_enabled" if trader_dca_enabled else "avg_down_enabled"
                                logger.warning(f"⚠️ [{acct_name}] OPPOSITE BLOCKED - In {existing_position_side} {existing_position_qty}, {mode_name}=True expects system/manual exit")
                                return {
                                    'success': False,
                                    'error': f'Opposite signal blocked - use TP/SL or manual exit ({mode_name}=True)',
                                    'acct_name': acct_name,
                                    'skipped': True
                                }
                            else:
                                # CLOSE position - strategy is sending exit signal
                                # Use existing position qty to prevent flip
                                # Example: LONG 2, SELL signal with 10x multiplier would place SELL 10
                                #          That closes 2 LONG and opens 8 SHORT - BAD!
                                # Fix: Use existing_position_qty (2) so it only closes, doesn't flip
                                logger.info(f"🔄 [{acct_name}] CLOSE SIGNAL - Opposite {signal_side} signal closes {existing_position_side} {existing_position_qty}")
                                logger.info(f"   Adjusting quantity from {adjusted_quantity} to {existing_position_qty} (close exact position size)")
                                adjusted_quantity = existing_position_qty
                    
                    # SCALABLE APPROACH: Use bracket order via WebSocket for NEW entries
                    # This sends entry + TP + SL in ONE call (no rate limits, guaranteed orders)
                    # NOW SUPPORTS: Native break-even and autoTrail (trailing-after-profit) via Tradovate API
                    use_bracket_order = (
                        not has_existing_position and 
                        tp_ticks and tp_ticks > 0
                    )
                    
                    if use_bracket_order:
                        # Extract native break-even and autoTrail settings from risk_config
                        break_even_ticks = None
                        break_even_offset = None
                        auto_trail = None
                        trailing_stop_bool = False
                        
                        if risk_config:
                            # Break-even: { activation_ticks: X, offset_ticks: Y }
                            # offset_ticks = how many ticks of profit to lock in (0 = true breakeven at entry)
                            break_even_cfg = risk_config.get('break_even')
                            if break_even_cfg and break_even_cfg.get('activation_ticks'):
                                break_even_ticks = break_even_cfg.get('activation_ticks')
                                break_even_offset = break_even_cfg.get('offset_ticks', 0)  # Default to true breakeven
                                if break_even_offset > 0:
                                    logger.info(f"📊 [{acct_name}] Native break-even: activation={break_even_ticks} ticks, offset={break_even_offset} ticks")
                                else:
                                    logger.info(f"📊 [{acct_name}] Native break-even: {break_even_ticks} ticks (true BE)")

                            # Trailing: { offset_ticks: X, activation_ticks: Y, frequency_ticks: Z }
                            trail_cfg = risk_config.get('trail')
                            if trail_cfg:
                                offset_ticks = trail_cfg.get('offset_ticks')
                                activation_ticks = trail_cfg.get('activation_ticks')
                                frequency_ticks = trail_cfg.get('frequency_ticks')  # How often to update trail

                                # If activation_ticks exists and is different from offset_ticks, it's trail-after-profit
                                # If they're the same (or only offset_ticks exists), it's immediate trailing
                                if offset_ticks and activation_ticks and activation_ticks != offset_ticks:
                                    # Trail-after-profit: Use autoTrail (starts trailing after profit threshold)
                                    # freq = how often to update (in price units, not ticks)
                                    trail_freq = (frequency_ticks * local_tick_size) if frequency_ticks else (local_tick_size * 0.25)
                                    auto_trail = {
                                        'stopLoss': offset_ticks,  # Trailing distance
                                        'trigger': activation_ticks,  # Profit threshold to start trailing
                                        'freq': trail_freq  # Update frequency
                                    }
                                    freq_log = f", freq={frequency_ticks} ticks" if frequency_ticks else ""
                                    logger.info(f"📊 [{acct_name}] Native autoTrail: distance={offset_ticks} ticks, trigger={activation_ticks} ticks{freq_log}")
                                elif offset_ticks:
                                    # Immediate trailing: Use trailingStop boolean (starts trailing immediately)
                                    trailing_stop_bool = True
                                    logger.info(f"📊 [{acct_name}] Immediate trailing stop: {offset_ticks} ticks")
                        
                        sl_log = f" + SL: {sl_ticks} ticks" if sl_ticks > 0 else ""
                        be_log = f" + BE: {break_even_ticks} ticks" if break_even_ticks else ""
                        trail_log = f" + Trail" if auto_trail or trailing_stop_bool else ""
                        logger.info(f"📤 [{acct_name}] Using NATIVE BRACKET ORDER (WebSocket) - Entry + TP{sl_log}{be_log}{trail_log} in one call")
                        
                        bracket_result = await tradovate.place_bracket_order(
                            account_id=tradovate_account_id,
                            account_spec=tradovate_account_spec,
                            symbol=local_tradovate_symbol,
                            entry_side=order_action,
                            quantity=adjusted_quantity,
                            profit_target_ticks=tp_ticks,
                            stop_loss_ticks=sl_ticks if sl_ticks > 0 else None,  # Only place SL if configured
                            trailing_stop=trailing_stop_bool,  # Immediate trailing (boolean)
                            break_even_ticks=break_even_ticks,  # Native break-even
                            break_even_offset=break_even_offset,  # Offset beyond entry for breakevenPlus
                            auto_trail=auto_trail  # Native trailing-after-profit
                        )
                        
                        if bracket_result and bracket_result.get('success'):
                            strategy_id = bracket_result.get('orderStrategyId') or bracket_result.get('id')
                            logger.info(f"✅ [{acct_name}] BRACKET ORDER SUCCESS! Strategy ID: {strategy_id}")
                            
                            # OPTIMIZATION: Skip position verification - bracket order handles everything
                            # The TP is already placed as part of the bracket, no need to verify
                            # This saves 1 API call per trade!
                            broker_side = 'LONG' if order_action == 'Buy' else 'SHORT'
                            broker_qty = adjusted_quantity
                            
                            # Calculate expected TP/SL prices (without fetching position)
                            # Note: Actual TP will be at market fill price, but this is close enough for logging
                            if broker_side == 'LONG':
                                tp_price = None  # Will be set by bracket order automatically
                                sl_price = None
                            else:
                                tp_price = None
                                sl_price = None
                            
                            logger.info(f"📊 [{acct_name}] BRACKET: {broker_side} {broker_qty} with TP @ +{tp_ticks} ticks (1 API call!)")
                            
                            return {
                                'success': True,
                                'broker_avg': None,  # Not fetched - saves API call
                                'broker_qty': broker_qty,
                                'broker_side': broker_side,
                                'tp_price': tp_price,
                                'tp_order_id': strategy_id,
                                'sl_price': sl_price,
                                'sl_order_id': strategy_id if sl_ticks > 0 else None,
                                'acct_name': acct_name,
                                'method': 'BRACKET_WS',  # 1 API call for entry + TP!
                                'subaccount_id': tradovate_account_id  # For break-even monitoring
                            }
                        else:
                            # Bracket order failed - fall back to REST
                            logger.warning(f"⚠️ [{acct_name}] Bracket order failed, falling back to REST: {bracket_result}")
                    
                    # FALLBACK: REST API for DCA or if bracket fails
                    # STEP 1: Place market order via REST
                    order_data = tradovate.create_market_order(
                        tradovate_account_spec, local_tradovate_symbol,
                        order_action, adjusted_quantity, tradovate_account_id
                    )

                    logger.info(f"📤 [{acct_name}] Placing {order_action} {adjusted_quantity} {local_tradovate_symbol}...")
                    order_result = await tradovate.place_order_smart(order_data)
                    
                    if not order_result or not order_result.get('success'):
                        error = order_result.get('error', 'Order failed') if order_result else 'No response'
                        return {'success': False, 'error': error}
                    
                    order_id = order_result.get('orderId') or order_result.get('id')
                    logger.info(f"✅ [{acct_name}] Market order placed: {order_id}")
                    
                    # STEP 1.5: If risk_config has trail or break_even, use apply_risk_orders
                    # This handles trailing stops and break-even which bracket orders don't support
                    if risk_config and (risk_config.get('trail') or risk_config.get('break_even')):
                        logger.info(f"📊 [{acct_name}] Using apply_risk_orders for advanced risk management (trailing stop/break-even)")
                        try:
                            # Import apply_risk_orders from ultra_simple_server
                            import sys
                            import os
                            # Get the directory of ultra_simple_server.py
                            current_dir = os.path.dirname(os.path.abspath(__file__))
                            parent_dir = os.path.dirname(current_dir)
                            if parent_dir not in sys.path:
                                sys.path.insert(0, parent_dir)
                            
                            # We need to call apply_risk_orders after getting position fill
                            # Store it for later use
                            use_apply_risk_orders = True
                            logger.info(f"📊 [{acct_name}] Will use apply_risk_orders after position fill")
                        except Exception as import_err:
                            logger.warning(f"⚠️ [{acct_name}] Could not import apply_risk_orders: {import_err}")
                            use_apply_risk_orders = False
                    else:
                        use_apply_risk_orders = False
                    
                    # STEP 2: Get position info - OPTIMIZED (1 call max, use order result first)
                    # OPTIMIZATION: Check if order result has fill info (saves API call!)
                    broker_avg = order_result.get('avgFillPrice') or order_result.get('price')
                    broker_qty = adjusted_quantity
                    broker_side = 'LONG' if order_action == 'Buy' else 'SHORT'
                    contract_id = None
                    
                    # If order result has fill price AND not DCA, use it directly (no API call needed!)
                    # For DCA: ALWAYS fetch broker position to get NEW weighted average price
                    if broker_avg and not is_dca_local:
                        logger.info(f"📊 [{acct_name}] Using fill price from order result: {broker_side} {broker_qty} @ {broker_avg} (0 extra API calls!)")
                    else:
                        # Fetch position from broker - needed for DCA (weighted avg) or when no fill price
                        if is_dca_local:
                            logger.info(f"📊 [{acct_name}] DCA: Fetching broker position for new weighted average price...")
                            broker_avg = None  # Force position fetch to get new average

                        # RETRY LOGIC: Try up to 3 times with delays to get fill price
                        # This is critical for TP/SL placement - without a valid price, orders will fail
                        max_position_retries = 3
                        retry_delays = [0.5, 1.0, 1.5]  # Progressive delays

                        for retry_num in range(max_position_retries):
                            await asyncio.sleep(retry_delays[retry_num])  # Give order time to fill
                            positions = await tradovate.get_positions(account_id=tradovate_account_id)

                            for pos in positions:
                                pos_symbol = str(pos.get('symbol', '')).upper()
                                if local_symbol_root in pos_symbol:
                                    net_pos = pos.get('netPos', 0)
                                    if net_pos != 0:
                                        broker_avg = pos.get('netPrice')
                                        broker_qty = abs(net_pos)
                                        broker_side = 'LONG' if net_pos > 0 else 'SHORT'
                                        contract_id = pos.get('contractId')
                                        logger.info(f"📊 [{acct_name}] POSITION: {broker_side} {broker_qty} @ {broker_avg} (attempt {retry_num + 1})")
                                        break

                            if broker_avg and broker_avg > 0:
                                break  # Got valid fill price, stop retrying
                            elif retry_num < max_position_retries - 1:
                                logger.warning(f"⚠️ [{acct_name}] Position not visible yet (attempt {retry_num + 1}/{max_position_retries}) - retrying...")

                        if not broker_avg or broker_avg <= 0:
                            # Fallback: Use order result or existing position info
                            logger.warning(f"⚠️ [{acct_name}] Position not visible after {max_position_retries} attempts - using fallback")
                            # For DCA, we already know the existing position from earlier check
                            if has_existing_position and existing_position_qty > 0:
                                # Estimate new average after DCA
                                broker_qty = existing_position_qty + adjusted_quantity
                                broker_side = existing_position_side
                                # Use a placeholder - TP will still be calculated
                                broker_avg = order_result.get('avgFillPrice', 0) or 0
                            else:
                                broker_avg = 0  # Will trigger TP/SL placement to skip

                            if broker_avg <= 0:
                                logger.error(f"❌ [{acct_name}] CRITICAL: Could not get fill price after {max_position_retries} attempts!")
                                logger.error(f"   TP/SL orders will NOT be placed - position is UNPROTECTED")
                    
                    # STEP 2.5: Use apply_risk_orders if risk_config has trail or break_even
                    if use_apply_risk_orders and risk_config and broker_avg:
                        logger.info(f"📊 [{acct_name}] Calling apply_risk_orders for advanced risk management")
                        try:
                            # Import apply_risk_orders - it's in ultra_simple_server.py
                            # We need to import it dynamically since it's in a different file
                            from ultra_simple_server import apply_risk_orders
                            
                            # Call apply_risk_orders (it will handle TP, SL, trailing stop, break-even)
                            await apply_risk_orders(
                                tradovate=tradovate,
                                account_spec=tradovate_account_spec,
                                account_id=tradovate_account_id,
                                symbol=local_tradovate_symbol,
                                entry_side=order_action,
                                quantity=adjusted_quantity,
                                risk_config=risk_config
                            )
                            logger.info(f"✅ [{acct_name}] apply_risk_orders completed (trailing stop/break-even configured)")
                            
                            # Skip manual TP/SL placement since apply_risk_orders handled it
                            return {
                                'success': True,
                                'broker_avg': broker_avg,
                                'broker_qty': broker_qty,
                                'broker_side': broker_side,
                                'tp_price': None,  # Will be set by apply_risk_orders
                                'tp_order_id': None,
                                'sl_price': None,  # Will be set by apply_risk_orders
                                'sl_order_id': None,
                                'acct_name': acct_name,
                                'method': 'REST_WITH_RISK_ORDERS',
                                'subaccount_id': tradovate_account_id,  # For break-even monitoring
                                'account_spec': tradovate_account_spec  # For break-even monitoring
                            }
                        except ImportError as import_err:
                            logger.warning(f"⚠️ [{acct_name}] Could not import apply_risk_orders: {import_err}")
                            logger.warning(f"   Falling back to manual TP/SL placement")
                            use_apply_risk_orders = False  # Fall back to manual
                        except Exception as apply_err:
                            logger.error(f"❌ [{acct_name}] apply_risk_orders failed: {apply_err}")
                            logger.warning(f"   Falling back to manual TP/SL placement")
                            use_apply_risk_orders = False  # Fall back to manual
                    
                    # STEP 3: Calculate and place TP (only if tp_ticks > 0 AND we have a valid fill price)
                    tp_price = None
                    tp_action = None
                    tp_order_id = None

                    if tp_ticks and tp_ticks > 0:
                        # CRITICAL: Only calculate TP if we have a valid fill price
                        if not broker_avg or broker_avg <= 0:
                            logger.error(f"❌ [{acct_name}] CANNOT PLACE TP: No valid fill price (broker_avg={broker_avg})")
                            logger.error(f"   Position is UNPROTECTED - manually set TP in broker!")
                        else:
                            if broker_side == 'LONG':
                                tp_price_raw = broker_avg + (tp_ticks * local_tick_size)
                                tp_action = 'Sell'
                            else:
                                tp_price_raw = broker_avg - (tp_ticks * local_tick_size)
                                tp_action = 'Buy'
                            # CRITICAL: Round to nearest valid tick increment
                            # DCA averages produce fractional prices (e.g. 25074.805) that Tradovate rejects
                            tp_price = round(round(tp_price_raw / local_tick_size) * local_tick_size, 10)

                            # Validate the calculated TP price is reasonable
                            if tp_price <= 0:
                                logger.error(f"❌ [{acct_name}] INVALID TP PRICE: {tp_price} - skipping TP placement")
                                tp_price = None
                            else:
                                logger.info(f"🎯 [{acct_name}] TP: {broker_avg} {'+' if broker_side=='LONG' else '-'} ({tp_ticks}×{local_tick_size}) = {tp_price} (rounded from {tp_price_raw})")
                    else:
                        logger.info(f"🎯 [{acct_name}] TP DISABLED (tp_ticks=0) - letting strategy handle exit")
                    
                    # STEP 4: Find existing TP or place new - OPTIMIZED for minimum API calls
                    # Skip if TP is disabled (tp_ticks = 0)
                    existing_tp_id = None

                    if tp_price is None:
                        # TP disabled - skip all TP placement logic
                        pass
                    elif not has_existing_position:
                        # OPTIMIZATION: For NEW entries (no existing position), skip order lookup - just place TP
                        logger.info(f"📊 [{acct_name}] NEW ENTRY - placing TP directly (0 extra API calls)")
                    else:
                        # MULTI-ACCOUNT FIX: Skip DB tp_order_id lookup — recorded_trades has no
                        # subaccount_id column, so the stored tp_order_id could belong to ANY account
                        # trading this recorder. Instead, always use broker query (per-account correct).
                        if is_dca_local:
                            logger.info(f"📊 [{acct_name}] DCA: Skipping DB TP lookup (multi-account unsafe) - will cancel via broker query")
                        else:
                            # Non-DCA: DB lookup is still useful as a hint for single-account recorders
                            try:
                                tp_lookup_conn = get_db_connection()
                                tp_lookup_cursor = tp_lookup_conn.cursor()
                                tp_ph = '%s' if is_postgres else '?'
                                tp_lookup_cursor.execute(f'''
                                    SELECT tp_order_id FROM recorded_trades
                                    WHERE recorder_id = {tp_ph} AND ticker LIKE {tp_ph} AND status = 'open' AND tp_order_id IS NOT NULL
                                    ORDER BY entry_time DESC LIMIT 1
                                ''', (recorder_id, f'%{local_symbol_root}%'))
                                tp_row = tp_lookup_cursor.fetchone()
                                if tp_row and tp_row['tp_order_id']:
                                    existing_tp_id = int(tp_row['tp_order_id'])
                                    logger.info(f"🔍 [{acct_name}] Found stored TP order {existing_tp_id} in DB (hint only)")
                                tp_lookup_conn.close()
                            except Exception as e:
                                logger.debug(f"[{acct_name}] Could not check DB for TP: {e}")

                        # DCA: ALWAYS cancel and replace (modify is unreliable per Tradovate forum)
                        # Non-DCA: Try modify first
                        if existing_tp_id:
                            if is_dca_local:
                                # DCA: Cancel existing TP and place fresh with new qty/price
                                logger.info(f"🗑️ [{acct_name}] DCA: Cancelling old TP {existing_tp_id} to place fresh (per Tradovate best practice)")
                                try:
                                    await tradovate.cancel_order_smart(existing_tp_id)
                                    logger.info(f"✅ [{acct_name}] Old TP cancelled - will place fresh @ {tp_price} qty={broker_qty}")
                                except Exception as cancel_err:
                                    logger.warning(f"⚠️ [{acct_name}] Could not cancel old TP: {cancel_err} - placing fresh anyway")
                                existing_tp_id = None  # Fall through to place new
                            else:
                                # Non-DCA: Try modify
                                logger.info(f"🔄 [{acct_name}] MODIFYING TP {existing_tp_id} (1 API call)")
                                modify_result = await tradovate.modify_order_smart(
                                    order_id=existing_tp_id,
                                    order_data={
                                        "price": tp_price,
                                        "orderQty": broker_qty,
                                        "orderType": "Limit",
                                        "timeInForce": "GTC"
                                    }
                                )
                                if modify_result and modify_result.get('success'):
                                    tp_order_id = existing_tp_id
                                    logger.info(f"✅ [{acct_name}] TP MODIFIED @ {tp_price}")
                                else:
                                    error_msg = modify_result.get('error', 'Unknown error') if modify_result else 'No response'
                                    logger.warning(f"⚠️ [{acct_name}] TP MODIFY FAILED: {error_msg} - will place new")
                                    existing_tp_id = None  # Fall through to place new
                    
                    # Place new TP if needed (only if TP is enabled)
                    if tp_price is not None and not tp_order_id:
                        # CRITICAL: Cancel ALL existing TP orders on broker before placing new!
                        # This prevents duplicates (especially after bracket orders where strategy ID != order ID)
                        logger.info(f"🗑️ [{acct_name}] Checking for existing TPs on broker before placing new...")
                        try:
                            all_orders = await tradovate.get_orders(account_id=str(tradovate_account_id))
                            for order in (all_orders or []):
                                order_status = str(order.get('ordStatus', '')).upper()
                                order_action_check = order.get('action', '')
                                order_id_check = order.get('id')
                                
                                # Cancel any working TP orders (same action as our TP)
                                if order_status in ['WORKING', 'NEW', 'PENDINGNEW'] and order_action_check == tp_action and order_id_check:
                                    logger.info(f"🗑️ [{acct_name}] Cancelling existing TP {order_id_check} @ {order.get('price')} before placing new")
                                    try:
                                        await tradovate.cancel_order_smart(int(order_id_check))
                                        await asyncio.sleep(0.1)
                                    except Exception as cancel_err:
                                        logger.warning(f"⚠️ [{acct_name}] Could not cancel order {order_id_check}: {cancel_err}")
                        except Exception as e:
                            logger.warning(f"⚠️ [{acct_name}] Could not check/cancel existing orders: {e}")
                        
                        logger.info(f"📊 [{acct_name}] PLACING NEW TP @ {tp_price}")
                        tp_order_data = {
                            "accountId": tradovate_account_id,
                            "accountSpec": tradovate_account_spec,
                            "symbol": local_tradovate_symbol,
                            "action": tp_action,
                            "orderQty": broker_qty,
                            "orderType": "Limit",
                            "price": tp_price,
                            "timeInForce": "GTC",
                            "isAutomated": True
                        }
                        
                        # CRITICAL: NEVER GIVE UP on TP placement - keep retrying until success
                        # TP protection is essential - positions without TP are at risk
                        tp_result = None
                        max_attempts = 10  # Increased from 3 to 10
                        tp_placed = False
                        
                        for tp_attempt in range(max_attempts):
                            tp_result = await tradovate.place_order_smart(tp_order_data)
                            if tp_result and tp_result.get('success'):
                                tp_order_id = tp_result.get('orderId') or tp_result.get('id')
                                logger.info(f"✅ [{acct_name}] TP PLACED @ {tp_price} (order_id: {tp_order_id}) after {tp_attempt+1} attempt(s)")
                                tp_placed = True
                                break
                            else:
                                error_msg = tp_result.get('error', 'Unknown error') if tp_result else 'No response'
                                logger.warning(f"⚠️ [{acct_name}] TP placement attempt {tp_attempt+1}/{max_attempts} failed: {error_msg}")
                                
                                # Exponential backoff: 1s, 2s, 4s, 8s, etc. (max 10s)
                                wait_time = min(2 ** tp_attempt, 10)
                                if tp_attempt < max_attempts - 1:
                                    logger.info(f"   ⏳ Retrying in {wait_time}s...")
                                    await asyncio.sleep(wait_time)
                        
                        if not tp_placed:
                            # CRITICAL ERROR: Position has NO TP protection
                            logger.error(f"❌❌❌ [{acct_name}] CRITICAL: FAILED to place TP after {max_attempts} attempts!")
                            logger.error(f"   Position: {broker_side} {broker_qty} @ {broker_avg} has NO TP PROTECTION!")
                            logger.error(f"   TP should be @ {tp_price} ({tp_action} {broker_qty})")
                            logger.error(f"   Last error: {tp_result.get('error') if tp_result else 'No response'}")
                            logger.error(f"   ⚠️ MANUAL INTERVENTION REQUIRED - Position is unprotected!")
                            
                            # Still return success for the entry, but mark TP as failed
                            # The position monitoring system should detect this and retry
                    
                    # STEP 5: Place SL order if configured (sl_ticks > 0)
                    sl_price = None
                    sl_order_id = None

                    if sl_ticks and sl_ticks > 0:
                        # CRITICAL: Validate broker_avg before calculating SL price
                        # If broker_avg is 0 or None, we can't calculate a valid SL price
                        if not broker_avg or broker_avg <= 0:
                            logger.error(f"❌ [{acct_name}] CANNOT PLACE SL: broker_avg is invalid ({broker_avg})")
                            logger.error(f"   This usually means the fill price wasn't available from order result")
                            logger.error(f"   SL would have been calculated as: {broker_avg} - ({sl_ticks} * {local_tick_size}) = INVALID")
                            logger.error(f"   ⚠️ POSITION HAS NO STOP LOSS PROTECTION!")
                        else:
                            # Calculate SL price (opposite direction from TP)
                            if broker_side == 'LONG':
                                sl_price_raw = broker_avg - (sl_ticks * local_tick_size)
                                sl_action = 'Sell'  # SL sells to close LONG
                            else:
                                sl_price_raw = broker_avg + (sl_ticks * local_tick_size)
                                sl_action = 'Buy'   # SL buys to close SHORT
                            # CRITICAL: Round to nearest valid tick increment
                            sl_price = round(round(sl_price_raw / local_tick_size) * local_tick_size, 10)

                            # Additional validation: SL price must be positive
                            if sl_price <= 0:
                                logger.error(f"❌ [{acct_name}] CANNOT PLACE SL: calculated sl_price is invalid ({sl_price})")
                                logger.error(f"   broker_avg={broker_avg}, sl_ticks={sl_ticks}, tick_size={local_tick_size}")
                                logger.error(f"   ⚠️ POSITION HAS NO STOP LOSS PROTECTION!")
                            else:
                                logger.info(f"📊 [{acct_name}] PLACING SL @ {sl_price} ({sl_ticks} ticks from entry {broker_avg})")
                                sl_order_data = {
                                    "accountId": tradovate_account_id,
                                    "accountSpec": tradovate_account_spec,
                                    "symbol": local_tradovate_symbol,
                                    "action": sl_action,
                                    "orderQty": broker_qty,
                                    "orderType": "Stop",
                                    "stopPrice": sl_price,
                                    "timeInForce": "GTC",
                                    "isAutomated": True
                                }
                                sl_result = await tradovate.place_order_smart(sl_order_data)
                                if sl_result and sl_result.get('success'):
                                    sl_order_id = sl_result.get('orderId') or sl_result.get('id')
                                    logger.info(f"✅ [{acct_name}] SL PLACED @ {sl_price}")
                                else:
                                    error_msg = sl_result.get('error', 'Unknown error') if sl_result else 'No response'
                                    logger.warning(f"⚠️ [{acct_name}] SL order failed: {error_msg}")
                                    logger.warning(f"   Full response: {sl_result}")
                    
                    # CRITICAL: Register TP/SL as OCO pair so one cancels the other when filled
                    if tp_order_id and sl_order_id:
                        try:
                            # Import register_oco_pair from ultra_simple_server
                            import sys
                            import os
                            current_dir = os.path.dirname(os.path.abspath(__file__))
                            parent_dir = os.path.dirname(current_dir)
                            if parent_dir not in sys.path:
                                sys.path.insert(0, parent_dir)
                            
                            from ultra_simple_server import register_oco_pair
                            register_oco_pair(
                                tp_order_id=int(tp_order_id),
                                sl_order_id=int(sl_order_id),
                                account_id=tradovate_account_id,
                                symbol=local_tradovate_symbol.upper()
                            )
                            logger.info(f"🔗 [{acct_name}] OCO pair registered: TP={tp_order_id} <-> SL={sl_order_id}")
                        except ImportError as import_err:
                            logger.warning(f"⚠️ [{acct_name}] Could not import register_oco_pair: {import_err}")
                            logger.warning(f"   TP/SL orders will NOT cancel each other automatically!")
                        except Exception as oco_err:
                            logger.warning(f"⚠️ [{acct_name}] Could not register OCO pair: {oco_err}")
                            logger.warning(f"   TP/SL orders will NOT cancel each other automatically!")
                    elif tp_order_id:
                        logger.info(f"📊 [{acct_name}] TP placed but no SL - skipping OCO registration")
                    elif sl_order_id:
                        logger.info(f"📊 [{acct_name}] SL placed but no TP - skipping OCO registration")

                    # Store tp_order_id in recorded_trades (best-effort, for single-account recorders)
                    # NOTE: recorded_trades has no subaccount_id column, so this overwrites ALL open
                    # trades for the recorder. For multi-account recorders, DCA uses the broker query
                    # instead of this stored value. This is kept for backward compat only.
                    if tp_order_id:
                        try:
                            tp_store_conn = get_db_connection()
                            tp_store_cursor = tp_store_conn.cursor()
                            tp_store_ph = '%s' if is_postgres else '?'
                            tp_store_cursor.execute(f'''
                                UPDATE recorded_trades
                                SET tp_order_id = {tp_store_ph}, tp_price = {tp_store_ph}
                                WHERE recorder_id = {tp_store_ph} AND status = 'open'
                            ''', (str(tp_order_id), tp_price, recorder_id))
                            tp_store_conn.commit()
                            tp_store_conn.close()
                            logger.info(f"💾 [{acct_name}] Stored tp_order_id={tp_order_id} in recorded_trades (note: shared across accounts)")
                        except Exception as tp_store_err:
                            logger.warning(f"⚠️ [{acct_name}] Could not store tp_order_id: {tp_store_err}")

                    return {
                        'success': True,
                        'broker_avg': broker_avg,
                        'broker_qty': broker_qty,
                        'broker_side': broker_side,
                        'tp_price': tp_price,
                        'tp_order_id': tp_order_id,
                        'sl_price': sl_price,
                        'sl_order_id': sl_order_id,
                        'acct_name': acct_name
                    }
                finally:
                    # Clean up non-pooled connections to prevent resource leaks
                    if tradovate and not pooled_conn:
                        try:
                            await tradovate.__aexit__(None, None, None)
                        except:
                            pass
            except Exception as e:
                logger.error(f"❌ [{acct_name}] Exception: {e}")
                return {'success': False, 'error': str(e), 'acct_name': acct_name}
        
        # ============================================================
        # 🚀 SCALABLE EXECUTION - Batch processing for 50-1000 accounts
        # ============================================================
        # Instead of firing all at once (would overwhelm API), process in batches
        # This ensures we stay under rate limits even with 1000+ accounts
        # ============================================================
        
        async def run_all_trades():
            all_results = []
            total_accounts = len(traders)
            
            # Calculate batch count
            num_batches = (total_accounts + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(f"🚀 SCALABLE MODE: {total_accounts} accounts in {num_batches} batches of {BATCH_SIZE}")
            
            for batch_num in range(num_batches):
                start_idx = batch_num * BATCH_SIZE
                end_idx = min(start_idx + BATCH_SIZE, total_accounts)
                batch_traders = traders[start_idx:end_idx]
                
                logger.info(f"📦 Batch {batch_num + 1}/{num_batches}: Processing accounts {start_idx + 1}-{end_idx}")
                
                # Process this batch in parallel
                batch_tasks = [
                    do_trade_for_account(trader, start_idx + idx) 
                    for idx, trader in enumerate(batch_traders)
                ]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                all_results.extend(batch_results)
                
                # Delay between batches to allow rate limit recovery
                # Skip delay after last batch
                if batch_num < num_batches - 1:
                    logger.info(f"⏳ Batch {batch_num + 1} complete. Waiting {BATCH_DELAY_SECONDS}s before next batch...")
                    await asyncio.sleep(BATCH_DELAY_SECONDS)
            
            logger.info(f"✅ All {num_batches} batches processed!")
            return all_results

        # Initialize before try block so it's always defined
        failed_accounts = []
        all_results = []

        try:
            all_results = run_async(run_all_trades())

            for acct_result in all_results:
                if isinstance(acct_result, Exception):
                    logger.error(f"❌ Trade exception: {acct_result}")
                    failed_accounts.append({'error': str(acct_result), 'type': 'exception'})
                elif acct_result and acct_result.get('success'):
                    accounts_traded += 1
                    last_result = acct_result
                    acct_name = acct_result.get('acct_name', 'Unknown')
                    tp_order_id = acct_result.get('tp_order_id')
                    
                    # CRITICAL CHECK: Warn if trade succeeded but no TP was placed
                    if tp_order_id:
                        logger.info(f"✅ [{acct_name}] Trade completed with TP order {tp_order_id}")
                    else:
                        logger.warning(f"⚠️ [{acct_name}] Trade completed but NO TP ORDER PLACED!")
                else:
                    err = acct_result.get('error', 'Unknown') if acct_result else 'No result'
                    acct_name = acct_result.get('acct_name', 'Unknown') if acct_result else 'Unknown'
                    logger.error(f"❌ [{acct_name}] Trade failed: {err}")
                    failed_accounts.append({'acct_name': acct_name, 'error': err})
            
            # Log summary of failures
            if failed_accounts:
                logger.error(f"❌❌❌ CRITICAL: {len(failed_accounts)}/{len(traders)} accounts FAILED to execute!")
                for fail in failed_accounts:
                    logger.error(f"   - {fail.get('acct_name', 'Unknown')}: {fail.get('error', 'Unknown error')}")
                    
        except Exception as e:
            logger.error(f"❌ Parallel execution error: {e}")
            import traceback
            traceback.print_exc()
        
        # Return aggregated result
        # CRITICAL FIX: Set success=True if ANY account traded successfully
        if accounts_traded > 0:
            result['success'] = True
            result['accounts_traded'] = accounts_traded
            result['total_accounts'] = len(traders)

            # Use last_result for backward compatibility (TP/SL order IDs, prices, etc.)
            if last_result:
                result['broker_avg'] = last_result.get('broker_avg')
                result['broker_qty'] = last_result.get('broker_qty')
                result['broker_side'] = last_result.get('broker_side')
                result['tp_price'] = last_result.get('tp_price')
                result['tp_order_id'] = last_result.get('tp_order_id')
                result['sl_price'] = last_result.get('sl_price')
                result['sl_order_id'] = last_result.get('sl_order_id')

            # Store all successful results for multi-account tracking
            successful_results = [r for r in all_results if r and r.get('success')]
            result['all_account_results'] = successful_results
        else:
            result['success'] = False
            result['accounts_traded'] = 0
            result['total_accounts'] = len(traders)
            if failed_accounts:
                result['error'] = f"All {len(failed_accounts)} accounts failed"
                result['failed_accounts'] = failed_accounts

        logger.info(f"📊 TOTAL: {accounts_traded}/{len(traders)} accounts traded successfully")
        return result
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"❌ Trade execution error: {e}")
        import traceback
        traceback.print_exc()
        return result


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
            simulation_mode INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_recorders_webhook ON recorders(webhook_token)')

    # Migration: Add simulation_mode column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE recorders ADD COLUMN simulation_mode INTEGER DEFAULT 0')
        logger.info("✅ Added simulation_mode column to recorders table")
    except:
        pass  # Column already exists
    
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
    ticks = round(price / tick_size)
    clamped = ticks * tick_size
    decimals = max(2, len(str(tick_size).rstrip('0').split('.')[-1]))
    return round(clamped, decimals)


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
        is_postgres = is_using_postgres()
        placeholder = '%s' if is_postgres else '?'
        enabled_val = 'true' if is_postgres else '1'
        
        cursor.execute(f'''
            SELECT t.subaccount_id, t.is_demo, a.tradovate_token,
                   a.username, a.password, a.id as account_id, a.environment
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = {placeholder} AND t.enabled = {enabled_val}
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        if not trader:
            conn.close()
            return result
        
        trader = dict(trader)
        tradovate_account_id = trader.get('subaccount_id')
        # CRITICAL FIX: Use environment as source of truth for demo vs live
        env = (trader.get('environment') or 'demo').lower()
        is_demo = env != 'live'
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
                    # NOTE: Now that position API is fixed (Dec 16, 2025), we can trust broker
                    # BUT: Right after placing order, position may not be visible yet
                    # So we keep DB state here (during trade execution) and let the
                    # 60-second reconciliation handle actual mismatches
                    if broker_net_pos == 0 and db_qty > 0:
                        logger.info(f"ℹ️ Broker shows 0 but DB={db_side} {db_qty} for {ticker} - keeping DB (may be timing)")
                        # Don't clear DB here - reconciliation will handle if actually closed
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
        
        run_async(sync())
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
            is_postgres = is_using_postgres()
            placeholder = '%s' if is_postgres else '?'
            enabled_val = 'true' if is_postgres else '1'
            
            cursor.execute(f'''
                SELECT t.subaccount_id, t.is_demo, a.tradovate_token,
                       a.username, a.password, a.id as account_id, a.environment
                FROM traders t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.recorder_id = {placeholder} AND t.enabled = {enabled_val}
                LIMIT 1
            ''', (recorder_id,))
            
            trader = cursor.fetchone()
            conn.close()
            
            if not trader:
                return
            
            trader = dict(trader)
            tradovate_account_id = trader.get('subaccount_id')
            # CRITICAL FIX: Use environment as source of truth for demo vs live
            env = (trader.get('environment') or 'demo').lower()
            is_demo = env != 'live'
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
                                    result = await tradovate.cancel_order_smart(tp['id'])
                                    if result and result.get('success'):
                                        logger.info(f"✅ [CANCEL-OLD-TP] Cancelled TP order {tp['id']}: {tp['action']} {tp['qty']} @ {tp['price']}")
                                    else:
                                        logger.warning(f"⚠️ [CANCEL-OLD-TP] Cancel order failed for {tp['id']}: {result.get('error') if result else 'No response'}")
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
                run_async(cancel_tp())
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
        is_postgres = is_using_postgres()
        placeholder = '%s' if is_postgres else '?'
        enabled_val = 'true' if is_postgres else '1'
        
        cursor.execute(f'''
            SELECT t.subaccount_id, t.is_demo, a.tradovate_token,
                   a.username, a.password, a.id as account_id, a.environment
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = {placeholder} AND t.enabled = {enabled_val}
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        conn.close()
        
        if not trader:
            return False  # No trader, assume no position
        
        trader = dict(trader)
        tradovate_account_id = trader.get('subaccount_id')
        # CRITICAL FIX: Use environment as source of truth for demo vs live
        env = (trader.get('environment') or 'demo').lower()
        is_demo = env != 'live'
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

        return run_async(check_position())
        
    except Exception as e:
        logger.warning(f"Error checking broker position: {e}")
        return True  # Assume position exists on error (safer)


def get_broker_position_for_recorder(recorder_id: int, ticker: str) -> Dict[str, Any]:
    """
    Get the broker's current position for this recorder/ticker.
    Returns {'quantity': int} where positive=LONG, negative=SHORT, 0=flat.
    """
    result = {'quantity': 0}
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        placeholder = '%s' if is_postgres else '?'
        enabled_val = 'true' if is_postgres else '1'
        
        cursor.execute(f'''
            SELECT t.subaccount_id, t.is_demo, a.tradovate_token,
                   a.username, a.password, a.id as account_id, a.environment
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = {placeholder} AND t.enabled = {enabled_val}
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        conn.close()
        
        if not trader:
            return result
        
        trader = dict(trader)
        tradovate_account_id = trader.get('subaccount_id')
        # CRITICAL FIX: Use environment as source of truth for demo vs live
        env = (trader.get('environment') or 'demo').lower()
        is_demo = env != 'live'
        access_token = trader.get('tradovate_token')
        username = trader.get('username')
        password = trader.get('password')
        account_id = trader.get('account_id')
        
        if not tradovate_account_id:
            return result
        
        tradovate_symbol = convert_ticker_to_tradovate(ticker)
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        from tradovate_api_access import TradovateAPIAccess
        import asyncio
        
        async def get_position():
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
                return {'quantity': 0}
            
            async with TradovateIntegration(demo=is_demo) as tradovate:
                tradovate.access_token = current_token
                positions = await tradovate.get_positions(account_id=tradovate_account_id)
                
                for pos in positions:
                    pos_symbol = pos.get('symbol', '') or ''
                    net_pos = pos.get('netPos', 0)
                    if tradovate_symbol[:3] in pos_symbol:
                        logger.info(f"📊 Broker position for {ticker}: {net_pos}")
                        return {'quantity': net_pos}
                
                logger.info(f"📊 Broker has NO position for {tradovate_symbol}")
                return {'quantity': 0}

        return run_async(get_position())
        
    except Exception as e:
        logger.warning(f"Error getting broker position: {e}")
        return {'quantity': 0}


def get_front_month_contract(root_symbol: str) -> str:
    """
    Dynamically calculate the current front month contract for futures.

    Different products have different contract cycles:
    - Quarterly (index futures): H, M, U, Z (March, June, Sept, Dec)
    - Bimonthly (gold/silver): G, J, M, Q, V, Z (Feb, Apr, Jun, Aug, Oct, Dec)
    - Monthly (crude oil): F, G, H, J, K, M, N, Q, U, V, X, Z (all months)

    Roll typically happens ~1 week before expiration.
    This function returns the currently active front month contract.

    Args:
        root_symbol: The root symbol (e.g., "MNQ", "ES", "MGC", "CL")

    Returns:
        Full contract symbol (e.g., "MNQH5", "MGCG6", "CLG6")
    """
    from datetime import datetime, timedelta

    # Contract cycles by product type
    QUARTERLY_MONTHS = [
        (3, 'H'),   # March
        (6, 'M'),   # June
        (9, 'U'),   # September
        (12, 'Z'),  # December
    ]

    # Bimonthly for Gold/Silver (GC, MGC, SI, etc.)
    BIMONTHLY_MONTHS = [
        (2, 'G'),   # February
        (4, 'J'),   # April
        (6, 'M'),   # June
        (8, 'Q'),   # August
        (10, 'V'),  # October
        (12, 'Z'),  # December
    ]

    # Monthly for Crude Oil (CL, MCL, etc.)
    MONTHLY_MONTHS = [
        (1, 'F'),   # January
        (2, 'G'),   # February
        (3, 'H'),   # March
        (4, 'J'),   # April
        (5, 'K'),   # May
        (6, 'M'),   # June
        (7, 'N'),   # July
        (8, 'Q'),   # August
        (9, 'U'),   # September
        (10, 'V'),  # October
        (11, 'X'),  # November
        (12, 'Z'),  # December
    ]

    # Grain contract months (F, H, K, N, U, Z)
    GRAIN_MONTHS = [
        (1, 'F'),   # January
        (3, 'H'),   # March
        (5, 'K'),   # May
        (7, 'N'),   # July
        (9, 'U'),   # September
        (12, 'Z'),  # December
    ]

    # Determine which contract cycle to use
    root_upper = root_symbol.upper()

    # Metals: Bimonthly (Feb, Apr, Jun, Aug, Oct, Dec)
    if root_upper in ['GC', 'MGC', 'SI', 'SIL', 'HG', 'PL']:
        CONTRACT_MONTHS = BIMONTHLY_MONTHS

    # Energies: Monthly (all 12 months)
    elif root_upper in ['CL', 'MCL', 'NG', 'HO', 'RB']:
        CONTRACT_MONTHS = MONTHLY_MONTHS

    # Crypto: Monthly (all 12 months)
    elif root_upper in ['BTC', 'MBT', 'ETH', 'MET']:
        CONTRACT_MONTHS = MONTHLY_MONTHS

    # Grains: F, H, K, N, U, Z
    elif root_upper in ['ZC', 'ZS', 'ZW', 'ZM', 'ZL']:
        CONTRACT_MONTHS = GRAIN_MONTHS

    # Softs: Specific months (using bimonthly as approximation)
    elif root_upper in ['KC', 'CT', 'SB']:
        CONTRACT_MONTHS = BIMONTHLY_MONTHS

    # Default to quarterly for index futures, treasuries, currencies
    else:
        CONTRACT_MONTHS = QUARTERLY_MONTHS

    today = datetime.now()
    current_month = today.month
    current_year = today.year

    # Find the 3rd Friday of a given month/year (equity index expiration)
    def get_third_friday(year: int, month: int) -> datetime:
        """Get the 3rd Friday of the month"""
        first_day = datetime(year, month, 1)
        days_until_friday = (4 - first_day.weekday()) % 7
        first_friday = first_day + timedelta(days=days_until_friday)
        third_friday = first_friday + timedelta(days=14)
        return third_friday

    def get_expiration_date(year: int, month: int) -> datetime:
        """Get estimated expiration date based on product type.

        - Equity index futures (ES, NQ, etc.): 3rd Friday of contract month
        - Metals (GC, MGC, SI, etc.): ~3rd-to-last business day of month BEFORE contract month
        - Energies (CL, NG, etc.): ~3 business days before 25th of month BEFORE contract month
        - Grains (ZC, ZS, etc.): Mid-month before contract month
        - Default: 1st of the contract month (safe early roll)
        """
        if root_upper in ['ES', 'MES', 'NQ', 'MNQ', 'YM', 'MYM', 'RTY', 'M2K',
                          'ZB', 'ZN', 'ZF', 'ZT', '6E', '6J', '6A', '6B', '6C']:
            # Equity/treasury/currency: 3rd Friday of contract month
            return get_third_friday(year, month)
        elif root_upper in ['GC', 'MGC', 'SI', 'SIL', 'HG', 'PL']:
            # Metals: last trading day is ~3rd-to-last business day of month BEFORE contract month
            # Use 25th of prior month as approximation
            prior_month = month - 1
            prior_year = year
            if prior_month < 1:
                prior_month = 12
                prior_year -= 1
            return datetime(prior_year, prior_month, 25)
        elif root_upper in ['CL', 'MCL', 'NG', 'HO', 'RB']:
            # Energies: ~3 business days before 25th of month BEFORE contract month
            prior_month = month - 1
            prior_year = year
            if prior_month < 1:
                prior_month = 12
                prior_year -= 1
            return datetime(prior_year, prior_month, 20)
        else:
            # Safe default: 1st of contract month (roll early rather than late)
            return datetime(year, month, 1)

    # Roll date: 8 days before expiration for equity, 5 days for others
    ROLL_DAYS_BEFORE_EXPIRY = 8

    # Find the current front month
    for exp_month, month_code in CONTRACT_MONTHS:
        exp_year = current_year

        # If we're past this month entirely, skip to next
        if current_month > exp_month:
            continue

        # Get expiration date for this contract (product-specific)
        expiration = get_expiration_date(exp_year, exp_month)
        roll_date = expiration - timedelta(days=ROLL_DAYS_BEFORE_EXPIRY)

        # If today is before the roll date, this is the front month
        if today < roll_date:
            year_code = str(exp_year)[-1]  # Last digit of year (2026 -> 6)
            result = f"{root_symbol}{month_code}{year_code}"
            logger.debug(f"🗓️ Front month for {root_symbol}: {result}")
            return result

    # If we've passed all contracts this year, use the first contract of next year
    next_year = current_year + 1
    first_month, first_code = CONTRACT_MONTHS[0]
    year_code = str(next_year)[-1]
    result = f"{root_symbol}{first_code}{year_code}"
    logger.debug(f"🗓️ Front month for {root_symbol} (next year): {result}")
    return result


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
    
    # Check if ticker already has a month code (e.g., MNQZ5, ESH5, MGCJ6)
    # Pattern: ROOT + MONTH_CODE + YEAR_DIGIT(S)
    # All month codes: F(Jan) G(Feb) H(Mar) J(Apr) K(May) M(Jun) N(Jul) Q(Aug) U(Sep) V(Oct) X(Nov) Z(Dec)
    month_pattern = re.match(r'^([A-Z]+)([FGHJKMNQUVXZ])(\d{1,2})$', clean_ticker)
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
        is_postgres = is_using_postgres()
        placeholder = '%s' if is_postgres else '?'
        enabled_val = 'true' if is_postgres else '1'
        
        # Find enabled trader with username/password for REST API Access
        # CRITICAL: Include enabled_accounts for multi-account routing
        cursor.execute(f'''
            SELECT 
                t.id as trader_id, t.subaccount_id, t.subaccount_name, t.is_demo, t.enabled_accounts,
                a.name as account_name, a.tradovate_token,
                a.tradovate_refresh_token, a.md_access_token,
                a.username, a.password, a.id as account_id, a.environment
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = {placeholder} AND t.enabled = {enabled_val}
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
                    multiplier = float(acct.get('multiplier', 1.0))  # Extract multiplier from account settings
                    
                    # Look up credentials for this account - CRITICAL: Include environment
                    is_postgres = is_using_postgres()
                    placeholder = '%s' if is_postgres else '?'
                    cursor.execute(f'''
                        SELECT id, name, tradovate_token, tradovate_refresh_token, md_access_token,
                               username, password, environment
                        FROM accounts WHERE id = {placeholder}
                    ''', (acct_id,))
                    account_row = cursor.fetchone()
                    
                    if account_row:
                        account_row = dict(account_row)
                        if account_row.get('username') and account_row.get('password'):
                            # CRITICAL FIX: Detect demo vs live PER-SUBACCOUNT (not account level!)
                            # Priority: 1) acct.environment, 2) acct.is_demo, 3) subaccount name pattern, 4) account.environment
                            is_demo_val = True  # Default to demo for safety
                            if acct.get('environment'):
                                is_demo_val = acct['environment'].lower() != 'live'
                            elif 'is_demo' in acct:
                                is_demo_val = bool(acct.get('is_demo'))
                            elif subaccount_name and (subaccount_name.upper().startswith('DEMO') or 'DEMO' in subaccount_name.upper()):
                                is_demo_val = True  # Name contains DEMO = demo account
                            elif subaccount_name and subaccount_name.isdigit():
                                is_demo_val = False  # Numeric-only name = likely live account
                            else:
                                # Fallback to account-level environment
                                env = (account_row.get('environment') or 'demo').lower()
                                is_demo_val = env != 'live'
                            
                            logger.info(f"🔍 [{subaccount_name}] is_demo={is_demo_val} (detected from subaccount)")
                            accounts_to_trade.append({
                                'subaccount_id': subaccount_id,
                                'subaccount_name': subaccount_name,
                                'is_demo': is_demo_val,
                                'account_name': account_row['name'],
                                'tradovate_token': account_row['tradovate_token'],
                                'md_access_token': account_row['md_access_token'],
                                'username': account_row['username'],
                                'password': account_row['password'],
                                'account_id': account_row['id'],
                                'multiplier': multiplier  # Store multiplier for this account
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
            # CRITICAL FIX: Detect demo vs live from subaccount name pattern
            subaccount_name = trader.get('subaccount_name') or ''
            is_demo_val = True  # Default to demo for safety
            if trader.get('environment'):
                is_demo_val = trader['environment'].lower() != 'live'
            elif subaccount_name.upper().startswith('DEMO') or 'DEMO' in subaccount_name.upper():
                is_demo_val = True
            elif subaccount_name.isdigit():
                is_demo_val = False  # Numeric-only = live
            
            logger.info(f"🔍 [{subaccount_name}] is_demo={is_demo_val} (primary account)")
            accounts_to_trade.append({
                'subaccount_id': trader.get('subaccount_id'),
                'subaccount_name': subaccount_name,
                'is_demo': is_demo_val,
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
            account_multiplier = float(trading_account.get('multiplier', 1.0))  # Get multiplier for this account
            adjusted_quantity = max(1, int(quantity * account_multiplier))  # Apply multiplier to quantity
            
            if not tradovate_account_id:
                logger.warning(f"⚠️ [{acct_idx+1}] Missing account ID - skipping")
                all_results.append({'success': False, 'error': 'Missing account ID'})
                continue
            
            if not username or not password:
                logger.warning(f"⚠️ [{acct_idx+1}] No username/password - will try existing token")
            
            # Log multiplier application
            if account_multiplier != 1.0:
                logger.info(f"📊 [{trading_account['subaccount_name']}] Applying multiplier: {quantity} × {account_multiplier} = {adjusted_quantity} contracts")
            
            # Handle CLOSE action - need to determine position side first
            if action == 'CLOSE':
                order_action = None
            else:
                order_action = 'Buy' if action == 'BUY' else 'Sell'
            
            logger.info(f"📤 [{acct_idx+1}] {action} {adjusted_quantity} {tradovate_symbol} on {trading_account['subaccount_name']}")
            
            async def execute_simple():
                # CRITICAL: Use REST API Access for authentication (avoids rate limiting)
                api_access = TradovateAPIAccess(demo=is_demo)
                
                # Use local variables to avoid scoping issues
                current_access_token = access_token
                current_md_token = trading_account.get('md_access_token')
                # Define order_action - will be set after checking position for CLOSE
                current_order_action = None
                
                # Authenticate via REST API Access - TRY ALL METHODS
                if not current_access_token and username and password:
                    logger.info(f"🔐 Trying REST API Access authentication...")
                    login_result = await api_access.login(
                        username=username,
                        password=password,
                        db_path=DATABASE_PATH,
                        account_id=account_id
                    )
                    
                    if login_result.get('success'):
                        current_access_token = login_result.get('accessToken')
                        current_md_token = login_result.get('mdAccessToken')
                        logger.info(f"✅ REST API Access authentication successful")
                    else:
                        # API Access failed - try OAuth token fallback
                        logger.warning(f"⚠️ REST API Access failed: {login_result.get('error')}")
                        current_access_token = trading_account.get('tradovate_token')
                        if current_access_token:
                            logger.info(f"🔄 Falling back to OAuth token")
                        else:
                            logger.error(f"❌ No OAuth token available for fallback")
                            return {'success': False, 'error': f"Auth failed and no OAuth token"}
                elif current_access_token:
                    logger.info(f"✅ Using existing access token")
                else:
                    # No credentials - try OAuth token
                    current_access_token = trading_account.get('tradovate_token')
                    if current_access_token:
                        logger.info(f"🔑 Using OAuth token (no credentials)")
                    else:
                        logger.error(f"❌ No credentials or OAuth token available")
                        return {'success': False, 'error': 'No credentials or OAuth token available'}
                
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
                    # NOTE: adjusted_quantity is already calculated above with multiplier applied
                    trade_quantity = adjusted_quantity  # Use adjusted quantity (with multiplier)
                    if action == 'CLOSE':
                        if existing_net_pos == 0:
                            logger.warning(f"⚠️ CLOSE signal but no position on broker - nothing to close")
                            return {'success': True, 'message': 'No position to close'}
                        # Close LONG = Sell, Close SHORT = Buy
                        current_order_action = 'Sell' if existing_net_pos > 0 else 'Buy'
                        trade_quantity = abs(existing_net_pos)  # Close entire position (multiplier doesn't apply to closes)
                        logger.info(f"🔄 CLOSE: Closing {existing_net_pos} position with {current_order_action} {trade_quantity}")
                    else:
                        current_order_action = 'Buy' if action == 'BUY' else 'Sell'
                        trade_quantity = adjusted_quantity  # Use adjusted quantity (with multiplier) for BUY/SELL
                
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
                            # NOTE: Position API is now fixed, but we keep DB here for timing reasons
                            # The 60-second reconciliation will catch actual closures
                            if existing_net_pos == 0 and db_qty > 0:
                                logger.info(f"ℹ️ Broker shows 0 but DB shows {db_side} {db_qty} - keeping DB (reconciliation will verify)")
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
                    order_result = await tradovate.place_order_smart(order_data)
                
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
                                order_result = await tradovate.place_order_smart(order_data)
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
                    
                        # STEP 3.5: Check for EXISTING TP order on BROKER and MODIFY it
                        # Per Tradovate best practices: Use modifyOrder instead of cancel+replace
                        # This ensures ONLY ONE TP order exists at any time AND saves API calls
                        existing_tp_order = None
                        existing_tp_id = None
                        
                        # FIRST: Check BROKER directly for any existing TP orders (most reliable)
                        # This avoids cancel+replace - we just modify the existing order
                        try:
                            all_orders = await tradovate.get_orders(account_id=str(tradovate_account_id))
                            for order in (all_orders or []):
                                order_status = str(order.get('ordStatus', '')).upper()
                                order_action = order.get('action', '')
                                order_account = order.get('accountId')
                                
                                # Only match orders for THIS account
                                if order_account and order_account != tradovate_account_id:
                                    continue
                                
                                # Match working limit orders in the TP direction
                                if order_status in ['WORKING', 'NEW', 'PENDINGNEW'] and order_action == tp_side:
                                    existing_tp_id = order.get('id')
                                    existing_tp_order = order
                                    logger.info(f"🔍 Found WORKING TP order on broker: {existing_tp_id} @ {order.get('price')} - will MODIFY (saves API calls)")
                                    break
                        except Exception as e:
                            logger.warning(f"⚠️ Could not check broker for existing TP: {e}")
                        
                        # FALLBACK: Check DB for stored tp_order_id (if broker check missed it)
                        # NOTE: DB tp_order_id may belong to a DIFFERENT account (no subaccount filter
                        # in recorded_trades). We validate by fetching the order and checking accountId.
                        if not existing_tp_order:
                            try:
                                tp_conn = get_db_connection()
                                tp_cursor = tp_conn.cursor()
                                tp_ph2 = '%s' if is_postgres else '?'
                                tp_cursor.execute(f'''
                                    SELECT tp_order_id FROM recorded_trades
                                    WHERE recorder_id = {tp_ph2} AND status = 'open' AND tp_order_id IS NOT NULL
                                    ORDER BY entry_time DESC LIMIT 1
                                ''', (trading_account.get('recorder_id', recorder_id),))
                                tp_row = tp_cursor.fetchone()
                                if tp_row and tp_row['tp_order_id']:
                                    stored_tp_order_id = tp_row['tp_order_id']
                                    logger.info(f"🔍 Found stored TP order ID in DB: {stored_tp_order_id} - validating for this account...")
                                    try:
                                        existing_tp_order = await tradovate.get_order_item(int(stored_tp_order_id))
                                        if existing_tp_order:
                                            order_status = str(existing_tp_order.get('ordStatus', '')).upper()
                                            order_acct = existing_tp_order.get('accountId')
                                            # MULTI-ACCOUNT CHECK: Verify this TP belongs to THIS account
                                            if order_acct and order_acct != tradovate_account_id:
                                                logger.warning(f"⚠️ Stored TP order {stored_tp_order_id} belongs to account {order_acct}, not {tradovate_account_id} - ignoring")
                                                existing_tp_order = None
                                            elif order_status in ['FILLED', 'CANCELLED', 'REJECTED', 'EXPIRED']:
                                                logger.info(f"📋 Stored TP order {stored_tp_order_id} is {order_status} - will place new one")
                                                existing_tp_order = None  # Need to place new
                                            else:
                                                existing_tp_id = stored_tp_order_id
                                                logger.info(f"✅ Stored TP order {stored_tp_order_id} is WORKING - will MODIFY it")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Could not fetch stored TP order: {e}")
                                tp_conn.close()
                            except Exception as e:
                                logger.debug(f"Could not check DB for stored TP order: {e}")
                    
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
                                modify_result = await tradovate.modify_order_smart(
                                    order_id=int(existing_tp_id),
                                    order_data={
                                        "price": tp_price,
                                        "orderQty": tp_qty,  # REQUIRED
                                        "orderType": "Limit",  # REQUIRED
                                        "timeInForce": "GTC"  # REQUIRED - must match original
                                    }
                                )
                            
                                if modify_result and modify_result.get('success'):
                                    tp_order_id = existing_tp_id
                                    logger.info(f"✅ TP MODIFIED: {existing_tp_id} @ {tp_price} (qty: {tp_qty}) - ONLY ONE TP ORDER")
                                else:
                                    error = modify_result.get('error', 'Unknown') if modify_result else 'No response'
                                    logger.error(f"❌ MODIFY FAILED: {error} - Cancelling and placing new")
                                    # Fallback: cancel failed order and place new
                                    try:
                                        await tradovate.cancel_order_smart(int(existing_tp_id))
                                        await asyncio.sleep(0.2)
                                    except:
                                        pass
                                    # Fall through to place new
                                    existing_tp_order = None
                        
                            if not existing_tp_order:
                                # PLACE NEW TP - We already checked broker for existing TPs above,
                                # so if we're here, there truly is no existing TP to modify
                                # NO NEED to cancel anything - just place directly (saves API calls!)
                                logger.info(f"📊 PLACE NEW TP: {tp_side} {tp_qty} @ {tp_price} (no existing TP found on broker)")
                            
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
                            
                                # CRITICAL: NEVER GIVE UP on TP placement - keep retrying until success
                                tp_result = None
                                tp_placed = False
                                max_attempts = 10
                                
                                for tp_attempt in range(max_attempts):
                                    tp_result = await tradovate.place_order_smart(tp_order_data)
                                    if tp_result and tp_result.get('success'):
                                        tp_order_id = tp_result.get('orderId') or tp_result.get('id')
                                        logger.info(f"✅ TP PLACED: {tp_order_id} @ {tp_price} (qty: {tp_qty}) after {tp_attempt+1} attempt(s) - ONLY ONE TP ORDER")
                                        tp_placed = True
                                        break
                                    else:
                                        error_msg = tp_result.get('error', 'Unknown error') if tp_result else 'No response'
                                        logger.warning(f"⚠️ TP placement attempt {tp_attempt+1}/{max_attempts} failed: {error_msg}")
                                        
                                        # Exponential backoff: 1s, 2s, 4s, 8s, etc. (max 10s)
                                        wait_time = min(2 ** tp_attempt, 10)
                                        if tp_attempt < max_attempts - 1:
                                            logger.info(f"   ⏳ Retrying in {wait_time}s...")
                                            await asyncio.sleep(wait_time)
                                
                                if not tp_placed:
                                    logger.error(f"❌❌❌ CRITICAL: FAILED to place TP after {max_attempts} attempts!")
                                    logger.error(f"   Position needs TP @ {tp_price} ({tp_side} {tp_qty})")
                                    logger.error(f"   Last error: {tp_result.get('error') if tp_result else 'No response'}")
                                    logger.error(f"   ⚠️ MANUAL INTERVENTION REQUIRED - Position is unprotected!")
                        else:
                            # tp_price is None/invalid - log why
                            if not tp_price:
                                logger.warning(f"⚠️ TP price is None/invalid - skipping TP placement")
                                logger.warning(f"   This can happen if: 1) tp_ticks is 0, 2) TP calc resulted in invalid price")
                            else:
                                logger.warning(f"⚠️ TP {tp_price} invalid - skipping (would fill instantly)")
                
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
            exec_result = run_async(execute_simple())
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
                
                # NOTE: Tradovate uses 'Canceled' (single L), so after .upper() it's 'CANCELED'
                if order_status not in ['FILLED', 'CANCELED', 'CANCELLED', 'REJECTED', 'EXPIRED']:
                    # Order is still working - MODIFY it
                    logger.info(f"📋 [SINGLE-TP] Order {existing_tp_order_id} is {order_status}, modifying...")
                    
                    modify_result = await tradovate.modify_order_smart(
                        order_id=int(existing_tp_order_id),
                        order_data={
                            "price": float(tp_price),
                            "orderQty": desired_qty,
                            "orderType": "Limit",
                            "timeInForce": tif_default
                        }
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
        
        tp_result = await tradovate.place_order_smart(tp_order)
        
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
        is_postgres = is_using_postgres()
        placeholder = '%s' if is_postgres else '?'
        enabled_val = 'true' if is_postgres else '1'
        
        # NOTE: DB tp_order_id lookup skipped — recorded_trades has no subaccount_id column,
        # so stored tp_order_id may belong to a different account. The per-account broker query
        # below is the reliable approach for multi-account recorders.
        existing_tp_order_id = None
        logger.info(f"📋 [DCA-TP] Skipping DB tp_order_id lookup (multi-account unsafe) - will query broker per-account")
        
        cursor.execute(f'''
            SELECT t.subaccount_id, t.subaccount_name, t.is_demo,
                   a.tradovate_token, a.tradovate_refresh_token, a.md_access_token,
                   a.username, a.password, a.id as account_id, a.environment
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = {placeholder} AND t.enabled = {enabled_val}
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
        # CRITICAL: Use account's environment as source of truth for demo vs live
        env = (trader.get('environment') or 'demo').lower()
        is_demo = env != 'live'
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
            
            # Authenticate if needed - TRY ALL METHODS
            if not current_access_token and username and password:
                logger.info(f"🔐 [DCA-TP] Trying API Access for TP update...")
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
                    # API Access failed - try OAuth token fallback
                    logger.warning(f"⚠️ [DCA-TP] API Access failed: {login_result.get('error')}")
                    current_access_token = trader.get('tradovate_token')
                    if current_access_token:
                        logger.info(f"🔄 [DCA-TP] Falling back to OAuth token")
                    else:
                        return {'success': False, 'error': f"Auth failed and no OAuth token"}
            elif not current_access_token:
                # No credentials - try OAuth token
                current_access_token = trader.get('tradovate_token')
                if not current_access_token:
                    return {'success': False, 'error': 'No credentials or OAuth token available'}
            
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
            res = run_async(do_bulletproof_tp_update())
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
                tp_upd_ph = '%s' if is_postgres else '?'
                cursor2.execute(f'''
                    UPDATE recorded_trades
                    SET tp_order_id = {tp_upd_ph}, tp_price = {tp_upd_ph}
                    WHERE recorder_id = {tp_upd_ph} AND status = 'open'
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
                    # Handle both 'ticks' (new) and 'value' (old) keys
                    tp_val = tp_targets[0].get('ticks')
                    if tp_val is None:
                        tp_val = tp_targets[0].get('value')
                    tp_ticks = int(tp_val or 0)
                    logger.info(f"📊 TP config parsed: tp_ticks={tp_ticks} (from tp_targets: {tp_targets[0]})")
            except Exception as e:
                logger.warning(f"Could not parse tp_targets: {e}")
                tp_ticks = 0  # No TP by default - let strategy handle it

            # Get SL
            if rec.get('sl_enabled'):
                sl_ticks = int(rec.get('sl_amount', 0) or 0)
    except Exception as e:
        logger.warning(f"Could not get TP/SL settings: {e}")
        tp_ticks = 0  # No TP by default - let strategy handle it
        sl_ticks = 0
    
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
        is_postgres = is_using_postgres()
        placeholder = '%s' if is_postgres else '?'
        enabled_val = 'true' if is_postgres else '1'
        
        # Get trader linked to this recorder
        cursor.execute(f'''
            SELECT 
                t.subaccount_id,
                t.subaccount_name,
                t.is_demo,
                a.tradovate_token,
                a.tradovate_refresh_token,
                a.md_access_token,
                a.environment
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.recorder_id = {placeholder} AND t.enabled = {enabled_val}
            LIMIT 1
        ''', (recorder_id,))
        
        trader = cursor.fetchone()
        
        if not trader:
            result['error'] = "No enabled trader for this recorder"
            conn.close()
            return result
        
        trader = dict(trader)
        tradovate_account_id = trader.get('subaccount_id')
        # CRITICAL FIX: Use environment as source of truth for demo vs live
        env = (trader.get('environment') or 'demo').lower()
        is_demo = env != 'live'
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

        broker_pos = run_async(fetch_position())
        
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
                                # Handle both 'ticks' (new) and 'value' (old) keys
                                if tp_targets:
                                    tp_val = tp_targets[0].get('ticks')
                                    if tp_val is None:
                                        tp_val = tp_targets[0].get('value')
                                    tp_ticks = int(tp_val or 0)
                                else:
                                    tp_ticks = 0
                            except:
                                tp_ticks = 0
                            sl_amount = rec.get('sl_amount', 0) if rec.get('sl_enabled') else 0
                        else:
                            tp_ticks = 0  # No TP - let strategy handle it
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
        if is_postgres:
            cursor.execute('''
                SELECT t.*, r.name as recorder_name 
                FROM recorded_trades t
                JOIN recorders r ON t.recorder_id = r.id
                WHERE t.status = 'open' 
                AND (t.tp_price IS NOT NULL OR t.sl_price IS NOT NULL)
                AND (t.broker_managed_tp_sl IS NULL OR t.broker_managed_tp_sl = FALSE)
                AND t.entry_time + INTERVAL '5 seconds' < NOW()
            ''')
        else:
            cursor.execute('''
                SELECT t.*, r.name as recorder_name 
                FROM recorded_trades t
                JOIN recorders r ON t.recorder_id = r.id
                WHERE t.status = 'open' 
                AND (t.tp_price IS NOT NULL OR t.sl_price IS NOT NULL)
                AND (t.broker_managed_tp_sl IS NULL OR t.broker_managed_tp_sl = FALSE)
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
            
            # Check if this trade has broker TP order (tp_order_id set) - if so, let broker handle TP
            has_broker_tp = bool(trade.get('tp_order_id'))
            
            if side == 'LONG':
                logger.debug(f"📍 LONG check: price={current_price} vs TP={tp_price}, SL={sl_price} (broker_tp={has_broker_tp})")
                
                # TP CHECK: Only if NO broker TP order (signal-only mode / Trade Manager style)
                if tp_price and not has_broker_tp and current_price >= tp_price:
                    hit_type = 'tp'
                    exit_price = tp_price
                    logger.info(f"🎯 TP HIT for LONG! {current_price} >= {tp_price}")
                # SL CHECK: Always check SL via price (stops need manual monitoring)
                elif sl_price and current_price <= sl_price:
                    hit_type = 'sl'
                    exit_price = sl_price
                    logger.info(f"🛑 SL HIT for LONG! {current_price} <= {sl_price}")
            else:  # SHORT
                logger.debug(f"📍 SHORT check: price={current_price} vs TP={tp_price}, SL={sl_price} (broker_tp={has_broker_tp})")
                
                # TP CHECK: Only if NO broker TP order (signal-only mode / Trade Manager style)
                if tp_price and not has_broker_tp and current_price <= tp_price:
                    hit_type = 'tp'
                    exit_price = tp_price
                    logger.info(f"🎯 TP HIT for SHORT! {current_price} <= {tp_price}")
                # SL CHECK: Always check SL via price
                elif sl_price and current_price >= sl_price:
                    hit_type = 'sl'
                    exit_price = sl_price
                    logger.info(f"🛑 SL HIT for SHORT! {current_price} >= {sl_price}")
            
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
        
        # Get all open positions from database - CRITICAL: Include environment for demo/live detection
        is_postgres = is_using_postgres()
        enabled_val = 'true' if is_postgres else '1'
        cursor.execute(f'''
            SELECT rp.*, r.name as recorder_name, t.subaccount_id, t.is_demo,
                   a.tradovate_token, a.username, a.password, a.id as account_id, a.environment
            FROM recorder_positions rp
            JOIN recorders r ON rp.recorder_id = r.id
            JOIN traders t ON t.recorder_id = r.id AND t.enabled = {enabled_val}
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
                    # CRITICAL FIX: Use environment as source of truth for demo vs live
                    env = (db_pos.get('environment') or 'demo').lower()
                    is_demo = env != 'live'
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
                        
                        # Compare AND TAKE ACTION
                        if broker_qty == 0 and db_qty != 0:
                            # BROKER IS FLAT BUT DB SHOWS OPEN - CHECK GRACE PERIOD FIRST!
                            # Don't close trades that were recently updated (broker API can be slow)
                            conn_check = get_db_connection()
                            cursor_check = conn_check.cursor()
                            cursor_check.execute('''
                                SELECT updated_at, entry_time FROM recorded_trades 
                                WHERE recorder_id = ? AND status = 'open'
                                ORDER BY entry_time DESC LIMIT 1
                            ''', (recorder_id,))
                            trade_check = cursor_check.fetchone()
                            conn_check.close()
                            
                            if trade_check:
                                from datetime import datetime as dt
                                
                                # CHECK: Is this a signal-only trade? If so, DON'T sync with broker
                                # Signal-only trades (broker_managed_tp_sl = 0) should be closed by TP/SL polling, not broker sync
                                conn_signal_check = get_db_connection()
                                cursor_signal_check = conn_signal_check.cursor()
                                sync_ph = '%s' if is_using_postgres() else '?'
                                cursor_signal_check.execute(f'''
                                    SELECT broker_managed_tp_sl, tp_order_id FROM recorded_trades
                                    WHERE recorder_id = {sync_ph} AND status = 'open' LIMIT 1
                                ''', (recorder_id,))
                                signal_check = cursor_signal_check.fetchone()
                                conn_signal_check.close()
                                
                                if signal_check:
                                    broker_managed = signal_check['broker_managed_tp_sl'] or 0
                                    has_broker_tp = bool(signal_check['tp_order_id'])
                                    
                                    # SKIP BROKER SYNC for signal-only trades (Trade Manager style)
                                    if broker_managed == 0 and not has_broker_tp:
                                        logger.debug(f"📊 SYNC SKIP: Signal-only trade for {ticker} - letting TP/SL polling handle close")
                                        continue
                                
                                try:
                                    updated_str = trade_check['updated_at'] or trade_check['entry_time']
                                    if updated_str:
                                        # Handle both formats - DB stores UTC via datetime('now')
                                        if 'T' in str(updated_str):
                                            updated_at = dt.fromisoformat(str(updated_str).replace('Z', ''))
                                        else:
                                            updated_at = dt.strptime(str(updated_str), '%Y-%m-%d %H:%M:%S')
                                        # Use utcnow() since SQLite datetime('now') stores UTC
                                        age_seconds = (dt.utcnow() - updated_at).total_seconds()
                                        
                                        # GRACE PERIOD: Don't close trades updated in last 90 seconds
                                        if age_seconds < 90:
                                            logger.warning(f"⏳ SYNC SKIP: Broker says flat but trade updated {age_seconds:.0f}s ago - waiting (90s grace period)")
                                            continue  # Skip this closure, check again next cycle
                                except Exception as e:
                                    logger.debug(f"Could not parse timestamp: {e}")
                            
                            # Past grace period - safe to close
                            logger.warning(f"🔄 SYNC FIX: Broker is FLAT but DB shows {db_qty} {ticker} - CLOSING DB RECORD")
                            
                            conn_fix = get_db_connection()
                            cursor_fix = conn_fix.cursor()
                            
                            # Close the recorded_trades entry
                            timestamp_fn = 'NOW()' if is_postgres else "datetime('now')"
                            placeholder = '%s' if is_postgres else '?'
                            cursor_fix.execute(f'''
                                UPDATE recorded_trades 
                                SET status = 'closed', 
                                    exit_reason = 'broker_sync_flat',
                                    exit_time = {timestamp_fn},
                                    updated_at = {timestamp_fn}
                                WHERE recorder_id = {placeholder} AND status = 'open'
                            ''', (recorder_id,))
                            
                            # Clear recorder_positions
                            cursor_fix.execute('''
                                UPDATE recorder_positions
                                SET total_quantity = 0, avg_entry_price = NULL, status = 'closed'
                                WHERE recorder_id = ?
                            ''', (recorder_id,))
                            
                            conn_fix.commit()
                            conn_fix.close()
                            logger.info(f"✅ SYNC FIX COMPLETE: Closed DB record for {ticker} (broker was flat)")
                            
                        elif broker_qty != 0 and db_qty == 0:
                            logger.warning(f"⚠️ ORPHAN: Broker shows {broker_qty} {ticker} but DB shows 0 - manual intervention needed")
                            
                        elif abs(broker_qty) != abs(db_qty):
                            # QUANTITY MISMATCH - UPDATE DB TO MATCH BROKER
                            logger.warning(f"🔄 SYNC FIX: DB shows {db_qty} but broker shows {broker_qty} for {ticker} - UPDATING DB")
                            
                            conn_fix = get_db_connection()
                            cursor_fix = conn_fix.cursor()
                            
                            timestamp_fn = 'NOW()' if is_postgres else "datetime('now')"
                            placeholder = '%s' if is_postgres else '?'
                            cursor_fix.execute(f'''
                                UPDATE recorded_trades 
                                SET quantity = {placeholder},
                                    updated_at = {timestamp_fn}
                                WHERE recorder_id = {placeholder} AND status = 'open'
                            ''', (abs(broker_qty), recorder_id))
                            
                            cursor_fix.execute('''
                                UPDATE recorder_positions 
                                SET total_quantity = ?
                                WHERE recorder_id = ?
                            ''', (abs(broker_qty), recorder_id))
                            
                            conn_fix.commit()
                            conn_fix.close()
                            logger.info(f"✅ SYNC FIX: Updated {ticker} quantity to {abs(broker_qty)}")
                            
                        elif broker_avg and db_avg and abs(broker_avg - db_avg) > 0.5:
                            # PRICE MISMATCH - UPDATE DB AVG TO MATCH BROKER
                            logger.warning(f"🔄 SYNC FIX: DB avg {db_avg} but broker avg {broker_avg} for {ticker} - UPDATING DB")
                            
                            conn_fix = get_db_connection()
                            cursor_fix = conn_fix.cursor()
                            
                            timestamp_fn = 'NOW()' if is_postgres else "datetime('now')"
                            placeholder = '%s' if is_postgres else '?'
                            cursor_fix.execute(f'''
                                UPDATE recorded_trades 
                                SET entry_price = {placeholder},
                                    updated_at = {timestamp_fn}
                                WHERE recorder_id = {placeholder} AND status = 'open'
                            ''', (broker_avg, recorder_id))
                            
                            cursor_fix.execute('''
                                UPDATE recorder_positions 
                                SET avg_entry_price = ?
                                WHERE recorder_id = ?
                            ''', (broker_avg, recorder_id))
                            
                            conn_fix.commit()
                            conn_fix.close()
                            logger.info(f"✅ SYNC FIX: Updated {ticker} avg price to {broker_avg}")
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
                                        logger.warning(f"🔄 SYNC FIX: MISSING TP ORDER for {ticker} - PLACING NOW")
                                        
                                        # Calculate correct TP based on broker avg price
                                        is_long = db_side == 'LONG'
                                        tick_size = 0.25  # MNQ tick size
                                        tp_ticks = 0  # No TP by default - let strategy handle it

                                        # Get TP ticks from recorder settings
                                        conn_tp = get_db_connection()
                                        cursor_tp = conn_tp.cursor()
                                        cursor_tp.execute('SELECT tp_targets FROM recorders WHERE id = ?', (recorder_id,))
                                        rec_row = cursor_tp.fetchone()
                                        conn_tp.close()

                                        if rec_row and rec_row['tp_targets']:
                                            try:
                                                import json
                                                tp_config = json.loads(rec_row['tp_targets'])
                                                if isinstance(tp_config, list) and len(tp_config) > 0:
                                                    tp_ticks = tp_config[0].get('ticks', 0) or 0
                                                elif isinstance(tp_config, dict):
                                                    tp_ticks = tp_config.get('ticks', 0) or 0
                                            except:
                                                pass

                                        # Only place TP if tp_ticks > 0 (skip if 0 - let strategy handle)
                                        if tp_ticks and tp_ticks > 0:
                                            # Calculate TP price from BROKER avg (source of truth)
                                            if is_long:
                                                new_tp_price_raw = broker_avg + (tp_ticks * tick_size)
                                                tp_action = 'Sell'
                                            else:
                                                new_tp_price_raw = broker_avg - (tp_ticks * tick_size)
                                                tp_action = 'Buy'
                                            # Round to nearest valid tick increment
                                            new_tp_price = round(round(new_tp_price_raw / tick_size) * tick_size, 10)

                                            # Place the TP order
                                            try:
                                                result = await tradovate.place_order_smart(
                                                    account_id=str(subaccount_id),
                                                    symbol=tradovate_symbol,
                                                    action=tp_action,
                                                    quantity=abs(broker_qty),
                                                    order_type='Limit',
                                                    price=new_tp_price,
                                                    time_in_force='GTC'
                                                )

                                                if result and result.get('orderId'):
                                                    new_tp_order_id = result.get('orderId')
                                                    logger.info(f"✅ SYNC FIX: Placed TP order {new_tp_order_id}: {tp_action} {abs(broker_qty)} @ {new_tp_price}")

                                                    # Update DB with new TP order ID
                                                    conn_upd = get_db_connection()
                                                    cursor_upd = conn_upd.cursor()
                                                    tp_upd_ph2 = '%s' if is_postgres else '?'
                                                    cursor_upd.execute(f'''
                                                        UPDATE recorded_trades
                                                        SET tp_order_id = {tp_upd_ph2}, tp_price = {tp_upd_ph2}
                                                        WHERE recorder_id = {tp_upd_ph2} AND status = 'open'
                                                    ''', (str(new_tp_order_id), new_tp_price, recorder_id))
                                                    conn_upd.commit()
                                                    conn_upd.close()
                                                else:
                                                    logger.error(f"❌ Failed to place TP order: {result}")
                                            except Exception as tp_err:
                                                logger.error(f"❌ Error placing TP order: {tp_err}")
                            
                except Exception as e:
                    logger.error(f"Error reconciling position for {db_pos.get('ticker', 'unknown')}: {e}")

        run_async(check_all_positions())
        
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


# ============================================================
# 🚨🚨🚨 CRITICAL FUNCTION - DO NOT MODIFY WITHOUT APPROVAL 🚨🚨🚨
# ============================================================
# This function syncs DB with broker every 60 seconds.
# It TAKES ACTION (not just logs) - closes stale trades, updates quantities,
# and AUTO-PLACES missing TP orders.
# Disabling this = broken sync = missing TPs = unprotected trades
# ============================================================
_auto_flat_done_today = set()  # Track which traders were already flattened today

def check_auto_flat_cutoff():
    """Check if any traders with auto_flat_after_cutoff need positions closed.

    Runs inside the reconciliation loop (every 60 seconds).
    If current time is past the trader's time filter stop time,
    close all open positions for that trader.
    """
    global _auto_flat_done_today
    from datetime import datetime, time as dtime

    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')

    # Reset tracking at midnight
    _auto_flat_done_today = {k for k in _auto_flat_done_today if k.startswith(today_str)}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        is_postgres = is_using_postgres()
        ph = '%s' if is_postgres else '?'
        enabled_val = 'TRUE' if is_postgres else '1'

        cursor.execute(f'''
            SELECT t.id, t.recorder_id, t.time_filter_1_stop, t.time_filter_2_stop,
                   t.account_id, t.subaccount_id, t.subaccount_name, t.enabled_accounts
            FROM traders t
            WHERE t.auto_flat_after_cutoff = {enabled_val}
              AND t.enabled = {enabled_val}
        ''')
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return

        current_time = now.time()

        for row in rows:
            trader = dict(row)
            trader_id = trader['id']
            tracker_key = f"{today_str}_{trader_id}"

            if tracker_key in _auto_flat_done_today:
                continue  # Already flattened today

            # Check if past any stop time
            past_cutoff = False
            for stop_field in ['time_filter_1_stop', 'time_filter_2_stop']:
                stop_str = trader.get(stop_field, '')
                if not stop_str:
                    continue
                try:
                    # Parse time strings like "3:00 PM", "15:00", "8:45 AM"
                    stop_str = stop_str.strip()
                    for fmt in ['%I:%M %p', '%H:%M', '%I:%M%p', '%H:%M:%S']:
                        try:
                            parsed = datetime.strptime(stop_str, fmt).time()
                            if current_time > parsed:
                                past_cutoff = True
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            if not past_cutoff:
                continue

            # Check for open positions
            conn2 = get_db_connection()
            cursor2 = conn2.cursor()
            cursor2.execute(f'''
                SELECT id, ticker, side, quantity FROM recorded_trades
                WHERE recorder_id = {ph} AND status = 'open'
            ''', (trader['recorder_id'],))
            open_trades = cursor2.fetchall()
            conn2.close()

            if not open_trades:
                _auto_flat_done_today.add(tracker_key)
                continue

            logger.warning(f"⏰ AUTO FLAT: Trader {trader_id} past cutoff time - closing {len(open_trades)} open position(s)")

            # Close each open position
            for trade_row in open_trades:
                trade = dict(trade_row)
                try:
                    close_action = 'sell' if trade['side'] == 'LONG' else 'buy'
                    close_qty = int(trade.get('quantity', 1))
                    execute_trade_simple(
                        recorder_id=trader['recorder_id'],
                        action=close_action,
                        ticker=trade['ticker'],
                        quantity=close_qty,
                        tp_ticks=0,
                        sl_ticks=0
                    )
                    logger.info(f"⏰ AUTO FLAT: Closed {trade['side']} {trade['ticker']} x{close_qty} for trader {trader_id}")
                except Exception as close_err:
                    logger.error(f"❌ AUTO FLAT: Failed to close trade {trade['id']}: {close_err}")

            _auto_flat_done_today.add(tracker_key)
    except Exception as e:
        logger.error(f"❌ Auto flat cutoff check error: {e}")


def start_daily_state_reset():
    """Reset stale position tracking state daily at CME market close (4:15 PM CT).
    Clears recorder_positions and stale open recorded_trades for LIVE recorders only.
    Paper/simulation recorders are untouched — their trade history is preserved for analytics."""

    _reset_done_date = [None]  # mutable container for closure

    def reset_loop():
        while True:
            try:
                time.sleep(60)  # Check every minute
                now_ct = datetime.now(ZoneInfo('America/Chicago'))
                today_str = now_ct.strftime('%Y-%m-%d')

                # Only run once per day, during the 4:15-4:30 PM CT window
                if _reset_done_date[0] == today_str:
                    continue
                if not (now_ct.hour == 16 and 15 <= now_ct.minute <= 30):
                    continue
                # Skip weekends (Sat=5, Sun=6)
                if now_ct.weekday() >= 5:
                    continue

                logger.info("🧹 Daily state reset starting (market close cleanup)...")
                conn = get_db_connection()
                cursor = conn.cursor()
                is_postgres = is_using_postgres()
                ph = '%s' if is_postgres else '?'

                # Get all LIVE (non-simulation) recorder IDs
                cursor.execute('SELECT id FROM recorders WHERE simulation_mode = 0 OR simulation_mode IS NULL')
                live_ids = [row['id'] if hasattr(row, 'keys') else row[0] for row in cursor.fetchall()]

                if not live_ids:
                    logger.info("🧹 No live recorders found — skipping reset")
                    conn.close()
                    _reset_done_date[0] = today_str
                    continue

                id_list = ','.join(str(int(x)) for x in live_ids)

                # 1) Clear recorder_positions for live recorders
                cursor.execute(f'DELETE FROM recorder_positions WHERE recorder_id IN ({id_list})')
                pos_deleted = cursor.rowcount
                logger.info(f"🧹 Cleared {pos_deleted} recorder_positions rows (live recorders)")

                # 2) Close stale open recorded_trades for live recorders
                cursor.execute(f"UPDATE recorded_trades SET status = 'closed' WHERE status = 'open' AND recorder_id IN ({id_list})")
                trades_closed = cursor.rowcount
                logger.info(f"🧹 Closed {trades_closed} stale open recorded_trades (live recorders)")

                # 3) Zero signal counters on traders for live recorders
                cursor.execute(f'UPDATE traders SET signal_count = 0, today_signal_count = 0 WHERE recorder_id IN ({id_list})')
                traders_reset = cursor.rowcount
                logger.info(f"🧹 Reset signal counters on {traders_reset} traders")

                conn.commit()
                conn.close()
                _reset_done_date[0] = today_str
                logger.info(f"✅ Daily state reset complete — next reset tomorrow")
            except Exception as e:
                logger.error(f"❌ Daily state reset error: {e}")

    _reset_thread = threading.Thread(target=reset_loop, daemon=True, name="DailyStateReset")
    _reset_thread.start()


def start_position_reconciliation():
    """Start the position reconciliation thread (runs every 60 seconds)

    CRITICAL: This must ALWAYS run. It:
    1. Closes DB records when broker is flat
    2. Updates DB quantity to match broker
    3. Updates DB avg price to match broker
    4. AUTO-PLACES missing TP orders
    5. Checks auto_flat_after_cutoff traders
    """
    global _position_reconciliation_thread

    if _position_reconciliation_thread and _position_reconciliation_thread.is_alive():
        return

    def reconciliation_loop():
        logger.info("🔄 Starting position reconciliation thread (every 60 seconds)")
        while True:
            try:
                reconcile_positions_with_broker()
                check_auto_flat_cutoff()
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
        is_postgres = is_using_postgres()

        # Find any account with tradingview_session set (don't hardcode id=1)
        if is_postgres:
            cursor.execute("SELECT tradingview_session FROM accounts WHERE tradingview_session IS NOT NULL AND tradingview_session != '' ORDER BY id LIMIT 1")
        else:
            cursor.execute("SELECT tradingview_session FROM accounts WHERE tradingview_session IS NOT NULL AND tradingview_session != '' ORDER BY id LIMIT 1")

        row = cursor.fetchone()
        conn.close()

        if row:
            session_data = row['tradingview_session'] if isinstance(row, dict) else row[0]
            if session_data:
                return json.loads(session_data)
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
        run_async(connect_tradingview_websocket())
    
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


@app.route('/api/accounts/auth-status', methods=['GET'])
def api_accounts_auth_status():
    """
    Get authentication status for all accounts.
    Returns list of accounts that need OAuth re-authentication.
    """
    try:
        accounts_need_reauth = get_accounts_needing_reauth()
        
        # Get account names for the IDs
        account_details = []
        if accounts_need_reauth:
            conn = get_db_connection()
            cursor = conn.cursor()
            for acct_id in accounts_need_reauth:
                cursor.execute('SELECT id, name FROM accounts WHERE id = ?', (acct_id,))
                row = cursor.fetchone()
                if row:
                    account_details.append({
                        'id': row['id'],
                        'name': row['name'],
                        'status': 'needs_reauth',
                        'action': 'Go to Account Management and click "Connect to Tradovate"'
                    })
            conn.close()
        
        return jsonify({
            'success': True,
            'all_accounts_valid': len(accounts_need_reauth) == 0,
            'accounts_needing_reauth': account_details,
            'count': len(account_details),
            'message': 'All accounts authenticated!' if len(accounts_need_reauth) == 0 else f'{len(accounts_need_reauth)} account(s) need OAuth re-authentication'
        })
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


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
                recording_enabled, simulation_mode, webhook_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            1 if data.get('simulation_mode', False) else 0,
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
        if 'simulation_mode' in data:
            fields.append('simulation_mode = ?')
            values.append(1 if data['simulation_mode'] else 0)
        
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


@app.route('/api/recorders/clear-all-history', methods=['POST'])
def api_clear_all_trade_history():
    """Clear ALL trade history across all recorders - start fresh"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get counts before clearing
        cursor.execute('SELECT COUNT(*) FROM recorded_trades')
        trades_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM recorder_positions')
        positions_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM recorded_signals')
        signals_count = cursor.fetchone()[0]

        # Clear all trade-related tables
        cursor.execute('DELETE FROM recorded_trades')
        cursor.execute('DELETE FROM recorder_positions')
        cursor.execute('DELETE FROM recorded_signals')

        conn.commit()
        conn.close()

        # Rebuild index since positions changed
        rebuild_index()

        logger.info(f"🗑️ CLEARED ALL TRADE HISTORY: {trades_count} trades, {signals_count} signals, {positions_count} positions deleted")

        return jsonify({
            'success': True,
            'message': f'All trade history cleared! Deleted {trades_count} trades, {signals_count} signals, and {positions_count} positions.',
            'trades_deleted': trades_count,
            'signals_deleted': signals_count,
            'positions_deleted': positions_count
        })
    except Exception as e:
        logger.error(f"Error clearing all trade history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/recorders/<int:recorder_id>/toggle-simulation', methods=['POST'])
def api_toggle_simulation_mode(recorder_id):
    """Toggle simulation mode for a recorder (paper trading vs live)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if recorder exists and get current state
        cursor.execute('SELECT simulation_mode FROM recorders WHERE id = ?', (recorder_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return jsonify({'success': False, 'error': 'Recorder not found'}), 404

        current_mode = row[0] if row[0] else 0
        new_mode = 0 if current_mode else 1

        cursor.execute('''
            UPDATE recorders SET simulation_mode = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (new_mode, recorder_id))
        conn.commit()
        conn.close()

        mode_str = 'SIMULATION (Paper Trading)' if new_mode else 'LIVE (Broker Execution)'
        logger.info(f"📝 Recorder {recorder_id} mode changed to: {mode_str}")

        return jsonify({
            'success': True,
            'simulation_mode': bool(new_mode),
            'message': f'Recorder is now in {mode_str} mode'
        })
    except Exception as e:
        logger.error(f"Error toggling simulation mode for recorder {recorder_id}: {e}")
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
        simulation_mode = recorder.get('simulation_mode', 0) == 1

        if simulation_mode:
            logger.info(f"📝 SIMULATION MODE: Recording paper trade for '{recorder_name}' (no broker execution)")

        # CRITICAL: Sync with broker BEFORE processing signal to prevent drift
        # This ensures database matches broker state (especially if user cleared positions)
        # BUT: Skip sync if we're rate limited to avoid blocking trades
        data = request.get_json() if request.is_json else request.form.to_dict()
        ticker = data.get('ticker') or data.get('symbol', '')
        
        # NOTE: TP order cancellation is handled INSIDE execute_live_trade_with_bracket()
        # which has comprehensive logic to cancel old TPs without cancelling new ones.
        # We don't cancel here to avoid race conditions with newly placed TP orders.
        
        # Skip broker sync for simulation mode or test mode
        if ticker and not SIGNAL_BASED_TEST_MODE and not simulation_mode:
            try:
                sync_result = sync_position_with_broker(recorder_id, ticker)
                if sync_result.get('cleared'):
                    logger.info(f"🔄 Webhook: Cleared database position - broker has no position for {ticker}")
                elif sync_result.get('synced'):
                    logger.info(f"🔄 Webhook: Synced database with broker position for {ticker}")
            except Exception as e:
                # If sync fails (e.g., rate limited), continue anyway - don't block the trade
                logger.warning(f"⚠️ Sync failed (continuing anyway): {e}")
        elif SIGNAL_BASED_TEST_MODE:
            logger.debug(f"🧪 TEST MODE: Skipping broker sync for {ticker}")
        elif simulation_mode:
            logger.debug(f"📝 SIMULATION: Skipping broker sync for {ticker}")
        
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

        # Cache the real-time price from webhook (TradingView {{close}} is real-time)
        if ticker and price:
            try:
                root = extract_symbol_root(ticker)
                if root:
                    _market_data_cache[root] = {
                        'last': float(price),
                        'source': 'webhook',
                        'updated': time.time()
                    }
                    logger.debug(f"📊 Cached real-time price from webhook: {root} = {price}")
            except Exception as e:
                logger.debug(f"Could not cache webhook price: {e}")

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

        # Handle PRICE_UPDATE - just cache the price and return (no trade action)
        if normalized_action == 'PRICE_UPDATE':
            conn.close()
            root = extract_symbol_root(ticker) if ticker else None
            return jsonify({
                'success': True,
                'action': 'price_update',
                'ticker': ticker,
                'price': float(price) if price else None,
                'cached_as': root,
                'message': f'Price updated for {root}: {price}'
            })

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
        
        # Parse quantity from webhook - use recorder's initial_position_size if not specified
        raw_quantity = data.get('quantity', data.get('qty'))  # Don't default to 1
        if raw_quantity:
            quantity = int(raw_quantity)
        elif position_size:
            quantity = int(position_size)
        else:
            # Use recorder's initial_position_size setting
            quantity = int(recorder.get('initial_position_size', 1))
        
        # Detailed logging for quantity tracking
        logger.info(f"🎯 Processing webhook for '{recorder_name}': qty={quantity} (raw from webhook: {raw_quantity}, position_size: {position_size}, data keys: {list(data.keys())})")
        
        # Get TP/SL settings from recorder
        sl_enabled = recorder.get('sl_enabled', 0)
        sl_amount = recorder.get('sl_ticks', 0) or recorder.get('sl_amount', 0) or 0
        
        # Get TP ticks - first try direct column, then tp_targets JSON
        tp_ticks = recorder.get('tp_ticks', 0) or 0
        if not tp_ticks:
            # Fallback: Parse TP targets (JSON array) if direct column is empty
            tp_targets_raw = recorder.get('tp_targets', '[]')
            try:
                tp_targets = json.loads(tp_targets_raw) if isinstance(tp_targets_raw, str) else tp_targets_raw or []
                # Handle both 'ticks' (new) and 'value' (old) keys
                if tp_targets:
                    tp_val = tp_targets[0].get('ticks')
                    if tp_val is None:
                        tp_val = tp_targets[0].get('value')
                    tp_ticks = int(tp_val or 0)
                else:
                    tp_ticks = 0
            except:
                tp_ticks = 0
        
        logger.info(f"📊 Recorder TP/SL config: tp_ticks={tp_ticks}, sl_ticks={sl_amount}, sl_enabled={sl_enabled}")
        
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
                broker_closed = False

                # In simulation mode, skip broker liquidation entirely
                if simulation_mode:
                    logger.info(f"📝 SIMULATION: Closing {open_trade['side']} position (no broker call)")
                    broker_closed = True  # Simulated close always succeeds
                    # Publish paper signal for standalone paper trading service
                    try:
                        if _paper_redis:
                            _paper_redis.publish('paper_signals', json.dumps({
                                'recorder_id': recorder_id, 'action': 'CLOSE',
                                'ticker': ticker, 'price': float(current_price),
                                'quantity': int(open_trade.get('quantity', 1)),
                                'timestamp': datetime.utcnow().isoformat()
                            }))
                    except Exception:
                        logger.warning("Could not publish paper CLOSE signal")
                else:
                    logger.info(f"🔄 CLOSE signal: Liquidating {open_trade['side']} position on broker (cancels TP orders automatically)...")

                    # Get trader info for broker access
                    is_postgres_inner = is_using_postgres()
                    placeholder_inner = '%s' if is_postgres_inner else '?'
                    enabled_val_inner = 'true' if is_postgres_inner else '1'
                    cursor.execute(f'''
                        SELECT t.subaccount_id, t.subaccount_name, t.is_demo,
                               a.tradovate_token, a.tradovate_refresh_token, a.md_access_token,
                               a.username, a.password, a.id as account_id, a.environment
                        FROM traders t
                        JOIN accounts a ON t.account_id = a.id
                        WHERE t.recorder_id = {placeholder_inner} AND t.enabled = {enabled_val_inner}
                        LIMIT 1
                    ''', (recorder_id,))
                    trader = cursor.fetchone()

                    if trader:
                        trader = dict(trader)
                        tradovate_account_id = trader.get('subaccount_id')
                        # CRITICAL FIX: Use environment as source of truth for demo vs live
                        env = (trader.get('environment') or 'demo').lower()
                        is_demo = env != 'live'
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
                                            result = await tradovate.place_order_smart(order_data)
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
                                                            cancel_result = await tradovate.cancel_order_smart(int(order_id))
                                                            if cancel_result and cancel_result.get('success'):
                                                                cancelled += 1
                                                        except:
                                                            pass
                                                if cancelled > 0:
                                                    logger.info(f"✅ Cancelled {cancelled} TP order(s) after manual close")
                                                return {'success': True}

                                    return {'success': False, 'error': 'No position found to close'}

                            broker_result = run_async(liquidate())
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
            # ============================================================
            # SIMPLE BUY LOGIC - The Formula
            # 1. Place market order
            # 2. Get broker's position (avg + qty)
            # 3. Place/modify TP at avg + (ticks * tick_size)
            # 
            # NO separate DCA logic needed - broker tracks average for us!
            # ============================================================
            logger.info(f"📈 BUY signal for '{recorder_name}': {quantity} {ticker}")
            
            # Close any existing SHORT first (reversal)
            if open_trade and open_trade['side'] == 'SHORT':
                pnl_ticks = (open_trade['entry_price'] - current_price) / tick_size
                pnl, _ = close_trade_helper(cursor, open_trade, current_price, pnl_ticks, tick_value, 'reversal')
                logger.info(f"📊 SHORT closed by BUY reversal: ${pnl:.2f}")
            
            # SIMPLE EXECUTION: Place order, get broker position, place/modify TP
            # Skip broker execution in simulation mode - use signal-only tracking
            if simulation_mode:
                broker_result = {'success': False, 'no_broker': True, 'simulation': True}
                logger.info(f"📝 SIMULATION: Skipping broker execution for BUY {ticker}")
                # Publish paper signal for standalone paper trading service
                try:
                    if _paper_redis:
                        _paper_redis.publish('paper_signals', json.dumps({
                            'recorder_id': recorder_id, 'action': 'BUY',
                            'ticker': ticker, 'price': float(current_price),
                            'quantity': int(quantity), 'tp_ticks': int(tp_ticks),
                            'sl_enabled': int(sl_enabled), 'sl_amount': int(sl_amount),
                            'dca_enabled': bool(recorder.get('avg_down_enabled', 0)),
                            'timestamp': datetime.utcnow().isoformat()
                        }))
                except Exception:
                    logger.warning("Could not publish paper BUY signal")
            else:
                broker_result = execute_trade_simple(
                    recorder_id=recorder_id,
                    action='BUY',
                    ticker=ticker,
                    quantity=quantity,
                    tp_ticks=tp_ticks
                )

            if broker_result.get('success') and broker_result.get('broker_avg'):
                trade_result = {
                    'action': 'executed',
                    'side': 'LONG',
                    'avg_entry_price': broker_result['broker_avg'],
                    'total_quantity': broker_result['broker_qty'],
                    'tp_price': broker_result['tp_price'],
                    'tp_order_id': broker_result.get('tp_order_id'),
                    'broker_confirmed': True
                }
                logger.info(f"✅ BUY EXECUTED: {broker_result['broker_qty']} @ {broker_result['broker_avg']:.2f} | TP: {broker_result['tp_price']}")
            elif broker_result.get('error'):
                # Broker failed - fall through to signal-only tracking (Trade Manager style)
                logger.warning(f"⚠️ Broker unavailable: {broker_result['error']} - using signal-only tracking")
                broker_result = {'success': False, 'no_broker': True}
            
            # Check if we should do signal-only tracking (no broker or broker failed)
            if broker_result.get('no_broker') or (not broker_result.get('success') and not broker_result.get('broker_avg')):
                # SIGNAL-ONLY MODE (Trade Manager style) - record trade with internal TP/SL
                logger.info(f"📝 Recording signal-only trade with internal TP/SL (Trade Manager style)")
                
                entry_price = current_price
                calculated_tp, sl_price = calculate_tp_sl_prices(
                    entry_price, 'LONG', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                )
                
                # Create trade with TP/SL for internal monitoring (broker_managed_tp_sl = 0)
                cursor.execute('''
                    INSERT INTO recorded_trades
                    (recorder_id, signal_id, ticker, action, side, entry_price, entry_time,
                     quantity, status, tp_price, sl_price, broker_managed_tp_sl)
                    VALUES (?, ?, ?, 'BUY', 'LONG', ?, CURRENT_TIMESTAMP, ?, 'open', ?, ?, 0)
                ''', (recorder_id, signal_id, ticker, entry_price, quantity, calculated_tp, sl_price))
                
                new_trade_id = cursor.lastrowid
                
                # Update position tracking
                pos_id, is_new_pos, total_qty = update_recorder_position_helper(
                    cursor, recorder_id, ticker, 'LONG', entry_price, quantity
                )
                
                trade_result = {
                    'action': 'opened', 'trade_id': new_trade_id, 'side': 'LONG',
                    'entry_price': entry_price, 'quantity': quantity,
                    'tp_price': calculated_tp, 'sl_price': sl_price,
                    'position_id': pos_id, 'position_qty': total_qty,
                    'broker_managed_tp_sl': False,
                    'internal_tp_sl': True
                }
                logger.info(f"📈 LONG OPENED (signal-only) for '{recorder_name}': {ticker} @ {entry_price} x{quantity} | TP: {calculated_tp} | Internal TP/SL monitoring")
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
        
        elif normalized_action == 'SELL':
            # ============================================================
            # SIMPLE SELL LOGIC - The Formula
            # 1. Place market order
            # 2. Get broker's position (avg + qty)
            # 3. Place/modify TP at avg - (ticks * tick_size)
            # 
            # NO separate DCA logic needed - broker tracks average for us!
            # ============================================================
            logger.info(f"📉 SELL signal for '{recorder_name}': {quantity} {ticker}")
            
            # Close any existing LONG first (reversal)
            if open_trade and open_trade['side'] == 'LONG':
                pnl_ticks = (current_price - open_trade['entry_price']) / tick_size
                pnl, _ = close_trade_helper(cursor, open_trade, current_price, pnl_ticks, tick_value, 'reversal')
                logger.info(f"📊 LONG closed by SELL reversal: ${pnl:.2f}")
            
            # SIMPLE EXECUTION: Place order, get broker position, place/modify TP
            # Skip broker execution in simulation mode - use signal-only tracking
            if simulation_mode:
                broker_result = {'success': False, 'no_broker': True, 'simulation': True}
                logger.info(f"📝 SIMULATION: Skipping broker execution for SELL {ticker}")
                # Publish paper signal for standalone paper trading service
                try:
                    if _paper_redis:
                        _paper_redis.publish('paper_signals', json.dumps({
                            'recorder_id': recorder_id, 'action': 'SELL',
                            'ticker': ticker, 'price': float(current_price),
                            'quantity': int(quantity), 'tp_ticks': int(tp_ticks),
                            'sl_enabled': int(sl_enabled), 'sl_amount': int(sl_amount),
                            'dca_enabled': bool(recorder.get('avg_down_enabled', 0)),
                            'timestamp': datetime.utcnow().isoformat()
                        }))
                except Exception:
                    logger.warning("Could not publish paper SELL signal")
            else:
                broker_result = execute_trade_simple(
                    recorder_id=recorder_id,
                    action='SELL',
                    ticker=ticker,
                    quantity=quantity,
                    tp_ticks=tp_ticks
                )

            if broker_result.get('success') and broker_result.get('broker_avg'):
                trade_result = {
                    'action': 'executed',
                    'side': 'SHORT',
                    'avg_entry_price': broker_result['broker_avg'],
                    'total_quantity': broker_result['broker_qty'],
                    'tp_price': broker_result['tp_price'],
                    'tp_order_id': broker_result.get('tp_order_id'),
                    'broker_confirmed': True
                }
                logger.info(f"✅ SELL EXECUTED: {broker_result['broker_qty']} @ {broker_result['broker_avg']:.2f} | TP: {broker_result['tp_price']}")
            elif broker_result.get('error'):
                # Broker failed - fall through to signal-only tracking (Trade Manager style)
                logger.warning(f"⚠️ Broker unavailable: {broker_result['error']} - using signal-only tracking")
                broker_result = {'success': False, 'no_broker': True}
            
            # Check if we should do signal-only tracking (no broker or broker failed)
            if broker_result.get('no_broker') or (not broker_result.get('success') and not broker_result.get('broker_avg')):
                # SIGNAL-ONLY MODE (Trade Manager style) - record trade with internal TP/SL
                logger.info(f"📝 Recording signal-only trade with internal TP/SL (Trade Manager style)")
                
                entry_price = current_price
                calculated_tp, sl_price = calculate_tp_sl_prices(
                    entry_price, 'SHORT', tp_ticks, sl_amount if sl_enabled else 0, tick_size
                )
                
                # Create trade with TP/SL for internal monitoring (broker_managed_tp_sl = 0)
                cursor.execute('''
                    INSERT INTO recorded_trades
                    (recorder_id, signal_id, ticker, action, side, entry_price, entry_time,
                     quantity, status, tp_price, sl_price, broker_managed_tp_sl)
                    VALUES (?, ?, ?, 'SELL', 'SHORT', ?, CURRENT_TIMESTAMP, ?, 'open', ?, ?, 0)
                ''', (recorder_id, signal_id, ticker, entry_price, quantity, calculated_tp, sl_price))
                
                new_trade_id = cursor.lastrowid
                
                # Update position tracking
                pos_id, is_new_pos, total_qty = update_recorder_position_helper(
                    cursor, recorder_id, ticker, 'SHORT', entry_price, quantity
                )
                
                trade_result = {
                    'action': 'opened', 'trade_id': new_trade_id, 'side': 'SHORT',
                    'entry_price': entry_price, 'quantity': quantity,
                    'tp_price': calculated_tp, 'sl_price': sl_price,
                    'position_id': pos_id, 'position_qty': total_qty,
                    'broker_managed_tp_sl': False,
                    'internal_tp_sl': True
                }
                logger.info(f"📉 SHORT OPENED (signal-only) for '{recorder_name}': {ticker} @ {entry_price} x{quantity} | TP: {calculated_tp} | Internal TP/SL monitoring")
        
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
                'tp_enabled': bool(tp_ticks),
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

    # Start daily state reset daemon (clears stale position tracking at market close)
    start_daily_state_reset()
    logger.info("✅ Daily state reset active (4:15 PM CT, skips paper recorders)")

    # ============================================================
    # 🚨🚨🚨 CRITICAL: BROKER SYNC - DO NOT DISABLE 🚨🚨🚨
    # ============================================================
    # This keeps DB in sync with broker and auto-places missing TPs.
    # WITHOUT THIS:
    # - DB will drift out of sync with broker
    # - Stale trades will remain "open" in DB when broker is flat
    # - Missing TP orders won't be detected or fixed
    # - DCA will break because DB doesn't reflect real position
    #
    # NEVER COMMENT OUT OR DISABLE THIS LINE:
    start_position_reconciliation()
    logger.info("✅ Position reconciliation ENABLED (syncs DB with broker every 60s, auto-places missing TPs)")
    # ============================================================

    # Start bracket fill monitor (detects when Tradovate closes positions)
    start_bracket_monitor()
    logger.info("✅ Bracket fill monitor active")

    # Start position drawdown polling thread (Trade Manager style tracking)
    start_position_drawdown_polling()
    logger.info("✅ Position drawdown tracking active")

    # Start bulletproof token refresh daemon (auto-refresh before expiry)
    start_token_refresh_daemon()
    logger.info("✅ Token refresh daemon active - will auto-refresh tokens before expiry")

    logger.info(f"✅ Trading Engine ready on port {SERVICE_PORT}")
    logger.info("=" * 60)


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    initialize()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=False, threaded=True)
