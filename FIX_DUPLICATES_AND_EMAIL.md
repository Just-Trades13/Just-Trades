# 🔧 FIX: Same Leads & Locked Emails

## 🎯 TWO ISSUES TO FIX

### Issue 1: Getting Same Lead Over and Over
**Problem:** Apollo.io returns the same person every time  
**Solution:** Change search criteria or use pagination

### Issue 2: Locked Email Field
**Problem:** `email_not_unlocked@domain.com` is Apollo.io's placeholder  
**Solution:** Filter these out or unlock emails

---

## ✅ FIX 1: Get Different Leads (Stop Duplicates)

### Option A: Use Random Page Number (RECOMMENDED)

**In Module 1 (Apollo.io "Make an API Call"):**

**Current Body:**
```json
{
  "person_locations": ["California"],
  "page": 1,
  "per_page": 1
}
```

**Change to:**
```json
{
  "person_locations": ["California"],
  "page": {{random(1; 10)}},
  "per_page": 1
}
```

**OR use Make.com's random function:**
- In Make.com, use: `{{random(1; 100)}}` for page number
- This gets a random page each time

**Problem:** Make.com might not have `random()` function

**Better Solution:** Use different search criteria each time

### Option B: Vary Search Locations

**Change body to cycle through states:**

**Option 1 - California:**
```json
{
  "person_locations": ["California"],
  "page": 1,
  "per_page": 1
}
```

**Option 2 - Texas:**
```json
{
  "person_locations": ["Texas"],
  "page": 1,
  "per_page": 1
}
```

**Option 3 - Florida:**
```json
{
  "person_locations": ["Florida"],
  "page": 1,
  "per_page": 1
}
```

**Better:** Use multiple locations and increase per_page

### Option C: Get More Results Per Run

**Change to get multiple leads at once:**

**Body:**
```json
{
  "person_locations": ["California"],
  "page": 1,
  "per_page": 10
}
```

**Then modify Module 2 to process each person:**
- Use Iterator module to loop through people array
- Process each person separately

**Simplest:** Just increase `per_page` to 10, then handle duplicates in Module 4

---

## ✅ FIX 2: Filter Locked Emails

### Option A: Filter in Module 5 Router (RECOMMENDED)

**Add a filter before creating record:**

**In Module 5 (Router), add another route:**

**Current:** 
- Route 1 (If): No duplicate → Create
- Route 2 (Else): Duplicate → Update

**Add:**
- Route 3: If email is locked → Skip/Don't create

**Or filter in Module 6 condition:**

**In Module 6 (Create Record), add filter:**

**Filter condition:**
```
{{3.contact_email}} != "email_not_unlocked@domain.com" AND 
{{3.contact_email}} != "" AND 
{{3.contact_email}} CONTAINS "@" AND 
LENGTH({{3.contact_email}}) > 10
```

**This skips records with locked emails!**

### Option B: Filter in Module 3 (Parse JSON)

**Not recommended** - but you could modify the OpenAI prompt to skip locked emails

### Option C: Update Module 4 Search to Skip Locked Emails

**In Module 4 (Search), update formula:**

**Current:**
```
{Contact Email} = '{{3.contact_email}}'
```

**Change to also filter locked:**
```
AND({Contact Email} = '{{3.contact_email}}', {Contact Email} != 'email_not_unlocked@domain.com')
```

**Actually, better to skip in Module 6 before creating!**

---

## 🎯 RECOMMENDED FIX

### Fix 1: Get Different Leads

**In Module 1, change body to:**

```json
{
  "person_locations": ["California", "Texas", "Florida", "Arizona", "Nevada"],
  "page": 1,
  "per_page": 5
}
```

**This gets 5 different leads per run from different states!**

**OR cycle through pages manually:**
- Run 1: page 1
- Run 2: page 2
- Run 3: page 3
- etc.

**OR use different keywords each time:**
```json
{
  "q_keywords": "real estate agent",
  "person_locations": ["California"],
  "page": 1,
  "per_page": 1
}
```

**Change keywords each run:**
- "real estate agent"
- "property manager"
- "construction manager"
- "homeowner"
- etc.

### Fix 2: Skip Locked Emails

**In Module 5 Router, add filter BEFORE Create:**

**Modify Module 6 filter condition:**

**Add to Module 6 "Filter" (if it has one) or Router:**

**New Router Route:**
- **Route 1:** If email is valid → Create (Module 6)
- **Route 2:** If email is locked → Skip (do nothing)
- **Route 3:** If duplicate → Update (Module 7)

**Email validation condition:**
```
{{3.contact_email}} != "email_not_unlocked@domain.com" AND 
{{3.contact_email}} != "" AND 
{{3.contact_email}} CONTAINS "@"
```

---

## 📋 STEP-BY-STEP: Fix Duplicates

### Step 1: Update Module 1 Search

**Option A - Multiple locations:**
```json
{
  "person_locations": ["California", "Texas", "Florida"],
  "page": 1,
  "per_page": 5
}
```

**Option B - Different page each time:**
- Manually change page number: 1, 2, 3, 4...
- OR use different keywords

**Option C - Increase results:**
```json
{
  "person_locations": ["California"],
  "page": 1,
  "per_page": 10
}
```

### Step 2: Add Email Filter

**In Module 5 Router, add condition:**

**Route 1 (Create - Valid Email):**
- Condition: `{{3.contact_email}} != "email_not_unlocked@domain.com" AND {{4.`__IMTLENGTH__`}} = 0`
- Goes to: Module 6 (Create)

**Route 2 (Skip - Locked Email):**
- Condition: `{{3.contact_email}} = "email_not_unlocked@domain.com"`
- Goes to: Nothing (skip)

**Route 3 (Update - Duplicate):**
- Condition: `{{4.`__IMTLENGTH__`}} >= 1`
- Goes to: Module 7 (Update)

---

## 🔍 UNDERSTANDING LOCKED EMAILS

**Apollo.io has two types of emails:**
1. **Unlocked:** Real email address (e.g., `john@example.com`)
2. **Locked:** Placeholder (`email_not_unlocked@domain.com`)

**To unlock emails:**
- Costs Apollo.io credits
- Need paid plan
- Can unlock in bulk

**For now:** Just skip locked emails!

---

## ✅ QUICK FIX (SIMPLEST)

### Fix Duplicates:

**In Module 1, change:**
```json
{
  "person_locations": ["California"],
  "page": 1,
  "per_page": 5
}
```

**Then manually change page each run:**
- Run 1: `"page": 1`
- Run 2: `"page": 2`
- Run 3: `"page": 3`
- etc.

### Fix Locked Emails:

**In Module 6, add filter condition:**

**Filter:**
```
{{3.contact_email}} != "email_not_unlocked@domain.com"
```

**This prevents creating records with locked emails!**

---

## 🎯 EXPECTED RESULT

**After fixes:**
- ✅ Gets different leads each run
- ✅ Skips locked emails
- ✅ Only creates records with real emails
- ✅ No duplicates (Module 4 already handles this)

---

**Make these two changes and it will work perfectly!** 🚀

