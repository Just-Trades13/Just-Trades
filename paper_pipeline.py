"""
PaperPipeline — Orchestrates PaperTradingEngine + PostgreSQL persistence + SocketIO broadcast.

Adapted from reference pipeline for PostgreSQL compatibility (Rule 4: %s placeholders).
Uses DATABASE_URL env var (same as production). Falls back to SQLite for local dev.
"""

import os
import json
import logging
import threading
from datetime import datetime
from contextlib import contextmanager

from paper_engine_v3 import PaperTradingEngine

logger = logging.getLogger(__name__)


def _is_postgres():
    """Check if production PostgreSQL is in use."""
    db_url = os.environ.get('DATABASE_URL', '')
    return 'postgres' in db_url.lower()


# ─── Database layer ────────────────────────────────────────────────────────────

class PaperTradeDB:
    """
    Persistence layer for paper trades.
    PostgreSQL in production (DATABASE_URL), SQLite for local dev.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._use_pg = _is_postgres()
        if not self._use_pg:
            self._db_path = os.path.join(os.path.dirname(__file__) or '.', 'paper_trades_v3.db')
        self._ensure_schema()

    @contextmanager
    def _conn(self):
        """Get a DB connection with auto-commit/rollback."""
        if self._use_pg:
            import psycopg2
            import psycopg2.extras
            db_url = os.environ.get('DATABASE_URL', '')
            conn = psycopg2.connect(db_url)
            conn.autocommit = False
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            import sqlite3
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def _ensure_schema(self):
        """Create paper_trades_v3 table if it doesn't exist, add columns if missing."""
        with self._lock, self._conn() as conn:
            cur = conn.cursor()
            if self._use_pg:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS paper_trades_v3 (
                        id              TEXT PRIMARY KEY,
                        account         TEXT NOT NULL DEFAULT 'default',
                        symbol          TEXT NOT NULL,
                        side            TEXT NOT NULL,
                        qty             INTEGER NOT NULL,
                        avg_entry       REAL NOT NULL,
                        exit_price      REAL,
                        strategy_id     TEXT DEFAULT '',
                        comment         TEXT DEFAULT '',
                        exit_comment    TEXT DEFAULT '',
                        realized_pnl    REAL,
                        gross_pnl       REAL,
                        commission      REAL,
                        unrealized_pnl  REAL DEFAULT 0,
                        mae_points      REAL,
                        mfe_points      REAL,
                        mae_ticks       INTEGER,
                        mfe_ticks       INTEGER,
                        mae_dollars     REAL,
                        mfe_dollars     REAL,
                        mae_price       REAL,
                        mfe_price       REAL,
                        capture_ratio   REAL,
                        efficiency      REAL,
                        tick_count      INTEGER,
                        highest_seen    REAL,
                        lowest_seen     REAL,
                        hold_time_seconds INTEGER,
                        tp              REAL,
                        sl              REAL,
                        trail_points    REAL,
                        entry_time      TEXT,
                        exit_time       TEXT,
                        legs            TEXT,
                        status          TEXT DEFAULT 'open',
                        source          TEXT DEFAULT 'webhook',
                        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ptv3_account_status
                    ON paper_trades_v3(account, status)
                """)
            else:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS paper_trades_v3 (
                        id              TEXT PRIMARY KEY,
                        account         TEXT NOT NULL DEFAULT 'default',
                        symbol          TEXT NOT NULL,
                        side            TEXT NOT NULL,
                        qty             INTEGER NOT NULL,
                        avg_entry       REAL NOT NULL,
                        exit_price      REAL,
                        strategy_id     TEXT DEFAULT '',
                        comment         TEXT DEFAULT '',
                        exit_comment    TEXT DEFAULT '',
                        realized_pnl    REAL,
                        gross_pnl       REAL,
                        commission      REAL,
                        unrealized_pnl  REAL DEFAULT 0,
                        mae_points      REAL,
                        mfe_points      REAL,
                        mae_ticks       INTEGER,
                        mfe_ticks       INTEGER,
                        mae_dollars     REAL,
                        mfe_dollars     REAL,
                        mae_price       REAL,
                        mfe_price       REAL,
                        capture_ratio   REAL,
                        efficiency      REAL,
                        tick_count      INTEGER,
                        highest_seen    REAL,
                        lowest_seen     REAL,
                        hold_time_seconds INTEGER,
                        tp              REAL,
                        sl              REAL,
                        trail_points    REAL,
                        entry_time      TEXT,
                        exit_time       TEXT,
                        legs            TEXT,
                        status          TEXT DEFAULT 'open',
                        source          TEXT DEFAULT 'webhook',
                        created_at      TEXT DEFAULT (datetime('now'))
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ptv3_account_status
                    ON paper_trades_v3(account, status)
                """)

    def _ph(self):
        """Placeholder: %s for PostgreSQL, ? for SQLite."""
        return '%s' if self._use_pg else '?'

    def upsert_trade(self, trade, account="default"):
        """Insert or update a paper trade record."""
        ph = self._ph()
        legs_json = json.dumps(trade.get('legs', []))

        # Use ON CONFLICT for upsert
        if self._use_pg:
            sql = f"""
                INSERT INTO paper_trades_v3 (
                    id, account, symbol, side, qty, avg_entry, exit_price,
                    strategy_id, comment, exit_comment,
                    realized_pnl, gross_pnl, commission, unrealized_pnl,
                    mae_points, mfe_points, mae_ticks, mfe_ticks,
                    mae_dollars, mfe_dollars, mae_price, mfe_price,
                    capture_ratio, efficiency, tick_count, highest_seen, lowest_seen,
                    hold_time_seconds, tp, sl, trail_points,
                    entry_time, exit_time, legs, status, source
                ) VALUES (
                    {ph},{ph},{ph},{ph},{ph},{ph},{ph},
                    {ph},{ph},{ph},
                    {ph},{ph},{ph},{ph},
                    {ph},{ph},{ph},{ph},
                    {ph},{ph},{ph},{ph},
                    {ph},{ph},{ph},{ph},{ph},
                    {ph},{ph},{ph},{ph},
                    {ph},{ph},{ph},{ph},{ph}
                )
                ON CONFLICT (id) DO UPDATE SET
                    exit_price=EXCLUDED.exit_price,
                    realized_pnl=EXCLUDED.realized_pnl,
                    gross_pnl=EXCLUDED.gross_pnl,
                    commission=EXCLUDED.commission,
                    unrealized_pnl=EXCLUDED.unrealized_pnl,
                    mae_points=EXCLUDED.mae_points, mfe_points=EXCLUDED.mfe_points,
                    mae_ticks=EXCLUDED.mae_ticks, mfe_ticks=EXCLUDED.mfe_ticks,
                    mae_dollars=EXCLUDED.mae_dollars, mfe_dollars=EXCLUDED.mfe_dollars,
                    mae_price=EXCLUDED.mae_price, mfe_price=EXCLUDED.mfe_price,
                    capture_ratio=EXCLUDED.capture_ratio, efficiency=EXCLUDED.efficiency,
                    tick_count=EXCLUDED.tick_count,
                    highest_seen=EXCLUDED.highest_seen, lowest_seen=EXCLUDED.lowest_seen,
                    hold_time_seconds=EXCLUDED.hold_time_seconds,
                    exit_time=EXCLUDED.exit_time,
                    exit_comment=EXCLUDED.exit_comment,
                    legs=EXCLUDED.legs, status=EXCLUDED.status,
                    qty=EXCLUDED.qty, avg_entry=EXCLUDED.avg_entry
            """
        else:
            sql = """
                INSERT OR REPLACE INTO paper_trades_v3 (
                    id, account, symbol, side, qty, avg_entry, exit_price,
                    strategy_id, comment, exit_comment,
                    realized_pnl, gross_pnl, commission, unrealized_pnl,
                    mae_points, mfe_points, mae_ticks, mfe_ticks,
                    mae_dollars, mfe_dollars, mae_price, mfe_price,
                    capture_ratio, efficiency, tick_count, highest_seen, lowest_seen,
                    hold_time_seconds, tp, sl, trail_points,
                    entry_time, exit_time, legs, status, source
                ) VALUES (
                    ?,?,?,?,?,?,?,
                    ?,?,?,
                    ?,?,?,?,
                    ?,?,?,?,
                    ?,?,?,?,
                    ?,?,?,?,?,
                    ?,?,?,?,
                    ?,?,?,?,?
                )
            """

        params = (
            trade.get('id'),
            account,
            trade.get('symbol'),
            trade.get('side'),
            trade.get('qty'),
            trade.get('avg_entry'),
            trade.get('exit_price'),
            trade.get('strategy_id', ''),
            trade.get('comment', ''),
            trade.get('exit_comment', ''),
            trade.get('realized_pnl'),
            trade.get('gross_pnl'),
            trade.get('commission'),
            trade.get('unrealized_pnl', 0),
            trade.get('mae_points'),
            trade.get('mfe_points'),
            trade.get('mae_ticks'),
            trade.get('mfe_ticks'),
            trade.get('mae_dollars'),
            trade.get('mfe_dollars'),
            trade.get('mae_price'),
            trade.get('mfe_price'),
            trade.get('capture_ratio'),
            trade.get('efficiency'),
            trade.get('tick_count'),
            trade.get('highest_seen'),
            trade.get('lowest_seen'),
            trade.get('hold_time_seconds'),
            trade.get('tp'),
            trade.get('sl'),
            trade.get('trail_points'),
            trade.get('entry_time'),
            trade.get('exit_time'),
            legs_json,
            trade.get('status', 'open'),
            trade.get('source', 'webhook'),
        )

        with self._lock, self._conn() as conn:
            conn.cursor().execute(sql, params)

    def load_history(self, account="default", limit=200):
        """Load closed trades from DB."""
        ph = self._ph()
        with self._lock, self._conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT * FROM paper_trades_v3
                WHERE account = {ph} AND status = 'closed'
                ORDER BY exit_time DESC
                LIMIT {ph}
            """, (account, limit))
            rows = cur.fetchall()

        result = []
        for row in rows:
            if self._use_pg:
                t = dict(zip([desc[0] for desc in cur.description], row))
            else:
                t = dict(row)
            try:
                t['legs'] = json.loads(t.get('legs') or '[]')
            except Exception:
                t['legs'] = []
            result.append(t)
        return list(reversed(result))

    def load_open_positions(self, account="default"):
        """Reload open positions on restart (crash recovery)."""
        ph = self._ph()
        with self._lock, self._conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT * FROM paper_trades_v3
                WHERE account = {ph} AND status = 'open'
            """, (account,))
            rows = cur.fetchall()

        result = []
        for row in rows:
            if self._use_pg:
                t = dict(zip([desc[0] for desc in cur.description], row))
            else:
                t = dict(row)
            try:
                t['legs'] = json.loads(t.get('legs') or '[]')
            except Exception:
                t['legs'] = []
            result.append(t)
        return result

    def get_stats(self, account="default"):
        """Aggregate stats from DB."""
        ph = self._ph()
        with self._lock, self._conn() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT
                    COUNT(*)                                    as total,
                    SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(realized_pnl)                          as total_pnl,
                    AVG(mae_points)                            as avg_mae,
                    AVG(mfe_points)                            as avg_mfe,
                    AVG(capture_ratio)                         as avg_capture
                FROM paper_trades_v3
                WHERE account = {ph} AND status = 'closed'
            """, (account,))
            row = cur.fetchone()
        if row is None:
            return {}
        if self._use_pg:
            return dict(zip([desc[0] for desc in cur.description], row))
        return dict(row)


# ─── The Pipeline ──────────────────────────────────────────────────────────────

class PaperPipeline:
    """
    Owns the full paper trading lifecycle:
    engine (in-memory) + DB (persistence) + SocketIO (broadcast).
    """

    def __init__(self, socketio=None, broadcast_namespace="/paper"):
        self.db = PaperTradeDB()
        self.engine = PaperTradingEngine(socketio=None, broadcast_namespace=broadcast_namespace)
        self.socketio = socketio
        self.namespace = broadcast_namespace

        self._patch_engine_callbacks()
        self._restore_from_db()

        logger.info("[PaperPipeline] Initialized — DB=%s", "PostgreSQL" if self.db._use_pg else "SQLite")

    def _restore_from_db(self, account="default"):
        """Reload closed trade history into engine on startup."""
        try:
            history = self.db.load_history(account)
            if history:
                self.engine._history = history
                total_pnl = sum(t.get('realized_pnl', 0) for t in history)
                self.engine._realized[account] = total_pnl
                logger.info(f"[PaperPipeline] Restored {len(history)} closed trades "
                            f"(realized=${total_pnl:.2f})")
        except Exception as e:
            logger.warning(f"[PaperPipeline] DB restore failed: {e}")

    def _patch_engine_callbacks(self):
        """Wrap engine close methods to auto-persist to DB."""
        original_close = self.engine._close_position_locked
        original_partial = self.engine._partial_close_locked

        def patched_close(account, symbol, exit_price, comment=""):
            original_close(account, symbol, exit_price, comment)
            if self.engine._history:
                trade = dict(self.engine._history[-1])  # copy for thread safety
                def _persist():
                    try:
                        self.db.upsert_trade(trade, account)
                    except Exception as e:
                        logger.error(f"[PaperPipeline] DB persist failed: {e}")
                threading.Thread(target=_persist, daemon=True).start()
            self._broadcast(account)

        def patched_partial(account, symbol, close_qty, exit_price, comment=""):
            original_partial(account, symbol, close_qty, exit_price, comment)
            if self.engine._history:
                trade = dict(self.engine._history[-1])
                def _persist():
                    try:
                        self.db.upsert_trade(trade, account)
                    except Exception as e:
                        logger.error(f"[PaperPipeline] DB persist failed: {e}")
                threading.Thread(target=_persist, daemon=True).start()
            self._broadcast(account)

        self.engine._close_position_locked = patched_close
        self.engine._partial_close_locked = patched_partial

    # ── Webhook entry point ─────────────────────────────────────────────────

    def on_webhook(self, payload):
        """Process a TradingView webhook for paper trading."""
        account = str(payload.get("account", "default"))
        result = self.engine.on_signal(payload)

        # Persist open position to DB in background (so we have a record before close)
        symbol = str(payload.get("ticker", payload.get("symbol", ""))).upper()
        pos = self.engine._get_position(account, symbol)
        if pos is not None and pos.get("status") == "open":
            trade_record = {k: v for k, v in pos.items() if not k.startswith('_')}
            trade_record['unrealized_pnl'] = pos.get('unrealized_pnl', 0)
            def _persist_open():
                try:
                    self.db.upsert_trade(trade_record, account)
                except Exception as e:
                    logger.error(f"[PaperPipeline] open position persist failed: {e}")
            threading.Thread(target=_persist_open, daemon=True).start()

        self._broadcast(account)
        return {**result, "account": account, "symbol": symbol}

    # ── Tick entry point ────────────────────────────────────────────────────

    def on_tick(self, symbol, price):
        """Feed a price tick to the engine. Auto-closes handled via patched callbacks."""
        self.engine.on_tick(symbol, price)

    # ── Risk system ─────────────────────────────────────────────────────────

    def risk_close(self, symbol, reason, account="default", price=None):
        """Force-close a position (risk management)."""
        exit_price = price or self.engine._marks.get(symbol.upper(), 0)
        if exit_price == 0:
            return {"status": "error", "message": "no price"}
        result = self.engine._handle_exit(account, symbol.upper(), exit_price,
                                          comment=f"RISK:{reason}")
        self._broadcast(account)
        return result

    def flatten_all(self, account="default", reason="FLATTEN_ALL"):
        """Close every open paper position for an account."""
        with self.engine._lock:
            symbols = [
                sym for sym, pos in self.engine._positions.get(account, {}).items()
                if pos is not None and pos.get("status") == "open"
            ]
        for sym in symbols:
            price = self.engine._marks.get(sym, 0)
            if price > 0:
                self.risk_close(sym, reason, account, price)

    # ── State access ────────────────────────────────────────────────────────

    def get_state(self, account="default"):
        return self.engine.get_state(account)

    def get_analysis(self, account="default", strategy_id=None):
        return self.engine.get_mae_mfe_analysis(account, strategy_id=strategy_id)

    # ── Broadcast ───────────────────────────────────────────────────────────

    def _broadcast(self, account="default"):
        """Emit full state to connected dashboard clients (non-blocking daemon thread)."""
        if self.socketio is None:
            return
        try:
            state = self.get_state(account)
            sio = self.socketio
            ns = self.namespace
            t = threading.Thread(target=lambda: sio.emit("paper_state", state, namespace=ns),
                                 daemon=True)
            t.start()
        except Exception as e:
            logger.error(f"[PaperPipeline] Broadcast error: {e}")
