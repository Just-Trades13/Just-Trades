# 🔍 Apollo.io EXACT Setup Guide for Nelson HELOC

## 📋 Apollo.io Module Options in Make.com

When you search "Apollo.io" in Make.com, you'll see these modules:

### **Use This One: "Search People" or "List Contacts"**

These are the search/filter modules that find prospects. The other options (Create Contact, Update Contact, etc.) are for managing contacts, NOT searching for new leads.

---

## 🎯 Exact Module to Use: "Search People"

**Module Name**: Apollo.io → **"Search People"** (or **"List Contacts"** if available)

**What It Does**: Searches Apollo.io's database for people matching your criteria

---

## ⚙️ Exact Configuration Steps

### Step 1: Add Apollo.io Module

1. **Delete the webhook module** (Module 1)
2. **Click "+"** → Search **"Apollo.io"**
3. **Select "Search People"** (or "List Contacts")

---

### Step 2: Configure Connection

1. **Click "Add connection"** or select existing
2. **Connection Name**: "Apollo.io HELOC"
3. **API Key**: 
   - Get from: https://app.apollo.io/#/settings/integrations/api
   - Copy your API key
   - Paste it here
4. **Click "Test connection"**
5. **Save**

---

### Step 3: Configure "Search People" Module Parameters

When you click on the Apollo.io "Search People" module, you'll see these fields to configure:

#### **Field 1: Keywords** (Optional but Recommended)
```
homeowner property owner home equity
```
- **What it does**: Searches for people with these keywords in their profile
- **Use**: Broad search to find HELOC prospects

#### **Field 2: Person Titles** (Array)
Add these one by one:
- Property Manager
- Real Estate Agent
- Real Estate Developer
- Construction Manager
- Homeowner
- Property Owner

**How to add**: Click "Add item" or "+" for each title

#### **Field 3: Person Locations** (Array)
Add states/cities:
- Arizona
- California
- Florida
- Texas
- Nevada
- Or specific cities: Phoenix, Los Angeles, Miami, etc.

**How to add**: Click "Add item" for each location

#### **Field 4: Organization Industries** (Array)
Add:
- Real Estate
- Construction
- Property Management
- Home Services

**How to add**: Click "Add item" for each industry

#### **Field 5: Page** (Number)
```
1
```
- **What it does**: Which page of results (start with page 1)

#### **Field 6: Per Page** (Number)
```
1
```
- **What it does**: How many results per search
- **Use 1** for quality - process one lead at a time

#### **Field 7: Sort** (Optional)
- Leave default or choose "Relevance"

---

## 📊 Apollo.io Output Structure

After running, Apollo.io "Search People" returns data like this:

```json
{
  "people": [
    {
      "id": "abc123",
      "first_name": "Sarah",
      "last_name": "Johnson",
      "name": "Sarah Johnson",
      "email": "sarah@example.com",
      "phone_numbers": [
        {
          "raw_number": "+16025551234",
          "sanitized_number": "6025551234"
        }
      ],
      "organization_name": "ABC Property Management",
      "organization": {
        "name": "ABC Property Management",
        "industry": "Real Estate"
      },
      "title": "Property Manager",
      "city": "Phoenix",
      "state": "AZ",
      "country": "United States",
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

---

## 🔗 Connecting to Module 2 (OpenAI)

### Update OpenAI User Message

After adding Apollo.io module, you need to tell OpenAI where to find the person data:

1. **Click on Module 2** (OpenAI module)
2. **Find "User Message" field**
3. **Update it to**:
   ```
   {{`1.people[0]`}}
   ```

**Why**: Apollo.io returns `people` array, and `people[0]` is the first person found.

**Alternative paths to try** (depending on Apollo.io module structure):
- `{{`1.people[0]`}}` ← Most likely
- `{{`1.data.people[0]`}}`
- `{{`1`}}` ← If it returns single object directly

**How to know which one**: Run the scenario once and check Module 1 output structure.

---

## 🎯 Complete Configuration Example

### Apollo.io "Search People" Module Settings:

```
Keywords: homeowner property owner
Person Titles: [Property Manager, Real Estate Agent]
Person Locations: [Arizona, California, Florida]
Organization Industries: [Real Estate, Construction]
Page: 1
Per Page: 1
```

---

## 🔄 Alternative: If "Search People" Doesn't Exist

If Make.com doesn't have "Search People", use **"List Contacts"**:

### "List Contacts" Configuration:

**Different Fields**:
- **Filter/Query**: Enter search criteria
- **Limit**: 1
- **Sort**: Relevance

---

## 🛠️ Alternative: Use HTTP Module (If No Apollo.io Module)

If Apollo.io modules don't work, use **HTTP module**:

### HTTP Module Configuration:

1. **Add HTTP module** → **"Make a Request"**
2. **Method**: POST
3. **URL**: `https://api.apollo.io/v1/mixed_people/search`
4. **Headers**:
   - Header 1:
     - Name: `Content-Type`
     - Value: `application/json`
   - Header 2:
     - Name: `X-Api-Key`
     - Value: `YOUR_APOLLO_API_KEY`
