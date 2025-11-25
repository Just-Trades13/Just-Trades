#!/usr/bin/env python3
"""
Check if account has TradingView add-on enabled
This checks the /auth/me endpoint which shows active plugins
"""

import asyncio
import aiohttp
import sqlite3
import sys
import os

DB_PATH = os.getenv('DB_PATH', 'just_trades.db')

async def check_tradingview_addon(account_id):
    """Check if account has TradingView add-on enabled"""
    
    # Get account credentials
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT username, password, client_id, client_secret, name,
               tradovate_token
        FROM accounts
        WHERE id = ? AND enabled = 1
    """, (account_id,))
    
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print(f"❌ Account {account_id} not found")
        return False
    
    username = account['username']
    password = account['password']
    client_id = account['client_id']
    client_secret = account['client_secret']
    account_name = account['name']
    token = account['tradovate_token']
    
    print("=" * 60)
    print("Checking TradingView Add-On Status")
    print("=" * 60)
    print(f"Account: {account_name} (ID: {account_id})")
    print(f"Username: {username}")
    print()
    
    # If we have a stored token, use it
    if token:
        print("✅ Found stored token, using it...")
        access_token = token
    else:
        print("⚠️  No stored token, need to authenticate first")
        print("   This will check if TradingView add-on is required")
        print()
        
        # Try to authenticate
        login_data = {
            "name": username,
            "password": password,
            "appId": "Just.Trade",
            "appVersion": "1.0.0",
            "cid": client_id,
            "sec": client_secret
        }
        
        base_url = "https://demo.tradovateapi.com/v1"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/auth/accesstokenrequest",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                data = await response.json()
                
                # Check for CAPTCHA
                if "p-captcha" in data and data.get("p-captcha"):
                    print("❌ CAPTCHA challenge received")
                    print()
                    print("⚠️  This suggests:")
                    print("   1. TradingView add-on may not be enabled")
                    print("   2. Or account needs to enable API access")
                    print()
                    print("Solution:")
                    print("   1. Enable TradingView add-on in Tradovate account")
                    print("   2. Then try authentication again")
                    return False
                
                # Check for access token
                if "accessToken" in data:
                    access_token = data.get("accessToken")
                    print("✅ Authentication successful!")
                else:
                    error = data.get("errorText", "Unknown error")
                    print(f"❌ Authentication failed: {error}")
                    return False
    
    # Now check /auth/me to see active plugins
    print("\n📋 Checking account info and plugins...")
    base_url = "https://demo.tradovateapi.com/v1"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{base_url}/auth/me",
            headers=headers
        ) as response:
            if response.status == 200:
                me_data = await response.json()
                
                print("\n" + "=" * 60)
                print("Account Information:")
                print("=" * 60)
                print(f"User ID: {me_data.get('userId')}")
                print(f"Email: {me_data.get('email')}")
                print(f"Account Plan: {me_data.get('currentAccountPlan', 'N/A')}")
                print(f"Balance: ${me_data.get('currentBalance', 0)}")
                
                # Check active plugins
                plugins = me_data.get('activePlugins', [])
                print(f"\nActive Plugins: {plugins}")
                
                # Check for TradingView or API access
                has_tradingview = any('tradingview' in str(p).lower() for p in plugins)
                has_api_access = 'apiAccess' in plugins
                
                print()
                if has_api_access:
                    print("✅ apiAccess plugin is ACTIVE")
                else:
                    print("❌ apiAccess plugin is NOT active")
                    print("   This may be required for API access")
                
                if has_tradingview:
                    print("✅ TradingView plugin found in active plugins")
                else:
                    print("⚠️  TradingView plugin not found in active plugins")
                    print("   Trade Manager requires TradingView add-on to be enabled")
                
                # Check market data subscriptions
                md_subs = me_data.get('currentMDSubs', [])
                if md_subs:
                    print(f"\nMarket Data Subscriptions: {md_subs}")
                
                print()
                print("=" * 60)
                if has_api_access:
                    print("✅ Account appears to have API access enabled")
                    print("   Authentication should work")
                else:
                    print("⚠️  Account may not have API access enabled")
                    print("   Enable TradingView add-on or API Access subscription")
                print("=" * 60)
                
                return has_api_access
            else:
                text = await response.text()
                print(f"❌ Failed to get account info: {response.status}")
                print(f"Response: {text[:200]}")
                return False


def main():
    account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    
    print("Checking TradingView Add-On Requirement")
    print("Based on Trade Manager's requirement")
    print()
    
    has_access = asyncio.run(check_tradingview_addon(account_id))
    
    if has_access:
        print("\n✅ Account has API access - authentication should work!")
    else:
        print("\n⚠️  Account may need TradingView add-on enabled")
        print("\nNext steps:")
        print("1. Log into Tradovate account")
        print("2. Enable TradingView add-on/plugin")
        print("3. Test authentication again")


if __name__ == '__main__':
    main()

