#!/usr/bin/env python3
"""
Test Apollo.io API to check email status
"""
import subprocess
import json

API_KEY = "DtdKb5hTo_9GTtbohlNJ-Q"
BASE_URL = "https://api.apollo.io/v1/mixed_people/search"

def test_apollo_api():
    print("=" * 100)
    print("TESTING APOLLO.IO API - EMAIL STATUS")
    print("=" * 100)
    print()
    
    # Test 1: Simple search
    print("TEST 1: Simple Search (No Filters)")
    print("-" * 100)
    payload1 = {
        "page": 1,
        "per_page": 3
    }
    
    result1 = curl_request(payload1)
    if result1:
        analyze_emails(result1, "Simple Search")
    
    # Test 2: Property Manager search (your current search)
    print("\n" + "=" * 100)
    print("TEST 2: Property Manager Search (Your Current Search)")
    print("-" * 100)
    payload2 = {
        "q_keywords": "property manager",
        "person_locations": ["Texas"],
        "page": 1,
        "per_page": 5
    }
    
    result2 = curl_request(payload2)
    if result2:
        analyze_emails(result2, "Property Manager Search")
    
    # Test 3: With verified email filter
    print("\n" + "=" * 100)
    print("TEST 3: Property Manager + Verified Emails Only")
    print("-" * 100)
    payload3 = {
        "q_keywords": "property manager",
        "person_locations": ["Texas"],
        "page": 1,
        "per_page": 5,
        "email_status": ["verified"]
    }
    
    result3 = curl_request(payload3)
    if result3:
        analyze_emails(result3, "Property Manager + Verified Filter")
    
    print("\n" + "=" * 100)
    print("✅ TEST COMPLETE")
    print("=" * 100)

def curl_request(payload):
    """Make curl request to Apollo API"""
    try:
        payload_json = json.dumps(payload)
        cmd = [
            "curl", "-s", "-X", "POST", BASE_URL,
            "-H", "Content-Type: application/json",
            "-H", f"X-Api-Key: {API_KEY}",
            "-d", payload_json
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            print(f"❌ Error: {result.stderr}")
            return None
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def analyze_emails(data, test_name):
    """Analyze email status from Apollo response"""
    if "people" not in data:
        print(f"❌ No 'people' key in response")
        print(f"Response keys: {list(data.keys())}")
        return
    
    people = data.get("people", [])
    print(f"\n✅ Found {len(people)} people")
    
    if len(people) == 0:
        print("⚠️  No results returned")
        return
    
    verified_count = 0
    locked_count = 0
    unavailable_count = 0
    real_emails = 0
    
    print("\n" + "-" * 100)
    print("EMAIL ANALYSIS:")
    print("-" * 100)
    
    for i, person in enumerate(people, 1):
        name = person.get('name', 'N/A')
        email = person.get('email', 'N/A')
        email_status = person.get('email_status', 'N/A')
        title = person.get('title', 'N/A')
        org = person.get('organization', {})
        company = person.get('organization_name') or org.get('name', 'N/A')
        
        # Analyze email
        is_locked = 'email_not_unlocked' in str(email)
        is_real = email != 'N/A' and not is_locked
        
        if email_status == 'verified' and is_real:
            verified_count += 1
            real_emails += 1
            status_icon = "✅"
        elif is_locked:
            locked_count += 1
            status_icon = "🔒"
        elif email_status == 'unavailable':
            unavailable_count += 1
            status_icon = "❌"
        else:
            status_icon = "⚠️"
            if is_real:
                real_emails += 1
        
        print(f"\n{status_icon} Person {i}:")
        print(f"   Name: {name}")
        print(f"   Email: {email}")
        print(f"   Email Status: {email_status}")
        print(f"   Title: {title}")
        print(f"   Company: {company}")
    
    print("\n" + "-" * 100)
    print("SUMMARY:")
    print("-" * 100)
    print(f"   ✅ Verified & Unlocked: {verified_count}")
    print(f"   🔒 Locked (email_not_unlocked): {locked_count}")
    print(f"   ❌ Unavailable: {unavailable_count}")
    print(f"   📧 Real Emails (not locked): {real_emails}")
    print(f"   📊 Total: {len(people)}")
    
    if locked_count == len(people):
        print("\n⚠️  ALL EMAILS ARE LOCKED!")
        print("   → This could mean:")
        print("   1. Your Apollo plan doesn't include email access")
        print("   2. Property Managers in Texas don't have verified emails")
        print("   3. Industry has low email coverage")
    
    if real_emails > 0:
        print(f"\n✅ Good news: {real_emails} leads have real emails!")
        print("   → Your API can access emails")

if __name__ == "__main__":
    test_apollo_api()

