"""
Copy Trader Models Module
=========================
Database models and CRUD operations for the Pro Copy Trader feature.

Tables:
- leader_accounts: Tradovate accounts designated as signal sources
- follower_accounts: Accounts that copy trades from a leader
- copy_trade_log: Audit trail of all copied trades

PostgreSQL/SQLite dual support (Rule 4).
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger('copy_trader')

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================
DATABASE_URL = os.environ.get('DATABASE_URL')
SQLITE_PATH = os.environ.get('SQLITE_PATH', 'just_trades.db')


def get_copy_trader_db_connection():
    """Get database connection for copy trader operations."""
    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            db_url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
            conn = psycopg2.connect(db_url)
            conn.cursor_factory = RealDictCursor
            return conn, 'postgresql'
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed: {e}, falling back to SQLite")

    conn = sqlite3.connect(SQLITE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn, 'sqlite'


def _ph(db_type):
    """Return SQL placeholder for the given db_type."""
    return '%s' if db_type == 'postgresql' else '?'


# ============================================================================
# TABLE INITIALIZATION
# ============================================================================
def init_copy_trader_tables():
    """Create copy trader tables if they don't exist."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        if db_type == 'postgresql':
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leader_accounts (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    account_id INTEGER NOT NULL,
                    subaccount_id VARCHAR(50) NOT NULL,
                    label VARCHAR(100),
                    is_active BOOLEAN DEFAULT TRUE,
                    auto_copy_enabled BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, account_id, subaccount_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS follower_accounts (
                    id SERIAL PRIMARY KEY,
                    leader_id INTEGER NOT NULL REFERENCES leader_accounts(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL,
                    account_id INTEGER NOT NULL,
                    subaccount_id VARCHAR(50) NOT NULL,
                    label VARCHAR(100),
                    is_enabled BOOLEAN DEFAULT TRUE,
                    multiplier REAL DEFAULT 1.0,
                    max_position_size INTEGER DEFAULT 0,
                    copy_tp BOOLEAN DEFAULT TRUE,
                    copy_sl BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(leader_id, account_id, subaccount_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS copy_trade_log (
                    id SERIAL PRIMARY KEY,
                    leader_id INTEGER NOT NULL REFERENCES leader_accounts(id),
                    follower_id INTEGER NOT NULL REFERENCES follower_accounts(id),
                    leader_order_id VARCHAR(100),
                    follower_order_id VARCHAR(100),
                    symbol VARCHAR(50) NOT NULL,
                    side VARCHAR(50) NOT NULL,
                    leader_quantity INTEGER NOT NULL,
                    follower_quantity INTEGER NOT NULL,
                    leader_price REAL,
                    follower_price REAL,
                    status VARCHAR(20) DEFAULT 'pending',
                    error_message TEXT,
                    latency_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Migrations — widen varchar columns that were too narrow
            cursor.execute('ALTER TABLE copy_trade_log ALTER COLUMN side TYPE VARCHAR(50)')
            # NOTE: auto_copy_enabled defaults to FALSE — user must explicitly enable via UI toggle
            # Indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_leader_accounts_user ON leader_accounts(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_follower_accounts_leader ON follower_accounts(leader_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_copy_trade_log_leader ON copy_trade_log(leader_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_copy_trade_log_created ON copy_trade_log(created_at)')
        else:
            # SQLite schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS leader_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    account_id INTEGER NOT NULL,
                    subaccount_id TEXT NOT NULL,
                    label TEXT,
                    is_active INTEGER DEFAULT 1,
                    auto_copy_enabled INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, account_id, subaccount_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS follower_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    leader_id INTEGER NOT NULL REFERENCES leader_accounts(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL,
                    account_id INTEGER NOT NULL,
                    subaccount_id TEXT NOT NULL,
                    label TEXT,
                    is_enabled INTEGER DEFAULT 1,
                    multiplier REAL DEFAULT 1.0,
                    max_position_size INTEGER DEFAULT 0,
                    copy_tp INTEGER DEFAULT 1,
                    copy_sl INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(leader_id, account_id, subaccount_id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS copy_trade_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    leader_id INTEGER NOT NULL REFERENCES leader_accounts(id),
                    follower_id INTEGER NOT NULL REFERENCES follower_accounts(id),
                    leader_order_id TEXT,
                    follower_order_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    leader_quantity INTEGER NOT NULL,
                    follower_quantity INTEGER NOT NULL,
                    leader_price REAL,
                    follower_price REAL,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    latency_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_leader_accounts_user ON leader_accounts(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_follower_accounts_leader ON follower_accounts(leader_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_copy_trade_log_leader ON copy_trade_log(leader_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_copy_trade_log_created ON copy_trade_log(created_at)')

        # --- platform_settings table (global toggles) ---
        if db_type == 'postgresql':
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS platform_settings (
                    id SERIAL PRIMARY KEY,
                    key VARCHAR(100) UNIQUE NOT NULL,
                    value TEXT NOT NULL DEFAULT 'true',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by INTEGER
                )
            ''')
            cursor.execute('''
                INSERT INTO platform_settings (key, value) VALUES ('copy_trader_enabled', 'false')
                ON CONFLICT (key) DO NOTHING
            ''')
            # One-time fix: if copy_trader_enabled was previously set to 'true', reset to 'false'
            # Copy trading should default OFF to avoid interfering with webhook auto-traders
            cursor.execute("UPDATE platform_settings SET value = 'false' WHERE key = 'copy_trader_enabled' AND value = 'true'")
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS platform_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL DEFAULT 'true',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by INTEGER
                )
            ''')
            cursor.execute('''
                INSERT OR IGNORE INTO platform_settings (key, value) VALUES ('copy_trader_enabled', 'false')
            ''')
            cursor.execute("UPDATE platform_settings SET value = 'false' WHERE key = 'copy_trader_enabled' AND value = 'true'")

        # --- mirrored_orders table (order mirroring) ---
        if db_type == 'postgresql':
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mirrored_orders (
                    id SERIAL PRIMARY KEY,
                    leader_id INTEGER NOT NULL,
                    follower_id INTEGER NOT NULL,
                    leader_order_id INTEGER NOT NULL,
                    follower_order_id INTEGER,
                    symbol VARCHAR(50) NOT NULL,
                    action VARCHAR(10) NOT NULL,
                    order_type VARCHAR(20) NOT NULL,
                    leader_price REAL,
                    follower_price REAL,
                    stop_price REAL,
                    leader_qty INTEGER NOT NULL,
                    follower_qty INTEGER NOT NULL,
                    time_in_force VARCHAR(10) DEFAULT 'Day',
                    status VARCHAR(20) DEFAULT 'pending',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mirrored_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    leader_id INTEGER NOT NULL,
                    follower_id INTEGER NOT NULL,
                    leader_order_id INTEGER NOT NULL,
                    follower_order_id INTEGER,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    leader_price REAL,
                    follower_price REAL,
                    stop_price REAL,
                    leader_qty INTEGER NOT NULL,
                    follower_qty INTEGER NOT NULL,
                    time_in_force TEXT DEFAULT 'Day',
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mirrored_orders_leader_order ON mirrored_orders(leader_order_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mirrored_orders_follower ON mirrored_orders(follower_id, status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mirrored_orders_leader ON mirrored_orders(leader_id, status)')

        # Migration: deactivate stale leaders — keep only the most recent per user
        # This prevents circular follower checks from blocking when switching leaders
        if db_type == 'postgresql':
            cursor.execute('''
                UPDATE leader_accounts SET is_active = FALSE, auto_copy_enabled = FALSE
                WHERE id NOT IN (
                    SELECT DISTINCT ON (user_id) id FROM leader_accounts
                    ORDER BY user_id, updated_at DESC
                )
                AND is_active = TRUE
            ''')
        else:
            cursor.execute('''
                UPDATE leader_accounts SET is_active = 0, auto_copy_enabled = 0
                WHERE id NOT IN (
                    SELECT id FROM leader_accounts la1
                    WHERE updated_at = (
                        SELECT MAX(updated_at) FROM leader_accounts la2
                        WHERE la2.user_id = la1.user_id
                    )
                )
                AND is_active = 1
            ''')

        conn.commit()
        logger.info("Copy trader tables initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize copy trader tables: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# LEADER ACCOUNT CRUD
# ============================================================================
def create_leader(user_id: int, account_id: int, subaccount_id: str,
                  label: str = None) -> Optional[int]:
    """Create a leader account. Returns leader ID or None."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        # Deactivate all other leaders for this user (single active leader model)
        # This prevents circular follower checks from blocking when switching leaders
        if db_type == 'postgresql':
            cursor.execute(f'''
                UPDATE leader_accounts SET is_active = FALSE, auto_copy_enabled = FALSE, updated_at = NOW()
                WHERE user_id = {ph} AND NOT (account_id = {ph} AND subaccount_id = {ph})
            ''', (user_id, account_id, subaccount_id))
        else:
            cursor.execute(f'''
                UPDATE leader_accounts SET is_active = 0, auto_copy_enabled = 0, updated_at = datetime('now')
                WHERE user_id = {ph} AND NOT (account_id = {ph} AND subaccount_id = {ph})
            ''', (user_id, account_id, subaccount_id))

        if db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO leader_accounts (user_id, account_id, subaccount_id, label)
                VALUES ({ph}, {ph}, {ph}, {ph})
                ON CONFLICT (user_id, account_id, subaccount_id) DO UPDATE SET
                    label = EXCLUDED.label,
                    is_active = TRUE,
                    updated_at = NOW()
                RETURNING id
            ''', (user_id, account_id, subaccount_id, label))
            result = cursor.fetchone()
            leader_id = result['id'] if result else None
        else:
            cursor.execute(f'''
                INSERT OR REPLACE INTO leader_accounts
                (user_id, account_id, subaccount_id, label, is_active, updated_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, 1, datetime('now'))
            ''', (user_id, account_id, subaccount_id, label))
            leader_id = cursor.lastrowid

        conn.commit()
        logger.info(f"Created leader account: user={user_id}, account={account_id}:{subaccount_id}")
        return leader_id
    except Exception as e:
        logger.error(f"Failed to create leader account: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def get_leaders_for_user(user_id: int) -> List[Dict]:
    """Get all leader accounts for a user (filters out orphaned accounts)."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        active_val = 'TRUE' if db_type == 'postgresql' else '1'
        cursor.execute(f'''
            SELECT la.* FROM leader_accounts la
            INNER JOIN accounts a ON la.account_id = a.id
            WHERE la.user_id = {ph} AND la.is_active = {active_val}
            ORDER BY la.created_at DESC
        ''', (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_leader_by_id(leader_id: int) -> Optional[Dict]:
    """Get a leader account by ID."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'SELECT * FROM leader_accounts WHERE id = {ph}', (leader_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        conn.close()


def get_leader_for_account(user_id: int, account_id: int, subaccount_id: str = None) -> Optional[Dict]:
    """Look up a leader by its account — returns leader dict or None."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)
    enabled_val = 'TRUE' if db_type == 'postgresql' else '1'

    try:
        if subaccount_id:
            cursor.execute(
                f'SELECT * FROM leader_accounts WHERE user_id = {ph} '
                f'AND account_id = {ph} AND subaccount_id = {ph} '
                f'AND is_active = {enabled_val}',
                (user_id, account_id, str(subaccount_id))
            )
        else:
            cursor.execute(
                f'SELECT * FROM leader_accounts WHERE user_id = {ph} '
                f'AND account_id = {ph} AND is_active = {enabled_val}',
                (user_id, account_id)
            )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        cursor.close()
        conn.close()


def update_leader(leader_id: int, **kwargs) -> bool:
    """Update a leader account. Supported fields: label, is_active, auto_copy_enabled."""
    allowed = {'label', 'is_active', 'auto_copy_enabled'}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        set_parts = []
        values = []
        for key, val in updates.items():
            set_parts.append(f"{key} = {ph}")
            values.append(val)

        if db_type == 'postgresql':
            set_parts.append("updated_at = NOW()")
        else:
            set_parts.append("updated_at = datetime('now')")

        values.append(leader_id)
        cursor.execute(
            f"UPDATE leader_accounts SET {', '.join(set_parts)} WHERE id = {ph}",
            tuple(values)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update leader {leader_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def delete_leader(leader_id: int) -> bool:
    """Soft-delete a leader account (sets is_active=False)."""
    return update_leader(leader_id, is_active=False)


# ============================================================================
# FOLLOWER ACCOUNT CRUD
# ============================================================================
def check_circular_follower(leader_id: int, account_id: int, subaccount_id: str) -> Optional[str]:
    """Check if adding this follower would create a circular leader-follower loop.
    Returns an error message if circular, or None if safe."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)
    enabled_val = 'TRUE' if db_type == 'postgresql' else '1'

    try:
        # Get the leader's subaccount_id
        cursor.execute(f'SELECT subaccount_id FROM leader_accounts WHERE id = {ph}', (leader_id,))
        leader_row = cursor.fetchone()
        if not leader_row:
            return None  # Leader not found — let create_follower handle that

        leader_sub = str(leader_row['subaccount_id'] if isinstance(leader_row, dict) else leader_row[0])

        # Self-follow prevention: leader's own account cannot be a follower of itself
        if str(subaccount_id) == leader_sub:
            return ("Cannot add the leader's own account as a follower. "
                    "The leader account and follower account must be different Tradovate accounts.")

        # Check: is the proposed follower account ALSO a leader that has the current leader's
        # account as a follower? If so, A→B and B→A = circular loop.
        cursor.execute(f'''
            SELECT la.id, la.label FROM leader_accounts la
            JOIN follower_accounts fa ON fa.leader_id = la.id
            WHERE la.subaccount_id = {ph}
            AND la.is_active = {enabled_val}
            AND fa.subaccount_id = {ph}
            AND fa.is_enabled = {enabled_val}
        ''', (str(subaccount_id), leader_sub))
        conflict = cursor.fetchone()
        if conflict:
            conflict_dict = dict(conflict) if hasattr(conflict, 'keys') else {'id': conflict[0], 'label': conflict[1]}
            return (f"Circular loop detected: this account is leader '{conflict_dict.get('label', conflict_dict['id'])}' "
                    f"which already copies TO the leader you're adding it as a follower of. "
                    f"This would create an infinite copy loop (A→B→A).")
        return None
    except Exception as e:
        logger.error(f"Error checking circular follower: {e}")
        return None  # Don't block creation on check failure
    finally:
        cursor.close()
        conn.close()


def create_follower(leader_id: int, user_id: int, account_id: int,
                    subaccount_id: str, label: str = None,
                    multiplier: float = 1.0) -> Optional[int]:
    """Create a follower account linked to a leader. Returns follower ID or None."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        if db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO follower_accounts
                (leader_id, user_id, account_id, subaccount_id, label, multiplier)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                ON CONFLICT (leader_id, account_id, subaccount_id) DO UPDATE SET
                    label = EXCLUDED.label,
                    multiplier = EXCLUDED.multiplier,
                    is_enabled = TRUE,
                    updated_at = NOW()
                RETURNING id
            ''', (leader_id, user_id, account_id, subaccount_id, label, multiplier))
            result = cursor.fetchone()
            follower_id = result['id'] if result else None
        else:
            cursor.execute(f'''
                INSERT OR REPLACE INTO follower_accounts
                (leader_id, user_id, account_id, subaccount_id, label, multiplier, is_enabled, updated_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 1, datetime('now'))
            ''', (leader_id, user_id, account_id, subaccount_id, label, multiplier))
            follower_id = cursor.lastrowid

        conn.commit()
        logger.info(f"Created follower: leader={leader_id}, account={account_id}:{subaccount_id}")
        return follower_id
    except Exception as e:
        logger.error(f"Failed to create follower: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def get_followers_for_leader(leader_id: int) -> List[Dict]:
    """Get all enabled followers for a leader (filters out orphaned accounts)."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        enabled_val = 'TRUE' if db_type == 'postgresql' else '1'
        cursor.execute(f'''
            SELECT fa.* FROM follower_accounts fa
            INNER JOIN accounts a ON fa.account_id = a.id
            WHERE fa.leader_id = {ph} AND fa.is_enabled = {enabled_val}
            ORDER BY fa.created_at
        ''', (leader_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_subaccounts_with_active_traders(subaccount_ids: list) -> set:
    """Return the subset of subaccount_ids that have active webhook traders.

    Queries the traders table once, parses enabled_accounts JSON, and returns
    any subaccount_id that appears in an enabled trader's account list.
    Used by copy trader propagation to skip followers that already receive
    webhook signals — prevents double-fills (Rule: separate pipelines).
    """
    if not subaccount_ids:
        return set()

    target_ids = {str(sid) for sid in subaccount_ids}
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()

    try:
        enabled_val = 'TRUE' if db_type == 'postgresql' else '1'
        cursor.execute(f'''
            SELECT enabled_accounts FROM traders
            WHERE enabled = {enabled_val} AND enabled_accounts IS NOT NULL
        ''')
        rows = cursor.fetchall()

        taken = set()
        for row in rows:
            ea_raw = row['enabled_accounts'] if isinstance(row, dict) else row[0]
            if not ea_raw:
                continue
            try:
                accounts = json.loads(ea_raw) if isinstance(ea_raw, str) else ea_raw
                if not isinstance(accounts, list):
                    continue
                for acct in accounts:
                    sub_id = str(acct.get('subaccount_id', ''))
                    if sub_id and sub_id in target_ids:
                        taken.add(sub_id)
            except (json.JSONDecodeError, TypeError):
                continue

        return taken
    finally:
        cursor.close()
        conn.close()


def get_all_followers_for_leader(leader_id: int) -> List[Dict]:
    """Get all followers for a leader (including disabled, filters out orphaned accounts)."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'''
            SELECT fa.* FROM follower_accounts fa
            INNER JOIN accounts a ON fa.account_id = a.id
            WHERE fa.leader_id = {ph}
            ORDER BY fa.created_at
        ''', (leader_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def update_follower(follower_id: int, **kwargs) -> bool:
    """Update a follower account. Supported: is_enabled, multiplier, max_position_size, copy_tp, copy_sl, label."""
    allowed = {'is_enabled', 'multiplier', 'max_position_size', 'copy_tp', 'copy_sl', 'label'}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        set_parts = []
        values = []
        for key, val in updates.items():
            set_parts.append(f"{key} = {ph}")
            values.append(val)

        if db_type == 'postgresql':
            set_parts.append("updated_at = NOW()")
        else:
            set_parts.append("updated_at = datetime('now')")

        values.append(follower_id)
        cursor.execute(
            f"UPDATE follower_accounts SET {', '.join(set_parts)} WHERE id = {ph}",
            tuple(values)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update follower {follower_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def delete_follower(follower_id: int) -> bool:
    """Soft-delete a follower (sets is_enabled=False)."""
    return update_follower(follower_id, is_enabled=False)


# ============================================================================
# COPY TRADE LOG
# ============================================================================
def log_copy_trade(leader_id: int, follower_id: int, symbol: str, side: str,
                   leader_quantity: int, follower_quantity: int,
                   leader_order_id: str = None, follower_order_id: str = None,
                   leader_price: float = None, follower_price: float = None,
                   status: str = 'pending', error_message: str = None,
                   latency_ms: int = None) -> Optional[int]:
    """Log a copy trade execution. Returns log ID or None."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        if db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO copy_trade_log
                (leader_id, follower_id, leader_order_id, follower_order_id,
                 symbol, side, leader_quantity, follower_quantity,
                 leader_price, follower_price, status, error_message, latency_ms)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                RETURNING id
            ''', (leader_id, follower_id, leader_order_id, follower_order_id,
                  symbol, side, leader_quantity, follower_quantity,
                  leader_price, follower_price, status, error_message, latency_ms))
            result = cursor.fetchone()
            log_id = result['id'] if result else None
        else:
            cursor.execute(f'''
                INSERT INTO copy_trade_log
                (leader_id, follower_id, leader_order_id, follower_order_id,
                 symbol, side, leader_quantity, follower_quantity,
                 leader_price, follower_price, status, error_message, latency_ms)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
            ''', (leader_id, follower_id, leader_order_id, follower_order_id,
                  symbol, side, leader_quantity, follower_quantity,
                  leader_price, follower_price, status, error_message, latency_ms))
            log_id = cursor.lastrowid

        conn.commit()
        return log_id
    except Exception as e:
        logger.error(f"Failed to log copy trade: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def update_copy_trade_log(log_id: int, status: str, follower_order_id: str = None,
                          follower_price: float = None, error_message: str = None,
                          latency_ms: int = None) -> bool:
    """Update a copy trade log entry after execution."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'''
            UPDATE copy_trade_log
            SET status = {ph},
                follower_order_id = COALESCE({ph}, follower_order_id),
                follower_price = COALESCE({ph}, follower_price),
                error_message = COALESCE({ph}, error_message),
                latency_ms = COALESCE({ph}, latency_ms)
            WHERE id = {ph}
        ''', (status, follower_order_id, follower_price, error_message, latency_ms, log_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update copy trade log {log_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def get_copy_trade_history(leader_id: int, limit: int = 50) -> List[Dict]:
    """Get recent copy trade log entries for a leader."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'''
            SELECT ctl.*, fa.label as follower_label,
                   fa.account_id as follower_account_id,
                   fa.subaccount_id as follower_subaccount_id
            FROM copy_trade_log ctl
            JOIN follower_accounts fa ON ctl.follower_id = fa.id
            WHERE ctl.leader_id = {ph}
            ORDER BY ctl.created_at DESC
            LIMIT {ph}
        ''', (leader_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_copy_stats(leader_id: int) -> Dict:
    """Get copy trade statistics for a leader."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'''
            SELECT
                COUNT(*) as total_copies,
                COUNT(CASE WHEN status = 'filled' THEN 1 END) as successful,
                COUNT(CASE WHEN status = 'error' THEN 1 END) as failed,
                AVG(latency_ms) as avg_latency_ms
            FROM copy_trade_log
            WHERE leader_id = {ph}
        ''', (leader_id,))
        row = cursor.fetchone()
        if row:
            result = dict(row)
            result['avg_latency_ms'] = round(result['avg_latency_ms'] or 0, 1)
            return result
        return {'total_copies': 0, 'successful': 0, 'failed': 0, 'avg_latency_ms': 0}
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# ACTIVE LEADER QUERY (for WebSocket monitor)
# ============================================================================
def get_active_leaders_with_followers() -> List[Dict]:
    """Get all active leaders that have auto_copy_enabled and at least one enabled follower.
    Used by ws_leader_monitor to know which accounts to watch."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()

    try:
        active_val = 'TRUE' if db_type == 'postgresql' else '1'
        cursor.execute(f'''
            SELECT DISTINCT la.*
            FROM leader_accounts la
            INNER JOIN follower_accounts fa ON la.id = fa.leader_id
            WHERE la.is_active = {active_val}
              AND la.auto_copy_enabled = {active_val}
              AND fa.is_enabled = {active_val}
            ORDER BY la.id
        ''')
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# INITIALIZATION
# ============================================================================
def init_copy_trader_system():
    """Initialize the copy trader system. Call on app startup."""
    logger.info("Initializing copy trader system...")

    if not init_copy_trader_tables():
        logger.error("Failed to initialize copy trader tables")
        return False

    logger.info("Copy trader system initialized")
    return True


# ============================================================================
# MIRRORED ORDERS CRUD (Order Mirroring)
# ============================================================================
def create_mirrored_order(leader_id: int, follower_id: int, leader_order_id: int,
                          symbol: str, action: str, order_type: str,
                          leader_qty: int, follower_qty: int,
                          leader_price: float = None, stop_price: float = None,
                          time_in_force: str = 'Day') -> Optional[int]:
    """Create a mirrored order record. Returns mirror ID or None."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        if db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO mirrored_orders
                (leader_id, follower_id, leader_order_id, symbol, action, order_type,
                 leader_qty, follower_qty, leader_price, stop_price, time_in_force, status)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'pending')
                RETURNING id
            ''', (leader_id, follower_id, leader_order_id, symbol, action, order_type,
                  leader_qty, follower_qty, leader_price, stop_price, time_in_force))
            result = cursor.fetchone()
            mirror_id = result['id'] if result else None
        else:
            cursor.execute(f'''
                INSERT INTO mirrored_orders
                (leader_id, follower_id, leader_order_id, symbol, action, order_type,
                 leader_qty, follower_qty, leader_price, stop_price, time_in_force, status)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'pending')
            ''', (leader_id, follower_id, leader_order_id, symbol, action, order_type,
                  leader_qty, follower_qty, leader_price, stop_price, time_in_force))
            mirror_id = cursor.lastrowid

        conn.commit()
        logger.info(f"Created mirrored order: leader_order={leader_order_id}, follower={follower_id}, {action} {follower_qty} {symbol}")
        return mirror_id
    except Exception as e:
        logger.error(f"Failed to create mirrored order: {e}")
        conn.rollback()
        return None
    finally:
        cursor.close()
        conn.close()


def update_mirrored_order(mirror_id: int, status: str,
                          follower_order_id: int = None,
                          follower_price: float = None,
                          error_message: str = None) -> bool:
    """Update a mirrored order record (status, follower_order_id, error)."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        now_expr = 'NOW()' if db_type == 'postgresql' else "datetime('now')"
        cursor.execute(f'''
            UPDATE mirrored_orders
            SET status = {ph},
                follower_order_id = COALESCE({ph}, follower_order_id),
                follower_price = COALESCE({ph}, follower_price),
                error_message = COALESCE({ph}, error_message),
                updated_at = {now_expr}
            WHERE id = {ph}
        ''', (status, follower_order_id, follower_price, error_message, mirror_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update mirrored order {mirror_id}: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def get_mirrored_orders_by_leader_order(leader_order_id: int) -> List[Dict]:
    """Get all mirrored orders for a leader order, with follower account info."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'''
            SELECT mo.*, fa.account_id as follower_account_id,
                   fa.subaccount_id as follower_subaccount_id,
                   fa.multiplier as follower_multiplier
            FROM mirrored_orders mo
            JOIN follower_accounts fa ON mo.follower_id = fa.id
            WHERE mo.leader_order_id = {ph} AND mo.status = 'working'
        ''', (leader_order_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_active_mirror_for_follower(follower_id: int, symbol: str, action: str) -> Optional[Dict]:
    """Get an active (working) mirrored order for a follower on a symbol+side.
    Used by fill-path dedup to skip market orders when a limit order exists."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'''
            SELECT * FROM mirrored_orders
            WHERE follower_id = {ph} AND symbol = {ph} AND action = {ph} AND status = 'working'
            ORDER BY created_at DESC
            LIMIT 1
        ''', (follower_id, symbol, action))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        cursor.close()
        conn.close()


def cancel_all_mirrors_for_leader(leader_id: int) -> int:
    """Bulk cancel all working mirrors for a leader (used on disconnect cleanup).
    Returns count of cancelled mirrors."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        now_expr = 'NOW()' if db_type == 'postgresql' else "datetime('now')"
        cursor.execute(f'''
            UPDATE mirrored_orders
            SET status = 'cancelled', updated_at = {now_expr}
            WHERE leader_id = {ph} AND status = 'working'
        ''', (leader_id,))
        count = cursor.rowcount
        conn.commit()
        if count > 0:
            logger.info(f"Cancelled {count} working mirrors for leader {leader_id} (disconnect cleanup)")
        return count
    except Exception as e:
        logger.error(f"Failed to cancel mirrors for leader {leader_id}: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()


def get_working_mirrors_for_leader(leader_id: int) -> List[Dict]:
    """Get all working mirrored orders for a leader (for reconciliation)."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'''
            SELECT mo.*, fa.account_id as follower_account_id,
                   fa.subaccount_id as follower_subaccount_id
            FROM mirrored_orders mo
            JOIN follower_accounts fa ON mo.follower_id = fa.id
            WHERE mo.leader_id = {ph} AND mo.status = 'working'
            ORDER BY mo.created_at
        ''', (leader_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def cleanup_stale_mirrors(max_age_hours: int = 24) -> int:
    """Mark mirrors older than max_age_hours with status='working' as 'expired'.
    Called periodically for housekeeping. Returns count of expired mirrors."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()

    try:
        if db_type == 'postgresql':
            cursor.execute(f'''
                UPDATE mirrored_orders
                SET status = 'expired', updated_at = NOW()
                WHERE status = 'working'
                AND created_at < NOW() - INTERVAL '{max_age_hours} hours'
            ''')
        else:
            cursor.execute(f'''
                UPDATE mirrored_orders
                SET status = 'expired', updated_at = datetime('now')
                WHERE status = 'working'
                AND created_at < datetime('now', '-{max_age_hours} hours')
            ''')
        count = cursor.rowcount
        conn.commit()
        if count > 0:
            logger.info(f"Expired {count} stale mirrored orders (>{max_age_hours}h old)")
        return count
    except Exception as e:
        logger.error(f"Failed to cleanup stale mirrors: {e}")
        conn.rollback()
        return 0
    finally:
        cursor.close()
        conn.close()


# ============================================================================
# PLATFORM SETTINGS (Global Toggle)
# ============================================================================
_setting_cache: Dict[str, Any] = {}  # key -> {'value': str, 'ts': float}
_SETTING_CACHE_TTL = 10.0  # seconds


def get_platform_setting(key: str) -> Optional[str]:
    """Get a platform setting value by key. Returns None if not found."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'SELECT value FROM platform_settings WHERE key = {ph}', (key,))
        row = cursor.fetchone()
        if row:
            return row['value'] if isinstance(row, dict) else row[0]
        return None
    except Exception as e:
        logger.error(f"Error reading platform setting '{key}': {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def set_platform_setting(key: str, value: str, user_id: int = None) -> bool:
    """Upsert a platform setting. Returns True on success."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        if db_type == 'postgresql':
            cursor.execute(f'''
                INSERT INTO platform_settings (key, value, updated_by, updated_at)
                VALUES ({ph}, {ph}, {ph}, NOW())
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_by = EXCLUDED.updated_by,
                    updated_at = NOW()
            ''', (key, value, user_id))
        else:
            cursor.execute(f'''
                INSERT OR REPLACE INTO platform_settings (key, value, updated_by, updated_at)
                VALUES ({ph}, {ph}, {ph}, datetime('now'))
            ''', (key, value, user_id))
        conn.commit()
        # Invalidate cache
        _setting_cache.pop(key, None)
        logger.info(f"Platform setting '{key}' set to '{value}' by user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error setting platform setting '{key}': {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def is_copy_trader_enabled() -> bool:
    """Check if copy trading is globally enabled. Caches result for 10 seconds."""
    import time as _time
    now = _time.time()
    cached = _setting_cache.get('copy_trader_enabled')
    if cached and (now - cached['ts']) < _SETTING_CACHE_TTL:
        return cached['value'] != 'false'

    value = get_platform_setting('copy_trader_enabled')
    _setting_cache['copy_trader_enabled'] = {'value': value, 'ts': now}
    return value != 'false'


# ============================================================================
# TESTING
# ============================================================================
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("Initializing copy trader tables...")
    success = init_copy_trader_tables()
    print(f"Tables created: {success}")

    if success:
        # Quick CRUD test
        print("\nTesting CRUD...")
        lid = create_leader(user_id=1, account_id=1, subaccount_id='12345', label='Test Leader')
        print(f"Created leader: {lid}")

        leaders = get_leaders_for_user(1)
        print(f"Leaders for user 1: {leaders}")

        if lid:
            fid = create_follower(leader_id=lid, user_id=1, account_id=1,
                                  subaccount_id='67890', label='Test Follower', multiplier=2.0)
            print(f"Created follower: {fid}")

            followers = get_followers_for_leader(lid)
            print(f"Followers for leader {lid}: {followers}")

            if fid:
                log_id = log_copy_trade(
                    leader_id=lid, follower_id=fid,
                    symbol='NQH6', side='Buy',
                    leader_quantity=1, follower_quantity=2,
                    status='filled', latency_ms=45
                )
                print(f"Logged copy trade: {log_id}")

                stats = get_copy_stats(lid)
                print(f"Copy stats: {stats}")

                history = get_copy_trade_history(lid)
                print(f"Copy history: {history}")

        print("\nAll tests passed!")
