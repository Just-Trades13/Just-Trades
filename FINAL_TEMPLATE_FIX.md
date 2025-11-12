# Fix: OpenAI Template - Working Examples

## ✅ WORKING TEMPLATES FROM REAL BLUEPRINTS

Based on working blueprints, here are the correct formats:

---

## 📋 Option 1: Simple Module Reference (RECOMMENDED)

**From Scenario A (working blueprint):**
```
{{`1`}}
```

**For your HELOC scenario:**
```
{{`18`}}
```

**Replace 18 with your HTTP module number!**

This sends the entire module output bundle to OpenAI.

---

## 📋 Option 2: Specific Path with Backticks

**From Nelson HELOC HTTP blueprint:**
```
{{`18.body.people[0]`}}
```

**Replace 18 with your HTTP module number!**

Note: Uses backticks (`) around the entire expression!

---

## 📋 Option 3: No if() Function Needed

**Simple direct path:**
```
{{18.body.people[0]}}
```

**Replace 18 with your HTTP module number!**

---

## 🎯 RECOMMENDED: Use Backticks

**Most reliable format:**
```
{{`18.body.people[0]`}}
```

**Or for entire module:**
```
{{`18`}}
```

**The backticks (`) are important in Make.com!**

---

## ✅ QUICK FIX IN MAKE.COM

1. **Click Module 2** (OpenAI)
2. **Click "Message 2"** (User message)
3. **In "Text Content" field:**
   
   **Option A (Simplest):**
   ```
   {{`18`}}
   ```
   
   **Option B (Specific):**
   ```
   {{`18.body.people[0]`}}
   ```
   
   **Replace 18 with your HTTP module number!**
   
4. **Click outside to save**
5. **Click "OK"**

---

## 🔍 BACKTICKS ARE IMPORTANT!

Notice the difference:

- **WRONG:** `{{18.body.people[0]}}` (no backticks - might fail)
- **RIGHT:** `{{`18.body.people[0]`}}` (with backticks - works)

Make.com uses backticks (`) for map/reference syntax!

---

**Use the backtick format and it will work!** ✅

