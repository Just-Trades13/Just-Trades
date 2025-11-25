#!/usr/bin/env python3
"""
Detailed connection test with credential verification
"""

import sqlite3
import asyncio
import aiohttp
import sys

DB_PATH = 'just_trades.db'

async def test_connection_detailed(account_id=4):
    """Test connection with detailed debugging"""
    
    # Get account from database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, username, password, client_id, client_secret
        FROM accounts
        WHERE id = ?
    """, (account_id,))
    
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print(f"❌ Account {account_id} not found in database")
        return
    
    print("=" * 60)
    print("Detailed Connection Test")
    print("=" * 60)
    print()
    print(f"Account ID: {account['id']}")
    print(f"Account Name: {account['name']}")
    print(f"Username: {account['username']}")
    print(f"Password: {'*' * len(account['password']) if account['password'] else 'NOT SET'}")
    print(f"Client ID: {account['client_id']}")
    print(f"Client Secret: {'*' * 20 if account['client_secret'] else 'NOT SET'}")
    print()
    
    # Test authentication
    login_data = {
        "name": account['username'],
        "password": account['password'],
        "appId": "Just.Trade",
        "appVersion": "1.0.0",
        "cid": account['client_id'],
        "sec": account['client_secret']
    }
    
    print("🔄 Attempting authentication...")
    print(f"   Endpoint: https://demo.tradovateapi.com/v1/auth/accesstokenrequest")
    print()
    
    base_url = "https://demo.tradovateapi.com/v1"
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{base_url}/auth/accesstokenrequest",
            json=login_data,
            headers={"Content-Type": "application/json"}
        ) as response:
            status = response.status
            data = await response.json()
            
            print(f"Status Code: {status}")
            print()
            
            if "p-captcha" in data and data.get("p-captcha"):
                print("⚠️  CAPTCHA Required")
                print()
                print("This usually means:")
                print("  1. Account needs to be logged into Tradovate website first")
                print("  2. Or account needs additional security verification")
                print()
                print("Solution:")
                print("  1. Go to https://demo.tradovate.com")
                print("  2. Log in with these credentials")
                print("  3. Complete any security checks")
                print("  4. Then try connecting again")
                return False
            
            if "accessToken" in data:
                access_token = data.get("accessToken")
                print("✅ Authentication Successful!")
                print(f"   Access Token: {access_token[:50]}...")
                print()
                print("✅ Token can be stored and used for API calls")
                return True
            else:
                error = data.get("errorText", "Unknown error")
                print(f"❌ Authentication Failed")
                print(f"   Error: {error}")
                print()
                
                if "Incorrect username or password" in error:
                    print("Possible issues:")
                    print("  1. Password might be incorrect")
                    print("  2. Password might have special characters that need encoding")
                    print("  3. Account might be locked or disabled")
                    print()
                    print("Solution:")
                    print("  1. Verify credentials work on Tradovate website")
                    print("  2. Check if password has special characters")
                    print("  3. Try resetting password if needed")
                
                return False


if __name__ == '__main__':
    account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    asyncio.run(test_connection_detailed(account_id))

