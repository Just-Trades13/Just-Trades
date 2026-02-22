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
                    side VARCHAR(10) NOT NULL,
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
    """Get all leader accounts for a user."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        active_val = 'TRUE' if db_type == 'postgresql' else '1'
        cursor.execute(f'''
            SELECT * FROM leader_accounts
            WHERE user_id = {ph} AND is_active = {active_val}
            ORDER BY created_at DESC
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
    """Get all enabled followers for a leader."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        enabled_val = 'TRUE' if db_type == 'postgresql' else '1'
        cursor.execute(f'''
            SELECT * FROM follower_accounts
            WHERE leader_id = {ph} AND is_enabled = {enabled_val}
            ORDER BY created_at
        ''', (leader_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_all_followers_for_leader(leader_id: int) -> List[Dict]:
    """Get all followers for a leader (including disabled)."""
    conn, db_type = get_copy_trader_db_connection()
    cursor = conn.cursor()
    ph = _ph(db_type)

    try:
        cursor.execute(f'''
            SELECT * FROM follower_accounts
            WHERE leader_id = {ph}
            ORDER BY created_at
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
