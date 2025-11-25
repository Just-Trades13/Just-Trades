#!/usr/bin/env python3
"""
Test authentication flow similar to Trade Manager
Trade Manager likely uses a different approach - possibly:
1. User authenticates through web interface first
2. Then uses that session/token for API calls
3. Or uses a different OAuth flow
"""

import asyncio
import aiohttp
import json

async def test_trade_manager_style_auth(username, password, client_id, client_secret):
    """
    Test authentication methods that Trade Manager might use
    Based on the fact that Trade Manager CAN sync sim accounts
    """
    
    print("=" * 60)
    print("Testing Trade Manager-Style Authentication")
    print("=" * 60)
    print("Since Trade Manager can sync sim accounts,")
    print("we need to find the correct authentication method")
    print()
    
    # Method 1: Try without OAuth credentials (just username/password)
    # Trade Manager might authenticate first, then use OAuth
    print("Method 1: Direct username/password (no OAuth)")
    print("-" * 60)
    
    methods = [
        {
            "name": "Direct auth without OAuth",
            "data": {
                "name": username,
                "password": password,
                "appId": "Tradovate",
                "appVersion": "1.0.0"
            }
        },
        {
            "name": "OAuth with different appId",
            "data": {
                "name": username,
                "password": password,
                "appId": "Tradovate",
                "appVersion": "1.0.0",
                "cid": client_id,
                "sec": client_secret
            }
        },
        {
            "name": "OAuth with empty/optional fields",
            "data": {
                "name": username,
                "password": password,
                "cid": client_id,
                "sec": client_secret
            }
        }
    ]
    
    endpoints = [
        ("Demo", "https://demo.tradovateapi.com/v1"),
        ("Live", "https://live.tradovateapi.com/v1")
    ]
    
    async with aiohttp.ClientSession() as session:
        for env_name, base_url in endpoints:
            print(f"\n{'='*60}")
            print(f"Testing {env_name} Environment")
            print(f"{'='*60}")
            
            for method in methods:
                print(f"\n🔐 Trying: {method['name']}")
                
                try:
                    async with session.post(
                        f"{base_url}/auth/accesstokenrequest",
                        json=method['data'],
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json",
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                        },
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        status = response.status
                        text = await response.text()
                        
                        print(f"   Status: {status}")
                        
                        try:
                            data = json.loads(text)
                            
                            # Check for CAPTCHA
                            if "p-captcha" in data and data.get("p-captcha"):
                                print(f"   ⚠️  CAPTCHA challenge received")
                                print(f"   This is expected - Trade Manager likely handles this differently")
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
                                
                                print(f"\n   📊 Testing API access...")
                                
                                # Get account list
                                async with session.get(
                                    f"{base_url}/account/list",
                                    headers=headers
                                ) as acc_response:
                                    if acc_response.status == 200:
                                        accounts = await acc_response.json()
                                        print(f"   ✅ Found {len(accounts)} account(s)")
                                        
                                        for acc in accounts:
                                            acc_name = acc.get('name', 'N/A')
                                            acc_id = acc.get('id', 'N/A')
                                            print(f"      - {acc_name} (ID: {acc_id})")
                                            
                                            # Get balance
                                            async with session.get(
                                                f"{base_url}/account/item",
                                                headers=headers,
                                                params={"id": acc_id}
                                            ) as info_response:
                                                if info_response.status == 200:
                                                    info = await info_response.json()
                                                    balance = info.get('dayTradingBuyingPower') or info.get('netLiquidation')
                                                    if balance:
                                                        print(f"         💰 Balance: ${balance:,.2f}")
                                
                                print(f"\n   ✅ This method works! Use this for authentication")
                                return True
                            
                            # Check for errors
                            error = data.get("errorText") or data.get("error") or "Unknown"
                            print(f"   ❌ Error: {error}")
                            
                        except json.JSONDecodeError:
                            print(f"   Response (not JSON): {text[:200]}")
                            
                except Exception as e:
                    print(f"   ❌ Exception: {e}")
    
    print(f"\n{'='*60}")
    print("Key Insight:")
    print("=" * 60)
    print("Trade Manager likely:")
    print("1. Has users authenticate through THEIR web interface first")
    print("2. Uses that authentication session/token")
    print("3. Or uses a different OAuth flow (redirect-based)")
    print()
    print("For your recorder backend, you may need to:")
    print("1. Have users authenticate through your web interface first")
    print("2. Store their tokens after initial authentication")
    print("3. Use those tokens for API calls (bypassing CAPTCHA)")
    print()
    print("OR use API keys instead of OAuth for backend services")
    
    return False


async def main():
    username = "WhitneyHughes86"
    password = "L5998E7418C1681tv="
    client_id = "8552"
    client_secret = "d7d4fc4c-43f1-4f5d-a132-dd3e95213239"
    
    print("Testing Trade Manager-Style Authentication")
    print("Goal: Find how Trade Manager successfully authenticates sim accounts")
    print()
    
    success = await test_trade_manager_style_auth(username, password, client_id, client_secret)
    
    if not success:
        print("\n" + "="*60)
        print("Recommendation")
        print("="*60)
        print("\nSince Trade Manager can sync the account, the solution is likely:")
        print("\n1. **User authenticates through web interface first**")
        print("   - User logs into your website")
        print("   - They authenticate with Tradovate (solving CAPTCHA)")
        print("   - You store the access token")
        print("   - Backend uses stored token (no CAPTCHA needed)")
        print("\n2. **Use stored tokens for API calls**")
        print("   - Tokens are valid for 24 hours")
        print("   - Refresh tokens when they expire")
        print("   - This is how Trade Manager likely works")
        print("\n3. **Alternative: Use API Keys**")
        print("   - Generate API keys in Tradovate account")
        print("   - API keys may bypass CAPTCHA")
        print("   - Better for automated backend services")


if __name__ == '__main__':
    asyncio.run(main())

