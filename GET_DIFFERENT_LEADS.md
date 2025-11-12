# 🔄 FIX: Getting Different Leads (Not Same Contact)

## ❌ PROBLEM
**Changing page number still returns same contact info**

## 🎯 WHY THIS HAPPENS

### Reason 1: Apollo.io Search Too Restrictive
- If search criteria is too narrow, Apollo.io might only have a few matching results
- Page 1, 2, 3 all return the same limited set
- Solution: Broaden search criteria

### Reason 2: Apollo.io Results Cached
- Apollo.io might cache results
- Same search = same results
- Solution: Vary search criteria, not just page

### Reason 3: Page Parameter Not Working
- Page number might not be passed correctly
- Or Apollo.io doesn't support pagination for your search
- Solution: Use different search parameters

---

## ✅ SOLUTION: Vary Search Criteria

**Instead of just changing page, change the SEARCH itself!**

### Option 1: Rotate Through Locations

**Run 1 - California:**
```json
{
  "person_locations": ["California"],
  "page": 1,
  "per_page": 5
}
```

**Run 2 - Texas:**
```json
{
  "person_locations": ["Texas"],
  "page": 1,
  "per_page": 5
}
```

**Run 3 - Florida:**
```json
{
  "person_locations": ["Florida"],
  "page": 1,
  "per_page": 5
}
```

**Run 4 - Arizona:**
```json
{
  "person_locations": ["Arizona"],
  "page": 1,
  "per_page": 5
}
```

**This gets different leads from different states!**

---

### Option 2: Use Keywords to Vary Results

**Run 1 - Real Estate:**
```json
{
  "q_keywords": "real estate agent",
  "page": 1,
  "per_page": 5
}
```

**Run 2 - Property Manager:**
```json
{
  "q_keywords": "property manager",
  "page": 1,
  "per_page": 5
}
```

**Run 3 - Construction:**
```json
{
  "q_keywords": "construction manager",
  "page": 1,
  "per_page": 5
}
```

**Run 4 - Homeowner:**
```json
{
  "q_keywords": "homeowner property owner",
  "page": 1,
  "per_page": 5
}
```

---

### Option 3: Combine Location + Keywords

**Run 1:**
```json
{
  "q_keywords": "real estate",
  "person_locations": ["California"],
  "page": 1,
  "per_page": 5
}
```

**Run 2:**
```json
{
  "q_keywords": "property manager",
  "person_locations": ["Texas"],
  "page": 1,
  "per_page": 5
}
```

**Run 3:**
```json
{
  "q_keywords": "construction",
  "person_locations": ["Florida"],
  "page": 1,
  "per_page": 5
}
```

---

### Option 4: Use Job Titles

**Run 1:**
```json
{
  "person_titles": ["Real Estate Agent"],
  "person_locations": ["California"],
  "page": 1,
  "per_page": 5
}
```

**Run 2:**
```json
{
  "person_titles": ["Property Manager"],
  "person_locations": ["Texas"],
  "page": 1,
  "per_page": 5
}
```

**Run 3:**
```json
{
  "person_titles": ["Construction Manager"],
  "person_locations": ["Florida"],
  "page": 1,
  "per_page": 5
}
```

---

## 🎯 RECOMMENDED: Rotation Strategy

**Create a rotation of 10 different searches:**

### Week 1 - Major States

**Day 1:**
```json
{
  "person_locations": ["California"],
  "page": 1,
  "per_page": 5
}
```

**Day 2:**
```json
{
  "person_locations": ["Texas"],
  "page": 1,
  "per_page": 5
}
```

**Day 3:**
```json
{
  "person_locations": ["Florida"],
  "page": 1,
  "per_page": 5
}
```

**Day 4:**
```json
{
  "person_locations": ["New York"],
  "page": 1,
  "per_page": 5
}
```

**Day 5:**
```json
{
  "person_locations": ["Arizona"],
  "page": 1,
  "per_page": 5
}
```

### Week 2 - Add Keywords

**Day 1:**
```json
{
  "q_keywords": "real estate agent",
  "person_locations": ["California"],
  "page": 1,
  "per_page": 5
}
```

**Day 2:**
```json
{
  "q_keywords": "property manager",
  "person_locations": ["Texas"],
  "page": 1,
  "per_page": 5
}
```

**Continue rotating through different combinations!**

