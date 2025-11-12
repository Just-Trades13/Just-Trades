# Add Apollo.io API Key to HTTP Module

## ✅ Your API Key
```
DtdKb5hTo_9GTtbohlNJ-Q
```

---

## 🔧 Add to HTTP Module

### Option 1: Add as Header (Recommended for HTTP Module)

1. **In your HTTP module in Make.com:**
   - Go to **"Headers"** section
   - Click **"+ Add a header"**

2. **Add API Key header:**
   - **Name:** `X-Api-Key`
   - **Value:** `DtdKb5hTo_9GTtbohlNJ-Q`
   - Click outside to confirm

3. **You should now have TWO headers:**
   - `Content-Type: application/json`
   - `X-Api-Key: DtdKb5hTo_9GTtbohlNJ-Q`

4. **Save the module**

---

### Option 2: Use "Make an API Key Auth request" Module

If you want a cleaner setup:

1. **Replace your current HTTP module** with:
   - Search: **"HTTP - Make an API Key Auth request"**

2. **Configure:**
   - **URL:** `https://api.apollo.io/v1/mixed_people/search`
   - **Method:** `POST`
   - **API Key:** `DtdKb5hTo_9GTtbohlNJ-Q`
   - **Header Name:** `X-Api-Key`
   - **Body Type:** `Raw`
   - **Body:** Your JSON (same as before)
   - **Parse Response:** `Yes`

3. **This module handles authentication automatically**

---

## 🧪 How to Test

### Test 1: Run the Scenario

1. **Click "Save" on your HTTP module**
2. **Run the scenario manually** (click "Run once")
3. **Check the output:**
   - ✅ **200 status** = Success! API key works
   - ❌ **401** = Invalid API key
   - ❌ **403** = Free plan (endpoint requires paid)
   - ❌ **404** = Wrong URL or endpoint not available

### Test 2: Check Response

If you get **200 status**, the response should have:
```json
{
  "people": [
    {
      "first_name": "...",
      "last_name": "...",
      "email": "...",
      ...
    }
  ]
}
```

---

## ⚠️ Important Security Note

**You've shared your API key publicly!** 

**After you're done setting this up:**

1. **Go to Apollo.io:**
   - https://app.apollo.io/settings/integrations → API
   - **Delete or regenerate** this API key
   - **Create a new one** for security

2. **Update Make.com** with the new key

3. **Keep API keys private** - never share them publicly

---

## 📋 Complete HTTP Module Configuration

With your API key, your HTTP module should have:

| Field | Value |
|-------|-------|
| **URL** | `https://api.apollo.io/v1/mixed_people/search` |
| **Method** | `POST` |
| **Headers** | `Content-Type: application/json` |
| **Headers** | `X-Api-Key: DtdKb5hTo_9GTtbohlNJ-Q` |
| **Body Type** | `Raw` |
| **Body** | JSON with HELOC search criteria |
| **Parse Response** | `Yes` |

---

## 🚀 Next Steps

1. **Add the API key header** to your HTTP module
2. **Save** the module
3. **Run the scenario** to test
4. **Check for 200 status** in the output
5. **If it works** → Continue with Module 2 (OpenAI)
6. **Regenerate API key** for security

---

**Once the API key is added, your HTTP module should work!**

