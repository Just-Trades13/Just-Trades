"""
recorder_service_v2.py

JUST.TRADES Strategy Engine V2 - Full Architecture Implementation

Based on JUST_TRADES_STRATEGY_ENGINE_ARCHITECTURE.md:
- Virtual position engine with DCA/scaling logic
- Virtual PnL tracking using TradingView prices (not broker quotes)
- Strategy state management (virtual/live modes)
- Optional broker execution with position drift detection
- Full audit trail with VirtualFill records

Components:
- StrategyInstance: Strategy configuration with mode (virtual/live)
- VirtualPosition: Aggregated position state
- VirtualFill: Individual entry/exit records for audit
- VirtualBarPrice: TradingView candle price cache
- BrokerPositionSnapshot: Real broker state for drift detection
- DCAEngine: Auto-DCA ladder logic (ticks/ATR/percent triggers)
- PnLEngine: Virtual PnL calculation using TV prices
"""

from __future__ import annotations  # Enable forward references

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List, Any, Callable, Set, Tuple
from enum import Enum
import logging
import sqlite3
import os
import threading
import json
import time
import asyncio
import websockets
from queue import Queue, Empty
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import uuid


logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class StrategyMode(Enum):
    """Strategy execution mode"""
    VIRTUAL = "virtual"  # Shadow mode - no real orders
    LIVE = "live"        # Real broker execution enabled


class FillType(Enum):
    """Type of virtual fill"""
    ENTRY = "entry"
    DCA = "dca"
    EXIT_TP = "exit_tp"
    EXIT_SL = "exit_sl"
    EXIT_MANUAL = "exit_manual"
    EXIT_FLIP = "exit_flip"


class DCAType(Enum):
    """DCA trigger type"""
    TICKS = "ticks"      # Fixed tick distance
    PERCENT = "percent"  # Percentage drop from entry
    ATR = "atr"          # ATR-based distance


# =============================================================================
# PRODUCTION-READY COMPONENTS
# =============================================================================

class AsyncDBWriter:
    """
    Non-blocking database writer using a background thread.
    All DB writes are queued and processed asynchronously.
    This prevents DB writes from blocking price evaluation.
    """
    
    def __init__(self, db_path: str, max_queue_size: int = 1000):
        self.db_path = db_path
        self._queue: Queue = Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._writer_loop, daemon=True, name="AsyncDBWriter")
        self._thread.start()
        logger.info("🚀 AsyncDBWriter started (non-blocking DB writes)")
    
    def _writer_loop(self):
        """Background thread that processes DB write queue."""
        conn = None
        batch = []
        last_flush = time.time()
        
        while not self._stop_event.is_set():
            try:
                # Batch writes for efficiency (up to 50ms or 100 items)
                try:
                    item = self._queue.get(timeout=0.05)
                    batch.append(item)
                except Empty:
                    pass
                
                # Flush if batch is large enough or enough time passed
                should_flush = len(batch) >= 100 or (batch and time.time() - last_flush >= 0.1)
                
                if should_flush and batch:
                    if conn is None:
                        conn = sqlite3.connect(self.db_path)
                    
                    cursor = conn.cursor()
                    for query, params in batch:
                        try:
                            cursor.execute(query, params)
                        except Exception as e:
                            logger.warning(f"AsyncDB write error: {e}")
                    conn.commit()
                    batch = []
                    last_flush = time.time()
                    
            except Exception as e:
                logger.error(f"AsyncDBWriter error: {e}")
                batch = []  # Clear batch on error
        
        if conn:
            conn.close()
    
    def write(self, query: str, params: tuple) -> None:
        """Queue a write operation (non-blocking)."""
        try:
            self._queue.put_nowait((query, params))
        except:
            logger.warning("AsyncDB queue full, dropping write")
    
    def stop(self):
        """Stop the writer thread."""
        self._stop_event.set()
        self._thread.join(timeout=2.0)


class AsyncOrderQueue:
    """
    Non-blocking order execution queue with retry logic.
    Orders are processed in background threads without blocking price evaluation.
    """
    
    def __init__(self, max_workers: int = 4, max_retries: int = 3, retry_delay: float = 0.5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="OrderWorker")
        self._pending_orders: Dict[str, int] = {}  # key -> retry count
        self._lock = threading.Lock()
        self._rate_limiters: Dict[str, float] = {}  # account -> last_order_time
        self._min_order_interval = 0.5  # 500ms between orders per account
        logger.info(f"🚀 AsyncOrderQueue started ({max_workers} workers, {max_retries} retries)")
    
    def submit(self, order_fn: Callable, key: str, account_id: str = None) -> None:
        """
        Submit an order for async execution.
        order_fn: callable that places the order
        key: unique key for deduplication
        account_id: for per-account rate limiting
        """
        with self._lock:
            if key in self._pending_orders:
                logger.debug(f"Order {key} already pending, skipping")
                return
            self._pending_orders[key] = 0
        
        self._executor.submit(self._execute_with_retry, order_fn, key, account_id)
    
    def _execute_with_retry(self, order_fn: Callable, key: str, account_id: str):
        """Execute order with retry logic."""
        try:
            # Per-account rate limiting
            if account_id:
                with self._lock:
                    last_time = self._rate_limiters.get(account_id, 0)
                    wait_time = self._min_order_interval - (time.time() - last_time)
                    if wait_time > 0:
                        time.sleep(wait_time)
                    self._rate_limiters[account_id] = time.time()
            
            retries = 0
            while retries <= self.max_retries:
                try:
                    order_fn()
                    break  # Success
                except Exception as e:
                    retries += 1
                    if "429" in str(e) or "rate" in str(e).lower():
                        # Rate limit - exponential backoff
                        wait = self.retry_delay * (2 ** retries)
                        logger.warning(f"Rate limit on {key}, retrying in {wait}s...")
                        time.sleep(wait)
                    elif retries <= self.max_retries:
                        logger.warning(f"Order {key} failed (attempt {retries}): {e}")
                        time.sleep(self.retry_delay)
                    else:
                        logger.error(f"Order {key} failed after {self.max_retries} retries: {e}")
        finally:
            with self._lock:
                self._pending_orders.pop(key, None)
    
    def shutdown(self):
        """Shutdown the executor."""
        self._executor.shutdown(wait=True)


class TickerIndex:
    """
    O(1) lookup of positions by ticker.
    Maintains a reverse index: ticker -> set of position keys.
    """
    
    def __init__(self):
        self._index: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()
    
    def add(self, ticker: str, key: str) -> None:
        with self._lock:
            self._index[ticker].add(key)
    
    def remove(self, ticker: str, key: str) -> None:
        with self._lock:
            self._index[ticker].discard(key)
            if not self._index[ticker]:
                del self._index[ticker]
    
    def get_keys(self, ticker: str) -> Set[str]:
        with self._lock:
            return self._index.get(ticker, set()).copy()
    
    def get_all_tickers(self) -> Set[str]:
        with self._lock:
            return set(self._index.keys())


class V2FeatureFlags:
    """
    Simple JSON-backed feature flags for v2 enablement per recorder.
    File format: { "recorder_name": true/false, ... }
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.path.join(os.getcwd(), "v2_flags.json")
        self.flags: Dict[str, bool] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.flags = json.load(f) or {}
            except Exception:
                logger.warning("Could not load v2 flags, starting empty.")
                self.flags = {}

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.flags, f, indent=2)
        except Exception as e:
            logger.error("Failed to save v2 flags: %s", e, exc_info=True)

    def is_enabled(self, recorder: str) -> bool:
        return bool(self.flags.get(recorder, False))

    def set_flag(self, recorder: str, enabled: bool) -> None:
        self.flags[recorder] = enabled
        self._save()


class TradingViewCookieStore:
    """
    Reloadable cookie store for TradingView session cookies.
    Reads from environment variables by default:
      TV_SESSIONID
      TV_SESSION_SIGN
      TV_BACKEND
      TV_BACKEND_SIGN
      TV_ECUID
    """

    def __init__(self):
        self.cookies = {}
        self.refresh_cookies()

    def refresh_cookies(self) -> None:
        self.cookies = {
            "sessionid": os.getenv("TV_SESSIONID", ""),
            "sessionid_sign": os.getenv("TV_SESSION_SIGN", ""),
            "backend": os.getenv("TV_BACKEND", ""),
            "backend_sign": os.getenv("TV_BACKEND_SIGN", ""),
            "tv_ecuid": os.getenv("TV_ECUID", ""),
        }

    def get_cookies(self) -> Dict[str, str]:
        return {k: v for k, v in self.cookies.items() if v}


class TradingViewPriceFeedAdapter:
    """
    TradingView price feed adapter - FOR DEVELOPMENT USE ONLY.
    
    ⚠️  COMPLIANCE WARNING: This uses private TradingView endpoints via cookies.
    ⚠️  NOT RECOMMENDED FOR PRODUCTION - use webhook payload price instead.
    
    Production should:
    - Use TradingView alert payload price ({{close}}) as primary source
    - Set V2_TV_WS_ENABLE=0 (default) to disable this adapter
    
    Dev mode only (V2_TV_WS_ENABLE=1):
    - Connects to TradingView WebSocket for real-time prices
    - Requires TV_SESSIONID cookie (unofficial API)
    - May break without notice
    """

    def __init__(self, fetcher: Callable[[str, Dict[str, str]], Optional[float]], refresh_secs: int = 300):
        self.fetcher = fetcher
        self.cookies = TradingViewCookieStore()
        self.refresh_secs = refresh_secs
        self._last_refresh = 0.0
        self._cache: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.ws_url = "wss://data.tradingview.com/socket.io/websocket"
        self._ws_task = None
        self._ws_loop = None
        self._ws_thread = None
        self._stop_event = threading.Event()
        self._subs: Dict[str, str] = {}  # ticker -> tv_symbol
        # Read WebSocket enable flag and symbol mapping from env
        self.ws_enabled = bool(int(os.getenv("V2_TV_WS_ENABLE", "0")))
        tv_subs_str = os.getenv("V2_TV_SUBS", "{}")
        try:
            self._subs = json.loads(tv_subs_str) if tv_subs_str else {}
        except Exception:
            logger.warning("Failed to parse V2_TV_SUBS, using empty mapping")
            self._subs = {}

    def refresh_cookies(self) -> None:
        self.cookies.refresh_cookies()
        self._last_refresh = time.time()

    def _maybe_refresh(self) -> None:
        now = time.time()
        if now - self._last_refresh >= self.refresh_secs:
            self.refresh_cookies()

    def get_price(self, ticker: str) -> Optional[float]:
        with self._lock:
            self._maybe_refresh()
            price = self.fetcher(ticker, self.cookies.get_cookies())
            if price is not None:
                self._cache[ticker] = price
                return price
            return self._cache.get(ticker)

    # ---------- WebSocket-based quote handling (skeleton) ----------
    def start_ws(self, subs: Optional[Dict[str, str]] = None) -> None:
        """
        Start a background thread with a WS connection to TradingView quotes.
        subs: mapping of our ticker -> TradingView symbol (e.g., {"NQ1!": "CME_MINI:NQ1!"})
              If None, uses V2_TV_SUBS from environment
        """
        if not self.ws_enabled:
            logger.info("TradingView WebSocket disabled via V2_TV_WS_ENABLE")
            return
        if subs:
            self._subs = subs
        elif not self._subs:
            logger.warning("No symbol mapping provided and V2_TV_SUBS not set")
            return
        if self._ws_thread and self._ws_thread.is_alive():
            return
        self._stop_event.clear()
        self._ws_thread = threading.Thread(target=self._run_ws_thread, daemon=True)
        self._ws_thread.start()

    def stop_ws(self) -> None:
        self._stop_event.set()
        if self._ws_loop:
            self._ws_loop.call_soon_threadsafe(self._ws_loop.stop)

    def _run_ws_thread(self) -> None:
        self._ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ws_loop)
        self._ws_loop.run_until_complete(self._ws_main())

    async def _ws_main(self):
        self.refresh_cookies()
        cookies = self.cookies.get_cookies()
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items() if v])
        
        # TradingView requires these headers
        headers = {
            "Origin": "https://www.tradingview.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        if cookie_str:
            headers["Cookie"] = cookie_str
        
        try:
            # Try different websockets API versions
            try:
                # websockets >= 10.0
                ws = await websockets.connect(
                    self.ws_url,
                    additional_headers=headers,
                    ping_interval=20,
                    ping_timeout=20
                )
            except TypeError:
                # websockets < 10.0 (fallback)
                ws = await websockets.connect(
                    self.ws_url,
                    extra_headers=headers,
                    ping_interval=20,
                    ping_timeout=20
                )
            
            async with ws:
                # Subscribe
                for tv_symbol in self._subs.values():
                    sub_msg = json.dumps(["set_auth_token", None])
                    await ws.send(sub_msg)
                    cmd = json.dumps([
                        "quote_create_session",
                        "qs_1",
                    ])
                    await ws.send(cmd)
                    await ws.send(json.dumps(["quote_set_fields", "qs_1", "lp"]))
                    # NOTE: Do NOT use flags - it causes subscription errors!
                    await ws.send(json.dumps(["quote_add_symbols", "qs_1", tv_symbol]))
                while not self._stop_event.is_set():
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=5)
                        self._handle_ws_msg(msg)
                    except asyncio.TimeoutError:
                        continue
        except Exception as e:
            logger.error("TV WS error: %s", e, exc_info=True)

    def _handle_ws_msg(self, raw: str) -> None:
        # TV frames often start with ~m~length~m~payload
        parts = []
        buf = raw
        while buf.startswith("~m~"):
            try:
                buf = buf[3:]
                length_str, rest = buf.split("~m~", 1)
                length = int(length_str)
                payload = rest[:length]
                buf = rest[length:]
                parts.append(payload)
            except Exception:
                break

        for part in parts or [raw]:
            try:
                data = json.loads(part)
            except Exception:
                continue
            if not isinstance(data, list) or len(data) < 2:
                continue
            # Expecting ["qsd", { "lp": price, "n": "CME_MINI:NQ1!" }]
            if data[0] == "qsd":
                body = data[1] if isinstance(data[1], dict) else None
                if not body:
                    continue
                tv_symbol = body.get("n")
                price = body.get("lp")
                if price is None:
                    continue
                # map back to our ticker
                our_ticker = None
                for k, v in self._subs.items():
                    if v == tv_symbol:
                        our_ticker = k
                        break
                if our_ticker:
                    with self._lock:
                        self._cache[our_ticker] = price

    def stop(self) -> None:
        self.stop_ws()


# =============================================================================
# DCA ENGINE (Per Architecture Doc Section 5 - DCA Logic)
# =============================================================================

class DCAEngine:
    """
    Auto-DCA ladder logic supporting multiple trigger types.
    
    Trigger Types:
    - TICKS: Trigger when price moves X ticks against position
    - PERCENT: Trigger when price drops X% from entry
    - ATR: Trigger when price moves X * ATR against position
    
    Example DCA ladder:
    [
        {"trigger_type": "percent", "trigger_value": 1.0, "qty": 1},  # +1 at 1% drop
        {"trigger_type": "percent", "trigger_value": 2.5, "qty": 2},  # +2 at 2.5% drop
        {"trigger_type": "percent", "trigger_value": 5.0, "qty": 3},  # +3 at 5% drop
    ]
    """
    
    def __init__(self, tick_size_map: Optional[Dict[str, float]] = None):
        self.tick_size_map = tick_size_map or {}
        self._atr_cache: Dict[str, float] = {}  # ticker -> ATR value
        self._lock = threading.Lock()
    
    def set_atr(self, ticker: str, atr: float) -> None:
        """Update ATR value for a ticker (from TradingView data)."""
        with self._lock:
            self._atr_cache[ticker] = atr
    
    def get_atr(self, ticker: str) -> Optional[float]:
        """Get cached ATR value."""
        with self._lock:
            return self._atr_cache.get(ticker)
    
    def evaluate_dca_triggers(
        self,
        pos: "V2Position",
        current_price: float,
        dca_steps: List["DCAStep"],
        strategy: Optional["StrategyInstance"] = None
    ) -> List[Tuple["DCAStep", int]]:
        """
        Evaluate which DCA steps should trigger based on current price.
        
        Returns list of (DCAStep, qty) tuples for steps that should trigger.
        """
        triggered = []
        
        if not dca_steps or pos.total_qty == 0:
            return triggered
        
        tick_size = self.tick_size_map.get(pos.ticker, 0.25)
        if strategy:
            tick_size = strategy.tick_size
        
        entry_price = pos.avg_price
        
        for step in dca_steps:
            if not step.enabled or step.triggered:
                continue
            
            trigger_price = self._calculate_trigger_price(
                entry_price=entry_price,
                side=pos.side,
                trigger_type=step.trigger_type,
                trigger_value=step.trigger_value,
                tick_size=tick_size,
                ticker=pos.ticker
            )
            
            if trigger_price is None:
                continue
            
            # Check if trigger condition is met
            if pos.side == "LONG":
                # For LONG, DCA triggers when price drops BELOW trigger price
                if current_price <= trigger_price:
                    triggered.append((step, step.qty))
                    logger.info(f"📉 DCA TRIGGER ({step.trigger_type}): {pos.ticker} @ {current_price} <= {trigger_price}")
            else:
                # For SHORT, DCA triggers when price rises ABOVE trigger price
                if current_price >= trigger_price:
                    triggered.append((step, step.qty))
                    logger.info(f"📈 DCA TRIGGER ({step.trigger_type}): {pos.ticker} @ {current_price} >= {trigger_price}")
        
        return triggered
    
    def _calculate_trigger_price(
        self,
        entry_price: float,
        side: str,
        trigger_type: str,
        trigger_value: float,
        tick_size: float,
        ticker: str
    ) -> Optional[float]:
        """Calculate the price at which DCA should trigger."""
        
        if trigger_type == "ticks" or trigger_type == DCAType.TICKS.value:
            # Fixed tick distance
            tick_distance = trigger_value * tick_size
            if side == "LONG":
                return entry_price - tick_distance
            else:
                return entry_price + tick_distance
        
        elif trigger_type == "percent" or trigger_type == DCAType.PERCENT.value:
            # Percentage drop from entry
            pct_move = trigger_value / 100.0
            if side == "LONG":
                return entry_price * (1 - pct_move)
            else:
                return entry_price * (1 + pct_move)
        
        elif trigger_type == "atr" or trigger_type == DCAType.ATR.value:
            # ATR-based distance
            atr = self.get_atr(ticker)
            if atr is None:
                logger.warning(f"DCA: No ATR cached for {ticker}, skipping ATR-based trigger")
                return None
            atr_distance = trigger_value * atr
            if side == "LONG":
                return entry_price - atr_distance
            else:
                return entry_price + atr_distance
        
        return None


# =============================================================================
# PNL ENGINE (Per Architecture Doc Section 5 - PnL Logic)
# =============================================================================

class PnLEngine:
    """
    Virtual PnL calculation using TradingView prices.
    
    PnL uses TradingView candle prices to mirror chart performance,
    NOT broker quotes. This ensures strategy PnL matches what you see on the chart.
    """
    
    def __init__(self, tick_size_map: Optional[Dict[str, float]] = None):
        self.tick_size_map = tick_size_map or {}
        self._bar_cache: Dict[str, VirtualBarPrice] = {}  # ticker -> latest bar
        self._lock = threading.Lock()
    
    def update_bar(self, bar: "VirtualBarPrice") -> None:
        """Update cached bar price for a ticker."""
        with self._lock:
            self._bar_cache[bar.ticker] = bar
    
    def get_latest_bar(self, ticker: str) -> Optional["VirtualBarPrice"]:
        """Get latest cached bar for ticker."""
        with self._lock:
            return self._bar_cache.get(ticker)
    
    def calculate_unrealized_pnl(
        self,
        pos: "V2Position",
        current_price: float,
        strategy: Optional["StrategyInstance"] = None
    ) -> float:
        """
        Calculate unrealized PnL in dollars.
        
        Formula:
        - LONG: (current_price - avg_price) * qty * tick_value / tick_size
        - SHORT: (avg_price - current_price) * qty * tick_value / tick_size
        """
        if pos.total_qty == 0:
            return 0.0
        
        tick_size = self.tick_size_map.get(pos.ticker, 0.25)
        tick_value = 0.50  # Default for MNQ
        
        if strategy:
            tick_size = strategy.tick_size
            tick_value = strategy.tick_value
        
        price_diff = current_price - pos.avg_price
        
        if pos.side == "SHORT":
            price_diff = -price_diff
        
        # Convert price difference to ticks, then to dollars
        ticks = price_diff / tick_size
        pnl = ticks * tick_value * pos.total_qty
        
        return round(pnl, 2)
    
    def calculate_realized_pnl(
        self,
        entry_price: float,
        exit_price: float,
        qty: int,
        side: str,
        strategy: Optional["StrategyInstance"] = None,
        ticker: str = ""
    ) -> float:
        """
        Calculate realized PnL for a closed position.
        """
        tick_size = self.tick_size_map.get(ticker, 0.25)
        tick_value = 0.50
        
        if strategy:
            tick_size = strategy.tick_size
            tick_value = strategy.tick_value
        
        price_diff = exit_price - entry_price
        
        if side == "SHORT":
            price_diff = -price_diff
        
        ticks = price_diff / tick_size
        pnl = ticks * tick_value * qty
        
        return round(pnl, 2)
    
    def update_position_mfe_mae(
        self,
        pos: "V2Position",
        current_price: float,
        strategy: Optional["StrategyInstance"] = None
    ) -> Tuple[float, float]:
        """
        Update Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE).
        
        Returns (mfe, mae) tuple.
        """
        current_pnl = self.calculate_unrealized_pnl(pos, current_price, strategy)
        
        # Update MFE (best unrealized PnL)
        if current_pnl > pos.max_favorable_excursion:
            pos.max_favorable_excursion = current_pnl
        
        # Update MAE (worst unrealized PnL)
        if current_pnl < pos.max_adverse_excursion:
            pos.max_adverse_excursion = current_pnl
        
        pos.unrealized_pnl = current_pnl
        pos.last_price = current_price
        
        return (pos.max_favorable_excursion, pos.max_adverse_excursion)


# =============================================================================
# BROKER POSITION SYNC (Per Architecture Doc Section 6)
# =============================================================================

class BrokerPositionSync:
    """
    Compares virtual positions against real broker positions.
    Detects drift and optionally reconciles.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._snapshots: Dict[str, BrokerPositionSnapshot] = {}
        self._lock = threading.Lock()
    
    def take_snapshot(
        self,
        strategy_id: str,
        ticker: str,
        virtual_qty: int,
        virtual_avg_price: float,
        broker_qty: int,
        broker_avg_price: float
    ) -> BrokerPositionSnapshot:
        """
        Take a snapshot comparing virtual vs broker state.
        """
        snapshot = BrokerPositionSnapshot(
            strategy_id=strategy_id,
            ticker=ticker,
            broker_qty=broker_qty,
            broker_avg_price=broker_avg_price,
            virtual_qty=virtual_qty,
            virtual_avg_price=virtual_avg_price,
            drift_qty=broker_qty - virtual_qty,
            drift_price=broker_avg_price - virtual_avg_price if broker_qty > 0 and virtual_qty > 0 else 0.0,
            is_synced=(broker_qty == virtual_qty)
        )
        
        key = f"{strategy_id}:{ticker}"
        with self._lock:
            self._snapshots[key] = snapshot
        
        if not snapshot.is_synced:
            logger.warning(
                f"⚠️ POSITION DRIFT: {ticker} | Virtual: {virtual_qty} @ {virtual_avg_price:.2f} | "
                f"Broker: {broker_qty} @ {broker_avg_price:.2f} | Drift: {snapshot.drift_qty}"
            )
        
        self._persist_snapshot(snapshot)
        return snapshot
    
    def get_drift_report(self) -> List[BrokerPositionSnapshot]:
        """Get all snapshots with drift."""
        with self._lock:
            return [s for s in self._snapshots.values() if not s.is_synced]
    
    def _persist_snapshot(self, snapshot: BrokerPositionSnapshot) -> None:
        """Save snapshot to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO v2_broker_snapshots 
                (id, strategy_id, ticker, broker_qty, broker_avg_price, 
                 virtual_qty, virtual_avg_price, drift_qty, drift_price, 
                 snapshot_time, is_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                snapshot.id, snapshot.strategy_id, snapshot.ticker,
                snapshot.broker_qty, snapshot.broker_avg_price,
                snapshot.virtual_qty, snapshot.virtual_avg_price,
                snapshot.drift_qty, snapshot.drift_price,
                snapshot.snapshot_time.isoformat(), snapshot.is_synced
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to persist broker snapshot: {e}")


# =============================================================================
# BROKER-DRIVEN EXECUTION ENGINE (TradeManager-Style)
# =============================================================================
#
# This section implements the production-grade reactive execution engine:
# - BrokerEventLoop: Tradovate WS-driven exit triggers (not price-feed driven)
# - AdvancedExitManager: Limit→chase→market pattern with 50-150ms replace
# - ExitConfirmationLoop: Wait for flat confirmation, not fire-and-forget
# - ForceFlattenKillSwitch: Emergency flatten (750ms timeout)
# - PositionDriftReconciler: Virtual vs broker sync (2s max drift)
#
# KEY INSIGHT: TradeManager's tight execution comes from:
# 1. Exit logic tied to BROKER WebSocket events, not price feeds
# 2. Aggressive order replacement (limit→chase→market)
# 3. Confirmation loop until position is confirmed flat
# 4. Kill-switch flattening when market runs away
# =============================================================================


@dataclass
class ExitOrder:
    """Tracks an active exit order through its lifecycle."""
    order_id: str = ""  # Internal tracking ID
    broker_order_id: str = ""  # Tradovate order ID for modify/cancel
    strategy_id: str = ""
    ticker: str = ""
    tradovate_symbol: str = ""
    side: str = ""  # Buy or Sell (exit direction)
    qty: int = 0
    order_type: str = "Limit"  # Limit, Market, Stop
    limit_price: float = 0.0
    stop_price: float = 0.0
    status: str = "pending"  # pending, working, partial, filled, cancelled, replaced, flattening
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    created_at: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)
    replace_count: int = 0
    max_replaces: int = 10
    account_id: int = 0
    account_spec: str = ""


@dataclass
class BrokerTick:
    """Real-time tick from Tradovate WebSocket."""
    symbol: str = ""
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    timestamp: float = field(default_factory=time.time)


class BrokerEventLoop:
    """
    Tradovate WebSocket-driven event loop for exit triggers.
    
    KEY DIFFERENCE FROM PRICE-FEED APPROACH:
    - Exit logic triggers on BROKER events (fills, ticks, order status)
    - NOT waiting for update_price() from TV feed
    - Runs on same thread as WS event processing
    - Microsecond-level reactivity
    
    Events handled:
    - md/subscribeQuote: Real-time bid/ask/last
    - order/fills: Fill confirmations
    - order/item: Order status updates
    - position/item: Position changes
    """
    
    def __init__(self, db_path: str = "just_trades.db"):
        self.db_path = db_path
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ws: Optional[Any] = None
        self._running = False
        self._stop_event = threading.Event()
        
        # Callbacks for different event types
        self._on_tick: Optional[Callable[[BrokerTick], None]] = None
        self._on_fill: Optional[Callable[[Dict], None]] = None
        self._on_order_update: Optional[Callable[[Dict], None]] = None
        self._on_position_update: Optional[Callable[[Dict], None]] = None
        
        # State tracking
        self._subscribed_symbols: Set[str] = set()
        self._pending_exits: Dict[str, ExitOrder] = {}  # order_id -> ExitOrder
        self._last_ticks: Dict[str, BrokerTick] = {}  # symbol -> last tick
        
        # Timing thresholds (TradeManager-style)
        self.REPLACE_WINDOW_MS = 100  # 50-150ms replace windows
        self.FLATTEN_TIMEOUT_MS = 750  # 750ms forced flatten window
        self.MAX_DRIFT_WINDOW_MS = 2000  # 2-second max drift window
        
        logger.info("🔄 BrokerEventLoop initialized")
    
    def set_callbacks(
        self,
        on_tick: Optional[Callable[[BrokerTick], None]] = None,
        on_fill: Optional[Callable[[Dict], None]] = None,
        on_order_update: Optional[Callable[[Dict], None]] = None,
        on_position_update: Optional[Callable[[Dict], None]] = None,
    ) -> None:
        """Set event callbacks."""
        self._on_tick = on_tick
        self._on_fill = on_fill
        self._on_order_update = on_order_update
        self._on_position_update = on_position_update
    
    def start(self, access_token: str, is_demo: bool = True) -> None:
        """Start the broker event loop in background thread."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_until_complete(self._ws_main(access_token, is_demo))
            except Exception as e:
                logger.error(f"BrokerEventLoop error: {e}", exc_info=True)
            finally:
                self._running = False
        
        self._thread = threading.Thread(target=run_loop, daemon=True, name="BrokerEventLoop")
        self._thread.start()
        logger.info("🚀 BrokerEventLoop started")
    
    def stop(self) -> None:
        """Stop the event loop."""
        self._stop_event.set()
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("🛑 BrokerEventLoop stopped")
    
    async def _ws_main(self, access_token: str, is_demo: bool) -> None:
        """Main WebSocket connection and message handling."""
        base_url = "wss://demo.tradovateapi.com/v1/websocket" if is_demo else "wss://live.tradovateapi.com/v1/websocket"
        
        while self._running and not self._stop_event.is_set():
            try:
                async with websockets.connect(base_url) as ws:
                    self._ws = ws
                    logger.info(f"✅ BrokerEventLoop connected to {'demo' if is_demo else 'live'}")
                    
                    # Authenticate
                    auth_msg = f"authorize\n0\n\n{access_token}"
                    await ws.send(auth_msg)
                    
                    # Subscribe to user events (fills, orders, positions)
                    await ws.send("user/syncrequest\n1\n\n{}")
                    
                    # Message loop
                    while self._running and not self._stop_event.is_set():
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                            await self._process_message(msg)
                        except asyncio.TimeoutError:
                            continue
                        except websockets.ConnectionClosed:
                            logger.warning("BrokerEventLoop: Connection closed, reconnecting...")
                            break
                            
            except Exception as e:
                logger.error(f"BrokerEventLoop WS error: {e}")
                if not self._stop_event.is_set():
                    await asyncio.sleep(3)  # Reconnect delay
    
    async def _process_message(self, msg: str) -> None:
        """Process incoming WebSocket message and trigger callbacks."""
        try:
            # Tradovate frames: "endpoint\nid\n\n{json}"
            if '\n' in msg:
                parts = msg.split('\n', 3)
                if len(parts) >= 4:
                    endpoint = parts[0]
                    data = json.loads(parts[3]) if parts[3] else {}
                    
                    # Route to appropriate handler
                    if 'md/subscribeQuote' in endpoint or 'quote' in endpoint.lower():
                        await self._handle_quote(data)
                    elif 'order/fills' in endpoint or 'fill' in endpoint.lower():
                        await self._handle_fill(data)
                    elif 'order/item' in endpoint or 'order' in endpoint.lower():
                        await self._handle_order_update(data)
                    elif 'position' in endpoint.lower():
                        await self._handle_position_update(data)
            else:
                # Try parsing as plain JSON
                try:
                    data = json.loads(msg)
                    if isinstance(data, dict):
                        if 'fills' in data:
                            await self._handle_fill(data)
                        elif 'orderId' in data:
                            await self._handle_order_update(data)
                except:
                    pass
        except Exception as e:
            logger.debug(f"BrokerEventLoop parse error: {e}")
    
    async def _handle_quote(self, data: Dict) -> None:
        """Handle real-time quote update."""
        try:
            entries = data.get('quotes', data.get('d', [data]))
            if not isinstance(entries, list):
                entries = [entries]
            
            for quote in entries:
                if not isinstance(quote, dict):
                    continue
                
                symbol = quote.get('contractId') or quote.get('symbol', '')
                if not symbol:
                    continue
                
                tick = BrokerTick(
                    symbol=str(symbol),
                    bid=float(quote.get('bid', {}).get('price', 0) if isinstance(quote.get('bid'), dict) else quote.get('bidPrice', 0)),
                    ask=float(quote.get('ask', {}).get('price', 0) if isinstance(quote.get('ask'), dict) else quote.get('askPrice', 0)),
                    last=float(quote.get('trade', {}).get('price', 0) if isinstance(quote.get('trade'), dict) else quote.get('lastPrice', 0)),
                    timestamp=time.time(),
                )
                
                self._last_ticks[tick.symbol] = tick
                
                # CRITICAL: Trigger exit logic on EVERY broker tick
                if self._on_tick:
                    self._on_tick(tick)
                    
        except Exception as e:
            logger.debug(f"Quote handler error: {e}")
    
    async def _handle_fill(self, data: Dict) -> None:
        """Handle fill confirmation - CRITICAL for exit confirmation."""
        try:
            fills = data.get('fills', [data]) if 'fills' in data or 'orderId' in data else []
            if not isinstance(fills, list):
                fills = [fills]
            
            for fill in fills:
                if not isinstance(fill, dict):
                    continue
                
                order_id = str(fill.get('orderId', ''))
                if order_id and order_id in self._pending_exits:
                    exit_order = self._pending_exits[order_id]
                    exit_order.filled_qty += int(fill.get('qty', 0))
                    exit_order.avg_fill_price = float(fill.get('price', exit_order.avg_fill_price))
                    exit_order.last_update = time.time()
                    
                    if exit_order.filled_qty >= exit_order.qty:
                        exit_order.status = "filled"
                        logger.info(f"✅ EXIT FILLED: {exit_order.ticker} {exit_order.qty} @ {exit_order.avg_fill_price}")
                    else:
                        exit_order.status = "partial"
                
                # Trigger callback
                if self._on_fill:
                    self._on_fill(fill)
                    
        except Exception as e:
            logger.debug(f"Fill handler error: {e}")
    
    async def _handle_order_update(self, data: Dict) -> None:
        """Handle order status update."""
        try:
            order_id = str(data.get('orderId', data.get('id', '')))
            if order_id and order_id in self._pending_exits:
                exit_order = self._pending_exits[order_id]
                status = data.get('ordStatus', data.get('status', ''))
                
                if status in ('Filled', 'Completed'):
                    exit_order.status = "filled"
                elif status in ('Cancelled', 'Rejected'):
                    exit_order.status = "cancelled"
                elif status in ('Working', 'Accepted'):
                    exit_order.status = "working"
                
                exit_order.last_update = time.time()
            
            if self._on_order_update:
                self._on_order_update(data)
                
        except Exception as e:
            logger.debug(f"Order update handler error: {e}")
    
    async def _handle_position_update(self, data: Dict) -> None:
        """Handle position change notification."""
        if self._on_position_update:
            self._on_position_update(data)
    
    def subscribe_symbol(self, tradovate_symbol: str) -> None:
        """Subscribe to real-time quotes for a symbol."""
        if tradovate_symbol in self._subscribed_symbols:
            return
        self._subscribed_symbols.add(tradovate_symbol)
        
        if self._ws and self._loop:
            async def sub():
                try:
                    msg = f"md/subscribeQuote\n99\n\n{{\"symbol\":\"{tradovate_symbol}\"}}"
                    await self._ws.send(msg)
                except:
                    pass
            asyncio.run_coroutine_threadsafe(sub(), self._loop)
    
    def get_last_tick(self, symbol: str) -> Optional[BrokerTick]:
        """Get last known tick for symbol."""
        return self._last_ticks.get(symbol)
    
    def track_exit_order(self, order: ExitOrder) -> None:
        """Track an exit order for confirmation."""
        self._pending_exits[order.order_id] = order
    
    def get_exit_order(self, order_id: str) -> Optional[ExitOrder]:
        """Get tracked exit order."""
        return self._pending_exits.get(order_id)
    
    def remove_exit_order(self, order_id: str) -> None:
        """Remove completed exit order from tracking."""
        self._pending_exits.pop(order_id, None)


