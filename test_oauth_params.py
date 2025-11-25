#!/usr/bin/env python3
"""
Test different OAuth parameter formats
TradersPost shows OAuth page, but we're seeing regular login
"""

from urllib.parse import urlencode

CLIENT_ID = "8552"
REDIRECT_URI = "http://localhost:8082"
BASE_URL = "https://trader.tradovate.com/welcome"

print("=" * 60)
print("OAuth Parameter Testing")
print("=" * 60)
print()
print("Issue: Seeing regular login page, not OAuth authorization page")
print("TradersPost shows app name and permissions, but we don't")
print()
print("Testing different parameter formats:")
print()

# Test different parameter combinations
test_configs = [
    {
        "name": "Current format",
        "params": {
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': 'read write',
            'state': '4'
        }
    },
    {
        "name": "Space-separated scope",
        "params": {
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': 'read write',
            'state': '4'
        }
    },
    {
        "name": "Comma-separated scope",
        "params": {
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': 'read,write',
            'state': '4'
        }
    },
    {
        "name": "No scope",
        "params": {
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'state': '4'
        }
    },
    {
        "name": "With appId",
        "params": {
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'code',
            'scope': 'read write',
            'state': '4',
            'appId': 'Just.Trade'
        }
    },
    {
        "name": "Different response_type",
        "params": {
            'client_id': CLIENT_ID,
            'redirect_uri': REDIRECT_URI,
            'response_type': 'token',  # Implicit flow
            'scope': 'read write',
            'state': '4'
        }
    }
]

for config in test_configs:
    params = config['params']
    url = f"{BASE_URL}?{urlencode(params)}"
    print(f"{config['name']}:")
    print(f"  {url}")
    print()

print("=" * 60)
print("Possible Issues")
print("=" * 60)
print()
print("1. Client ID format")
print("   - Current: 8552")
print("   - Maybe needs to be a string or different format?")
print()
print("2. Redirect URI")
print("   - Current: http://localhost:8082")
print("   - Must match exactly what's registered")
print("   - Tradovate might not accept localhost")
print()
print("3. OAuth app status")
print("   - App name: 'test'")
print("   - Is it active/enabled?")
print("   - Is it approved by Tradovate?")
print()
print("4. Different endpoint")
print("   - Maybe need: https://trader.tradovate.com/oauth/authorize")
print("   - Or: https://demo.tradovate.com/welcome")
print()
print("5. Missing parameters")
print("   - Maybe need: app_name, app_id, or other params")
print()

print("=" * 60)
print("Next Steps")
print("=" * 60)
print()
print("1. Check OAuth app in Tradovate:")
print("   - Is it active?")
print("   - Is it approved?")
print("   - What's the exact Client ID format?")
print()
print("2. Try different endpoint:")
print("   - https://trader.tradovate.com/oauth/authorize")
print("   - Or check Tradovate API docs for correct endpoint")
print()
print("3. Check redirect URI:")
print("   - Must match EXACTLY (no trailing slash, no path)")
print("   - Tradovate might not accept localhost for OAuth")
print("   - Might need to use ngrok or production URL")
print()

