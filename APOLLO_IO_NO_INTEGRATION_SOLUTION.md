# ⚠️ Apollo.io Has NO Make.com Integration - Here's How to Connect It

## The Problem

**Apollo.io does NOT have a native Make.com integration.** 

Looking at Apollo.io's integrations list, I see:
- ✅ Zapier
- ✅ API
- ❌ NO Make.com

This means we need a **workaround** to connect Apollo.io to Make.com.

---

## ✅ Solution Options (Choose One)

### Option 1: Use Zapier as Bridge (Easiest)

**Zapier connects Apollo.io → Make.com**

#### Setup Steps:

1. **Connect Apollo.io to Zapier:**
   - Go to Zapier.com → Create Zap
   - **Trigger**: Apollo.io → "New Person in List" or "Person Search"
   - **Action**: Webhooks by Zapier → "POST" → Your Make.com webhook URL

2. **In Make.com:**
   - Keep the webhook module (Module 1)
   - Configure webhook to receive data from Zapier
   - Rest of flow works automatically!

3. **How It Works:**
   ```
   Apollo.io → Zapier → Make.com Webhook → OpenAI → Parse → Airtable
   ```

---

### Option 2: Use HTTP Module (Direct API Call) ⭐ Recommended

**Call Apollo.io API directly from Make.com**

#### Setup Steps:

1. **Get Apollo.io API Key:**
   - Apollo.io → Settings → Integrations → **API**
   - Click "Connect" on API
   - Copy your API key

2. **In Make.com - Delete Webhook & Add HTTP Module:**

   **Delete Module 1** (webhook)

   **Add HTTP Module**:
   - Click "+" → Search "HTTP" → "Make a Request"
   - **Method**: POST
   - **URL**: `https://api.apollo.io/v1/mixed_people/search`
   - **Headers**:
     - Header 1:
       - Name: `Content-Type`
       - Value: `application/json`
     - Header 2:
       - Name: `X-Api-Key`
       - Value: `YOUR_APOLLO_API_KEY` (paste your key here)
   - **Body Type**: JSON
   - **Body** (JSON):
   ```json
   {
     "q_keywords": "homeowner property owner",
     "person_titles": ["Property Manager", "Real Estate Agent"],
     "person_locations": ["Arizona", "California", "Florida", "Texas"],
     "organization_industries": ["Real Estate", "Construction"],
     "page": 1,
     "per_page": 1
   }
   ```

3. **Update OpenAI Module (Module 2):**
   - Click on Module 2 (OpenAI)
   - **User Message**: Change to `{{`1.body.people[0]`}}`
   - This tells OpenAI to use the person data from Apollo.io API response

4. **Connect**: HTTP Module → OpenAI → Rest of flow

---

### Option 3: Use Schedule + HTTP Module (Automated)

**Automatically search Apollo.io on a schedule**

1. **Delete webhook module**

2. **Add Schedule Module** (as Module 1):
   - Click "+" → Search "Schedule"
   - **Frequency**: Daily at 9 AM, or Weekly
   - **Time**: Your preferred time

3. **Add HTTP Module** (as Module 2):
   - Same configuration as Option 2 above
   - Connects: Schedule → HTTP → OpenAI

**Result**: Automatically searches Apollo.io daily/weekly for new HELOC leads!

---

## 🎯 Which Option Should You Use?

| Option | Difficulty | Cost | Best For |
|--------|-----------|------|----------|
| **Zapier Bridge** | Easy | Zapier plan | Quick setup, visual workflow |
| **HTTP Module** | Medium | Apollo.io API only | Direct control, no middleman |
| **Schedule + HTTP** | Medium | Apollo.io API only | Fully automated daily searches |

**Recommended**: **Option 2 (HTTP Module)** or **Option 3 (Schedule + HTTP)** for full automation.

---

## 📋 Step-by-Step: HTTP Module Setup (Recommended)

### Step 1: Get Apollo.io API Key

1. Go to Apollo.io → **Settings** → **Integrations**
2. Find **"API"** in the list
3. Click **"Connect"**
4. Copy your **API Key**

### Step 2: In Make.com - Setup HTTP Module

1. **Import** the blueprint (webhook will be there)

2. **Delete Module 1** (webhook)

3. **Add HTTP Module**:
   - Click "+" button
   - Search **"HTTP"** → Select **"Make a Request"** (or similar HTTP module)
   
4. **Configure HTTP Module**:
   
   **URL**:
   ```
   https://api.apollo.io/v1/mixed_people/search
   ```
   
   **Method**: 
   ```
   POST
   ```
   
   **Headers** (Add 2 headers):
   
   Header 1:
   - **Name**: `Content-Type`
   - **Value**: `application/json`
   
   Header 2:
   - **Name**: `X-Api-Key`
   - **Value**: `YOUR_APOLLO_API_KEY` (paste your actual key)
   
   **Body Type**: 
   ```
   JSON
   ```
   
   **Body** (JSON):
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