5. **Body Type**: JSON
6. **Body** (JSON):
```json
{
  "q_keywords": "homeowner property owner",
  "person_titles": ["Property Manager", "Real Estate Agent"],
  "person_locations": ["Arizona", "California", "Florida"],
  "organization_industries": ["Real Estate", "Construction"],
  "page": 1,
  "per_page": 1
}
```

7. **Update OpenAI User Message**: `{{`1.body.people[0]`}}`

---

## 🧪 Testing Apollo.io Connection

### Test Step-by-Step:

1. **Configure Apollo.io module** with test search:
   - Locations: Just "Arizona"
   - Titles: Just "Property Manager"
   - Per Page: 1

2. **Click "Run once"** button in Make.com

3. **Check Module 1 Output**:
   - Click on Apollo.io module
   - View "Output" or "Data structure"
   - You should see person data

4. **Note the structure**:
   - Does it have `people` array?
   - Or is it directly an object?
   - Where is the person data located?

5. **Update OpenAI User Message** based on actual structure

---

## 📝 Field Mapping: Apollo.io → HELOC Fields

The AI (Module 2) automatically maps Apollo.io fields:

| Apollo.io Field | Maps To HELOC Field |
|----------------|---------------------|
| `first_name` | `first_name` |
| `city` | `property_city` |
| `email` | `contact_email` |
| `phone_numbers[0].sanitized_number` | `contact_phone` |
| `organization_name` | `company` |
| `title` | `contact_role` |
| `state` | `location_state` |
| `linkedin_url` | `contact_linkedin` |
| `organization.industry` | `industry` (mapped to HELOC categories) |

**Auto-Added Fields** (by AI):
- `referral_link` → Nelson's HELOC URL
- `channel` → "email"
- `source` → "apollo_io"
- `tags` → HELOC tags (heloc_prospect, home_owner, etc.)

---

## 🚀 Automation Setup

### Option 1: Schedule Trigger (Recommended)

1. **Add Schedule module** before Apollo.io:
   - Frequency: Daily at 9 AM
   - Or: Weekly on Monday
2. **Connect**: Schedule → Apollo.io → OpenAI → Rest of flow
3. **Result**: Automatically searches for new HELOC leads daily/weekly

### Option 2: Manual Trigger
- Run scenario manually when you want leads
- Good for testing

---

## ✅ Complete Setup Checklist

- [ ] Deleted webhook module
- [ ] Added Apollo.io "Search People" module
- [ ] Configured Apollo.io connection with API key
- [ ] Set search criteria:
  - [ ] Keywords: "homeowner property owner"
  - [ ] Person Titles: Property Manager, Real Estate Agent, etc.
  - [ ] Person Locations: Arizona, California, etc.
  - [ ] Organization Industries: Real Estate, Construction
  - [ ] Per Page: 1
- [ ] Connected Apollo.io to Module 2 (OpenAI)
- [ ] Updated OpenAI User Message: `{{`1.people[0]`}}`
- [ ] Tested scenario - Apollo.io returns data
- [ ] Verified AI extracts first_name and property_city
- [ ] Confirmed lead created in Airtable with all HELOC fields

---

## 🔧 Troubleshooting

### "Search People" Not Found:
- Try "List Contacts"
- Or use HTTP module approach

### No Results from Apollo.io:
- **Check API key** is valid
- **Verify paid Apollo.io plan** (People Search requires paid tier)
- **Make search less restrictive**: Remove some filters
- **Check API credits/quota** in Apollo.io dashboard

### Wrong Data Structure:
- **Run scenario once** to see actual Apollo.io output
- **Check Module 1 output** structure
- **Adjust OpenAI user message** path accordingly:
  - If array: `{{`1.people[0]`}}`
  - If object: `{{`1`}}`
  - If nested: `{{`1.data.people[0]`}}`

### AI Not Extracting Fields:
- **Verify Apollo.io returns data** correctly
- **Check OpenAI user message** points to correct path
- **Review AI system prompt** (already configured for Apollo.io)
- **Test with sample data** manually

---

## 📞 Quick Reference

**Apollo.io Module**: "Search People"  
**API Endpoint**: `https://api.apollo.io/v1/mixed_people/search`  
**Method**: POST  
**Required Header**: `X-Api-Key: YOUR_API_KEY`  
**Response Structure**: `{ "people": [...], "pagination": {...} }`  
**OpenAI Input**: `{{`1.people[0]`}}`

---

**Now you have the EXACT steps to set up Apollo.io with your HELOC blueprint!**

