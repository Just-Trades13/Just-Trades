# 📋 CREATE DATA STRUCTURE FOR MODULE 3

## ✅ STEP-BY-STEP: Create Data Structure

### Step 1: Open Module 3

1. **Click Module 3** (Parse JSON)
2. **Find "Data structure" field**
3. **Click "Add" or "Create" or "Define"** button

### Step 2: Choose Structure Type

**You'll see options like:**
- "AI JSON" (might auto-detect)
- "Custom structure"
- "From sample"

**Since OpenAI returned an ARRAY, choose:**
- **"Custom structure"** or **"From sample"**

### Step 3: Define the Structure

**Since OpenAI returned an ARRAY `[{...}, {...}]`, you need:**

**Option A: Define Array Structure**

1. **Structure type:** Array of objects
2. **Add fields below:**

**Fields to add (one per line or one per field):**

```
lead_id (text)
source (text)
acquired_at (text)
company (text)
contact_full_name (text)
first_name (text)
property_city (text)
contact_email (text)
contact_phone (text)
contact_linkedin (text)
location_city (text)
location_state (text)
contact_role (text)
industry (text)
referral_link (text)
channel (text)
status (text)
utm_list_id (text)
tags (array of text)
notes (text)
```

**Option B: Use "From Sample" (EASIER)**

1. **Click "From sample" or "Use sample JSON"**
2. **Paste this sample:**
   ```json
   [
     {
       "lead_id": "example123",
       "source": "apollo_io",
       "acquired_at": "",
       "company": "Example Company",
       "contact_full_name": "John Doe",
       "first_name": "John",
       "property_city": "Dallas",
       "contact_email": "john@example.com",
       "contact_phone": "+1234567890",
       "contact_linkedin": "http://www.linkedin.com/in/johndoe",
       "location_city": "Dallas",
       "location_state": "TX",
       "contact_role": "Property Manager",
       "industry": "real_estate",
       "referral_link": "https://axenmortgageheloc.com/account/heloc/register-v2?referrer=55ac77e7-8bb0-48c5-92a8-65960f3efe42",
       "channel": "email",
       "status": "new",
       "utm_list_id": "heloc-nelson-apollo-",
       "tags": ["heloc_prospect", "home_owner"],
       "notes": ""
     }
   ]
   ```
3. **Make.com will auto-create the structure**

---

## 🎯 RECOMMENDED: Use "From Sample"

**This is the EASIEST way:**

1. **In Module 3, click "Data structure"**
2. **Click "Add" or "Create"**
3. **Choose "From sample" or "Use sample JSON"**
4. **Paste the sample JSON above**
5. **Save**

**Make.com will automatically create all the fields!**

---

## 📋 COMPLETE FIELD LIST

**If you need to add manually, here are all fields:**

| Field Name | Type | Required |
|------------|------|----------|
| lead_id | text | No |
| source | text | No |
| acquired_at | text | No |
| company | text | No |
| contact_full_name | text | No |
| first_name | text | No |
| property_city | text | No |
| contact_email | text | No |
| contact_phone | text | No |
| contact_linkedin | text | No |
| location_city | text | No |
| location_state | text | No |
| contact_role | text | No |
| industry | text | No |
| referral_link | text | No |
| channel | text | No |
| status | text | No |
| utm_list_id | text | No |
| tags | array (of text) | No |
| notes | text | No |

**Note:** `tags` should be an **array of text**, not just text!

---

## ⚠️ IMPORTANT: Array Structure

**Since OpenAI returns an ARRAY `[{...}]`:**

1. **Structure should be:** Array
2. **Item type:** Object
3. **Object contains:** All the fields above

**Make.com should auto-detect this if you use "From sample"!**

---

## ✅ QUICK STEPS (Use Sample Method)

1. **Click Module 3**
2. **Find "Data structure" field**
3. **Click "Add" or dropdown arrow**
4. **Choose "From sample" or "Sample JSON"**
5. **Paste the sample JSON I provided**
6. **Save**
7. **Test!**

**This should work!** 🎯