5. **Click "OK"**

### Step 3: Connect HTTP Module to OpenAI

1. **Connect**: HTTP Module (Module 1) → OpenAI Module (Module 2)
2. **Click on OpenAI Module** (Module 2)
3. **Find "User Message" field**
4. **Update to**: `{{`1.body.people[0]`}}`
   - This references: HTTP response → body → people array → first person
5. **Click "OK"**

### Step 4: Test

1. **Click "Run once"** in Make.com
2. **Check HTTP Module output**:
   - Should return person data
   - Should have `people` array with contact info
3. **Check OpenAI Module output**:
   - Should extract first_name, property_city, etc.
4. **Check Airtable**:
   - Lead should be created with all HELOC fields

---

## 🔄 Apollo.io API Response Structure

When HTTP module calls Apollo.io API, it returns:

```json
{
  "people": [
    {
      "id": "abc123",
      "first_name": "Sarah",
      "last_name": "Johnson",
      "email": "sarah@example.com",
      "phone_numbers": [
        {
          "raw_number": "+16025551234",
          "sanitized_number": "6025551234"
        }
      ],
      "organization_name": "ABC Property Management",
      "title": "Property Manager",
      "city": "Phoenix",
      "state": "AZ",
      "linkedin_url": "https://linkedin.com/in/sarahjohnson",
      "industry": "Real Estate"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 1,
    "total_entries": 150
  }
}
```

**That's why we use**: `{{`1.body.people[0]`}}` in OpenAI

---

## 🚀 Automation: Add Schedule Trigger

To automatically search Apollo.io daily:

1. **Delete webhook** (if still there)

2. **Add Schedule Module** (becomes Module 1):
   - Frequency: Daily at 9 AM
   - Or: Weekly on Monday at 9 AM

3. **Add HTTP Module** (becomes Module 2):
   - Same configuration as above

4. **Connect**: Schedule → HTTP → OpenAI → Rest of flow

**Result**: Apollo.io automatically searches for HELOC prospects daily/weekly!

---

## 🧪 Testing Apollo.io API Directly

Before setting up in Make.com, test the API:

**Using cURL or Postman:**
```bash
curl -X POST https://api.apollo.io/v1/mixed_people/search \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: YOUR_API_KEY" \
  -d '{
    "q_keywords": "homeowner",
    "person_titles": ["Property Manager"],
    "person_locations": ["Arizona"],
    "page": 1,
    "per_page": 1
  }'
```

If this works, the HTTP module in Make.com will work the same way!

---

## ✅ Complete Checklist

**For HTTP Module Setup:**
- [ ] Got Apollo.io API key from Settings → Integrations → API
- [ ] Deleted webhook module in Make.com
- [ ] Added HTTP module
- [ ] Configured HTTP module:
  - [ ] URL: `https://api.apollo.io/v1/mixed_people/search`
  - [ ] Method: POST
  - [ ] Header: `Content-Type: application/json`
  - [ ] Header: `X-Api-Key: YOUR_KEY`
  - [ ] Body: JSON with search criteria
- [ ] Connected HTTP → OpenAI
- [ ] Updated OpenAI User Message: `{{`1.body.people[0]`}}`
- [ ] Tested - Apollo.io returns data
- [ ] Verified AI extracts fields correctly
- [ ] Confirmed lead created in Airtable

**For Schedule Automation:**
- [ ] Added Schedule module (daily/weekly)
- [ ] Connected Schedule → HTTP module
- [ ] Scheduled time configured
- [ ] Tested automated run

---

## 🔧 Troubleshooting

### HTTP Module Returns Error:
- **Check API key** is correct
- **Verify paid Apollo.io plan** (API requires paid tier)
- **Check request format** matches Apollo.io API docs
- **Test API directly** with Postman/curl first

### No Results from Apollo.io:
- Make search criteria **less restrictive**
- Check Apollo.io **API credits/quota**
- Try searching just by location first, then add filters

### Wrong Data Structure:
- Check HTTP module **output** in Make.com
- Verify response has `people` array
- Adjust OpenAI user message path if needed

---

## 📞 Next Steps

1. **Choose your option** (HTTP Module recommended)
2. **Get Apollo.io API key**
3. **Set up HTTP module** in Make.com
4. **Test** with single search
5. **Add Schedule** for automation
6. **Monitor** lead quality

---

**The webhook is just a placeholder - Apollo.io doesn't integrate with Make.com, so we use the API directly via HTTP module!**

