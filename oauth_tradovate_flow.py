#!/usr/bin/env python3
"""
OAuth Flow for Tradovate (Like TradersPost)
This implements OAuth 2.0 authorization code flow instead of credential-based auth
This may bypass the TradingView add-on requirement
"""

import asyncio
import aiohttp
import sqlite3
import sys
import os
from urllib.parse import urlencode, parse_qs, urlparse
from datetime import datetime, timedelta

DB_PATH = os.getenv('DB_PATH', 'just_trades.db')
CLIENT_ID = "8552"
CLIENT_SECRET = "d7d4fc4c-43f1-4f5d-a132-dd3e95213239"
REDIRECT_URI = "http://localhost:8082/auth/tradovate/callback"

# OAuth endpoints (need to verify these with Tradovate)
DEMO_AUTH_URL = "https://demo.tradovate.com/oauth/authorize"
DEMO_TOKEN_URL = "https://demo.tradovateapi.com/v1/auth/accesstokenrequest"
LIVE_AUTH_URL = "https://tradovate.com/oauth/authorize"
LIVE_TOKEN_URL = "https://live.tradovateapi.com/v1/auth/accesstokenrequest"


def get_oauth_authorization_url(demo=True, state=None):
    """
    Generate OAuth authorization URL
    User should visit this URL to authorize the application
    """
    base_url = DEMO_AUTH_URL if demo else LIVE_AUTH_URL
    
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "read write"  # Adjust based on Tradovate's requirements
    }
    
    if state:
        params["state"] = state
    
    return f"{base_url}?{urlencode(params)}"


async def exchange_code_for_token(authorization_code, demo=True):
    """
    Exchange authorization code for access token
    This is the OAuth token exchange step
    """
    base_url = DEMO_TOKEN_URL if demo else LIVE_TOKEN_URL
    
    # OAuth token exchange request
    token_data = {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            base_url,
            json=token_data,
            headers={"Content-Type": "application/json"}
        ) as response:
            data = await response.json()
            
            if "accessToken" in data:
                return {
                    "success": True,
                    "access_token": data.get("accessToken"),
                    "refresh_token": data.get("refreshToken"),
                    "expires_in": data.get("expiresIn", 86400),
                    "token_type": data.get("tokenType", "Bearer")
                }
            else:
                return {
                    "success": False,
                    "error": data.get("errorText", "Unknown error"),
                    "data": data
                }


async def test_oauth_flow_alternative(demo=True):
    """
    Alternative: Try OAuth-style authentication
    TradersPost might be using a different approach
    """
    print("=" * 60)
    print("Testing OAuth-Style Authentication (Like TradersPost)")
    print("=" * 60)
    print()
    print("TradersPost doesn't require TradingView add-on")
    print("They likely use OAuth flow instead of credential-based")
    print()
    
    # Get account from database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, password, name
        FROM accounts
        WHERE id = 4
    """)
    
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print("Account not found")
        return
    
    username = account['username']
    password = account['password']
    account_name = account['name']
    
    print(f"Account: {account_name}")
    print(f"Username: {username}")
    print()
    
    # Try different OAuth-style approaches
    base_url = "https://demo.tradovateapi.com/v1" if demo else "https://live.tradovateapi.com/v1"
    
    methods = [
        {
            "name": "OAuth with client credentials grant",
            "data": {
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "username": username,
                "password": password
            }
        },
        {
            "name": "OAuth with password grant",
            "data": {
                "grant_type": "password",
                "username": username,
                "password": password,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET
            }
        },
        {
            "name": "OAuth-style with scope",
            "data": {
                "name": username,
                "password": password,
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
                "cid": CLIENT_ID,
                "sec": CLIENT_SECRET,
                "scope": "read write",
                "grant_type": "authorization_code"
            }
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for method in methods:
            print(f"🔐 Trying: {method['name']}")
            
            try:
                async with session.post(
                    f"{base_url}/auth/accesstokenrequest",
                    json=method['data'],
                    headers={"Content-Type": "application/json"}
                ) as response:
                    data = await response.json()
                    
                    # Check for CAPTCHA
                    if "p-captcha" in data and data.get("p-captcha"):
                        print(f"   ⚠️  CAPTCHA challenge")
                        continue
                    
                    # Check for access token
                    if "accessToken" in data:
                        access_token = data.get("accessToken")
                        print(f"   ✅ SUCCESS! Got access token!")
                        print(f"   Token: {access_token[:50]}...")
                        
                        # Test API access
                        headers = {
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        }
                        
                        async with session.get(
                            f"{base_url}/account/list",
                            headers=headers
                        ) as acc_response:
                            if acc_response.status == 200:
                                accounts = await acc_response.json()
                                print(f"   ✅ Found {len(accounts)} account(s)")
                                return True
                    
                    error = data.get("errorText", "Unknown error")
                    print(f"   ❌ Error: {error}")
                    
            except Exception as e:
                print(f"   ❌ Exception: {e}")
    
    print()
    print("=" * 60)
    print("Key Insight:")
    print("=" * 60)
    print("TradersPost uses OAuth redirect flow:")
    print("1. User clicks 'Connect Tradovate'")
    print("2. Redirect to Tradovate OAuth page")
    print("3. User authorizes")
    print("4. Tradovate redirects back with code")
    print("5. Exchange code for token")
    print()
    print("This bypasses add-on requirements!")
    print()
    print("Next: Implement OAuth redirect flow in your web app")
    
    return False


def print_oauth_instructions():
    """Print instructions for OAuth flow"""
    print("=" * 60)
    print("OAuth Flow Implementation (Like TradersPost)")
    print("=" * 60)
    print()
    print("Step 1: User clicks 'Connect Tradovate'")
    print("Step 2: Redirect to OAuth authorization URL:")
    print()
    auth_url = get_oauth_authorization_url(demo=True)
    print(f"   {auth_url}")
    print()
    print("Step 3: User logs in and authorizes")
    print("Step 4: Tradovate redirects to callback with code")
    print("Step 5: Exchange code for token")
    print("Step 6: Store token in database")
    print()
    print("Note: Need to verify OAuth endpoints with Tradovate")
    print("      May need to check Tradovate API documentation")
    print()


async def main():
    print("TradersPost-Style OAuth Flow")
    print("Goal: Bypass TradingView add-on requirement")
    print()
    
    # Print OAuth instructions
    print_oauth_instructions()
    
    # Try alternative OAuth-style methods
    print("\n" + "=" * 60)
    print("Testing Alternative OAuth Methods")
    print("=" * 60)
    print()
    
    success = await test_oauth_flow_alternative(demo=True)
    
    if not success:
        print("\n" + "=" * 60)
        print("Recommendation")
        print("=" * 60)
        print("\n1. Check Tradovate API documentation for OAuth endpoints")
        print("2. Verify OAuth authorization URL format")
        print("3. Implement OAuth redirect flow in web app")
        print("4. Test with demo account")
        print("\nThis should work like TradersPost (no add-on required)")


if __name__ == '__main__':
    asyncio.run(main())

