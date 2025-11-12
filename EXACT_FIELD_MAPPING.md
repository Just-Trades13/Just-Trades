# ✅ EXACT FIELD MAPPING - Module 3 → Airtable

## 🎉 GOOD NEWS!

**Module 3 output is PERFECT!** All data is there:
- ✅ contact_email
- ✅ contact_full_name
- ✅ first_name
- ✅ company
- ✅ contact_phone
- ✅ location_city
- ✅ location_state
- ✅ contact_role
- ✅ industry
- ✅ etc.

**The problem:** Module 6 isn't mapping these fields to Airtable!

---

## 🔧 FIX: Module 6 Field Mappings

### In Make.com Module 6 (Airtable Create Record):

**Scroll to "Record" section and map EXACTLY like this:**

| Airtable Field | Map From Module 3 | Value |
|----------------|-------------------|-------|
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
| **Status** | `new` | (hardcode) |
| **Source** | `apollo_io` | (hardcode) |
| **Referral Link** | `{{3.referral_link}}` | |
| **Channel** | `email` | (hardcode or `{{3.channel}}`) |
| **Notes** | `{{3.notes}}` | |
| **Lead ID** | `{{3.lead_id}}` | |
| **Acquired At** | `{{3.acquired_at}}` | |
| **UTM List ID** | `{{3.utm_list_id}}` | |

**Optional (if available):**
- **Tags** | `{{3.tags}}` | (array)
- **Estimated Equity** | `{{3.estimated_equity}}` | (if number)

---

## 📋 STEP-BY-STEP: Configure Module 6

### Step 1: Open Module 6

1. Click **Module 6** (Airtable Create Record)
2. Make sure it's in the **"If" path** from Router (no duplicate found)

### Step 2: Configure Base/Table

1. **Connection:** Your Airtable connection
2. **Base:** Your base (where you imported CSV)
3. **Table:** Your table

### Step 3: Map Record Fields

**Click on each field in the "Record" section and enter:**

#### Essential Fields (Must Map):

1. **Contact Email:**
   - Click field
   - Enter: `{{3.contact_email}}`

2. **Contact Full Name:**
   - Click field
   - Enter: `{{3.contact_full_name}}`

3. **First Name:**
   - Click field
   - Enter: `{{3.first_name}}`

4. **Company:**
   - Click field
   - Enter: `{{3.company}}`

5. **Contact Phone:**
   - Click field
   - Enter: `{{3.contact_phone}}`

6. **Contact LinkedIN:**
   - Click field
   - Enter: `{{3.contact_linkedin}}`

7. **Location City:**
   - Click field
   - Enter: `{{3.location_city}}`

8. **Location State:**
   - Click field
   - Enter: `{{3.location_state}}`

9. **Property City:**
   - Click field
   - Enter: `{{3.property_city}}`

10. **Contact Role:**
    - Click field
    - Enter: `{{3.contact_role}}`

11. **Industry:**
    - Click field
    - Enter: `{{3.industry}}`

12. **Status:**
    - Click field
    - Enter: `new` (hardcode, or use `{{3.status}}`)

13. **Source:**
    - Click field
    - Enter: `apollo_io` (hardcode - must match Airtable option!)

14. **Referral Link:**
    - Click field
    - Enter: `{{3.referral_link}}`

15. **Channel:**
    - Click field
    - Enter: `email` (hardcode, or `{{3.channel}}`)

16. **Notes:**
    - Click field
    - Enter: `{{3.notes}}`

### Step 4: Click "OK"

---

## 🚨 IMPORTANT NOTES

### Field Names Must Match EXACTLY!

**Your Airtable fields (from CSV):**
- `Contact Email` (with space, capital C and E)
- `Contact Full Name` (with spaces)
- `First Name` (with space)

**Module 3 fields:**
- `contact_email` (lowercase, underscore)
- `contact_full_name` (lowercase, underscore)
- `first_name` (lowercase, underscore)

**The mapping connects them:**
- Airtable "Contact Email" ← mapped from → `{{3.contact_email}}`

**Make sure field names in Airtable match the CSV headers exactly!**

---

## ✅ VERIFICATION

### After Mapping, Test:

1. **Run scenario**
2. **Check Module 6 input bundle:**
   - Should show all fields mapped
   - Values should show actual data (not empty)
3. **Check Airtable:**
   - New record created?
   - Fields populated?

---

## 🔍 IF STILL BLANK

### Check 1: Field Names

**In Airtable, check exact field names:**
- Case-sensitive!
- Spaces matter!
- Must match CSV headers exactly

### Check 2: Select Field Options

**Make sure these options exist in Airtable:**
- **Status field:** Has option `new`
- **Source field:** Has option `apollo_io`
- **Channel field:** Has option `email`

### Check 3: Module 6 Mappings

**Verify mappings show actual values:**
- Not empty
- Using `{{3.field_name}}` format
- Field names match Module 3 output

---

## 📊 YOUR DATA EXAMPLE

**From your Module 3 output, this should map to:**

```
Contact Email: email_not_unlocked@domain.com
Contact Full Name: Tony Robbins
First Name: Tony
Company: Robbins Research International
Contact Phone: +18585359900
Contact LinkedIN: http://www.linkedin.com/in/officialtonyrobbins
Location City: San Diego
Location State: CA
Property City: San Diego
Contact Role: Chairman
Industry: real_estate
Status: new
Source: apollo_io
Referral Link: https://axenmortgageheloc.com/account/heloc/register-v2?referrer=55ac77e7-8bb0-48c5-92a8-65960f3efe42
Channel: email
Tags: heloc_prospect, high_priority, real_estate
Notes: (empty in this case)
```

**This is what should appear in Airtable!**

---

**Map all these fields in Module 6 and it will work!** 🚀

