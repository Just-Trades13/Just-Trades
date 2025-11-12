#!/usr/bin/env python3
"""
Test login endpoint directly
"""

import sys
import json

try:
    from http.client import HTTPConnection
except ImportError:
    from httplib import HTTPConnection

def test_login():
    """Test the login endpoint"""
    conn = HTTPConnection('localhost', 5000)
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    body = json.dumps({
        'username': 'testuser',
        'password': 'testpass123'
    })
    
    print("Testing login endpoint...")
    print(f"URL: POST http://localhost:5000/api/auth/login/")
    print(f"Body: {body}")
    print()
    
    conn.request('POST', '/api/auth/login/', body, headers)
    response = conn.getresponse()
    
    data = response.read().decode('utf-8')
    
    print(f"Status: {response.status}")
    print(f"Response: {data}")
    
    if response.status == 200:
        result = json.loads(data)
        if result.get('success'):
            print("\n✅ Login successful!")
            print(f"   User: {result.get('user', {}).get('username')}")
        else:
            print("\n❌ Login failed (success: false)")
    else:
        print("\n❌ Login failed (HTTP error)")
    
    conn.close()

if __name__ == '__main__':
    test_login()

