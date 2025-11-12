# 🔗 How Apollo.io Integrates with Nelson HELOC Blueprint

## Overview

The blueprint currently has a **webhook placeholder** (Module 1). You need to **manually replace it with Apollo.io** after importing. Here's how it works:

---

## 🔄 How It Works - Flow Diagram

```
Apollo.io Search → OpenAI Processing → Parse JSON → Airtable Check → Create/Update Lead
     (Module 1)      (Module 2)         (Module 3)     (Module 4)       (Module 7/9)
```

---

## 📋 Step-by-Step: Connecting Apollo.io

### Step 1: Import Blueprint into Make.com

1. Go to Make.com → **Scenarios** → **Create new scenario**
2. Click **"Import"**
3. Upload `Nelson_HELOC_Blueprint.json`
4. Click **"Import"**

You'll see a webhook module as Module 1 - **this is temporary**.

---

### Step 2: Delete Webhook & Add Apollo.io Module

1. **Click on Module 1** (Webhook)
2. **Delete it** (trash icon or right-click → Delete)

3. **Click "+" button** (Add module)
4. **Search for "Apollo.io"** or **"Apollo"**
5. **Look for one of these modules:**
   - **"List People"** ← Most likely
   - **"Search People"**
   - **"Search Contacts"**
   - **"Find People"**
   - **"Get People"**

6. **Add the Apollo.io module** (it becomes your new Module 1)

---

### Step 3: Configure Apollo.io Connection

1. **Click on the Apollo.io module** (Module 1)

2. **Add Connection:**
   - Click **"Add connection"** or select existing
   - **Connection Type**: Apollo.io API
   - **Enter your Apollo.io API Key**
     - Get it from: https://app.apollo.io/#/settings/integrations/api
     - Go to Apollo.io → Settings → Integrations → API
     - Copy your API key
   - **Test connection** and save

**Note**: Apollo.io requires a **paid plan** for People Search API access.

---

### Step 4: Configure Apollo.io Search for HELOC Prospects

After connecting, configure the search criteria. Fields vary by module, but typically:

#### **Target Locations** (Person Locations):
- Arizona (Phoenix, Mesa, Scottsdale)
- California (Los Angeles, San Diego, San Francisco)
- Florida (Miami, Orlando, Tampa)
- Texas (Houston, Dallas, Austin)
- Nevada (Las Vegas)

#### **Target Job Titles** (Person Titles):
- Property Manager
- Real Estate Agent
- Real Estate Developer
- Construction Manager
- Homeowner
- Property Owner

#### **Target Industries** (Organization Industries):
- Real Estate
- Construction
- Property Management
- Home Services

#### **Keywords** (q_keywords):
- "homeowner"
- "property owner"
- "home equity"

#### **Results Settings**:
- **Page**: 1
- **Per Page**: 1 (process one lead at a time for quality)

---

### Step 5: Connect Apollo.io to OpenAI Module

1. **Apollo.io module output** should connect to **Module 2** (OpenAI)
2. If not connected automatically, drag the connection line

---

### Step 6: Update OpenAI Input (If Needed)

After adding Apollo.io, check the output structure:

1. **Run scenario once** (test mode)
2. **Check Module 1 (Apollo.io) output**:
   - Click on the module
   - View the data structure
   - Note how Apollo.io returns the data

3. **Update Module 2 (OpenAI) User Message**:
   
   **If Apollo.io returns array of people:**
   ```
   {{`1.people[0]`}}
   ```
   
   **If Apollo.io returns direct object:**
   ```
   {{`1`}}
   ```
   
   **If Apollo.io returns nested:**
   ```
   {{`1.data.people[0]`}}
   ```

---

## 🎯 Apollo.io Output Structure

Apollo.io typically returns data in one of these formats:

### Format 1: Array of People
```json
{
  "people": [
    {
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "phone_numbers": [
        {
          "raw_number": "+1234567890",
          "sanitized_number": "1234567890"
        }
      ],
      "organization_name": "ABC Real Estate",
      "title": "Property Manager",
      "city": "Phoenix",
      "state": "AZ",
      "linkedin_url": "https://linkedin.com/in/johndoe"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 1,
    "total_entries": 150
  }
}
```
→ Use in OpenAI: `{{`1.people[0]`}}`

