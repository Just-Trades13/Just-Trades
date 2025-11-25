#!/usr/bin/env python3
"""
Test OAuth redirect flow
Checks if the redirect to Tradovate works
"""

import requests
import sys

def test_oauth_redirect(account_id=4, base_url="http://localhost:8082"):
    """Test OAuth redirect endpoint"""
    
    print("=" * 60)
    print("Testing OAuth Redirect Flow")
    print("=" * 60)
    print()
    print(f"Account ID: {account_id}")
    print(f"Endpoint: {base_url}/api/accounts/{account_id}/connect")
    print()
    
    try:
        # Make request with allow_redirects=False to see redirect
        print("🔄 Testing OAuth redirect...")
        response = requests.get(
            f"{base_url}/api/accounts/{account_id}/connect",
            allow_redirects=False,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print()
        
        if response.status_code == 302 or response.status_code == 301:
            # Redirect found!
            redirect_url = response.headers.get('Location', '')
            print("✅ Redirect detected!")
            print()
            print("Redirect URL:")
            print(f"  {redirect_url}")
            print()
            
            if 'trader.tradovate.com' in redirect_url or 'tradovate.com' in redirect_url:
                print("✅ Redirecting to Tradovate OAuth page!")
                print()
                print("This is correct - user will log in on Tradovate's website")
                print()
                print("Next steps:")
                print("  1. Visit this URL in your browser:")
                print(f"     {base_url}/api/accounts/{account_id}/connect")
                print("  2. You'll be redirected to Tradovate")
                print("  3. Log in and authorize")
                print("  4. You'll be redirected back with token")
                return True
            else:
                print("⚠️  Redirect URL doesn't look like Tradovate")
                print("   Expected: trader.tradovate.com or tradovate.com")
                return False
        elif response.status_code == 200:
            # No redirect - might be JSON response
            try:
                data = response.json()
                print("Response (JSON):")
                print(f"  {data}")
                if data.get('error'):
                    print()
                    print(f"❌ Error: {data.get('error')}")
            except:
                print("Response (HTML):")
                print(response.text[:200])
            return False
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Server not running")
        print()
        print("Start the server first:")
        print("  python3 ultra_simple_server.py")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == '__main__':
    account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8082"
    
    success = test_oauth_redirect(account_id, base_url)
    
    print()
    print("=" * 60)
    if success:
        print("✅ OAuth redirect is working!")
        print()
        print("To test in browser:")
        print(f"  {base_url}/api/accounts/{account_id}/connect")
    else:
        print("❌ OAuth redirect test failed")
        print()
        print("Check:")
        print("  1. Server is running")
        print("  2. Redirect URI is registered in OAuth app")
        print("  3. Client ID is correct")
    print("=" * 60)

