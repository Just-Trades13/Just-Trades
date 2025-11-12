# 🚀 ADD ITERATOR: Process All 5 Leads Automatically

## ✅ WHAT THIS DOES

**Instead of processing just 1 person (people[0]), this processes ALL 5 people automatically!**

**Result:** Gets all different leads from Apollo.io in one run!

---

## 📋 STEP-BY-STEP INSTRUCTIONS

### Step 1: Add Iterator Module

1. **Open your Make.com scenario**
2. **Find Module 20 (Apollo.io)** and **Module 2 (OpenAI)**
3. **Click the "+" button** between them (or drag from left sidebar)
4. **Search for "Iterator"** and select it
5. **Position it** between Module 20 and Module 2

### Step 2: Configure Iterator

1. **Click the Iterator module** (it should be Module 21 or similar)
2. **Find "Array" field**
3. **Enter:** `{{20.body.people}}`
   - This references the people array from Apollo.io
4. **Click "OK"**

### Step 3: Update Module 2 (OpenAI)

1. **Click Module 2** (OpenAI)
2. **Find "Text Content" field** under "Message 2"
3. **Currently shows:** `{{20.body.people[0]}}`
4. **Change to:** `{{21.person}}`
   - Replace `21` with your Iterator module number if different
   - The Iterator outputs each person as `person` (or check what variable name it uses)
5. **Click "OK"**

### Step 4: Update Module Connections

**Make sure:**
- Module 20 → Iterator → Module 2 → Module 3 → Module 4 → Module 5
- The flow should be connected properly

### Step 5: Test

1. **Run the scenario**
2. **Iterator will loop through all 5 people**
3. **Each person processes through Modules 2-7**
4. **Result: 5 different leads in Airtable!**

---

## 🎯 WHAT HAPPENS NOW

**Before:**
- Module 20 returns 5 people
- Module 2 processes only `people[0]` (first person)
- Result: 1 lead per run

**After:**
- Module 20 returns 5 people
- Iterator loops through all 5 people
- Module 2 processes each person one by one
- Result: 5 leads per run!

---

## ⚠️ IMPORTANT NOTES

### Iterator Variable Name

**The Iterator might output to different variable names:**
- `{{21.person}}`
- `{{21.value}}`
- `{{21.item}}`

**To find out:**
1. **Run the scenario**
2. **Click Iterator module**
3. **Check output bundle**
4. **See what the variable name is**
5. **Update Module 2 to use that name**

### Module Numbers

**If Iterator becomes Module 21:**
- Use `{{21.person}}` in Module 2

**If Iterator becomes a different number:**
- Use that number instead

**To find Iterator module number:**
- Look above the Iterator module icon in Make.com
- It shows the module number

---

## ✅ EXPECTED RESULT

**After setup:**
- 1 run = 5 different leads in Airtable
- No more same lead issue!
- All 5 people from Apollo.io processed

---

## 🔧 TROUBLESHOOTING

### Issue: "Variable not found"

**If Module 2 shows error about `{{21.person}}`:**

1. **Check Iterator module number** (might not be 21)
2. **Check Iterator output variable name**
3. **Update Module 2 with correct path**

### Issue: "Iterator not processing"

**Make sure:**
- Iterator array is `{{20.body.people}}`
- Modules are connected in order
- Iterator is between Module 20 and Module 2

### Issue: "Still getting same leads"

**Check:**
- Is Iterator actually looping? (Look at execution log)
- Is Module 2 using Iterator output?
- Is Apollo.io returning 5 different people?

---

**Follow these steps and you'll process all 5 leads automatically!** 🚀

