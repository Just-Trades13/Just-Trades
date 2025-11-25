#!/usr/bin/env python3
"""Test using stored tokens from database"""

import sqlite3
import asyncio
import aiohttp
import json
from datetime import datetime

async def test_with_stored_tokens():
    """Try to use stored tokens from database"""
    
    print("Checking for stored tokens in database...")
    print("=" * 60)
    
    # Connect to database
    db_path = "/Users/mylesjadwin/Trading Projects/trading_data.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get account with tokens
        cursor.execute("""
            SELECT id, name, username, tradovate_token, tradovate_refresh_token, 
                   token_expires_at, md_access_token, client_id, client_secret
            FROM accounts 
            WHERE broker = 'Tradovate' 
            AND tradovate_token IS NOT NULL
            LIMIT 1
        """)
        
        account = cursor.fetchone()
        conn.close()
        
        if not account:
            print("❌ No stored tokens found in database")
            print("\nYou need to:")
            print("1. Authenticate through the main server first")
            print("2. Or use the /api/accounts/<id>/authenticate endpoint")
            return False
        
        # Unpack account data
        (acc_id, name, username, access_token, refresh_token, 
         token_expires, md_access_token, client_id, client_secret) = account
        
        print(f"✅ Found stored tokens for account: {name} (ID: {acc_id})")
        print(f"   Username: {username}")
        print(f"   Has access_token: {bool(access_token)}")
        print(f"   Has md_access_token: {bool(md_access_token)}")
        print(f"   Token expires: {token_expires}")
        
        if not access_token:
            print("❌ No access token stored")
            return False
        
        # Check if token is expired
        if token_expires:
            expires_dt = datetime.fromisoformat(token_expires.replace('Z', '+00:00'))
            if datetime.now(expires_dt.tzinfo) >= expires_dt:
                print("⚠️  Token is expired, need to refresh")
                if refresh_token:
                    print("   Has refresh token, can refresh")
                else:
                    print("   No refresh token, need to re-authenticate")
                return False
            else:
                print(f"✅ Token is valid (expires: {token_expires})")
        
        # Test the token
        print(f"\n{'='*60}")
        print("Testing stored token...")
        print(f"{'='*60}")
        
        base_url = "https://demo.tradovateapi.com/v1"
        
        async with aiohttp.ClientSession() as session:
            # Try to get account list with stored token
            async with session.get(
                f"{base_url}/account/list",
                headers={"Authorization": f"Bearer {access_token}"}
            ) as response:
                if response.status == 200:
                    accounts = await response.json()
                    print(f"✅ Token works! Found {len(accounts)} accounts")
                    if accounts:
                        print(f"   Account: {accounts[0].get('name', 'Unknown')}")
                    return True
                else:
                    text = await response.text()
                    print(f"❌ Token test failed: {response.status}")
                    print(f"   Response: {text[:200]}")
                    return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_with_stored_tokens())
    if result:
        print("\n✅ Can use stored tokens!")
        print("\nNext: Update test_pnl_tracking.py to use stored tokens")
    else:
        print("\n❌ Cannot use stored tokens")
        print("\nNeed to authenticate first through main server")

