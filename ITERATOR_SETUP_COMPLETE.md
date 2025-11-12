# ✅ ITERATOR SETUP - USE THIS IN MODULE 2

## 🎯 WHAT TO USE IN MODULE 2

**Since your Iterator (Module 21) is outputting the person data directly:**

**In Module 2 (OpenAI), "Text Content" field under "Message 2":**

**Use:**
```
{{21}}
```

**This sends the entire person object to OpenAI!**

---

## 📋 STEP-BY-STEP

### Step 1: Update Module 2

1. **Click Module 2** (OpenAI)
2. **Find "Text Content" field** under "Message 2"
3. **Currently shows:** `{{20.body.people[0]}}` or `{{21.person}}`
4. **Change to:** `{{21}}`
5. **Click "OK"**

### Step 2: Test

1. **Run the scenario**
2. **Iterator will process each person**
3. **Module 2 receives the person data from Iterator**
4. **OpenAI processes each person**
5. **Result: All 5 leads saved to Airtable!**

---

## ✅ WHAT'S HAPPENING

**Flow:**
1. Module 20 (Apollo) → Returns array of 5 people
2. Iterator (Module 21) → Loops through array, outputs each person as `{{21}}`
3. Module 2 (OpenAI) → Receives `{{21}}` (one person at a time)
4. Module 3 (Parse JSON) → Parses OpenAI output
5. Module 4-7 → Save to Airtable

**Result:** All 5 different leads processed automatically!

---

## 💡 ALTERNATIVE

**If `{{21}}` doesn't work, try:**
- `{{21.person}}`
- `{{21.value}}`
- `{{21.item}}`

**But `{{21}}` should work since Iterator outputs the item directly!**

---

**Update Module 2 to use `{{21}}` and you're done!** 🚀

