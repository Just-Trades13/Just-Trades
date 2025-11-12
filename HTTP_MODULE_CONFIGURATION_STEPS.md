# 📋 HTTP Module Configuration - Step by Step

Based on your HTTP module screen, here's exactly what to do:

---

## ✅ Step-by-Step Configuration

### Step 1: Change Method to POST

1. **Click on "Method" dropdown** (currently shows "GET")
2. **Select "POST"** from the dropdown

**Why**: Apollo.io API requires POST method for searching people.

---

### Step 2: Add Headers

1. **Click the purple "+ Add a header" link** (under Headers section)
2. **Add Header 1**:
   - **Name**: `Content-Type`
   - **Value**: `application/json`
   - Click "OK" or checkmark

3. **Click "+ Add a header" again**
4. **Add Header 2**:
   - **Name**: `X-Api-Key`
   - **Value**: `YOUR_APOLLO_API_KEY` (paste your actual Apollo.io API key here)
   - Get API key: Apollo.io → Settings → Integrations → API → Connect → Copy
   - Click "OK" or checkmark

**You should now have 2 headers.**

---

### Step 3: Set Body Type

1. **Click on "Body type" dropdown** (currently empty)
2. **Select "JSON"** from the dropdown

---

### Step 4: Add Request Body (JSON)

After selecting "JSON" as body type, you should see a text box appear.

**Paste this JSON** into the body field:

```json
{
  "q_keywords": "homeowner property owner",
  "person_titles": ["Property Manager", "Real Estate Agent", "Homeowner"],
  "person_locations": ["Arizona", "California", "Florida", "Texas", "Nevada"],
  "organization_industries": ["Real Estate", "Construction", "Property Management"],
  "page": 1,
  "per_page": 1
}
```

---

### Step 5: Enable Parse Response (Important!)

1. **Click the radio button for "Yes"** (under "Parse response")
   - Currently "No" is selected - change it to "Yes"

**Why**: This automatically parses Apollo.io's JSON response so you can access `body.people[0]` easily.

---

### Step 6: Configure Advanced Settings (Optional)

1. **Toggle "Advanced settings"** ON (if you want to customize timeout, etc.)
   - Usually not needed - leave it OFF for now

---

### Step 7: Save

1. **Click the purple "Save" button** (bottom right)

---

## ✅ Final Configuration Summary

Your HTTP module should have:

- ✅ **URL**: `https://api.apollo.io/v1/mixed_people/search`
- ✅ **Method**: **POST** (changed from GET)
- ✅ **Headers**: 
  - `Content-Type: application/json`
  - `X-Api-Key: YOUR_API_KEY`
- ✅ **Body type**: **JSON**
- ✅ **Body**: JSON with search criteria (pasted above)
- ✅ **Parse response**: **Yes**

---

## 🧪 Test It

1. **Click "Save"**
2. **Click "Run once"** button (top of Make.com)
3. **Check Module 1 output**:
   - Should show Apollo.io API response
   - Should have `people` array with contact data
   - Status should be 200 (success)

---

## 🔍 What to Check After Running

1. **Click on HTTP module** after it runs
2. **View "Output"** or "Data structure"
3. **You should see**:
   ```json
   {
     "people": [
       {
         "first_name": "...",
         "email": "...",
         "city": "...",
         ...
       }
     ]
   }
   ```

4. **If you see this structure**: ✅ Good! Move to next step
5. **If you see errors**: Check API key and try again

---

## ⚠️ Common Issues

### Error: "401 Unauthorized"
- **Problem**: Wrong API key
- **Fix**: Double-check your Apollo.io API key

### Error: "403 Forbidden"
- **Problem**: Your Apollo.io plan doesn't include People Search API
- **Fix**: Upgrade Apollo.io plan

### Error: "No results"
- **Problem**: Search criteria too restrictive
- **Fix**: Remove some filters or make keywords broader

### Wrong Method Error
- **Problem**: Still set to GET instead of POST
- **Fix**: Change Method dropdown to POST

---

## 📝 Next Steps After HTTP Module Works

Once HTTP module returns data:

1. ✅ **Module 2 (OpenAI)** should automatically receive the data
2. ✅ **Verify OpenAI User Message** is: `{{`1.body.people[0]`}}`
   - If not, update it
3. ✅ **Run full scenario** to test end-to-end
4. ✅ **Check Airtable** for new lead with HELOC fields

---

**Follow these exact steps and your HTTP module will call Apollo.io API successfully!**

