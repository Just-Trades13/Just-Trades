# 🔍 DEBUG: Same Lead in Airtable (Different in Apollo)

## ✅ WHAT'S WORKING
- **Module 1 (Apollo):** Returns different contacts ✅
- **No errors:** Modules running successfully ✅

## ❌ PROBLEM
- **Module 6 (Airtable):** Creates same lead every time ❌
- **Different contact in Apollo → Same contact in Airtable**

---

## 🎯 WHERE TO CHECK

### Check 1: Module 2 Input (OpenAI)

**Module 2 is processing: `{{20.body.people[0]}}`**

**The issue:** `people[0]` is always the FIRST person in the array.

**If Apollo.io always sorts/returns the same person first:**
- You'll always get that person
- Even if Apollo returns 5 different people, `[0]` = same person

**Check:**
1. **Run scenario**
2. **Click Module 2**
3. **Check input data** (what `{{20.body.people[0]}}` contains)
4. **Is it the same person every time?**

**Fix:** Process different index:
- `{{20.body.people[1]}}` (second person)
- `{{20.body.people[2]}}` (third person)
- OR use Iterator to process all

---

### Check 2: Module 3 Output (Parse JSON)

**Module 3 parses Module 2 output**

**Check:**
1. **Run scenario**
2. **Click Module 3**
3. **Check output bundle**
4. **Look at `contact_email` field**
5. **Is it the same email every time? Or different?**

**If Module 3 shows same email:**
- Problem is before Module 3 (Module 1 or 2)
- Check Module 2 output

**If Module 3 shows different email:**
- Problem is after Module 3 (Module 4, 5, 6)
- Check Module 6 mappings

---

### Check 3: Module 6 Input (Airtable Create)

**Module 6 creates record from Module 3 output**

**Check:**
1. **Run scenario**
2. **Click Module 6**
3. **Check input bundle** (before it runs)
4. **Look at field mappings:**
   - `Contact Email` field
   - `Contact Full Name` field
   - Are they using correct Module 3 paths?

**Common issue:** Module 6 might be using:
- Wrong module reference (old data)
- Cached data
- Wrong field path

**Fix:** Make sure Module 6 uses `{{3.contact_email}}`, `{{3.contact_full_name}}`, etc.

---

### Check 4: Module 4 Search (Duplicate Check)

**Module 4 searches for duplicates before creating**

**Check:**
1. **Module 4 formula:** `{Contact Email} = '{{3.contact_email}}'`
2. **If same email found every time:**
   - Module 5 Router sends to Module 7 (Update)
   - Module 7 updates existing record (not creates new)
   - This would explain why you see same lead!

**Check:**
- After Module 4 runs, does it find a record?
- If yes → Goes to Module 7 (Update existing)
- If no → Goes to Module 6 (Create new)

---

## 🔍 STEP-BY-STEP DEBUG

### Step 1: Check Module 2 Input

**After running:**

1. **Click Module 2 (OpenAI)**
2. **Check input data** (what's being sent to OpenAI)
3. **Tell me:**
   - What email/name does it show?
   - Is it the same every run?
   - Or different each run?

**If same every run:**
- Module 2 is the problem
- Apollo returns different people, but `people[0]` is always same person
- Fix: Use `people[1]` or `people[2]` or Iterator

### Step 2: Check Module 3 Output

**After running:**

1. **Click Module 3 (Parse JSON)**
2. **Check output bundle**
3. **Look at:**
   - `contact_email`
   - `contact_full_name`
   - `first_name`
4. **Tell me:**
   - Are these different each run?
   - Or same every time?

**If different:**
- Modules 1-3 are working ✅
- Problem is Module 4, 5, 6, or 7

**If same:**
- Problem is Module 1 or 2

### Step 3: Check Module 4 & 5 (Router)

**After running:**

1. **Click Module 4 (Airtable Search)**
2. **Did it find a duplicate?**
   - If yes → Goes to Module 7 (Update)
   - If no → Goes to Module 6 (Create)

3. **Click Module 5 (Router)**
4. **Which route executed?**
   - Route 1: No duplicate → Create (Module 6)
   - Route 2: Duplicate → Update (Module 7)

**If always goes to Module 7:**
- Same email already exists in Airtable
- Module 7 updates that record (not creates new)
- This explains why you see same lead!

**Fix:** Check if email already exists in Airtable, or change search logic

### Step 4: Check Module 6 Mappings

**If Module 5 sends to Module 6 (Create):**

1. **Click Module 6**
2. **Check field mappings:**
   - `Contact Email` = `{{3.contact_email}}`?
   - `Contact Full Name` = `{{3.contact_full_name}}`?
   - Are all fields using `{{3.xxx}}` paths?

**If using wrong paths:**
- Might be using old/cached data
- Fix: Update all mappings to use `{{3.xxx}}`

---

## 🎯 MOST LIKELY ISSUES

### Issue 1: Module 2 Always Processes `people[0]`

**Apollo returns 5 people:**
- `people[0]` = Same person (always first)
- `people[1]` = Different person
- `people[2]` = Different person
- etc.

**You're always processing `[0]`, so you get the same person.**

**Fix:**
- Change to `{{20.body.people[1]}}` (second person)
- OR `{{20.body.people[2]}}` (third person)
- OR use Iterator to process all

### Issue 2: Module 4 Finds Duplicate Every Time

**If Module 4 always finds existing record:**
- Module 5 sends to Module 7 (Update)
- Module 7 updates same record
- Result: Same lead in Airtable

**Fix:**
- Check Airtable - does email already exist?
- If yes, delete it or change search logic
- OR Module 4 search is wrong

### Issue 3: Module 6 Using Cached Data

**Module 6 might be using old mappings:**
- Not using `{{3.xxx}}` paths
- Using wrong module reference
- Cached data

**Fix:**
- Check all Module 6 field mappings
- Make sure they use `{{3.contact_email}}`, etc.

---

## ✅ QUICK CHECKS TO DO NOW

1. **Check Module 2 input:**
   - What email/name does it show?
   - Same or different each run?

2. **Check Module 3 output:**
   - What email does it show?
   - Same or different each run?

3. **Check Module 4:**
   - Does it find a duplicate?
   - Same email every time?

4. **Check Module 5 Router:**
   - Which route executed?
   - Create (Module 6) or Update (Module 7)?

**Tell me what you find at each step!** 🔍

