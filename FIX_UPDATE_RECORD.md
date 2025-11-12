# 🔧 FIX: Update Record Module (Module 9)

## 🎯 CURRENT CONFIGURATION

**Module 9 (Update Records):**
- **Trigger:** When Module 4 finds a duplicate (Route 2 of Router)
- **Record ID:** `{{4.id}}` (ID of found record)
- **Record fields:** `{}` (Empty - doesn't update anything!)

---

## ❌ PROBLEM IDENTIFIED

**Module 9 has empty `record` field:**
```json
"record": {}
```

**This means:**
- Module 9 finds the record to update ✅
- But doesn't update any fields ❌
- Updates nothing!

---

## ✅ FIX: Add Field Mappings to Update Record

**Module 9 needs to update fields with new data from Module 3.**

### Step 1: Click Module 9 (Update Records)

### Step 2: Find "Record" section

### Step 3: Map these fields (same as Module 6):

**Copy-paste these field mappings:**

**Lead ID:** `{{23.unique_lead_id}}`  
**Status:** `{{3.status}}`  
**Company:** `{{3.company}}`  
**Notes:** `{{3.notes}}`  
**Industry:** `{{3.industry}}`  
**Contact Full Name:** `{{3.contact_full_name}}`  
**Contact Role:** `{{3.contact_role}}`  
**Contact Email:** `{{3.contact_email}}`  
**Contact Phone:** `{{3.contact_phone}}`  
**Contact LinkedIn:** `{{3.contact_linkedin}}`  
**Location City:** `{{3.location_city}}`  
**Location State:** `{{3.location_state}}`  
**Source:** `{{3.source}}`

**OR use Module 6 field IDs:**
- Check Module 6 (Create Record) to see exact field IDs
- Use same mappings in Module 9

---

## 📋 QUICK FIX IN MAKE.COM

### Option 1: Copy from Module 6 (Easiest)

1. **Click Module 6** (Create Record)
2. **Check all field mappings**
3. **Copy them** (take screenshot or note them)
4. **Click Module 9** (Update Records)
5. **Paste same mappings** in "Record" section
6. **Save**

**This ensures Module 9 updates all fields same as Module 6 creates!**

---

### Option 2: Manual Mapping

**In Module 9, add these fields:**

1. **Lead ID:** `{{23.unique_lead_id}}`
2. **Company:** `{{3.company}}`
3. **Contact Full Name:** `{{3.contact_full_name}}`
4. **Contact Email:** `{{3.contact_email}}`
5. **Contact Phone:** `{{3.contact_phone}}`
6. **Contact LinkedIn:** `{{3.contact_linkedin}}`
7. **Location City:** `{{3.location_city}}`
8. **Location State:** `{{3.location_state}}`
9. **Industry:** `{{3.industry}}`
10. **Status:** `{{3.status}}`
11. **Source:** `{{3.source}}`

**Only map fields you want to update!**

---

## 💡 WHAT MODULE 9 SHOULD DO

**When Module 4 finds a duplicate:**
- Module 9 should update the existing record
- Update with latest data from Module 3
- Keep existing data that's not in Module 3

**Example:**
- Existing record has: Name, Email, Phone
- Module 3 has: New Name, New Email, New Phone
- Module 9 updates: Name, Email, Phone with new values

---

## 🎯 RECOMMENDED FIELDS TO UPDATE

**Most important fields to update:**

1. **Contact Email** - In case email was unlocked
2. **Contact Phone** - In case phone number updated
3. **Company** - In case company changed
4. **Status** - To track lead status changes
5. **Location City/State** - If location updated

**Optional:**
- Leave other fields as-is (don't overwrite existing data)
- OR update all fields (replace with new data)

---

## ⚠️ COMMON ISSUES

### Issue 1: Empty Record Field

**Problem:** `"record": {}`  
**Fix:** Add field mappings (see above)

### Issue 2: Wrong Record ID

**Problem:** Using wrong ID field  
**Fix:** Use `{{4.id}}` (ID from Module 4 search results)

### Issue 3: Field IDs Don't Match

**Problem:** Field IDs in Module 9 don't match Airtable  
**Fix:** Use Make.com data mapper to see correct field IDs

---

## 📋 STEP-BY-STEP FIX

1. **Open Make.com scenario**
2. **Click Module 9** (Update Records)
3. **Find "Record" section** (field mappings)
4. **Add fields using data mapper:**
   - Click `{}` icon
   - Navigate to Module 3
   - Select fields to update
5. **Important fields:**
   - Lead ID: `{{23.unique_lead_id}}`
   - Contact Email: `{{3.contact_email}}`
   - Contact Phone: `{{3.contact_phone}}`
   - Company: `{{3.company}}`
6. **Save and test**

---

## ✅ AFTER FIX

**Module 9 should:**
- Find existing record by ID
- Update specified fields with new data
- Keep other fields unchanged (unless mapped)

**Test:**
- Run scenario
- Check if duplicate records get updated
- Verify fields changed in Airtable

---

**What specific error or issue are you seeing with Module 9? Share the error message or what's not working, and I can help fix it!** 🔧

