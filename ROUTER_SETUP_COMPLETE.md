# ✅ ROUTER (MODULE 5) - Complete Setup Guide

## 🎯 HOW THE ROUTER WORKS

**Module 5 (Router) decides:**
- **Route 1:** If no duplicate found → Create new record (Module 6/7)
- **Route 2:** If duplicate found → Update existing record (Module 9)

**The decision is based on Module 4's search results!**

---

## ✅ CORRECT CONDITIONS

### Route 1: Create New Lead (No Duplicate)

**Condition Type:** Filter/If
**Field:** `{{4.__IMTLENGTH__}}`
**Operator:** `equals` or `=`
**Value:** `0`
**Data Type:** `number`

**Full condition:**
```
{{4.__IMTLENGTH__}} equals 0
```

**Meaning:** Module 4 found 0 records → No duplicate → Create new

**Connection:** Goes to Module 6 (Create Record)

---

### Route 2: Update Existing Lead (Duplicate Found)

**Condition Type:** Filter/Else
**Field:** `{{4.__IMTLENGTH__}}`
**Operator:** `>=` or `greater than or equal`
**Value:** `1`
**Data Type:** `number`

**Full condition:**
```
{{4.__IMTLENGTH__}} >= 1
```

**OR:**
```
{{4.__IMTLENGTH__}} > 0
```

**Meaning:** Module 4 found 1+ records → Duplicate exists → Update

**Connection:** Goes to Module 9 (Update Record)

---

## 📋 STEP-BY-STEP IN MAKE.COM

### Step 1: Open Module 5 (Router)

1. **Click Module 5** (Router)
2. **You should see "Routes" section**

### Step 2: Configure Route 1 (Create New Lead)

1. **Click on Route 1** (or "Add Route")
2. **Name:** "Create New Lead" or "No Duplicate"
3. **Click "Add filter" or "Set condition"**

4. **Configure filter:**
   - **Field:** Click `{}` → Navigate to Module 4
   - **Select:** `__IMTLENGTH__` or "Total number of bundles"
   - **Operator:** Select `equals` or `=`
   - **Value:** Type `0`
   - **Data Type:** Select `number` (important!)

5. **Condition should read:**
   ```
   {{4.__IMTLENGTH__}} equals 0
   ```

6. **Connect Route 1 to:** Module 6 or Module 7 (Create Record)

### Step 3: Configure Route 2 (Update Existing Lead)

1. **Click on Route 2** (or "Add Route")
2. **Name:** "Update Existing Lead" or "Duplicate Found"
3. **Click "Add filter" or "Set condition"**

4. **Configure filter:**
   - **Field:** Click `{}` → Navigate to Module 4
   - **Select:** `__IMTLENGTH__` or "Total number of bundles"
   - **Operator:** Select `>=` or `greater than or equal`
   - **Value:** Type `1`
   - **Data Type:** Select `number` (important!)

5. **Condition should read:**
   ```
   {{4.__IMTLENGTH__}} >= 1
   ```

6. **Connect Route 2 to:** Module 9 (Update Record)

---

## ⚠️ CRITICAL: Data Type Must Be Number!

**If you get errors:**
- Make sure data type is `number`, not `text`
- `__IMTLENGTH__` returns a number (0, 1, 2, etc.)
- Using `text` comparison might not work correctly

---

## 🔄 ALTERNATIVE CONDITIONS (If __IMTLENGTH__ Doesn't Work)

### Option 1: Use ID Field

**Route 1 (Create):**
```
{{4.id}} is empty
```

**Route 2 (Update):**
```
{{4.id}} is not empty
```

**This checks if Module 4 found a record ID.**

---

### Option 2: Use ID Length

**Route 1 (Create):**
```
LENGTH({{4.id}}) = 0
```

**Route 2 (Update):**
```
LENGTH({{4.id}}) > 0
```

---

## 🎯 EXACT SETUP IN MAKE.COM ROUTER

**In Make.com Router interface:**

### Route 1 Configuration:
```
┌─────────────────────────────────────┐
│ Route Name: Create New Lead          │
├─────────────────────────────────────┤
│ Filter:                              │
│   {{4.__IMTLENGTH__}} equals 0       │
│   (Type: number)                     │
├─────────────────────────────────────┤
│ Connect to: Module 6 (Create Record) │
└─────────────────────────────────────┘
```

### Route 2 Configuration:
```
┌─────────────────────────────────────┐
│ Route Name: Update Existing Lead    │
├─────────────────────────────────────┤
│ Filter:                              │
│   {{4.__IMTLENGTH__}} >= 1           │
│   (Type: number)                     │
├─────────────────────────────────────┤
│ Connect to: Module 9 (Update Record) │
└─────────────────────────────────────┘
```

---

## ✅ VERIFICATION

**After setup, test:**

1. **Run scenario with new lead** (should not exist in Airtable)
   - Module 4 should find 0 records
   - Router should go to Route 1 (Create)
   - Module 6 should execute
   - New record created ✅

2. **Run scenario with duplicate** (should already exist)
   - Module 4 should find 1+ records
   - Router should go to Route 2 (Update)
   - Module 9 should execute
   - Record updated ✅

---

## 📋 CHECKLIST

- [ ] Route 1 condition: `{{4.__IMTLENGTH__}} equals 0` (number type)
- [ ] Route 1 connects to: Module 6 (Create Record)
- [ ] Route 2 condition: `{{4.__IMTLENGTH__}} >= 1` (number type)
- [ ] Route 2 connects to: Module 9 (Update Record)
- [ ] Data type is `number`, not `text`
- [ ] Both routes configured correctly

---

## 💡 TROUBLESHOOTING

### If Router Always Goes to Route 1:
- Check if `__IMTLENGTH__` is actually 0
- Check Module 4 output - did it find records?
- Verify Module 4 search formula is correct

### If Router Always Goes to Route 2:
- Check if `__IMTLENGTH__` is actually >= 1
- Module 4 might be finding duplicates incorrectly
- Check Module 4 search formula

### If Router Goes to Wrong Route:
- Check data type (must be `number`)
- Check operator (equals vs >=)
- Check value (0 vs 1)

---

**Follow these exact conditions in Make.com Router, and it should work perfectly!** 🔧

