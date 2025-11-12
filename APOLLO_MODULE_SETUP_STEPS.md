# Apollo.io Module Setup - Step by Step

## 📋 What You're Setting Up

You're configuring the Apollo.io API call to search for HELOC leads. This is **Module 1** in your scenario.

---

## ✅ Step-by-Step Configuration

### Step 1: Connection ✅ (Already Done!)
- **Connection:** "My Apollo connection" ✅
- **Verify:** Click "Add" next to connection if you need to update your API key
- **Get API key from:** https://app.apollo.io/settings/integrations → API

---

### Step 2: URL Configuration

1. **Find the "URL" field** (required, currently empty)
2. **Enter this EXACT path:**
   ```
   /v1/mixed_people/search
   ```
3. **Or enter the full URL:**
   ```
   https://api.apollo.io/v1/mixed_people/search
   ```
4. **Note:** Make.com will automatically prepend `https://api.apollo.io/` if you just use the path

---

### Step 3: Method Configuration

1. **Find the "Method" dropdown** (currently shows "GET")
2. **Change it to:** `POST`
3. **Reason:** Apollo.io search requires POST method to send search criteria

---

### Step 4: Headers (Already Set ✅)

You already have:
- **Key:** `Content-Type`
- **Value:** `application/json`

**✅ Keep this as is!** Don't change it.

---

### Step 5: Body Configuration (CRITICAL!)

1. **Find the "Body" section** (currently empty)
2. **Click in the text area**
3. **Paste this EXACT JSON:**

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

4. **Make sure:**
   - No extra spaces
   - Valid JSON format
   - All quotes are straight quotes (`"`), not curly quotes (`"`)

---

### Step 6: Save

1. **Click "Save" button** (bottom right)
2. **The module should now be configured**

---

## 🔍 Verification Checklist

After saving, verify:

- [ ] **Connection:** "My Apollo connection" is selected
- [ ] **URL:** `/v1/mixed_people/search` or full URL
- [ ] **Method:** `POST` (not GET)
- [ ] **Headers:** `Content-Type: application/json`
- [ ] **Body:** JSON with HELOC search criteria
- [ ] **Module shows green checkmark** ✅

---

## ⚠️ Important Notes

1. **API Key:** Make sure your Apollo.io connection has a valid API key
   - Requires **paid Apollo.io plan** ($49+/month)
   - Free plan won't work with `/v1/mixed_people/search`

2. **If you have free plan:** Use `Nelson_HELOC_Webhook_Blueprint.json` instead

3. **Test the module:**
   - Click "Run once" or run the scenario
   - Should return 200 status (not 401 or 403)
   - Response should have `people[]` array

---

## 🚀 Next Steps

After configuring Module 1:

1. **Module 2 (OpenAI):** Already configured, just verify connection
2. **Module 3 (Parse JSON):** Should work automatically
3. **Module 4-5 (Airtable):** Should work if previous modules succeed

---

**Once saved, test by running the scenario!**

