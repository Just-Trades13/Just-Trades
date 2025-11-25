#!/usr/bin/env python3
"""Test using the main server's authentication endpoint"""

import requests
import json

def test_main_server_auth():
    """Try to authenticate through the main server"""
    
    print("Testing authentication through main server...")
    print("=" * 60)
    
    # Try the main server's authenticate endpoint
    base_url = "http://localhost:8082"  # Default port from ultra_simple_server.py
    
    # First, check if server is running
    try:
        response = requests.get(f"{base_url}/api/health", timeout=2)
        print(f"✅ Server is running on {base_url}")
    except:
        print(f"❌ Server not running on {base_url}")
        print("\nOptions:")
        print("1. Start the main server: python ultra_simple_server.py")
        print("2. Or use stored tokens from database")
        return False
    
    # Try to get account info
    try:
        response = requests.get(f"{base_url}/api/accounts", timeout=5)
        if response.status_code == 200:
            accounts = response.json()
            print(f"\nFound {len(accounts)} accounts")
            for acc in accounts:
                print(f"  - {acc.get('name')}: has_token={bool(acc.get('tradovate_token'))}")
    except Exception as e:
        print(f"Could not get accounts: {e}")
    
    return True

if __name__ == "__main__":
    test_main_server_auth()

