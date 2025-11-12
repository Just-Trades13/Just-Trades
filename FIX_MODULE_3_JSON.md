# 🔧 FIX: Module 3 JSON Parse Error

## ❌ ERROR LOCATION
**Module 3 (Parse JSON) is getting invalid JSON from Module 2 (OpenAI)**

## 🎯 STEP-BY-STEP DEBUG

### Step 1: Check Module 2 Output

**After running the scenario:**

1. **Click Module 2** (OpenAI)
2. **Check "Output Bundle" or "Data" tab**
3. **Look for `result` field**
4. **Click to expand `result`**
5. **Tell me what you see:**
   - Is it JSON like `{"lead_id": "...", ...}`?
   - Is it wrapped in markdown like `\`\`\`json {...} \`\`\``?
   - Is it plain text?
   - Is it empty?

### Step 2: Check Module 3 Configuration

**In Module 3:**

1. **Click Module 3** (Parse JSON)
2. **Find "JSON" field** (or "JSON string" field)
3. **Check what path it uses:**
   - Should be: `{{2.result}}`
   - Tell me what it currently shows

### Step 3: Compare

**The path in Module 3 must match what Module 2 outputs!**

---

## ✅ COMMON FIXES

### Fix 1: OpenAI Returning Markdown-Wrapped JSON

**If Module 2 output looks like:**
```
\`\`\`json
{
  "lead_id": "...",
  ...
}
\`\`\`
```

**Solution:** We need to strip the markdown. But first, let's see what you're getting.

### Fix 2: OpenAI Returning Plain Text

**If Module 2 output is just text (not JSON):**

**The system message should force JSON, but sometimes it doesn't work.**

**We might need to update the OpenAI prompt.**

### Fix 3: Module 3 Wrong Path

**If Module 3 uses wrong path:**
- Current: `{{2.something_wrong}}`
- Should be: `{{2.result}}`

**Change it to `{{2.result}}`**

---

## 🔍 WHAT TO CHECK RIGHT NOW

1. **Run the scenario**
2. **Click Module 2** → Check `result` field
3. **Screenshot or tell me:**
   - What's in the `result` field?
   - Is it valid JSON?
   - Or is it wrapped/plain text?

4. **Click Module 3** → Check "JSON" field
5. **Tell me:**
   - What path does it use?
   - Is it `{{2.result}}`?

**This will tell us exactly what's wrong!**

---

## 💡 QUICK TEST

**Try this:**

1. **In Module 3, temporarily change JSON field to:**
   ```
   {{2}}
   ```
   (This shows the full Module 2 output)

2. **Run scenario**
3. **Check Module 3 error message**
4. **This will show what Module 2 is actually outputting**

**Then we can fix it properly!**

---

## 🎯 MOST LIKELY ISSUES

1. **OpenAI returning markdown-wrapped JSON**
   - Solution: Strip markdown or update prompt

2. **OpenAI returning plain text**
   - Solution: Update OpenAI system message

3. **Module 3 path wrong**
   - Solution: Change to `{{2.result}}`

**Check Module 2 output first - that will tell us!** 🔍

