#!/usr/bin/env python3
"""
Setup test environment for signal-based tracking test

This script:
1. Creates a test recorder if it doesn't exist
2. Gets the webhook token
3. Prints configuration for the test script
"""

import sqlite3
import secrets
import sys

DB_PATH = "just_trades.db"
TEST_RECORDER_NAME = "TEST_SIGNAL_TRACKING"

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_test_recorder():
    """Create test recorder if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recorders'")
    if not cursor.fetchone():
        print("❌ 'recorders' table doesn't exist")
        print("   Please run the server once to initialize the database")
        conn.close()
        return None, None
    
    # Check if recorder exists
    cursor.execute('SELECT id, webhook_token FROM recorders WHERE name = ?', (TEST_RECORDER_NAME,))
    existing = cursor.fetchone()
    
    if existing:
        print(f"✅ Test recorder '{TEST_RECORDER_NAME}' already exists")
        print(f"   ID: {existing['id']}")
        print(f"   Webhook Token: {existing['webhook_token']}")
        conn.close()
        return existing['id'], existing['webhook_token']
    
    # Create test recorder
    webhook_token = secrets.token_urlsafe(32)
    
    # Get a trader ID (or create one)
    cursor.execute('SELECT id FROM traders LIMIT 1')
    trader = cursor.fetchone()
    
    if not trader:
        print("❌ No traders found. Creating a test trader...")
        # Create a test account first
        cursor.execute('SELECT id FROM accounts LIMIT 1')
        account = cursor.fetchone()
        
        if not account:
            print("❌ No accounts found. Please create an account first.")
            conn.close()
            return None, None
        
        # Create test trader
        cursor.execute('''
            INSERT INTO traders (account_id, name, is_demo, enabled)
            VALUES (?, ?, ?, ?)
        ''', (account['id'], 'TEST_TRADER', 1, 1))
        trader_id = cursor.lastrowid
    else:
        trader_id = trader['id']
    
    # Create recorder
    cursor.execute('''
        INSERT INTO recorders 
        (trader_id, name, webhook_token, recording_enabled, initial_position_size, enabled)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (trader_id, TEST_RECORDER_NAME, webhook_token, 1, 1, 1))
    
    recorder_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    print(f"✅ Created test recorder '{TEST_RECORDER_NAME}'")
    print(f"   ID: {recorder_id}")
    print(f"   Webhook Token: {webhook_token}")
    
    return recorder_id, webhook_token

def main():
    """Setup test environment"""
    print("\n" + "="*60)
    print("🧪 SETUP TEST ENVIRONMENT")
    print("="*60)
    
    recorder_id, webhook_token = create_test_recorder()
    
    if not recorder_id or not webhook_token:
        print("\n❌ Failed to setup test environment")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("📋 TEST CONFIGURATION")
    print("="*60)
    print(f"\nRecorder Name: {TEST_RECORDER_NAME}")
    print(f"Recorder ID: {recorder_id}")
    print(f"Webhook Token: {webhook_token}")
    print(f"\nWebhook URL: http://localhost:8083/webhook/{webhook_token}")
    print(f"\nTo run the test:")
    print(f"  1. Start server: SIGNAL_BASED_TEST=true python3 recorder_service.py")
    print(f"  2. Update test_long_term_accuracy.py with:")
    print(f"     WEBHOOK_URL = 'http://localhost:8083/webhook/{webhook_token}'")
    print(f"     RECORDER_NAME = '{TEST_RECORDER_NAME}'")
    print(f"  3. Run: python3 test_long_term_accuracy.py")
    
    # Update test script automatically
    try:
        with open('test_long_term_accuracy.py', 'r') as f:
            content = f.read()
        
        # Replace placeholders
        content = content.replace(
            "WEBHOOK_URL = \"http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN\"",
            f"WEBHOOK_URL = \"http://localhost:8083/webhook/{webhook_token}\""
        )
        content = content.replace(
            "RECORDER_NAME = \"TEST_RECORDER\"",
            f"RECORDER_NAME = \"{TEST_RECORDER_NAME}\""
        )
        
        with open('test_long_term_accuracy.py', 'w') as f:
            f.write(content)
        
        print(f"\n✅ Updated test_long_term_accuracy.py with configuration")
    except Exception as e:
        print(f"\n⚠️  Could not auto-update test script: {e}")
        print("   Please update manually")

if __name__ == "__main__":
    main()
