# 🔧 FIX: All Emails Show as "Locked"

## ❌ PROBLEM

**All leads have emails like:**
- `email_not_unlocked@domain.com`
- `email_not_unlocked@boxerproperty.com`
- etc.

**This is Apollo.io's placeholder for locked emails.**

---

## 🎯 WHY THIS HAPPENS

**Apollo.io locks email addresses:**
- Free/low-tier plans: Most emails are locked
- Locked emails require credits to unlock
- Cost: ~$0.10 - $0.50 per email unlock
- Apollo shows placeholder: `email_not_unlocked@domain.com`

**This is NOT a blueprint error - it's Apollo.io's business model!**

---

## ✅ SOLUTION OPTIONS

### Option 1: Filter Out Locked Emails (BEST)

**Skip leads with locked emails - only process unlocked emails:**

**Add a Router after Module 21 (Iterator):**

1. **Add Router module between Module 21 and Module 2**
2. **Route 1 (Skip locked emails):**
   - **Condition:** `{{21.email}} = "email_not_unlocked@domain.com"` OR `{{21.email}} CONTAINS "email_not_unlocked"`
   - **Action:** End (skip this lead)
3. **Route 2 (Process unlocked emails):**
   - **Condition:** `{{21.email}} != "email_not_unlocked@domain.com"` AND `{{21.email}} NOT CONTAINS "email_not_unlocked"`
   - **Action:** Continue to Module 2 (OpenAI)

**This only processes leads with real emails!**

---

### Option 2: Unlock Emails in Apollo.io (PAID)

**If you have Apollo.io credits:**

1. **Go to Apollo.io dashboard**
2. **Find the contact**
3. **Click "Unlock Email"**
4. **Spend credits (~$0.10-0.50 per email)**
5. **Email becomes available**

**Then re-run the scenario - emails will be unlocked.**

---

### Option 3: Use Apollo.io API to Unlock (ADVANCED)

**Automatically unlock emails before processing:**

**Add HTTP module after Module 20:**
- **URL:** `https://api.apollo.io/v1/people/match`
- **Method:** POST
- **Body:** Contact details
- **Headers:** `X-Api-Key: YOUR_API_KEY`
- **This unlocks emails automatically (costs credits)**

---

### Option 4: Search for Unlocked Emails Only

**In Module 20 (Apollo.io), add filter:**

**Body:**
```json
{
  "person_locations": ["Texas"],
  "page": 1,
  "per_page": 10,
  "email_status": ["verified", "likely", "guess"]
}
```

**This filters for contacts with unlocked/available emails.**

**Available email_status values:**
- `verified` - Email is verified and unlocked
- `likely` - Email is likely correct (unlocked)
- `guess` - Email is a guess (may be unlocked)
- `unavailable` - Email is locked (default for most)

---

## 📋 RECOMMENDED FIX: Option 1 (Filter Locked Emails)

### Step 1: Add Router Module

1. **Open Make.com scenario**
2. **Click "+" between Module 21 (Iterator) and Module 2 (OpenAI)**
3. **Search "Router" and add it**

### Step 2: Configure Router

**Route 1: Skip Locked Emails (End)**
1. **Click Route 1**
2. **Name:** "Skip Locked Emails"
3. **Add filter:**
   - **Field:** `{{21.email}}`
   - **Operator:** `contains`
   - **Value:** `email_not_unlocked`
   - **Action:** End scenario (skip this lead)
4. **Connect to:** End (or nothing)

**Route 2: Process Unlocked Emails**
1. **Click Route 2**
2. **Name:** "Process Unlocked Emails"
3. **This is the "else" route - no filter needed**
4. **Connect to:** Module 2 (OpenAI)

### Step 3: Test

1. **Run scenario**
2. **Router will skip leads with locked emails**
3. **Only process leads with real emails**

---

## 💡 UNDERSTANDING APOLLO.IO EMAIL STATUS

**Apollo.io email statuses:**
- `verified` - Email is verified and unlocked ✅
- `likely` - Email likely correct, unlocked ✅
- `guess` - Email is a guess, may be unlocked ✅
- `unavailable` - Email is locked, requires credits ❌

**Check `email_status` field in Apollo output:**
- If `unavailable` → Email is locked
- If `verified`, `likely`, or `guess` → Email may be unlocked

---

## 🎯 QUICK CHECK: Are Emails Actually Locked?

**Check Module 20 (Apollo.io) output:**

1. **Run scenario**
2. **Click Module 20**
3. **Check "people" array**
4. **Look for `email_status` field:**
   - If `"email_status": "unavailable"` → Locked
   - If `"email_status": "verified"` → Unlocked ✅

**Also check `email` field:**
- If `email_not_unlocked@domain.com` → Locked ❌
- If real email like `john@company.com` → Unlocked ✅

---

## 📋 BEST PRACTICE

**Filter in Apollo.io search (Module 20 body):**

```json
{
  "person_locations": ["Texas"],
  "page": 1,
  "per_page": 10,
  "email_status": ["verified"]
}
```

**This only gets leads with verified (unlocked) emails!**

**Plus add Router as backup to skip any locked emails that slip through.**

---

**Add the filter in Module 20 and/or Router to skip locked emails!** 🔧

