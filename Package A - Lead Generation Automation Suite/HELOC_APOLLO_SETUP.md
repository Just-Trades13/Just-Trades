# 🏠 HELOC Lead Capture Setup with Apollo.io

## Overview

This blueprint replaces the webhook module with **Apollo.io Search People** module to automatically source HELOC (Home Equity Line of Credit) leads. The AI processing has been tailored specifically for HELOC prospects.

---

## 🎯 What Changed from Original Scenario A

### Module 1: Apollo.io Search People (Replaces Webhook)
- **Module**: `apollo-io:SearchPeople`
- **Purpose**: Automatically search and find potential HELOC prospects
- **Output**: Array of people matching your search criteria

### Module 2: AI Processing (Updated for HELOC)
- **Updated Prompt**: Extracts data from Apollo.io structure
- **HELOC-Focused**: Industry mappings and tags specific to home equity prospects
- **Source**: Changed from "linkedin" to "apollo_io"

---

## 📋 Prerequisites

Before importing, ensure you have:

1. ✅ **Make.com Account** (with appropriate plan)
2. ✅ **Apollo.io Account** with API access
   - Sign up at: https://www.apollo.io/
   - Get API key from: Settings → Integrations → API
   - **Note**: Apollo.io requires a paid plan for People Search API
3. ✅ **OpenAI API Key** (for AI processing)
4. ✅ **Airtable Connection** configured
   - Base ID: `appo7Y0cbtd1wa8Ph`
   - Table: `tblmVnZaaWToTXxaR`

---

## 🚀 Setup Instructions

### Step 1: Import the Blueprint

1. Go to Make.com → **Scenarios** → **Create a new scenario**
2. Click **"Import"** button
3. Upload: `Scenario A - HELOC Lead Capture (Apollo.io).blueprint.json`
4. Click **"Import"**

---

### Step 2: Configure Module 1 - Apollo.io Search People

1. **Click on the Apollo.io module** (first module)

2. **Connect Apollo.io**:
   - If not connected, click "Add connection"
   - Enter your Apollo.io API key
   - Test connection and save

3. **Configure Search Parameters** (for HELOC prospects):
   
   **Recommended HELOC Search Criteria:**
   
   - **Person Titles** (Optional):
     - Property Manager
     - Real Estate Agent
     - Homeowner
     - Property Owner
     - Real Estate Developer
     - Construction Manager
     
   - **Organization Industries** (Optional):
     - Real Estate
     - Construction
     - Property Management
     - Home Services
     
   - **Person Locations** (Target markets):
     - Specific cities: Los Angeles, CA; Phoenix, AZ; Miami, FL
     - Or states: California, Florida, Texas, Arizona
     
   - **Keywords** (`q_keywords`):
     - "homeowner"
     - "property owner"
     - "home equity"
     - Leave empty to search all criteria
     
   - **Results Per Page**: `1` (processes one lead at a time)
   - **Page**: `1` (for initial run)

4. **Click "OK"** to save

---

### Step 3: Configure Module 2 - OpenAI Chat Completion

1. **Click on the OpenAI module** (second module)

2. **Select Connection**: Choose your OpenAI connection

3. **Verify Settings**:
   - **Model**: `gpt-4o`
   - **Select Method**: "Create a Chat Completion (GPT and o1 models)"
   - **System Message**: Should already contain HELOC-specific extraction instructions
   - **User Message**: Should be `{{`1.people[0]`}}` (references Apollo.io output)
   - **Response Format**: "Text"
   - **Max Tokens**: 1000
   - **Temperature**: 1

4. **Click "OK"**

---

### Step 4: Configure Module 3 - Parse JSON

1. **Click on Parse JSON module**

2. **JSON Input**: `{{2.result}}`
   - Note: Uses `result` because Scenario A uses `CreateCompletion` module

