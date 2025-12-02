#!/usr/bin/env python3
"""
Test Hunter.io API directly
"""

import requests

HUNTER_API_KEY = "8c91a296393dcf910f13d0debb01ee58286927a0"

def test_hunter_api():
    url = "https://api.hunter.io/v2/domain-search"
    params = {
        "domain": "microsoft.com",
        "api_key": HUNTER_API_KEY,
        "limit": 5
    }
    
    print(f"Making request to: {url}")
    print(f"Params: {params}")
    
    response = requests.get(url, params=params)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text[:500]}")

if __name__ == "__main__":
    test_hunter_api()
