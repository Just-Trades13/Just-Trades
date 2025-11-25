#!/usr/bin/env python3
"""
Test if callback handler works by simulating OAuth callback
"""

import requests
import sys

def test_callback(code="test_code_123", state="4"):
    """Test callback handler with a test code"""
    
    base_url = "http://localhost:8082"
    
    print("=" * 60)
    print("Testing OAuth Callback Handler")
    print("=" * 60)
    print()
    print(f"Simulating OAuth callback with:")
    print(f"  code: {code}")
    print(f"  state: {state}")
    print()
    
    # Test callback URL
    callback_url = f"{base_url}/?code={code}&state={state}"
    print(f"Testing: {callback_url}")
    print()
    
    try:
        response = requests.get(callback_url, allow_redirects=False, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print()
        
        if response.status_code == 302:
            redirect = response.headers.get('Location', '')
            print(f"✅ Redirect detected: {redirect}")
            return True
        elif response.status_code == 200:
            try:
                data = response.json()
                print("Response (JSON):")
                print(f"  {data}")
            except:
                print("Response (HTML):")
                print(response.text[:500])
            return False
        else:
            print(f"Unexpected status: {response.status_code}")
            print(response.text[:200])
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Server not running")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == '__main__':
    code = sys.argv[1] if len(sys.argv) > 1 else "test_code_123"
    state = sys.argv[2] if len(sys.argv) > 2 else "4"
    
    test_callback(code, state)