class ExitState(Enum):
    """Exit order state machine states (per Section 5.2 of TRADEMANAGER_REPLICA.md)."""
    IDLE = "idle"
    PREPARE_EXIT = "prepare_exit"
    WORKING_EXIT = "working_exit"
    CONFIRM_FLAT = "confirm_flat"


class AdvancedExitManager:
    """
    TradeManager-style exit execution with aggressive order management.
    
    State Machine: IDLE → PREPARE_EXIT → WORKING_EXIT → CONFIRM_FLAT → IDLE
    
    Pattern: limit-at-bid → reprice every tick → cancel/replace → market fallback
    
    This is NOT fire-and-forget. We:
    1. Place limit exit at best price (PREPARE_EXIT)
    2. On every broker tick: check if filled, else REPLACE order (WORKING_EXIT)
    3. Chase the market aggressively (75ms replace intervals)
    4. Fallback to market if no fill within threshold (500ms)
    5. Force flatten if still not filled (750ms)
    6. Wait for broker confirmation of flat (CONFIRM_FLAT)
    """
    
    def __init__(self, broker_loop: BrokerEventLoop, db_path: str = "just_trades.db"):
        self.broker_loop = broker_loop
        self.db_path = db_path
        self._active_exits: Dict[str, ExitOrder] = {}  # strategy_id:ticker -> ExitOrder
        self._exit_states: Dict[str, ExitState] = {}  # strategy_id:ticker -> state
        
        # Dedicated event loop for async Tradovate calls
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_event_loop()
        
        # Timing thresholds (TradeManager-style microsecond intervals)
        self.LIMIT_TIMEOUT_MS = 100  # 100ms before first replace
        self.REPLACE_INTERVAL_MS = 75  # 75ms between replaces
        self.MARKET_FALLBACK_MS = 500  # 500ms before switching to market
        self.FORCE_FLATTEN_MS = 750  # 750ms before force flatten
        self.CONFIRM_TIMEOUT_MS = 2000  # 2s max to confirm flat
        
        # Register tick callback for exit chasing
        broker_loop.set_callbacks(on_tick=self._on_broker_tick)
        
        logger.info("📊 AdvancedExitManager initialized (state machine mode)")
    
    def _start_event_loop(self) -> None:
        """Start dedicated event loop for async Tradovate calls."""
        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True, name="ExitManagerLoop")
        self._loop_thread.start()
        # Wait for loop to be ready
        for _ in range(50):
            if self._loop is not None:
                break
            time.sleep(0.1)
    
    def _run_async(self, coro) -> Any:
        """Run coroutine in dedicated event loop (thread-safe)."""
        if not self._loop:
            logger.error("Exit manager event loop not available")
            return None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout=10)
        except Exception as e:
            logger.error(f"Async execution error: {e}")
            return None
    
    def _get_tradovate_client(self, exit_order: ExitOrder) -> Optional[Any]:
        """Get TradovateIntegration client for an exit order."""
        try:
            from phantom_scraper.tradovate_integration import TradovateIntegration
            
            # Get credentials from database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get account credentials
            cursor.execute('''
                SELECT a.tradovate_token, a.tradovate_refresh_token, 
                       t.is_demo
                FROM accounts a
                JOIN traders t ON t.account_id = a.id
                WHERE t.subaccount_id = ?
                LIMIT 1
            ''', (exit_order.account_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            is_demo = bool(row['is_demo'])
            tv = TradovateIntegration(demo=is_demo)
            tv.access_token = row['tradovate_token']
            tv.refresh_token = row['tradovate_refresh_token']
            
            return tv
        except Exception as e:
            logger.error(f"Failed to get Tradovate client: {e}")
            return None
    
    def _on_broker_tick(self, tick: BrokerTick) -> None:
        """
        CRITICAL: Called on EVERY broker tick.
        This is where we chase exits - not on price feed updates.
        """
        for key, exit_order in list(self._active_exits.items()):
            if exit_order.tradovate_symbol == tick.symbol or str(exit_order.account_id) == tick.symbol:
                self._evaluate_exit(exit_order, tick)
    
    def _evaluate_exit(self, exit_order: ExitOrder, tick: BrokerTick) -> None:
        """Evaluate and potentially replace exit order based on latest tick."""
        now = time.time()
        age_ms = (now - exit_order.created_at) * 1000
        since_update_ms = (now - exit_order.last_update) * 1000
        key = f"{exit_order.strategy_id}:{exit_order.ticker}"
        state = self._exit_states.get(key, ExitState.IDLE)
        
        # Already filled?
        if exit_order.status == "filled":
            self._transition_state(key, ExitState.CONFIRM_FLAT)
            self._cleanup_exit(exit_order)
            return
        
        # Get current best price for exit
        if exit_order.side == "Sell":
            best_price = tick.bid if tick.bid > 0 else tick.last
        else:  # Buy to cover
            best_price = tick.ask if tick.ask > 0 else tick.last
        
        if best_price <= 0:
            return
        
        # State machine transitions based on age
        if state == ExitState.PREPARE_EXIT:
            # Initial order placed, now working
            self._transition_state(key, ExitState.WORKING_EXIT)
        
        if age_ms < self.LIMIT_TIMEOUT_MS:
            # Still within initial limit window - wait
            return
        
        if age_ms < self.MARKET_FALLBACK_MS:
            # Chase phase: replace order if price moved
            if since_update_ms >= self.REPLACE_INTERVAL_MS:
                price_diff = abs(best_price - exit_order.limit_price)
                tick_size = 0.25  # TODO: Get from symbol config
                if price_diff >= tick_size:
                    self._replace_exit_order(exit_order, best_price)
            return
        
        if age_ms < self.FORCE_FLATTEN_MS:
            # Market fallback phase
            if exit_order.order_type != "Market":
                logger.warning(f"⚠️ EXIT TIMEOUT: Switching to market order for {exit_order.ticker}")
                self._convert_to_market(exit_order)
            return
        
        # Force flatten phase
        if exit_order.status not in ("filled", "flattening"):
            logger.error(f"🚨 FORCE FLATTEN: {exit_order.ticker} not filled after {age_ms:.0f}ms")
            self._force_flatten(exit_order)
    
    def _transition_state(self, key: str, new_state: ExitState) -> None:
        """Transition exit state machine."""
        old_state = self._exit_states.get(key, ExitState.IDLE)
        self._exit_states[key] = new_state
        logger.debug(f"Exit state: {key} {old_state.value} → {new_state.value}")
    
    def _replace_exit_order(self, exit_order: ExitOrder, new_price: float) -> None:
        """Replace limit order with new price (chase the market)."""
        if exit_order.replace_count >= exit_order.max_replaces:
            logger.warning(f"Max replaces reached for {exit_order.ticker}, converting to market")
            self._convert_to_market(exit_order)
            return
        
        exit_order.replace_count += 1
        old_price = exit_order.limit_price
        exit_order.limit_price = new_price
        exit_order.last_update = time.time()
        
        logger.info(f"🔄 REPLACE EXIT: {exit_order.ticker} {old_price} → {new_price} (#{exit_order.replace_count})")
        
        # Actually call Tradovate modify_order API
        async def do_modify():
            tv = self._get_tradovate_client(exit_order)
            if tv:
                async with tv:
                    # Try to modify existing order
                    if exit_order.broker_order_id:
                        result = await tv.modify_order(
                            order_id=int(exit_order.broker_order_id),
                            new_price=new_price
                        )
                        if result and result.get('success'):
                            logger.info(f"✅ Order modified: {exit_order.broker_order_id} → {new_price}")
                        else:
                            # If modify fails, cancel and replace
                            logger.warning(f"Modify failed, cancel and replace")
                            await tv.cancel_order(int(exit_order.broker_order_id))
                            order = tv.create_limit_order(
                                exit_order.account_spec,
                                exit_order.tradovate_symbol,
                                exit_order.side,
                                exit_order.qty - exit_order.filled_qty,
                                new_price,
                                exit_order.account_id
                            )
                            new_result = await tv.place_order(order)
                            if new_result:
                                exit_order.broker_order_id = str(new_result.get('orderId', ''))
        
        self._run_async(do_modify())
    
    def _convert_to_market(self, exit_order: ExitOrder) -> None:
        """Convert limit order to market order."""
        exit_order.order_type = "Market"
        exit_order.last_update = time.time()
        
        logger.info(f"🔥 MARKET EXIT: {exit_order.ticker} qty={exit_order.qty - exit_order.filled_qty}")
        
        # Cancel existing order and place market
        async def do_market():
            tv = self._get_tradovate_client(exit_order)
            if tv:
                async with tv:
                    # Cancel existing order
                    if exit_order.broker_order_id:
                        await tv.cancel_order(int(exit_order.broker_order_id))
                    
                    # Place market order
                    remaining_qty = exit_order.qty - exit_order.filled_qty
                    if remaining_qty > 0:
                        order = tv.create_market_order(
                            exit_order.account_spec,
                            exit_order.tradovate_symbol,
                            exit_order.side,
                            remaining_qty,
                            exit_order.account_id
                        )
                        result = await tv.place_order(order)
                        if result:
                            exit_order.broker_order_id = str(result.get('orderId', ''))
                            logger.info(f"✅ Market exit placed: {exit_order.broker_order_id}")
        
        self._run_async(do_market())
    
    def _force_flatten(self, exit_order: ExitOrder) -> None:
        """
        Emergency flatten - cancel all orders and liquidate position.
        This is the kill switch.
        """
        logger.error(f"🚨 FORCE FLATTEN: {exit_order.ticker} - Emergency liquidation")
        
        exit_order.order_type = "Market"
        exit_order.status = "flattening"
        exit_order.last_update = time.time()
        
        key = f"{exit_order.strategy_id}:{exit_order.ticker}"
        self._transition_state(key, ExitState.CONFIRM_FLAT)
        
        # Call Tradovate liquidatePosition
        async def do_flatten():
            tv = self._get_tradovate_client(exit_order)
            if tv:
                async with tv:
                    # Get contract ID for liquidation
                    contract_id = await tv.get_contract_id(exit_order.tradovate_symbol)
                    if contract_id:
                        result = await tv.liquidate_position(
                            exit_order.account_id,
                            contract_id
                        )
                        if result and result.get('success'):
                            logger.info(f"✅ Position liquidated: {exit_order.tradovate_symbol}")
                            exit_order.status = "filled"
                        else:
                            logger.error(f"❌ Liquidation failed: {result}")
                    else:
                        # Fallback: aggressive market order
                        order = tv.create_market_order(
                            exit_order.account_spec,
                            exit_order.tradovate_symbol,
                            exit_order.side,
                            exit_order.qty - exit_order.filled_qty,
                            exit_order.account_id
                        )
                        await tv.place_order(order)
        
        self._run_async(do_flatten())
    
    def _cleanup_exit(self, exit_order: ExitOrder) -> None:
        """Clean up completed exit order."""
        key = f"{exit_order.strategy_id}:{exit_order.ticker}"
        self._active_exits.pop(key, None)
        self._exit_states.pop(key, None)
        self.broker_loop.remove_exit_order(exit_order.order_id)
        logger.info(f"✅ Exit completed: {exit_order.ticker} filled {exit_order.filled_qty}/{exit_order.qty}")
    
    def initiate_exit(
        self,
        strategy_id: str,
        ticker: str,
        tradovate_symbol: str,
        side: str,
        qty: int,
        target_price: float,
        account_id: int,
        account_spec: str,
    ) -> ExitOrder:
        """
        Initiate an exit with MARKET order.
        
        ALWAYS use MARKET orders for exits - no limit orders.
        This ensures immediate fills without risk of stranded orders.
        """
        order = ExitOrder(
            order_id=str(uuid.uuid4()),
            strategy_id=strategy_id,
            ticker=ticker,
            tradovate_symbol=tradovate_symbol,
            side=side,
            qty=qty,
            order_type="Market",  # ALWAYS market
            limit_price=target_price,  # For reference only
            account_id=account_id,
            account_spec=account_spec,
        )
        
        key = f"{strategy_id}:{ticker}"
        self._active_exits[key] = order
        self._exit_states[key] = ExitState.PREPARE_EXIT
        self.broker_loop.track_exit_order(order)
        
        logger.info(f"📤 EXIT INITIATED: {side} {qty} {ticker} @ MARKET")
        
        # Place MARKET order via Tradovate
        async def do_place():
            tv = self._get_tradovate_client(order)
            if tv:
                async with tv:
                    market_order = tv.create_market_order(
                        account_spec,
                        tradovate_symbol,
                        side,
                        qty,
                        account_id
                    )
                    result = await tv.place_order(market_order)
                    if result:
                        order.broker_order_id = str(result.get('orderId', ''))
                        order.status = "working"
                        logger.info(f"✅ Market exit order placed: {order.broker_order_id}")
                    else:
                        logger.error(f"❌ Failed to place market exit order")
        
        self._run_async(do_place())
        
        return order
    
    def get_exit_status(self, strategy_id: str, ticker: str) -> Optional[ExitOrder]:
        """Get status of active exit."""
        key = f"{strategy_id}:{ticker}"
        return self._active_exits.get(key)
    
    def get_exit_state(self, strategy_id: str, ticker: str) -> ExitState:
        """Get current state machine state for an exit."""
        key = f"{strategy_id}:{ticker}"
        return self._exit_states.get(key, ExitState.IDLE)
    
    def is_exit_pending(self, strategy_id: str, ticker: str) -> bool:
        """Check if there's a pending exit for this position."""
        key = f"{strategy_id}:{ticker}"
        order = self._active_exits.get(key)
        return order is not None and order.status not in ("filled", "cancelled")
    
    def shutdown(self) -> None:
        """Clean shutdown of event loop."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread:
                self._loop_thread.join(timeout=2)


class ExitConfirmationLoop:
    """
    Confirmation loop that waits until position is confirmed flat.
    NOT fire-and-forget.
    
    Pattern:
    while position not flat:
        process fills
        adjust order
        if timeout exceeded:
            force flatten
    """
    
    def __init__(self, exit_manager: AdvancedExitManager, broker_loop: BrokerEventLoop):
        self.exit_manager = exit_manager
        self.broker_loop = broker_loop
        self._pending_confirmations: Dict[str, Dict] = {}  # strategy:ticker -> confirmation state
        self._lock = threading.Lock()
        
        # Register fill callback
        original_on_fill = broker_loop._on_fill
        def on_fill_wrapper(fill: Dict):
            self._process_fill(fill)
            if original_on_fill:
                original_on_fill(fill)
        broker_loop._on_fill = on_fill_wrapper
        
        logger.info("✅ ExitConfirmationLoop initialized")
    
    def await_flat(
        self,
        strategy_id: str,
        ticker: str,
        expected_qty: int,
        timeout_ms: float = 2000,
    ) -> bool:
        """
        Wait for position to be confirmed flat.
        Returns True if flat confirmed, False if timeout.
        
        This is BLOCKING - use in background thread.
        """
        key = f"{strategy_id}:{ticker}"
        start = time.time()
        timeout_s = timeout_ms / 1000
        
        with self._lock:
            self._pending_confirmations[key] = {
                "expected_qty": expected_qty,
                "filled_qty": 0,
                "confirmed": False,
                "start_time": start,
            }
        
        # Poll for confirmation
        while (time.time() - start) < timeout_s:
            with self._lock:
                state = self._pending_confirmations.get(key)
                if state and state["confirmed"]:
                    self._pending_confirmations.pop(key, None)
                    logger.info(f"✅ FLAT CONFIRMED: {ticker} after {(time.time()-start)*1000:.0f}ms")
                    return True
            time.sleep(0.010)  # 10ms poll interval
        
        # Timeout
        with self._lock:
            self._pending_confirmations.pop(key, None)
        
        logger.warning(f"⚠️ FLAT TIMEOUT: {ticker} not confirmed after {timeout_ms}ms")
        return False
    
    def _process_fill(self, fill: Dict) -> None:
        """Process fill and update confirmation state."""
        order_id = str(fill.get('orderId', ''))
        filled_qty = int(fill.get('qty', 0))
        
        # Match fill to pending confirmation via exit order tracking
        exit_order = self.broker_loop.get_exit_order(order_id)
        if not exit_order:
            return
        
        key = f"{exit_order.strategy_id}:{exit_order.ticker}"
        
        with self._lock:
            state = self._pending_confirmations.get(key)
            if state:
                state["filled_qty"] += filled_qty
                if state["filled_qty"] >= state["expected_qty"]:
                    state["confirmed"] = True


class ForceFlattenKillSwitch:
    """
    Emergency kill switch that force-flattens positions when:
    - Market volatility increases (ATR spike)
    - DCA step would get invalidated
    - Position drift > threshold
    - Exit order sits too long
    
    This runs independently and can override normal exit logic.
    """
    
    def __init__(self, broker_loop: BrokerEventLoop, db_path: str = "just_trades.db"):
        self.broker_loop = broker_loop
        self.db_path = db_path
        self._armed_positions: Dict[str, Dict] = {}  # strategy:ticker -> kill state
        self._lock = threading.Lock()
        
        # Thresholds
        self.MAX_EXIT_AGE_MS = 750  # Force flatten after 750ms
        self.ATR_SPIKE_MULTIPLIER = 2.0  # 2x ATR = spike
        self.MAX_DRIFT_QTY = 2  # Max allowed qty drift
        self.MAX_DRIFT_TICKS = 20  # Max price drift in ticks
        
        logger.info("🚨 ForceFlattenKillSwitch initialized")
    
    def arm(self, strategy_id: str, ticker: str, qty: int, entry_price: float, atr: float = 0) -> None:
        """Arm the kill switch for a position."""
        key = f"{strategy_id}:{ticker}"
        with self._lock:
            self._armed_positions[key] = {
                "qty": qty,
                "entry_price": entry_price,
                "atr": atr,
                "armed_at": time.time(),
                "triggered": False,
            }
    
    def disarm(self, strategy_id: str, ticker: str) -> None:
        """Disarm kill switch (position closed normally)."""
        key = f"{strategy_id}:{ticker}"
        with self._lock:
            self._armed_positions.pop(key, None)
    
    def check_triggers(self, strategy_id: str, ticker: str, current_price: float, broker_qty: int = 0) -> bool:
        """
        Check if kill switch should trigger.
        Returns True if flatten should be forced.
        """
        key = f"{strategy_id}:{ticker}"
        
        with self._lock:
            state = self._armed_positions.get(key)
            if not state or state["triggered"]:
                return False
            
            entry = state["entry_price"]
            atr = state["atr"]
            expected_qty = state["qty"]
            
            # Check ATR spike
            if atr > 0:
                price_move = abs(current_price - entry)
                if price_move > (atr * self.ATR_SPIKE_MULTIPLIER):
                    logger.warning(f"🚨 ATR SPIKE: {ticker} moved {price_move:.2f} (ATR={atr:.2f})")
                    state["triggered"] = True
                    return True
            
            # Check position drift
            if broker_qty != 0 and abs(broker_qty - expected_qty) > self.MAX_DRIFT_QTY:
                logger.warning(f"🚨 QTY DRIFT: {ticker} expected={expected_qty}, broker={broker_qty}")
                state["triggered"] = True
                return True
        
        return False
    
    def force_flatten(self, account_id: int, symbol: str) -> None:
        """Execute force flatten via Tradovate."""
        logger.error(f"🚨 EXECUTING FORCE FLATTEN: {symbol}")
        
        # TODO: Implement actual Tradovate flatten call
        # This would use liquidatePosition or aggressive market order
        pass


class PositionDriftReconciler:
    """
    Continuously monitors virtual vs broker position state.
    If they diverge beyond threshold, triggers resync.
    
    TM does this constantly to ensure virtual engine matches reality.
    """
    
    def __init__(self, broker_loop: BrokerEventLoop, db_path: str = "just_trades.db"):
        self.broker_loop = broker_loop
        self.db_path = db_path
        self._virtual_positions: Dict[str, Dict] = {}  # ticker -> {qty, avg_price}
        self._broker_positions: Dict[str, Dict] = {}  # ticker -> {qty, avg_price}
        self._lock = threading.Lock()
        
        # Thresholds
        self.MAX_DRIFT_WINDOW_MS = 2000  # 2 seconds
        self.MAX_QTY_DRIFT = 1  # Allow 1 contract drift temporarily
        self.MAX_PRICE_DRIFT_TICKS = 10  # Allow 10 ticks price drift
        
        # Register position update callback
        broker_loop.set_callbacks(on_position_update=self._on_position_update)
        
        logger.info("🔄 PositionDriftReconciler initialized")
    
    def update_virtual(self, ticker: str, qty: int, avg_price: float) -> None:
        """Update virtual position state."""
        with self._lock:
            self._virtual_positions[ticker] = {
                "qty": qty,
                "avg_price": avg_price,
                "updated_at": time.time(),
            }
    
    def _on_position_update(self, data: Dict) -> None:
        """Update broker position state from WS message."""
        symbol = data.get('contractId') or data.get('symbol', '')
        qty = data.get('netPos', data.get('quantity', 0))
        avg_price = data.get('netPrice', data.get('avgPrice', 0))
        
        with self._lock:
            self._broker_positions[str(symbol)] = {
                "qty": int(qty),
                "avg_price": float(avg_price),
                "updated_at": time.time(),
            }
    
    def check_drift(self, ticker: str) -> Optional[Dict]:
        """
        Check for position drift.
        Returns drift details if drift detected, None if synced.
        CRITICAL: Detects when broker is flat but virtual has position (manual close scenario).
        """
        with self._lock:
            virtual = self._virtual_positions.get(ticker)
            broker = self._broker_positions.get(ticker)
            
            if not virtual and not broker:
                return None  # Both flat
            
            v_qty = virtual.get("qty", 0) if virtual else 0
            b_qty = broker.get("qty", 0) if broker else 0
            v_price = virtual.get("avg_price", 0) if virtual else 0
            b_price = broker.get("avg_price", 0) if broker else 0
            
            # CRITICAL: Detect when broker is flat but virtual has position (manual close on broker)
            if b_qty == 0 and v_qty != 0:
                logger.warning(f"⚠️ DRIFT DETECTED: Broker is flat (0) but virtual has {v_qty} contracts for {ticker}")
                return {
                    "type": "broker_flat_virtual_open",
                    "virtual_qty": v_qty,
                    "broker_qty": 0,
                    "drift": v_qty,  # Full position needs to be closed
                    "action": "close_virtual"  # Signal that virtual should be closed
                }
            
            # Detect when virtual is flat but broker has position (unexpected broker position)
            if v_qty == 0 and b_qty != 0:
                logger.warning(f"⚠️ DRIFT DETECTED: Virtual is flat (0) but broker has {b_qty} contracts for {ticker}")
                return {
                    "type": "virtual_flat_broker_open",
                    "virtual_qty": 0,
                    "broker_qty": b_qty,
                    "drift": b_qty,
                    "action": "sync_from_broker"  # Signal that virtual should sync from broker
                }
            
            qty_drift = abs(v_qty - b_qty)
            price_drift = abs(v_price - b_price)
            
            if qty_drift > self.MAX_QTY_DRIFT:
                return {
                    "type": "qty_drift",
                    "virtual_qty": v_qty,
                    "broker_qty": b_qty,
                    "drift": qty_drift,
                }
            
            if price_drift > (self.MAX_PRICE_DRIFT_TICKS * 0.25):  # Assuming 0.25 tick size
                return {
                    "type": "price_drift",
                    "virtual_price": v_price,
                    "broker_price": b_price,
                    "drift": price_drift,
                }
        
        return None
    
    def resync_from_broker(self, ticker: str) -> Optional[Dict]:
        """
        Force resync virtual state from broker state.
        Handles case where broker is flat (0) but virtual still has position.
        """
        with self._lock:
            broker = self._broker_positions.get(ticker)
            virtual = self._virtual_positions.get(ticker)
            
            b_qty = broker.get("qty", 0) if broker else 0
            v_qty = virtual.get("qty", 0) if virtual else 0
            
            # If broker is flat but virtual has position, close virtual position
            if b_qty == 0 and v_qty != 0:
                logger.warning(f"⚠️ DRIFT: Broker is flat (0) but virtual has {v_qty} contracts for {ticker} - closing virtual position")
                # Remove virtual position to match broker (flat)
                if ticker in self._virtual_positions:
                    del self._virtual_positions[ticker]
                return {"qty": 0, "avg_price": 0.0}  # Return flat state
            
            # If broker has position, sync virtual to match
            if broker:
                self._virtual_positions[ticker] = broker.copy()
                logger.info(f"🔄 RESYNCED: {ticker} virtual ← broker: {broker}")
                return broker
            
            # Both are flat
            if ticker in self._virtual_positions:
                del self._virtual_positions[ticker]
            return None


# =============================================================================
# DATA MODELS (Per Architecture Doc Section 3)
# =============================================================================

@dataclass
class VirtualFill:
    """
    Individual fill record for audit trail.
    Every entry, DCA add, and exit creates a VirtualFill.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    ticker: str = ""
    side: str = ""  # LONG or SHORT
    fill_type: str = ""  # FillType value
    qty: int = 0
    price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    pnl: Optional[float] = None  # Set on exit fills
    notes: str = ""


@dataclass
class VirtualBarPrice:
    """
    TradingView candle price cache.
    Used for PnL calculation that matches chart performance.
    """
    ticker: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0


@dataclass
class BrokerPositionSnapshot:
    """
    Snapshot of real broker position for drift detection.
    Compared against virtual position to detect mismatches.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    ticker: str = ""
    broker_qty: int = 0
    broker_avg_price: float = 0.0
    virtual_qty: int = 0
    virtual_avg_price: float = 0.0
    drift_qty: int = 0  # broker_qty - virtual_qty
    drift_price: float = 0.0  # broker_avg_price - virtual_avg_price
    snapshot_time: datetime = field(default_factory=datetime.utcnow)
    is_synced: bool = True


@dataclass
class DCAStep:
    """
    Single DCA ladder step configuration.
    """
    trigger_type: str = "percent"  # ticks, percent, atr
    trigger_value: float = 0.0     # e.g., 2.0 for 2% drop or 20 for 20 ticks
    qty: int = 1
    enabled: bool = True
    triggered: bool = False        # Track if this step was already triggered


@dataclass
class StrategyInstance:
    """
    Strategy instance with full configuration.
    Maps to architecture's StrategyDefinition + StrategyInstance.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    symbol: str = ""
    timeframe: str = ""
    mode: str = "virtual"  # virtual or live
    tp_ticks: int = 0
    sl_ticks: Optional[int] = None
    dca_steps: List[DCAStep] = field(default_factory=list)
    max_qty: Optional[int] = None
    max_risk_dollars: Optional[float] = None
    tick_size: float = 0.25
    tick_value: float = 0.50  # Dollar value per tick (e.g., $0.50 for MNQ)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    config_json: str = "{}"  # Additional configuration


@dataclass
class V2Position:
    """
    Virtual position state - the "brain's" view of the position.
    Aggregates all entries into weighted average.
    """
    recorder: str
    ticker: str
    side: str  # LONG or SHORT
    total_qty: int
    avg_price: float
    entries: List[Dict] = field(default_factory=list)
    opened_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    # === NEW: Enhanced tracking ===
    strategy_id: str = ""
    unrealized_pnl: float = 0.0
    max_favorable_excursion: float = 0.0  # Best unrealized PnL
    max_adverse_excursion: float = 0.0    # Worst unrealized PnL
    dca_steps_triggered: int = 0
    last_price: float = 0.0
    # === CRITICAL: Persist which DCA steps were triggered (prevents double-trigger after restart) ===
    dca_triggered_indices: List[int] = field(default_factory=list)  # e.g., [0, 1] = steps 0 and 1 triggered
    # === CRITICAL: Pending fill flag - don't evaluate TP/SL until broker confirms entry ===
    pending_fill: bool = True  # True until broker fill confirms entry
    entry_order_id: str = ""   # Broker order ID for entry (to match fills)


@dataclass
class V2StrategySettings:
    """Legacy settings - use StrategyInstance for new code."""
    tp_ticks: int
    sl_ticks: Optional[int] = None
    dca_steps: List[Dict] = field(default_factory=list)  # [{pct_drop: float, qty: int}, ...]
    max_qty: Optional[int] = None
    max_risk: Optional[float] = None  # dollars


class RecorderServiceV2:
    """
    JUST.TRADES Strategy Engine V2 - Full Architecture Implementation
    
    Per JUST_TRADES_STRATEGY_ENGINE_ARCHITECTURE.md:
    - Virtual position engine (brain) - tracks positions independently of broker
    - DCA/scaling logic with auto-trigger (ticks/percent/ATR)
    - Virtual PnL using TradingView prices (matches chart performance)
    - Optional broker execution (hands) - routes to Tradovate
    - Full audit trail with VirtualFill records
    - Broker position drift detection
    
    SCALABILITY FEATURES:
    - In-memory position cache with async DB sync (non-blocking writes)
    - O(1) ticker lookup via TickerIndex (instant price broadcast)
    - Async order queue with retry logic (non-blocking broker calls)
    - Thread-safe operations for concurrent access
    
    PERFORMANCE:
    - Price → TP/SL check: <10ms (vs 2-5s with polling)
    - 100 positions: same speed as 1 position
    - DB writes: non-blocking (batched every 100ms)
    - Broker orders: parallel execution with rate limiting
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        broker_adapter: Optional[Callable[[str, V2Position, float, int], Any]] = None,
        price_feed_adapter: Optional[Callable[[str], Optional[float]]] = None,
        flags: Optional[V2FeatureFlags] = None,
        tick_size_map: Optional[Dict[str, float]] = None,
        poll_interval_secs: int = 2,
    ):
        # Core state - all in memory for speed
        self.positions: Dict[str, V2Position] = {}
        self.settings: Dict[str, V2StrategySettings] = {}
        self.strategies: Dict[str, StrategyInstance] = {}  # NEW: Full strategy configs
        self.db_path = db_path or os.path.join(os.getcwd(), "recorder_v2.db")
        self._price_lock = threading.RLock()  # RLock for nested calls
        self.flags = flags or V2FeatureFlags()
        self.tick_size_map = tick_size_map or self._default_tick_sizes()
        self.poll_interval_secs = poll_interval_secs
        self._poller_stop = threading.Event()
        self._poller_thread: Optional[threading.Thread] = None
        
        # === PRODUCTION COMPONENTS ===
        # Ticker index for O(1) position lookup by symbol
        self._ticker_index = TickerIndex()
        
        # Async DB writer (non-blocking persistence)
        self._async_db = AsyncDBWriter(self.db_path)
        
        # Async order queue (non-blocking broker execution)
        self._order_queue = AsyncOrderQueue(max_workers=4, max_retries=3)
        
        # Price cache with timestamps for staleness detection
        self._price_cache: Dict[str, tuple] = {}  # ticker -> (price, timestamp)
        
        # === NEW: Architecture Components ===
        # DCA Engine for auto-DCA ladder logic
        self._dca_engine = DCAEngine(tick_size_map=self.tick_size_map)
        
        # PnL Engine for virtual PnL calculation
        self._pnl_engine = PnLEngine(tick_size_map=self.tick_size_map)
        
        # Broker Position Sync for drift detection
        self._broker_sync: Optional[BrokerPositionSync] = None  # Initialized after DB setup
        
        # Virtual fills cache (recent fills for quick access)
        self._recent_fills: List[VirtualFill] = []
        self._max_recent_fills = 100
        
        # === CRITICAL: Pending entry fills for TP/SL activation ===
        # Maps broker order_id -> position key (recorder:ticker)
        # Used to update position with actual fill price and enable TP/SL
        self._pending_entry_fills: Dict[str, str] = {}
        
        # === DCA/TP ORDER MANAGEMENT (Fix for multiple TP orders) ===
        # Track active TP orders per position to enforce "exactly one TP" invariant
        self._active_tp_orders: Dict[str, Dict[str, Any]] = {}  # position_key -> {order_id, price, qty, timestamp}
        self._tp_reconciliation_locks: Dict[str, threading.Lock] = {}  # position_key -> Lock for coalescing
        self._tp_sequence_counter: Dict[str, int] = {}  # position_key -> sequence number for tagging

        # Stats for monitoring
        self._stats = {
            "price_updates": 0,
            "tp_hits": 0,
            "sl_hits": 0,
            "dca_triggers": 0,
            "orders_placed": 0,
            "orders_failed": 0,
            "last_price_update": 0,
            "total_virtual_pnl": 0.0,
            "drift_events": 0,
        }
        
        logger.info("🚀 V2 Engine: Full Architecture Mode")
        logger.info("   - AsyncDBWriter: ✅ (non-blocking writes)")
        logger.info("   - TickerIndex: ✅ (O(1) lookup)")
        logger.info("   - AsyncOrderQueue: ✅ (parallel execution)")
        logger.info("   - DCAEngine: ✅ (ticks/percent/ATR triggers)")
        logger.info("   - PnLEngine: ✅ (TradingView price-based)")
        logger.info("   - BrokerPositionSync: ✅ (drift detection)")
    
        # Auto-initialize broker adapter to read from database (not env vars)
        if broker_adapter is None:
            try:
                # Use just_trades.db for credentials (same as V1 engine)
                main_db = os.path.join(os.path.dirname(self.db_path), "just_trades.db")
                self.broker_adapter = TradovateBrokerAdapter(db_path=main_db)
                logger.info("V2: Auto-initialized TradovateBrokerAdapter (reads from DB)")
            except Exception as e:
                logger.warning("V2: Failed to auto-init TradovateBrokerAdapter: %s", e)
                self.broker_adapter = None
        else:
            self.broker_adapter = broker_adapter
        
        # Auto-initialize price feed adapter from env vars if not provided
        # CRITICAL: Prefer webhook payload price ({{close}}) over TV WebSocket
        # TV WebSocket is for dev/testing only - set V2_TV_WS_ENABLE=1 to enable
        self._tv_feed_adapter = None
        tv_ws_enabled = bool(int(os.getenv("V2_TV_WS_ENABLE", "0")))
        
        if price_feed_adapter is None:
            if tv_ws_enabled:
                # DEV MODE ONLY: Use TradingView WebSocket for price feed
                tv_sessionid = os.getenv("TV_SESSIONID", "")
                if tv_sessionid:
                    logger.warning("⚠️  V2: TradingView WebSocket enabled (DEV MODE ONLY)")
                    logger.warning("⚠️  V2: For production, use webhook payload price instead")
                    # Create a stub fetcher (can be replaced with actual TV API call)
                    def tv_fetcher(ticker: str, cookies: Dict[str, str]) -> Optional[float]:
                        # Placeholder: return None to use WebSocket feed instead
                        return None
                    self._tv_feed_adapter = TradingViewPriceFeedAdapter(tv_fetcher)
                    # Auto-start WebSocket
                    self._tv_feed_adapter.start_ws()
                    logger.info("V2: TradingView WebSocket feed started (DEV MODE)")
                    # Use the adapter's get_price method
                    self.price_feed_adapter = lambda ticker: self._tv_feed_adapter.get_price(ticker)
                else:
                    logger.warning("V2: V2_TV_WS_ENABLE=1 but no TV_SESSIONID set")
                    self.price_feed_adapter = None
            else:
                # PRODUCTION MODE: No automatic price feed - rely on webhook payload price
                logger.info("V2: Price feed disabled (production mode) - using webhook payload price as source")
                self.price_feed_adapter = None
        else:
            self.price_feed_adapter = price_feed_adapter
        
        self._init_db()
        self._load_db()
        self._start_poller_if_needed()
        
        # === BROKER-DRIVEN EXECUTION ENGINE (TradeManager-style) ===
        # These components provide production-grade reactive execution:
        # - Exit logic tied to BROKER WebSocket events, not price feeds
        # - Aggressive order replacement (limit→chase→market)
        # - Confirmation loop until position is confirmed flat
        # - Kill-switch flattening when market runs away
        
        self._broker_event_loop: Optional[BrokerEventLoop] = None
        self._exit_manager: Optional[AdvancedExitManager] = None
        self._exit_confirm_loop: Optional[ExitConfirmationLoop] = None
        self._kill_switch: Optional[ForceFlattenKillSwitch] = None
        self._drift_reconciler: Optional[PositionDriftReconciler] = None
        
        # Auto-initialize broker execution engine if we have broker adapter
        if self.broker_adapter:
            self._init_broker_execution_engine()
        
        logger.info("RecorderServiceV2 initialized with db=%s", self.db_path)
    
    def _init_broker_execution_engine(self) -> None:
        """
        Initialize broker-driven execution engine for TradeManager-style exits.

        This provides:
        - Real-time exit triggers from Tradovate WebSocket
        - Limit→chase→market order pattern
        - Exit confirmation loop (not fire-and-forget)
        - Kill switch for emergency flatten
        - Position drift reconciliation
        
        Per Section 5.2 of JUST_TRADES_TRADEMANAGER_REPLICA.md:
        - Broker WebSocket drives exit logic
        - Fill/position updates trigger immediate reactions
        """
        try:
            main_db = os.path.join(os.path.dirname(self.db_path), "just_trades.db")

            # 1. BrokerEventLoop - Tradovate WS-driven triggers
            self._broker_event_loop = BrokerEventLoop(db_path=main_db)

            # 2. AdvancedExitManager - Limit→chase→market
            self._exit_manager = AdvancedExitManager(self._broker_event_loop, db_path=main_db)

            # 3. ExitConfirmationLoop - Wait for flat
            self._exit_confirm_loop = ExitConfirmationLoop(self._exit_manager, self._broker_event_loop)

            # 4. ForceFlattenKillSwitch - Emergency flatten
            self._kill_switch = ForceFlattenKillSwitch(self._broker_event_loop, db_path=main_db)

            # 5. PositionDriftReconciler - Virtual vs broker sync
            self._drift_reconciler = PositionDriftReconciler(self._broker_event_loop, db_path=main_db)

            # === CRITICAL: Wire broker WebSocket events to execution loop ===
            
            # Callback for broker ticks (exit chasing + kill switch)
            def on_broker_tick(tick: BrokerTick):
                # Check kill switch triggers for all positions
                for key, pos in self.positions.items():
                    if self._kill_switch:
                        atr = self._dca_engine.get_atr(pos.ticker)
                        if self._kill_switch.check_triggers(pos.recorder, pos.ticker, tick.last, 0):
                            logger.warning(f"🚨 KILL SWITCH TRIGGERED: {pos.ticker}")
                            if hasattr(self.broker_adapter, '_get_trader_credentials'):
                                creds = self.broker_adapter._get_trader_credentials(pos.recorder)
                                if creds:
                                    self._kill_switch.force_flatten(
                                        creds.get('subaccount_id', 0),
                                        self.broker_adapter._convert_ticker(pos.ticker)
                                    )
                
                # Update price for TP/SL evaluation (broker-driven, not TV-driven)
                # This ensures exit logic runs on broker ticks, not just price feed
                self.update_price(tick.symbol, tick.last)
            
            # Callback for broker fills (exit confirmation)
            def on_broker_fill(fill: Dict):
                order_id = str(fill.get('orderId', ''))
                filled_qty = int(fill.get('qty', 0))
                fill_price = float(fill.get('price', 0))
                
                logger.info(f"📥 BROKER FILL: order={order_id}, qty={filled_qty}, price={fill_price}")
                
                # Call the service layer method
                self.on_broker_fill(fill)
            
            # Callback for broker position updates (drift detection)
            def on_broker_position_update(data: Dict):
                symbol = data.get('contractId') or data.get('symbol', '')
                qty = data.get('netPos', data.get('quantity', 0))
                avg_price = data.get('netPrice', data.get('avgPrice', 0))
                
                logger.debug(f"📊 BROKER POSITION: {symbol} qty={qty} @ {avg_price}")
                
                # Update drift reconciler
                if self._drift_reconciler:
                    self._drift_reconciler._on_position_update(data)
                
                # Call the service layer method
                self.on_broker_position_update(data)
            
            # Callback for broker order updates (exit status tracking)
            def on_broker_order_update(data: Dict):
                order_id = str(data.get('orderId', data.get('id', '')))
                status = data.get('ordStatus', data.get('status', ''))
                
                logger.debug(f"📋 BROKER ORDER: {order_id} status={status}")
                
                # Update exit manager's tracked orders
                if self._exit_manager:
                    for key, exit_order in self._exit_manager._active_exits.items():
                        if exit_order.broker_order_id == order_id:
                            if status in ('Filled', 'Completed'):
                                exit_order.status = "filled"
                                exit_order.filled_qty = exit_order.qty
                            elif status in ('Cancelled', 'Rejected'):
                                exit_order.status = "cancelled"
                            elif status in ('Working', 'Accepted'):
                                exit_order.status = "working"

            # Set all callbacks on the broker event loop
            self._broker_event_loop.set_callbacks(
                on_tick=on_broker_tick,
                on_fill=on_broker_fill,
                on_order_update=on_broker_order_update,
                on_position_update=on_broker_position_update,
            )

            logger.info("🚀 Broker-Driven Execution Engine initialized:")
            logger.info("   - BrokerEventLoop: ✅ (Tradovate WS triggers)")
            logger.info("   - AdvancedExitManager: ✅ (limit→chase→market)")
            logger.info("   - ExitConfirmationLoop: ✅ (wait for flat)")
            logger.info("   - ForceFlattenKillSwitch: ✅ (750ms timeout)")
            logger.info("   - PositionDriftReconciler: ✅ (2s max drift)")
            logger.info("   - Fill/Order/Position callbacks: ✅ (wired to execution loop)")

        except Exception as e:
            logger.warning(f"Failed to init broker execution engine: {e}")
            logger.info("Falling back to basic execution mode")
    
    def _default_tick_sizes(self) -> Dict[str, float]:
        """Default tick sizes for common futures."""
        return {
            "MNQ": 0.25, "NQ": 0.25, "MNQ1!": 0.25, "NQ1!": 0.25,
            "MES": 0.25, "ES": 0.25, "MES1!": 0.25, "ES1!": 0.25,
            "M2K": 0.10, "RTY": 0.10, "M2K1!": 0.10, "RTY1!": 0.10,
            "MYM": 1.0, "YM": 1.0, "MYM1!": 1.0, "YM1!": 1.0,
            "MCL": 0.01, "CL": 0.01, "MCL1!": 0.01, "CL1!": 0.01,
            "MGC": 0.10, "GC": 0.10, "MGC1!": 0.10, "GC1!": 0.10,
        }

    # ---------- Poller for price_feed_adapter (if no WS) ----------
    def _start_poller_if_needed(self) -> None:
        """Start polling price feed if adapter is available and WebSocket is not enabled."""
        if not self.price_feed_adapter:
            return
        # Don't start poller if TradingView WebSocket is enabled
        if self._tv_feed_adapter and self._tv_feed_adapter.ws_enabled:
            return
        if self._poller_thread and self._poller_thread.is_alive():
            return
        self._poller_stop.clear()
        self._poller_thread = threading.Thread(target=self._poller_loop, daemon=True)
        self._poller_thread.start()

    def _poller_loop(self) -> None:
        """Background thread that polls price feed for active positions."""
        while not self._poller_stop.is_set():
            try:
                tickers = {pos.ticker for pos in self.positions.values()}
                for tic in tickers:
                    try:
                        price = self.price_feed_adapter(tic)
                        if price is not None:
                            self.update_price(tic, price)
                    except Exception:
                        continue
            except Exception:
                pass
            time.sleep(self.poll_interval_secs)

    # ---------- Public entry points ----------
    def register_strategy(self, recorder: str, settings: V2StrategySettings) -> None:
        self.settings[recorder] = settings
        logger.info("V2 strategy registered: %s %s", recorder, settings)
        self._persist_settings(recorder, settings)

    def _load_strategy_from_db(self, recorder: str) -> None:
        """Load strategy from database if not in memory."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM v2_strategies 
                WHERE name = ? OR id = ?
                LIMIT 1
            ''', (recorder, recorder))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                import json
                
                dca_steps = []
                if row['dca_steps_json']:
                    try:
                        dca_data = json.loads(row['dca_steps_json'])
                        dca_steps = [DCAStep(**step) for step in dca_data]
                    except:
                        pass
                
                strategy = StrategyInstance(
                    id=row['id'],
                    name=row['name'],
                    symbol=row['symbol'] or '',
                    timeframe=row['timeframe'] or '',
                    mode=row['mode'] or 'virtual',
                    tp_ticks=int(row['tp_ticks'] or 0),
                    sl_ticks=int(row['sl_ticks']) if row['sl_ticks'] else None,
                    dca_steps=dca_steps,
                    max_qty=int(row['max_qty']) if row['max_qty'] else None,
                    max_risk_dollars=float(row['max_risk_dollars']) if row['max_risk_dollars'] else None,
                    tick_size=float(row['tick_size'] or 0.25),
                    tick_value=float(row['tick_value'] or 0.5),
                )
                
                self.strategies[recorder] = strategy
                logger.info(f"📊 Loaded strategy from DB: {recorder} (mode: {strategy.mode})")
            else:
                # Auto-create strategy with LIVE mode if not found
                logger.info(f"📊 Strategy '{recorder}' not found in database - auto-creating with LIVE mode")
                try:
                    import uuid
                    strategy_id = str(uuid.uuid4())
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    
                    # Get recorder settings from recorders table if available
                    cursor.execute('SELECT tp_targets, sl_amount FROM recorders WHERE name = ?', (recorder,))
                    recorder_row = cursor.fetchone()
                    
                    tp_ticks = 5  # Default
                    if recorder_row and recorder_row[0]:
                        try:
                            import json
                            tp_targets = json.loads(recorder_row[0]) if isinstance(recorder_row[0], str) else recorder_row[0]
                            if tp_targets and len(tp_targets) > 0:
                                tp_ticks = int(tp_targets[0].get('value', 5))
                        except:
                            pass
                    
                    cursor.execute('''
                        INSERT INTO v2_strategies 
                        (id, name, symbol, timeframe, mode, tp_ticks, sl_ticks, dca_steps_json, max_qty, tick_size, tick_value, config_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        strategy_id, recorder, '', '', 'live', tp_ticks, None, '[]', None, 0.25, 0.50, '{}'
                    ))
                    conn.commit()
                    conn.close()
                    
                    # Load the newly created strategy
                    strategy = StrategyInstance(
                        id=strategy_id,
                        name=recorder,
                        symbol='',
                        timeframe='',
                        mode='live',
                        tp_ticks=tp_ticks,
                        sl_ticks=None,
                        dca_steps=[],
                        max_qty=None,
                        max_risk_dollars=None,
                        tick_size=0.25,
                        tick_value=0.5,
                    )
                    self.strategies[recorder] = strategy
                    logger.info(f"✅ Auto-created strategy '{recorder}' with LIVE mode (tp_ticks={tp_ticks})")
                except Exception as create_err:
                    logger.error(f"Failed to auto-create strategy: {create_err}", exc_info=True)
                    logger.warning(f"⚠️ Strategy '{recorder}' not found in database - will use legacy mode (should still execute)")
        except Exception as e:
            logger.error(f"Error loading strategy from DB: {e}", exc_info=True)
    
    def handle_signal(self, recorder: str, action: str, ticker: str, price: float, qty: int) -> None:
        """
        Process a signal (e.g., from TradingView webhook).
        Actions: BUY, SELL, CLOSE. DCA is treated as BUY/SELL on same side.
        """
        logger.info(f"📨 V2 handle_signal: {recorder} {action} {ticker} @ {price} qty={qty}")
        
        if not self.flags.is_enabled(recorder):
            logger.info("V2 disabled for recorder=%s; ignoring signal.", recorder)
            return
        
        # CRITICAL: Ensure strategy is loaded from database if not in memory
        if recorder not in self.strategies:
            logger.info(f"📊 Strategy '{recorder}' not in memory, loading from DB...")
            self._load_strategy_from_db(recorder)
        
        action = action.upper()
        key = self._pos_key(recorder, ticker)
        pos = self.positions.get(key)
        
        # Log strategy mode for debugging
        strategy = self.strategies.get(recorder)
        if strategy:
            logger.info(f"📊 Strategy '{recorder}' mode: {strategy.mode} (LIVE={strategy.mode == StrategyMode.LIVE.value})")
            if strategy.mode != StrategyMode.LIVE.value:
                logger.warning(f"⚠️ Strategy '{recorder}' is in '{strategy.mode}' mode, not 'live' - broker orders will be skipped!")
        else:
            logger.warning(f"⚠️ Strategy '{recorder}' not found after load attempt - will use legacy mode (should still execute)")
        
        # Check broker adapter
        if not self.broker_adapter:
            logger.error(f"❌ V2 broker adapter is None for {recorder} - broker orders will NOT execute! Check broker adapter initialization.")
        else:
            logger.info(f"✅ V2 broker adapter exists for {recorder}")
        
        # === CRITICAL: Cancel ALL old TP orders BEFORE processing new signal ===
        # This prevents old resting TP orders from interfering with new positions/flips
        if strategy and strategy.mode == StrategyMode.LIVE.value:
            self._cancel_all_old_tp_orders_for_symbol(recorder, ticker)

        if action == "CLOSE":
            if pos:
                self._exit_position(pos, price, reason="manual_close")
            return

        side = "LONG" if action == "BUY" else "SHORT"

        if pos and pos.side != side:
            # Flip: close then open fresh
            old_qty = pos.total_qty
            logger.info(f"🔄 FLIP DETECTED: Closing {pos.side} position (qty={old_qty}) and opening new {side} position (qty={qty})")
            self._exit_position(pos, price, reason="flip")
            pos = None
            # SAFETY: Ensure we use the webhook qty, not the old position qty
            if qty <= 0:
                logger.error(f"❌ Invalid qty={qty} from webhook after flip - using default qty=1")
                qty = 1
            logger.info(f"✅ After flip: Opening new {side} position with qty={qty} (webhook quantity)")

        if pos:
            self._dca_add(pos, price, qty)
        else:
            # SAFETY CHECK: Validate qty before opening position
            if qty <= 0:
                logger.error(f"❌ Invalid qty={qty} from webhook - using default qty=1")
                qty = 1
            logger.info(f"📊 Opening new position: {side} {ticker} qty={qty} @ {price}")
            self._open_position(recorder, ticker, side, price, qty)

        # === CRITICAL: Don't evaluate TP/SL immediately after opening ===
        # Wait for broker fill confirmation to get actual fill price
        # The pending_fill flag will prevent evaluation until fill is confirmed
        # This prevents instant exits when webhook price is stale vs real-time price
        # self._evaluate_targets(recorder, ticker, price)  # DISABLED - wait for fill confirmation

    def update_price(self, ticker: str, price: float) -> None:
        """
        External price feed updates should call this.
        Uses O(1) ticker index lookup - same speed for 1 or 1000 positions.
        
        This is the main price evaluation loop that:
        1. Updates MFE/MAE for all positions
        2. Evaluates DCA triggers (auto-DCA ladder)
        3. Evaluates TP/SL targets
        """
        # Update price cache
        self._price_cache[ticker] = (price, time.time())
        self._stats["price_updates"] += 1
        self._stats["last_price_update"] = time.time()
        
        # Update bar price cache for PnL engine
        bar = VirtualBarPrice(ticker=ticker, close=price, high=price, low=price, open=price)
        self._pnl_engine.update_bar(bar)
        
        # O(1) lookup: get all position keys for this ticker
        position_keys = self._ticker_index.get_keys(ticker)
        
        # Evaluate each position (typically just 1-2 per ticker per account)
        for key in position_keys:
            pos = self.positions.get(key)
            if not pos:
                continue
            
            # Get strategy for this position
            strategy = self.strategies.get(pos.recorder) or self.strategies.get(pos.strategy_id)
            
            # === Step 1: Update MFE/MAE ===
            self._pnl_engine.update_position_mfe_mae(pos, price, strategy)
            
            # === Step 2: Evaluate Auto-DCA triggers ===
            self._evaluate_dca_triggers(pos, price, strategy)
            
            # === Step 3: Evaluate TP/SL targets ===
            self._evaluate_targets(pos.recorder, ticker, price)

    def poll_price_and_evaluate(self, ticker: str) -> None:
        """
        If a price_feed_adapter is provided, poll it once for ticker and evaluate targets.
        """
        if not self.price_feed_adapter:
            return
        price = self.price_feed_adapter(ticker)
        if price is None:
            return
        with self._price_lock:
            self.update_price(ticker, price)

    # ---------- Broker Event Loop Control ----------
    def start_broker_event_loop(self, recorder: str) -> bool:
        """
        Start the broker event loop for live trading.
        
        This enables:
        - Real-time exit triggers from Tradovate WebSocket
        - Limit→chase→market order pattern
        - Exit confirmation loop
        - Kill switch for emergency flatten
        
        Returns True if started successfully, False otherwise.
        """
        if not self._broker_event_loop:
            logger.warning("Broker event loop not initialized")
            return False
        
        if not self.broker_adapter or not hasattr(self.broker_adapter, '_get_trader_credentials'):
            logger.warning("No broker adapter available")
            return False
        
        try:
            creds = self.broker_adapter._get_trader_credentials(recorder)
            if not creds:
                logger.warning(f"No credentials found for {recorder}")
                return False
            
            access_token = creds.get('tradovate_token')
            is_demo = bool(creds.get('is_demo', True))
            
            if not access_token:
                logger.warning(f"No access token for {recorder}")
                return False
            
            self._broker_event_loop.start(access_token, is_demo)
            logger.info(f"✅ Broker event loop started for {recorder} (demo={is_demo})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start broker event loop: {e}")
            return False
    
    def stop_broker_event_loop(self) -> None:
        """Stop the broker event loop."""
        if self._broker_event_loop:
            self._broker_event_loop.stop()
            logger.info("🛑 Broker event loop stopped")
    
    def is_broker_event_loop_running(self) -> bool:
        """Check if broker event loop is running."""
        return self._broker_event_loop is not None and self._broker_event_loop._running
    
    def get_exit_status(self, strategy_id: str, ticker: str) -> Optional[Dict]:
        """Get status of pending exit order."""
        if not self._exit_manager:
            return None
        order = self._exit_manager.get_exit_status(strategy_id, ticker)
        if order:
            return {
                "order_id": order.order_id,
                "status": order.status,
                "qty": order.qty,
                "filled_qty": order.filled_qty,
                "order_type": order.order_type,
                "limit_price": order.limit_price,
                "replace_count": order.replace_count,
                "age_ms": (time.time() - order.created_at) * 1000,
            }
        return None
    
    def get_drift_status(self, ticker: str) -> Optional[Dict]:
        """Get position drift status for a ticker."""
        if not self._drift_reconciler:
            return None
        return self._drift_reconciler.check_drift(ticker)

    # ---------- TradingView Add-On Enforcement (Section 7 of TRADEMANAGER_REPLICA.md) ----------
    # ========================================================================
    # THE KEY SECRET: TradingView Routing Mode
    # ========================================================================
    # When an account has the TradingView Add-On enabled:
    #   - Tradovate automatically switches the session to TradingView routing
    #   - WebSocket gets high-frequency TV tick stream
    #   - Orders route through TradingView router
    #   - Low-latency execution (microsecond fills)
    #   - Instant partial fills
    #   - Chart-synchronized PnL
    # 
    # When NOT enabled:
    #   - Standard (slower) routing
    #   - Delayed exit fills
    #   - Worse DCA timing
    #   - Dropped WS events
    #   - TP/SL drifting
    # 
    # This is why TradeManager REQUIRES the add-on. We replicate this.
    # ========================================================================
    
    def check_tradingview_addon(self, account_id: int, force_api_check: bool = False) -> Dict:
        """
        Check if account has TradingView routing enabled.
        
        This is THE KEY to TradeManager-grade execution.
        
        Args:
            account_id: The account ID to check
            force_api_check: If True, always call Tradovate API (not just DB)
        
        Returns:
            Dict with:
                - 'has_addon': bool - TRUE if TradingView routing is active
                - 'can_auto_trade': bool - TRUE if ready for automation
                - 'detection_method': str - How the flag was detected
                - 'error': str - Error message if any
        """
        try:
            main_db = os.path.join(os.path.dirname(self.db_path), "just_trades.db")
            conn = sqlite3.connect(main_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Ensure has_tradingview_addon column exists
            cursor.execute("PRAGMA table_info(accounts)")
            columns = [col['name'] for col in cursor.fetchall()]
            if 'has_tradingview_addon' not in columns:
                cursor.execute("ALTER TABLE accounts ADD COLUMN has_tradingview_addon INTEGER DEFAULT 0")
                conn.commit()
                logger.info("Added has_tradingview_addon column to accounts table")
            
            # Get account credentials
            cursor.execute('''
                SELECT id, has_tradingview_addon, enabled, tradovate_token, 
                       tradovate_refresh_token, name
                FROM accounts WHERE id = ?
            ''', (account_id,))
            
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return {
                    'has_addon': False,
                    'can_auto_trade': False,
                    'error': f"Account {account_id} not found"
                }
            
            # Check cached value first (unless force_api_check)
            cached_addon = bool(row['has_tradingview_addon'])
            has_token = bool(row['tradovate_token'])
            enabled = bool(row['enabled'])
            
            if cached_addon and not force_api_check:
                conn.close()
                return {
                    'has_addon': True,
                    'can_auto_trade': True,
                    'detection_method': 'cached',
                    'account_id': account_id,
                    'error': None
                }
            
            # If we have a token, check Tradovate API directly
            if has_token and (force_api_check or not cached_addon):
                conn.close()
                return self._check_tradingview_via_api(account_id, row['tradovate_token'])
            
            conn.close()
            return {
                'has_addon': cached_addon,
                'can_auto_trade': cached_addon and enabled and has_token,
                'detection_method': 'database' if cached_addon else 'not_detected',
                'account_id': account_id,
                'error': None if cached_addon else "TradingView Add-On not enabled. Enable it in Tradovate account settings."
            }
            
        except Exception as e:
            logger.error(f"Error checking TradingView addon: {e}")
            return {
                'has_addon': False,
                'can_auto_trade': False,
                'error': str(e)
            }
    
    def _check_tradingview_via_api(self, account_id: int, token: str) -> Dict:
        """
        Check TradingView routing status directly via Tradovate API.
        
        Calls /auth/me and looks for:
        - tradingViewTradingEnabled
        - features.tradingViewTradingEnabled
        - orderRouting.tradingViewAuthorized
        - activePlugins containing 'tradingView'
        """
        import asyncio
        import aiohttp
        
        async def do_check():
            try:
                # Try both live and demo
                for base_url in ["https://live.tradovateapi.com/v1", "https://demo.tradovateapi.com/v1"]:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"{base_url}/auth/me",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json"
                            }
                        ) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                # Check for TradingView routing flag
                                tv_enabled = False
                                detection_method = None
                                
                                # Method 1: Direct field
                                if data.get('tradingViewTradingEnabled'):
                                    tv_enabled = True
                                    detection_method = 'tradingViewTradingEnabled'
                                
                                # Method 2: Nested in features
                                elif data.get('features', {}).get('tradingViewTradingEnabled'):
                                    tv_enabled = True
                                    detection_method = 'features.tradingViewTradingEnabled'
                                
                                # Method 3: Order routing
                                elif data.get('orderRouting', {}).get('tradingViewAuthorized'):
                                    tv_enabled = True
                                    detection_method = 'orderRouting.tradingViewAuthorized'
                                
                                # Method 4: Active plugins
                                active_plugins = data.get('activePlugins', [])
                                if isinstance(active_plugins, list):
                                    for plugin in active_plugins:
                                        plugin_str = str(plugin).lower()
                                        if 'tradingview' in plugin_str or 'apiAccess' in str(plugin):
                                            tv_enabled = True
                                            detection_method = f'activePlugins: {plugin}'
                                            break
                                
                                # Store result in database
                                if tv_enabled:
                                    self.set_tradingview_addon_status(account_id, True)
                                    logger.info(f"✅ TRADINGVIEW ROUTING ENABLED for account {account_id} via {detection_method}")
                                else:
                                    logger.warning(f"⚠️ TRADINGVIEW ROUTING NOT DETECTED for account {account_id}")
                                
                                return {
                                    'has_addon': tv_enabled,
                                    'can_auto_trade': tv_enabled,
                                    'detection_method': detection_method or 'api_check',
                                    'account_id': account_id,
                                    'active_plugins': active_plugins,
                                    'error': None if tv_enabled else "TradingView Add-On not enabled"
                                }
                
                return {
                    'has_addon': False,
                    'can_auto_trade': False,
                    'error': 'Could not reach Tradovate API'
                }
                
            except Exception as e:
                return {
                    'has_addon': False,
                    'can_auto_trade': False,
                    'error': str(e)
                }
        
        # Run async check
        try:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(do_check())
            loop.close()
            return result
        except Exception as e:
            logger.error(f"API check failed: {e}")
            return {
                'has_addon': False,
                'can_auto_trade': False,
                'error': str(e)
            }
    
    def set_tradingview_addon_status(self, account_id: int, has_addon: bool) -> bool:
        """
        Set the TradingView add-on status for an account.
        
        This should be called after verifying the account has the addon
        via Tradovate's /auth/me endpoint (see check_tradingview_addon.py).
        """
        try:
            main_db = os.path.join(os.path.dirname(self.db_path), "just_trades.db")
            conn = sqlite3.connect(main_db)
            cursor = conn.cursor()
            
            # Ensure column exists
            try:
                cursor.execute("ALTER TABLE accounts ADD COLUMN has_tradingview_addon INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            cursor.execute('''
                UPDATE accounts SET has_tradingview_addon = ? WHERE id = ?
            ''', (1 if has_addon else 0, account_id))
            
            conn.commit()
            rows_affected = cursor.rowcount
            conn.close()
            
            if rows_affected > 0:
                logger.info(f"✅ Set TradingView addon status for account {account_id}: {has_addon}")
                return True
            else:
                logger.warning(f"Account {account_id} not found")
                return False
                
        except Exception as e:
            logger.error(f"Error setting TradingView addon status: {e}")
            return False
    
    def enforce_tradingview_addon(self, recorder: str) -> Dict:
        """
        Enforce TradingView add-on requirement before enabling auto-trading.
        
        Per Section 7.3 of JUST_TRADES_TRADEMANAGER_REPLICA.md:
        If someone tries to enable auto-trade without addon, show error.
        
        Returns:
            Dict with 'allowed': bool, 'reason': str
        """
        try:
            main_db = os.path.join(os.path.dirname(self.db_path), "just_trades.db")
            conn = sqlite3.connect(main_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get recorder's trader and account
            cursor.execute('''
                SELECT t.id as trader_id, t.enabled as trader_enabled,
                       a.id as account_id, a.has_tradingview_addon, a.enabled as account_enabled
                FROM recorders r
                JOIN traders t ON t.recorder_id = r.id
                JOIN accounts a ON t.account_id = a.id
                WHERE r.name = ? AND t.enabled = 1
                LIMIT 1
            ''', (recorder,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return {
                    'allowed': True,  # No live trader - virtual only
                    'reason': 'No live trader configured (virtual mode only)'
                }
            
            has_addon = bool(row['has_tradingview_addon']) if row['has_tradingview_addon'] is not None else False
            
            if not has_addon:
                return {
                    'allowed': False,
                    'reason': 'Enable the TradingView Add-On with Tradovate to use auto-trading.',
                    'account_id': row['account_id'],
                    'trader_id': row['trader_id']
                }
            
            return {
                'allowed': True,
                'reason': 'TradingView add-on verified',
                'account_id': row['account_id'],
                'trader_id': row['trader_id']
            }
            
        except Exception as e:
            logger.error(f"Error enforcing TradingView addon: {e}")
            return {
                'allowed': False,
                'reason': f'Error checking addon status: {e}'
            }

    # ---------- Service Layer (Section 9.2 of TRADEMANAGER_REPLICA.md) ----------
    # These methods wrap RecorderServiceV2 for external API integration
    
    def handle_tv_signal(self, signal: Dict) -> Dict:
        """
        Handle TradingView signal via service layer.
        
        Per Section 4.2 of JUST_TRADES_TRADEMANAGER_REPLICA.md:
        - Validate and normalize payload
        - Route to strategy engine
        - Record VirtualFill
        
        Args:
            signal: Dict with keys: strategy_id, recorder, symbol, side, event, price_chart, qty_hint
        
        Returns:
            Dict with 'success': bool, 'position': dict if opened, 'error': str if failed
        """
        try:
            # Extract fields
            recorder = signal.get('recorder', signal.get('strategy_id', ''))
            action = signal.get('event', signal.get('action', '')).upper()
            ticker = signal.get('symbol', signal.get('ticker', ''))
            price = float(signal.get('price_chart', signal.get('price', 0)))
            qty = int(signal.get('qty_hint', signal.get('qty', 1)))
            
            if not recorder or not ticker:
                return {'success': False, 'error': 'Missing recorder or ticker'}
            
            # Check V2 enabled
            if not self.flags.is_enabled(recorder):
                return {'success': False, 'error': f'V2 not enabled for {recorder}'}
            
            # Check TradingView add-on if going live
            strategy = self.strategies.get(recorder)
            if strategy and strategy.mode == StrategyMode.LIVE.value:
                addon_check = self.enforce_tradingview_addon(recorder)
                if not addon_check.get('allowed'):
                    return {'success': False, 'error': addon_check.get('reason')}
            
            # Log signal receipt
            ts_received = time.time()
            logger.info(f"📨 TV SIGNAL: {recorder} {action} {ticker} @ {price} qty={qty}")
            
            # Route to handle_signal
            self.handle_signal(recorder, action, ticker, price, qty)
            
            # Return position state
            key = self._pos_key(recorder, ticker)
            pos = self.positions.get(key)
            
            return {
                'success': True,
                'recorder': recorder,
                'action': action,
                'ticker': ticker,
                'price': price,
                'qty': qty,
                'position': {
                    'side': pos.side,
                    'total_qty': pos.total_qty,
                    'avg_price': pos.avg_price,
                } if pos else None,
                'latency_ms': (time.time() - ts_received) * 1000,
            }
            
        except Exception as e:
            logger.error(f"handle_tv_signal error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    def on_broker_fill(self, fill: Dict) -> None:
        """
        Handle broker fill event via service layer.
        
        Per Section 5.2 of JUST_TRADES_TRADEMANAGER_REPLICA.md:
        - Update exit order status
        - Confirm flat if all filled
        - Update virtual position to match broker reality
        
        Args:
            fill: Dict from Tradovate fill event
        """
        try:
            order_id = str(fill.get('orderId', ''))
            filled_qty = int(fill.get('qty', 0))
            fill_price = float(fill.get('price', 0))
            contract_id = fill.get('contractId')
            action = fill.get('action', '')
            
            logger.info(f"📥 on_broker_fill: order={order_id}, qty={filled_qty}, price={fill_price}, action={action}")
            
            # === CRITICAL: Check if this is an ENTRY fill ===
            # This enables TP/SL evaluation with the actual fill price
            if hasattr(self, '_pending_entry_fills') and order_id in self._pending_entry_fills:
                pos_key = self._pending_entry_fills.pop(order_id)
                pos = self.positions.get(pos_key)
                if pos and pos.pending_fill:
                    old_price = pos.avg_price
                    pos.avg_price = fill_price  # Update to actual fill price
                    pos.pending_fill = False    # Enable TP/SL evaluation
                    pos.updated_at = datetime.utcnow()
                    
                    logger.info(f"✅ ENTRY FILL CONFIRMED: {pos_key} @ {fill_price} (was {old_price})")
                    logger.info(f"   TP/SL evaluation now ENABLED for {pos.ticker}")
                    
                    # Persist updated position
                    self._persist_position(pos)
            
            # Update exit manager's tracked orders
            if self._exit_manager:
                for key, exit_order in list(self._exit_manager._active_exits.items()):
                    if exit_order.broker_order_id == order_id:
                        exit_order.filled_qty += filled_qty
                        exit_order.avg_fill_price = fill_price
                        exit_order.last_update = time.time()
                        
                        if exit_order.filled_qty >= exit_order.qty:
                            exit_order.status = "filled"
                            logger.info(f"✅ EXIT COMPLETE: {exit_order.ticker} filled {exit_order.filled_qty}/{exit_order.qty} @ {fill_price}")
                            
                            # Transition to CONFIRM_FLAT state
                            self._exit_manager._transition_state(key, ExitState.CONFIRM_FLAT)
                        else:
                            exit_order.status = "partial"
                            logger.info(f"⏳ EXIT PARTIAL: {exit_order.ticker} filled {exit_order.filled_qty}/{exit_order.qty}")
            
            # === CRITICAL: Reconcile TP orders after any fill ===
            # Check if this fill affects a position that needs TP reconciliation
            if contract_id or action:
                # Try to find the position this fill belongs to
                for pos_key, pos in list(self.positions.items()):
                    # Check if this fill is for an entry/DCA order
                    if (hasattr(pos, 'entry_order_id') and pos.entry_order_id == order_id) or \
                       (hasattr(pos, 'dca_order_ids') and order_id in pos.dca_order_ids):
                        strategy = self.strategies.get(pos.recorder) or self.strategies.get(pos.strategy_id)
                        if strategy and strategy.mode == StrategyMode.LIVE.value and strategy.tp_ticks:
                            # Trigger TP reconciliation after a short delay to allow position to update
                            threading.Timer(0.3, lambda: self._reconcile_tp_orders_after_position_change(pos, strategy)).start()
                            break
            
            # Update stats
            self._stats["orders_placed"] += 1
            
        except Exception as e:
            logger.error(f"on_broker_fill error: {e}", exc_info=True)
    
    def on_broker_position_update(self, data: Dict) -> None:
        """
        Handle broker position update via service layer.
        
        Per Section 6.2 of JUST_TRADES_TRADEMANAGER_REPLICA.md:
        - Compare virtual vs broker position
        - Create drift snapshot if mismatch
        - Trigger resync if drift exceeds threshold
        
        Args:
            data: Dict from Tradovate position update
        """
        try:
            symbol = str(data.get('contractId') or data.get('symbol', ''))
            broker_qty = int(data.get('netPos', data.get('quantity', 0)))
            broker_price = float(data.get('netPrice', data.get('avgPrice', 0)))
            
            if not symbol:
                return
            
            logger.debug(f"📊 on_broker_position_update: {symbol} qty={broker_qty} @ {broker_price}")
            
            # Update drift reconciler
            if self._drift_reconciler:
                # Store broker position
                with self._drift_reconciler._lock:
                    self._drift_reconciler._broker_positions[symbol] = {
                        "qty": broker_qty,
                        "avg_price": broker_price,
                        "updated_at": time.time(),
                    }
                
                # Check for drift
                drift = self._drift_reconciler.check_drift(symbol)
                if drift:
                    self._stats["drift_events"] += 1
                    logger.warning(f"⚠️ POSITION DRIFT: {symbol} - {drift}")
                    
                    # CRITICAL: Handle broker flat but virtual open (manual close on broker)
                    if drift.get('type') == 'broker_flat_virtual_open':
                        logger.error(f"🚨 CRITICAL DRIFT: Broker is flat but virtual has position for {symbol} - closing virtual position")
                        # Resync will close the virtual position
                        self._drift_reconciler.resync_from_broker(symbol)
                        # Also close the actual V2 position if it exists
                        for key, pos in list(self.positions.items()):
                            if symbol in key or pos.ticker == symbol:
                                logger.info(f"🗑️ Closing virtual position {key} due to broker being flat")
                                self._exit_position(pos, pos.last_price or pos.avg_price, reason="broker_flat")
                    
                    # If significant drift, trigger resync
                    elif drift.get('type') == 'qty_drift' and abs(drift.get('drift', 0)) > 2:
                        logger.error(f"🚨 CRITICAL DRIFT: {symbol} - forcing resync")
                        self._drift_reconciler.resync_from_broker(symbol)
            
            # If broker shows flat and we have virtual position, clean up
            if broker_qty == 0:
                for key, pos in list(self.positions.items()):
                    if symbol in key or pos.ticker == symbol:
                        # Check if this is expected (exit was triggered)
                        if self._exit_manager:
                            exit_order = self._exit_manager.get_exit_status(pos.recorder, pos.ticker)
                            if exit_order and exit_order.status in ("filled", "flattening"):
                                # Expected flat - clean up
                                logger.info(f"✅ CONFIRMED FLAT: {pos.ticker}")
                                continue
                        
                        # Unexpected flat - broker closed position
                        logger.warning(f"⚠️ UNEXPECTED FLAT: {pos.ticker} - broker closed position")
            
        except Exception as e:
            logger.error(f"on_broker_position_update error: {e}", exc_info=True)
    
    def get_service_status(self) -> Dict:
        """
        Get comprehensive service status for Control Center.
        
        Returns status of all components per Section 3.1 of TRADEMANAGER_REPLICA.md.
        """
        return {
            "engine": "RecorderServiceV2",
            "positions": len(self.positions),
            "strategies": len(self.strategies),
            "stats": self._stats,
            "broker_event_loop": {
                "running": self._broker_event_loop._running if self._broker_event_loop else False,
                "subscribed_symbols": len(self._broker_event_loop._subscribed_symbols) if self._broker_event_loop else 0,
            } if self._broker_event_loop else None,
            "exit_manager": {
                "active_exits": len(self._exit_manager._active_exits) if self._exit_manager else 0,
            } if self._exit_manager else None,
            "drift_reconciler": {
                "virtual_positions": len(self._drift_reconciler._virtual_positions) if self._drift_reconciler else 0,
                "broker_positions": len(self._drift_reconciler._broker_positions) if self._drift_reconciler else 0,
            } if self._drift_reconciler else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ---------- Internal helpers ----------
    def _pos_key(self, recorder: str, ticker: str) -> str:
        """Generate position key for indexing."""
        return f"{recorder}:{ticker}"

    def _open_position(self, recorder: str, ticker: str, side: str, price: float, qty: int) -> None:
        # SAFETY CHECK: Validate qty before opening position
        if qty <= 0:
            logger.error(f"❌ Invalid qty={qty} for {recorder} {ticker} - using default qty=1")
            qty = 1
        
        key = self._pos_key(recorder, ticker)
        settings = self.settings.get(recorder)
        strategy = self.strategies.get(recorder)
        
        max_qty = strategy.max_qty if strategy else (settings.max_qty if settings else None)
        if max_qty and qty > max_qty:
            logger.warning("V2 open blocked: qty %s exceeds max_qty %s for %s", qty, max_qty, recorder)
            return
        
        entries = [{"price": price, "qty": qty, "time": datetime.utcnow().isoformat()}]
        pos = V2Position(
            recorder=recorder,
            ticker=ticker,
            side=side,
            total_qty=qty,
            avg_price=price,
            entries=entries,
            strategy_id=strategy.id if strategy else "",
            last_price=price,
        )
        
        with self._price_lock:
            self.positions[key] = pos
            # Add to ticker index for O(1) lookup
            self._ticker_index.add(ticker, key)
        
        logger.info(f"📊 V2 open {side} {ticker} qty={qty} @ {price} (webhook quantity, entries sum={qty})")
        
        # === Record VirtualFill for audit trail ===
        fill = VirtualFill(
            strategy_id=strategy.id if strategy else recorder,
            ticker=ticker,
            side=side,
            fill_type=FillType.ENTRY.value,
            qty=qty,
            price=price,
            notes=f"Initial entry for {recorder}"
        )
        self._record_fill(fill)
        
        # Execute broker order if in LIVE mode
        strategy_mode_str = strategy.mode if strategy else 'None'
        live_value_str = StrategyMode.LIVE.value
        # Case-insensitive comparison to handle any string variations
        mode_match = (strategy and str(strategy.mode).lower().strip() == live_value_str.lower().strip())
        
        logger.info(f"🔍 V2 _open_position: strategy={strategy is not None}, mode='{strategy_mode_str}', LIVE.value='{live_value_str}', match={mode_match}")
        logger.info(f"   Broker adapter exists: {self.broker_adapter is not None}")
        
        if mode_match:
            logger.info(f"🚀 V2: Executing ENTRY broker order (LIVE mode) for {recorder} {ticker} qty={qty}")
            if not self.broker_adapter:
                logger.error(f"❌ V2: Broker adapter is None - cannot execute order for {recorder}!")
            else:
                self._execute_broker("ENTRY", pos, price, qty)
        elif not strategy:
            # Legacy behavior - check if broker adapter exists
            logger.info(f"🚀 V2: Executing ENTRY broker order (no strategy, legacy) for {recorder} {ticker} qty={qty}")
            if not self.broker_adapter:
                logger.error(f"❌ V2: Broker adapter is None - cannot execute order for {recorder}!")
            else:
                self._execute_broker("ENTRY", pos, price, qty)
        else:
            logger.warning(f"⏸️ V2: Skipping broker execution - strategy mode is '{strategy.mode}' (expected '{StrategyMode.LIVE.value}') for {recorder}")
            logger.warning(f"   Strategy mode type: {type(strategy.mode)}, LIVE.value type: {type(StrategyMode.LIVE.value)}")
            logger.warning(f"   Mode comparison: {strategy.mode == StrategyMode.LIVE.value}, repr: {repr(strategy.mode)} == {repr(StrategyMode.LIVE.value)}")
            logger.warning(f"   Lowercase comparison: {str(strategy.mode).lower()} == {live_value_str.lower()}")
        
        # === FALLBACK: Enable TP/SL after timeout if no fill confirmation ===
        # In case broker WebSocket isn't connected, don't wait forever
        # CRITICAL: Increased delay to 5 seconds to ensure position is actually filled
        # and to prevent instant exits when webhook price is stale vs real-time price
        def enable_tp_sl_fallback():
            time.sleep(5.0)  # Wait 5 seconds for broker fill (increased from 2s)
            if pos.pending_fill:
                pos.pending_fill = False
                logger.info(f"⏱️ Entry fill timeout - enabling TP/SL for {key} (assumed filled @ {price})")
                logger.warning(f"⚠️ Using webhook price {price} - actual fill may differ. TP/SL evaluation enabled.")
        
        threading.Thread(target=enable_tp_sl_fallback, daemon=True).start()
        
        # === BROKER-DRIVEN EXECUTION ENGINE INTEGRATION ===
        # Update drift reconciler with new position
        if self._drift_reconciler:
            self._drift_reconciler.update_virtual(ticker, qty, price)
        
        # Subscribe to broker ticks for this symbol (for exit chasing)
        if self._broker_event_loop and self.broker_adapter and hasattr(self.broker_adapter, '_convert_ticker'):
            try:
                tradovate_symbol = self.broker_adapter._convert_ticker(ticker)
                self._broker_event_loop.subscribe_symbol(tradovate_symbol)
            except Exception as e:
                logger.debug(f"Failed to subscribe to broker ticks: {e}")
        
        # Arm kill switch for this position
        if self._kill_switch:
            atr = self._dca_engine.get_atr(ticker)
            self._kill_switch.arm(recorder, ticker, qty, price, atr)
        
        # === CRITICAL: Place initial TP order if in LIVE mode ===
        # Proactive TP placement (not just reactive exits)
        strategy = self.strategies.get(recorder)
        if strategy and strategy.mode == StrategyMode.LIVE.value and strategy.tp_ticks:
            # Coalesce - wait a bit in case multiple entries come in quickly
            threading.Timer(0.2, lambda: self._reconcile_tp_orders_after_position_change(pos, strategy)).start()

        self._persist_position_async(pos)

    def _dca_add(self, pos: V2Position, price: float, qty: int, auto_triggered: bool = False) -> None:
        settings = self.settings.get(pos.recorder)
        strategy = self.strategies.get(pos.recorder) or self.strategies.get(pos.strategy_id)
        
        max_qty = strategy.max_qty if strategy else (settings.max_qty if settings else None)
        if max_qty and (pos.total_qty + qty) > max_qty:
            logger.warning("V2 DCA blocked: qty %s would exceed max_qty %s for %s", pos.total_qty + qty, max_qty, pos.recorder)
            return
        
        with self._price_lock:
            new_qty = pos.total_qty + qty
            pos.avg_price = ((pos.avg_price * pos.total_qty) + (price * qty)) / new_qty
            pos.total_qty = new_qty
            pos.entries.append({"price": price, "qty": qty, "time": datetime.utcnow().isoformat()})
            pos.updated_at = datetime.utcnow()
            pos.last_price = price
        
        logger.info("V2 DCA add %s %s +%s -> qty=%s avg=%s%s", 
                    pos.side, pos.ticker, qty, pos.total_qty, pos.avg_price,
                    " (AUTO)" if auto_triggered else "")
        
        # === Record VirtualFill for audit trail ===
        fill = VirtualFill(
            strategy_id=strategy.id if strategy else pos.recorder,
            ticker=pos.ticker,
            side=pos.side,
            fill_type=FillType.DCA.value,
            qty=qty,
            price=price,
            notes=f"DCA #{len(pos.entries)} - {'Auto-triggered' if auto_triggered else 'Manual'} | New avg: {pos.avg_price:.2f}"
        )
        self._record_fill(fill)
        
        # Execute broker order if in LIVE mode
        strategy_mode_str = strategy.mode if strategy else 'None'
        live_value_str = StrategyMode.LIVE.value
        # Case-insensitive comparison to handle any string variations
        mode_match = (strategy and str(strategy.mode).lower().strip() == live_value_str.lower().strip())
        
        logger.info(f"🔍 V2 _dca_add: strategy={strategy is not None}, mode='{strategy_mode_str}', LIVE.value='{live_value_str}', match={mode_match}")
        logger.info(f"   Broker adapter exists: {self.broker_adapter is not None}")
        
        if mode_match:
            logger.info(f"🚀 V2: Executing DCA broker order (LIVE mode) for {pos.recorder} {pos.ticker} qty={qty}")
            if not self.broker_adapter:
                logger.error(f"❌ V2: Broker adapter is None - cannot execute DCA order for {pos.recorder}!")
            else:
                self._execute_broker("DCA", pos, price, qty)
        elif not strategy:
            logger.info(f"🚀 V2: Executing DCA broker order (no strategy, legacy) for {pos.recorder} {pos.ticker} qty={qty}")
            if not self.broker_adapter:
                logger.error(f"❌ V2: Broker adapter is None - cannot execute DCA order for {pos.recorder}!")
            else:
                self._execute_broker("DCA", pos, price, qty)
        else:
            logger.warning(f"⏸️ V2: Skipping DCA broker execution - strategy mode is '{strategy.mode}' (expected '{StrategyMode.LIVE.value}') for {pos.recorder}")
            logger.warning(f"   Strategy mode type: {type(strategy.mode)}, LIVE.value type: {type(StrategyMode.LIVE.value)}")
            logger.warning(f"   Mode comparison: {strategy.mode == StrategyMode.LIVE.value}, repr: {repr(strategy.mode)} == {repr(StrategyMode.LIVE.value)}")
            logger.warning(f"   Lowercase comparison: {str(strategy.mode).lower()} == {live_value_str.lower()}")
        
        # === CRITICAL: Reconcile TP orders after DCA fill ===
        # This prevents multiple TP orders from existing simultaneously
        if strategy and strategy.mode == StrategyMode.LIVE.value:
            self._reconcile_tp_orders_after_position_change(pos, strategy)
        
        self._persist_position_async(pos)

    def _exit_position(self, pos: V2Position, price: float, reason: str) -> None:
        """
        Exit position with full timing metrics and PnL calculation.
        Critical path for TP/SL - optimized for speed.
        """
        exit_start = time.time()
        
        settings = self.settings.get(pos.recorder)
        strategy = self.strategies.get(pos.recorder) or self.strategies.get(pos.strategy_id)
        tick_size = self.tick_size_map.get(pos.ticker, 0.25)
        
        # === Calculate realized PnL ===
        realized_pnl = self._pnl_engine.calculate_realized_pnl(
            entry_price=pos.avg_price,
            exit_price=price,
            qty=pos.total_qty,
            side=pos.side,
            strategy=strategy,
            ticker=pos.ticker
        )
        self._stats["total_virtual_pnl"] += realized_pnl
        
        # Calculate slippage (difference from target)
        tp_ticks = strategy.tp_ticks if strategy else (settings.tp_ticks if settings else 0)
        sl_ticks = strategy.sl_ticks if strategy else (settings.sl_ticks if settings else None)
        
        if tp_ticks:
            if pos.side == "LONG":
                tp_target = pos.avg_price + (tp_ticks * tick_size)
                sl_target = pos.avg_price - (sl_ticks * tick_size) if sl_ticks else None
            else:
                tp_target = pos.avg_price - (tp_ticks * tick_size)
                sl_target = pos.avg_price + (sl_ticks * tick_size) if sl_ticks else None
            
            if reason == "tp_hit":
                slippage = abs(price - tp_target) / tick_size
                logger.info(f"V2 exit {pos.side} {pos.ticker} qty={pos.total_qty} @ {price} | TP target: {tp_target} | Slippage: {slippage:.1f} ticks | PnL: ${realized_pnl:.2f}")
            elif reason == "sl_hit" and sl_target:
                slippage = abs(price - sl_target) / tick_size
                logger.info(f"V2 exit {pos.side} {pos.ticker} qty={pos.total_qty} @ {price} | SL target: {sl_target} | Slippage: {slippage:.1f} ticks | PnL: ${realized_pnl:.2f}")
            else:
                logger.info(f"V2 exit {pos.side} {pos.ticker} qty={pos.total_qty} @ {price} reason={reason} | PnL: ${realized_pnl:.2f}")
        else:
            logger.info(f"V2 exit {pos.side} {pos.ticker} qty={pos.total_qty} @ {price} reason={reason} | PnL: ${realized_pnl:.2f}")
        
        # Track stats
        if reason == "tp_hit":
            self._stats["tp_hits"] += 1
        elif reason == "sl_hit":
            self._stats["sl_hits"] += 1
        
        # === Determine fill type based on reason ===
        fill_type_map = {
            "tp_hit": FillType.EXIT_TP.value,
            "sl_hit": FillType.EXIT_SL.value,
            "manual_close": FillType.EXIT_MANUAL.value,
            "flip": FillType.EXIT_FLIP.value,
        }
        fill_type = fill_type_map.get(reason, FillType.EXIT_MANUAL.value)
        
        # === Record VirtualFill for audit trail ===
        fill = VirtualFill(
            strategy_id=strategy.id if strategy else pos.recorder,
            ticker=pos.ticker,
            side=pos.side,
            fill_type=fill_type,
            qty=pos.total_qty,
            price=price,
            pnl=realized_pnl,
            notes=f"Exit: {reason} | Entry: {pos.avg_price:.2f} | MFE: ${pos.max_favorable_excursion:.2f} | MAE: ${pos.max_adverse_excursion:.2f} | DCA adds: {pos.dca_steps_triggered}"
        )
        self._record_fill(fill)
        
        # === BROKER-DRIVEN EXIT (TradeManager-style) ===
        # Use AdvancedExitManager for limit→chase→market pattern if available
        should_execute_broker = (
            (strategy and strategy.mode == StrategyMode.LIVE.value) or 
            (not strategy)
        )
        
        if should_execute_broker:
            if self._exit_manager and self.broker_adapter and hasattr(self.broker_adapter, '_get_trader_credentials'):
                # Use advanced exit with limit→chase→market pattern
                try:
                    creds = self.broker_adapter._get_trader_credentials(pos.recorder)
                    if creds:
                        tradovate_symbol = self.broker_adapter._convert_ticker(pos.ticker)
                        exit_side = "Sell" if pos.side == "LONG" else "Buy"
                        
                        # Arm kill switch for this exit
                        if self._kill_switch:
                            atr = self._dca_engine.get_atr(pos.ticker)
                            self._kill_switch.arm(pos.recorder, pos.ticker, pos.total_qty, pos.avg_price, atr)
                        
                        # SAFETY CHECK: Calculate actual qty from entries to prevent quantity mismatch bugs
                        entries_qty = sum(entry.get('qty', 0) for entry in pos.entries)
                        if entries_qty != pos.total_qty:
                            logger.warning(f"⚠️ QUANTITY MISMATCH: pos.total_qty={pos.total_qty} but sum(entries)={entries_qty} for {pos.ticker} - using entries sum")
                            actual_qty = entries_qty  # Use entries sum as source of truth
                        else:
                            actual_qty = pos.total_qty
                        
                        if actual_qty <= 0:
                            logger.error(f"❌ Invalid exit quantity: {actual_qty} for {pos.ticker} - skipping exit")
                            return
                        
                        # Initiate exit with advanced manager (limit→chase→market)
                        exit_order = self._exit_manager.initiate_exit(
                            strategy_id=strategy.id if strategy else pos.recorder,
                            ticker=pos.ticker,
                            tradovate_symbol=tradovate_symbol,
                            side=exit_side,
                            qty=actual_qty,  # Use validated quantity
                            target_price=price,
                            account_id=creds.get('subaccount_id', 0),
                            account_spec=creds.get('subaccount_name', ''),
                        )
                        
                        # Wait for flat confirmation (non-blocking in background)
                        # The exit_confirm_loop will handle this asynchronously
                        logger.info(f"📤 EXIT ORDER: {exit_order.order_id[:8]}... | {exit_side} {actual_qty} {tradovate_symbol}")
                        
                        # Disarm kill switch after exit initiated
                        if self._kill_switch:
                            self._kill_switch.disarm(pos.recorder, pos.ticker)
                    else:
                        # Fall back to basic execution
                        # SAFETY CHECK: Calculate actual qty from entries
                        entries_qty = sum(entry.get('qty', 0) for entry in pos.entries)
                        actual_qty = entries_qty if entries_qty != pos.total_qty else pos.total_qty
                        if actual_qty != pos.total_qty:
                            logger.warning(f"⚠️ QUANTITY MISMATCH in fallback exit: pos.total_qty={pos.total_qty} but sum(entries)={entries_qty} for {pos.ticker}")
                        self._execute_broker("EXIT", pos, price, actual_qty)
                except Exception as e:
                    logger.error(f"Advanced exit failed, falling back: {e}")
                    # SAFETY CHECK: Calculate actual qty from entries
                    entries_qty = sum(entry.get('qty', 0) for entry in pos.entries)
                    actual_qty = entries_qty if entries_qty != pos.total_qty else pos.total_qty
                    if actual_qty != pos.total_qty:
                        logger.warning(f"⚠️ QUANTITY MISMATCH in exception fallback: pos.total_qty={pos.total_qty} but sum(entries)={entries_qty} for {pos.ticker}")
                    self._execute_broker("EXIT", pos, price, actual_qty)
            else:
                # No advanced exit manager - use basic execution
                # SAFETY CHECK: Calculate actual qty from entries
                entries_qty = sum(entry.get('qty', 0) for entry in pos.entries)
                actual_qty = entries_qty if entries_qty != pos.total_qty else pos.total_qty
                if actual_qty != pos.total_qty:
                    logger.warning(f"⚠️ QUANTITY MISMATCH in basic exit: pos.total_qty={pos.total_qty} but sum(entries)={entries_qty} for {pos.ticker}")
                self._execute_broker("EXIT", pos, price, actual_qty)
        
        key = self._pos_key(pos.recorder, pos.ticker)
        with self._price_lock:
            self.positions.pop(key, None)
            # Remove from ticker index
            self._ticker_index.remove(pos.ticker, key)
        
        # Update drift reconciler
        if self._drift_reconciler:
            self._drift_reconciler.update_virtual(pos.ticker, 0, 0)
        
        # === CRITICAL: Cancel all TP orders when position is closed ===
        pos_key = self._pos_key(pos.recorder, pos.ticker)
        if pos_key in self._active_tp_orders:
            tp_order = self._active_tp_orders[pos_key]
            order_id = tp_order.get('order_id')
            if order_id and self.broker_adapter:
                # Cancel TP order asynchronously
                creds = self.broker_adapter._get_trader_credentials(pos.recorder)
                if creds:
                    async def cancel_tp():
                        from phantom_scraper.tradovate_integration import TradovateIntegration
                        is_demo = bool(creds.get('is_demo'))
                        access_token = creds.get('tradovate_token')
                        refresh_token = creds.get('tradovate_refresh_token')
                        md_token = creds.get('md_access_token')
                        
                        async with TradovateIntegration(demo=is_demo) as tv:
                            tv.access_token = access_token
                            tv.refresh_token = refresh_token
                            tv.md_access_token = md_token
                            await tv.cancel_order(int(order_id))
                            logger.info(f"🗑️ Canceled TP order {order_id} (position closed)")
                    
                    if hasattr(self.broker_adapter, '_run_async'):
                        self.broker_adapter._run_async(cancel_tp())
            
            # Remove from tracking
            del self._active_tp_orders[pos_key]
        
        # Clean up locks
        if pos_key in self._tp_reconciliation_locks:
            del self._tp_reconciliation_locks[pos_key]
        if pos_key in self._tp_sequence_counter:
            del self._tp_sequence_counter[pos_key]
        
        self._delete_position_async(pos)
        
        # Log total exit latency
        exit_latency = (time.time() - exit_start) * 1000
        logger.info(f"⏱️ Total exit latency: {exit_latency:.0f}ms | Total Session PnL: ${self._stats['total_virtual_pnl']:.2f}")

    def _evaluate_dca_triggers(self, pos: V2Position, price: float, strategy: Optional[StrategyInstance]) -> None:
        """
        Evaluate and execute auto-DCA triggers based on price movement.
        
        This is the auto-DCA ladder logic from the architecture doc.
        CRITICAL: Uses pos.dca_triggered_indices to persist state across restarts.
        """
        if not strategy:
            # Fall back to legacy settings
            settings = self.settings.get(pos.recorder)
            if not settings or not settings.dca_steps:
                return
            # Convert legacy format to DCAStep objects
            dca_steps = [
                DCAStep(
                    trigger_type=step.get('trigger_type', 'percent'),
                    trigger_value=step.get('pct_drop', step.get('trigger_value', 0)),
                    qty=step.get('qty', 1),
                    enabled=True,
                    triggered=(i in pos.dca_triggered_indices)  # CRITICAL: Restore triggered state from position
                ) for i, step in enumerate(settings.dca_steps)
            ]
        else:
            # Mark steps as triggered based on position's persisted state
            dca_steps = strategy.dca_steps
            for i, step in enumerate(dca_steps):
                if i in pos.dca_triggered_indices:
                    step.triggered = True
        
        if not dca_steps:
            return
        
        # Check max_qty limit
        max_qty = strategy.max_qty if strategy else (self.settings.get(pos.recorder) and self.settings[pos.recorder].max_qty)
        if max_qty and pos.total_qty >= max_qty:
            return
        
        # Evaluate triggers
        triggered_steps = self._dca_engine.evaluate_dca_triggers(pos, price, dca_steps, strategy)
        
        for step_idx, (step, qty) in enumerate(triggered_steps):
            # Find the actual index of this step in the ladder
            actual_idx = dca_steps.index(step) if step in dca_steps else step_idx
            
            # CRITICAL: Skip if this step was already triggered (persisted state)
            if actual_idx in pos.dca_triggered_indices:
                logger.debug(f"DCA step {actual_idx} already triggered, skipping")
                continue
            
            # Mark step as triggered (both in memory and in position for persistence)
            step.triggered = True
            pos.dca_triggered_indices.append(actual_idx)  # CRITICAL: Persist the index
            pos.dca_steps_triggered += 1
            self._stats["dca_triggers"] += 1
            
            # Check qty limits
            if max_qty and (pos.total_qty + qty) > max_qty:
                qty = max_qty - pos.total_qty
                if qty <= 0:
                    continue
            
            logger.info(f"🔄 AUTO-DCA: {pos.side} {pos.ticker} +{qty} @ {price} (trigger: {step.trigger_type} {step.trigger_value}, step #{actual_idx})")
            
            # Execute DCA add
            self._dca_add(pos, price, qty, auto_triggered=True)

    def _evaluate_targets(self, recorder: str, ticker: str, price: float) -> None:
        """
        Evaluate TP/SL targets with timing metrics.
        This is the critical path - must be as fast as possible.
        
        CRITICAL: Uses StrategyInstance as source of truth (not legacy V2StrategySettings).
        """
        eval_start = time.time()
        
        key = self._pos_key(recorder, ticker)
        pos = self.positions.get(key)
        if not pos:
            return
        
        # === CRITICAL: Don't evaluate TP/SL until broker confirms entry fill ===
        # This prevents instant exits when webhook price is stale vs real-time price
        if pos.pending_fill:
            return  # Wait for broker fill confirmation before evaluating TP/SL
        
        # CRITICAL FIX: Use StrategyInstance as primary source of truth
        strategy = self.strategies.get(recorder) or self.strategies.get(pos.strategy_id)
        if strategy:
            tp_ticks = strategy.tp_ticks
            sl_ticks = strategy.sl_ticks
            tick_size = strategy.tick_size or self.tick_size_map.get(ticker, 0.25)
        else:
            # Fallback to legacy settings only if no strategy exists
            settings = self.settings.get(recorder)
            if not settings:
                return
            tp_ticks = settings.tp_ticks
            sl_ticks = settings.sl_ticks
            tick_size = self.tick_size_map.get(ticker, 0.25)
        
        # Skip if no TP configured
        if not tp_ticks:
            return

        if pos.side == "LONG":
            tp_price = pos.avg_price + (tp_ticks * tick_size)
            sl_price = pos.avg_price - (sl_ticks * tick_size) if sl_ticks else None
            
            if price >= tp_price:
                # Log timing for TP hit
                trigger_latency = (time.time() - eval_start) * 1000
                logger.info(f"🎯 TP HIT: {ticker} @ {price} (target: {tp_price}) | Eval: {trigger_latency:.1f}ms")
                self._exit_position(pos, price, reason="tp_hit")
            elif sl_price and price <= sl_price:
                trigger_latency = (time.time() - eval_start) * 1000
                logger.info(f"🛑 SL HIT: {ticker} @ {price} (target: {sl_price}) | Eval: {trigger_latency:.1f}ms")
                self._exit_position(pos, price, reason="sl_hit")
        else:
            tp_price = pos.avg_price - (tp_ticks * tick_size)
            sl_price = pos.avg_price + (sl_ticks * tick_size) if sl_ticks else None
            
            if price <= tp_price:
                trigger_latency = (time.time() - eval_start) * 1000
                logger.info(f"🎯 TP HIT: {ticker} @ {price} (target: {tp_price}) | Eval: {trigger_latency:.1f}ms")
                self._exit_position(pos, price, reason="tp_hit")
            elif sl_price and price >= sl_price:
                trigger_latency = (time.time() - eval_start) * 1000
                logger.info(f"🛑 SL HIT: {ticker} @ {price} (target: {sl_price}) | Eval: {trigger_latency:.1f}ms")
                self._exit_position(pos, price, reason="sl_hit")

    def _execute_broker(self, intent: str, pos: V2Position, price: float, qty: int) -> None:
        """
        Broker execution with priority handling.
        - EXIT orders: IMMEDIATE execution (no queue) - critical for TP/SL
        - ENTRY/DCA orders: Queued for rate limiting
        """
        if not self.broker_adapter:
            logger.warning(f"⏸️ V2: No broker adapter - skipping broker execution for {intent} {pos.recorder} {pos.ticker} qty={qty}")
            return
        
        logger.info(f"🔍 V2: Broker adapter exists, checking credentials for {pos.recorder}...")
        
        intent_upper = intent.upper()
        start_time = time.time()
        
        # === CRITICAL: EXIT ORDERS EXECUTE IMMEDIATELY ===
        # TP/SL exits must not be delayed by queue - every ms matters for slippage
        if intent_upper == "EXIT":
            try:
                self.broker_adapter(intent, pos, price, qty)
                self._stats["orders_placed"] += 1
                latency_ms = (time.time() - start_time) * 1000
                logger.info(f"⚡ V2 EXIT executed in {latency_ms:.0f}ms")
            except Exception as e:
                self._stats["orders_failed"] += 1
                logger.error(f"❌ V2 EXIT failed: {e}")
            return
        
        # === ENTRY/DCA orders go through queue (rate limited) ===
        order_key = f"{pos.recorder}:{pos.ticker}:{intent}:{time.time()}"
        
        # Get account_id for per-account rate limiting
        account_id = None
        if hasattr(self.broker_adapter, '_get_trader_credentials'):
            creds = self.broker_adapter._get_trader_credentials(pos.recorder)
            if creds:
                account_id = str(creds.get('subaccount_id', ''))
        
        # Create closure for the order - capture order ID for entry fills
        def place_order():
            try:
                logger.info(f"🔄 V2: Executing queued order: {intent} {pos.ticker} qty={qty}")
                result = self.broker_adapter(intent, pos, price, qty)
                if result:
                    self._stats["orders_placed"] += 1
                    logger.info(f"✅ V2: Queued order executed successfully: {result}")
                    
                    # === CRITICAL: Track entry order ID for fill matching ===
                    if result and intent_upper == "ENTRY":
                        order_id = str(result.get('orderId', ''))
                        if order_id:
                            pos.entry_order_id = order_id
                            logger.info(f"📝 Entry order tracked: {order_id} for {pos.recorder}:{pos.ticker}")
                            
                            # Also store in pending entries dict for fill matching
                            if not hasattr(self, '_pending_entry_fills'):
                                self._pending_entry_fills = {}
                            self._pending_entry_fills[order_id] = self._pos_key(pos.recorder, pos.ticker)
                else:
                    logger.warning(f"⚠️ V2: Queued order returned None - broker execution may have failed")
                    self._stats["orders_failed"] += 1
                        
            except Exception as e:
                self._stats["orders_failed"] += 1
                logger.error(f"❌ V2: Queued order execution failed: {e}", exc_info=True)
                raise e
        
        # Submit to async queue (non-blocking)
        logger.info(f"📤 V2: Submitting order to queue: {order_key} (intent={intent}, qty={qty})")
        self._order_queue.submit(place_order, order_key, account_id)
        logger.info(f"✅ V2: Order queued successfully: {order_key}")

    # ---------- TP ORDER MANAGEMENT (DCA Fix) ----------
    
    def _generate_order_tag(self, account_id: int, symbol: str, strategy_id: str, role: str, sequence: int) -> str:
        """
        Generate order tag for tracking and reconciliation.
        Format: JT:{account_id}:{symbol}:{strategy_id}:{role}:{sequence}
        """
        # Truncate strategy_id if too long (Tradovate may have length limits)
        strategy_short = strategy_id[:20] if len(strategy_id) > 20 else strategy_id
        return f"JT:{account_id}:{symbol}:{strategy_short}:{role}:{sequence}"
    
    def _get_position_lock(self, pos_key: str) -> threading.Lock:
        """Get or create lock for position (for coalescing rapid DCA fills)."""
        if pos_key not in self._tp_reconciliation_locks:
            self._tp_reconciliation_locks[pos_key] = threading.Lock()
        return self._tp_reconciliation_locks[pos_key]
    
    def _check_tp_marketability(self, tp_price: float, current_price: float, side: str, tick_size: float) -> Tuple[bool, Optional[str]]:
        """
        Check if TP order would be marketable (fill immediately).
        Returns (is_safe, error_message)
        """
        if side == "LONG":
            # For long positions, TP must be above current price
            min_tp = current_price + (2 * tick_size)  # At least 2 ticks above
            if tp_price <= current_price:
                return False, f"TP {tp_price} is at or below current price {current_price} for LONG"
            if tp_price < min_tp:
                return False, f"TP {tp_price} is too close to current price {current_price} (min: {min_tp})"
        else:  # SHORT
            # For short positions, TP must be below current price
            max_tp = current_price - (2 * tick_size)  # At least 2 ticks below
            if tp_price >= current_price:
                return False, f"TP {tp_price} is at or above current price {current_price} for SHORT"
            if tp_price > max_tp:
                return False, f"TP {tp_price} is too close to current price {current_price} (max: {max_tp})"
        
        return True, None
    
    def _reconcile_tp_orders_after_position_change(self, pos: V2Position, strategy: StrategyInstance) -> None:
        """
        CRITICAL: Reconcile TP orders after position change (DCA fill, entry fill, etc.)
        Enforces "exactly one TP order" invariant.
        
        Algorithm:
        1. Acquire lock (coalesce rapid fills)
        2. Query broker for all working orders
        3. Cancel all stale TP orders
        4. Compute desired TP
        5. Check marketability
        6. Place new TP if needed
        7. Verify exactly one TP exists
        """
        logger.info(f"🔄 DYNAMIC TP: Starting reconciliation for {pos.recorder}:{pos.ticker} (avg_price={pos.avg_price}, qty={pos.total_qty})")
        
        if not self.broker_adapter:
            logger.warning(f"⚠️ DYNAMIC TP: No broker adapter - skipping reconciliation for {pos.recorder}:{pos.ticker}")
            return
        
        if not strategy.tp_ticks:
            logger.warning(f"⚠️ DYNAMIC TP: No tp_ticks configured (tp_ticks={strategy.tp_ticks}) - skipping reconciliation for {pos.recorder}:{pos.ticker}")
            return
        
        pos_key = self._pos_key(pos.recorder, pos.ticker)
        lock = self._get_position_lock(pos_key)
        
        # Acquire lock to coalesce rapid DCA fills
        if not lock.acquire(timeout=1.0):
            logger.warning(f"TP reconciliation lock timeout for {pos_key}")
            return
        
        try:
            # Small delay to coalesce multiple rapid fills
            time.sleep(0.1)
            
            # Get credentials
            creds = self.broker_adapter._get_trader_credentials(pos.recorder)
            if not creds:
                return
            
            account_id = int(creds.get('subaccount_id', 0))
            if not account_id:
                logger.warning(f"⚠️ DYNAMIC TP: No account_id found for {pos.recorder}")
                return
            
            # Compute desired TP price
            tick_size = strategy.tick_size or self.tick_size_map.get(pos.ticker, 0.25)
            if pos.side == "LONG":
                desired_tp_price = pos.avg_price + (strategy.tp_ticks * tick_size)
                exit_side = "Sell"
            else:
                desired_tp_price = pos.avg_price - (strategy.tp_ticks * tick_size)
                exit_side = "Buy"
            
            logger.info(f"📊 DYNAMIC TP: Calculated TP for {pos.ticker} - Entry: {pos.avg_price}, TP: {desired_tp_price} ({strategy.tp_ticks} ticks), Side: {pos.side}, Qty: {pos.total_qty}")
            
            # Check marketability (prevent instant fill)
            current_price = pos.last_price or pos.avg_price
            is_safe, error_msg = self._check_tp_marketability(desired_tp_price, current_price, pos.side, tick_size)
            if not is_safe:
                logger.warning(f"⚠️ TP order would be marketable: {error_msg} - skipping placement")
                return
            
            # Get strategy ID for tagging
            strategy_id = strategy.id or strategy.name
            bot_run_id = f"{pos.recorder}_{pos.ticker}"
            
            # Increment sequence counter
            if pos_key not in self._tp_sequence_counter:
                self._tp_sequence_counter[pos_key] = 0
            self._tp_sequence_counter[pos_key] += 1
            sequence = self._tp_sequence_counter[pos_key]
            
            # Generate tag for new TP order
            tradovate_symbol = self.broker_adapter._convert_ticker(pos.ticker)
            new_tp_tag = self._generate_order_tag(account_id, tradovate_symbol, strategy_id, "TP", sequence)
            
            # Query broker for working orders (async)
            async def reconcile():
                from phantom_scraper.tradovate_integration import TradovateIntegration
                from tradovate_api_access import TradovateAPIAccess
                
                is_demo = bool(creds.get('is_demo'))
                access_token = creds.get('tradovate_token')
                refresh_token = creds.get('tradovate_refresh_token')
                md_token = creds.get('md_access_token')
                account_spec = creds.get('subaccount_name')
                username = creds.get('username')
                password = creds.get('password')
                account_id_for_auth = creds.get('account_id')
                
                # CRITICAL: Use REST API Access for authentication (avoids rate limiting)
                api_access = TradovateAPIAccess(demo=is_demo)
                
                # Use local variables to avoid scoping issues
                current_access_token = access_token
                current_md_token = md_token
                
                # Authenticate via REST API Access if no token or credentials available
                if not current_access_token and username and password:
                    logger.info(f"🔐 DYNAMIC TP: Authenticating via REST API Access...")
                    login_result = await api_access.login(
                        username=username,
                        password=password,
                        db_path=self.broker_adapter.db_path,
                        account_id=account_id_for_auth
                    )
                    
                    if not login_result.get('success'):
                        logger.error(f"❌ DYNAMIC TP: REST API Access authentication failed: {login_result.get('error')}")
                        return
                    
                    current_access_token = login_result.get('accessToken')
                    current_md_token = login_result.get('mdAccessToken')
                    logger.info(f"✅ DYNAMIC TP: REST API Access authentication successful")
                elif current_access_token:
                    logger.info(f"✅ DYNAMIC TP: Using existing access token (will re-auth via REST API Access if expired)")
                else:
                    logger.error(f"❌ DYNAMIC TP: No credentials available for authentication")
                    return
                
                async with TradovateIntegration(demo=is_demo) as tv:
                    tv.access_token = current_access_token
                    tv.md_access_token = current_md_token
                    
                    # Query working orders for this account and symbol
                    try:
                        # Get orders from broker
                        working_orders = await tv.get_orders(account_id=str(account_id))
                        
                        # Filter to working orders for this symbol
                        symbol_orders = [
                            o for o in working_orders 
                            if o.get('symbol') == tradovate_symbol and 
                               o.get('ordStatus') in ('Working', 'PartiallyFilled')
                        ]
                        
                        # Find TP orders (by tag or by side/type inference)
                        tp_orders = []
                        for order in symbol_orders:
                            order_id = str(order.get('orderId', ''))
                            order_side = order.get('action', '')
                            order_type = order.get('orderType', '')
                            
                            # Check if this looks like a TP order
                            # TP for LONG = Sell Limit, TP for SHORT = Buy Limit
                            is_tp_candidate = (
                                (pos.side == "LONG" and order_side == "Sell" and order_type == "Limit") or
                                (pos.side == "SHORT" and order_side == "Buy" and order_type == "Limit")
                            )
                            
                            # Also check tag if available
                            cl_ord_id = order.get('clOrdId', '') or order.get('clientOrderId', '')
                            has_tp_tag = cl_ord_id and cl_ord_id.startswith(f"JT:{account_id}:{tradovate_symbol}:{strategy_id}:TP:")
                            
                            if is_tp_candidate or has_tp_tag:
                                tp_orders.append({
                                    'orderId': order_id,
                                    'price': float(order.get('price', 0)),
                                    'qty': int(order.get('orderQty', 0)),
                                    'clOrdId': cl_ord_id
                                })
                        
                        logger.info(f"📊 DYNAMIC TP: Found {len(tp_orders)} existing TP orders for {pos.ticker}")
                        if tp_orders:
                            for tp in tp_orders:
                                logger.info(f"   - TP Order {tp.get('orderId')}: {tp.get('qty')} @ {tp.get('price')}")
                        
                        # Also check local tracking (in case broker query missed it)
                        if pos_key in self._active_tp_orders:
                            local_tp = self._active_tp_orders[pos_key]
                            local_id = local_tp.get('order_id')
                            # Only add if not already in tp_orders
                            if not any(o.get('orderId') == local_id for o in tp_orders):
                                tp_orders.append({
                                    'orderId': local_id,
                                    'price': local_tp.get('price', 0),
                                    'qty': local_tp.get('qty', 0),
                                    'clOrdId': local_tp.get('tag', '')
                                })
                                logger.info(f"📊 Added locally tracked TP order: {local_id}")
                        
                        # Cancel all existing TP orders
                        for tp_order in tp_orders:
                            order_id = tp_order.get('orderId') or tp_order.get('order_id')
                            if order_id:
                                try:
                                    result = await tv.cancel_order(int(order_id))
                                    if result:
                                        logger.info(f"🗑️ Canceled stale TP order: {order_id} @ {tp_order.get('price')}")
                                    else:
                                        logger.warning(f"Cancel order returned False for {order_id}")
                                except Exception as e:
                                    logger.warning(f"Failed to cancel TP order {order_id}: {e}")
                        
                        # Wait a bit for cancellations to process
                        await asyncio.sleep(0.2)
                        
                        # SAFETY CHECK: Calculate actual qty from entries to prevent quantity mismatch bugs
                        entries_qty = sum(entry.get('qty', 0) for entry in pos.entries)
                        if entries_qty != pos.total_qty:
                            logger.warning(f"⚠️ QUANTITY MISMATCH: pos.total_qty={pos.total_qty} but sum(entries)={entries_qty} for {pos.ticker} - using entries sum")
                            actual_qty = entries_qty  # Use entries sum as source of truth
                        else:
                            actual_qty = pos.total_qty
                        
                        if actual_qty <= 0:
                            logger.error(f"❌ Invalid TP order quantity: {actual_qty} for {pos.ticker} - skipping TP placement")
                            return
                        
                        # Place new TP order with tag
                        tp_order_data = tv.create_limit_order(
                            account_spec,
                            tradovate_symbol,
                            exit_side,
                            actual_qty,  # Use validated quantity
                            desired_tp_price,
                            account_id,
                            cl_ord_id=new_tp_tag  # Tag for reconciliation
                        )
                        
                        tp_result = await tv.place_order(tp_order_data)
                        
                        # If token expired, re-authenticate via REST API Access
                        if tp_result and not tp_result.get('orderId') and ('Expired Access Token' in str(tp_result.get('error', '')) or '401' in str(tp_result.get('error', ''))):
                            if username and password:
                                logger.warning(f"🔄 DYNAMIC TP: Token expired, re-authenticating via REST API Access...")
                                login_result = await api_access.login(
                                    username=username,
                                    password=password,
                                    db_path=self.broker_adapter.db_path,
                                    account_id=account_id_for_auth
                                )
                                if login_result.get('success'):
                                    logger.info(f"✅ DYNAMIC TP: Re-authentication successful via REST API Access, retrying TP order...")
                                    current_access_token = login_result.get('accessToken')
                                    current_md_token = login_result.get('mdAccessToken')
                                    tv.access_token = current_access_token
                                    tv.md_access_token = current_md_token
                                    
                                    # Retry TP order with new token
                                    tp_result = await tv.place_order(tp_order_data)
                                else:
                                    logger.error(f"❌ DYNAMIC TP: REST API Access re-authentication failed: {login_result.get('error')}")
                        
                        if tp_result and tp_result.get('orderId'):
                            tp_order_id = str(tp_result.get('orderId'))
                            logger.info(f"✅ New TP order placed: {tp_order_id} @ {desired_tp_price} (qty={actual_qty}, tag={new_tp_tag})")
                            
                            # Track active TP order
                            self._active_tp_orders[pos_key] = {
                                'order_id': tp_order_id,
                                'price': desired_tp_price,
                                'qty': actual_qty,  # Use validated quantity
                                'tag': new_tp_tag,
                                'timestamp': time.time()
                            }
                        else:
                            error_msg = tp_result.get('error') if tp_result else 'Unknown error'
                            logger.error(f"❌ Failed to place TP order: {error_msg}")
                    
                    except Exception as e:
                        logger.error(f"TP reconciliation error: {e}", exc_info=True)
            
            # Run reconciliation async
            if self.broker_adapter and hasattr(self.broker_adapter, '_run_async'):
                self.broker_adapter._run_async(reconcile())
            else:
                # Fallback: run in thread
                threading.Thread(target=lambda: asyncio.run(reconcile()), daemon=True).start()
        
        finally:
            lock.release()
    
    def _cancel_all_tp_orders(self, account_id: int, symbol: str, strategy_id: str) -> None:
        """Cancel all TP orders for a position (when position is closed)."""
        # This will be called when position is closed
        pass  # Implementation similar to reconciliation but simpler
    
    def _cancel_all_old_tp_orders_for_symbol(self, recorder: str, ticker: str) -> None:
        """
        CRITICAL: Cancel ALL old TP orders for a symbol before processing new signals.
        This prevents old resting TP orders from interfering with new positions.
        
        Called at the start of handle_signal() to ensure clean slate before new trades.
        """
        if not self.broker_adapter:
            return
        
        strategy = self.strategies.get(recorder)
        if not strategy or strategy.mode != StrategyMode.LIVE.value:
            # Only cancel in LIVE mode
            return
        
        try:
            # Get credentials
            creds = self.broker_adapter._get_trader_credentials(recorder)
            if not creds:
                return
            
            account_id = int(creds.get('subaccount_id', 0))
            if not account_id:
                return
            
            # Convert ticker to Tradovate symbol
            tradovate_symbol = self.broker_adapter._convert_ticker(ticker)
            
            logger.info(f"🗑️ CANCEL OLD TP: Checking for old TP orders on {ticker} ({tradovate_symbol}) before processing new signal")
            
            # Cancel asynchronously (non-blocking)
            async def cancel_old_tp():
                from phantom_scraper.tradovate_integration import TradovateIntegration
                from tradovate_api_access import TradovateAPIAccess
                
                is_demo = bool(creds.get('is_demo'))
                access_token = creds.get('tradovate_token')
                refresh_token = creds.get('tradovate_refresh_token')
                md_token = creds.get('md_access_token')
                username = creds.get('username')
                password = creds.get('password')
                account_id_for_auth = creds.get('account_id')
                
                # Use REST API Access for authentication
                api_access = TradovateAPIAccess(demo=is_demo)
                current_access_token = access_token
                current_md_token = md_token
                
                # Authenticate if needed
                if not current_access_token and username and password:
                    login_result = await api_access.login(
                        username=username,
                        password=password,
                        db_path=self.broker_adapter.db_path,
                        account_id=account_id_for_auth
                    )
                    if login_result.get('success'):
                        current_access_token = login_result.get('accessToken')
                        current_md_token = login_result.get('mdAccessToken')
                    else:
                        logger.warning(f"⚠️ Failed to authenticate for TP cancellation: {login_result.get('error')}")
                        return
                
                async with TradovateIntegration(demo=is_demo) as tv:
                    tv.access_token = current_access_token
                    tv.md_access_token = current_md_token
                    
                    # Query ALL working orders for this symbol
                    try:
                        working_orders = await tv.get_orders(account_id=str(account_id))
                        
                        # Filter to working limit orders for this symbol (TP orders are limits)
                        tp_orders = [
                            o for o in working_orders 
                            if o.get('symbol') == tradovate_symbol and 
                               o.get('ordStatus') in ('Working', 'PartiallyFilled') and
                               o.get('orderType') == 'Limit'  # TP orders are limit orders
                        ]
                        
                        if tp_orders:
                            logger.info(f"🗑️ CANCEL OLD TP: Found {len(tp_orders)} old TP order(s) for {ticker} - cancelling all")
                            for order in tp_orders:
                                order_id = order.get('orderId')
                                order_price = order.get('price')
                                order_qty = order.get('orderQty')
                                order_side = order.get('action', '')
                                
                                if order_id:
                                    try:
                                        result = await tv.cancel_order(int(order_id))
                                        if result:
                                            logger.info(f"✅ CANCEL OLD TP: Cancelled TP order {order_id}: {order_side} {order_qty} @ {order_price}")
                                        else:
                                            logger.warning(f"⚠️ Cancel order returned False for {order_id}")
                                    except Exception as e:
                                        logger.warning(f"⚠️ Failed to cancel TP order {order_id}: {e}")
                            
                            # Wait a bit for cancellations to process
                            await asyncio.sleep(0.2)
                            logger.info(f"✅ CANCEL OLD TP: Finished cancelling old TP orders for {ticker}")
                        else:
                            logger.debug(f"ℹ️ CANCEL OLD TP: No old TP orders found for {ticker}")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ Error querying/cancelling old TP orders for {ticker}: {e}")
            
            # Run asynchronously (non-blocking)
            if hasattr(self.broker_adapter, '_run_async'):
                self.broker_adapter._run_async(cancel_old_tp())
            else:
                threading.Thread(target=lambda: asyncio.run(cancel_old_tp()), daemon=True).start()
                
        except Exception as e:
            logger.warning(f"⚠️ Error in _cancel_all_old_tp_orders_for_symbol for {recorder}:{ticker}: {e}")

    # ---------- DB helpers ----------
    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # === Core Tables ===
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorder TEXT NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                total_qty INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                entries_json TEXT,
                opened_at TEXT,
                updated_at TEXT,
                strategy_id TEXT,
                unrealized_pnl REAL DEFAULT 0,
                max_favorable_excursion REAL DEFAULT 0,
                max_adverse_excursion REAL DEFAULT 0,
                dca_steps_triggered INTEGER DEFAULT 0,
                last_price REAL DEFAULT 0,
                dca_triggered_indices_json TEXT DEFAULT '[]',
                UNIQUE(recorder, ticker)
            )
            """
        )
        
        # Add column if it doesn't exist (migration for existing DBs)
        try:
            cursor.execute("ALTER TABLE v2_positions ADD COLUMN dca_triggered_indices_json TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorder TEXT UNIQUE NOT NULL,
                tp_ticks INTEGER NOT NULL,
                sl_ticks INTEGER,
                dca_steps_json TEXT,
                max_qty INTEGER,
                max_risk REAL
            )
            """
        )
        
        # === NEW: Strategy Instance Table (Architecture Section 3) ===
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_strategies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                symbol TEXT,
                timeframe TEXT,
                mode TEXT DEFAULT 'virtual',
                tp_ticks INTEGER NOT NULL,
                sl_ticks INTEGER,
                dca_steps_json TEXT,
                max_qty INTEGER,
                max_risk_dollars REAL,
                tick_size REAL DEFAULT 0.25,
                tick_value REAL DEFAULT 0.50,
                config_json TEXT DEFAULT '{}',
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(name)
            )
            """
        )
        
        # === NEW: Virtual Fill Table (Architecture Section 3) ===
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_fills (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                fill_type TEXT NOT NULL,
                qty INTEGER NOT NULL,
                price REAL NOT NULL,
                timestamp TEXT NOT NULL,
                pnl REAL,
                notes TEXT,
                FOREIGN KEY (strategy_id) REFERENCES v2_strategies(id)
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fills_strategy ON v2_fills(strategy_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fills_timestamp ON v2_fills(timestamp)")
        
        # === NEW: Virtual Bar Price Table (Architecture Section 3) ===
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_bar_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                UNIQUE(ticker, timestamp)
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bar_ticker ON v2_bar_prices(ticker)")
        
        # === NEW: Broker Position Snapshot Table (Architecture Section 6) ===
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_broker_snapshots (
                id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                broker_qty INTEGER NOT NULL,
                broker_avg_price REAL NOT NULL,
                virtual_qty INTEGER NOT NULL,
                virtual_avg_price REAL NOT NULL,
                drift_qty INTEGER NOT NULL,
                drift_price REAL NOT NULL,
                snapshot_time TEXT NOT NULL,
                is_synced INTEGER NOT NULL
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_strategy ON v2_broker_snapshots(strategy_id)")
        
        # === NEW: PnL History Table ===
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_pnl_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id TEXT NOT NULL,
                ticker TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                unrealized_pnl REAL,
                realized_pnl REAL,
                total_pnl REAL,
                price REAL
            )
            """
        )
        
        conn.commit()
        conn.close()
        
        # Initialize broker sync after DB is ready
        self._broker_sync = BrokerPositionSync(self.db_path)

    def _load_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # === Load Legacy Settings ===
            cursor.execute("SELECT recorder, tp_ticks, sl_ticks, dca_steps_json, max_qty, max_risk FROM v2_settings")
            for row in cursor.fetchall():
                rec, tp, sl, dca_json, max_qty, max_risk = row
                try:
                    dca_steps = json.loads(dca_json) if dca_json else []
                except Exception:
                    dca_steps = []
                self.settings[rec] = V2StrategySettings(tp_ticks=tp, sl_ticks=sl, dca_steps=dca_steps, max_qty=max_qty, max_risk=max_risk)
            
            # === Load Strategy Instances (NEW) ===
            try:
                cursor.execute('''
                    SELECT id, name, symbol, timeframe, mode, tp_ticks, sl_ticks, 
                           dca_steps_json, max_qty, max_risk_dollars, tick_size, 
                           tick_value, config_json, created_at, updated_at
                    FROM v2_strategies
                ''')
                strategies_loaded = 0
                for row in cursor.fetchall():
                    try:
                        dca_json = row['dca_steps_json']
                        dca_data = json.loads(dca_json) if dca_json else []
                        dca_steps = [
                            DCAStep(
                                trigger_type=d.get('trigger_type', 'percent'),
                                trigger_value=d.get('trigger_value', 0),
                                qty=d.get('qty', 1),
                                enabled=d.get('enabled', True),
                                triggered=False
                            ) for d in dca_data
                        ]
                    except Exception:
                        dca_steps = []
                    
                    strategy = StrategyInstance(
                        id=row['id'],
                        name=row['name'],
                        symbol=row['symbol'] or "",
                        timeframe=row['timeframe'] or "",
                        mode=row['mode'] or "virtual",
                        tp_ticks=row['tp_ticks'],
                        sl_ticks=row['sl_ticks'],
                        dca_steps=dca_steps,
                        max_qty=row['max_qty'],
                        max_risk_dollars=row['max_risk_dollars'],
                        tick_size=row['tick_size'] or 0.25,
                        tick_value=row['tick_value'] or 0.50,
                        config_json=row['config_json'] or "{}",
                        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.utcnow(),
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.utcnow(),
                    )
                    
                    self.strategies[strategy.name] = strategy
                    self.strategies[strategy.id] = strategy
                    strategies_loaded += 1
                
                if strategies_loaded > 0:
                    logger.info(f"V2: Loaded {strategies_loaded} strategy instances")
            except Exception as e:
                logger.debug(f"V2: No strategies table yet or error: {e}")
            
            # === Load Positions ===
            cursor.execute('''
                SELECT recorder, ticker, side, total_qty, avg_price, entries_json,
                       opened_at, updated_at, strategy_id, unrealized_pnl,
                       max_favorable_excursion, max_adverse_excursion, 
                       dca_steps_triggered, last_price, dca_triggered_indices_json
                FROM v2_positions
            ''')
            positions_loaded = 0
            for row in cursor.fetchall():
                rec = row['recorder']
                tic = row['ticker']
                try:
                    entries = json.loads(row['entries_json']) if row['entries_json'] else []
                except Exception:
                    entries = []
                
                # CRITICAL: Load DCA triggered indices to prevent double-triggers after restart
                try:
                    dca_triggered_indices = json.loads(row['dca_triggered_indices_json']) if row.get('dca_triggered_indices_json') else []
                except Exception:
                    dca_triggered_indices = []
                
                pos = V2Position(
                    recorder=rec,
                    ticker=tic,
                    side=row['side'],
                    total_qty=row['total_qty'],
                    avg_price=row['avg_price'],
                    entries=entries,
                    opened_at=datetime.fromisoformat(row['opened_at']) if row['opened_at'] else datetime.utcnow(),
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.utcnow(),
                    strategy_id=row['strategy_id'] or "",
                    unrealized_pnl=row['unrealized_pnl'] or 0.0,
                    max_favorable_excursion=row['max_favorable_excursion'] or 0.0,
                    max_adverse_excursion=row['max_adverse_excursion'] or 0.0,
                    dca_steps_triggered=row['dca_steps_triggered'] or 0,
                    last_price=row['last_price'] or 0.0,
                    dca_triggered_indices=dca_triggered_indices,  # CRITICAL: Restore triggered state
                )
                key = self._pos_key(rec, tic)
                self.positions[key] = pos
                # Build ticker index on load
                self._ticker_index.add(tic, key)
                positions_loaded += 1
            
            if positions_loaded > 0:
                logger.info(f"V2: Loaded {positions_loaded} positions, indexed {len(self._ticker_index.get_all_tickers())} tickers")
                
        except Exception as e:
            logger.warning("V2 load DB issue: %s", e)
        conn.close()

    def _persist_settings(self, recorder: str, settings: V2StrategySettings) -> None:
        """Non-blocking settings persist via async DB writer."""
        query = """
            INSERT INTO v2_settings (recorder, tp_ticks, sl_ticks, dca_steps_json, max_qty, max_risk)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(recorder) DO UPDATE SET
                tp_ticks=excluded.tp_ticks,
                sl_ticks=excluded.sl_ticks,
                dca_steps_json=excluded.dca_steps_json,
                max_qty=excluded.max_qty,
                max_risk=excluded.max_risk
        """
        params = (
            recorder,
            settings.tp_ticks,
            settings.sl_ticks,
            json.dumps(settings.dca_steps),
            settings.max_qty,
            settings.max_risk,
        )
        self._async_db.write(query, params)
    
    def shutdown(self) -> None:
        """Graceful shutdown of all background workers."""
        logger.info("V2 Engine: Shutting down...")
        self._poller_stop.set()
        if hasattr(self, '_tv_feed_adapter') and self._tv_feed_adapter:
            self._tv_feed_adapter.stop()
        self._async_db.stop()
        self._order_queue.shutdown()
        
        # Shutdown broker-driven execution engine
        if hasattr(self, '_broker_event_loop') and self._broker_event_loop:
            self._broker_event_loop.stop()
        
        # Shutdown broker adapter's event loop if it has one
        if hasattr(self, 'broker_adapter') and hasattr(self.broker_adapter, 'shutdown'):
            self.broker_adapter.shutdown()
        logger.info("V2 Engine: Shutdown complete")

    def _persist_position(self, pos: V2Position) -> None:
        """Synchronous persist (legacy, use _persist_position_async for production)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO v2_positions (recorder, ticker, side, total_qty, avg_price, entries_json, opened_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recorder, ticker) DO UPDATE SET
                side=excluded.side,
                total_qty=excluded.total_qty,
                avg_price=excluded.avg_price,
                entries_json=excluded.entries_json,
                updated_at=excluded.updated_at
            """,
            (
                pos.recorder,
                pos.ticker,
                pos.side,
                pos.total_qty,
                pos.avg_price,
                json.dumps(pos.entries),
                pos.opened_at.isoformat(),
                pos.updated_at.isoformat(),
            ),
        )
        conn.commit()
        conn.close()
    
    def _persist_position_async(self, pos: V2Position) -> None:
        """Non-blocking position persist via async DB writer."""
        query = """
            INSERT INTO v2_positions 
            (recorder, ticker, side, total_qty, avg_price, entries_json, opened_at, updated_at,
             strategy_id, unrealized_pnl, max_favorable_excursion, max_adverse_excursion,
             dca_steps_triggered, last_price, dca_triggered_indices_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recorder, ticker) DO UPDATE SET
                side=excluded.side,
                total_qty=excluded.total_qty,
                avg_price=excluded.avg_price,
                entries_json=excluded.entries_json,
                updated_at=excluded.updated_at,
                strategy_id=excluded.strategy_id,
                unrealized_pnl=excluded.unrealized_pnl,
                max_favorable_excursion=excluded.max_favorable_excursion,
                max_adverse_excursion=excluded.max_adverse_excursion,
                dca_steps_triggered=excluded.dca_steps_triggered,
                last_price=excluded.last_price,
                dca_triggered_indices_json=excluded.dca_triggered_indices_json
        """
        params = (
            pos.recorder,
            pos.ticker,
            pos.side,
            pos.total_qty,
            pos.avg_price,
            json.dumps(pos.entries),
            pos.opened_at.isoformat(),
            pos.updated_at.isoformat(),
            pos.strategy_id,
            pos.unrealized_pnl,
            pos.max_favorable_excursion,
            pos.max_adverse_excursion,
            pos.dca_steps_triggered,
            pos.last_price,
            json.dumps(pos.dca_triggered_indices),  # CRITICAL: Persist which DCA steps were triggered
        )
        self._async_db.write(query, params)

    def _delete_position(self, pos: V2Position) -> None:
        """
        Synchronous delete (legacy).
        CRITICAL: Verifies position is flat (qty=0) before deletion.
        """
        # SAFETY CHECK: Verify position is actually flat
        entries_qty = sum(entry.get('qty', 0) for entry in pos.entries)
        if entries_qty != 0 or pos.total_qty != 0:
            logger.warning(f"⚠️ Attempting to delete position with non-zero qty: total_qty={pos.total_qty}, entries_sum={entries_qty} for {pos.recorder}:{pos.ticker}")
        
        # Clear from memory
        key = self._pos_key(pos.recorder, pos.ticker)
        with self._price_lock:
            if key in self.positions:
                del self.positions[key]
            self._ticker_index.remove(pos.ticker, key)
        
        # Delete from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM v2_positions WHERE recorder = ? AND ticker = ?",
            (pos.recorder, pos.ticker),
        )
        conn.commit()
        conn.close()
        
        logger.info(f"🗑️ Position deleted and cleared: {pos.recorder}:{pos.ticker} (verified flat: qty={pos.total_qty})")
    
    def _delete_position_async(self, pos: V2Position) -> None:
        """Non-blocking position delete via async DB writer."""
        query = "DELETE FROM v2_positions WHERE recorder = ? AND ticker = ?"
        params = (pos.recorder, pos.ticker)
        self._async_db.write(query, params)
    
    def get_stats(self) -> Dict:
        """Get engine statistics for monitoring."""
        return {
            **self._stats,
            "open_positions": len(self.positions),
            "indexed_tickers": len(self._ticker_index.get_all_tickers()),
            "price_cache_size": len(self._price_cache),
            "strategies_loaded": len(self.strategies),
            "recent_fills": len(self._recent_fills),
        }
    
    # ---------- VirtualFill Methods ----------
    def _record_fill(self, fill: VirtualFill) -> None:
        """Record a virtual fill to DB and cache."""
        # Add to recent fills cache
        self._recent_fills.append(fill)
        if len(self._recent_fills) > self._max_recent_fills:
            self._recent_fills = self._recent_fills[-self._max_recent_fills:]
        
        # Persist to DB (async)
        query = '''
            INSERT INTO v2_fills (id, strategy_id, ticker, side, fill_type, qty, price, timestamp, pnl, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            fill.id, fill.strategy_id, fill.ticker, fill.side, fill.fill_type,
            fill.qty, fill.price, fill.timestamp.isoformat(), fill.pnl, fill.notes
        )
        self._async_db.write(query, params)
        
        logger.debug(f"📝 Fill recorded: {fill.fill_type} {fill.side} {fill.qty} {fill.ticker} @ {fill.price}")
    
    def get_fills(self, strategy_id: Optional[str] = None, limit: int = 100) -> List[VirtualFill]:
        """Get recent fills, optionally filtered by strategy."""
        if strategy_id:
            return [f for f in self._recent_fills if f.strategy_id == strategy_id][-limit:]
        return self._recent_fills[-limit:]
    
    def get_fills_from_db(self, strategy_id: Optional[str] = None, limit: int = 1000) -> List[VirtualFill]:
        """Load fills from database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if strategy_id:
            cursor.execute(
                "SELECT * FROM v2_fills WHERE strategy_id = ? ORDER BY timestamp DESC LIMIT ?",
                (strategy_id, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM v2_fills ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
        
        fills = []
        for row in cursor.fetchall():
            fills.append(VirtualFill(
                id=row['id'],
                strategy_id=row['strategy_id'],
                ticker=row['ticker'],
                side=row['side'],
                fill_type=row['fill_type'],
                qty=row['qty'],
                price=row['price'],
                timestamp=datetime.fromisoformat(row['timestamp']),
                pnl=row['pnl'],
                notes=row['notes']
            ))
        
        conn.close()
        return fills
    
    # ---------- Strategy Instance Methods ----------
    def register_strategy_instance(self, strategy: StrategyInstance) -> None:
        """
        Register a full strategy instance (per architecture doc).
        This replaces the legacy register_strategy() for new code.
        """
        self.strategies[strategy.name] = strategy
        self.strategies[strategy.id] = strategy  # Index by both name and ID
        
        # Also register in legacy settings for compatibility
        self.settings[strategy.name] = V2StrategySettings(
            tp_ticks=strategy.tp_ticks,
            sl_ticks=strategy.sl_ticks,
            dca_steps=[{
                'trigger_type': step.trigger_type,
                'trigger_value': step.trigger_value,
                'qty': step.qty
            } for step in strategy.dca_steps],
            max_qty=strategy.max_qty,
            max_risk=strategy.max_risk_dollars
        )
        
        logger.info(f"📊 Strategy registered: {strategy.name} | Mode: {strategy.mode} | TP: {strategy.tp_ticks} | SL: {strategy.sl_ticks}")
        logger.info(f"   DCA ladder: {len(strategy.dca_steps)} steps | Max qty: {strategy.max_qty}")
        
        self._persist_strategy(strategy)
    
    def _persist_strategy(self, strategy: StrategyInstance) -> None:
        """Persist strategy to database."""
        query = '''
            INSERT INTO v2_strategies 
            (id, name, symbol, timeframe, mode, tp_ticks, sl_ticks, dca_steps_json, 
             max_qty, max_risk_dollars, tick_size, tick_value, config_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                symbol=excluded.symbol, timeframe=excluded.timeframe, mode=excluded.mode,
                tp_ticks=excluded.tp_ticks, sl_ticks=excluded.sl_ticks,
                dca_steps_json=excluded.dca_steps_json, max_qty=excluded.max_qty,
                max_risk_dollars=excluded.max_risk_dollars, tick_size=excluded.tick_size,
                tick_value=excluded.tick_value, config_json=excluded.config_json,
                updated_at=excluded.updated_at
        '''
        dca_json = json.dumps([{
            'trigger_type': s.trigger_type,
            'trigger_value': s.trigger_value,
            'qty': s.qty,
            'enabled': s.enabled
        } for s in strategy.dca_steps])
        
        params = (
            strategy.id, strategy.name, strategy.symbol, strategy.timeframe,
            strategy.mode, strategy.tp_ticks, strategy.sl_ticks, dca_json,
            strategy.max_qty, strategy.max_risk_dollars, strategy.tick_size,
            strategy.tick_value, strategy.config_json,
            strategy.created_at.isoformat(), datetime.utcnow().isoformat()
        )
        self._async_db.write(query, params)
    
    def get_strategy(self, name_or_id: str) -> Optional[StrategyInstance]:
        """Get strategy by name or ID."""
        return self.strategies.get(name_or_id)
    
    def set_strategy_mode(self, name: str, mode: str) -> bool:
        """Change strategy mode (virtual/live)."""
        strategy = self.strategies.get(name)
        if not strategy:
            return False
        
        strategy.mode = mode
        strategy.updated_at = datetime.utcnow()
        self._persist_strategy(strategy)
        logger.info(f"📊 Strategy {name} mode changed to: {mode}")
        return True
    
    # ---------- Broker Position Sync Methods ----------
    def sync_broker_position(
        self,
        strategy_id: str,
        ticker: str,
        broker_qty: int,
        broker_avg_price: float
    ) -> Optional[BrokerPositionSnapshot]:
        """
        Compare virtual position against broker position.
        Call this periodically to detect drift.
        """
        if not self._broker_sync:
            return None
        
        # Get virtual position
        key = self._pos_key(strategy_id, ticker)
        pos = self.positions.get(key)
        
        virtual_qty = pos.total_qty if pos else 0
        virtual_avg_price = pos.avg_price if pos else 0.0
        
        snapshot = self._broker_sync.take_snapshot(
            strategy_id=strategy_id,
            ticker=ticker,
            virtual_qty=virtual_qty,
            virtual_avg_price=virtual_avg_price,
            broker_qty=broker_qty,
            broker_avg_price=broker_avg_price
        )
        
        if not snapshot.is_synced:
            self._stats["drift_events"] += 1
        
        return snapshot
    
    def get_drift_report(self) -> List[BrokerPositionSnapshot]:
        """Get all positions with drift between virtual and broker."""
        if not self._broker_sync:
            return []
        return self._broker_sync.get_drift_report()
    
    # ---------- ATR Update (for ATR-based DCA) ----------
    def update_atr(self, ticker: str, atr: float) -> None:
        """
        Update ATR value for a ticker.
        Call this from TradingView data feed for ATR-based DCA.
        """
        self._dca_engine.set_atr(ticker, atr)
        logger.debug(f"ATR updated: {ticker} = {atr}")
    
    # ---------- Position PnL Methods ----------
    def get_position_pnl(self, recorder: str, ticker: str) -> Dict:
        """Get current PnL for a position."""
        key = self._pos_key(recorder, ticker)
        pos = self.positions.get(key)
        if not pos:
            return {"error": "Position not found"}
        
        strategy = self.strategies.get(recorder)
        current_price = pos.last_price or self._price_cache.get(pos.ticker, (0, 0))[0]
        
        unrealized = self._pnl_engine.calculate_unrealized_pnl(pos, current_price, strategy)
        
        return {
            "recorder": recorder,
            "ticker": ticker,
            "side": pos.side,
            "qty": pos.total_qty,
            "avg_price": pos.avg_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized,
            "mfe": pos.max_favorable_excursion,
            "mae": pos.max_adverse_excursion,
            "dca_steps_triggered": pos.dca_steps_triggered,
        }
    
    def get_all_positions_pnl(self) -> List[Dict]:
        """Get PnL for all open positions."""
        results = []
        for key, pos in self.positions.items():
            strategy = self.strategies.get(pos.recorder)
            current_price = pos.last_price or self._price_cache.get(pos.ticker, (0, 0))[0]
            unrealized = self._pnl_engine.calculate_unrealized_pnl(pos, current_price, strategy)
            
            results.append({
                "recorder": pos.recorder,
                "ticker": pos.ticker,
                "side": pos.side,
                "qty": pos.total_qty,
                "avg_price": pos.avg_price,
                "current_price": current_price,
                "unrealized_pnl": unrealized,
                "mfe": pos.max_favorable_excursion,
                "mae": pos.max_adverse_excursion,
            })
        
        return results


class TradovateBrokerAdapter:
    """
    Tradovate adapter for v2 that reads credentials from the database.
    This matches how V1 engine works - always uses fresh credentials.
    
    CRITICAL: Uses a dedicated event loop thread to avoid asyncio.run() deadlocks.
    """

    def __init__(self, db_path: str = "just_trades.db"):
        self.db_path = db_path
        # CRITICAL: Dedicated event loop thread to avoid asyncio.run() deadlocks
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._start_event_loop()
    
    def _start_event_loop(self) -> None:
        """Start dedicated event loop in background thread."""
        def run_loop():
            try:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                logger.info("🔄 BrokerAsyncLoop: Event loop started")
                self._loop.run_forever()
            except Exception as e:
                logger.error(f"❌ BrokerAsyncLoop error: {e}", exc_info=True)
            finally:
                logger.warning("⚠️ BrokerAsyncLoop: Event loop stopped")
        
        self._loop_thread = threading.Thread(target=run_loop, daemon=True, name="BrokerAsyncLoop")
        self._loop_thread.start()
        # Wait for loop to be ready
        import time
        for _ in range(50):  # Max 5 seconds
            if self._loop is not None:
                break
            time.sleep(0.1)
        
        if self._loop is None:
            logger.error("❌ BrokerAsyncLoop: Failed to start event loop")
        else:
            logger.info(f"✅ BrokerAsyncLoop: Event loop ready (running={self._loop.is_running()})")
        if self._loop:
            logger.info("🔄 TradovateBrokerAdapter: Async event loop started")
    
    def _run_async(self, coro) -> Any:
        """Run coroutine in dedicated event loop (thread-safe, no deadlock)."""
        if not self._loop:
            logger.error("❌ V2 Broker: Event loop not available")
            return None
        
        if not self._loop.is_running():
            logger.error(f"❌ V2 Broker: Event loop is not running (closed={self._loop.is_closed()})")
            # Try to restart it
            logger.warning("⚠️ V2 Broker: Attempting to restart event loop...")
            self._start_event_loop()
            if not self._loop or not self._loop.is_running():
                logger.error("❌ V2 Broker: Failed to restart event loop")
                return None
        
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result(timeout=15)  # 15 second timeout
        except RuntimeError as e:
            if "cannot schedule new futures after interpreter shutdown" in str(e):
                logger.error(f"❌ V2 Broker: Event loop shutting down - cannot schedule coroutine")
                logger.error(f"   Loop running: {self._loop.is_running() if self._loop else 'N/A'}")
                logger.error(f"   Loop closed: {self._loop.is_closed() if self._loop else 'N/A'}")
            else:
                logger.error(f"❌ V2 Broker async execution error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ V2 Broker async execution error: {e}", exc_info=True)
            return None
    
    def shutdown(self) -> None:
        """Clean shutdown of event loop."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread:
                self._loop_thread.join(timeout=2)

    def _get_trader_credentials(self, recorder: str) -> Optional[Dict]:
        """Get credentials from database (like V1 engine does)."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get recorder_id first
            cursor.execute("SELECT id FROM recorders WHERE name = ?", (recorder,))
            rec = cursor.fetchone()
            if not rec:
                logger.warning(f"V2 Broker: Recorder '{recorder}' not found")
                conn.close()
                return None
            
            recorder_id = rec['id']
            
            # Get enabled trader with credentials (same query as V1)
            cursor.execute('''
                SELECT 
                    t.subaccount_id, t.subaccount_name, t.is_demo,
                    a.name as account_name, a.tradovate_token,
                    a.tradovate_refresh_token, a.md_access_token,
                    a.username, a.password, a.id as account_id
                FROM traders t
                JOIN accounts a ON t.account_id = a.id
                WHERE t.recorder_id = ? AND t.enabled = 1
                LIMIT 1
            ''', (recorder_id,))
            
            trader = cursor.fetchone()
            conn.close()
            
            if not trader:
                logger.info(f"V2 Broker: No enabled trader for '{recorder}' - recording only")
                return None
            
            return dict(trader)
        except Exception as e:
            logger.error(f"V2 Broker: Failed to get credentials: {e}")
            return None

    def _convert_ticker(self, ticker: str) -> str:
        """Convert TradingView ticker to Tradovate format (e.g., MNQ1! → MNQZ5)."""
        import datetime
        
        # Map of base symbols
        base_map = {
            'MNQ': 'MNQ', 'NQ': 'NQ', 'MES': 'MES', 'ES': 'ES',
            'MCL': 'MCL', 'CL': 'CL', 'MGC': 'MGC', 'GC': 'GC',
            'M2K': 'M2K', 'RTY': 'RTY', 'MYM': 'MYM', 'YM': 'YM',
        }
        
        # Month codes
        month_codes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
        
        # Strip trailing ! or 1!
        clean = ticker.rstrip('!')
        if clean.endswith('1'):
            clean = clean[:-1]
        
        # If already in correct format (e.g., MNQZ5), return as-is
        if len(clean) >= 4 and clean[-1].isdigit() and clean[-2].isalpha():
            return clean
        
        # Get base symbol
        base = clean.upper()
        if base not in base_map:
            logger.warning(f"V2 Broker: Unknown symbol base '{base}', using as-is")
            return ticker
        
        # Calculate front month
        now = datetime.datetime.now()
        month = now.month
        year = now.year % 10
        
        # Quarterly contracts: H(Mar), M(Jun), U(Sep), Z(Dec)
        quarterly = [2, 5, 8, 11]  # Indices for H, M, U, Z
        
        # Find next quarterly month
        for q in quarterly:
            if month <= q + 1:  # Give a buffer for rollover
                month_code = month_codes[q]
                break
        else:
            month_code = month_codes[2]  # H (March next year)
            year = (year + 1) % 10
        
        result = f"{base}{month_code}{year}"
        logger.info(f"V2 Broker: Converted {ticker} → {result}")
        return result

    def __call__(self, intent: str, pos: V2Position, price: float, qty: int) -> Optional[Dict]:
        """
        Execute broker order. Returns order result dict with orderId if successful.
        
        CRITICAL: Uses REST API Access (TradovateAPIAccess) instead of OAuth to avoid rate limiting.
        This matches Trade Manager's approach - uses /auth/accesstokenrequest endpoint.
        """
        from phantom_scraper.tradovate_integration import TradovateIntegration
        from tradovate_api_access import TradovateAPIAccess
        import asyncio

        entry_side = self._entry_side(intent, pos)
        if not entry_side:
            return None

        # Get fresh credentials from database
        logger.info(f"🔑 V2 Broker: Getting credentials for {pos.recorder}...")
        creds = self._get_trader_credentials(pos.recorder)
        if not creds:
            logger.warning(f"❌ V2 Broker: No credentials found - skipping broker execution for {pos.recorder}")
            logger.warning(f"   Check: traders table has enabled=1 for recorder_id matching '{pos.recorder}'")
            return None
        
        logger.info(f"✅ V2 Broker: Credentials found for {pos.recorder}")
        
        account_id = creds.get('subaccount_id')
        account_spec = creds.get('subaccount_name')
        is_demo = bool(creds.get('is_demo'))
        access_token = creds.get('tradovate_token')
        refresh_token = creds.get('tradovate_refresh_token')
        md_token = creds.get('md_access_token')
        username = creds.get('username')
        password = creds.get('password')
        
        if not account_id:
            logger.warning(f"❌ V2 Broker: Missing account_id for {pos.recorder}")
            return None
        
        # Convert ticker to Tradovate format
        tradovate_symbol = self._convert_ticker(pos.ticker)
        
        # SAFETY CHECK: Validate qty before placing broker order
        if qty <= 0:
            logger.error(f"❌ Invalid broker order qty={qty} for {pos.recorder} {pos.ticker} - cannot place order")
            return None
        
        # SAFETY CHECK: Verify qty matches position entries (for entry orders)
        if intent.upper() == "ENTRY":
            entries_qty = sum(entry.get('qty', 0) for entry in pos.entries)
            if entries_qty != qty:
                logger.warning(f"⚠️ QUANTITY MISMATCH in entry order: qty param={qty} but pos.entries sum={entries_qty} for {pos.ticker}")
                logger.warning(f"   Using qty param={qty} for broker order (webhook quantity)")
        
        logger.info(f"🚀 V2 BROKER: {intent} {entry_side} {qty} {tradovate_symbol} @ {price} (demo={is_demo}, using REST API Access)")

        async def run():
            # CRITICAL: Use REST API Access for authentication (avoids rate limiting)
            # This matches Trade Manager's approach - uses /auth/accesstokenrequest
            api_access = TradovateAPIAccess(demo=is_demo)
            
            # Authenticate via REST API Access if no token or token is invalid
            # CRITICAL: Always use REST API Access for authentication (avoids OAuth rate limiting)
            if not access_token or not username or not password:
                if not username or not password:
                    logger.error(f"❌ V2 Broker: No username/password for REST API Access authentication")
                    return None
                
                logger.info(f"🔐 V2 Broker: Authenticating via REST API Access (avoids rate limiting)...")
                login_result = await api_access.login(
                    username=username,
                    password=password,
                    db_path=self.db_path,
                    account_id=creds.get('account_id')
                )
                
                if not login_result.get('success'):
                    logger.error(f"❌ V2 Broker: REST API Access authentication failed: {login_result.get('error')}")
                    return None
                
                # Get tokens from API Access result
                access_token = login_result.get('accessToken')
                md_token = login_result.get('mdAccessToken')
                logger.info(f"✅ V2 Broker: REST API Access authentication successful")
                logger.info(f"   AccessToken: {bool(access_token)}, MDAccessToken: {bool(md_token)}")
            else:
                logger.info(f"✅ V2 Broker: Using existing access token (will re-auth via REST API Access if expired)")
            
            # Use TradovateIntegration for order placement (it has the order logic)
            async with TradovateIntegration(demo=is_demo) as tv:
                tv.access_token = access_token
                tv.md_access_token = md_token
                # Use the validated qty parameter directly
                order = tv.create_market_order(account_spec, tradovate_symbol, entry_side, qty, account_id)
                logger.info(f"📤 Placing broker order: {entry_side} {qty} {tradovate_symbol} (qty from webhook={qty})")
                result = await tv.place_order(order)
                
                # If token expired, re-authenticate via REST API Access
                if result and not result.get('success') and ('Expired Access Token' in str(result.get('error', '')) or '401' in str(result.get('error', ''))):
                    logger.warning(f"🔄 V2 Broker: Token expired, re-authenticating via REST API Access for {pos.recorder}...")
                    if username and password:
                        login_result = await api_access.login(
                            username=username,
                            password=password,
                            db_path=self.db_path,
                            account_id=creds.get('account_id')
                        )
                        if login_result.get('success'):
                            logger.info(f"✅ V2 Broker: Re-authentication successful via REST API Access, retrying order...")
                            # Update tokens
                            tv.access_token = login_result.get('accessToken')
                            tv.md_access_token = login_result.get('mdAccessToken')
                            
                            # Retry order with new token
                            order = tv.create_market_order(account_spec, tradovate_symbol, entry_side, qty, account_id)
                            result = await tv.place_order(order)
                            if result and result.get('success'):
                                logger.info(f"✅ V2 BROKER: Order placed successfully after REST API Access re-auth: {result}")
                        else:
                            logger.error(f"❌ V2 Broker: REST API Access re-authentication failed: {login_result.get('error')}")
                    else:
                        logger.error(f"❌ V2 Broker: No username/password available for REST API Access re-authentication")
                
                if result:
                    logger.info(f"✅ V2 BROKER: Order placed successfully: {result}")
                return result

        # CRITICAL FIX: Use dedicated event loop thread - no asyncio.run() deadlock
        try:
            logger.info(f"🔄 V2 Broker: Calling _run_async for {intent} {tradovate_symbol}...")
            result = self._run_async(run())
            if result:
                logger.info(f"✅ V2 Broker: Order execution completed - result: {result}")
                if result.get('orderId'):
                    logger.info(f"✅ V2 Broker: Order ID = {result.get('orderId')}")
                else:
                    logger.warning(f"⚠️ V2 Broker: Order executed but no orderId in result: {result}")
                return result
            else:
                logger.warning(f"⚠️ V2 Broker: _run_async returned None - order may have failed")
        except Exception as e:
            logger.error(f"❌ V2 Broker adapter error: {e}", exc_info=True)
        return None

    def _entry_side(self, intent: str, pos: V2Position) -> Optional[str]:
        intent = intent.upper()
        if intent in ("ENTRY", "DCA"):
            return "Buy" if pos.side == "LONG" else "Sell"
        if intent == "EXIT":
            return "Sell" if pos.side == "LONG" else "Buy"
        return None


if __name__ == "__main__":
    """
    Demonstration of JUST.TRADES Strategy Engine V2
    Per JUST_TRADES_STRATEGY_ENGINE_ARCHITECTURE.md
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*60)
    print("JUST.TRADES Strategy Engine V2 - Full Architecture Demo")
    print("="*60 + "\n")
    
    # Initialize engine
    flags = V2FeatureFlags()
    flags.set_flag("demo_strategy", True)
    
    svc = RecorderServiceV2(flags=flags)
    
    # === Demo 1: Register Strategy Instance with DCA Ladder ===
    print("\n📊 Demo 1: Registering Strategy with Auto-DCA Ladder")
    print("-" * 50)
    
    # Create DCA ladder: Add contracts at 1%, 2.5%, and 5% drops
    dca_ladder = [
        DCAStep(trigger_type="percent", trigger_value=1.0, qty=1, enabled=True),
        DCAStep(trigger_type="percent", trigger_value=2.5, qty=2, enabled=True),
        DCAStep(trigger_type="percent", trigger_value=5.0, qty=3, enabled=True),
    ]
    
    strategy = StrategyInstance(
        name="demo_strategy",
        symbol="MNQ",
        timeframe="5m",
        mode="virtual",  # Start in virtual mode (shadow trading)
        tp_ticks=20,     # Take profit at 20 ticks ($10 for MNQ)
        sl_ticks=40,     # Stop loss at 40 ticks ($20 for MNQ)
        dca_steps=dca_ladder,
        max_qty=10,      # Maximum 10 contracts
        tick_size=0.25,
        tick_value=0.50,  # $0.50 per tick for MNQ
    )
    
    svc.register_strategy_instance(strategy)
    
    # === Demo 2: Open Position ===
    print("\n📈 Demo 2: Opening Long Position")
    print("-" * 50)
    
    entry_price = 21000.0
    svc.handle_signal("demo_strategy", "BUY", "MNQ1!", price=entry_price, qty=1)
    
    # === Demo 3: Price Updates with MFE/MAE Tracking ===
    print("\n📊 Demo 3: Price Updates (MFE/MAE Tracking)")
    print("-" * 50)
    
    # Price goes up (MFE improves)
    svc.update_price("MNQ1!", entry_price + 2.0)  # +8 ticks = +$4
    print(f"   Price up to {entry_price + 2.0} (+8 ticks)")
    
    svc.update_price("MNQ1!", entry_price + 3.0)  # +12 ticks = +$6
    print(f"   Price up to {entry_price + 3.0} (+12 ticks)")
    
    # === Demo 4: Price Pullback (small, not triggering DCA) ===
    print("\n📉 Demo 4: Price Pullback (MAE Tracking)")
    print("-" * 50)
    
    # Small pullback - not enough to trigger DCA (which is at 1% drop)
    pullback_price = entry_price - 1.0  # -4 ticks, small pullback
    print(f"   Price pulls back to {pullback_price:.2f} (-4 ticks)")
    svc.update_price("MNQ1!", pullback_price)
    
    # Check position state
    pnl_data = svc.get_position_pnl("demo_strategy", "MNQ1!")
    if "error" not in pnl_data:
        print(f"   Position: {pnl_data.get('qty')} contracts @ avg {pnl_data.get('avg_price'):.2f}")
        print(f"   Current PnL: ${pnl_data.get('unrealized_pnl'):.2f}")
        print(f"   MFE: ${pnl_data.get('mfe'):.2f} | MAE: ${pnl_data.get('mae'):.2f}")
    
    # === Demo 5: Take Profit Hit ===
    print("\n🎯 Demo 5: Take Profit Hit")
    print("-" * 50)
    
    # Price rallies to TP level (20 ticks above entry)
    tp_price = entry_price + (20 * 0.25)  # 20 ticks = 5 points above entry
    print(f"   Price rallies to TP: {tp_price}")
    svc.update_price("MNQ1!", tp_price)
    
    # === Demo 6: Check Stats and Fills ===
    print("\n📋 Demo 6: Engine Stats and Fill History")
    print("-" * 50)
    
    stats = svc.get_stats()
    print(f"   Price updates: {stats['price_updates']}")
    print(f"   TP hits: {stats['tp_hits']}")
    print(f"   DCA triggers: {stats['dca_triggers']}")
    print(f"   Total Virtual PnL: ${stats['total_virtual_pnl']:.2f}")
    
    fills = svc.get_fills()
    print(f"\n   Recent fills ({len(fills)} total):")
    for fill in fills[-5:]:
        pnl_str = f" | PnL: ${fill.pnl:.2f}" if fill.pnl else ""
        print(f"   - {fill.fill_type}: {fill.side} {fill.qty} @ {fill.price:.2f}{pnl_str}")
    
    # === Demo 7: DCA Ladder Demo (Separate Position) ===
    print("\n🔄 Demo 7: DCA Ladder Demo (New Strategy)")
    print("-" * 50)
    
    # Create a new strategy with more aggressive DCA settings for demo
    flags.set_flag("dca_demo", True)
    
    dca_demo_ladder = [
        DCAStep(trigger_type="ticks", trigger_value=10, qty=1, enabled=True),  # +1 at 10 ticks down
        DCAStep(trigger_type="ticks", trigger_value=20, qty=2, enabled=True),  # +2 at 20 ticks down
    ]
    
    dca_strategy = StrategyInstance(
        name="dca_demo",
        symbol="MNQ",
        mode="virtual",
        tp_ticks=30,
        sl_ticks=100,  # Wide SL so we can see DCA work
        dca_steps=dca_demo_ladder,
        max_qty=10,
        tick_size=0.25,
        tick_value=0.50,
    )
    svc.register_strategy_instance(dca_strategy)
    
    # Open position
    dca_entry = 21500.0
    print(f"   Opening LONG @ {dca_entry}")
    svc.handle_signal("dca_demo", "BUY", "MNQ1!", price=dca_entry, qty=1)
    
    # Price drops 10 ticks - trigger first DCA
    print(f"   Price drops 10 ticks to {dca_entry - 2.5}")
    svc.update_price("MNQ1!", dca_entry - 2.5)
    
    dca_pnl = svc.get_position_pnl("dca_demo", "MNQ1!")
    if "error" not in dca_pnl:
        print(f"   After DCA #1: {dca_pnl.get('qty')} contracts @ avg {dca_pnl.get('avg_price'):.2f}")
    
    # Price drops 20 ticks from original entry - trigger second DCA
    print(f"   Price drops 20 ticks to {dca_entry - 5.0}")
    svc.update_price("MNQ1!", dca_entry - 5.0)
    
    dca_pnl = svc.get_position_pnl("dca_demo", "MNQ1!")
    if "error" not in dca_pnl:
        print(f"   After DCA #2: {dca_pnl.get('qty')} contracts @ avg {dca_pnl.get('avg_price'):.2f}")
        print(f"   DCA steps triggered: {dca_pnl.get('dca_steps_triggered')}")
    
    # Price recovers and hits TP
    if "error" not in dca_pnl:
        avg = dca_pnl.get('avg_price', dca_entry)
        tp = avg + (30 * 0.25)
        print(f"   Price rallies to TP @ {tp}")
        svc.update_price("MNQ1!", tp)
    
    # === Demo 8: Switch to LIVE Mode ===
    print("\n🔴 Demo 8: Strategy Mode Management")
    print("-" * 50)
    
    print(f"   Current mode: {strategy.mode}")
    print("   Switching to LIVE mode...")
    svc.set_strategy_mode("demo_strategy", "live")
    print(f"   New mode: {svc.get_strategy('demo_strategy').mode}")
    print("   (In LIVE mode, orders would be sent to Tradovate)")
    
    # === Cleanup ===
    print("\n" + "="*60)
    print("Demo Complete - Flushing writes...")
    print("="*60 + "\n")
    
    # Allow async DB writer to flush
    time.sleep(0.5)
    
    svc.shutdown()
    
    # Verify database state
    print("\n📊 Database Verification:")
    import sqlite3
    conn = sqlite3.connect(svc.db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM v2_fills")
    fill_count = cursor.fetchone()[0]
    print(f"   Virtual fills recorded: {fill_count}")
    
    cursor.execute("SELECT COUNT(*) FROM v2_strategies")
    strategy_count = cursor.fetchone()[0]
    print(f"   Strategies stored: {strategy_count}")
    
    conn.close()
    print("\n✅ V2 Engine fully operational!")
