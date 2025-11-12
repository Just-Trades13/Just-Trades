# 🏠 Nelson HELOC Lead Capture Setup Guide

## Overview

This blueprint is specifically configured for **Nelson Morales** at **AXEN MORTGAGE / NEXA MORTGAGE LLC** to automatically capture and process HELOC leads from Apollo.io.

**File**: `Scenario A - Nelson HELOC Lead Capture (Apollo.io HTTP).blueprint.json`

---

## 🎯 What's Included

### Business Information Pre-configured:
- **Company**: AXEN MORTGAGE DBA OF NEXA MORTGAGE LLC
- **Loan Officer**: Nelson Morales (NMLS #1174028)
- **Company NMLS**: 1660690
- **Phone**: 773-592-8213
- **Email**: nmorales@nexamortgage.com
- **HELOC URL**: https://axenmortgageheloc.com/account/heloc/register-v2?referrer=55ac77e7-8bb0-48c5-92a8-65960f3efe42

### HELOC-Specific Features:
- ✅ **Apollo.io Search** configured for HELOC prospects
- ✅ **AI Processing** extracts first name for personalization
- ✅ **Property City** captured for location-based outreach
- ✅ **Referral Link** automatically added to each lead
- ✅ **Channel** field set to "email" (can be updated)
- ✅ **HELOC Tags** automatically applied

---

## 📋 Prerequisites

1. ✅ **Make.com Account**
2. ✅ **Apollo.io API Key** (paid plan required)
   - Get from: https://app.apollo.io/#/settings/integrations/api
3. ✅ **OpenAI API Key**
4. ✅ **Airtable Base** with Leads table
   - Base ID: `appo7Y0cbtd1wa8Ph` (or your base)
   - Table: Leads

---

## 🚀 Step-by-Step Setup

### Step 1: Import Blueprint

1. Go to Make.com → **Scenarios** → **Create new scenario**
2. Click **"Import"**
3. Upload: `Scenario A - Nelson HELOC Lead Capture (Apollo.io HTTP).blueprint.json`
4. Click **"Import"**

---

### Step 2: Configure Module 1 - HTTP Request (Apollo.io API)

1. **Click on Module 1** (HTTP module)

2. **Configure URL**:
   - Method: **POST**
   - URL: `https://api.apollo.io/v1/mixed_people/search`

3. **Add Headers**:
   - Header 1:
     - Name: `Content-Type`
     - Value: `application/json`
   - Header 2:
     - Name: `Cache-Control`
     - Value: `no-cache`
   - Header 3:
     - Name: `X-Api-Key`
     - Value: **YOUR_APOLLO_API_KEY** ⚠️ **Add your API key here!**

4. **Configure Body** (JSON):
   ```json
   {
     "q_keywords": "homeowner property owner home equity",
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

5. **Body Content Type**: `JSON`

6. **Click "OK"**

---

### Step 3: Configure Module 2 - OpenAI Chat Completion

1. **Click on Module 2** (OpenAI module)

2. **Select Connection**: Your OpenAI connection

3. **Verify Settings**:
   - **Model**: `gpt-4o`
   - **Select Method**: "Create a Chat Completion (GPT and o1 models)"
   - **System Message**: Should contain HELOC-specific extraction instructions
   - **User Message**: `{{`1.body.people[0]`}}` (references Apollo.io response)
   - **Response Format**: "Text"
   - **Max Tokens**: 1000
   - **Temperature**: 1

4. **Click "OK"**

---

### Step 4: Configure Module 3 - Parse JSON

1. **Click on Module 3** (Parse JSON)

2. **JSON Input**: `{{2.result}}`

3. **Data Structure**: Should auto-detect, or create with these fields:
   - `lead_id` (text)
   - `source` (text)
   - `acquired_at` (text)
   - `company` (text)
   - `contact_full_name` (text)
   - **`first_name`** (text) ⭐ Nelson HELOC field
   - **`property_city`** (text) ⭐ Nelson HELOC field
   - `contact_email` (text)
   - `contact_phone` (text)
   - `contact_role` (text)
   - `location_city` (text)
   - `location_state` (text)
   - `industry` (text)
   - **`estimated_equity`** (number) ⭐ Nelson HELOC field
   - **`referral_link`** (text) ⭐ Nelson HELOC field
   - **`channel`** (text) ⭐ Nelson HELOC field
   - `status` (text)
   - `utm_list_id` (text)
   - `tags` (array)
   - `notes` (text)

4. **Click "OK"**

---

### Step 5: Configure Module 4 - Airtable Search Records

1. **Click on Module 4** (Airtable Search)

2. **Connection**: Your Airtable connection

3. **Base**: Your Airtable base ID

4. **Table**: Leads table

5. **Formula**: `{Contact Full Name} = '{{3.contact_full_name}}'`

6. **Max Records**: 20

7. **Click "OK"**

---

### Step 6: Configure Airtable Create/Update Modules

#### For Create Record (Route 1):
1. **Click on "Create New Lead" module** (inside Router → Route 1)
2. **Base**: Your Airtable base
3. **Table**: Leads
4. **Fields Mapping**: Map these fields:
   - Contact Full Name → `{{3.contact_full_name}}`
   - **First Name** → `{{3.first_name}}` ⭐
   - **Property City** → `{{3.property_city}}` ⭐
   - Contact Email → `{{3.contact_email}}`
   - Contact Phone → `{{3.contact_phone}}`
   - Location City → `{{3.location_city}}`
   - Location State → `{{3.location_state}}`
   - **Referral Link** → `{{3.referral_link}}` ⭐
   - **Channel** → `{{3.channel}}` ⭐
   - Source → `{{3.source}}`
   - Status → `{{3.status}}`
   - Tags → `{{3.tags}}`
   - Notes → `{{3.notes}}`

#### For Update Record (Route 2):
Same field mappings as above, plus:
- **Record ID**: `{{4.id}}` (from search results)

---

## 🎯 HELOC Search Criteria (Customizable)

### Target Locations:
- Arizona (Phoenix, Mesa, Scottsdale)
- California (Los Angeles, San Diego, San Francisco)
- Florida (Miami, Orlando, Tampa)
- Texas (Houston, Dallas, Austin)
- Nevada (Las Vegas)

### Target Job Titles:
- Property Manager
- Real Estate Agent
- Real Estate Developer
- Construction Manager
- Homeowner
- Property Owner

### Target Industries:
- Real Estate
- Construction
- Property Management
- Home Services

### Keywords:
- "homeowner"
- "property owner"
- "home equity"

**You can customize these in Module 1's Body configuration!**

---

## 📊 Expected Data Flow

1. **Apollo.io Search** → Finds HELOC prospects
2. **AI Processing** → Extracts:
   - First name (for personalization)
   - Property city (for location-based messaging)
   - All contact details
   - HELOC-relevant tags
3. **Parse JSON** → Structures data with HELOC fields
4. **Airtable Search** → Checks for duplicates
5. **Create/Update** → Saves lead with Nelson's referral link

---

## 🔧 Customization Options

### Update Search Criteria:
Edit Module 1 → Body → Adjust:
- `person_locations` → Target your preferred states/cities
- `person_titles` → Add more HELOC-relevant titles
- `organization_industries` → Focus on specific industries

### Update Referral Link:
If referral link changes, update in:
- Module 2 → System Message → `referral_link` field
- Or update in Airtable mapping

### Add Estimated Equity:
If you have equity data sources:
- Add enrichment step after Apollo.io
- Map to `estimated_equity` field

---

## 🧪 Testing

### Test Flow:
1. **Run scenario once** manually
2. **Check Module 1 Output**:
   - Should return `{ "people": [...], "pagination": {...} }`
   - Verify person data exists
3. **Check Module 2 Output**:
   - Should return JSON with all fields
   - Verify `first_name` and `property_city` are extracted
4. **Check Module 3 Output**:
   - Should parse all fields correctly
   - Verify HELOC-specific fields present
5. **Check Airtable**:
   - Lead should be created with:
     - First name ✅
     - Property city ✅
     - Referral link ✅
     - Channel = "email" ✅
     - Source = "apollo_io" ✅
     - HELOC tags ✅

---

## 📝 Airtable Schema Recommendations

### Required Fields (add to your Leads table):

| Field Name | Type | Purpose |
|------------|------|---------|
| First Name | Text | For personalization |
| Property City | Text | Location-based outreach |
| Referral Link | URL | Nelson's HELOC application link |
| Channel | Select | email, sms, dm |
| Estimated Equity | Number | Future enrichment |
| Source | Text | apollo_io |
| Status | Select | new, contacted, qualified, etc. |
| Tags | Multiple Selects | heloc_prospect, home_owner, etc. |

---

## 🚀 Automation Options

### Option 1: Schedule Trigger (Daily/Weekly)
1. Add **Schedule module** before HTTP module
2. Set frequency: Daily at 9 AM, or Weekly on Monday
3. Apollo.io will automatically search for new leads

### Option 2: Manual Trigger
- Run scenario manually when needed
- Useful for testing or targeted searches

### Option 3: Webhook Trigger
- Connect from external systems
- Trigger from form submissions or other sources

---

## ✅ Success Checklist

After setup, verify:
- ✅ Apollo.io API key configured
- ✅ HTTP request returns people data
- ✅ AI extracts `first_name` correctly
- ✅ AI extracts `property_city` correctly
- ✅ Referral link = Nelson's HELOC URL
- ✅ Channel = "email"
- ✅ Leads created in Airtable with all fields
- ✅ HELOC tags applied automatically

---

## 🔗 Next Steps

1. **Set up Follow-up Automation**: Connect to email outreach scenario
2. **Add Personalization**: Use `first_name` and `property_city` in email templates
3. **Track Conversions**: Monitor referral link clicks
4. **Optimize Search**: Adjust Apollo.io criteria based on lead quality

---

## 📞 Support

If you encounter issues:
1. Check Apollo.io API key is valid
2. Verify Apollo.io API credits/quota
3. Test HTTP request manually (use Postman)
4. Check AI output for parsing errors
5. Verify Airtable field mappings

---

**Created for**: Nelson Morales - AXEN MORTGAGE / NEXA MORTGAGE LLC  
**Purpose**: HELOC Lead Generation via Apollo.io  
**Last Updated**: 2025-01-25

