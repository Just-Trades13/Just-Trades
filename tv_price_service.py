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
    "CME_MINI:ES1!",   # E-mini S&P 500
    "CME_MINI:NQ1!",   # E-mini Nasdaq 100
]


def get_tradingview_session() -> Optional[str]:
    """
    Get TradingView session token from database.
    Returns the sessionid for premium data access, or None for public data.
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
            sessionid = session_data.get('sessionid')
            if sessionid:
                logger.info(f"✅ Found TradingView premium session")
                return sessionid

        logger.warning("⚠️ No TradingView session found - using public data (delayed)")
        return None

    except Exception as e:
        logger.error(f"Error getting TradingView session: {e}")
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
        # Auth token for premium data - get from database if not provided
        self.auth_token = auth_token or get_tradingview_session() or "unauthorized_user_token"
        self.is_premium = self.auth_token != "unauthorized_user_token"

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
        # Handle ping
        if message.startswith('~m~') and '~h~' in message:
            # Respond to heartbeat
            ws.send(message)
            return

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

        # Run in thread
        wst = threading.Thread(target=self.ws.run_forever)
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

                # Refresh auth token in case it was updated
                new_token = get_tradingview_session()
                if new_token:
                    self.auth_token = new_token
                    self.is_premium = True
                    logger.info("🔄 Refreshed TradingView auth token")

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
                    if pos['side'].upper() == 'LONG':
                        pnl = (current_price - pos['entry_price']) * pos['quantity']
                    else:  # SHORT
                        pnl = (pos['entry_price'] - current_price) * pos['quantity']

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

        # Calculate final P&L
        if pos['side'] == 'LONG':
            pnl = (exit_price - pos['entry_price']) * pos['quantity']
        else:
            pnl = (pos['entry_price'] - exit_price) * pos['quantity']

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

            cursor.execute(f'''
                UPDATE paper_trades SET exit_price = {ph}, pnl = {ph}, closed_at = {ph}, status = 'closed'
                WHERE recorder_id = {ph} AND symbol = {ph} AND status = 'open'
            ''', (exit_price, pnl, now, recorder_id, symbol))

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
