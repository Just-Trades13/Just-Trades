#!/usr/bin/env python3
"""
Quick API test script
Tests all endpoints to verify everything works
"""

import requests
import json
import time

BASE_URL = "http://localhost:5001/api"

def test_endpoint(method, endpoint, data=None, cookies=None):
    """Test an API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, cookies=cookies, timeout=2)
        else:
            response = requests.post(url, json=data, cookies=cookies, timeout=2)
        
        return {
            "status": response.status_code,
            "success": response.status_code == 200,
            "data": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
    except requests.exceptions.ConnectionError:
        return {"status": 0, "success": False, "error": "Connection refused - server not running"}
    except Exception as e:
        return {"status": 0, "success": False, "error": str(e)}

def main():
    print("=" * 60)
    print("🧪 Testing Just.Trades API")
    print("=" * 60)
    print()
    
    # Wait for server
    print("⏳ Waiting for server to start...")
    for i in range(10):
        result = test_endpoint("GET", "/system/csrf-token/")
        if result["success"]:
            print("✅ Server is running!")
            break
        time.sleep(1)
    else:
        print("❌ Server not responding. Start it with: python3 app.py")
        return
    
    print()
    
    # Test 1: CSRF Token
    print("1️⃣  Testing CSRF Token...")
    result = test_endpoint("GET", "/system/csrf-token/")
    if result["success"]:
        token = result["data"].get("csrf_token", "")
        print(f"   ✅ CSRF Token: {token[:30]}...")
    else:
        print(f"   ❌ Failed: {result.get('error', result['status'])}")
    
    # Test 2: Login
    print("\n2️⃣  Testing Login...")
    login_data = {"username": "testuser", "password": "testpass123"}
    result = test_endpoint("POST", "/auth/login/", data=login_data)
    cookies = None
    if result["success"]:
        user = result["data"].get("user", {})
        print(f"   ✅ Login successful!")
        print(f"   👤 User: {user.get('username')}")
        print(f"   📧 Email: {user.get('email')}")
        # Get session cookie
        session = requests.Session()
        session.post(f"{BASE_URL}/auth/login/", json=login_data)
        cookies = session.cookies
    else:
        print(f"   ❌ Login failed: {result.get('error', result.get('data', {}))}")
        return
    
    # Test 3: Check Auth
    print("\n3️⃣  Testing Check Auth...")
    result = test_endpoint("GET", "/auth/check-auth/", cookies=cookies)
    if result["success"]:
        user = result["data"].get("user", {})
        print(f"   ✅ Authenticated: {user.get('username')}")
    else:
        print(f"   ❌ Failed: {result.get('error', result['status'])}")
    
    # Test 4: Dashboard Summary
    print("\n4️⃣  Testing Dashboard Summary...")
    result = test_endpoint("GET", "/dashboard/summary/", cookies=cookies)
    if result["success"]:
        data = result["data"]
        print(f"   ✅ Dashboard loaded")
        print(f"   📊 Strategies: {data.get('total_strategies', 0)}")
        print(f"   📈 Positions: {data.get('active_positions', 0)}")
        print(f"   💰 P&L: ${data.get('total_pnl', 0):.2f}")
    else:
        print(f"   ❌ Failed: {result.get('error', result['status'])}")
    
    # Test 5: Get Strategies
    print("\n5️⃣  Testing Get Strategies...")
    result = test_endpoint("GET", "/strategies/", cookies=cookies)
    if result["success"]:
        strategies = result["data"].get("strategies", [])
        print(f"   ✅ Found {len(strategies)} strategies")
    else:
        print(f"   ❌ Failed: {result.get('error', result['status'])}")
    
    # Test 6: Get Accounts
    print("\n6️⃣  Testing Get Accounts...")
    result = test_endpoint("GET", "/accounts/get-all-at-accounts/", cookies=cookies)
    if result["success"]:
        accounts = result["data"].get("accounts", [])
        print(f"   ✅ Found {len(accounts)} accounts")
    else:
        print(f"   ❌ Failed: {result.get('error', result['status'])}")
    
    print()
    print("=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)
    print()
    print("🌐 Frontend should connect to: http://localhost:5001")
    print("📱 Login credentials: testuser / testpass123")

if __name__ == "__main__":
    main()

