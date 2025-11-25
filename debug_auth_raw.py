#!/usr/bin/env python3
"""
Debug authentication with full error details
"""

import asyncio
import aiohttp
import json

async def debug_auth():
    username = "WhitneyHughes86"
    password = "L5998E7418C1681tv="
    client_id = "8552"
    client_secret = "d7d4fc4c-43f1-4f5d-a132-dd3e95213239"
    
    login_data = {
        "name": username,
        "password": password,
        "appId": "Just.Trade",
        "appVersion": "1.0.0",
        "cid": client_id,
        "sec": client_secret
    }
    
    print("=" * 60)
    print("Raw Authentication Debug")
    print("=" * 60)
    print(f"\nRequest URL: https://demo.tradovateapi.com/v1/auth/accesstokenrequest")
    print(f"Request Payload:")
    print(json.dumps(login_data, indent=2))
    print()
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://demo.tradovateapi.com/v1/auth/accesstokenrequest",
                json=login_data,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                print(f"Response Status: {response.status}")
                print(f"Response Headers: {dict(response.headers)}")
                print()
                
                # Try to get response as text first
                text = await response.text()
                print(f"Response (raw text):")
                print(text)
                print()
                
                # Try to parse as JSON
                try:
                    data = json.loads(text)
                    print(f"Response (parsed JSON):")
                    print(json.dumps(data, indent=2))
                    
                    # Check for specific error fields
                    if "errorText" in data:
                        print(f"\n❌ Error Text: {data['errorText']}")
                    if "error" in data:
                        print(f"❌ Error: {data['error']}")
                    if "message" in data:
                        print(f"❌ Message: {data['message']}")
                    if "accessToken" in data:
                        print(f"✅ Access Token found!")
                        
                except json.JSONDecodeError:
                    print("Response is not valid JSON")
                    
        except Exception as e:
            print(f"Exception: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(debug_auth())

