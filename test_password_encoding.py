#!/usr/bin/env python3
"""
Test password encoding - the password has special characters
Password: L5998E7418C1681tv=
"""

import asyncio
import aiohttp
import sqlite3
from urllib.parse import quote

DB_PATH = 'just_trades.db'

async def test_with_different_encodings(account_id=4):
    """Test authentication with different password encodings"""
    
    # Get account from database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, password, client_id, client_secret
        FROM accounts
        WHERE id = ?
    """, (account_id,))
    
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print("Account not found")
        return
    
    username = account['username']
    password = account['password']
    client_id = account['client_id']
    client_secret = account['client_secret']
    
    print("=" * 60)
    print("Testing Password Encoding")
    print("=" * 60)
    print()
    print(f"Username: {username}")
    print(f"Password (raw): {password}")
    print(f"Password length: {len(password)}")
    print(f"Password ends with: '{password[-1]}'")
    print()
    
    # Test different encoding methods
    methods = [
        {
            "name": "Raw password (as stored)",
            "password": password
        },
        {
            "name": "URL encoded password",
            "password": quote(password, safe='')
        },
        {
            "name": "Password with = removed",
            "password": password.rstrip('=')
        },
        {
            "name": "Password with = replaced",
            "password": password.replace('=', '%3D')
        }
    ]
    
    base_url = "https://demo.tradovateapi.com/v1"
    
    async with aiohttp.ClientSession() as session:
        for method in methods:
            print(f"🔐 Testing: {method['name']}")
            print(f"   Password: {method['password']}")
            
            login_data = {
                "name": username,
                "password": method['password'],
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
                "cid": client_id,
                "sec": client_secret
            }
            
            try:
                async with session.post(
                    f"{base_url}/auth/accesstokenrequest",
                    json=login_data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    data = await response.json()
                    
                    if "p-captcha" in data and data.get("p-captcha"):
                        print("   ⚠️  CAPTCHA challenge")
                        continue
                    
                    if "accessToken" in data:
                        print("   ✅ SUCCESS! This encoding works!")
                        print(f"   Token: {data.get('accessToken')[:50]}...")
                        return True
                    else:
                        error = data.get("errorText", "Unknown")
                        print(f"   ❌ {error}")
                        
            except Exception as e:
                print(f"   ❌ Exception: {e}")
            
            print()
    
    print("=" * 60)
    print("None of the encoding methods worked")
    print()
    print("Next steps:")
    print("1. Verify the password is correct in the database")
    print("2. Try logging into Tradovate website with these exact credentials")
    print("3. Check if password has changed")
    print("4. Consider updating the password in the database")
    
    return False


if __name__ == '__main__':
    asyncio.run(test_with_different_encodings(4))

