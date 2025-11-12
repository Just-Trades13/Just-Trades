# 🔍 Apollo.io Module Selection Guide for Make.com

## The Problem

Make.com doesn't recognize `apollo-io:SearchPeople`. You need to identify which Apollo.io module Make.com actually supports for searching/listing people.

---

## 🎯 Solution Options

### Option 1: Use HTTP Module (Recommended - Most Reliable)

**File**: `Scenario A - HELOC Lead Capture (Apollo.io HTTP).blueprint.json`

✅ **Pros:**
- Always works (HTTP module is standard in Make.com)
- Direct API access - no module compatibility issues
- Full control over Apollo.io API calls
- No dependency on Make.com's Apollo.io module availability

❌ **Cons:**
- Requires manual API key configuration
- Need to set headers manually

**Setup:**
1. Import the HTTP blueprint
2. Module 1 will be `http:MakeARequest`
3. Configure:
   - **URL**: `https://api.apollo.io/v1/mixed_people/search`
   - **Method**: POST
   - **Headers**: 
     - `Content-Type: application/json`
     - `X-Api-Key: YOUR_APOLLO_API_KEY`
   - **Body** (JSON):
     ```json
     {
       "q_keywords": "homeowner property owner",
       "person_titles": ["Property Manager", "Real Estate Agent"],
       "person_locations": ["Los Angeles, CA", "Phoenix, AZ"],
       "organization_industries": ["Real Estate", "Construction"],
       "page": 1,
       "per_page": 1
     }
     ```

---

### Option 2: Try Native Apollo.io Modules

Make.com has Apollo.io modules, but the exact module name varies. Try these:

#### Common Apollo.io Module Names:

1. **`apollo-io:ListPeople`** ← Most likely
   - File: `Scenario A - HELOC (apollo-io:ListPeople).blueprint.json`
   
2. **`apollo-io:SearchContacts`**
   - File: `Scenario A - HELOC (apollo-io:SearchContacts).blueprint.json`

3. **`apollo-io:FindPeople`**

4. **`apollo-io:SearchPeople`** (original - doesn't work)

5. **`apollo:ListPeople`** (without "io" suffix)

---

## 🔎 How to Find the Correct Module Name

### Method 1: Check Make.com UI

1. Go to Make.com → Create New Scenario
2. Click **"Add module"**
3. Search for **"Apollo"** or **"Apollo.io"**
4. Look at available modules:
   - What's the exact name?
   - Does it say "List People", "Search People", "Find People", "Search Contacts"?

### Method 2: Check Module Library

1. Make.com → **Integrations** → Search **"Apollo.io"**
2. View available actions/triggers
3. Look for modules related to **People** or **Contacts**

### Method 3: Try Importing Each Version

1. Import `Scenario A - HELOC (apollo-io:ListPeople).blueprint.json`
2. If it fails, try `Scenario A - HELOC (apollo-io:SearchContacts).blueprint.json`
3. If both fail, use **HTTP module version** (Option 1)

---

## 📋 Apollo.io Module Configuration

Once you identify the correct module name, configure it:

### Common Configuration Fields:

- **Connection**: Your Apollo.io API key
- **Page**: 1
- **Per Page**: 1 (one lead at a time)
- **Person Titles**: `["Property Manager", "Real Estate Agent", "Homeowner"]`
- **Person Locations**: `["Los Angeles, CA", "Phoenix, AZ", "Miami, FL"]`
- **Organization Industries**: `["Real Estate", "Construction", "Property Management"]`
- **Keywords** (`q_keywords`): `"homeowner property owner"`

---

## 🛠️ Manual Setup After Import

If Apollo.io module still doesn't work:

1. **Delete the Apollo.io module** from the imported scenario
2. **Add HTTP module** manually:
   - Click "+" → Search "HTTP" → "Make a Request"
   - Configure as shown in Option 1 above
3. **Connect to Module 2** (OpenAI)

---

## 🧪 Testing

### Test HTTP Module:
1. Run scenario once
2. Check Module 1 output:
   - Should return `{ "people": [...], "pagination": {...} }`
3. Verify `1.body.people[0]` contains person data

### Test Apollo.io Module:
1. Run scenario once
2. Check Module 1 output:
   - Should have `people` array
3. Verify `1.people[0]` contains person data

---

## 📝 Which Module to Use?

| Situation | Recommended Solution |
|-----------|---------------------|
| You want reliability | **HTTP Module** (Option 1) |
| You found "List People" module | Use `apollo-io:ListPeople` version |
| You found "Search Contacts" module | Use `apollo-io:SearchContacts` version |
| No Apollo.io modules found | **HTTP Module** (Option 1) |
| Module import fails | **HTTP Module** (Option 1) |

---

## 🔧 Quick Fix: Update Module Name After Import

If you import a blueprint and the module name is wrong:

1. **Open the scenario** in Make.com
2. **Click on Module 1** (Apollo.io module)
3. If it shows "Module Not Found":
   - **Delete Module 1**
   - **Click "+"** → Search "Apollo"
   - **Select the correct Apollo.io module** (List People, Search Contacts, etc.)
   - **Configure** with your search criteria
   - **Connect** to Module 2

The rest of the flow (AI processing, Airtable) will work automatically!

---

## ✅ Recommended Approach

**Start with HTTP Module** (most reliable):
- ✅ Always works
- ✅ Direct API access
- ✅ No module compatibility issues
- ✅ Full control over requests

**Then try Apollo.io native modules** if you want UI-based configuration:
- ⚠️ May not be available in all Make.com plans
- ⚠️ Module names vary
- ✅ Easier configuration (if it works)

---

## 📞 Next Steps

1. **Import HTTP version** first (most reliable)
2. **If you prefer native Apollo.io module**: Check Make.com UI for available modules
3. **Update the blueprint** with the correct module name
4. **Configure search criteria** for HELOC prospects
5. **Test** with a single run

---

**Tip**: The HTTP module version will definitely work - start there if Apollo.io native modules are causing issues!

