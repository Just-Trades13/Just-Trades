# 🔧 FIX: Module 2 Reference + JSON Error

## ❌ PROBLEM 1: Wrong Module Reference

**Module 2 is still using:**
```
{{`18.data.people[0]`}}
```

**But your Apollo.io is Module 20, so it should be:**
```
{{20.body.people[0]}}
```

## ❌ PROBLEM 2: JSON Parse Error

**OpenAI might be returning invalid JSON** (wrapped in markdown, or plain text)

---

## ✅ FIX BOTH ISSUES

### Step 1: Fix Module 2 Reference

1. **Click Module 2** (OpenAI)
2. **Find "Text Content" field** under "Message 2"
3. **Current:** `{{`18.data.people[0]`}}`
4. **Change to:** `{{20.body.people[0]}}`
5. **Remove backticks** - just use: `{{20.body.people[0]}}`

### Step 2: Check Module 2 Output

**After running:**

1. **Click Module 2** (OpenAI)
2. **Check "Output Bundle"**
3. **Look for `result` field**
4. **Check what's inside:**
   - Should be JSON like `{"lead_id": "...", ...}`
   - NOT markdown like `\`\`\`json {...} \`\`\``
   - NOT plain text

### Step 3: Fix OpenAI Output (If Needed)

**If OpenAI returns markdown-wrapped JSON:**

The system message tells OpenAI to return "ONLY valid JSON", but sometimes it still wraps it.

**You might need to clean it in Module 3:**
- Use a text function to strip markdown
- Or update the OpenAI prompt

---

## 🎯 QUICK FIX

**In Module 2, change:**
```
{{`18.data.people[0]`}}
```

**To:**
```
{{20.body.people[0]}}
```

**No backticks! Just:**
```
{{20.body.people[0]}}
```

**Then test again!**

---

## 📋 CHECKLIST

- [ ] Module 2 references Module 20 (not 18)
- [ ] Module 2 uses `{{20.body.people[0]}}` (no backticks)
- [ ] Module 3 uses `{{2.result}}`
- [ ] OpenAI returns valid JSON (check Module 2 output)

---

**Fix Module 2 reference first - that's the main issue!** 🔧

