# 🔧 FIX: "Source is not valid JSON" Error

## ❌ ERROR
```
Source is not valid JSON.
```

## 🎯 CAUSE
**Module 3 (Parse JSON) is receiving invalid JSON from Module 2 (OpenAI)**

This happens when:
1. Module 3 is reading the wrong path from Module 2 output
2. OpenAI output format changed
3. Data structure doesn't match expected JSON

---

## ✅ SOLUTION: Check Module 3 Configuration

### Step 1: Find Module 3 (Parse JSON)

1. **Click Module 3** (Parse JSON)
2. **Find the "JSON" field** (where it reads Module 2 output)

### Step 2: Check Current Path

**Module 3 should be reading from Module 2 output.**

**Expected paths for OpenAI Module 2:**
- `{{2.result}}` (if using CreateCompletion API)
- `{{2.text.output[0].content[0].text}}` (if using createModelResponse API)

**YOUR BLUEPRINT USES:** `CreateCompletion` API
**SO USE:** `{{2.result}}`

### Step 3: Verify Module 2 Output

**After running Module 2:**

1. **Click Module 2** (OpenAI)
2. **Check "Output Bundle"**
3. **Look for:**
   - `result` field (if CreateCompletion)
   - OR `text.output[0].content[0].text` (if createModelResponse)

**See what's actually there!**

---

## 🔧 QUICK FIXES TO TRY

### Fix 1: Check Module 3 JSON Path

**In Module 3, the "JSON" field should be:**
```
{{2.result}}
```

**If it's something else, change it to `{{2.result}}`**

### Fix 2: Verify OpenAI Output Format

**Check Module 2 output structure:**
- If you see `result` → Use `{{2.result}}`
- If you see `text.output` → Use `{{2.text.output[0].content[0].text}}`

### Fix 3: Check If OpenAI Is Returning Valid JSON

**OpenAI should return a JSON string like:**
```json
{
  "lead_id": "...",
  "contact_email": "...",
  ...
}
```

**If it's returning plain text or error, that's the problem!**

---

## 📋 STEP-BY-STEP DEBUG

### Step 1: Check Module 2 Output

1. **Run scenario**
2. **Click Module 2** (OpenAI)
3. **Check output bundle**
4. **Tell me what you see:**
   - Is there a `result` field?
   - What does it contain?
   - Is it valid JSON or plain text?

### Step 2: Check Module 3 Input

1. **Click Module 3** (Parse JSON)
2. **Check "JSON" field**
3. **What path does it use?**
   - Should be `{{2.result}}`
   - Or `{{2.text.output[0].content[0].text}}`

### Step 3: Compare

**The path in Module 3 must match what Module 2 outputs!**

---

## 🎯 MOST LIKELY ISSUE

**Module 3 is using wrong path!**

**Your blueprint uses `CreateCompletion` API, so:**
- Module 2 outputs to: `result`
- Module 3 should read: `{{2.result}}`

**Check Module 3 and make sure it uses `{{2.result}}`!**

---

## ✅ WHAT TO DO NOW

1. **Click Module 3** (Parse JSON)
2. **Check "JSON" field**
3. **Tell me what path it uses**
4. **Or change it to:** `{{2.result}}`
5. **Test again**

**This should fix it!** 🔧

