#!/usr/bin/env python3
"""
Test Apollo.io API to unlock emails
"""
import subprocess
import json

API_KEY = "DtdKb5hTo_9GTtbohlNJ-Q"

def test_unlock_email():
    """Test different Apollo.io unlock endpoints"""
    
    print("=" * 100)
    print("TESTING APOLLO.IO EMAIL UNLOCK")
    print("=" * 100)
    print()
    
    # First, get a contact ID from search
    print("Step 1: Getting a contact with locked email...")
    search_url = "https://api.apollo.io/v1/mixed_people/search"
    search_payload = {
        "page": 1,
        "per_page": 1,
        "email_status": ["verified"]
    }
    
    result = curl_request("POST", search_url, search_payload)
    if not result or "people" not in result or len(result["people"]) == 0:
        print("❌ No contacts found")
        return
    
    person = result["people"][0]
    person_id = person.get("id")
    person_name = person.get("name")
    person_email = person.get("email")
    
    print(f"✅ Found contact: {person_name}")
    print(f"   ID: {person_id}")
    print(f"   Email: {person_email}")
    print()
    
    # Try different unlock methods
    print("Step 2: Testing unlock methods...")
    print()
    
    # Method 1: People Match/Enrich
    print("Method 1: People Match/Enrich API")
    print("-" * 100)
    match_url = "https://api.apollo.io/v1/people/match"
    match_payload = {
        "first_name": person.get("first_name"),
        "last_name": person.get("last_name"),
        "organization_name": person.get("organization", {}).get("name") if person.get("organization") else None
    }
    
    match_result = curl_request("POST", match_url, match_payload)
    if match_result:
        if "person" in match_result:
            unlocked_email = match_result["person"].get("email")
            print(f"✅ Match API Response:")
            print(f"   Email: {unlocked_email}")
            if "email_not_unlocked" not in unlocked_email:
                print(f"   🎉 EMAIL UNLOCKED!")
            else:
                print(f"   ❌ Still locked")
        else:
            print(f"   Response: {json.dumps(match_result, indent=2)[:500]}")
    else:
        print("❌ Match API failed")
    
    print()
    
    # Method 2: People Enrichment
    print("Method 2: People Enrichment API")
    print("-" * 100)
    enrich_url = f"https://api.apollo.io/v1/people/{person_id}/enrich"
    enrich_result = curl_request("GET", enrich_url, None)
    if enrich_result:
        print(f"✅ Enrich API Response:")
        print(json.dumps(enrich_result, indent=2)[:500])
    else:
        print("❌ Enrich API failed")
    
    print()
    
    # Method 3: Direct person lookup
    print("Method 3: Direct Person Lookup")
    print("-" * 100)
    lookup_url = f"https://api.apollo.io/v1/people/{person_id}"
    lookup_result = curl_request("GET", lookup_url, None)
    if lookup_result:
        if "person" in lookup_result:
            unlocked_email = lookup_result["person"].get("email")
            print(f"✅ Lookup API Response:")
            print(f"   Email: {unlocked_email}")
            if "email_not_unlocked" not in unlocked_email:
                print(f"   🎉 EMAIL UNLOCKED!")
            else:
                print(f"   ❌ Still locked - may need to unlock via dashboard")
        else:
            print(f"   Response: {json.dumps(lookup_result, indent=2)[:500]}")
    else:
        print("❌ Lookup API failed")
    
    print()
    print("=" * 100)
    print("💡 NOTE: If emails are still locked, you may need to:")
    print("   1. Unlock via Apollo.io dashboard (web UI)")
    print("   2. Use Apollo.io's bulk unlock feature")
    print("   3. Check if your plan includes auto-unlock for verified emails")
    print("=" * 100)

def curl_request(method, url, payload):
    """Make curl request"""
    try:
        headers = [
            "-H", "Content-Type: application/json",
            "-H", f"X-Api-Key: {API_KEY}"
        ]
        
        cmd = ["curl", "-s", "-X", method, url] + headers
        
        if payload:
            cmd += ["-d", json.dumps(payload)]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        else:
            print(f"   Error: {result.stderr or result.stdout}")
            return None
    except Exception as e:
        print(f"   Exception: {e}")
        return None

if __name__ == "__main__":
    test_unlock_email()

