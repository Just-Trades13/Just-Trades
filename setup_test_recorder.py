#!/usr/bin/env python3
"""
Setup script for testing recorder backend with demo account
This will create test data in the database
"""

import sqlite3
import sys
import os
from datetime import datetime

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


def create_test_user():
    """Create a test user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if test user exists
    cursor.execute("SELECT id FROM users WHERE username = ?", ("test_user",))
    user = cursor.fetchone()
    
    if user:
        user_id = user[0]
        print(f"✅ Test user already exists (ID: {user_id})")
    else:
        # Create test user (password hash is just a placeholder for testing)
        cursor.execute("""
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
        """, ("test_user", "test@example.com", "test_hash"))
        user_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Created test user (ID: {user_id})")
    
    conn.close()
    return user_id


def create_demo_account(user_id, account_name, username, password, client_id, client_secret):
    """Create a demo account record"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if account exists
    cursor.execute("SELECT id FROM accounts WHERE name = ? AND user_id = ?", (account_name, user_id))
    account = cursor.fetchone()
    
    if account:
        account_id = account[0]
        # Update credentials
        cursor.execute("""
            UPDATE accounts
            SET username = ?, password = ?, client_id = ?, client_secret = ?
            WHERE id = ?
        """, (username, password, client_id, client_secret, account_id))
        conn.commit()
        print(f"✅ Updated demo account '{account_name}' (ID: {account_id})")
    else:
        # Create new account
        cursor.execute("""
            INSERT INTO accounts (user_id, name, username, password, client_id, client_secret, enabled)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (user_id, account_name, username, password, client_id, client_secret))
        account_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Created demo account '{account_name}' (ID: {account_id})")
    
    conn.close()
    return account_id


def create_test_strategy(user_id, demo_account_id, strategy_name, symbol="NQ"):
    """Create a test strategy/recorder"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if strategy exists
    cursor.execute("SELECT id FROM strategies WHERE name = ? AND user_id = ?", (strategy_name, user_id))
    strategy = cursor.fetchone()
    
    if strategy:
        strategy_id = strategy[0]
        # Update demo account
        cursor.execute("""
            UPDATE strategies
            SET demo_account_id = ?, symbol = ?, recording_enabled = 1, active = 1
            WHERE id = ?
        """, (demo_account_id, symbol, strategy_id))
        conn.commit()
        print(f"✅ Updated test strategy '{strategy_name}' (ID: {strategy_id})")
    else:
        # Create new strategy
        cursor.execute("""
            INSERT INTO strategies (
                user_id, demo_account_id, name, symbol,
                recording_enabled, stop_loss, take_profit, tpsl_units, active
            )
            VALUES (?, ?, ?, ?, 1, 20, 40, 'Ticks', 1)
        """, (user_id, demo_account_id, strategy_name, symbol))
        strategy_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Created test strategy '{strategy_name}' (ID: {strategy_id})")
    
    conn.close()
    return strategy_id


def main():
    """Main setup function"""
    print("=" * 60)
    print("Recorder Backend Test Setup")
    print("=" * 60)
    print()
    
    # Initialize database
    init_database()
    print()
    
    # Create test user
    user_id = create_test_user()
    print()
    
    # Get Tradovate credentials
    print("📝 Enter Tradovate Demo Account Details:")
    print("   (Get these from your Tradovate account)")
    print()
    
    account_name = input("Account Name (e.g., 'My Demo Account'): ").strip()
    if not account_name:
        account_name = "Test Demo Account"
    
    username = input("Tradovate Username: ").strip()
    if not username:
        print("❌ Username is required!")
        sys.exit(1)
    
    password = input("Tradovate Password: ").strip()
    if not password:
        print("❌ Password is required!")
        sys.exit(1)
    
    print()
    print("📝 Enter OAuth Credentials (from Tradovate OAuth Registration):")
    print("   (These are the Client ID and Client Secret you got after clicking 'Generate')")
    print()
    
    client_id = input("Client ID (cid): ").strip()
    if not client_id:
        print("❌ Client ID is required!")
        sys.exit(1)
    
    client_secret = input("Client Secret (sec): ").strip()
    if not client_secret:
        print("❌ Client Secret is required!")
        sys.exit(1)
    
    print()
    print("📝 Strategy Configuration:")
    strategy_name = input("Strategy Name (e.g., 'Test Recorder'): ").strip()
    if not strategy_name:
        strategy_name = "Test Recorder"
    
    symbol = input("Symbol to track (e.g., NQ, ES) [default: NQ]: ").strip().upper()
    if not symbol:
        symbol = "NQ"
    
    print()
    print("Creating test data...")
    print()
    
    # Create demo account
    account_id = create_demo_account(user_id, account_name, username, password, client_id, client_secret)
    print()
    
    # Create test strategy
    strategy_id = create_test_strategy(user_id, account_id, strategy_name, symbol)
    print()
    
    print("=" * 60)
    print("✅ Setup Complete!")
    print("=" * 60)
    print()
    print("Test Data Created:")
    print(f"  User ID: {user_id}")
    print(f"  Account ID: {account_id}")
    print(f"  Strategy ID: {strategy_id}")
    print()
    print("Next Steps:")
    print("1. Start the recorder backend:")
    print("   python3 recorder_backend.py --port 8083")
    print()
    print("2. Test starting a recording:")
    print(f"   curl -X POST http://localhost:8083/api/recorders/start/{strategy_id} \\")
    print("        -H 'X-API-Key: your-api-key' \\")
    print("        -H 'Content-Type: application/json' \\")
    print(f"        -d '{{\"user_id\": {user_id}, \"poll_interval\": 30}}'")
    print()
    print("3. Check status:")
    print("   curl http://localhost:8083/health")
    print()


if __name__ == '__main__':
    main()