### Format 2: Direct Object
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  ...
}
```
→ Use in OpenAI: `{{`1`}}`

---

## 🤖 How AI Processes Apollo.io Data

The AI (Module 2) is already configured to extract:

1. **Contact Info**: Name, email, phone
2. **Company Info**: Organization name, industry
3. **Location**: City, state
4. **HELOC-Specific Fields**:
   - `first_name` → For "Hi {{first_name}}" personalization
   - `property_city` → For "homeowners in {{property_city}}" messaging
   - `referral_link` → Nelson's HELOC URL (auto-added)
   - `channel` → Set to "email" by default

The AI automatically:
- Maps Apollo.io fields to HELOC format
- Adds HELOC tags (heloc_prospect, home_owner, etc.)
- Sets source to "apollo_io"
- Formats data for Airtable

---

## 🔄 Complete Flow Example

### Example: Searching for HELOC Prospects in Phoenix

1. **Apollo.io Module** searches:
   - Location: "Phoenix, AZ"
   - Industry: "Real Estate"
   - Title: "Property Manager"
   - Returns: Person data

2. **OpenAI Module** extracts:
   - First Name: "Sarah"
   - Property City: "Phoenix"
   - Email: "sarah@example.com"
   - Company: "ABC Property Management"
   - Adds: referral_link, channel="email", HELOC tags

3. **Parse JSON** structures data with all 23 fields

4. **Airtable Search** checks if "Sarah" already exists

5. **Create/Update** saves lead with:
   - First Name: Sarah
   - Property City: Phoenix
   - Referral Link: Nelson's HELOC URL
   - Channel: email
   - Source: apollo_io
   - Tags: [heloc_prospect, home_owner, real_estate]

---

## 🚀 Automation Options

### Option 1: Schedule Trigger (Recommended)

1. **Delete webhook module**
2. **Add Schedule module** as Module 1:
   - Frequency: Daily at 9 AM, or Weekly on Monday
   - Time: Your preferred time
3. **Add Apollo.io module** as Module 2 (after Schedule)
4. Apollo.io will automatically search daily/weekly

**Flow**: Schedule → Apollo.io → OpenAI → Parse → Airtable

### Option 2: Manual Trigger

- Run scenario manually when needed
- Useful for testing or targeted searches

### Option 3: Webhook Trigger (Alternative)

- Keep webhook module
- Call Apollo.io API externally
- Send results to Make.com webhook
- More complex but gives full control

---

## 🔍 Finding the Right Apollo.io Module

### In Make.com UI:

1. Go to **Add Module**
2. Search **"Apollo"** or **"Apollo.io"**
3. Look for modules related to **People** or **Contacts**
4. Common names:
   - List People
   - Search People
   - Search Contacts
   - Find People

### If No Apollo.io Module Found:

**Use HTTP Module Workaround:**
1. Add **HTTP module** (`http:MakeARequest` or similar)
2. Method: **POST**
3. URL: `https://api.apollo.io/v1/mixed_people/search`
4. Headers:
   - `Content-Type: application/json`
   - `X-Api-Key: YOUR_APOLLO_API_KEY`
5. Body (JSON):
```json
{
  "q_keywords": "homeowner property owner",
  "person_titles": ["Property Manager", "Real Estate Agent"],
  "person_locations": ["Arizona", "California"],
  "organization_industries": ["Real Estate", "Construction"],
  "page": 1,
  "per_page": 1
}
```

---

## ✅ Testing Checklist

After setup, verify:

- [ ] Apollo.io module connects successfully
- [ ] API key is valid
- [ ] Search returns results
- [ ] Apollo.io output structure is correct
- [ ] OpenAI extracts `first_name` correctly
- [ ] OpenAI extracts `property_city` correctly
- [ ] Parse JSON has all HELOC fields
- [ ] Lead created in Airtable with:
  - First Name ✅
  - Property City ✅
  - Referral Link ✅
  - Channel = "email" ✅
  - Source = "apollo_io" ✅
  - HELOC tags ✅

---

## 📊 Apollo.io Search Strategy for HELOC

### Best Practices:

1. **Start Broad, Then Narrow**:
   - First: Search by location (Arizona, California)
   - Then: Add industry filters (Real Estate)
   - Finally: Add title filters (Property Manager)

2. **Target High-Value Markets**:
   - Focus on states with high home values
   - Major metropolitan areas
   - Growing real estate markets

3. **Use Multiple Searches**:
   - Create separate scenarios for different locations
   - Or use iterations/loops to search multiple cities

4. **Quality Over Quantity**:
   - Set `per_page: 1` to process leads carefully
   - Review lead quality before scaling

---

## 🔧 Troubleshooting

### Apollo.io Returns No Results:
- Check API key is valid
- Verify paid Apollo.io plan includes People Search
- Make search criteria less restrictive
- Check Apollo.io API credits/quota

### Wrong Data Structure:
- Run scenario in test mode
- Check Apollo.io module output
- Adjust OpenAI user message path
- Review AI system prompt for field mappings

### AI Not Extracting Fields:
- Verify Apollo.io output matches expected format
- Check OpenAI user message references correct path
- Review AI system prompt for Apollo.io field names
- Test with sample Apollo.io response

---

## 💡 Pro Tips

1. **Create Saved Searches in Apollo.io**:
   - Save your HELOC search criteria in Apollo.io dashboard
   - Reference saved search IDs in Make.com (if supported)

2. **Use Apollo.io Filters**:
   - Filter by company size
   - Filter by location radius
   - Filter by recent updates

3. **Enrichment**:
   - Apollo.io may provide additional data
   - Use it to populate `estimated_equity` if available

4. **Rate Limits**:
   - Apollo.io has API rate limits
   - Add delays between searches if processing multiple leads

---

## 📞 Next Steps

1. **Import blueprint**
2. **Add Apollo.io module** manually
3. **Configure search** for HELOC prospects
4. **Test** with single search
5. **Add Schedule trigger** for automation
6. **Monitor** lead quality and adjust criteria

---

**The blueprint is designed to work with Apollo.io - you just need to connect it manually after import!**