3. **Data Structure**: 
   - Should auto-detect or use "AI JSON" type
   - Or manually create structure with these fields:
     - `lead_id` (text)
     - `source` (text)
     - `acquired_at` (text)
     - `company` (text)
     - `domain` (text)
     - `industry` (text)
     - `employee_count` (number)
     - `contact_full_name` (text)
     - `contact_role` (text)
     - `contact_email` (text)
     - `contact_phone` (text)
     - `contact_linkedin` (text)
     - `location_city` (text)
     - `location_state` (text)
     - `status` (text)
     - `utm_list_id` (text)
     - `tags` (array)
     - `notes` (text)

4. **Click "OK"**

---

### Step 5: Configure Module 4 - Airtable Search Records

1. **Click on Airtable Search Records module**

2. **Connection**: Select your Airtable connection

3. **Base**: `appo7Y0cbtd1wa8Ph` (Leads Manager AI CRM)

4. **Table**: `tblmVnZaaWToTXxaR` (Leads)

5. **Formula**: `{Contact Full Name} = '{{3.contact_full_name}}'`
   - This searches for duplicate leads by name

6. **Max Records**: 20

7. **Click "OK"**

---

### Step 6: Configure Module 5 - Router

The router automatically:
- **Route 1**: Creates new lead if no duplicates found (`__IMTLENGTH__` = 0)
- **Route 2**: Updates existing lead if duplicate found (`__IMTLENGTH__` >= 1)

No configuration needed - already set up!

---

### Step 7: Configure Module 7 - Create New Lead (Route 1)

1. **Click on "Create New Lead" module** (inside Route 1)

2. **Connection**: Select Airtable connection

3. **Base**: `appo7Y0cbtd1wa8Ph`

4. **Table**: `tblmVnZaaWToTXxaR`

5. **Fields**: Should auto-map from Module 3 output
   - Verify all fields are mapped correctly
   - Check that `tags` array is mapped

6. **Click "OK"**

---

### Step 8: Configure Module 9 - Update Existing Lead (Route 2)

1. **Click on "Update Existing Lead" module** (inside Route 2)

2. **Connection**: Select Airtable connection

3. **Base**: `appo7Y0cbtd1wa8Ph`

4. **Table**: `tblmVnZaaWToTXxaR`

5. **Record ID**: `{{4.id}}` (from search results)

6. **Fields**: Should auto-map from Module 3 output

7. **Click "OK"**

---

## 🎯 HELOC-Specific Features

### Industry Mappings
The AI automatically maps industries relevant to HELOC:
- **Real Estate** → `real_estate`
- **Construction** → `construction`
- **Property Management** → `real_estate`
- **Home Services** → `real_estate`
- **Financial Services** → `finance`
- **Banking** → `finance`
- **Mortgage** → `finance`

### HELOC Tags
The system automatically adds relevant tags:
- `heloc_prospect` - All leads from Apollo.io
- `home_owner` - For homeowners
- `property_owner` - For property owners
- `high_equity` - For high-value prospects
- `real_estate`, `construction`, `finance` - Industry tags
- `high_priority` - For executive roles (CEO, VP, Director)
- Location tags: `los_angeles`, `new_york`, `chicago`, etc.

---

## 🔄 How to Run (Trigger Options)

### Option 1: Manual Trigger (Testing)
1. Click **"Run once"** button in Make.com
2. Select Apollo.io module to trigger manually
3. Verify leads are processed

### Option 2: Schedule Trigger (Recommended)
1. **Delete the Apollo.io module** temporarily
2. **Add Schedule module** as first module:
   - Module: `schedule:Schedule`
   - Frequency: Daily, Weekly, or Hourly
   - Time: Set your preferred time (e.g., 9 AM daily)
3. **Add Apollo.io as Module 2** (after schedule)
4. Apollo.io will run automatically on schedule

### Option 3: Webhook Trigger (Alternative)
If you want to trigger from external systems:
1. Add a **Webhook module** before Apollo.io
2. Configure webhook to receive triggers
3. Pass search parameters via webhook

---

## 🧪 Testing

1. **Run Scenario Once**:
   - Click "Run once" in Make.com
   - Monitor execution flow

