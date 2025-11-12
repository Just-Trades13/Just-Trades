#!/usr/bin/env python3
"""
Test Apollo.io API directly to compare with Make.com behavior
"""

import json
import requests

# Your API key
API_KEY = "DtdKb5hTo_9GTtbohlNJ-Q"

# Headers - exactly like Make.com sends
headers = {
    "Content-Type": "application/json",
    "X-Api-Key": API_KEY
}

# Test different search queries
test_searches = [
    # Test 1: Simplest possible
    {
        "page": 1,
        "per_page": 1
    },
    # Test 2: Just location
    {
        "person_locations": ["California"],
        "page": 1,
        "per_page": 1
    },
    # Test 3: Just keywords
    {
        "q_keywords": "Real Estate",
        "page": 1,
        "per_page": 1
    },
    # Test 4: Title search
    {
        "person_titles": ["Real Estate Agent"],
        "page": 1,
        "per_page": 1
    }
]

print("=" * 100)
print("TESTING APOLLO.IO API DIRECTLY")
print("=" * 100)
print()

url = "https://api.apollo.io/v1/mixed_people/search"

for i, search in enumerate(test_searches, 1):
    print(f"\n{'='*100}")
    print(f"TEST {i}: {json.dumps(search, indent=2)}")
    print(f"{'='*100}\n")
    
    try:
        response = requests.post(url, headers=headers, json=search)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\nResponse Structure:")
            print(f"  Keys: {list(data.keys())}")
            
            if "people" in data:
                people_count = len(data.get("people", []))
                print(f"\nPeople Found: {people_count}")
                
                if "pagination" in data:
                    pag = data["pagination"]
                    print(f"Total Entries: {pag.get('total_entries', 0)}")
                    print(f"Total Pages: {pag.get('total_pages', 0)}")
                
                if people_count > 0:
                    print(f"\n✅ SUCCESS! First person:")
                    person = data["people"][0]
                    print(f"  Name: {person.get('first_name', 'N/A')} {person.get('last_name', 'N/A')}")
                    print(f"  Email: {person.get('email', 'N/A')}")
                    print(f"  Title: {person.get('title', 'N/A')}")
                    print(f"  Company: {person.get('organization_name', 'N/A')}")
                    print(f"\n🎯 THIS SEARCH WORKS! Use this in Make.com")
                    break
                else:
                    print(f"\n❌ No people found")
            else:
                print(f"\n⚠️  No 'people' key in response")
                print(f"Full response: {json.dumps(data, indent=2)[:500]}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

print(f"\n{'='*100}")
print("TEST COMPLETE")
print(f"{'='*100}")

