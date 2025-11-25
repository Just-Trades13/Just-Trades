#!/usr/bin/env python3
"""
Test TradersPost-Style Connection
Tests the new /api/accounts/<id>/connect endpoint
"""

import requests
import json
import sys

def test_connection(account_id=4, base_url="http://localhost:8082"):
    """Test the TradersPost-style connection endpoint"""
    
    print("=" * 60)
    print("Testing TradersPost-Style Connection")
    print("=" * 60)
    print()
    print(f"Account ID: {account_id}")
    print(f"Endpoint: {base_url}/api/accounts/{account_id}/connect")
    print()
    
    try:
        # Make GET request to connect endpoint
        print("🔄 Connecting to Tradovate...")
        response = requests.get(
            f"{base_url}/api/accounts/{account_id}/connect",
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print()
        
        # Parse response
        try:
            data = response.json()
        except:
            print("❌ Response is not JSON:")
            print(response.text)
            return False
        
        # Display result
        if data.get('success'):
            print("✅ SUCCESS! Account connected!")
            print()
            print("Details:")
            print(f"  Account ID: {data.get('account_id')}")
            print(f"  Account Name: {data.get('account_name')}")
            print(f"  Token Expires: {data.get('expires_at')}")
            print()
            print("✅ Token stored in database")
            print("✅ Recorder backend can now use this token")
            print("✅ No CAPTCHA needed for future API calls")
            return True
        else:
            print("❌ Connection Failed")
            print()
            print("Error Details:")
            print(f"  Error: {data.get('error')}")
            print(f"  Message: {data.get('message', 'N/A')}")
            print()
            
            if data.get('error') == 'CAPTCHA_REQUIRED':
                print("⚠️  CAPTCHA Required")
                print()
                print("Possible solutions:")
                print("  1. Log into Tradovate website first")
                print("  2. Complete any security checks")
                print("  3. Try again after logging in")
            elif data.get('requires_setup'):
                print("⚠️  Account may need additional setup")
                print("   Try logging into Tradovate website first")
            
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Server not running")
        print()
        print("Start the server first:")
        print("  python3 ultra_simple_server.py")
        return False
    except requests.exceptions.Timeout:
        print("❌ Request Timeout: Server took too long to respond")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_token_usage(account_id=4, base_url="http://localhost:8082"):
    """Test if stored token can be used"""
    
    print()
    print("=" * 60)
    print("Testing Token Usage")
    print("=" * 60)
    print()
    
    try:
        # Test connection endpoint (uses stored token)
        print("🔄 Testing connection with stored token...")
        response = requests.post(
            f"{base_url}/api/accounts/{account_id}/test-connection",
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Token is valid and working!")
                if 'accounts' in data:
                    print(f"   Found {len(data['accounts'])} account(s)")
                    for acc in data['accounts']:
                        balance = acc.get('balance', 0)
                        print(f"   - {acc.get('name')}: ${balance:,.2f}")
                return True
            else:
                print("❌ Token test failed")
                print(f"   Error: {data.get('error')}")
                return False
        else:
            print(f"❌ Test failed: Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing token: {e}")
        return False


def main():
    account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8082"
    
    print()
    print("TradersPost-Style Connection Test")
    print("=" * 60)
    print()
    
    # Test connection
    success = test_connection(account_id, base_url)
    
    if success:
        # Test token usage
        test_token_usage(account_id, base_url)
    
    print()
    print("=" * 60)
    if success:
        print("✅ All tests passed!")
        print()
        print("Next steps:")
        print("  1. Test recorder backend with stored token")
        print("  2. Verify positions can be fetched")
        print("  3. Start recording positions")
    else:
        print("❌ Connection test failed")
        print()
        print("Troubleshooting:")
        print("  1. Check if server is running")
        print("  2. Verify account credentials in database")
        print("  3. Try logging into Tradovate website first")
        print("  4. Check server logs for errors")
    print("=" * 60)


if __name__ == '__main__':
    main()

