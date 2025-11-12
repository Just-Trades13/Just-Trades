# 🔍 ITERATOR TROUBLESHOOTING

## ❌ Issue: `{{21}}`, `{{21.person}}`, `{{21.value}}` Don't Work

## ✅ HOW TO FIND THE CORRECT PATH

### Step 1: Check Iterator Module Number

1. **Look at the Iterator module** in your Make.com scenario
2. **Check the number shown above it** (like "21", "22", etc.)
3. **Make sure you're using the correct module number**

### Step 2: Check Iterator Output Structure

1. **Run the scenario** (or just check the Iterator module)
2. **Click on the Iterator module**
3. **Look at the "Output Bundle" or "Data" tab**
4. **See what the structure looks like**

### Step 3: Try Different Paths

**Based on what you see, try these:**

**Option 1: Entire bundle**
```
{{21}}
```

**Option 2: Check if it's wrapped**
```
{{21.data}}
{{21.item}}
{{21.array}}
```

**Option 3: Reference Module 20 directly**
Since Iterator is just looping, maybe you can reference the original:
```
{{20.body.people[{{21.__IMTINDEX__}}]}}
```

**Option 4: Use the index from Iterator**
If Iterator has an index field:
```
{{20.body.people[{{21.__IMTINDEX__}}]}}
```

---

## 🎯 ALTERNATIVE: Check What Make.com Shows

**In Module 2:**

1. **Click the "Text Content" field**
2. **Look at the available data mapping options**
3. **See if Iterator (Module 21) appears**
4. **Click through the available fields**
5. **Use whatever Make.com suggests**

**Make.com's data mapper usually shows the correct path!**

---

## 💡 QUICK TEST

**Try this:**

1. **In Module 2, click "Text Content"**
2. **Click the data mapping icon** (usually looks like `{}` or `</>`)
3. **Navigate to Module 21 (Iterator)**
4. **See what fields it shows**
5. **Click on the root level or top item**
6. **This should give you the correct path**

**Make.com will show you the exact syntax to use!**

---

## 🔍 WHAT TO LOOK FOR

**Check the Iterator output for:**
- What's the top-level item name?
- Is there a wrapper object?
- What fields are available?

**Then use that structure in Module 2!**

---

## ✅ MOST LIKELY SOLUTION

**Use Make.com's data mapper:**

1. **In Module 2, find "Text Content" field**
2. **Click the mapping icon** (`{}` or `</>`)
3. **Navigate to Iterator (Module 21)**
4. **Click on the top-level item** (the person object)
5. **Make.com will auto-fill the correct path**

**This is the easiest way - let Make.com show you the path!**

---

**Use Make.com's data mapper to find the correct path - it will show you exactly what to use!** 🎯

