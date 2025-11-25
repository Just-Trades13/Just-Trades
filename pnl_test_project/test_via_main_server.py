#!/usr/bin/env python3
"""Test authentication through main server API"""

import requests
import json

def test_via_main_server():
    """Authenticate through main server's API endpoint"""
    
    print("Testing authentication through main server API...")
    print("=" * 60)
    
    base_url = "http://localhost:8082"
    
    # Get account ID first
    try:
        response = requests.get(f"{base_url}/api/accounts", timeout=5)
        if response.status_code == 200:
            accounts_data = response.json()
            # Handle both list and dict responses
            if isinstance(accounts_data, list):
                accounts = accounts_data
            elif isinstance(accounts_data, dict) and 'accounts' in accounts_data:
                accounts = accounts_data['accounts']
            else:
                accounts = [accounts_data] if accounts_data else []
            
            print(f"Found {len(accounts)} accounts")
            for acc in accounts:
                acc_id = acc.get('id') if isinstance(acc, dict) else acc[0] if isinstance(acc, (list, tuple)) else None
                acc_name = acc.get('name') if isinstance(acc, dict) else 'Unknown'
                print(f"  - Account ID: {acc_id}, Name: {acc_name}")
                
                if acc_id:
                    # Try to authenticate this account
                    print(f"\n{'='*60}")
                    print(f"Attempting to authenticate account {acc_id}...")
                    print(f"{'='*60}")
                    
                    auth_url = f"{base_url}/api/accounts/{acc_id}/authenticate"
                    try:
                        auth_response = requests.post(auth_url, timeout=10)
                        print(f"Auth response status: {auth_response.status_code}")
                        
                        if auth_response.status_code == 200:
                            auth_data = auth_response.json()
                            print(f"Response: {json.dumps(auth_data, indent=2)}")
                            
                            if auth_data.get('success'):
                                print("✅ Authentication successful!")
                                print(f"   Access token: {auth_data.get('access_token', '')[:30]}...")
                                print(f"   MD Access token: {auth_data.get('md_access_token', '')[:30]}...")
                                return True
                            else:
                                print(f"❌ Authentication failed: {auth_data.get('error', 'Unknown error')}")
                        else:
                            print(f"❌ Auth failed: {auth_response.status_code}")
                            print(f"   Response: {auth_response.text[:200]}")
                    except Exception as e:
                        print(f"❌ Error calling auth endpoint: {e}")
                    
                    break  # Try first account only
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return False

if __name__ == "__main__":
    result = test_via_main_server()
    if result:
        print("\n✅ Can authenticate through main server!")
        print("\nNext: Use main server's authentication, then get tokens for test")
    else:
        print("\n❌ Could not authenticate through main server")

