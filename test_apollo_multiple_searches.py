import requests
import json

api_key = "DtdKb5hTo_9GTtbohlNJ-Q"
url = "https://api.apollo.io/v1/mixed_people/search"
headers = {
    "Content-Type": "application/json",
    "X-Api-Key": api_key
}

print("🔍 TESTING APOLLO.IO - Multiple Searches\n")
print("=" * 100)
print()

# Test 1: California
print("TEST 1: California")
payload1 = {
    "person_locations": ["California"],
    "page": 1,
    "per_page": 5
}
response1 = requests.post(url, headers=headers, data=json.dumps(payload1))
data1 = response1.json()
people1 = data1.get("people", [])
print(f"Results: {len(people1)} people")
if people1:
    print(f"First person: {people1[0].get('first_name', 'N/A')} {people1[0].get('last_name', 'N/A')} - {people1[0].get('organization', {}).get('name', 'N/A')}")
    print(f"Email: {people1[0].get('email', 'N/A')}")
print()

# Test 2: Texas
print("TEST 2: Texas")
payload2 = {
    "person_locations": ["Texas"],
    "page": 1,
    "per_page": 5
}
response2 = requests.post(url, headers=headers, data=json.dumps(payload2))
data2 = response2.json()
people2 = data2.get("people", [])
print(f"Results: {len(people2)} people")
if people2:
    print(f"First person: {people2[0].get('first_name', 'N/A')} {people2[0].get('last_name', 'N/A')} - {people2[0].get('organization', {}).get('name', 'N/A')}")
    print(f"Email: {people2[0].get('email', 'N/A')}")
print()

# Test 3: Florida
print("TEST 3: Florida")
payload3 = {
    "person_locations": ["Florida"],
    "page": 1,
    "per_page": 5
}
response3 = requests.post(url, headers=headers, data=json.dumps(payload3))
data3 = response3.json()
people3 = data3.get("people", [])
print(f"Results: {len(people3)} people")
if people3:
    print(f"First person: {people3[0].get('first_name', 'N/A')} {people3[0].get('last_name', 'N/A')} - {people3[0].get('organization', {}).get('name', 'N/A')}")
    print(f"Email: {people3[0].get('email', 'N/A')}")
print()

# Test 4: No filters (maximum results)
print("TEST 4: No Filters (Maximum)")
payload4 = {
    "page": 1,
    "per_page": 5
}
response4 = requests.post(url, headers=headers, data=json.dumps(payload4))
data4 = response4.json()
people4 = data4.get("people", [])
print(f"Results: {len(people4)} people")
if people4:
    print(f"First person: {people4[0].get('first_name', 'N/A')} {people4[0].get('last_name', 'N/A')} - {people4[0].get('organization', {}).get('name', 'N/A')}")
    print(f"Email: {people4[0].get('email', 'N/A')}")
print()

# Test 5: Different page (California)
print("TEST 5: California Page 2")
payload5 = {
    "person_locations": ["California"],
    "page": 2,
    "per_page": 5
}
response5 = requests.post(url, headers=headers, data=json.dumps(payload5))
data5 = response5.json()
people5 = data5.get("people", [])
print(f"Results: {len(people5)} people")
if people5:
    print(f"First person: {people5[0].get('first_name', 'N/A')} {people5[0].get('last_name', 'N/A')} - {people5[0].get('organization', {}).get('name', 'N/A')}")
    print(f"Email: {people5[0].get('email', 'N/A')}")
print()

print("=" * 100)
print("\n📊 COMPARISON:")
print()

# Check if all first people are the same
emails = []
if people1:
    emails.append(people1[0].get('email', 'N/A'))
if people2:
    emails.append(people2[0].get('email', 'N/A'))
if people3:
    emails.append(people3[0].get('email', 'N/A'))
if people4:
    emails.append(people4[0].get('email', 'N/A'))
if people5:
    emails.append(people5[0].get('email', 'N/A'))

if len(set(emails)) == 1:
    print("❌ ALL SEARCHES RETURN SAME EMAIL!")
    print(f"   Email: {emails[0]}")
    print("\n   This means Apollo.io is either:")
    print("   1. Returning cached results")
    print("   2. Only has one matching lead in database")
    print("   3. API plan limitation (free plan might only return one lead)")
    print("   4. Search criteria too restrictive")
else:
    print("✅ Different searches return different emails!")
    print(f"   Unique emails: {len(set(emails))}")

