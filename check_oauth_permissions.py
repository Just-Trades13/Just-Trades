#!/usr/bin/env python3
"""
Check OAuth app permissions and account access
Based on: https://community.tradovate.com/t/oauth-api-not-working/10503/4
"""

import asyncio
import aiohttp
import json

async def check_oauth_permissions(username, password, client_id, client_secret):
    """
    Check OAuth permissions and account access
    Reference: https://community.tradovate.com/t/oauth-api-not-working/10503/4
    """
    
    print("=" * 60)
    print("OAuth Permissions Diagnostic")
    print("Reference: https://community.tradovate.com/t/oauth-api-not-working/10503/4")
    print("=" * 60)
    print()
    
    # Try to authenticate first
    login_data = {
        "name": username,
        "password": password,
        "appId": "Just.Trade",
        "appVersion": "1.0.0",
        "cid": client_id,
        "sec": client_secret
    }
    
    endpoints = [
        ("Demo", "https://demo.tradovateapi.com/v1"),
        ("Live", "https://live.tradovateapi.com/v1")
    ]
    
    async with aiohttp.ClientSession() as session:
        for env_name, base_url in endpoints:
            print(f"\n{'='*60}")
            print(f"Testing {env_name} Environment")
            print(f"{'='*60}")
            
            # Try to login
            print(f"\n🔐 Attempting authentication...")
            try:
                async with session.post(
                    f"{base_url}/auth/accesstokenrequest",
                    json=login_data,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        text = await response.text()
                        print(f"   ❌ Login failed: {response.status}")
                        print(f"   Response: {text[:200]}")
                        continue
                    
                    data = await response.json()
                    
                    if "accessToken" not in data:
                        error = data.get("errorText", "Unknown error")
                        print(f"   ❌ Authentication failed: {error}")
                        continue
                    
                    access_token = data.get("accessToken")
                    print(f"   ✅ Authentication successful!")
                    print(f"   Access Token: {access_token[:40]}...")
                    
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    
                    # Check /auth/me endpoint (shows account info and permissions)
                    print(f"\n📋 Checking /auth/me (account info)...")
                    async with session.get(
                        f"{base_url}/auth/me",
                        headers=headers
                    ) as me_response:
                        if me_response.status == 200:
                            me_data = await me_response.json()
                            print(f"   ✅ Account Info Retrieved:")
                            print(f"   User ID: {me_data.get('userId')}")
                            print(f"   Email: {me_data.get('email')}")
                            print(f"   Account Plan: {me_data.get('currentAccountPlan', 'N/A')}")
                            print(f"   Current Balance: ${me_data.get('currentBalance', 0)}")
                            
                            # Check active plugins
                            plugins = me_data.get('activePlugins', [])
                            print(f"   Active Plugins: {plugins}")
                            
                            if 'apiAccess' in plugins:
                                print(f"   ✅ apiAccess plugin is ACTIVE")
                            else:
                                print(f"   ⚠️  apiAccess plugin is NOT active")
                                print(f"   This account may not have API access enabled")
                            
                            # Check organization
                            org = me_data.get('organizationName', 'N/A')
                            print(f"   Organization: {org}")
                            
                        else:
                            print(f"   ❌ Failed to get /auth/me: {me_response.status}")
                    
                    # Try to get accounts
                    print(f"\n📊 Testing API Endpoints...")
                    print(f"   Getting account list...")
                    async with session.get(
                        f"{base_url}/account/list",
                        headers=headers
                    ) as acc_response:
                        if acc_response.status == 200:
                            accounts = await acc_response.json()
                            print(f"   ✅ Account List: {len(accounts)} account(s)")
                            
                            if len(accounts) == 0:
                                print(f"   ⚠️  Empty account list - this is the issue mentioned in the forum")
                                print(f"   OAuth app may not have 'Account Information' permission")
                            
                            for acc in accounts[:3]:
                                acc_id = acc.get('id')
                                acc_name = acc.get('name', 'N/A')
                                print(f"      - {acc_name} (ID: {acc_id})")
                                
                                # Try to get account details
                                async with session.get(
                                    f"{base_url}/account/item",
                                    headers=headers,
                                    params={"id": acc_id}
                                ) as info_response:
                                    if info_response.status == 200:
                                        account_info = await info_response.json()
                                        balance = (
                                            account_info.get('dayTradingBuyingPower') or
                                            account_info.get('netLiquidation') or
                                            account_info.get('availableFunds')
                                        )
                                        if balance is not None:
                                            print(f"         Balance: ${balance:,.2f}")
                    
                    # Try positions endpoint
                    print(f"\n   Getting positions...")
                    async with session.get(
                        f"{base_url}/position/list",
                        headers=headers
                    ) as pos_response:
                        if pos_response.status == 200:
                            positions = await pos_response.json()
                            print(f"   ✅ Positions: {len(positions)} position(s)")
                            
                            if len(positions) == 0:
                                print(f"   (No open positions - this is normal if account has no positions)")
                            else:
                                for pos in positions:
                                    symbol = pos.get('symbol', 'N/A')
                                    qty = pos.get('quantity', 0)
                                    print(f"      - {symbol}: {qty}")
                        else:
                            print(f"   ❌ Failed to get positions: {pos_response.status}")
                            text = await pos_response.text()
                            print(f"   Response: {text[:200]}")
                    
                    # Try orders endpoint
                    print(f"\n   Getting orders...")
                    async with session.get(
                        f"{base_url}/order/list",
                        headers=headers
                    ) as order_response:
                        if order_response.status == 200:
                            orders = await order_response.json()
                            print(f"   ✅ Orders: {len(orders)} order(s)")
                            
                            if len(orders) == 0:
                                print(f"   (No orders - this is normal)")
                        else:
                            print(f"   ❌ Failed to get orders: {order_response.status}")
                    
                    print(f"\n{'='*60}")
                    print(f"✅ Diagnostic Complete for {env_name}")
                    print(f"{'='*60}")
                    return True
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    return False


async def main():
    username = "WhitneyHughes86"
    password = "L5998E7418C1681tv="
    client_id = "8552"
    client_secret = "d7d4fc4c-43f1-4f5d-a132-dd3e95213239"
    
    print("OAuth Permissions Diagnostic Tool")
    print("Based on forum discussion: https://community.tradovate.com/t/oauth-api-not-working/10503/4")
    print()
    print("This will check:")
    print("  1. Authentication status")
    print("  2. Account info (/auth/me)")
    print("  3. Active plugins (apiAccess)")
    print("  4. API endpoint access (accounts, positions, orders)")
    print()
    
    success = await check_oauth_permissions(username, password, client_id, client_secret)
    
    if success:
        print("\n" + "="*60)
        print("Diagnostic Results")
        print("="*60)
        print("\nIf you see empty arrays [] from endpoints:")
        print("  → Check OAuth app permissions in Tradovate settings")
        print("  → Ensure 'Account Information' and 'Positions' are ALLOWED")
        print("  → Verify account has 'apiAccess' plugin active")
    else:
        print("\n" + "="*60)
        print("Authentication Failed")
        print("="*60)
        print("\nPlease verify:")
        print("  1. Credentials are correct")
        print("  2. OAuth app is properly registered")
        print("  3. Account has API access enabled")


if __name__ == '__main__':
    asyncio.run(main())

