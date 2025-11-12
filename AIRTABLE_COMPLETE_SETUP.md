# 📋 COMPLETE AIRTABLE SETUP - Get Data Populating!

## 🎯 THE PROBLEM

Your blueprint isn't mapping fields correctly to Airtable. Here's how to fix it!

---

## ✅ STEP 1: Create/Import Airtable Table

### Option A: Import CSV (EASIEST)

1. **Download:** `HELOC_Leads_Airtable.csv` (already created for you!)
2. **Go to:** [airtable.com](https://airtable.com)
3. **Click:** "+ Add a base" → "Import a spreadsheet"
4. **Upload:** `HELOC_Leads_Airtable.csv`
5. **Name it:** "HELOC Leads" or "Nelson Leads"

### Option B: Create Manually

**Create a new table with these fields:**

#### Required Fields (Must Have!)

| Field Name | Field Type | Options/Notes |
|------------|------------|---------------|
| **Contact Email** | Email | Used for duplicate detection |
| **Contact Full Name** | Single line text | |
| **First Name** | Single line text | |
| **Company** | Single line text | |
| **Status** | Single select | Options: `new`, `contacted`, `qualified`, `closed` |
| **Source** | Single select | Options: `apollo_io` ← **MUST ADD THIS!** |
| **Contact Phone** | Phone number | |
| **Contact LinkedIN** | URL | |
| **Location City** | Single line text | |
| **Location State** | Single line text | |
| **Contact Role** | Single line text | |
| **Industry** | Single line text | |
| **Property City** | Single line text | HELOC-specific |
| **Referral Link** | URL | |
| **Channel** | Single select | Options: `email`, `sms`, `dm` |
| **Notes** | Long text | |

---

## 🔧 STEP 2: Fix Module 4 (Airtable Search)

**In Make.com:**

1. **Click Module 4** (Airtable Search Records)
2. **Update these settings:**

**Base:** Select your Airtable base  
**Table:** Select your table (probably "Table 1" or "HELOC Leads")

**Formula (IMPORTANT!):**
```
{Contact Email} = '{{3.contact_email}}'
```

**Fields to Return:**
- ✅ Select: `Contact Email`
- ✅ Select: `Status`
- ✅ Select: `Contact Full Name`
- ✅ Select: `Company`
- ✅ Select: `id` (always include this!)

**Max Records:** `1`

**Why:** This searches for existing leads by email to avoid duplicates!

---

## 🎯 STEP 3: Fix Module 7 (Create Record)

**In Make.com:**

1. **Click Module 7** (Airtable Create Record - in Router "If" path)
2. **Update field mappings:**

**Base:** Your Airtable base  
**Table:** Your table

**Map these fields from Module 3 (Parsed JSON):**

| Airtable Field | Map From | Example |
|----------------|----------|---------|
| **Contact Email** | `{{3.contact_email}}` | |
| **Contact Full Name** | `{{3.contact_full_name}}` | |
| **First Name** | `{{3.first_name}}` | |
| **Company** | `{{3.company}}` | |
| **Contact Phone** | `{{3.contact_phone}}` | |
| **Contact LinkedIN** | `{{3.contact_linkedin}}` | |
| **Location City** | `{{3.location_city}}` | |
| **Location State** | `{{3.location_state}}` | |
| **Property City** | `{{3.property_city}}` | |
| **Contact Role** | `{{3.contact_role}}` | |
| **Industry** | `{{3.industry}}` | |
| **Status** | `new` | (hardcode or use `{{3.status}}`) |
| **Source** | `apollo_io` | (hardcode - MUST match select option!) |
| **Referral Link** | `{{3.referral_link}}` | |
| **Channel** | `{{3.channel}}` | (or hardcode `email`) |
| **Notes** | `{{3.notes}}` | |

**IMPORTANT:** 
- Field names must match EXACTLY (case-sensitive!)
- Select fields need exact option values

---

## 🚨 COMMON ISSUES & FIXES

### Issue 1: "Field not found"

**Problem:** Field name doesn't match  
**Fix:** 
- Check exact field name in Airtable
- Match capitalization exactly
- No extra spaces

### Issue 2: "Insufficient permissions to create new select option"

**Problem:** Select field doesn't have the option  
**Fix:** 
- Go to Airtable
- Click on "Source" field
- Add option: `apollo_io`
- Save
- Try again

### Issue 3: "No data in Airtable"

**Problem:** Fields aren't mapped  
**Fix:**
- Check Module 7 has all fields mapped
- Verify Module 3 (Parse JSON) has the data
- Test each module one by one

### Issue 4: "Creates duplicates"

**Problem:** Search formula is wrong  
**Fix:**
- Check Module 4 formula: `{Contact Email} = '{{3.contact_email}}'`
- Make sure "Contact Email" field name matches exactly

---

## ✅ STEP 4: Test the Flow

### Test Each Module:

1. **Module 1 (Apollo.io):**
   - ✅ Returns `people` array
   - ✅ Has person data

2. **Module 2 (OpenAI):**
   - ✅ Receives person data
   - ✅ Returns JSON with all fields

3. **Module 3 (Parse JSON):**
   - ✅ Parses successfully
   - ✅ Has `contact_email`, `contact_full_name`, etc.

4. **Module 4 (Search):**
   - ✅ Searches Airtable by email
   - ✅ Returns 0 or 1 record

5. **Module 7 (Create - if no duplicate):**
   - ✅ Creates new record
   - ✅ Maps all fields correctly

6. **Check Airtable:**
   - ✅ New record appears!
   - ✅ All fields populated!

---

## 📋 QUICK CHECKLIST

**Airtable Setup:**
- [ ] Table created with all required fields
- [ ] "Source" field has `apollo_io` option
- [ ] "Status" field has `new` option
- [ ] "Channel" field has `email` option
- [ ] Field names match exactly (case-sensitive)

**Make.com Modules:**
- [ ] Module 4 searches by `{Contact Email} = '{{3.contact_email}}'`
- [ ] Module 7 maps all fields from Module 3
- [ ] Module 7 uses exact field names from Airtable
- [ ] All select field values match Airtable options

**Test:**
- [ ] Run scenario
- [ ] Check Module 3 output has data
- [ ] Check Module 4 finds/doesn't find duplicate
- [ ] Check Module 7 creates record
- [ ] Verify record in Airtable!

---

## 🎯 EXAMPLE FIELD MAPPING

**In Module 7, your mappings should look like:**

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
Referral Link: {{3.referral_link}}
Channel: email
Notes: {{3.notes}}
```

---

## 💡 TIP: Start Simple

**First, just map these 3 fields:**
1. Contact Email
2. Contact Full Name  
3. Company

**Test if that works, then add more fields!**

---

**Once fields are mapped correctly, data will populate automatically!** 🚀

