# Fix: Blank Data from Apollo.io

## 🔴 THE PROBLEM

Your data is blank because the OpenAI module is getting the **wrong data path**.

---

## ❌ WHAT'S HAPPENING NOW

**Module 18** (HTTP Apollo.io) outputs:
```json
{
  "status": 200,
  "body": {
    "people": [
      {
        "first_name": "John",
        "last_name": "Smith",
        "email": "john@example.com",
        ...
      }
    ]
  },
  "headers": [...]
}
```

**Module 2** (OpenAI) currently uses:
```
{{`18`}}
```

This sends the **ENTIRE bundle** (status, body, headers) to OpenAI!

OpenAI expects just the person's data, not all the HTTP metadata.

---

## ✅ THE FIX

**Change Module 2 to extract just the person data:**

### In Make.com:

1. **Click Module 2** (OpenAI CreateCompletion)
2. **Find the "Messages" section**
3. **Look for the User message**
4. **Change from:**
   ```
   {{`18`}}
   ```
5. **Change to:**
   ```
   {{`18.body.people[0]`}}
   ```

This extracts just the first person from Apollo.io's response!

---

## 🎯 ALTERNATIVE PATHS TO TRY

If `{{`18.body.people[0]`}}` still doesn't work, try:

**Option 1: Full path with nested fields**
```
{{`18.body.people[0]`}}
```

**Option 2: Without index (if array issues)**
```
{{`18.body.people`}}
```

**Option 3: Check if data is in different location**
```
{{`18.body`}}
```

**Option 4: If using older HTTP module format**
```
{{`18.data.people[0]`}}
```

---

## 📋 HOW TO DEBUG

1. **Run Module 18 only** (stop before Module 2)
2. **Click on Module 18's output bundle**
3. **Look at the structure**:
   - Find where "people" array is located
   - Note the exact path (e.g., `body.people[0]`, `data.people[0]`, etc.)
4. **Use that exact path** in Module 2

---

## ✅ VERIFY IT WORKS

After fixing, you should see:
- OpenAI receives just the person's data
- JSON extraction works properly
- Airtable gets populated fields

**Test run and check Module 2's input bundle!**

