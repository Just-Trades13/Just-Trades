#!/usr/bin/env python3
"""
Manual Token Storage for Testing
Since CAPTCHA is required, you can:
1. Get token from browser (after solving CAPTCHA)
2. Store it here manually
3. Recorder backend will use stored token (no CAPTCHA needed)
"""

import sqlite3
import sys
from datetime import datetime, timedelta

DB_PATH = 'just_trades.db'

def store_token_manually(account_id, access_token, refresh_token=None, expires_in_hours=24):
    """Manually store a Tradovate access token"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Calculate expiration
    expires_at = datetime.now() + timedelta(hours=expires_in_hours)
    
    cursor.execute("""
        UPDATE accounts
        SET tradovate_token = ?,
            tradovate_refresh_token = ?,
            token_expires_at = ?
        WHERE id = ?
    """, (access_token, refresh_token, expires_at.isoformat(), account_id))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Token stored for account {account_id}")
    print(f"   Expires: {expires_at}")
    print()
    print("Now the recorder backend can use this token (no CAPTCHA needed)!")


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 manual_token_storage.py <account_id> <access_token> [refresh_token]")
        print()
        print("To get a token:")
        print("1. Open browser developer tools (F12)")
        print("2. Go to Network tab")
        print("3. Log into Tradovate website")
        print("4. Look for requests to /auth/accesstokenrequest")
        print("5. Copy the accessToken from the response")
        print()
        print("Or use a tool like Postman to authenticate and get the token")
        sys.exit(1)
    
    account_id = int(sys.argv[1])
    access_token = sys.argv[2]
    refresh_token = sys.argv[3] if len(sys.argv) > 3 else None
    
    store_token_manually(account_id, access_token, refresh_token)


if __name__ == '__main__':
    main()

