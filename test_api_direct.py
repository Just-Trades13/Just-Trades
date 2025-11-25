#!/usr/bin/env python3
"""
Test direct API authentication with CID 8581 to place a trade
This tests if the API credentials work for trading
"""
import asyncio
import aiohttp
import json

# API credentials
CLIENT_ID = "8581"
CLIENT_SECRET = "43469c08-7b5d-4401-8a98-0bd67ad1eb13"

async def test_api_auth_and_trade():
    """Test API authentication and place a trade"""
    print("=" * 60)
    print("TESTING API CREDENTIALS (CID: 8581) FOR TRADING")
    print("=" * 60)
    
    # Try to authenticate with API credentials
    # Note: This might need username/password, or might be OAuth-based
    # Let's try the OAuth token endpoint first
    
    print("\n1️⃣ Attempting to get token with API credentials...")
    
    async with aiohttp.ClientSession() as session:
        # Try different authentication methods
        endpoints = [
            'https://demo.tradovateapi.com/v1/auth/oauthtoken',
            'https://live.tradovateapi.com/v1/auth/oauthtoken',
        ]
        
        for endpoint in endpoints:
            print(f"\n   Trying: {endpoint}")
            
            # Try with client credentials grant (if supported)
            try:
                async with session.post(
                    endpoint,
                    data={
                        'grant_type': 'client_credentials',
                        'client_id': CLIENT_ID,
                        'client_secret': CLIENT_SECRET
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                ) as response:
                    print(f"   Status: {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        print(f"   ✅ Got token!")
                        print(f"   Response: {json.dumps(data, indent=2)}")
                        return data
                    else:
                        text = await response.text()
                        print(f"   ❌ Failed: {text[:200]}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        print("\n⚠️ Direct API authentication not available")
        print("   API credentials (8581) are likely for OAuth flow, not direct auth")
        print("\n   The issue is:")
        print("   - OAuth tokens are generated with phs as number (no trading permissions)")
        print("   - Even though OAuth app has 'Orders: Full Access' enabled")
        print("   - This suggests Tradovate's token generation isn't respecting app permissions")
        print("\n   Possible solutions:")
        print("   1. Check if user account has 'API Trading' enabled in account settings")
        print("   2. Try creating a new OAuth app and re-connecting")
        print("   3. Contact Tradovate support about token permissions not matching app settings")

if __name__ == "__main__":
    asyncio.run(test_api_auth_and_trade())

