# 🚀 HTTP Module Setup Steps for Nelson HELOC

## ✅ What's Changed

Your blueprint now has **HTTP module** (Module 1) instead of webhook!

**File**: `Nelson_HELOC_Blueprint.json`

---

## 📋 After Importing - Quick Setup

### Step 1: Import Blueprint

1. Make.com → Scenarios → Create new scenario
2. Click "Import"
3. Upload `Nelson_HELOC_Blueprint.json`
4. Click "Import"

**⚠️ If you see "Module Not Found" for HTTP module**, see troubleshooting below.

---

### Step 2: Add Your Apollo.io API Key

1. **Click on Module 1** (HTTP module)

2. **Find Headers section**

3. **Edit Header 2** (X-Api-Key):
   - Current value: (empty)
   - **Change to**: Your Apollo.io API key
   - Get API key: Apollo.io → Settings → Integrations → API → Connect → Copy key

4. **Click "OK"**

---

### Step 3: Configure Search Criteria (Optional)

The HTTP module is already pre-configured with HELOC search criteria:

**Current settings:**
- Keywords: "homeowner property owner"
- Person Titles: Property Manager, Real Estate Agent, etc.
- Locations: Arizona, California, Florida, Texas, Nevada
- Industries: Real Estate, Construction, Property Management

**To customize:**
1. Click on Module 1 (HTTP module)
2. Find "Body" section
3. Edit the JSON to change search criteria
4. Click "OK"

---

### Step 4: Test It

1. **Click "Run once"** button
2. **Check Module 1 output**:
   - Should return Apollo.io API response
   - Should have `people` array with contact data
3. **Check Module 2 (OpenAI)**:
   - Should extract first_name, property_city, etc.
4. **Check Airtable**:
   - Lead should be created with HELOC fields

---

## ⚠️ If HTTP Module Shows "Module Not Found"

If Make.com doesn't recognize the HTTP module after import:

### Option 1: Try Different HTTP Module Names

The module might be named:
- `http:MakeARequest`
- `http:Request`
- `tools:HttpRequest`
- Just "HTTP" or "Make a Request"

### Option 2: Manual Setup

1. **Delete the HTTP module** (if it says "Not Found")
2. **Click "+"** → Search **"HTTP"**
3. **Select "Make a Request"** (or similar)
4. **Configure manually**:
   - Method: POST
   - URL: `https://api.apollo.io/v1/mixed_people/search`
   - Add headers (Content-Type, X-Api-Key)
   - Add body (JSON with search criteria)
5. **Connect** to Module 2 (OpenAI)
6. **Update OpenAI User Message**: `{{`1.body.people[0]`}}`

---

## 📊 What the HTTP Module Does

The HTTP module:
1. **Calls Apollo.io API** directly
2. **Searches for HELOC prospects** using your criteria
3. **Returns person data** in `body.people[]` array
4. **Sends to OpenAI** for processing

**API Endpoint**: `https://api.apollo.io/v1/mixed_people/search`  
**Method**: POST  
**Response**: `{ "people": [...], "pagination": {...} }`

---

## ✅ Success Indicators

After setup:
- ✅ HTTP module connects to Apollo.io API
- ✅ Returns person data (check Module 1 output)
- ✅ OpenAI extracts HELOC fields correctly
- ✅ Lead created in Airtable with:
  - First Name
  - Property City
  - Referral Link
  - Channel = "email"
  - Source = "apollo_io"

---

## 🔧 Troubleshooting

### API Key Error:
- Verify API key is correct
- Check paid Apollo.io plan (API requires paid tier)

### No Results:
- Make search criteria less restrictive
- Check Apollo.io API credits/quota

### Wrong Data Path:
- Check HTTP module output structure
- Adjust OpenAI user message if needed (currently: `{{`1.body.people[0]`}}`)

---

**The blueprint is ready - just add your Apollo.io API key and you're good to go!**

