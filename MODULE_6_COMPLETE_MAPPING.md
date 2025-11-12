# 🔧 FIX: Module 6 Only Mapping One Field

## ❌ THE PROBLEM

**Module 6 input bundle shows:**
```json
{
    "record": {
        "fldjgeXBU1quVB2TB": "new"
    }
}
```

**This means:** Only one field (Status) is mapped!

**All other fields are missing!**

---

## ✅ THE FIX: Map ALL Fields

### In Make.com Module 6 (Create Record):

1. **Click Module 6**
2. **Scroll to "Record" section**
3. **You should see a list of fields from your Airtable table**
4. **For EACH field, click it and map:**

---

## 📋 COMPLETE FIELD MAPPING

**Click on each field in the Record section and enter these values:**

### Core Contact Fields:

1. **Contact Email** (field type: Email)
   - Click field → Enter: `{{3.contact_email}}`

2. **Contact Full Name** (field type: Single line text)
   - Click field → Enter: `{{3.contact_full_name}}`

3. **First Name** (field type: Single line text)
   - Click field → Enter: `{{3.first_name}}`

4. **Company** (field type: Single line text)
   - Click field → Enter: `{{3.company}}`

5. **Contact Phone** (field type: Phone number)
   - Click field → Enter: `{{3.contact_phone}}`

6. **Contact LinkedIN** (field type: URL)
   - Click field → Enter: `{{3.contact_linkedin}}`

7. **Contact Role** (field type: Single line text)
   - Click field → Enter: `{{3.contact_role}}`

### Location Fields:

8. **Location City** (field type: Single line text)
   - Click field → Enter: `{{3.location_city}}`

9. **Location State** (field type: Single line text)
   - Click field → Enter: `{{3.location_state}}`

10. **Property City** (field type: Single line text)
    - Click field → Enter: `{{3.property_city}}`

### Status & Source:

11. **Status** (field type: Single select)
    - Click field → Enter: `new`
    - OR: `{{3.status}}` (if you want to use Module 3 value)

12. **Source** (field type: Single select)
    - Click field → Enter: `apollo_io`
    - **CRITICAL:** Must be exact value that exists in Airtable!

13. **Channel** (field type: Single select)
    - Click field → Enter: `email`
    - OR: `{{3.channel}}`

### Additional Fields:

14. **Industry** (field type: Single line text)
    - Click field → Enter: `{{3.industry}}`

15. **Referral Link** (field type: URL)
    - Click field → Enter: `{{3.referral_link}}`

16. **Notes** (field type: Long text)
    - Click field → Enter: `{{3.notes}}`

17. **Lead ID** (field type: Single line text)
    - Click field → Enter: `{{3.lead_id}}`

18. **Acquired At** (field type: Date)
    - Click field → Enter: `{{3.acquired_at}}`

19. **UTM List ID** (field type: Single line text)
    - Click field → Enter: `{{3.utm_list_id}}`

20. **Tags** (field type: Multiple select)
    - Click field → Enter: `{{3.tags}}`
    - Note: This might need special formatting for arrays

---

## 🔍 HOW TO SEE ALL FIELDS IN MODULE 6

**In Make.com:**

1. **Click Module 6**
2. **Look for "Record" section** (usually a list or grid)
3. **If you don't see all fields:**
   - Click "Add field" or "+"
   - Select fields from your Airtable table
   - Then map each one

**If fields are collapsed/hidden:**
- Look for expand/collapse buttons
- Click to expand all fields
- You should see all fields from your Airtable table

---

## 💡 IMPORTANT NOTES

### Field Names Must Match

**Your Airtable has fields like:**
- `Contact Email`
- `Contact Full Name`
- `Company`
- etc.

**Module 6 should show these exact field names** (not IDs like `fldjgeXBU1quVB2TB`)

**If you see field IDs instead of names:**
- Make.com might be using Column IDs
- Try unchecking "Use Column ID" if there's an option
- Or manually select fields by name

### Select Fields Need Exact Values

**For "Source" field:**
- Must enter: `apollo_io` (exact, lowercase, underscore)
- Not: "Apollo.io" or "apollo io" or "Apollo IO"

**For "Status" field:**
- Must enter: `new` (exact value)
- Check what options exist in Airtable

**For "Channel" field:**
- Must enter: `email` (exact value)
- Or whatever options you have in Airtable

---

## 🧪 TEST AFTER MAPPING

1. **Map all fields above**
2. **Click "OK" to save**
3. **Run scenario**
4. **Check Module 6 input bundle again:**
   - Should show ALL fields mapped
   - Not just one field
5. **Check Airtable:**
   - New record should have ALL fields populated!

---

## 📊 EXPECTED INPUT BUNDLE (After Fix)

**Module 6 input should look like:**
```json
{
    "base": "appKMaYEwkkH5bCSY",
    "table": "tblxnRcBS21l0VTgW",
    "record": {
        "Contact Email": "{{3.contact_email}}",
        "Contact Full Name": "{{3.contact_full_name}}",
        "First Name": "{{3.first_name}}",
        "Company": "{{3.company}}",
        "Contact Phone": "{{3.contact_phone}}",
        "Location City": "{{3.location_city}}",
        "Location State": "{{3.location_state}}",
        "Status": "new",
        "Source": "apollo_io",
        ...
    }
}
```

**Not just one field!**

---

## 🚨 IF YOU CAN'T SEE ALL FIELDS

**Problem:** Module 6 only shows one or a few fields

**Fixes:**

1. **Check "Use Column ID" setting:**
   - Uncheck it if checked
   - This might show field names instead of IDs

2. **Manually add fields:**
   - Look for "Add field" button
   - Click and select from your Airtable fields
   - Add each field you need

3. **Refresh Airtable connection:**
   - Disconnect and reconnect Airtable
   - This refreshes field list

4. **Check Airtable permissions:**
   - Make sure Make.com has access to all fields
   - Check Airtable base permissions

---

## ✅ CHECKLIST

- [ ] Module 6 shows all Airtable fields (not just one)
- [ ] Each field is mapped from `{{3.field_name}}`
- [ ] Field names match exactly (case-sensitive)
- [ ] Select fields use exact values (`apollo_io`, `new`, `email`)
- [ ] Test run shows multiple fields in input bundle
- [ ] Airtable record has all fields populated

---

**Map all these fields and your Airtable will populate completely!** 🚀

