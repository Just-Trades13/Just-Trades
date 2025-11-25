#!/usr/bin/env python3
"""Simple test to verify basic functionality before full test"""

import asyncio
import aiohttp
import json

async def test_auth():
    """Test just authentication"""
    print("Testing Tradovate authentication...")
    
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    use_client = input("Use Client ID/Secret? (y/n): ").strip().lower() == 'y'
    
    client_id = None
    client_secret = None
    if use_client:
        client_id = input("Client ID: ").strip()
        client_secret = input("Client Secret: ").strip()
    
    demo = input("Use demo? (y/n): ").strip().lower() == 'y'
    base_url = "https://demo.tradovateapi.com/v1" if demo else "https://live.tradovateapi.com/v1"
    
    login_data = {
        "name": username,
        "password": password,
        "appId": "Just.Trade",
        "appVersion": "1.0.0",
    }
    
    if client_id and client_secret:
        login_data["cid"] = client_id
        login_data["sec"] = client_secret
    
    print(f"\nAttempting authentication to: {base_url}")
    print(f"Login data keys: {list(login_data.keys())}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/auth/accesstokenrequest",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                print(f"\nResponse status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"Response keys: {list(data.keys())}")
                    
                    if "errorText" in data:
                        print(f"❌ Error: {data['errorText']}")
                        return False
                    
                    access_token = data.get("accessToken")
                    md_access_token = data.get("mdAccessToken")
                    
                    if access_token:
                        print(f"✅ Got accessToken: {access_token[:30]}...")
                    else:
                        print("❌ No accessToken in response!")
                        return False
                    
                    if md_access_token:
                        print(f"✅ Got mdAccessToken: {md_access_token[:30]}...")
                    else:
                        print("⚠️  No mdAccessToken in response")
                    
                    return True
                else:
                    text = await response.text()
                    print(f"❌ Failed: {response.status}")
                    print(f"Response: {text[:500]}")
                    return False
                    
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_auth())
    if result:
        print("\n✅ Authentication successful!")
    else:
        print("\n❌ Authentication failed!")

