#!/usr/bin/env python3
"""
Test different OAuth endpoints to find the correct one
"""

CLIENT_ID = "8552"
REDIRECT_URI = "http://localhost:8082"

# Different possible OAuth endpoints
endpoints = [
    "https://trader.tradovate.com/welcome",
    "https://trader.tradovate.com/oauth/authorize",
    "https://trader.tradovate.com/api/oauth/authorize",
    "https://demo.tradovate.com/oauth/authorize",
    "https://demo.tradovate.com/api/oauth/authorize",
    "https://tradovate.com/oauth/authorize",
    "https://tradovateapi.com/oauth/authorize",
    "https://live.tradovateapi.com/oauth/authorize",
    "https://demo.tradovateapi.com/oauth/authorize",
]

print("=" * 60)
print("OAuth Endpoint Testing")
print("=" * 60)
print()
print("TradersPost shows: 'Sign In with Tradovate to continue to TradersPost Production Env'")
print("But you're seeing: Regular login page (no app name, no permissions)")
print()
print("This suggests the OAuth endpoint or format is wrong.")
print()
print("Possible OAuth URLs:")
print("-" * 60)
for endpoint in endpoints:
    oauth_url = f"{endpoint}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=read+write"
    print(f"  {oauth_url}")
print()
print("=" * 60)
print("What to Check")
print("=" * 60)
print()
print("1. Check OAuth App Registration:")
print("   - Log into Tradovate")
print("   - Application Settings → API Access → OAuth Registration")
print("   - Verify Client ID: 8552 exists")
print("   - Check what redirect URI is registered")
print("   - Check if app is active/enabled")
print()
print("2. Try Different Endpoints:")
print("   - The endpoint might be different")
print("   - Try: https://trader.tradovate.com/oauth/authorize")
print("   - Try: https://demo.tradovate.com/oauth/authorize")
print()
print("3. Check OAuth App Type:")
print("   - Is it registered as OAuth app or API key?")
print("   - Does it support OAuth authorization flow?")
print()
print("4. Compare with TradersPost:")
print("   - TradersPost uses: https://trader.tradovate.com/welcome")
print("   - But shows OAuth authorization page")
print("   - Maybe different parameters needed?")

