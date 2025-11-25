#!/usr/bin/env python3
"""
Test authentication based on Tradovate API documentation
Reference: https://api.tradovate.com/
"""

import asyncio
import aiohttp
import json

async def test_api_docs_authentication(username, password, client_id, client_secret):
    """Test authentication following Tradovate API documentation"""
    
    print("=" * 60)
    print("Testing Tradovate API Authentication")
    print("Reference: https://api.tradovate.com/")
    print("=" * 60)
    print()
    
    # According to Tradovate API docs, the endpoint should be:
    # POST https://demo.tradovateapi.com/v1/auth/accesstokenrequest
    # or
    # POST https://live.tradovateapi.com/v1/auth/accesstokenrequest
    
    # The request body should include:
    # - name (username)
    # - password
    # - appId (optional, but recommended)
    # - appVersion (optional)
    # - cid (Client ID from OAuth registration)
    # - sec (Client Secret from OAuth registration)
    
    endpoints = [
        {
            "name": "Demo API",
            "url": "https://demo.tradovateapi.com/v1/auth/accesstokenrequest",
            "base_url": "https://demo.tradovateapi.com/v1"
        },
        {
            "name": "Live API", 
            "url": "https://live.tradovateapi.com/v1/auth/accesstokenrequest",
            "base_url": "https://live.tradovateapi.com/v1"
        }
    ]
    
    # Try different payload formats as per API docs
    payloads = [
        {
            "name": "Full OAuth with appId",
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
            "name": "OAuth without appId",
            "data": {
                "name": username,
                "password": password,
                "cid": client_id,
                "sec": client_secret
            }
        },
        {
            "name": "OAuth with Tradovate appId",
            "data": {
                "name": username,
                "password": password,
                "appId": "Tradovate",
                "appVersion": "1.0.0",
                "cid": client_id,
                "sec": client_secret
            }
        }
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            print(f"\n{'='*60}")
            print(f"Testing {endpoint['name']}")
            print(f"URL: {endpoint['url']}")
            print(f"{'='*60}")
            
            for payload in payloads:
                print(f"\n🔐 Trying: {payload['name']}")
                print(f"   Payload keys: {list(payload['data'].keys())}")
                
                try:
                    async with session.post(
                        endpoint['url'],
                        json=payload['data'],
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                        },
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as response:
                        status = response.status
                        
                        # Get response
                        try:
                            data = await response.json()
                        except:
                            text = await response.text()
                            print(f"   Status: {status}")
                            print(f"   Response (text): {text[:300]}")
                            continue
                        
                        print(f"   Status: {status}")
                        
                        if status == 200:
                            if "accessToken" in data:
                                access_token = data.get("accessToken")
                                refresh_token = data.get("refreshToken")
                                user_id = data.get("userId")
                                
                                print(f"   ✅ SUCCESS!")
                                print(f"   Access Token: {access_token[:50]}...")
                                print(f"   User ID: {user_id}")
                                
                                # Now test getting account info
                                print(f"\n   📊 Testing API endpoints...")
                                headers = {
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "application/json",
                                    "Accept": "application/json"
                                }
                                
                                # Get account list
                                print(f"   Getting account list...")
                                async with session.get(
                                    f"{endpoint['base_url']}/account/list",
                                    headers=headers
                                ) as acc_response:
                                    if acc_response.status == 200:
                                        accounts = await acc_response.json()
                                        print(f"   ✅ Found {len(accounts)} account(s)")
                                        
                                        for acc in accounts[:3]:
                                            acc_id = acc.get('id')
                                            acc_name = acc.get('name', 'N/A')
                                            acc_type = acc.get('accountType', 'N/A')
                                            
                                            print(f"\n   Account: {acc_name}")
                                            print(f"   ID: {acc_id}")
                                            print(f"   Type: {acc_type}")
                                            
                                            # Get account item/details
                                            print(f"   Getting account details...")
                                            async with session.get(
                                                f"{endpoint['base_url']}/account/item",
                                                headers=headers,
                                                params={"id": acc_id}
                                            ) as info_response:
                                                if info_response.status == 200:
                                                    account_info = await info_response.json()
                                                    
                                                    # Display balance information
                                                    balance_fields = {
                                                        'dayTradingBuyingPower': 'Day Trading Buying Power',
                                                        'netLiquidation': 'Net Liquidation',
                                                        'availableFunds': 'Available Funds',
                                                        'cashBalance': 'Cash Balance',
                                                        'balance': 'Balance'
                                                    }
                                                    
                                                    print(f"   💰 Account Balance Information:")
                                                    for field, label in balance_fields.items():
                                                        value = account_info.get(field)
                                                        if value is not None:
                                                            print(f"      {label}: ${value:,.2f}")
                                                    
                                                    # Get positions
                                                    print(f"   Getting positions...")
                                                    async with session.get(
                                                        f"{endpoint['base_url']}/position/list",
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
                                                                    pnl = pos.get('realizedPnL', 0)
                                                                    print(f"      - {symbol}: {qty} @ ${avg} (PnL: ${pnl})")
                                                            else:
                                                                print(f"   No open positions")
                                                
                                    print(f"\n   ✅ Connection verified! API is working correctly!")
                                    print(f"   ✅ This endpoint and payload combination works!")
                                    return True
                                    
                            else:
                                error = data.get("errorText", data.get("error", "Unknown error"))
                                print(f"   ❌ Failed: {error}")
                                
                                # Provide helpful error messages
                                if "password" in error.lower() or "username" in error.lower():
                                    print(f"   ⚠️  Credential issue - verify username/password")
                                elif "app" in error.lower() or "registered" in error.lower():
                                    print(f"   ⚠️  OAuth app issue - check Client ID/Secret")
                                    
                        else:
                            print(f"   ❌ HTTP {status}")
                            print(f"   Response: {json.dumps(data, indent=2)[:300]}")
                            
                except asyncio.TimeoutError:
                    print(f"   ❌ Request timeout")
                except Exception as e:
                    print(f"   ❌ Error: {e}")
                    import traceback
                    traceback.print_exc()
    
    print(f"\n{'='*60}")
    print("❌ All authentication attempts failed")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("1. Verify credentials work on Tradovate website")
    print("2. Check OAuth app permissions in Tradovate settings")
    print("3. Ensure OAuth app supports the account type (sim/demo/live)")
    print("4. Review API docs: https://api.tradovate.com/")
    return False


async def main():
    username = "WhitneyHughes86"
    password = "L5998E7418C1681tv="
    client_id = "8552"
    client_secret = "d7d4fc4c-43f1-4f5d-a132-dd3e95213239"
    
    print("Testing Tradovate API Authentication")
    print("Following official API documentation: https://api.tradovate.com/")
    print()
    
    success = await test_api_docs_authentication(username, password, client_id, client_secret)
    
    if success:
        print("\n" + "="*60)
        print("✅ SUCCESS! Authentication working!")
        print("="*60)
        print("\nYour recorder backend should now be able to:")
        print("  ✅ Authenticate users")
        print("  ✅ Fetch account balances")
        print("  ✅ Read positions")
        print("  ✅ Record trading activity")
    else:
        print("\n" + "="*60)
        print("❌ Authentication still failing")
        print("="*60)
        print("\nPlease check:")
        print("  1. OAuth app settings in Tradovate")
        print("  2. Account API access permissions")
        print("  3. API documentation: https://api.tradovate.com/")


if __name__ == '__main__':
    asyncio.run(main())

