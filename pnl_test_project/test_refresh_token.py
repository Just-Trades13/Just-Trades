#!/usr/bin/env python3
"""Test refreshing token to avoid CAPTCHA"""

import sqlite3
import asyncio
import aiohttp
import json
from datetime import datetime, timedelta

async def refresh_token():
    """Refresh access token using refresh token (no CAPTCHA needed)"""
    
    print("Attempting to refresh token (no CAPTCHA required)...")
    print("=" * 60)
    
    db_path = "/Users/mylesjadwin/Trading Projects/just_trades.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get account with refresh token
        cursor.execute("""
            SELECT id, name, tradovate_refresh_token, client_id, client_secret
            FROM accounts 
            WHERE broker = 'Tradovate' 
            AND tradovate_refresh_token IS NOT NULL
            LIMIT 1
        """)
        
        account = cursor.fetchone()
        conn.close()
        
        if not account:
            print("❌ No refresh token found")
            return False
        
        acc_id, name, refresh_token, client_id, client_secret = account
        
        print(f"✅ Found refresh token for account: {name} (ID: {acc_id})")
        print(f"   Client ID: {client_id or '8580'}")
        
        # Use default if not set
        client_id = client_id or "8580"
        client_secret = client_secret or "59dc97d6-0c11-4d2e-9044-480f8a6c1260"
        
        # Refresh token endpoint - try multiple formats
        base_url = "https://demo.tradovateapi.com/v1"
        
        # Try OAuth 2.0 format (from tradovate_integration.py)
        from urllib.parse import urlencode
        
        oauth_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        if client_id:
            oauth_data['client_id'] = client_id
        if client_secret:
            oauth_data['client_secret'] = client_secret
        
        oauth_form_data = urlencode(oauth_data)
        
        print(f"\nRefreshing token...")
        print(f"Endpoint: {base_url}/oauth/token")
        print(f"Using OAuth 2.0 format")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/oauth/token",
                data=oauth_form_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
            ) as response:
                print(f"Status: {response.status}")
                data = await response.json()
                print(f"Response keys: {list(data.keys())}")
                
                if "errorText" in data:
                    print(f"❌ Error: {data['errorText']}")
                    return False
                
                if "accessToken" in data:
                    access_token = data.get("accessToken")
                    md_access_token = data.get("mdAccessToken")
                    new_refresh_token = data.get("refreshToken", refresh_token)
                    
                    print(f"✅ Token refreshed successfully!")
                    print(f"   Access Token: {access_token[:50]}...")
                    if md_access_token:
                        print(f"   MD Access Token: {md_access_token[:50]}...")
                    else:
                        print(f"   ⚠️  No MD Access Token in refresh response")
                    
                    # Update database
                    expires_in = data.get("expiresIn", 86400)
                    expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
                    
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE accounts 
                        SET tradovate_token = ?,
                            tradovate_refresh_token = ?,
                            token_expires_at = ?,
                            md_access_token = ?
                        WHERE id = ?
                    """, (access_token, new_refresh_token, expires_at, md_access_token, acc_id))
                    conn.commit()
                    conn.close()
                    
                    print(f"✅ Tokens updated in database")
                    
                    return {
                        'access_token': access_token,
                        'md_access_token': md_access_token,
                        'refresh_token': new_refresh_token
                    }
                else:
                    print(f"❌ Unexpected response: {data}")
                    return False
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(refresh_token())
    if result:
        print("\n✅ Token refresh successful!")
        print("\nNow you can run test_pnl_tracking.py and it should work")
    else:
        print("\n❌ Token refresh failed")
        print("\nMay need to authenticate through web interface first")

