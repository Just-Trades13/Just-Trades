# 🔧 EXACT FIX: Module 9 (Update Record) Field Mappings

## ❌ PROBLEMS IN YOUR SCREENSHOT

**Wrong data sources being used:**

1. **Lead ID:** Using `4. ID` (Airtable record ID)  
   → **Should be:** `23. unique_lead_id` (unique Lead ID)

2. **Company:** Using `21. organization: name` (raw Apollo data)  
   → **Should be:** `3. Company` (processed data)

3. **Contact Full Name:** Using `21. name` (raw Apollo data)  
   → **Should be:** `3. Contact full name` (processed data)

4. **Contact Role:** Using `21. title` (raw Apollo data)  
   → **Should be:** `3. Contact role` (processed data)

5. **Contact Email:** Using `21. email` (raw Apollo data)  
   → **Should be:** `3. Contact email` (processed data)

6. **Contact Phone:** Empty ❌  
   → **Should be:** `3. Contact phone`

---

## ✅ CORRECT FIELD MAPPINGS

### Update Each Field in Module 9:

**Click each field and change to these:**

1. **Lead ID:** 
   - **Change from:** `4. ID`
   - **Change to:** `23. unique_lead_id`
   - **Source:** Tools - Set variable (Module 23)

2. **Company:**
   - **Change from:** `21. organization: name`
   - **Change to:** `3. Company`
   - **Source:** {} JSON - Parse JSON (Module 3)

3. **Contact Full Name:**
   - **Change from:** `21. name`
   - **Change to:** `3. Contact full name`
   - **Source:** {} JSON - Parse JSON (Module 3)

4. **Contact Role:**
   - **Change from:** `21. title`
   - **Change to:** `3. Contact role`
   - **Source:** {} JSON - Parse JSON (Module 3)

5. **Contact Email:**
   - **Change from:** `21. email`
   - **Change to:** `3. Contact email`
   - **Source:** {} JSON - Parse JSON (Module 3)

6. **Contact Phone:**
   - **Currently:** Empty
   - **Add:** `3. Contact phone`
   - **Source:** {} JSON - Parse JSON (Module 3)

7. **Contact LinkedIn:**
   - **Currently:** Empty
   - **Add:** `3. Contact linkedin`
   - **Source:** {} JSON - Parse JSON (Module 3)

8. **Location City:**
   - **Currently:** Empty
   - **Add:** `3. Location city`
   - **Source:** {} JSON - Parse JSON (Module 3)

**Keep these (already correct):**
- ✅ **Status:** `3. Status` ✓
- ✅ **Notes:** `3. Notes` ✓
- ✅ **Industry:** `3. Industry` ✓
- ✅ **Location State:** (if mapped correctly)

---

## 📋 STEP-BY-STEP IN MAKE.COM

### Step 1: Open Module 9

1. **Click Module 9** (Update Records)
2. **Find "Record" section**
3. **Click on each field** to update

### Step 2: Fix Lead ID

1. **Click "Lead ID" field**
2. **Click the data mapper icon** `{}`
3. **Navigate to:** "Tools - Set variable" (Module 23)
4. **Select:** `unique_lead_id`
5. **Click OK**

### Step 3: Fix Company

1. **Click "Company" field**
2. **Clear current value** (`21. organization: name`)
3. **Click data mapper icon** `{}`
4. **Navigate to:** "{} JSON - Parse JSON" (Module 3)
5. **Select:** `Company`
6. **Click OK**

### Step 4: Fix Contact Full Name

1. **Click "Contact Full Name" field**
2. **Clear current value** (`21. name`)
3. **Click data mapper icon** `{}`
4. **Navigate to:** "{} JSON - Parse JSON" (Module 3)
5. **Select:** `Contact full name`
6. **Click OK**

### Step 5: Fix Contact Role

1. **Click "Contact Role" field**
2. **Clear current value** (`21. title`)
3. **Click data mapper icon** `{}`
4. **Navigate to:** "{} JSON - Parse JSON" (Module 3)
5. **Select:** `Contact role`
6. **Click OK**

### Step 6: Fix Contact Email

1. **Click "Contact Email" field**
2. **Clear current value** (`21. email`)
3. **Click data mapper icon** `{}`
4. **Navigate to:** "{} JSON - Parse JSON" (Module 3)
5. **Select:** `Contact email`
6. **Click OK**

### Step 7: Add Contact Phone

1. **Click "Contact Phone" field** (if empty, find it or add it)
2. **Click data mapper icon** `{}`
3. **Navigate to:** "{} JSON - Parse JSON" (Module 3)
4. **Select:** `Contact phone`
5. **Click OK**

### Step 8: Add Other Missing Fields

**Repeat for:**
- **Contact LinkedIn:** `3. Contact linkedin`
- **Location City:** `3. Location city`
- **Location State:** `3. Location state` (if not already correct)

### Step 9: Save

1. **Click "OK" to save Module 9**
2. **Test the scenario**

---

## 🎯 QUICK REFERENCE

**All fields should use Module 3 (Parse JSON), except:**

- **Lead ID:** Use `23. unique_lead_id` (Module 23)
- **Record ID:** Use `4. ID` (Module 4 - for identifying which record to update)

**Everything else:** Use `3. [field name]` from Module 3!

---

## ✅ AFTER FIX

**Module 9 will:**
- ✅ Update Lead ID correctly (unique ID with timestamp)
- ✅ Update all contact info from processed data
- ✅ Refresh records with latest information
- ✅ No more missing fields!

---

**Follow these steps in Make.com to fix Module 9!** 🔧

