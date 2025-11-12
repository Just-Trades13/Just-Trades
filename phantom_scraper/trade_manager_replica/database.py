"""
Database setup and utilities
"""
import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get('DATABASE_PATH', 'trade_manager.db')

def init_db():
    """Initialize database with all tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            discord_user_id TEXT,
            discord_dms_enabled BOOLEAN DEFAULT 1,
            push_notifications_enabled BOOLEAN DEFAULT 1,
            admin BOOLEAN DEFAULT 0,
            access TEXT DEFAULT 'full',
            is_email_verified BOOLEAN DEFAULT 0,
            session_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add push_notifications_enabled column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN push_notifications_enabled BOOLEAN DEFAULT 1")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Accounts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            platform TEXT NOT NULL DEFAULT 'Tradovate',
            status TEXT,
            disabled BOOLEAN DEFAULT 0,
            username TEXT,
            password TEXT,
            client_id TEXT,
            client_secret TEXT,
            tradovate_token TEXT,
            tradovate_refresh_token TEXT,
            token_expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Subaccounts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subaccounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)
    
    # Strategies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_id INTEGER,
            name TEXT NOT NULL,
            position_size INTEGER DEFAULT 1,
            position_add INTEGER DEFAULT 1,
            take_profit REAL,
            stop_loss REAL,
            tpsl_units TEXT DEFAULT 'Ticks',
            symbol TEXT,
            recording_enabled BOOLEAN DEFAULT 1,
            demo_account_id INTEGER,
            active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (demo_account_id) REFERENCES accounts(id)
        )
    """)
    
    # Recorded positions table
    cursor.execute("""
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
            tradovate_order_id TEXT,
            tradovate_position_id TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)
    
    # Strategy logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            log_type TEXT NOT NULL,
            message TEXT NOT NULL,
            data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    """)
    
    # Trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            strategy_id INTEGER,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL,
            order_type TEXT DEFAULT 'market',
            status TEXT DEFAULT 'pending',
            tradovate_order_id TEXT,
            entry_price REAL,
            exit_price REAL,
            pnl REAL DEFAULT 0.0,
            usage_type TEXT DEFAULT 'manual',
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            filled_at TIMESTAMP,
            closed_at TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (strategy_id) REFERENCES strategies(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Webhook logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS webhook_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER,
            payload TEXT NOT NULL,
            response TEXT,
            status_code INTEGER,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    """)
    
    # Subaccount tags (many-to-many relationship)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subaccount_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subaccount_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subaccount_id) REFERENCES subaccounts(id),
            UNIQUE(subaccount_id, tag)
        )
    """)
    
    # Add missing columns to strategies table if they don't exist
    missing_columns = [
        ('strat_type', 'TEXT'),
        ('days_to_expiry', 'INTEGER'),
        ('strike_offset', 'REAL'),
        ('trim', 'TEXT DEFAULT "All"'),
        ('directional_strategy', 'TEXT'),
        ('manual_trading_enabled', 'BOOLEAN DEFAULT 0'),
        ('enabled', 'BOOLEAN DEFAULT 1'),
        ('private', 'BOOLEAN DEFAULT 0'),
        ('algo_driven', 'BOOLEAN DEFAULT 0'),
        ('delay_add', 'INTEGER DEFAULT 1'),
        ('maxcons', 'INTEGER DEFAULT 0'),
        ('leverage', 'INTEGER DEFAULT 1'),
        ('alternate_name', 'TEXT'),
        ('description', 'TEXT'),
        ('discord_channel', 'TEXT'),
        ('sub_ticker', 'TEXT DEFAULT "ALL"'),
        ('sub_timeframe', 'TEXT DEFAULT "ALL"'),
        ('premium_filter', 'INTEGER DEFAULT 0'),
        ('webhook_key', 'TEXT')
    ]
    
    for col_name, col_def in missing_columns:
        try:
            cursor.execute(f"ALTER TABLE strategies ADD COLUMN {col_name} {col_def}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Update take_profit to TEXT to store JSON array
    try:
        cursor.execute("ALTER TABLE strategies ADD COLUMN take_profit_json TEXT")
        # Migrate existing take_profit to JSON format
        cursor.execute("UPDATE strategies SET take_profit_json = '[' || take_profit || ']' WHERE take_profit IS NOT NULL AND take_profit_json IS NULL")
    except sqlite3.OperationalError:
        pass
    
    # Add indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_strategies_user_id ON strategies(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_account_id ON trades(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_strategy_id ON trades(strategy_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_recorded_positions_strategy_id ON recorded_positions(strategy_id)")
    
    conn.commit()
    conn.close()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def db_connection():
    """Context manager for database connections"""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()

