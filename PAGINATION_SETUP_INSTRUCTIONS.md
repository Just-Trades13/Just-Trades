# 🚀 PAGINATION SETUP: Step-by-Step Instructions

## 📋 WHAT THIS ADDS

**Automatic pagination loop:**
- Processes pages 1-10 automatically
- Gets 50 leads per execution (10 pages × 5 leads)
- No manual page number changes needed!

---

## ✅ OPTION 1: Simple Update (Quick Fix)

### Just Increase per_page

**Update Module 1 (Apollo.io):**

1. **Click Module 1**
2. **Find "Body" field**
3. **Change:**
   ```json
   {
     "q_keywords": "property manager",
     "person_locations": ["Texas"],
     "page": 1,
     "per_page": 10
   }
   ```
4. **Save**

**Result:** Gets 10 leads per run (instead of 5)

---

## ✅ OPTION 2: Full Pagination Loop (Best)

### Step 1: Add Variable Module BEFORE Module 1

1. **Click "+" before Module 1**
2. **Search:** "Set Variable" or "Tools > Set Variables"
3. **Add module**
4. **Configure:**
   - **Variable name:** `current_page`
   - **Variable value:** `1`
   - **Variable lifetime:** "One cycle" or "Roundtrip"
5. **Save**

**This will be Module 0**

---

### Step 2: Update Module 1 to Use Variable

1. **Click Module 1 (Apollo.io)**
2. **Find "Body" field**
3. **Change from:**
   ```json
   {"page": 1, ...}
   ```
4. **Change to:**
   ```json
   {"page": {{0.current_page}}, ...}
   ```
   (Replace `0` with your Variable module number)
5. **Save**

---

### Step 3: Add Increment Module AFTER Last Module

**After Module 7 (or Module 9), add:**

1. **Click "+" after last module**
2. **Search:** "Set Variable" or "Tools > Set Variables"
3. **Add module**
4. **Configure:**
   - **Variable name:** `current_page`
   - **Variable value:** `{{add(0.current_page; 1)}}` OR `{{0.current_page + 1}}`
     - Try `{{add(0.current_page; 1)}}` first
     - If that doesn't work, try `{{0.current_page + 1}}`
   - **Variable lifetime:** "One cycle" or "Roundtrip"
5. **Save**

**This will be Module 8**

---

### Step 4: Add Router to Loop Back

**After the increment module, add:**

1. **Click "+" after increment module**
2. **Search:** "Router" or "Flow Control > Router"
3. **Add Router module**

**Configure Route 1 (Continue Looping):**
- **Name:** "Continue to next page"
- **Condition:** `{{0.current_page}} <= 10`
  - OR: `{{0.current_page}} < 11`
- **Connect to:** Module 1 (Apollo.io)

**Configure Route 2 (Stop):**
- **Name:** "All pages done"
- **Condition:** `{{0.current_page}} > 10`
- **End here (no connection)**

---

### Step 5: Test

1. **Run scenario**
2. **Watch execution log**
3. **Should see:**
   - Module 0: Sets page = 1
   - Module 1: Fetches page 1
   - Modules 2-7: Process leads
   - Module 8: Increments to page 2
   - Router: Loops back to Module 1
   - Repeats until page 10
3. **Result:** 50 leads processed!

---

## ⚠️ IMPORTANT NOTES

### Apollo.io Response

**Check Module 1 output for pagination info:**
- Look for `pagination.total_pages`
- Don't loop beyond available pages

**Update Router condition:**
```
{{0.current_page}} <= {{20.body.pagination.total_pages}}
```

### Make.com Roundtrips

**In scenario settings:**
- Set "Roundtrips" to at least `10` (for 10 pages)
- Or set to `20` if you want more pages

**Settings → Scenario → Roundtrips:** `10`

---

### Rate Limiting

**Add delay between loops:**
- After Module 8 (increment), add "Sleep" module
- Set delay: 2-3 seconds
- Prevents API rate limit errors

---

## 🎯 RECOMMENDED CONFIGURATION

### Conservative (Safe):
- **per_page:** `5`
- **Max pages:** `10`
- **Total leads:** `50`
- **Delay:** `2 seconds`

### Aggressive (More leads):
- **per_page:** `10`
- **Max pages:** `5`
- **Total leads:** `50`
- **Delay:** `3 seconds`

---

## 📋 QUICK REFERENCE

**Module 0:** Set Variable → `current_page = 1`  
**Module 1:** Apollo.io → `page: {{0.current_page}}`  
**Module 2-7:** (Existing modules)  
**Module 8:** Set Variable → `current_page = {{add(0.current_page; 1)}}`  
**Module 9:** Router → If `<= 10` → Loop to Module 1, Else → Stop

---

## ✅ TESTING CHECKLIST

- [ ] Variable module (Module 0) sets `current_page = 1`
- [ ] Module 1 uses `{{0.current_page}}` in page field
- [ ] Module 8 increments `current_page`
- [ ] Router checks if `current_page <= 10`
- [ ] Router loops back to Module 1 if condition true
- [ ] Scenario processes 10 pages = 50 leads

---

**Want me to update your blueprint with the full pagination system?** 🚀

