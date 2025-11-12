# 🚀 MAXIMUM LEADS CONFIGURATION

## 🎯 GOAL: Get As Many Leads As Possible

**Remove all restrictions and get maximum results!**

---

## ✅ MODULE 1: Apollo.io Configuration

### Option 1: MAXIMUM RESULTS (No Filters)

**Body (Module 1):**
```json
{
  "page": 1,
  "per_page": 100
}
```

**This gets:**
- ✅ 100 leads per run (Apollo.io max per page)
- ✅ From anywhere (no location restrictions)
- ✅ Any industry, any title
- ✅ Fastest, most results

**Then change page number each run:**
- Run 1: `"page": 1` → Gets leads 1-100
- Run 2: `"page": 2` → Gets leads 101-200
- Run 3: `"page": 3` → Gets leads 201-300
- etc.

---

### Option 2: HELOC-Targeted But Broad

**Body (Module 1):**
```json
{
  "q_keywords": "real estate property construction",
  "page": 1,
  "per_page": 100
}
```

**This gets:**
- ✅ 100 leads per run
- ✅ Still HELOC-relevant
- ✅ From anywhere
- ✅ Broader than location-specific

---

### Option 3: Multiple Locations, Max Per Page

**Body (Module 1):**
```json
{
  "person_locations": [
    "United States",
    "California",
    "Texas",
    "Florida",
    "New York",
    "Arizona",
    "Nevada",
    "Colorado",
    "Washington",
    "Oregon"
  ],
  "page": 1,
  "per_page": 100
}
```

**This gets:**
- ✅ 100 leads per run
- ✅ All major US states
- ✅ HELOC-relevant locations

---

## 🎯 RECOMMENDED: Maximum Leads

### BEST CONFIGURATION FOR MAX LEADS:

**Module 1 Body:**
```json
{
  "page": 1,
  "per_page": 100
}
```

**Why:**
- ✅ No restrictions = Maximum results
- ✅ 100 leads per run (Apollo.io limit)
- ✅ Fast execution
- ✅ Can run multiple times with different pages

**To get different batches:**
- Change `page` number: 1, 2, 3, 4, 5, etc.
- Each page = 100 new leads
- Page 1 = Leads 1-100
- Page 2 = Leads 101-200
- etc.

---

## 📊 EXPECTED RESULTS

**With `per_page: 100`:**
- **Per run:** Up to 100 leads
- **Per day (if you run 10 times):** Up to 1,000 leads
- **Per week:** Thousands of leads!

**Apollo.io limits:**
- Check your plan's daily/hourly limits
- Free plan: Usually limited
- Paid plan: Higher limits

---

## ⚠️ IMPORTANT NOTES

### Apollo.io Rate Limits

**Check your plan:**
- Free plan: ~200 requests/day
- Basic plan: ~1,000 requests/day
- Professional: Higher limits

**With `per_page: 100`:**
- Each request = 100 leads
- 10 requests = 1,000 leads
- Easy to hit limits quickly!

### Cost Considerations

**Apollo.io may charge:**
- Per lead retrieved
- Per email unlocked
- Check your plan pricing

### Duplicate Handling

**Module 4 already handles this:**
- Searches for duplicates by email
- Creates new if no duplicate
- Updates if duplicate found
- ✅ This protects you from duplicates automatically!

---

## 🔧 STEP-BY-STEP

### Step 1: Update Module 1

1. **Click Module 1** (Apollo.io "Make an API Call")
2. **Find "Body" field**
3. **Change to:**
   ```json
   {
     "page": 1,
     "per_page": 100
   }
   ```
4. **Click "OK"**

### Step 2: Process Multiple Leads

**Current setup processes 1 lead at a time.**

**For 100 leads, you need:**

**Option A: Use Iterator (Advanced)**
- Add Iterator module after Module 1
- Loop through `{{1.people}}` array
- Process each person

**Option B: Keep it simple**
- Change `per_page` to 5-10 for now
- Run multiple times
- Let Module 4 handle duplicates

### Step 3: Get Different Batches

**After each run:**
- Change `"page": 1` to `"page": 2`
- Then `"page": 3`
- etc.

**OR set up a schedule:**
- Run every hour
- Automatically increment page number
- Gets new leads continuously

---

## 🎯 RECOMMENDED SETUP

### For Testing (Start Small):

```json
{
  "page": 1,
  "per_page": 5
}
```

**Why:**
- ✅ Tests the flow
- ✅ Doesn't hit rate limits
- ✅ Easy to debug
- ✅ Processes quickly

### For Production (Maximum Leads):

```json
{
  "page": 1,
  "per_page": 100
}
```

**Then:**
- Run manually with different page numbers
- OR set up schedule to run every X hours
- Change page number each run

---

## 💡 PRO TIPS

### Tip 1: Schedule Runs

**Set up Make.com schedule:**
- Run every 6 hours
- Each run gets page 1, 2, 3, etc.
- Gets fresh leads continuously

### Tip 2: Track Pages

**Keep track of which page you're on:**
- Page 1 → Used
- Page 2 → Used
- Page 3 → Next
- etc.

**Or use variable to auto-increment!**

### Tip 3: Filter in Airtable

**After importing:**
- Filter by industry, location
- Focus on best leads
- Archive or delete low-quality ones

---

## ✅ QUICK CONFIGURATION

**For MAXIMUM leads, use this in Module 1:**

```json
{
  "page": 1,
  "per_page": 100
}
```

**Then:**
1. Run scenario
2. Get 100 leads (if available)
3. Change page to 2
4. Run again
5. Repeat!

**Module 4 (Search) will automatically prevent duplicates!**

---

**This configuration will get you the MOST leads possible!** 🚀

