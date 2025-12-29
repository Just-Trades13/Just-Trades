#!/usr/bin/env python3
"""
Setup Live Test Webhook with 10 Tick TP

This script:
1. Initializes database if needed
2. Creates a test recorder with 10 tick TP
3. Provides webhook URL for TradingView
"""

import sqlite3
import secrets
import sys
import os

DB_PATH = 'just_trades.db'
RECORDER_NAME = 'LIVE_TEST_RECORDER'
TP_TICKS = 10
PORT = 8083  # Default port for recorder_service

def init_database():
    """Initialize database tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if recorders table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recorders'")
    if cursor.fetchone():
        conn.close()
        return True
    
    print("⚠️  Database not initialized. Creating basic structure...")
    
    # Create basic tables (minimal structure)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT,
            tradovate_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS traders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            name TEXT,
            is_demo INTEGER DEFAULT 1,
            enabled INTEGER DEFAULT 1,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recorders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trader_id INTEGER,
            name TEXT UNIQUE,
            webhook_token TEXT UNIQUE,
            recording_enabled INTEGER DEFAULT 1,
            enabled INTEGER DEFAULT 1,
            initial_position_size INTEGER DEFAULT 1,
            tp_ticks INTEGER DEFAULT 10,
            tp_enabled INTEGER DEFAULT 1,
            sl_ticks INTEGER DEFAULT 0,
            sl_enabled INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (trader_id) REFERENCES traders(id)
        )
    ''')
    
    # Create a default account if none exists
    cursor.execute('SELECT id FROM accounts LIMIT 1')
    if not cursor.fetchone():
        cursor.execute('INSERT INTO accounts (username) VALUES (?)', ('test_account',))
        account_id = cursor.lastrowid
        print(f"✅ Created default account (ID: {account_id})")
    else:
        cursor.execute('SELECT id FROM accounts LIMIT 1')
        account_id = cursor.fetchone()[0]
    
    # Create a default trader if none exists
    cursor.execute('SELECT id FROM traders LIMIT 1')
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO traders (account_id, name, is_demo, enabled)
            VALUES (?, ?, ?, ?)
        ''', (account_id, 'LIVE_TEST_TRADER', 1, 1))
        trader_id = cursor.lastrowid
        print(f"✅ Created default trader (ID: {trader_id})")
    else:
        cursor.execute('SELECT id FROM traders LIMIT 1')
        trader_id = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    return True

def create_or_update_recorder():
    """Create or update the test recorder with 10 tick TP"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if recorder exists
    cursor.execute('SELECT id, webhook_token, tp_ticks FROM recorders WHERE name = ?', (RECORDER_NAME,))
    existing = cursor.fetchone()
    
    if existing:
        recorder_id = existing['id']
        webhook_token = existing['webhook_token']
        
        # Update TP to 10 ticks if different
        if existing['tp_ticks'] != TP_TICKS:
            cursor.execute('UPDATE recorders SET tp_ticks = ?, tp_enabled = 1 WHERE id = ?', 
                          (TP_TICKS, recorder_id))
            conn.commit()
            print(f"✅ Updated existing recorder '{RECORDER_NAME}'")
            print(f"   TP Ticks: {TP_TICKS}")
        else:
            print(f"✅ Using existing recorder '{RECORDER_NAME}'")
            print(f"   TP Ticks: {TP_TICKS} (already set)")
    else:
        # Get trader ID
        cursor.execute('SELECT id FROM traders LIMIT 1')
        trader = cursor.fetchone()
        
        if not trader:
            print("❌ No traders found. Please run the server once to initialize properly.")
            conn.close()
            return None, None
        
        trader_id = trader['id']
        
        # Create new recorder
        webhook_token = secrets.token_urlsafe(32)
        cursor.execute('''
            INSERT INTO recorders 
            (trader_id, name, webhook_token, recording_enabled, enabled, 
             initial_position_size, tp_ticks, tp_enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trader_id, RECORDER_NAME, webhook_token, 1, 1, 1, TP_TICKS, 1))
        
        recorder_id = cursor.lastrowid
        conn.commit()
        print(f"✅ Created new recorder '{RECORDER_NAME}'")
        print(f"   ID: {recorder_id}")
        print(f"   TP Ticks: {TP_TICKS}")
    
    conn.close()
    return recorder_id, webhook_token

def get_server_url():
    """Determine the server URL"""
    # Check if running on Railway or localhost
    railway_url = os.getenv('RAILWAY_PUBLIC_DOMAIN')
    if railway_url:
        return f"https://{railway_url}"
    
    # Check for custom domain
    custom_domain = os.getenv('CUSTOM_DOMAIN')
    if custom_domain:
        return f"https://{custom_domain}"
    
    # Default to localhost
    return f"http://localhost:{PORT}"

def main():
    """Main setup function"""
    print("\n" + "="*60)
    print("🔗 LIVE TEST WEBHOOK SETUP")
    print("="*60)
    print(f"\nRecorder: {RECORDER_NAME}")
    print(f"TP Ticks: {TP_TICKS}")
    print()
    
    # Initialize database
    if not init_database():
        print("❌ Failed to initialize database")
        sys.exit(1)
    
    # Create or update recorder
    recorder_id, webhook_token = create_or_update_recorder()
    
    if not recorder_id or not webhook_token:
        print("❌ Failed to create recorder")
        sys.exit(1)
    
    # Get server URL
    base_url = get_server_url()
    webhook_url = f"{base_url}/webhook/{webhook_token}"
    
    print("\n" + "="*60)
    print("📋 WEBHOOK CONFIGURATION")
    print("="*60)
    print(f"\n✅ Recorder Created/Updated Successfully!")
    print(f"\n📝 Recorder Details:")
    print(f"   Name: {RECORDER_NAME}")
    print(f"   ID: {recorder_id}")
    print(f"   TP Ticks: {TP_TICKS}")
    print(f"   TP Enabled: Yes")
    
    print(f"\n🔗 Webhook URL for TradingView:")
    print(f"   {webhook_url}")
    
    print(f"\n📨 TradingView Alert Message Format:")
    print(f"   Use this JSON in your TradingView alert:")
    print()
    print(f'   {{')
    print(f'     "recorder": "{RECORDER_NAME}",')
    print(f'     "action": "{{strategy.order.action}}",')
    print(f'     "ticker": "{{ticker}}",')
    print(f'     "price": "{{close}}"')
    print(f'   }}')
    print()
    
    print(f"   Or use the simple format:")
    print(f'   {{')
    print(f'     "recorder": "{RECORDER_NAME}",')
    print(f'     "action": "buy",')
    print(f'     "ticker": "MNQ1!",')
    print(f'     "price": "{{close}}"')
    print(f'   }}')
    print()
    
    print("="*60)
    print("⚠️  IMPORTANT: Start Server in Test Mode")
    print("="*60)
    print(f"\nBefore sending signals, start the server with:")
    print(f"   SIGNAL_BASED_TEST=true python3 recorder_service.py")
    print()
    print(f"This enables signal-based tracking (no broker sync)")
    print(f"and allows us to test accuracy over time.")
    print()
    
    # Save to file for easy copy
    with open('webhook_url.txt', 'w') as f:
        f.write(webhook_url)
    
    print(f"✅ Webhook URL saved to: webhook_url.txt")
    print()

if __name__ == "__main__":
    main()
