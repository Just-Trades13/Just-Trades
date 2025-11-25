#!/usr/bin/env python3
"""
Test OAuth state storage and retrieval
"""

import sqlite3
from datetime import datetime, timedelta

def test_oauth_state():
    """Test OAuth state in database"""
    try:
        conn = sqlite3.connect('just_trades.db')
        cursor = conn.cursor()
        
        # Check if oauth_states table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='oauth_states'
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ oauth_states table doesn't exist")
            return
        
        # Get all states
        cursor.execute("SELECT state, account_id, created_at FROM oauth_states ORDER BY created_at DESC")
        states = cursor.fetchall()
        
        if not states:
            print("✅ oauth_states table exists but is empty")
            print("   This is normal if no OAuth flow has been started recently")
            return
        
        print(f"✅ Found {len(states)} OAuth states in database:")
        print()
        
        for state, account_id, created_at in states:
            created = datetime.fromisoformat(created_at)
            age = datetime.now() - created
            age_seconds = age.total_seconds()
            age_minutes = age_seconds / 60
            
            print(f"State: {state[:50]}...")
            print(f"Account ID: {account_id}")
            print(f"Created: {created_at}")
            print(f"Age: {age_minutes:.1f} minutes ({age_seconds:.0f} seconds)")
            
            if age_seconds > 1800:  # 30 minutes
                print(f"⚠️  State is expired (older than 30 minutes)")
            else:
                print(f"✅ State is valid (within 30 minute limit)")
            print()
        
        # Clean up old states (older than 1 hour)
        cursor.execute("""
            DELETE FROM oauth_states 
            WHERE datetime(created_at) < datetime('now', '-1 hour')
        """)
        deleted = cursor.rowcount
        if deleted > 0:
            conn.commit()
            print(f"🧹 Cleaned up {deleted} old states (older than 1 hour)")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_oauth_state()

