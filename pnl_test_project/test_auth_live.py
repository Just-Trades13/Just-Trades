#!/usr/bin/env python3
"""Test authentication with live endpoint and different approaches"""

import asyncio
import aiohttp
import json

async def test_live_endpoint():
    """Try live endpoint instead of demo"""
    
    username = "markjad58"
    password = "Greens131393!"
    client_id = "8580"
    client_secret = "59dc97d6-0c11-4d2e-9044-480f8a6c1260"
    
    # Try LIVE endpoint
    base_url = "https://live.tradovateapi.com/v1"
    
    approaches = [
        {
            "name": "Live - Without Client ID/Secret",
            "data": {
                "name": username,
                "password": password,
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
            }
        },
        {
            "name": "Live - With Client ID/Secret (8580)",
            "data": {
                "name": username,
                "password": password,
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
                "cid": client_id,
                "sec": client_secret
            }
        },
    ]
    
    async with aiohttp.ClientSession() as session:
        for approach in approaches:
            print(f"\n{'='*60}")
            print(f"Testing: {approach['name']}")
            print(f"{'='*60}")
            
            try:
                async with session.post(
                    f"{base_url}/auth/accesstokenrequest",
                    json=approach['data'],
                    headers={"Content-Type": "application/json"}
                ) as response:
                    print(f"Status: {response.status}")
                    data = await response.json()
                    print(f"Response keys: {list(data.keys())}")
                    
                    if "errorText" in data:
                        print(f"❌ Error: {data['errorText']}")
                    elif "accessToken" in data:
                        print(f"✅ SUCCESS! Got accessToken: {data['accessToken'][:30]}...")
                        if "mdAccessToken" in data:
                            print(f"✅ Got mdAccessToken: {data['mdAccessToken'][:30]}...")
                        print(f"\n🎉 This approach works! Use LIVE endpoint with this configuration.")
                        return approach['name']
                    elif "p-captcha" in data:
                        print(f"⚠️  CAPTCHA required (credentials might be correct)")
                    else:
                        print(f"⚠️  Unexpected response: {data}")
                        
            except Exception as e:
                print(f"❌ Exception: {e}")
                import traceback
                traceback.print_exc()
            
            print()
            await asyncio.sleep(0.5)
    
    return None

if __name__ == "__main__":
    print("Testing LIVE endpoint (not demo)...")
    result = asyncio.run(test_live_endpoint())
    if result:
        print(f"\n✅ Working approach: {result}")
    else:
        print("\n❌ Live endpoint also failed")
        print("\nThe CAPTCHA response suggests:")
        print("1. Credentials might be correct but Tradovate requires CAPTCHA")
        print("2. May need to handle CAPTCHA verification")
        print("3. Or Client ID/Secret might not be registered for this account")

