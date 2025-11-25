#!/usr/bin/env python3
"""Debug authentication - try multiple approaches"""

import asyncio
import aiohttp
import json

async def test_auth_approaches():
    """Try different authentication approaches"""
    
    username = "markjad58"
    password = "Greens131393!"
    client_id = "8580"
    client_secret = "59dc97d6-0c11-4d2e-9044-480f8a6c1260"
    
    base_url = "https://demo.tradovateapi.com/v1"
    
    # Try different approaches
    approaches = [
        {
            "name": "Without Client ID/Secret",
            "data": {
                "name": username,
                "password": password,
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
            }
        },
        {
            "name": "With Client ID/Secret (8580)",
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
            "name": "With Client ID/Secret (cid8580)",
            "data": {
                "name": username,
                "password": password,
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
                "cid": f"cid{client_id}",
                "sec": client_secret
            }
        },
        {
            "name": "Different appId: Tradovate",
            "data": {
                "name": username,
                "password": password,
                "appId": "Tradovate",
                "appVersion": "1.0.0",
            }
        },
        {
            "name": "Different appId: TradovateAPI",
            "data": {
                "name": username,
                "password": password,
                "appId": "TradovateAPI",
                "appVersion": "1.0.0",
            }
        },
    ]
    
    async with aiohttp.ClientSession() as session:
        for approach in approaches:
            print(f"\n{'='*60}")
            print(f"Testing: {approach['name']}")
            print(f"{'='*60}")
            print(f"Request data: {json.dumps(approach['data'], indent=2)}")
            
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
                        print(f"\n🎉 This approach works! Use this configuration.")
                        return approach['name']
                    else:
                        print(f"⚠️  Unexpected response: {data}")
                        
            except Exception as e:
                print(f"❌ Exception: {e}")
                import traceback
                traceback.print_exc()
            
            print()
            await asyncio.sleep(0.5)  # Small delay between attempts
    
    print("\n❌ None of the approaches worked")
    return None

if __name__ == "__main__":
    result = asyncio.run(test_auth_approaches())
    if result:
        print(f"\n✅ Working approach: {result}")
    else:
        print("\n❌ All approaches failed")
        print("\nTroubleshooting:")
        print("1. Verify username and password are correct")
        print("2. Check if account is demo or live")
        print("3. Try logging into Tradovate website directly")
        print("4. Check if Client ID/Secret are correct for your account")

