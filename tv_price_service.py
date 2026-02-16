#!/usr/bin/env python3
"""
TradingView Real-Time Price Service
Streams live tick data from TradingView WebSocket for paper trading
~300-500ms delay with TradingView Premium
"""

import json
import random
import string
import re
import threading
import time
import sqlite3
from datetime import datetime
from typing import Dict, Callable, Optional
import logging

try:
    import websocket
except ImportError:
    print("Installing websocket-client...")
    import subprocess
    subprocess.check_call(['pip3', 'install', 'websocket-client', '--break-system-packages'])
    import websocket

import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TVPriceService')

# TradingView WebSocket URL
TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"

# Symbols to track (TradingView format)
DEFAULT_SYMBOLS = [
    # Futures
    "CME_MINI:ES1!",   # E-mini S&P 500
    "CME_MINI:NQ1!",   # E-mini Nasdaq 100
    "CME_MINI:MES1!",  # Micro E-mini S&P 500
    "CME_MINI:MNQ1!",  # Micro E-mini Nasdaq 100
    # ETFs / Indices
    "AMEX:QQQ",        # Nasdaq 100 ETF
    "AMEX:SPY",        # S&P 500 ETF
    "CBOE:VIX",        # Volatility Index
    "TVC:DXY",         # US Dollar Index
    # Mega-cap stocks
    "NASDAQ:AAPL",     # Apple
    "NASDAQ:NVDA",     # Nvidia
    "NASDAQ:MSFT",     # Microsoft
    "NASDAQ:META",     # Meta
    "NASDAQ:GOOG",     # Alphabet
    "NASDAQ:AMZN",     # Amazon
    "NASDAQ:TSLA",     # Tesla
    "NASDAQ:AVGO",     # Broadcom
    # Commodities / Crypto
    "COMEX:GC1!",      # Gold futures
    "COMEX:MGC1!",     # Micro Gold futures
    "COMEX:SI1!",      # Silver futures
    "BITSTAMP:BTCUSD", # Bitcoin
]

# Futures contract specifications for P&L calculation
# Format: symbol -> (tick_size, tick_value, point_value, exchange)
FUTURES_SPECS = {
    # E-mini contracts
    'ES': {'tick_size': 0.25, 'tick_value': 12.50, 'point_value': 50.00, 'exchange': 'CME'},
    'NQ': {'tick_size': 0.25, 'tick_value': 5.00, 'point_value': 20.00, 'exchange': 'CME'},
    'RTY': {'tick_size': 0.10, 'tick_value': 5.00, 'point_value': 50.00, 'exchange': 'CME'},
    'YM': {'tick_size': 1.00, 'tick_value': 5.00, 'point_value': 5.00, 'exchange': 'CBOT'},

    # Micro contracts
    'MES': {'tick_size': 0.25, 'tick_value': 1.25, 'point_value': 5.00, 'exchange': 'CME'},
    'MNQ': {'tick_size': 0.25, 'tick_value': 0.50, 'point_value': 2.00, 'exchange': 'CME'},
    'M2K': {'tick_size': 0.10, 'tick_value': 0.50, 'point_value': 5.00, 'exchange': 'CME'},
    'MYM': {'tick_size': 1.00, 'tick_value': 0.50, 'point_value': 0.50, 'exchange': 'CBOT'},

    # Energy
    'CL': {'tick_size': 0.01, 'tick_value': 10.00, 'point_value': 1000.00, 'exchange': 'NYMEX'},
    'MCL': {'tick_size': 0.01, 'tick_value': 1.00, 'point_value': 100.00, 'exchange': 'NYMEX'},
    'NG': {'tick_size': 0.001, 'tick_value': 10.00, 'point_value': 10000.00, 'exchange': 'NYMEX'},

    # Metals
    'GC': {'tick_size': 0.10, 'tick_value': 10.00, 'point_value': 100.00, 'exchange': 'COMEX'},
    'MGC': {'tick_size': 0.10, 'tick_value': 1.00, 'point_value': 10.00, 'exchange': 'COMEX'},
    'SI': {'tick_size': 0.005, 'tick_value': 25.00, 'point_value': 5000.00, 'exchange': 'COMEX'},
    'SIL': {'tick_size': 0.005, 'tick_value': 2.50, 'point_value': 500.00, 'exchange': 'COMEX'},
    'HG': {'tick_size': 0.0005, 'tick_value': 12.50, 'point_value': 25000.00, 'exchange': 'COMEX'},

    # Currencies
    '6E': {'tick_size': 0.00005, 'tick_value': 6.25, 'point_value': 125000.00, 'exchange': 'CME'},
    '6J': {'tick_size': 0.0000005, 'tick_value': 6.25, 'point_value': 12500000.00, 'exchange': 'CME'},
    '6B': {'tick_size': 0.0001, 'tick_value': 6.25, 'point_value': 62500.00, 'exchange': 'CME'},

    # Treasuries
    'ZB': {'tick_size': 0.03125, 'tick_value': 31.25, 'point_value': 1000.00, 'exchange': 'CBOT'},
    'ZN': {'tick_size': 0.015625, 'tick_value': 15.625, 'point_value': 1000.00, 'exchange': 'CBOT'},
    'ZF': {'tick_size': 0.0078125, 'tick_value': 7.8125, 'point_value': 1000.00, 'exchange': 'CBOT'},

    # Agriculture
    'ZC': {'tick_size': 0.25, 'tick_value': 12.50, 'point_value': 50.00, 'exchange': 'CBOT'},
    'ZS': {'tick_size': 0.25, 'tick_value': 12.50, 'point_value': 50.00, 'exchange': 'CBOT'},
    'ZW': {'tick_size': 0.25, 'tick_value': 12.50, 'point_value': 50.00, 'exchange': 'CBOT'},
}


