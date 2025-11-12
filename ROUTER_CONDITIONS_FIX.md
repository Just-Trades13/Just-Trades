# 🔧 FIX: Router (Module 5) Conditions

## 🎯 CURRENT ROUTER SETUP

**Module 5 (Router) has 2 routes:**

1. **Route 1:** "Create New Lead"
   - **Condition:** `{{4.__IMTLENGTH__}} = 0`
   - **Action:** Goes to Module 6 (Create Record)
   - **Meaning:** If Module 4 found NO records → Create new

2. **Route 2:** "Update Existing Lead"
   - **Condition:** `{{4.__IMTLENGTH__}} >= 1`
   - **Action:** Goes to Module 9 (Update Record)
   - **Meaning:** If Module 4 found 1+ records → Update existing

---

## ✅ CORRECT CONDITIONS

### Route 1: Create New Lead (No Duplicate Found)

**Condition:**
```
{{4.__IMTLENGTH__}} = 0
```

**OR:**
```
{{4.__IMTLENGTH__}} is empty
```

**OR:**
```
{{4.__IMTLENGTH__}} equals 0
```

**This means:** Module 4 found 0 records → No duplicate → Create new record

---

### Route 2: Update Existing Lead (Duplicate Found)

**Condition:**
```
{{4.__IMTLENGTH__}} >= 1
```

**OR:**
```
{{4.__IMTLENGTH__}} > 0
```

**OR:**
```
{{4.__IMTLENGTH__}} is not empty
```

**This means:** Module 4 found 1+ records → Duplicate exists → Update record

---

## 📋 STEP-BY-STEP: Fix Router in Make.com

### Step 1: Open Module 5 (Router)

1. **Click Module 5** (Router)
2. **You should see 2 routes**

### Step 2: Check Route 1 (Create New Lead)

1. **Click Route 1** (should be named "Create New Lead")
2. **Check the filter/condition:**
   - **Field:** `{{4.__IMTLENGTH__}}`
   - **Operator:** `equals` or `=`
   - **Value:** `0`
3. **Should read:** `{{4.__IMTLENGTH__}} equals 0`
4. **If different, change it to this!**

### Step 3: Check Route 2 (Update Existing Lead)

1. **Click Route 2** (should be named "Update Existing Lead")
2. **Check the filter/condition:**
   - **Field:** `{{4.__IMTLENGTH__}}`
   - **Operator:** `>=` or `greater than or equal`
   - **Value:** `1`
3. **Should read:** `{{4.__IMTLENGTH__}} >= 1` or `{{4.__IMTLENGTH__}} greater than or equal 1`
4. **If different, change it to this!**

### Step 4: Verify Routes Connect Correctly

**Route 1 (Create):**
- Should connect to Module 6 (Create Record)

**Route 2 (Update):**
- Should connect to Module 9 (Update Record)

---

## ⚠️ COMMON ISSUES

### Issue 1: Wrong Field in Condition

**Problem:** Using `{{4.id}}` instead of `{{4.__IMTLENGTH__}}`

**Fix:** 
- Use `__IMTLENGTH__` (total number of bundles)
- This tells you HOW MANY records were found
- `id` just gives you the record ID

### Issue 2: Wrong Operator

**Problem:** Using `is empty` or `is not empty`

**Fix:**
- Route 1: Use `equals 0` or `= 0`
- Route 2: Use `>= 1` or `> 0`

### Issue 3: Conditions Reversed

**Problem:** Route 1 checks for `>= 1`, Route 2 checks for `= 0`

**Fix:** Swap the conditions!

---

## 🎯 EXACT CONDITIONS TO USE

### Route 1: Create New Lead

**In Make.com Router:**
- **Condition type:** "If/Else" or "Filter"
- **Field:** `{{4.__IMTLENGTH__}}`
- **Operator:** `equals` or `=`
- **Value:** `0`
- **Connection:** Module 6 (Create Record)

### Route 2: Update Existing Lead

**In Make.com Router:**
- **Condition type:** "Else" or "Otherwise"
- **Field:** `{{4.__IMTLENGTH__}}`
- **Operator:** `>=` or `greater than or equal`
- **Value:** `1`
- **Connection:** Module 9 (Update Record)

---

## ✅ ALTERNATIVE CONDITIONS

**If `__IMTLENGTH__` doesn't work, try:**

### Route 1 (Create):
```
{{4.id}} is empty
```
OR
```
{{4.ID}} is empty
```

### Route 2 (Update):
```
{{4.id}} is not empty
```
OR
```
{{4.ID}} is not empty
```

**These check if Module 4 found a record ID (which means it found a duplicate).**

---

## 📋 VERIFICATION CHECKLIST

- [ ] Route 1 condition: `{{4.__IMTLENGTH__}} = 0`
- [ ] Route 1 connects to: Module 6 (Create Record)
- [ ] Route 2 condition: `{{4.__IMTLENGTH__}} >= 1`
- [ ] Route 2 connects to: Module 9 (Update Record)
- [ ] Conditions are not reversed
- [ ] Both routes are configured

---

## 💡 TEST THE ROUTER

**Run scenario and check:**

1. **Execution log:**
   - Does Route 1 execute when no duplicate?
   - Does Route 2 execute when duplicate found?

2. **Module 4 output:**
   - Check `__IMTLENGTH__` value
   - If `0` → Should go to Route 1 (Create)
   - If `1` or more → Should go to Route 2 (Update)

3. **Module 6 vs Module 9:**
   - New leads → Should execute Module 6
   - Duplicate leads → Should execute Module 9

---

**Share what you see in the Router conditions, and I'll help you fix them exactly!** 🔧

