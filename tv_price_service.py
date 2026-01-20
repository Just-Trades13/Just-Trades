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

class TradingViewTicker:
    """
    TradingView WebSocket ticker for real-time price data
    Based on reverse-engineered TradingView WebSocket protocol
    """

    def __init__(self, symbols: list = None):
        self.symbols = symbols or DEFAULT_SYMBOLS
        self.ws = None
        self.session_id = self._generate_session()
        self.chart_session = self._generate_session("cs_")
        self.prices: Dict[str, dict] = {}
        self.callbacks: list = []
        self.running = False
        self.connected = False
        self.lock = threading.Lock()

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
        logger.info("WebSocket connected to TradingView")
        self.connected = True

        # Set auth token (empty for public data)
        self._send_message("set_auth_token", ["unauthorized_user_token"])

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

    def start(self):
        """Start the ticker"""
        if self.running:
            return

        self.running = True
        logger.info(f"Starting TradingView ticker for {len(self.symbols)} symbols")
        self._connect()

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
    Paper trading engine that tracks theoretical trades using real-time prices
    """

    def __init__(self, db_path: str = "paper_trades.db"):
        self.db_path = db_path
        self.positions: Dict[str, dict] = {}  # {recorder_id: {symbol: position}}
        self.current_prices: Dict[str, dict] = {}
        self._init_db()
        self._load_positions()

    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Paper positions table
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

        # Paper trades history
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

        # Price history for analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                bid REAL,
                ask REAL,
                volume INTEGER,
                timestamp TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Paper trading database initialized")

    def _load_positions(self):
        """Load open positions from database"""
        conn = sqlite3.connect(self.db_path)
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
        logger.info(f"Loaded {len(self.positions)} recorder positions")

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT OR REPLACE INTO paper_positions
            (recorder_id, symbol, side, quantity, entry_price, current_price, opened_at, updated_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
        ''', (recorder_id, symbol, side.upper(), quantity, entry_price, entry_price, now, now))

        cursor.execute('''
            INSERT INTO paper_trades
            (recorder_id, symbol, side, quantity, entry_price, opened_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'open')
        ''', (recorder_id, symbol, side.upper(), quantity, entry_price, now))

        conn.commit()
        conn.close()

        logger.info(f"Opened paper {side} position: {quantity} {symbol} @ {entry_price} for recorder {recorder_id}")

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute('''
            UPDATE paper_positions SET status = 'closed', updated_at = ?
            WHERE recorder_id = ? AND symbol = ? AND status = 'open'
        ''', (now, recorder_id, symbol))

        cursor.execute('''
            UPDATE paper_trades SET exit_price = ?, pnl = ?, closed_at = ?, status = 'closed'
            WHERE recorder_id = ? AND symbol = ? AND status = 'open'
        ''', (exit_price, pnl, now, recorder_id, symbol))

        conn.commit()
        conn.close()

        # Remove from memory
        del self.positions[recorder_id][symbol]

        logger.info(f"Closed paper position: {symbol} @ {exit_price}, P&L: {pnl:.2f} for recorder {recorder_id}")

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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if recorder_id:
            cursor.execute('''
                SELECT * FROM paper_trades
                WHERE recorder_id = ?
                ORDER BY opened_at DESC LIMIT ?
            ''', (recorder_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM paper_trades
                ORDER BY opened_at DESC LIMIT ?
            ''', (limit,))

        columns = [desc[0] for desc in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return trades


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