def get_futures_spec(symbol: str) -> dict:
    """Get futures specification for a symbol. Returns default if not found."""
    # Strip exchange prefix first (e.g., "CME_MINI:NQ1!" -> "NQ1!", "COMEX:MGC1!" -> "MGC1!")
    clean = symbol.upper()
    if ':' in clean:
        clean = clean.split(':')[-1]
    # Strip continuous contract markers (e.g., "NQ1!" -> "NQ", "NQ1!1!" -> "NQ")
    clean = clean.replace('1!', '').replace('!', '')
    # Remove trailing digits for contract months (e.g., "MGCJ2026" -> "MGCJ")
    clean_symbol = ''.join(c for c in clean if c.isalpha())

    # Try exact match first
    if clean_symbol in FUTURES_SPECS:
        return FUTURES_SPECS[clean_symbol]

    # Try prefix matching (longest key first so MNQ matches before NQ)
    for key in sorted(FUTURES_SPECS.keys(), key=len, reverse=True):
        if clean_symbol.startswith(key) or key.startswith(clean_symbol):
            return FUTURES_SPECS[key]

    # Default spec — $1/point (safe fallback, comment and value now match)
    logger.warning(f"Unknown futures symbol: {symbol} (cleaned: {clean_symbol}), using default $1/point")
    return {'tick_size': 0.01, 'tick_value': 1.00, 'point_value': 1.00, 'exchange': 'UNKNOWN'}


def calculate_pnl(symbol: str, entry_price: float, exit_price: float, quantity: int, side: str) -> float:
    """Calculate P&L in dollars for a futures trade."""
    spec = get_futures_spec(symbol)
    point_value = spec['point_value']

    if side.upper() in ['LONG', 'BUY']:
        points = exit_price - entry_price
    else:  # SHORT, SELL
        points = entry_price - exit_price

    return points * point_value * quantity


def get_tradingview_session() -> Optional[dict]:
    """
    Get TradingView session cookies from database.
    Returns dict with 'sessionid' and 'sessionid_sign', or None.
    """
    try:
        # Check for PostgreSQL (Railway)
        database_url = os.environ.get('DATABASE_URL')

        if database_url:
            import psycopg2
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tradingview_session FROM accounts
                WHERE tradingview_session IS NOT NULL
                AND tradingview_session != ''
                LIMIT 1
            ''')
        else:
            conn = sqlite3.connect('just_trades.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT tradingview_session FROM accounts
                WHERE tradingview_session IS NOT NULL
                AND tradingview_session != ''
                LIMIT 1
            ''')

        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            session_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            if session_data.get('sessionid'):
                logger.info(f"✅ Found TradingView session cookies")
                return session_data

        logger.warning("⚠️ No TradingView session found - using public data (delayed)")
        return None

    except Exception as e:
        logger.error(f"Error getting TradingView session: {e}")
        return None


