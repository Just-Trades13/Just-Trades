#!/usr/bin/env python3
"""
Quick setup for testing recorder backend with provided credentials
"""

import sqlite3
import os
import sys

# Your credentials
CLIENT_ID = "8552"
CLIENT_SECRET = "d7d4fc4c-43f1-4f5d-a132-dd3e95213239"

# Database path
DB_PATH = os.getenv('DB_PATH', 'just_trades.db')

def init_database():
    """Initialize database tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create accounts table
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create strategies table
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
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id),
            FOREIGN KEY (demo_account_id) REFERENCES accounts(id)
        )
    ''')
    
    # Create recorded_positions table
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
    
    # Create strategy_logs table
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
    print("✅ Database tables initialized")


def setup_test_data():
    """Set up test data with provided credentials"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create or get test user
    cursor.execute("SELECT id FROM users WHERE username = ?", ("test_user",))
    user = cursor.fetchone()
    if user:
        user_id = user[0]
        print(f"✅ Using existing test user (ID: {user_id})")
    else:
        cursor.execute("""
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
        """, ("test_user", "test@example.com", "test_hash"))
        user_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Created test user (ID: {user_id})")
    
    # Get Tradovate credentials from user
    print()
    print("📝 Please enter your Tradovate demo account credentials:")
    print()
    username = input("Tradovate Username: ").strip()
    if not username:
        print("❌ Username is required!")
        sys.exit(1)
    
    password = input("Tradovate Password: ").strip()
    if not password:
        print("❌ Password is required!")
        sys.exit(1)
    
    print()
    symbol = input("Symbol to track (e.g., NQ, ES) [default: NQ]: ").strip().upper()
    if not symbol:
        symbol = "NQ"
    
    # Create or update demo account
    account_name = "Test Demo Account"
    cursor.execute("SELECT id FROM accounts WHERE name = ? AND user_id = ?", (account_name, user_id))
    account = cursor.fetchone()
    
    if account:
        account_id = account[0]
        cursor.execute("""
            UPDATE accounts
            SET username = ?, password = ?, client_id = ?, client_secret = ?, enabled = 1
            WHERE id = ?
        """, (username, password, CLIENT_ID, CLIENT_SECRET, account_id))
        conn.commit()
        print(f"✅ Updated demo account '{account_name}' (ID: {account_id})")
    else:
        cursor.execute("""
            INSERT INTO accounts (user_id, name, username, password, client_id, client_secret, enabled)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (user_id, account_name, username, password, CLIENT_ID, CLIENT_SECRET))
        account_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Created demo account '{account_name}' (ID: {account_id})")
    
    # Create or update test strategy
    strategy_name = "Test Recorder"
    cursor.execute("SELECT id FROM strategies WHERE name = ? AND user_id = ?", (strategy_name, user_id))
    strategy = cursor.fetchone()
    
    if strategy:
        strategy_id = strategy[0]
        cursor.execute("""
            UPDATE strategies
            SET demo_account_id = ?, symbol = ?, recording_enabled = 1, active = 1
            WHERE id = ?
        """, (account_id, symbol, strategy_id))
        conn.commit()
        print(f"✅ Updated test strategy '{strategy_name}' (ID: {strategy_id})")
    else:
        cursor.execute("""
            INSERT INTO strategies (
                user_id, demo_account_id, name, symbol,
                recording_enabled, stop_loss, take_profit, tpsl_units, active
            )
            VALUES (?, ?, ?, ?, 1, 20, 40, 'Ticks', 1)
        """, (user_id, account_id, strategy_name, symbol))
        strategy_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Created test strategy '{strategy_name}' (ID: {strategy_id})")
    
    conn.close()
    
    print()
    print("=" * 60)
    print("✅ Setup Complete!")
    print("=" * 60)
    print()
    print("Test Data Created:")
    print(f"  User ID: {user_id}")
    print(f"  Account ID: {account_id}")
    print(f"  Strategy ID: {strategy_id}")
    print(f"  Symbol: {symbol}")
    print()
    print("OAuth Credentials:")
    print(f"  Client ID: {CLIENT_ID}")
    print(f"  Client Secret: {CLIENT_SECRET[:10]}...")
    print()
    print("Next Steps:")
    print("1. Set API key in .env file:")
    print("   RECORDER_API_KEY=test-key-12345")
    print()
    print("2. Start the recorder backend:")
    print("   python3 recorder_backend.py --port 8083")
    print()
    print("3. Test starting a recording:")
    print(f"   curl -X POST http://localhost:8083/api/recorders/start/{strategy_id} \\")
    print("        -H 'X-API-Key: test-key-12345' \\")
    print("        -H 'Content-Type: application/json' \\")
    print(f"        -d '{{\"user_id\": {user_id}, \"poll_interval\": 30}}'")
    print()


if __name__ == '__main__':
    print("=" * 60)
    print("Quick Setup for Recorder Backend Testing")
    print("=" * 60)
    print()
    init_database()
    print()
    setup_test_data()

