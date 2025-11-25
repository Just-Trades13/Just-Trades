#!/usr/bin/env python3
"""
Update OAuth credentials for account
"""

import sqlite3
import sys

# New OAuth app credentials
NEW_CLIENT_ID = "8556"
NEW_CLIENT_SECRET = "65a4a390-0acc-4102-b383-972348434f05"
ACCOUNT_ID = 4  # Update account ID 4

def update_oauth_credentials():
    """Update OAuth credentials in database"""
    try:
        conn = sqlite3.connect('just_trades.db')
        cursor = conn.cursor()
        
        # Check if account exists
        cursor.execute("SELECT id, name, client_id FROM accounts WHERE id = ?", (ACCOUNT_ID,))
        account = cursor.fetchone()
        
        if not account:
            print(f"❌ Account {ACCOUNT_ID} not found")
            return False
        
        print(f"✅ Found account: {account[1]} (ID: {account[0]})")
        print(f"   Current Client ID: {account[2]}")
        
        # Update OAuth credentials
        cursor.execute("""
            UPDATE accounts
            SET client_id = ?,
                client_secret = ?
            WHERE id = ?
        """, (NEW_CLIENT_ID, NEW_CLIENT_SECRET, ACCOUNT_ID))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Updated OAuth credentials:")
        print(f"   Client ID: {NEW_CLIENT_ID}")
        print(f"   Client Secret: {NEW_CLIENT_SECRET[:20]}...")
        print("")
        print("Next steps:")
        print("  1. Make sure OAuth app redirect URI is set to:")
        print("     https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback")
        print("  2. Test OAuth flow:")
        print("     http://localhost:8082/api/accounts/4/connect")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating credentials: {e}")
        return False

if __name__ == "__main__":
    update_oauth_credentials()

