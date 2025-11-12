#!/usr/bin/env python3
"""
Backend Validation Script
Tests what we have and identifies what's missing
"""

import requests
import json
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:5000"

def test_endpoint(method: str, endpoint: str, data: dict = None, headers: dict = None) -> Tuple[bool, dict]:
    """Test an API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            return False, {"error": "Invalid method"}
        
        return True, {
            "status_code": response.status_code,
            "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
    except requests.exceptions.ConnectionError:
        return False, {"error": "Server not running"}
    except Exception as e:
        return False, {"error": str(e)}

def validate_backend():
    """Validate current backend implementation"""
    
    print("=" * 60)
    print("BACKEND VALIDATION REPORT")
    print("=" * 60)
    
    # Get CSRF token first
    print("\n1. Testing System Endpoints...")
    success, result = test_endpoint("GET", "/api/system/csrf-token/")
    if success and result.get("status_code") == 200:
        csrf_token = result.get("response", {}).get("csrf_token", "")
        print(f"   ✅ CSRF Token: {csrf_token[:20]}...")
    else:
        print(f"   ❌ CSRF Token failed: {result}")
        csrf_token = ""
    
    headers = {
        "X-CSRFToken": csrf_token,
        "Content-Type": "application/json"
    }
    
    # Test endpoints
    endpoints_to_test = [
        # System
        ("GET", "/api/system/csrf-token/", None, None),
        
        # Auth
        ("GET", "/api/auth/check-auth/", None, headers),
        ("POST", "/api/auth/login/", {"username": "test", "password": "test"}, headers),
        
        # Accounts
        ("GET", "/api/accounts/get-all-at-accounts/", None, headers),
        ("POST", "/api/accounts/add-tradovate/", {
            "username": "test",
            "password": "test",
            "client_id": "test",
            "client_secret": "test"
        }, headers),
        
        # Strategies
        ("GET", "/api/strategies/", None, headers),
        ("POST", "/api/strategies/", {
            "name": "Test Strategy",
            "position_size": 1
        }, headers),
        
        # Dashboard
        ("GET", "/api/dashboard/summary/", None, headers),
        
        # Recorder
        ("GET", "/api/recorder/positions/", None, headers),
    ]
    
    results = {
        "working": [],
        "missing": [],
        "errors": []
    }
    
    print("\n2. Testing API Endpoints...")
    for method, endpoint, data, test_headers in endpoints_to_test:
        success, result = test_endpoint(method, endpoint, data, test_headers)
        
        if not success:
            if "not running" in result.get("error", ""):
                print(f"\n⚠️  SERVER NOT RUNNING")
                print(f"   Start the server with: python app.py")
                return
            results["errors"].append((method, endpoint, result))
            print(f"   ❌ {method} {endpoint} - Error: {result.get('error')}")
        elif result.get("status_code") == 200:
            results["working"].append((method, endpoint))
            print(f"   ✅ {method} {endpoint}")
        elif result.get("status_code") == 404:
            results["missing"].append((method, endpoint))
            print(f"   ⚠️  {method} {endpoint} - Not implemented (404)")
        elif result.get("status_code") == 401:
            results["working"].append((method, endpoint))
            print(f"   ✅ {method} {endpoint} - Auth required (expected)")
        else:
            results["errors"].append((method, endpoint, result))
            print(f"   ❌ {method} {endpoint} - Status: {result.get('status_code')}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Working endpoints: {len(results['working'])}")
    print(f"⚠️  Missing endpoints: {len(results['missing'])}")
    print(f"❌ Errors: {len(results['errors'])}")
    
    if results["missing"]:
        print("\nMissing Endpoints:")
        for method, endpoint in results["missing"]:
            print(f"   - {method} {endpoint}")
    
    if results["errors"]:
        print("\nErrors:")
        for method, endpoint, error in results["errors"]:
            print(f"   - {method} {endpoint}: {error}")

if __name__ == "__main__":
    validate_backend()

