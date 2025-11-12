# HTTP Module Setup - Complete Step-by-Step Guide

## 📋 Fill Out Each Field

---

### ✅ Step 1: URL Field

**Location:** "URL *" (required field, currently has purple border)

**What to enter:**
```
https://api.apollo.io/v1/mixed_people/search
```

**OR just the path:**
```
/v1/mixed_people/search
```

**Important:** NO trailing slash (`/`) at the end!

---

### ✅ Step 2: Method

**Location:** "Method *" dropdown (currently shows "GET")

**What to do:**
1. Click the dropdown
2. Select: **"POST"**
3. (Keep "Map" toggle OFF)

**Why:** Apollo.io search requires POST to send body data.

---

### ✅ Step 3: Headers

**Location:** "Headers" section (has "+ Add a header" link)

**What to do:**
1. Click **"+ Add a header"**
2. A new row appears with "Name" and "Value" fields
3. **Name field:** Type `Content-Type`
4. **Value field:** Type `application/json`
5. Click outside to confirm

**Note:** The `X-Api-Key` header for authentication will be handled separately (see Step 9).

---

### ✅ Step 4: Query String

**Location:** "Query String" section

**What to do:**
- **Leave this EMPTY** ✅
- Don't add anything here
- (We're sending data in the body, not query parameters)

---

### ✅ Step 5: Body Type

**Location:** "Body type" dropdown (currently empty)

**What to do:**
1. Click the dropdown
2. Select: **"Raw"**
3. A text area will appear below it - this is where you paste JSON

---

### ✅ Step 6: Body (JSON)

**Location:** Text area that appears after selecting "Raw" body type

**What to paste:**
Copy and paste this EXACT JSON:

```json
{
  "q_keywords": "homeowner property owner",
  "person_titles": [
    "Property Manager",
    "Real Estate Agent",
    "Real Estate Developer",
    "Construction Manager",
    "Homeowner",
    "Property Owner"
  ],
  "person_locations": [
    "Arizona",
    "California",
    "Florida",
    "Texas",
    "Nevada"
  ],
  "organization_industries": [
    "Real Estate",
    "Construction",
    "Property Management",
    "Home Services"
  ],
  "page": 1,
  "per_page": 1
}
```

**Important:**
- Make sure all quotes are straight (`"`), not curly (`"`)
- No extra spaces or characters
- Valid JSON format

---

### ✅ Step 7: Parse Response

**Location:** "Parse response" section (currently shows "No" selected)

**What to do:**
1. Select: **"Yes"** ✅
2. This allows Make.com to automatically parse the JSON response

**Why:** This makes the data accessible to subsequent modules (like OpenAI).

---

### ✅ Step 8: Advanced Settings

**Location:** "Advanced settings" toggle

**What to do:**
- **Leave it OFF** (unless you have specific needs)

---

### ✅ Step 9: API Authentication

**Important:** This HTTP module needs Apollo.io API key authentication.

**Option A: Use "Make an API Key Auth request" Module Instead**
- This HTTP module might not handle API key automatically
- Better option: Use **"HTTP - Make an API Key Auth request"** module
- That module has dedicated "API Key" field for authentication

**Option B: Add API Key to Headers Manually**
1. Click **"+ Add a header"** again
2. **Name:** `X-Api-Key`
3. **Value:** Your Apollo.io API key
   - Get it from: https://app.apollo.io/settings/integrations → API
   - Should be alphanumeric string (30-50 characters)

---

### ✅ Step 10: Evaluate All States as Errors

**Location:** Top section with toggle and radio buttons

**Current:** "Yes" is selected

**What to do:**
- **Keep "Yes" selected** ✅
- This ensures errors (401, 403, 404) will fail the module, making debugging easier

---

### ✅ Step 11: Save

**Location:** Bottom buttons

**What to do:**
1. Review all fields
2. Click **"Save"** button (purple, bottom right)

---

## 📋 Quick Checklist

Before saving, verify:

- [ ] **URL:** `https://api.apollo.io/v1/mixed_people/search` or `/v1/mixed_people/search`
- [ ] **Method:** `POST` (not GET)
- [ ] **Headers:** `Content-Type: application/json` added
- [ ] **Headers:** `X-Api-Key: [your-api-key]` added (OR use API Key Auth module)
- [ ] **Query String:** Empty
- [ ] **Body Type:** `Raw`
- [ ] **Body:** JSON with HELOC search criteria pasted
- [ ] **Parse Response:** `Yes`
- [ ] **Advanced Settings:** Off
- [ ] **Evaluate Errors:** Yes

---

## ⚠️ Important Notes

1. **API Key:** Make sure you add `X-Api-Key` header OR use "Make an API Key Auth request" module
2. **Paid Plan Required:** `/v1/mixed_people/search` requires paid Apollo.io plan ($49+/month)
3. **Free Plan:** Won't work - use webhook version instead
4. **JSON Format:** Make sure body is valid JSON (no syntax errors)

---

## 🚀 After Saving

1. **Test the module:**
   - Click "Run once" or run the scenario
   - Should return **200** status (not 401, 403, or 404)
   - Response should have `people[]` array

2. **If errors:**
   - **401:** Invalid API key → Update API key
   - **403:** Free plan → Upgrade Apollo.io
   - **404:** Wrong URL or endpoint not available → Check URL format

---

**Fill out all fields above and click Save!**

