# 🏠 Nelson HELOC - Manual Apollo.io Setup Guide

## ⚠️ Important: Manual Module Setup Required

Since Make.com doesn't support HTTP or Apollo.io modules in JSON imports, you'll need to **manually add the Apollo.io module** after importing the blueprint.

**File to Import**: `Scenario A - Nelson HELOC (Webhook Placeholder).blueprint.json`

---

## 🚀 Step-by-Step Setup

### Step 1: Import the Blueprint

1. Go to Make.com → **Scenarios** → **Create new scenario**
2. Click **"Import"**
3. Upload: `Scenario A - Nelson HELOC (Webhook Placeholder).blueprint.json`
4. Click **"Import"**

You'll see a webhook module as the first module - **this is just a placeholder**.

---

### Step 2: Delete Webhook & Add Apollo.io Module

1. **Delete Module 1** (the webhook module):
   - Click on Module 1
   - Click the trash icon or right-click → Delete

2. **Add Apollo.io Module**:
   - Click **"+"** button (Add module)
   - Search for **"Apollo.io"** or **"Apollo"**
   - Look for one of these modules:
     - **"List People"** ← Try this first
     - **"Search People"**
     - **"Search Contacts"**
     - **"Find People"**
     - **"Get People"**
   - Click to add it

3. **Configure Apollo.io Module**:
   - **Connection**: Create/Select your Apollo.io connection
     - Enter your Apollo.io API key
     - Get API key from: https://app.apollo.io/#/settings/integrations/api
   
   - **Search Criteria** (configure based on available fields):
     - **Keywords** (`q_keywords`): `"homeowner property owner home equity"`
     - **Person Titles**: 
       - Property Manager
       - Real Estate Agent
       - Real Estate Developer
       - Construction Manager
       - Homeowner
     - **Person Locations**:
       - Arizona
       - California
       - Florida
       - Texas
       - Nevada
     - **Organization Industries**:
       - Real Estate
       - Construction
       - Property Management
       - Home Services
     - **Results Per Page**: `1`
     - **Page**: `1`

4. **Connect** Apollo.io module to Module 2 (OpenAI)

5. **Click "OK"**

---

### Step 3: Update OpenAI User Message

After adding Apollo.io module, you need to update the AI input:

1. **Click on Module 2** (OpenAI module)

2. **Find User Message field**

3. **Update the content** based on Apollo.io output structure:
   
   **If Apollo.io outputs an array of people:**
   ```
   {{`1.people[0]`}}
   ```
   
   **If Apollo.io outputs directly as object:**
   ```
   {{`1`}}
   ```
   
   **If Apollo.io outputs nested structure:**
   ```
   {{`1.data.people[0]`}}
   ```

4. **Test** by running the scenario once and checking Module 1 output
5. **Adjust** the user message path based on actual Apollo.io output structure

---

### Step 4: Configure Remaining Modules

#### Module 3 - Parse JSON
- **JSON**: `{{2.result}}`
- **Data Structure**: Should include HELOC fields:
  - `first_name`, `property_city`, `referral_link`, `channel`

#### Module 4 - Airtable Search
- **Base**: Your Airtable base
- **Table**: Leads
- **Formula**: `{Contact Full Name} = '{{3.contact_full_name}}'`

#### Modules 7 & 9 - Airtable Create/Update
- Map HELOC-specific fields:
  - First Name → `{{3.first_name}}`
  - Property City → `{{3.property_city}}`
  - Referral Link → `{{3.referral_link}}`
  - Channel → `{{3.channel}}`

---

## 🔍 Finding the Correct Apollo.io Output Path

### Method 1: Check Module Output
1. Run scenario once (even if it fails later)
2. Click on **Apollo.io module**
3. Click **"Data structure"** or view output
4. See the actual structure Apollo.io returns
5. Update OpenAI user message accordingly

### Common Apollo.io Output Structures:

**Structure 1** (Array):
```json
{
  "people": [
    {
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com"
    }
  ]
}
```
→ Use: `{{`1.people[0]`}}`

**Structure 2** (Direct object):
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com"
}
```
→ Use: `{{`1`}}`

**Structure 3** (Nested):
```json
{
  "data": {
    "people": [
      {
        "first_name": "John"
      }
    ]
  }
}
```
→ Use: `{{`1.data.people[0]`}}`

---

## 🎯 Alternative: Use Schedule Trigger + Apollo.io

If Apollo.io search module doesn't work, use this approach:

1. **Delete webhook module**

2. **Add Schedule Trigger**:
   - Click "+" → Search "Schedule"
   - Set frequency: Daily at 9 AM, or Weekly

3. **Add Apollo.io Module** (as Module 2):
   - Same configuration as above
   - Connect Schedule → Apollo.io → OpenAI

---

## 🧪 Testing

### Test Apollo.io Module:
1. Run scenario once
2. Check Apollo.io module output
3. Verify person data exists
4. Note the exact structure

### Test AI Processing:
1. Check Module 2 (OpenAI) output
2. Verify it extracts:
   - `first_name` ✅
   - `property_city` ✅
   - Contact details ✅

### Test End-to-End:
1. Check Airtable for new lead
2. Verify all HELOC fields populated:
   - First Name ✅
   - Property City ✅
   - Referral Link = Nelson's URL ✅
   - Channel = "email" ✅
   - Source = "apollo_io" ✅

---

## 📋 Apollo.io API Key Setup

1. **Go to Apollo.io**: https://www.apollo.io/
2. **Login** to your account
3. **Settings** → **Integrations** → **API**
4. **Copy API Key**
5. **In Make.com**: 
   - Apollo.io module → Add connection
   - Paste API key
   - Test connection
   - Save

**Note**: Apollo.io requires a **paid plan** for People Search API access.

---

## ✅ Quick Checklist

After setup:
- [ ] Webhook module deleted
- [ ] Apollo.io module added and configured
- [ ] Apollo.io connection created with API key
- [ ] Search criteria configured for HELOC prospects
- [ ] OpenAI user message updated to match Apollo.io output
- [ ] Parse JSON configured with HELOC fields
- [ ] Airtable fields mapped (including first_name, property_city, referral_link)
- [ ] Test run successful
- [ ] Lead created in Airtable with all HELOC fields

---

## 🔧 Troubleshooting

### Apollo.io Module Not Found:
- Make.com may not have Apollo.io modules in your plan
- **Solution**: Use webhook + external system to call Apollo.io API, then send data to Make.com webhook

### Wrong Output Structure:
- Apollo.io module returns different structure than expected
- **Solution**: Check Module 1 output, adjust OpenAI user message path

### No Results from Apollo.io:
- Check API key is valid
- Verify paid Apollo.io plan includes People Search
- Adjust search criteria (make less restrictive)
- Check API credits/quota

### AI Not Extracting Fields:
- Verify Apollo.io output structure matches AI prompt expectations
- Check OpenAI user message path is correct
- Review AI system prompt for field mappings

---

## 📞 Next Steps

1. **Import blueprint**
2. **Manually add Apollo.io module**
3. **Configure Apollo.io search criteria**
4. **Test and adjust**
5. **Connect to email outreach** (use first_name and property_city for personalization)

---

**Tip**: The webhook placeholder approach is the most reliable way to import complex scenarios when modules aren't available in JSON format. Once you manually add the Apollo.io module, everything else works automatically!

---

**Created for**: Nelson Morales - AXEN MORTGAGE / NEXA MORTGAGE LLC  
**Purpose**: HELOC Lead Generation via Apollo.io  
**Last Updated**: 2025-01-25

