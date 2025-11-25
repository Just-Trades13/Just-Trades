#!/usr/bin/env python3
"""
Detailed test of Tradovate credentials with multiple approaches
"""

import asyncio
import aiohttp
import json

async def test_login_approaches(username, password, client_id, client_secret):
    """Try different login approaches"""
    
    username = username.strip()
    password = password.strip()
    
    print("=" * 60)
    print("Testing Multiple Authentication Approaches")
    print("=" * 60)
    print(f"Username: '{username}' (length: {len(username)})")
    print(f"Password: '{password[:5]}...{password[-3:]}' (length: {len(password)})")
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {client_secret[:15]}...")
    print()
    
    # Different endpoints to try
    endpoints = [
        ("Demo", "https://demo.tradovateapi.com/v1/auth/accesstokenrequest"),
        ("Live", "https://live.tradovateapi.com/v1/auth/accesstokenrequest"),
    ]
    
    # Different app IDs to try
    app_ids = [
        "Just.Trade",
        "Tradovate",
        "TradovateAPI",
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint_name, endpoint_url in endpoints:
            print(f"\n{'='*60}")
            print(f"Testing {endpoint_name} Endpoint")
            print(f"{'='*60}")
            
            for app_id in app_ids:
                login_data = {
                    "name": username,
                    "password": password,
                    "appId": app_id,
                    "appVersion": "1.0.0",
                    "cid": client_id,
                    "sec": client_secret
                }
                
                print(f"\n🔐 Trying App ID: {app_id}")
                print(f"   Endpoint: {endpoint_url}")
                
                try:
                    async with session.post(
                        endpoint_url,
                        json=login_data,
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        status = response.status
                        try:
                            data = await response.json()
                        except:
                            text = await response.text()
                            print(f"   ❌ Status: {status}")
                            print(f"   Response: {text[:200]}")
                            continue
                        
                        print(f"   Status: {status}")
                        
                        if status == 200 and "accessToken" in data:
                            access_token = data.get("accessToken")
                            refresh_token = data.get("refreshToken")
                            
                            print(f"   ✅ SUCCESS!")
                            print(f"   Access Token: {access_token[:30]}...")
                            print(f"   Refresh Token: {refresh_token[:30] if refresh_token else 'N/A'}...")
                            
                            # Now get account info
                            print(f"\n   📊 Fetching account information...")
                            headers = {
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json"
                            }
                            
                            base_url = endpoint_url.replace("/auth/accesstokenrequest", "")
                            
                            # Get accounts
                            async with session.get(
                                f"{base_url}/account/list",
                                headers=headers
                            ) as acc_response:
                                if acc_response.status == 200:
                                    accounts = await acc_response.json()
                                    print(f"   ✅ Found {len(accounts)} account(s)")
                                    
                                    for acc in accounts[:3]:  # Show first 3
                                        acc_id = acc.get('id')
                                        acc_name = acc.get('name', 'N/A')
                                        
                                        print(f"\n   Account: {acc_name} (ID: {acc_id})")
                                        
                                        # Get account details
                                        async with session.get(
                                            f"{base_url}/account/item?id={acc_id}",
                                            headers=headers
                                        ) as info_response:
                                            if info_response.status == 200:
                                                account_info = await info_response.json()
                                                
                                                # Try to find balance
                                                balance_fields = [
                                                    'dayTradingBuyingPower',
                                                    'netLiquidation',
                                                    'availableFunds',
                                                    'balance',
                                                    'cashBalance'
                                                ]
                                                
                                                for field in balance_fields:
                                                    value = account_info.get(field)
                                                    if value is not None:
                                                        print(f"      {field}: ${value}")
                                                        break
                                                
                                                # Get positions
                                                async with session.get(
                                                    f"{base_url}/position/list",
                                                    headers=headers,
                                                    params={"accountId": acc_id}
                                                ) as pos_response:
                                                    if pos_response.status == 200:
                                                        positions = await pos_response.json()
                                                        if positions:
                                                            print(f"      Open Positions: {len(positions)}")
                                                            for pos in positions[:3]:
                                                                symbol = pos.get('symbol', 'N/A')
                                                                qty = pos.get('quantity', 0)
                                                                avg = pos.get('averagePrice', 0)
                                                                print(f"        - {symbol}: {qty} @ ${avg}")
                                    
                                    print(f"\n   ✅ Connection verified! Balance retrieved successfully!")
                                    return True
                                    
                        else:
                            error = data.get("errorText", "Unknown error")
                            print(f"   ❌ Failed: {error}")
                            
                except asyncio.TimeoutError:
                    print(f"   ❌ Timeout")
                except Exception as e:
                    print(f"   ❌ Error: {e}")
    
    print(f"\n{'='*60}")
    print("❌ All authentication attempts failed")
    print(f"{'='*60}")
    return False


async def main():
    username = "WhitneyHughes86"
    password = "L5998E7418C1681tv="
    client_id = "8552"
    client_secret = "d7d4fc4c-43f1-4f5d-a132-dd3e95213239"
    
    success = await test_login_approaches(username, password, client_id, client_secret)
    
    if success:
        print("\n✅ Authentication successful! Your setup is working.")
    else:
        print("\n❌ Authentication failed. Please check:")
        print("   1. Credentials are correct")
        print("   2. OAuth app has proper permissions")
        print("   3. Account is active")


if __name__ == '__main__':
    asyncio.run(main())