---

## 📋 QUICK COPY-PASTE OPTIONS

### Option A - California Only (Rotate Keywords)
```json
{"q_keywords": "real estate", "person_locations": ["California"], "page": 1, "per_page": 5}
{"q_keywords": "property manager", "person_locations": ["California"], "page": 1, "per_page": 5}
{"q_keywords": "construction", "person_locations": ["California"], "page": 1, "per_page": 5}
{"q_keywords": "homeowner", "person_locations": ["California"], "page": 1, "per_page": 5}
```

### Option B - Rotate States (No Keywords)
```json
{"person_locations": ["California"], "page": 1, "per_page": 5}
{"person_locations": ["Texas"], "page": 1, "per_page": 5}
{"person_locations": ["Florida"], "page": 1, "per_page": 5}
{"person_locations": ["Arizona"], "page": 1, "per_page": 5}
{"person_locations": ["Nevada"], "page": 1, "per_page": 5}
{"person_locations": ["Colorado"], "page": 1, "per_page": 5}
```

### Option C - Multiple States at Once
```json
{"person_locations": ["California", "Texas", "Florida"], "page": 1, "per_page": 5}
{"person_locations": ["Arizona", "Nevada", "Colorado"], "page": 1, "per_page": 5}
{"person_locations": ["New York", "New Jersey", "Connecticut"], "page": 1, "per_page": 5}
```

---

## 🔍 DEBUG: Check What Apollo.io Returns

### Step 1: Check Module 1 Output

**After running Module 1, check the output bundle:**
- How many people are in the `people` array?
- Are they all the same?
- Or is it only returning 1 person total?

### Step 2: Test Direct API Call

**If Module 1 shows only 1 person, test with direct API:**

**Try this in terminal or Postman:**
```bash
curl -X POST https://api.apollo.io/v1/mixed_people/search \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: YOUR_API_KEY" \
  -d '{"person_locations": ["California"], "page": 1, "per_page": 10}'
```

**Check the response:**
- How many people returned?
- Are they different on page 1 vs page 2?

---

## ✅ BEST PRACTICE: Combination Strategy

**Use this rotation pattern:**

### Pattern 1: Location Rotation
- California → Texas → Florida → Arizona → etc.
- Each location = different leads

### Pattern 2: Keyword Rotation  
- "real estate" → "property manager" → "construction" → etc.
- Each keyword = different leads

### Pattern 3: Combined
- California + "real estate" → Texas + "property manager" → etc.
- Maximum variety!

---

## 💡 PRO TIPS

### Tip 1: Keep a Log
**Track which combinations you've used:**
- California + real estate ✓
- Texas + property manager ✓
- Florida + construction ✓
- etc.

### Tip 2: Use Make.com Scheduler
**Set up different schedules:**
- Schedule 1: California searches (runs daily)
- Schedule 2: Texas searches (runs daily)
- Schedule 3: Florida searches (runs daily)
- Each gets different leads automatically!

### Tip 3: Check Apollo.io Dashboard
**See what's available:**
- Check your Apollo.io account
- See total results for each search
- Adjust strategy based on available data

---

## 🎯 RECOMMENDED ACTION

**Instead of just changing page numbers, rotate through these:**

**Copy-paste these 10 different searches (use one per run):**

1. `{"person_locations": ["California"], "page": 1, "per_page": 5}`
2. `{"person_locations": ["Texas"], "page": 1, "per_page": 5}`
3. `{"person_locations": ["Florida"], "page": 1, "per_page": 5}`
4. `{"person_locations": ["Arizona"], "page": 1, "per_page": 5}`
5. `{"person_locations": ["Nevada"], "page": 1, "per_page": 5}`
6. `{"q_keywords": "real estate agent", "person_locations": ["California"], "page": 1, "per_page": 5}`
7. `{"q_keywords": "property manager", "person_locations": ["Texas"], "page": 1, "per_page": 5}`
8. `{"q_keywords": "construction manager", "person_locations": ["Florida"], "page": 1, "per_page": 5}`
9. `{"person_titles": ["Real Estate Agent"], "person_locations": ["California"], "page": 1, "per_page": 5}`
10. `{"person_titles": ["Property Manager"], "person_locations": ["Texas"], "page": 1, "per_page": 5}`

**Rotate through these - you'll get different leads every time!** 🚀

