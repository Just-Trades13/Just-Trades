# ✅ COMPLETE SETUP: Apollo.io "Make an API Call" Module

## 🎯 SOLUTION

Use **Apollo.io → OTHER → "Make an API Call"** to call the search endpoint directly!

This will work because it uses Apollo.io's native authentication.

---

## 📋 STEP-BY-STEP SETUP

### Step 1: Replace Module 18

1. **Delete the current Module 18** (HTTP module)
2. **Click "+" to add a new module**
3. **Search**: `Apollo`
4. **Select**: `Apollo.io` (the verified one with purple checkmark)
5. **Go to**: `OTHER` section
6. **Select**: `Make an API Call`
7. **Position**: As Module 1 (first module in flow)

---

### Step 2: Configure Apollo.io Connection

When you add the module, it will ask for:

**Connection:**
- Click "Add" or select existing Apollo.io connection
- **Authentication**: API Key
- **API Key**: `DtdKb5hTo_9GTtbohlNJ-Q`
- **Save connection**

---

### Step 3: Configure "Make an API Call" Module

**After connection is set:**

**API Call Configuration:**

**Method:** `POST`

**URL:** `/v1/mixed_people/search`
(Don't include `https://api.apollo.io` - just the path)

**Query String:** (Leave empty)

**Body Type:** `JSON`

**Body:**
```json
{
  "person_locations": ["California"],
  "page": 1,
  "per_page": 1
}
```

**Headers:** (Usually auto-filled by Apollo.io module)
- `Content-Type: application/json`
- `X-Api-Key: DtdKb5hTo_9GTtbohlNJ-Q` (may be auto-added)

**Parse Response:** `Yes` (if option exists)

---

### Step 4: Update Module 2 (OpenAI)

**The output structure will be different!**

**Module 18 Output Structure (Apollo.io module):**
```
Module 1 (Apollo.io):
  - people: [...]
  - pagination: {...}
```

**Update Module 2 User Message:**

**OLD:** `{{`18.data.people[0]`}}`  
**NEW:** `{{`1.people[0]`}}`

Or try:
```
{{`1.body.people[0]`}}
```

**If that doesn't work, try sending the entire response:**
```
{{`1`}}
```

---

## 🧪 TEST STEPS

1. **Run Module 1 only** (the Apollo.io module)
2. **Check output bundle:**
   - Look for `people` array
   - Note the exact structure
3. **Update Module 2** with correct path
4. **Test full flow**

---

## 🔍 TROUBLESHOOTING

### Issue: "Module Not Found" or Error

**Fix:**
- Make sure you selected `Apollo.io` (with .io)
- Not "Apollo" or "Apollo GraphQL"
- Should have purple "Verified" checkmark

### Issue: API Key Authentication Error

**Fix:**
- Go to Apollo.io → Settings → Integrations → API
- Generate a new API key if needed
- Make sure it's active

### Issue: Data Path Wrong

**Fix:**
1. Run Module 1
2. Click on output bundle
3. Find where `people` array is located
4. Update Module 2 to match exact path

**Common paths:**
- `{{`1.people[0]`}}`
- `{{`1.body.people[0]`}}`
- `{{`1.data.people[0]`}}`
- `{{`1.response.people[0]`}}`

---

## 📊 EXPECTED OUTPUT STRUCTURE

**Apollo.io "Make an API Call" typically returns:**

```json
{
  "people": [
    {
      "first_name": "John",
      "last_name": "Smith",
      "email": "john@example.com",
      "title": "Real Estate Agent",
      "organization_name": "ABC Real Estate",
      "city": "Los Angeles",
      "state": "CA",
      "phone_numbers": [...],
      "linkedin_url": "..."
    }
  ],
  "pagination": {
    "total_entries": 1000,
    "total_pages": 1000,
    "page": 1,
    "per_page": 1
  }
}
```

**Module 2 should reference:** `{{`1.people[0]`}}`

---

## ✅ CHECKLIST

- [ ] Deleted old Module 18 (HTTP module)
- [ ] Added Apollo.io "Make an API Call" module
- [ ] Configured Apollo.io connection with API key
- [ ] Set Method: POST
- [ ] Set URL: `/v1/mixed_people/search`
- [ ] Set Body with search criteria
- [ ] Tested Module 1 output
- [ ] Updated Module 2 data path
- [ ] Tested full flow

---

## 🎯 ALTERNATIVE: Try Different Search

**If `/v1/mixed_people/search` doesn't work:**

**Try:** `/v1/people/search`

**Or:** `/v1/contacts/search`

**URL would be:**
- `/v1/people/search`
- `/v1/contacts/search`

**Body format may be slightly different - check Apollo.io API docs**

---

## 💡 QUICK REFERENCE

**Module Type:** `Apollo.io → OTHER → Make an API Call`  
**Authentication:** API Key (`DtdKb5hTo_9GTtbohlNJ-Q`)  
**Method:** POST  
**URL:** `/v1/mixed_people/search`  
**Body:** JSON with search criteria  
**Output Path:** `{{`1.people[0]`}}` (usually)

---

**This should work! Apollo.io native module handles authentication automatically!** 🚀

