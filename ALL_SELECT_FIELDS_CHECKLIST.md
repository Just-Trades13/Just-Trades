# ✅ COMPLETE SELECT FIELD CHECKLIST

## 🔴 ERRORS YOU'VE HIT

1. ✅ **Industry:** "real_estate" - FIXED (you added it)
2. ❌ **Source:** "apollo_io" - NEED TO ADD NOW

---

## 📋 ALL SELECT FIELDS TO CONFIGURE

### 1. Industry Field ⚠️

**Your CSV shows:** retail, finance, other  
**Module 3 outputs:** real_estate, construction

**Add these options:**
- ✅ `real_estate` (you added this)
- `construction`

**Steps:**
1. Click "Industry" field in Airtable
2. Add option: `construction`
3. Save

---

### 2. Source Field 🔴 CURRENT ISSUE

**Your CSV shows:** linkedin  
**Module 6 uses:** apollo_io

**Add this option:**
- ❌ `apollo_io` ← **ADD THIS NOW!**

**Steps:**
1. Click "Source" field in Airtable
2. Add option: `apollo_io`
   - **IMPORTANT:** Use exact spelling: `apollo_io`
   - Lowercase, underscore (not "Apollo.io" or "apollo io")
3. Save
4. Run scenario again

---

### 3. Status Field ⚠️

**Your CSV shows:** emailed  
**Module 6 uses:** new (or `{{3.status}}`)

**Check if "new" exists:**
- If YES → ✅ Good!
- If NO → Either:
  - Add option `new` to Status field
  - OR change Module 6 to use `emailed` instead

**To add "new":**
1. Click "Status" field
2. Add option: `new`
3. Save

**OR change Module 6:**
- Instead of: `Status → new`
- Use: `Status → emailed`

---

### 4. Tags Field (If Multiple Select)

**Your CSV shows:** retail, finance, director, technology  
**Module 3 outputs:** heloc_prospect, high_priority, real_estate

**If Tags is a Select field, add:**
- `heloc_prospect`
- `high_priority`
- `real_estate`
- `construction`
- `home_owner`
- `property_owner`
- `finance`

**If Tags is a Text field:**
- ✅ No options needed, can accept any value

---

## 🚀 QUICK FIX ORDER

**Do these in order:**

1. **Source field** ← DO THIS FIRST (current error)
   - Add: `apollo_io`

2. **Check Status field**
   - Verify `new` exists OR change Module 6 to `emailed`

3. **Check Industry field**
   - Add `construction` if missing

4. **Test scenario**

---

## ✅ VERIFICATION

**After adding options, check:**

- [ ] Source field has `apollo_io` option ✅
- [ ] Industry field has `real_estate` option ✅
- [ ] Status field has `new` option (or Module 6 uses `emailed`)
- [ ] Run scenario - no 422 errors!

---

## 🎯 EXPECTED RESULT

**After fixing Source field:**
- Scenario should run successfully
- Record should create in Airtable
- All fields should populate!

---

**Add "apollo_io" to Source field and you're done!** 🚀

