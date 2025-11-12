# Fix: Invalid HTTP Header Name Error

## 🔴 THE ERROR
```
ERR_INVALID_HTTP_TOKEN: Header name must be a valid HTTP token ["Content-Type:"]
```

## ❌ THE PROBLEM

You added a colon (`:`) in the **Header Name** field!

**Wrong:**
- Name: `Content-Type:` ❌ (has colon)
- Name: `Content-Type :` ❌ (has colon and space)

**Make.com only wants the header name, NOT the colon!**

---

## ✅ THE FIX

### In Your HTTP Module:

1. **Go to Headers section**
2. **Edit Header 1:**
   - **Name field:** `Content-Type` (NO colon!)
   - **Value field:** `application/json`
3. **Edit Header 2:**
   - **Name field:** `X-Api-Key` (NO colon!)
   - **Value field:** `DtdKb5hTo_9GTtbohlNJ-Q`

---

## 📋 CORRECT HEADER FORMAT

| Field | Correct Value | ❌ Wrong |
|-------|--------------|---------|
| **Header 1 Name** | `Content-Type` | `Content-Type:` |
| **Header 1 Value** | `application/json` | ✅ Correct |
| **Header 2 Name** | `X-Api-Key` | `X-Api-Key:` |
| **Header 2 Value** | `DtdKb5hTo_9GTtbohlNJ-Q` | ✅ Correct |

---

## 🎯 QUICK FIX STEPS

1. **Click your HTTP module** in Make.com
2. **Go to Headers section**
3. **Edit each header:**
   - Click on the header row
   - **Name field:** Remove any colons (`:`) or extra spaces
   - Should be just: `Content-Type` and `X-Api-Key`
   - **Value fields:** Keep as they are
4. **Click "Save"**

---

## ✅ VERIFICATION

After fixing, your headers should look like:

```
Header 1:
   Name:  Content-Type
   Value: application/json

Header 2:
   Name:  X-Api-Key
   Value: DtdKb5hTo_9GTtbohlNJ-Q
```

**NO colons in the Name fields!**

---

## 💡 WHY THIS HAPPENS

HTTP headers are formatted as:
```
Header-Name: Header-Value
```

But in Make.com's UI:
- **Name field:** Just the header name (before the colon)
- **Value field:** Just the header value (after the colon)
- **Make.com adds the colon automatically** when sending the request

So you only enter:
- Name: `Content-Type`
- Value: `application/json`

Make.com creates: `Content-Type: application/json`

---

**Fix the header names (remove colons) and it will work!** ✅

