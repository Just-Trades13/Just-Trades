# 📋 COMPLETE MODULE CONFIGURATION GUIDE

## 🎯 Setup Order

1. **First:** Create Airtable table (Step 1)
2. **Then:** Configure modules 3 → 4 → 5 → 6 → 7

---

## ✅ STEP 1: CREATE AIRTABLE TABLE

### Option A: Import CSV (RECOMMENDED)

1. **Go to:** [airtable.com](https://airtable.com)
2. **Click:** "+ Add a base" → "Import a spreadsheet"
3. **Upload:** `HELOC_Leads_Airtable.csv`
4. **Name:** "HELOC Leads" or "Nelson Leads"

### Option B: Create Manually

**Create new table with these fields (in order):**

#### Required Fields:

| Field Name | Type | Options | Notes |
|------------|------|---------|-------|
| **Contact Email** | Email | | Used for duplicate detection |
| **Contact Full Name** | Single line text | | |
| **First Name** | Single line text | | For personalization |
| **Company** | Single line text | | |
| **Contact Phone** | Phone number | | |
| **Contact LinkedIN** | URL | | |
| **Location City** | Single line text | | |
| **Location State** | Single line text | | State abbreviation |
| **Property City** | Single line text | | HELOC-specific |
| **Contact Role** | Single line text | | Job title |
| **Industry** | Single line text | | |
| **Status** | Single select | `new`, `contacted`, `qualified`, `closed` | |
| **Source** | Single select | `apollo_io` | **MUST ADD THIS OPTION!** |
| **Channel** | Single select | `email`, `sms`, `dm` | |
| **Referral Link** | URL | | |
| **Notes** | Long text | | |
| **Lead ID** | Single line text | | Auto-generated |
| **Acquired At** | Date | | |
| **Domain** | Single line text | | |
| **Employee Count** | Number | | |
| **Tags** | Multiple select | See below | |
| **Estimated Equity** | Number | | |
| **UTM List ID** | Single line text | | |
| **Last Out Reach** | Date | | |
| **Next Step** | Single line text | | |
| **Meeting Link** | URL | | |
| **Email Campaign** | Single select | `initial_outreach`, `follow_up_1`, etc. | |
| **Reply Received** | Checkbox | | |
| **Meeting Completed** | Checkbox | | |
| **Pipeline Value** | Currency | | |

#### Configure Select Fields:

**Status:**
- Options: `new`, `contacted`, `qualified`, `closed_lost`

**Source:**
- Options: `apollo_io` ← **CRITICAL - MUST ADD!**

**Channel:**
- Options: `email`, `sms`, `dm`

**Tags (Multiple Select):**
- Options: `heloc_prospect`, `home_owner`, `property_owner`, `real_estate`, `construction`, `finance`, `high_priority`

**Email Campaign:**
- Options: `initial_outreach`, `follow_up_1`, `follow_up_2`, `nurture`, `closed`

---

## 🔧 MODULE 3: JSON PARSE

**Location:** After OpenAI (Module 2)

### Configuration:

1. **Click Module 3** (Parse JSON)
2. **JSON String Field:**
   ```
   {{2.result}}
   ```
   (This gets the JSON output from OpenAI Module 2)

3. **Data Structure:**
   - Click "Add" or "Define"
   - Select "AI JSON" (recommended)
   - OR manually create structure with these fields:
     - `contact_email` (text)
     - `contact_full_name` (text)
     - `first_name` (text)
     - `company` (text)
     - `contact_phone` (text)
     - `contact_linkedin` (text)
     - `location_city` (text)
     - `location_state` (text)
     - `property_city` (text)
     - `contact_role` (text)
     - `industry` (text)
     - `status` (text)
     - `source` (text)
     - `referral_link` (text)
     - `channel` (text)
     - `notes` (text)
     - `tags` (array)

4. **Click "OK"**

**✅ Expected Output:**
Module 3 should now have fields like:
- `{{3.contact_email}}`
- `{{3.contact_full_name}}`
- `{{3.company}}`
- etc.

---

## 🔍 MODULE 4: AIRTABLE SEARCH RECORDS

**Location:** After Parse JSON (Module 3)

### Configuration:

1. **Click Module 4** (Airtable Search Records)
2. **Connection:** Select your Airtable connection
3. **Base:** Select your base (where you imported the CSV)
4. **Table:** Select your table
5. **Formula (CRITICAL!):**
   ```
   {Contact Email} = '{{3.contact_email}}'
   ```
   **This searches for existing leads by email to avoid duplicates!**

6. **Max Records:** `1`

7. **Fields to Return:**
   - ✅ `Contact Email`
   - ✅ `Contact Full Name`
   - ✅ `Company`
   - ✅ `Status`
   - ✅ `id` (always include - needed for update!)

8. **Click "OK"**

**✅ Expected Output:**
- If duplicate found: Returns 1 record with `id`
- If no duplicate: Returns empty array (length = 0)

---

## 🚦 MODULE 5: ROUTER

**Location:** After Airtable Search (Module 4)

### Configuration:

1. **Click Module 5** (Router)
2. **Route Type:** Select "If/Else"
3. **Filter (for "If" path - Create New Lead):**
   ```
   {{4.`__IMTLENGTH__`}} = 0
   ```
   **This means:** "If Module 4 found 0 records (no duplicate), create new lead"

4. **Routes:**
   - **"If" Path (True):** Goes to Module 6 (Create Record) - No duplicate found
   - **"Else" Path (False):** Goes to Module 7 (Update Record) - Duplicate found

5. **Click "OK"**

**✅ Logic:**
- No duplicate? → Create new record (Module 6)
- Duplicate found? → Update existing record (Module 7)

---

## ➕ MODULE 6: AIRTABLE CREATE RECORD

**Location:** Router "If" path (no duplicate found)

### Configuration:

1. **Click Module 6** (Airtable Create Record)
2. **Connection:** Select your Airtable connection
3. **Base:** Select your base
4. **Table:** Select your table
5. **Record Fields - Map from Module 3:**

**Essential Fields:**
```
Contact Email: {{3.contact_email}}
Contact Full Name: {{3.contact_full_name}}
First Name: {{3.first_name}}
Company: {{3.company}}
Contact Phone: {{3.contact_phone}}
Contact LinkedIN: {{3.contact_linkedin}}
Location City: {{3.location_city}}
Location State: {{3.location_state}}
Property City: {{3.property_city}}
Contact Role: {{3.contact_role}}
Industry: {{3.industry}}
Status: new
Source: apollo_io
Channel: email
Referral Link: {{3.referral_link}}
Notes: {{3.notes}}
```

**Optional Fields (if available in Module 3):**
```
Domain: {{3.domain}}
Employee Count: {{3.employee_count}}
Estimated Equity: {{3.estimated_equity}}
UTM List ID: {{3.utm_list_id}}
Tags: {{3.tags}}
Acquired At: {{now}}
Last Out Reach: {{now}}
```

6. **Click "OK"**

**✅ Expected Result:**
New lead record created in Airtable with all mapped fields!

---

## ✏️ MODULE 7: AIRTABLE UPDATE RECORD

**Location:** Router "Else" path (duplicate found)

### Configuration:

1. **Click Module 7** (Airtable Update Record)
2. **Connection:** Select your Airtable connection
3. **Base:** Select your base
4. **Table:** Select your table
5. **Record ID:** 
   ```
   {{4.id[0]}}
   ```
   (Gets the ID from Module 4 search result)

6. **Record Fields - Update with new data:**

**Update these fields:**
```
Contact Full Name: {{3.contact_full_name}}
First Name: {{3.first_name}}
Company: {{3.company}}
Contact Phone: {{3.contact_phone}}
Contact LinkedIN: {{3.contact_linkedin}}
Location City: {{3.location_city}}
Location State: {{3.location_state}}
Property City: {{3.property_city}}
Contact Role: {{3.contact_role}}
Industry: {{3.industry}}
Last Out Reach: {{now}}
Notes: {{3.notes}} (append or replace)
```

**Keep existing:**
- Contact Email (don't change)
- Status (keep current unless you want to update)
- Source (keep existing)

7. **Click "OK"**

**✅ Expected Result:**
Existing lead record updated with latest information!

---

## ✅ TESTING CHECKLIST

### Test Module 3:
- [ ] Module 3 receives JSON from Module 2
- [ ] Can see fields like `{{3.contact_email}}`
- [ ] All fields have data

### Test Module 4:
- [ ] Searches by email correctly
- [ ] Returns 0 if new lead
- [ ] Returns 1 if duplicate exists

### Test Module 5:
- [ ] Routes correctly based on duplicate check
- [ ] "If" path goes to Module 6
- [ ] "Else" path goes to Module 7

### Test Module 6 (Create):
- [ ] Creates new record in Airtable
- [ ] All fields populated correctly
- [ ] Status = "new"
- [ ] Source = "apollo_io"

### Test Module 7 (Update):
- [ ] Updates existing record
- [ ] Uses correct Record ID
- [ ] Fields updated correctly

### Final Check:
- [ ] Run full scenario
- [ ] Check Airtable - new lead appears!
- [ ] All fields populated!
- [ ] No errors!

---

## 🚨 TROUBLESHOOTING

### Issue: Module 3 shows no data
**Fix:** Check Module 2 (OpenAI) output. Make sure it's returning JSON.

### Issue: Module 4 can't find field "Contact Email"
**Fix:** Field name must match exactly. Check Airtable field name (case-sensitive).

### Issue: Module 6 creates but fields are blank
**Fix:** Check field mappings. Make sure you're using `{{3.field_name}}` format.

### Issue: "Insufficient permissions to create new select option"
**Fix:** Add "apollo_io" option to "Source" field in Airtable first.

### Issue: Module 7 can't find Record ID
**Fix:** Make sure Module 4 returns `id` field. Check formula is correct.

---

## 📋 QUICK REFERENCE

**Module 3 (Parse):** `{{2.result}}`  
**Module 4 (Search):** Formula: `{Contact Email} = '{{3.contact_email}}'`  
**Module 5 (Router):** Filter: `{{4.`__IMTLENGTH__`}} = 0`  
**Module 6 (Create):** Map all fields from `{{3.*}}`  
**Module 7 (Update):** Record ID: `{{4.id[0]}}`, Update fields from `{{3.*}}`

---

**Follow these steps in order and your Airtable will populate perfectly!** 🚀