def get_tradingview_auth_token(session_data: dict) -> Optional[str]:
    """
    Get JWT auth token from TradingView chart page using session cookies.
    This is required for premium WebSocket data.
    """
    try:
        import requests
        import re

        cookies = {
            'sessionid': session_data.get('sessionid'),
            'sessionid_sign': session_data.get('sessionid_sign', '')
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        logger.info("🔑 Fetching TradingView auth token...")
        r = requests.get('https://www.tradingview.com/chart/', cookies=cookies, headers=headers, timeout=15)

        if r.status_code != 200:
            logger.error(f"Failed to fetch chart page: {r.status_code}")
            return None

        # Extract JWT auth token from HTML
        auth_match = re.search(r'"auth_token":"([^"]+)"', r.text)
        if auth_match:
            auth_token = auth_match.group(1)
            logger.info(f"✅ Got TradingView JWT auth token")
            return auth_token

        logger.warning("⚠️ Could not find auth_token in chart page")
        return None

    except Exception as e:
        logger.error(f"Error getting auth token: {e}")
        return None

class TradingViewTicker:
    """
    TradingView WebSocket ticker for real-time price data
    Based on reverse-engineered TradingView WebSocket protocol
    """

    # Stale data threshold (60 seconds without updates = stale)
    STALE_THRESHOLD_SECONDS = 60
    # Health check interval (30 seconds)
    HEALTH_CHECK_INTERVAL = 30

    def __init__(self, symbols: list = None, auth_token: str = None):
        self.symbols = symbols or DEFAULT_SYMBOLS
        self.ws = None
        self.session_id = self._generate_session()
        self.chart_session = self._generate_session("cs_")
        self.prices: Dict[str, dict] = {}
        self.callbacks: list = []
        self.running = False
        self.connected = False
        self.lock = threading.Lock()
        self.last_update_time = 0
        self.reconnect_count = 0
        self.health_thread = None
        # Auth token for premium data - get JWT from TradingView
        self.auth_token = auth_token or self._get_auth_token() or "unauthorized_user_token"
        self.is_premium = self.auth_token != "unauthorized_user_token"

    def _get_auth_token(self) -> Optional[str]:
        """Get JWT auth token from TradingView using stored session cookies."""
        session_data = get_tradingview_session()
        if session_data:
            return get_tradingview_auth_token(session_data)
        return None

    def _generate_session(self, prefix: str = "qs_") -> str:
        """Generate random session ID"""
        chars = string.ascii_lowercase + string.digits
        return prefix + ''.join(random.choice(chars) for _ in range(12))

    def _create_message(self, func: str, params: list) -> str:
        """Create TradingView protocol message"""
        return json.dumps({"m": func, "p": params})

    def _send_message(self, func: str, params: list):
        """Send message to TradingView WebSocket"""
        if self.ws:
            msg = "~m~" + str(len(self._create_message(func, params))) + "~m~" + self._create_message(func, params)
            try:
                self.ws.send(msg)
            except Exception as e:
                logger.error(f"Error sending message: {e}")

    def _parse_message(self, message: str) -> list:
        """Parse TradingView protocol message"""
        results = []
        pattern = re.compile(r'~m~(\d+)~m~')

        pos = 0
        while pos < len(message):
            match = pattern.match(message, pos)
            if match:
                length = int(match.group(1))
                pos = match.end()
                data = message[pos:pos + length]
                pos += length

                if data.startswith('{'):
                    try:
                        results.append(json.loads(data))
                    except:
                        pass
            else:
                break

        return results

    def _on_message(self, ws, message):
        """Handle incoming WebSocket message"""
        # Handle TradingView application-level heartbeats (can be anywhere in message)
        # Format: ~m~X~m~~h~Y where X is length and Y is the heartbeat number
        heartbeat_pattern = re.compile(r'~m~\d+~m~~h~\d+')
        heartbeats = heartbeat_pattern.findall(message)
        for hb in heartbeats:
            try:
                ws.send(hb)
                logger.debug(f"💓 Heartbeat responded: {hb}")
            except Exception as e:
                logger.error(f"Failed to send heartbeat response: {e}")

        parsed = self._parse_message(message)

        for data in parsed:
            if isinstance(data, dict) and data.get('m') == 'qsd':
                # Quote data update
                try:
                    params = data.get('p', [])
                    if len(params) >= 2:
                        symbol_data = params[1]
                        symbol = symbol_data.get('n', '')
                        values = symbol_data.get('v', {})

                        if values:
                            with self.lock:
                                self.prices[symbol] = {
                                    'symbol': symbol,
                                    'last_price': values.get('lp'),
                                    'bid': values.get('bid'),
                                    'ask': values.get('ask'),
                                    'volume': values.get('volume'),
                                    'change': values.get('ch'),
                                    'change_percent': values.get('chp'),
                                    'high': values.get('high_price'),
                                    'low': values.get('low_price'),
                                    'open': values.get('open_price'),
                                    'prev_close': values.get('prev_close_price'),
                                    'timestamp': datetime.now().isoformat(),
                                    'update_time': time.time()
                                }

                            # Update last update time
                            self.last_update_time = time.time()

                            # Call registered callbacks
                            for callback in self.callbacks:
                                try:
                                    callback(symbol, self.prices[symbol])
                                except Exception as e:
                                    logger.error(f"Callback error: {e}")

                except Exception as e:
                    logger.error(f"Error parsing quote data: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket error"""
        logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False

        # Attempt reconnect
        if self.running:
            logger.info("Attempting reconnect in 5 seconds...")
            time.sleep(5)
            self._connect()

    def _on_open(self, ws):
        """Handle WebSocket connection open"""
        if self.is_premium:
            logger.info("🚀 WebSocket connected to TradingView with PREMIUM auth (~100ms delay)")
        else:
            logger.info("WebSocket connected to TradingView with PUBLIC auth (delayed data)")
        self.connected = True

        # Set auth token - premium sessionid for real-time, or unauthorized for delayed
        self._send_message("set_auth_token", [self.auth_token])

        # Create quote session
        self._send_message("quote_create_session", [self.session_id])

        # Set fields we want to receive
        self._send_message("quote_set_fields", [
            self.session_id,
            "lp", "bid", "ask", "volume", "ch", "chp",
            "high_price", "low_price", "open_price", "prev_close_price"
        ])

        # Add symbols to quote session
        for symbol in self.symbols:
            logger.info(f"Subscribing to {symbol}")
            self._send_message("quote_add_symbols", [self.session_id, symbol])

    def _connect(self):
        """Establish WebSocket connection"""
        self.ws = websocket.WebSocketApp(
            TV_WS_URL,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )

        # Run in thread with keepalive pings
        wst = threading.Thread(target=lambda: self.ws.run_forever(ping_interval=25, ping_timeout=10))
        wst.daemon = True
        wst.start()

    def _health_monitor(self):
        """Monitor connection health and force reconnect if stale"""
        logger.info("📡 TradingView health monitor started")

        while self.running:
            time.sleep(self.HEALTH_CHECK_INTERVAL)

            if not self.running:
                break

            current_time = time.time()
            seconds_since_update = current_time - self.last_update_time if self.last_update_time else 999

            if seconds_since_update > self.STALE_THRESHOLD_SECONDS:
                logger.warning(f"⚠️ TradingView data stale ({seconds_since_update:.0f}s since last update) - forcing reconnect")
                self.reconnect_count += 1

                # Force close existing connection
                if self.ws:
                    try:
                        self.ws.close()
                    except:
                        pass

                # Generate new session IDs for fresh start
                self.session_id = self._generate_session()
                self.chart_session = self._generate_session("cs_")

                # Refresh auth token (JWT expires, need to get fresh one)
                new_token = self._get_auth_token()
                if new_token:
                    self.auth_token = new_token
                    self.is_premium = True
                    logger.info("🔄 Refreshed TradingView JWT auth token")

                # Reconnect
                self._connect()
                logger.info(f"🔄 TradingView reconnect attempt #{self.reconnect_count}")

                # Wait a bit before next check
                time.sleep(10)
            elif self.connected:
                logger.debug(f"✅ TradingView healthy - last update {seconds_since_update:.0f}s ago")

        logger.info("📡 TradingView health monitor stopped")

    def start(self):
        """Start the ticker"""
        if self.running:
            return

        self.running = True
        self.last_update_time = time.time()  # Initialize to avoid immediate stale detection
        if self.is_premium:
            logger.info(f"🚀 Starting TradingView PREMIUM ticker for {len(self.symbols)} symbols (~100ms delay)")
        else:
            logger.info(f"Starting TradingView PUBLIC ticker for {len(self.symbols)} symbols (delayed data)")
        self._connect()

        # Start health monitor thread
        self.health_thread = threading.Thread(target=self._health_monitor, daemon=True)
        self.health_thread.start()

    def stop(self):
        """Stop the ticker"""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("TradingView ticker stopped")

    def add_callback(self, callback: Callable):
        """Add callback for price updates"""
        self.callbacks.append(callback)

    def get_price(self, symbol: str) -> Optional[dict]:
        """Get current price for symbol"""
        with self.lock:
            return self.prices.get(symbol)

    def get_all_prices(self) -> Dict[str, dict]:
        """Get all current prices"""
        with self.lock:
            return dict(self.prices)

    def add_symbol(self, symbol: str):
        """Add symbol to track"""
        if symbol not in self.symbols:
            self.symbols.append(symbol)
            if self.connected:
                self._send_message("quote_add_symbols", [self.session_id, symbol])
                logger.info(f"Added symbol: {symbol}")


class PaperTradingEngine:
    """
    Paper trading engine that tracks theoretical trades using real-time prices.
    Uses PostgreSQL on Railway, SQLite locally.
    """

    def __init__(self, db_path: str = "paper_trades.db"):
        self.db_path = db_path
        self.positions: Dict[str, dict] = {}  # {recorder_id: {symbol: position}}
        self.current_prices: Dict[str, dict] = {}

        # Check for PostgreSQL (Railway)
        import os
        self.database_url = os.environ.get('DATABASE_URL')
        self.use_postgres = bool(self.database_url)

        if self.use_postgres:
            logger.info("Paper trading using PostgreSQL (Railway)")
        else:
            logger.info("Paper trading using SQLite (local)")

        self._init_db()
        self._load_positions()

    def _get_connection(self):
        """Get database connection (PostgreSQL or SQLite)"""
        if self.use_postgres:
            try:
                import psycopg2
                return psycopg2.connect(self.database_url)
            except ImportError:
                logger.error("psycopg2 not available, falling back to SQLite")
                self.use_postgres = False
                return sqlite3.connect(self.db_path)
        else:
            return sqlite3.connect(self.db_path)

    def _get_placeholder(self):
        """Get SQL placeholder for current database"""
        return '%s' if self.use_postgres else '?'

    def _init_db(self):
        """Initialize database tables"""
        conn = self._get_connection()
        cursor = conn.cursor()

        ph = self._get_placeholder()

        if self.use_postgres:
            # PostgreSQL syntax
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id SERIAL PRIMARY KEY,
                    recorder_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    unrealized_pnl REAL DEFAULT 0,
                    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    status TEXT DEFAULT 'open'
                )
            ''')

            # Create unique index if not exists
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS paper_positions_unique_idx
                ON paper_positions (recorder_id, symbol) WHERE status = 'open'
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id SERIAL PRIMARY KEY,
                    recorder_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    pnl REAL,
                    opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    status TEXT DEFAULT 'open'
                )
            ''')
        else:
            # SQLite syntax
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorder_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL,
                    unrealized_pnl REAL DEFAULT 0,
                    opened_at TEXT NOT NULL,
                    updated_at TEXT,
                    status TEXT DEFAULT 'open',
                    UNIQUE(recorder_id, symbol, status)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS paper_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorder_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    pnl REAL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    status TEXT DEFAULT 'open'
                )
            ''')

        conn.commit()
        conn.close()
        logger.info(f"Paper trading database initialized ({'PostgreSQL' if self.use_postgres else 'SQLite'})")

    def _load_positions(self):
        """Load open positions from database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT recorder_id, symbol, side, quantity, entry_price
                FROM paper_positions WHERE status = 'open'
            ''')

            for row in cursor.fetchall():
                recorder_id, symbol, side, quantity, entry_price = row
                if recorder_id not in self.positions:
                    self.positions[recorder_id] = {}
                self.positions[recorder_id][symbol] = {
                    'side': side,
                    'quantity': quantity,
                    'entry_price': entry_price,
                    'unrealized_pnl': 0
                }

            conn.close()
            logger.info(f"Loaded {len(self.positions)} recorder positions from {'PostgreSQL' if self.use_postgres else 'SQLite'}")
        except Exception as e:
            logger.error(f"Error loading positions: {e}")

    def update_price(self, symbol: str, price_data: dict):
        """Update price and recalculate P&L for all positions"""
        self.current_prices[symbol] = price_data

        # Update P&L for all positions with this symbol
        for recorder_id, positions in self.positions.items():
            if symbol in positions:
                pos = positions[symbol]
                current_price = price_data.get('last_price', 0)

                if current_price and pos['entry_price']:
                    # Use proper futures P&L calculation
                    pnl = calculate_pnl(symbol, pos['entry_price'], current_price, pos['quantity'], pos['side'])
                    pos['unrealized_pnl'] = pnl
                    pos['current_price'] = current_price

    def open_position(self, recorder_id: int, symbol: str, side: str, quantity: float, entry_price: float = None):
        """Open a new paper position"""
        # Use current market price if not specified
        if entry_price is None:
            if symbol in self.current_prices:
                price_data = self.current_prices[symbol]
                entry_price = price_data.get('ask') if side.upper() == 'LONG' else price_data.get('bid')
                if not entry_price:
                    entry_price = price_data.get('last_price')

        if not entry_price:
            logger.error(f"No price available for {symbol}")
            return None

        # Store in memory
        if recorder_id not in self.positions:
            self.positions[recorder_id] = {}

        self.positions[recorder_id][symbol] = {
            'side': side.upper(),
            'quantity': quantity,
            'entry_price': entry_price,
            'unrealized_pnl': 0,
            'current_price': entry_price
        }

        # Store in database
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()

            now = datetime.now().isoformat()

            if self.use_postgres:
                # PostgreSQL: Delete existing open position first, then insert
                cursor.execute(f'''
                    DELETE FROM paper_positions
                    WHERE recorder_id = {ph} AND symbol = {ph} AND status = 'open'
                ''', (recorder_id, symbol))

                cursor.execute(f'''
                    INSERT INTO paper_positions
                    (recorder_id, symbol, side, quantity, entry_price, current_price, opened_at, updated_at, status)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'open')
                ''', (recorder_id, symbol, side.upper(), quantity, entry_price, entry_price, now, now))
            else:
                # SQLite: Use INSERT OR REPLACE
                cursor.execute(f'''
                    INSERT OR REPLACE INTO paper_positions
                    (recorder_id, symbol, side, quantity, entry_price, current_price, opened_at, updated_at, status)
                    VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'open')
                ''', (recorder_id, symbol, side.upper(), quantity, entry_price, entry_price, now, now))

            cursor.execute(f'''
                INSERT INTO paper_trades
                (recorder_id, symbol, side, quantity, entry_price, opened_at, status)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'open')
            ''', (recorder_id, symbol, side.upper(), quantity, entry_price, now))

            conn.commit()
            conn.close()

            logger.info(f"📊 Opened paper {side} position: {quantity} {symbol} @ {entry_price} for recorder {recorder_id}")
        except Exception as e:
            logger.error(f"Error opening paper position: {e}")

        return {
            'recorder_id': recorder_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'entry_price': entry_price
        }

    def close_position(self, recorder_id: int, symbol: str, exit_price: float = None):
        """Close a paper position"""
        if recorder_id not in self.positions or symbol not in self.positions[recorder_id]:
            logger.warning(f"No open position for recorder {recorder_id} symbol {symbol}")
            return None

        pos = self.positions[recorder_id][symbol]

        # Use current market price if not specified
        if exit_price is None:
            if symbol in self.current_prices:
                price_data = self.current_prices[symbol]
                exit_price = price_data.get('bid') if pos['side'] == 'LONG' else price_data.get('ask')
                if not exit_price:
                    exit_price = price_data.get('last_price')

        if not exit_price:
            exit_price = pos.get('current_price', pos['entry_price'])

        # Calculate final P&L using proper futures point values
        pnl = calculate_pnl(symbol, pos['entry_price'], exit_price, pos['quantity'], pos['side'])

        # Update database
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()

            now = datetime.now().isoformat()

            cursor.execute(f'''
                UPDATE paper_positions SET status = 'closed', updated_at = {ph}
                WHERE recorder_id = {ph} AND symbol = {ph} AND status = 'open'
            ''', (now, recorder_id, symbol))

            # Close each paper_trade individually with its own P&L
            # (batch UPDATE would stamp one P&L on all rows regardless of entry price)
            cursor.execute(f'''
                SELECT id, side, quantity, entry_price FROM paper_trades
                WHERE recorder_id = {ph} AND symbol = {ph} AND status = 'open'
            ''', (recorder_id, symbol))
            open_trades = cursor.fetchall()

            for trade_id, trade_side, trade_qty, trade_entry in open_trades:
                trade_pnl = calculate_pnl(symbol, trade_entry, exit_price, trade_qty, trade_side)
                cursor.execute(f'''
                    UPDATE paper_trades SET exit_price = {ph}, pnl = {ph}, exit_reason = 'signal', closed_at = {ph}, status = 'closed'
                    WHERE id = {ph}
                ''', (exit_price, trade_pnl, now, trade_id))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error closing paper position: {e}")

        # Remove from memory
        del self.positions[recorder_id][symbol]

        logger.info(f"📊 Closed paper position: {symbol} @ {exit_price}, P&L: ${pnl:.2f} for recorder {recorder_id}")

        return {
            'recorder_id': recorder_id,
            'symbol': symbol,
            'side': pos['side'],
            'quantity': pos['quantity'],
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'pnl': pnl
        }

    def get_position(self, recorder_id: int, symbol: str = None) -> dict:
        """Get position(s) for a recorder"""
        if recorder_id not in self.positions:
            return {} if symbol else {}

        if symbol:
            return self.positions[recorder_id].get(symbol, {})

        return self.positions[recorder_id]

    def get_all_positions(self) -> dict:
        """Get all open positions"""
        return dict(self.positions)

    def get_recorder_pnl(self, recorder_id: int) -> dict:
        """Get total P&L for a recorder"""
        if recorder_id not in self.positions:
            return {'unrealized_pnl': 0, 'positions': []}

        total_pnl = 0
        positions_list = []

        for symbol, pos in self.positions[recorder_id].items():
            total_pnl += pos.get('unrealized_pnl', 0)
            positions_list.append({
                'symbol': symbol,
                **pos
            })

        return {
            'recorder_id': recorder_id,
            'unrealized_pnl': total_pnl,
            'positions': positions_list
        }

    def get_trade_history(self, recorder_id: int = None, limit: int = 100) -> list:
        """Get trade history"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()

            if recorder_id:
                cursor.execute(f'''
                    SELECT * FROM paper_trades
                    WHERE recorder_id = {ph}
                    ORDER BY opened_at DESC LIMIT {ph}
                ''', (recorder_id, limit))
            else:
                cursor.execute(f'''
                    SELECT * FROM paper_trades
                    ORDER BY opened_at DESC LIMIT {ph}
                ''', (limit,))

            columns = [desc[0] for desc in cursor.description]
            trades = [dict(zip(columns, row)) for row in cursor.fetchall()]

            conn.close()
            return trades
        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            return []

    def get_chart_data(self, recorder_id: int = None, limit: int = 500) -> dict:
        """Get PnL chart data: cumulative profit + drawdown arrays for Chart.js"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()

            if recorder_id:
                cursor.execute(f'''
                    SELECT pnl, closed_at
                    FROM paper_trades
                    WHERE recorder_id = {ph} AND status = 'closed' AND pnl IS NOT NULL
                    ORDER BY closed_at ASC
                    LIMIT {ph}
                ''', (recorder_id, limit))
            else:
                cursor.execute(f'''
                    SELECT pnl, closed_at
                    FROM paper_trades
                    WHERE status = 'closed' AND pnl IS NOT NULL
                    ORDER BY closed_at ASC
                    LIMIT {ph}
                ''', (limit,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return {'labels': [], 'profit': [], 'drawdown': []}

            labels = []
            profit = []
            drawdown = []
            running_pnl = 0.0
            peak_pnl = 0.0

            for row in rows:
                pnl_val = row[0]
                closed_at = row[1] or ''
                running_pnl += pnl_val

                if running_pnl > peak_pnl:
                    peak_pnl = running_pnl

                dd = peak_pnl - running_pnl

                # Format label from closed_at
                if closed_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(str(closed_at).replace('Z', '+00:00'))
                        labels.append(dt.strftime('%b %d'))
                    except Exception:
                        labels.append(str(closed_at)[:10])
                else:
                    labels.append(f'Trade {len(labels) + 1}')

                profit.append(round(running_pnl, 2))
                drawdown.append(round(-dd, 2))  # Negative for chart display

            return {'labels': labels, 'profit': profit, 'drawdown': drawdown}

        except Exception as e:
            logger.error(f"Error getting chart data: {e}")
            return {'labels': [], 'profit': [], 'drawdown': []}

    def get_trade_history_paginated(self, page: int = 1, per_page: int = 20,
                                     result_filter: str = None, recorder_id: int = None) -> dict:
        """Get paginated trade history with optional win/loss filter."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()

            # Build WHERE clause
            conditions = ["pt.status = 'closed'", "pt.pnl IS NOT NULL"]
            params = []

            if recorder_id:
                conditions.append(f"pt.recorder_id = {ph}")
                params.append(recorder_id)

            if result_filter == 'win':
                conditions.append("pt.pnl >= 0")
            elif result_filter == 'loss':
                conditions.append("pt.pnl < 0")

            where_clause = ' AND '.join(conditions)

            # Count total
            cursor.execute(f"SELECT COUNT(*) FROM paper_trades pt WHERE {where_clause}", tuple(params))
            total = cursor.fetchone()[0]

            total_pages = max(1, (total + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * per_page

            # Fetch trades - LEFT JOIN recorders for name
            cursor.execute(f'''
                SELECT pt.id, pt.recorder_id, pt.symbol, pt.side, pt.quantity,
                       pt.entry_price, pt.exit_price, pt.pnl, pt.opened_at, pt.closed_at,
                       pt.status
                FROM paper_trades pt
                WHERE {where_clause}
                ORDER BY pt.closed_at DESC
                LIMIT {ph} OFFSET {ph}
            ''', tuple(params) + (per_page, offset))

            rows = cursor.fetchall()
            conn.close()

            trades = []
            for row in rows:
                pnl = row[7] or 0
                if pnl > 0:
                    status = 'WIN'
                elif pnl < 0:
                    status = 'LOSS'
                else:
                    status = 'FLAT'

                trades.append({
                    'id': row[0],
                    'recorder_id': row[1],
                    'symbol': row[2],
                    'side': row[3],
                    'quantity': row[4],
                    'entry_price': row[5],
                    'exit_price': row[6],
                    'pnl': pnl,
                    'opened_at': str(row[8]) if row[8] else None,
                    'closed_at': str(row[9]) if row[9] else None,
                    'trade_status': row[10],
                    'result_status': status,
                })

            return {
                'trades': trades,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_pages': total_pages,
                    'total': total,
                    'has_prev': page > 1,
                    'has_next': page < total_pages,
                }
            }

        except Exception as e:
            logger.error(f"Error getting paginated trade history: {e}")
            return {
                'trades': [],
                'pagination': {'page': 1, 'per_page': per_page, 'total_pages': 0, 'total': 0, 'has_prev': False, 'has_next': False}
            }

    def get_analytics(self, recorder_id: int = None) -> dict:
        """
        Get comprehensive trading analytics.
        If recorder_id is provided, returns analytics for that recorder only.
        Otherwise returns analytics for all trades.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()

            # Get all closed trades
            if recorder_id:
                cursor.execute(f'''
                    SELECT symbol, side, quantity, entry_price, exit_price, pnl, opened_at, closed_at
                    FROM paper_trades
                    WHERE recorder_id = {ph} AND status = 'closed' AND pnl IS NOT NULL
                    ORDER BY closed_at ASC
                ''', (recorder_id,))
            else:
                cursor.execute('''
                    SELECT symbol, side, quantity, entry_price, exit_price, pnl, opened_at, closed_at
                    FROM paper_trades
                    WHERE status = 'closed' AND pnl IS NOT NULL
                    ORDER BY closed_at ASC
                ''')

            trades = cursor.fetchall()
            conn.close()

            if not trades:
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0,
                    'total_pnl': 0,
                    'gross_profit': 0,
                    'gross_loss': 0,
                    'profit_factor': 0,
                    'average_win': 0,
                    'average_loss': 0,
                    'largest_win': 0,
                    'largest_loss': 0,
                    'max_drawdown': 0,
                    'max_drawdown_pct': 0,
                    'current_drawdown': 0,
                    'average_trade': 0,
                    'expectancy': 0,
                }

            # Calculate analytics
            pnls = [t[5] for t in trades]  # pnl is index 5
            winners = [p for p in pnls if p > 0]
            losers = [p for p in pnls if p < 0]

            total_trades = len(trades)
            winning_trades = len(winners)
            losing_trades = len(losers)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            total_pnl = sum(pnls)
            gross_profit = sum(winners) if winners else 0
            gross_loss = abs(sum(losers)) if losers else 0
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf') if gross_profit > 0 else 0

            average_win = (gross_profit / winning_trades) if winning_trades > 0 else 0
            average_loss = (gross_loss / losing_trades) if losing_trades > 0 else 0
            largest_win = max(winners) if winners else 0
            largest_loss = min(losers) if losers else 0  # Most negative

            average_trade = total_pnl / total_trades if total_trades > 0 else 0

            # Expectancy = (Win% * Avg Win) - (Loss% * Avg Loss)
            loss_rate = losing_trades / total_trades if total_trades > 0 else 0
            expectancy = ((win_rate / 100) * average_win) - (loss_rate * average_loss)

            # Calculate drawdown from equity curve
            equity_curve = []
            running_pnl = 0
            peak_pnl = 0
            max_dd = 0
            max_dd_pct = 0

            for pnl in pnls:
                running_pnl += pnl
                equity_curve.append(running_pnl)

                if running_pnl > peak_pnl:
                    peak_pnl = running_pnl

                dd = peak_pnl - running_pnl
                if dd > max_dd:
                    max_dd = dd
                    # Calculate percentage drawdown (from peak)
                    if peak_pnl > 0:
                        max_dd_pct = (dd / peak_pnl) * 100

            current_dd = peak_pnl - running_pnl if running_pnl < peak_pnl else 0

            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'breakeven_trades': total_trades - winning_trades - losing_trades,
                'win_rate': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2),
                'gross_profit': round(gross_profit, 2),
                'gross_loss': round(gross_loss, 2),
                'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 'Infinite',
                'average_win': round(average_win, 2),
                'average_loss': round(average_loss, 2),
                'largest_win': round(largest_win, 2),
                'largest_loss': round(largest_loss, 2),
                'max_drawdown': round(max_dd, 2),
                'max_drawdown_pct': round(max_dd_pct, 2),
                'current_drawdown': round(current_dd, 2),
                'average_trade': round(average_trade, 2),
                'expectancy': round(expectancy, 2),
                'equity_curve': equity_curve[-100:] if len(equity_curve) > 100 else equity_curve,  # Last 100 points
            }

        except Exception as e:
            logger.error(f"Error calculating analytics: {e}")
            return {'error': str(e)}

    def get_equity_curve(self, recorder_id: int = None, limit: int = 500) -> list:
        """Get equity curve data points for charting."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()

            if recorder_id:
                cursor.execute(f'''
                    SELECT pnl, closed_at, symbol, side
                    FROM paper_trades
                    WHERE recorder_id = {ph} AND status = 'closed' AND pnl IS NOT NULL
                    ORDER BY closed_at ASC
                    LIMIT {ph}
                ''', (recorder_id, limit))
            else:
                cursor.execute(f'''
                    SELECT pnl, closed_at, symbol, side
                    FROM paper_trades
                    WHERE status = 'closed' AND pnl IS NOT NULL
                    ORDER BY closed_at ASC
                    LIMIT {ph}
                ''', (limit,))

            trades = cursor.fetchall()
            conn.close()

            equity_points = []
            running_pnl = 0

            for trade in trades:
                pnl, closed_at, symbol, side = trade
                running_pnl += pnl
                equity_points.append({
                    'timestamp': closed_at,
                    'pnl': round(pnl, 2),
                    'cumulative_pnl': round(running_pnl, 2),
                    'symbol': symbol,
                    'side': side
                })

            return equity_points

        except Exception as e:
            logger.error(f"Error getting equity curve: {e}")
            return []

    def get_daily_pnl(self, recorder_id: int = None, days: int = 30) -> list:
        """Get daily P&L summary for the last N days."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()

            if self.use_postgres:
                date_func = "DATE(closed_at)"
                date_filter = f"closed_at >= CURRENT_DATE - INTERVAL '{days} days'"
            else:
                date_func = "DATE(closed_at)"
                date_filter = f"closed_at >= DATE('now', '-{days} days')"

            if recorder_id:
                cursor.execute(f'''
                    SELECT {date_func} as trade_date,
                           COUNT(*) as trade_count,
                           SUM(pnl) as daily_pnl,
                           SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winners,
                           SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losers
                    FROM paper_trades
                    WHERE recorder_id = {ph} AND status = 'closed' AND pnl IS NOT NULL
                    AND {date_filter}
                    GROUP BY {date_func}
                    ORDER BY trade_date DESC
                ''', (recorder_id,))
            else:
                cursor.execute(f'''
                    SELECT {date_func} as trade_date,
                           COUNT(*) as trade_count,
                           SUM(pnl) as daily_pnl,
                           SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winners,
                           SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losers
                    FROM paper_trades
                    WHERE status = 'closed' AND pnl IS NOT NULL
                    AND {date_filter}
                    GROUP BY {date_func}
                    ORDER BY trade_date DESC
                ''')

            rows = cursor.fetchall()
            conn.close()

            daily_data = []
            for row in rows:
                trade_date, trade_count, daily_pnl, winners, losers = row
                daily_data.append({
                    'date': str(trade_date),
                    'trade_count': trade_count,
                    'pnl': round(daily_pnl, 2) if daily_pnl else 0,
                    'winners': winners or 0,
                    'losers': losers or 0,
                    'win_rate': round((winners / trade_count * 100), 1) if trade_count > 0 else 0
                })

            return daily_data

        except Exception as e:
            logger.error(f"Error getting daily P&L: {e}")
            return []

    def get_symbol_stats(self, recorder_id: int = None) -> list:
        """Get P&L breakdown by symbol."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            ph = self._get_placeholder()

            if recorder_id:
                cursor.execute(f'''
                    SELECT symbol,
                           COUNT(*) as trade_count,
                           SUM(pnl) as total_pnl,
                           SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winners,
                           SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losers,
                           AVG(pnl) as avg_pnl,
                           MAX(pnl) as best_trade,
                           MIN(pnl) as worst_trade
                    FROM paper_trades
                    WHERE recorder_id = {ph} AND status = 'closed' AND pnl IS NOT NULL
                    GROUP BY symbol
                    ORDER BY total_pnl DESC
                ''', (recorder_id,))
            else:
                cursor.execute('''
                    SELECT symbol,
                           COUNT(*) as trade_count,
                           SUM(pnl) as total_pnl,
                           SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winners,
                           SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losers,
                           AVG(pnl) as avg_pnl,
                           MAX(pnl) as best_trade,
                           MIN(pnl) as worst_trade
                    FROM paper_trades
                    WHERE status = 'closed' AND pnl IS NOT NULL
                    GROUP BY symbol
                    ORDER BY total_pnl DESC
                ''')

            rows = cursor.fetchall()
            conn.close()

            symbol_stats = []
            for row in rows:
                symbol, trade_count, total_pnl, winners, losers, avg_pnl, best, worst = row
                symbol_stats.append({
                    'symbol': symbol,
                    'trade_count': trade_count,
                    'total_pnl': round(total_pnl, 2) if total_pnl else 0,
                    'winners': winners or 0,
                    'losers': losers or 0,
                    'win_rate': round((winners / trade_count * 100), 1) if trade_count > 0 else 0,
                    'avg_pnl': round(avg_pnl, 2) if avg_pnl else 0,
                    'best_trade': round(best, 2) if best else 0,
                    'worst_trade': round(worst, 2) if worst else 0
                })

            return symbol_stats

        except Exception as e:
            logger.error(f"Error getting symbol stats: {e}")
            return []


# Global instances
_ticker: Optional[TradingViewTicker] = None
_paper_engine: Optional[PaperTradingEngine] = None


def get_ticker() -> TradingViewTicker:
    """Get or create the global ticker instance"""
    global _ticker
    if _ticker is None:
        _ticker = TradingViewTicker(DEFAULT_SYMBOLS)
    return _ticker


def get_paper_engine() -> PaperTradingEngine:
    """Get or create the global paper trading engine"""
    global _paper_engine
    if _paper_engine is None:
        _paper_engine = PaperTradingEngine()
    return _paper_engine


def start_price_service(symbols: list = None, on_price_update: Callable = None):
    """Start the price service with optional custom symbols and callback"""
    ticker = get_ticker()
    paper_engine = get_paper_engine()

    if symbols:
        for symbol in symbols:
            ticker.add_symbol(symbol)

    # Register paper engine price updates
    def price_callback(symbol: str, price_data: dict):
        paper_engine.update_price(symbol, price_data)
        if on_price_update:
            on_price_update(symbol, price_data)

    ticker.add_callback(price_callback)
    ticker.start()

    return ticker, paper_engine


# Standalone test
if __name__ == "__main__":
    def print_price(symbol: str, data: dict):
        price = data.get('last_price', 'N/A')
        change = data.get('change_percent', 0)
        sign = '+' if change and change >= 0 else ''
        print(f"{symbol}: ${price} ({sign}{change:.2f}%)")

    print("Starting TradingView Price Service...")
    print("Symbols: NQ, ES futures")
    print("-" * 50)

    ticker, paper_engine = start_price_service(on_price_update=print_price)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        ticker.stop()
