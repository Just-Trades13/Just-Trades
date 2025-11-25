#!/usr/bin/env python3
"""Test using stored tokens from just_trades.db"""

import sqlite3
import asyncio
import aiohttp
import json
from datetime import datetime

async def test_with_stored_tokens():
    """Try to use stored tokens from just_trades.db"""
    
    print("Checking for stored tokens in just_trades.db...")
    print("=" * 60)
    
    # Connect to correct database
    db_path = "/Users/mylesjadwin/Trading Projects/just_trades.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get account with tokens (checking correct columns)
        cursor.execute("""
            SELECT id, name, tradovate_token, md_access_token, token_expires_at
            FROM accounts 
            WHERE broker = 'Tradovate' 
            AND tradovate_token IS NOT NULL
            LIMIT 1
        """)
        
        account = cursor.fetchone()
        conn.close()
        
        if not account:
            print("❌ No stored tokens found in just_trades.db")
            print("\nOptions:")
            print("1. Authenticate through main server web interface first")
            print("2. Or wait for CAPTCHA requirement to expire")
            print("3. Or use main server's /api/positions endpoint instead")
            return False
        
        # Unpack account data
        acc_id, name, access_token, md_access_token, token_expires = account
        
        print(f"✅ Found stored tokens for account: {name} (ID: {acc_id})")
        print(f"   Has access_token: {bool(access_token)}")
        print(f"   Has md_access_token: {bool(md_access_token)}")
        print(f"   Token expires: {token_expires}")
        
        if not access_token:
            print("❌ No access token stored")
            return False
        
        # Check if token is expired
        if token_expires:
            try:
                expires_dt = datetime.fromisoformat(token_expires.replace('Z', '+00:00'))
                now = datetime.now(expires_dt.tzinfo) if expires_dt.tzinfo else datetime.now()
                if now >= expires_dt:
                    print("⚠️  Token is expired")
                    return False
                else:
                    print(f"✅ Token is valid (expires: {token_expires})")
            except:
                print("⚠️  Could not parse expiration date")
        
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
                    
                    print(f"\n{'='*60}")
                    print("✅ SUCCESS! Can use stored tokens")
                    print(f"{'='*60}")
                    print(f"\nAccess Token: {access_token[:50]}...")
                    if md_access_token:
                        print(f"MD Access Token: {md_access_token[:50]}...")
                    else:
                        print("MD Access Token: None (may need to re-authenticate)")
                    
                    return {
                        'access_token': access_token,
                        'md_access_token': md_access_token,
                        'account_id': acc_id
                    }
                else:
                    text = await response.text()
                    print(f"❌ Token test failed: {response.status}")
                    print(f"   Response: {text[:200]}")
                    return False
        
    except sqlite3.OperationalError as e:
        print(f"❌ Database error: {e}")
        print("   Database structure may be different")
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
        print("\nNext: Update test_pnl_tracking.py to use these tokens")
    else:
        print("\n❌ Cannot use stored tokens")
        print("\nNeed to authenticate first (CAPTCHA required)")