2. **Check Apollo.io Output**:
   - Verify Module 1 returns people array
   - Check that `people[0]` contains contact data

3. **Verify AI Processing**:
   - Check Module 2 output contains valid JSON
   - Verify all fields extracted correctly

4. **Check Airtable**:
   - Open your Airtable base
   - Verify new lead created with HELOC-specific tags
   - Check `source` = "apollo_io"

---

## ⚠️ Common Issues & Solutions

### Issue: Apollo.io Module Not Found
**Solution**: 
- Apollo.io module might need to be added manually in Make.com UI
- Go to Make.com → Add module → Search "Apollo.io"
- If not available, use Make.com's **API module** to call Apollo.io REST API directly

### Issue: No Results from Apollo.io
**Solution**:
- Check your Apollo.io API key is valid
- Verify you have a paid Apollo.io plan (People Search requires paid plan)
- Adjust search criteria (make it less restrictive)
- Check Apollo.io API credits/quota

### Issue: AI Not Extracting Data Correctly
**Solution**:
- Verify Apollo.io output structure matches expected format
- Check Module 2 user message: should be `{{`1.people[0]`}}`
- Review AI system prompt for Apollo.io field mappings
- Test with sample Apollo.io response

### Issue: JSON Parse Error
**Solution**:
- Verify Module 3 input: `{{2.result}}`
- Check AI output is valid JSON (no markdown formatting)
- Review AI temperature (should be 1, not too high)
- Check max_tokens is sufficient (1000 should be enough)

---

## 📊 Apollo.io API Notes

### Module Name Variations
Apollo.io in Make.com might be named:
- `apollo-io:SearchPeople`
- `apollo:SearchPeople`
- `apollocom:SearchPeople`

If module not found in JSON import:
1. Import blueprint anyway (creates structure)
2. Delete placeholder module
3. Manually add Apollo.io module from Make.com UI
4. Configure with your search criteria

### Alternative: Use HTTP Module
If Apollo.io module doesn't exist:
1. Use **HTTP module** (`http:MakeARequest`)
2. Method: POST
3. URL: `https://api.apollo.io/v1/mixed_people/search`
4. Headers:
   - `Content-Type: application/json`
   - `X-Api-Key: YOUR_APOLLO_API_KEY`
5. Body: JSON with search criteria

---

## 🎓 HELOC Lead Generation Tips

### Best Apollo.io Search Strategies for HELOC:

1. **Target High-Value Locations**:
   - Major metropolitan areas
   - Areas with high home values
   - States with growing real estate markets

2. **Search by Job Titles**:
   - Real Estate Agents
   - Property Managers
   - Construction Professionals
   - Homeowners (if available in Apollo.io)

3. **Industry Filters**:
   - Real Estate
   - Construction
   - Property Management
   - Home Services

4. **Keywords**:
   - "homeowner"
   - "property owner"
   - "home equity"
   - "real estate"

---

## ✅ Success Checklist

After setup, verify:
- ✅ Apollo.io connection successful
- ✅ Search returns results
- ✅ AI extracts all fields correctly
- ✅ Leads created in Airtable with correct tags
- ✅ Source field = "apollo_io"
- ✅ HELOC-specific tags applied
- ✅ Duplicate detection working

---

## 📞 Support

If you encounter issues:
1. Check Make.com execution logs
2. Verify all API keys are valid
3. Test Apollo.io API directly (using Postman or curl)
4. Review AI output for parsing errors
5. Check Airtable field mappings

---

## 🔄 Next Steps

After setup:
1. **Configure Follow-up Automation**: Set up Scenario B (Initial Outreach) to email HELOC leads
2. **Add Website Integration**: Connect your HELOC website form to trigger this scenario
3. **Monitor Performance**: Track conversion rates and optimize search criteria
4. **Scale**: Adjust Apollo.io search to find more prospects

---

**Created for**: HELOC Lead Generation  
**Last Updated**: 2025-01-25  
**Blueprint Version**: Apollo.io Integration v1.0

