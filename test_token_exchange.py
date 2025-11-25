#!/usr/bin/env python3
"""
Test OAuth token exchange endpoint
"""

import aiohttp
import asyncio
import json

# Test parameters
TEST_CODE = "test_code_12345"
CLIENT_ID = "8556"
CLIENT_SECRET = "65a4a390-0acc-4102-b383-972348434f05"
REDIRECT_URI = "https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback"

# Token exchange endpoints to test
TOKEN_ENDPOINTS = [
    'https://live-api.tradovate.com/auth/oauthtoken',
    'https://demo-api.tradovate.com/auth/oauthtoken',
    'https://live.tradovateapi.com/v1/auth/oauthtoken',
    'https://demo.tradovateapi.com/v1/auth/oauthtoken',
    'https://live.tradovateapi.com/v1/auth/accesstokenrequest',
    'https://demo.tradovateapi.com/v1/auth/accesstokenrequest',
]

async def test_token_endpoint(endpoint, token_data):
    """Test a token exchange endpoint"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                endpoint,
                json=token_data,
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
            ) as response:
                response_text = await response.text()
                print(f"\n{'='*60}")
                print(f"Endpoint: {endpoint}")
                print(f"Status: {response.status}")
                print(f"Response: {response_text[:300]}")
                
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        if 'accessToken' in data or 'access_token' in data:
                            print("✅ SUCCESS - Token received!")
                            return True
                        else:
                            print("⚠️  Response doesn't contain token")
                    except:
                        print("⚠️  Could not parse JSON")
                else:
                    print(f"❌ Failed - Status {response.status}")
                
                return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

async def test_all_endpoints():
    """Test all token exchange endpoints"""
    token_data = {
        'grant_type': 'authorization_code',
        'code': TEST_CODE,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    
    print("Testing OAuth token exchange endpoints...")
    print(f"Client ID: {CLIENT_ID}")
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"Code: {TEST_CODE} (test code)")
    print("\nNote: This will fail because test_code is invalid, but we can see which endpoints exist")
    
    results = []
    for endpoint in TOKEN_ENDPOINTS:
        result = await test_token_endpoint(endpoint, token_data)
        results.append((endpoint, result))
    
    print(f"\n{'='*60}")
    print("Summary:")
    for endpoint, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {endpoint}")

if __name__ == "__main__":
    asyncio.run(test_all_endpoints())

