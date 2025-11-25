#!/usr/bin/env python3
"""
Test Tradovate Sim Trading authentication
Sim trading accounts may use different endpoints or authentication
"""

import asyncio
import aiohttp
import json

async def test_sim_trading_login(username, password, client_id, client_secret):
    """Test sim trading account authentication"""
    
    username = username.strip()
    password = password.strip()
    
    print("=" * 60)
    print("Testing Sim Trading Account Authentication")
    print("=" * 60)
    print(f"Username: {username}")
    print(f"Client ID: {client_id}")
    print()
    
    # Try different endpoints that might work for sim trading
    endpoints = [
        ("Sim Trading", "https://sim.tradovateapi.com/v1/auth/accesstokenrequest"),
        ("Demo (Sim)", "https://demo.tradovateapi.com/v1/auth/accesstokenrequest"),
        ("Live", "https://live.tradovateapi.com/v1/auth/accesstokenrequest"),
    ]
    
    # Different login payload formats
    login_formats = [
        {
            "name": "Standard with OAuth",
            "data": {
                "name": username,
                "password": password,
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
                "cid": client_id,
                "sec": client_secret
            }
        },
        {
            "name": "Standard without OAuth",
            "data": {
                "name": username,
                "password": password,
                "appId": "Tradovate",
                "appVersion": "1.0.0"
            }
        },
        {
            "name": "With device ID",
            "data": {
                "name": username,
                "password": password,
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
                "cid": client_id,
                "sec": client_secret,
                "deviceId": "Just.Trade-Device-1"
            }
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint_name, endpoint_url in endpoints:
            print(f"\n{'='*60}")
            print(f"Testing {endpoint_name} Endpoint")
            print(f"URL: {endpoint_url}")
            print(f"{'='*60}")
            
            for login_format in login_formats:
                print(f"\n🔐 Trying: {login_format['name']}")
                
                try:
                    async with session.post(
                        endpoint_url,
                        json=login_format['data'],
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        status = response.status
                        try:
                            data = await response.json()
                        except:
                            text = await response.text()
                            print(f"   Status: {status}")
                            print(f"   Response (text): {text[:200]}")
                            continue
                        
                        print(f"   Status: {status}")
                        
                        if status == 200:
                            if "accessToken" in data:
                                access_token = data.get("accessToken")
                                refresh_token = data.get("refreshToken")
                                
                                print(f"   ✅ SUCCESS!")
                                print(f"   Access Token: {access_token[:40]}...")
                                
                                # Get account info
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
                                        
                                        for acc in accounts:
                                            acc_id = acc.get('id')
                                            acc_name = acc.get('name', 'N/A')
                                            acc_type = acc.get('accountType', 'N/A')
                                            
                                            print(f"\n   Account: {acc_name}")
                                            print(f"   ID: {acc_id}")
                                            print(f"   Type: {acc_type}")
                                            
                                            # Get account details
                                            async with session.get(
                                                f"{base_url}/account/item?id={acc_id}",
                                                headers=headers
                                            ) as info_response:
                                                if info_response.status == 200:
                                                    account_info = await info_response.json()
                                                    
                                                    # Find balance
                                                    balance = (
                                                        account_info.get('dayTradingBuyingPower') or
                                                        account_info.get('netLiquidation') or
                                                        account_info.get('availableFunds') or
                                                        account_info.get('cashBalance') or
                                                        account_info.get('balance')
                                                    )
                                                    
                                                    if balance is not None:
                                                        print(f"   💰 Balance/Buying Power: ${balance}")
                                                    
                                                    # Get positions
                                                    async with session.get(
                                                        f"{base_url}/position/list",
                                                        headers=headers,
                                                        params={"accountId": acc_id}
                                                    ) as pos_response:
                                                        if pos_response.status == 200:
                                                            positions = await pos_response.json()
                                                            if positions:
                                                                print(f"   📈 Open Positions: {len(positions)}")
                                                                for pos in positions:
                                                                    symbol = pos.get('symbol', 'N/A')
                                                                    qty = pos.get('quantity', 0)
                                                                    avg = pos.get('averagePrice', 0)
                                                                    print(f"      - {symbol}: {qty} @ ${avg}")
                                    
                                    print(f"\n   ✅ Connection verified! Balance retrieved successfully!")
                                    return True
                                    
                            else:
                                error = data.get("errorText", data.get("error", "Unknown error"))
                                print(f"   ❌ Failed: {error}")
                        else:
                            text = await response.text()
                            print(f"   ❌ Status: {status}")
                            print(f"   Response: {text[:200]}")
                            
                except asyncio.TimeoutError:
                    print(f"   ❌ Timeout")
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    import traceback
                    traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("❌ All authentication attempts failed")
    print(f"{'='*60}")
    return False


async def main():
    username = "WhitneyHughes86"
    password = "L5998E7418C1681tv="
    client_id = "8552"
    client_secret = "d7d4fc4c-43f1-4f5d-a132-dd3e95213239"
    
    print("Testing Sim Trading Account Authentication")
    print("Note: Sim trading accounts may require different authentication")
    print()
    
    success = await test_sim_trading_login(username, password, client_id, client_secret)
    
    if success:
        print("\n✅ Authentication successful! Sim trading account connected.")
    else:
        print("\n❌ Authentication failed.")
        print("\nPossible issues:")
        print("1. Sim trading accounts might need to be accessed through the web interface first")
        print("2. OAuth app might need sim trading specific permissions")
        print("3. Account might need to be activated for API access")


if __name__ == '__main__':
    asyncio.run(main())

