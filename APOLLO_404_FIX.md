# 🔧 FIX: Apollo.io 404 Error

## 🔴 THE ERROR

```
[404] Not found
```

**This means:** The API endpoint URL is wrong!

---

## ✅ FIXES TO TRY

### Fix 1: Use Full URL Instead of Path

**In "Make an API Call" module:**

**WRONG:**
```
/v1/mixed_people/search
```

**RIGHT:**
```
https://api.apollo.io/v1/mixed_people/search
```

**Try the FULL URL** in the URL field!

---

### Fix 2: Check Apollo.io API Documentation

The endpoint might be different. Try these alternatives:

**Option A:**
```
https://api.apollo.io/v1/mixed_people/search
```

**Option B:**
```
https://api.apollo.io/v1/people/search
```

**Option C:**
```
https://api.apollo.io/v1/contacts/search
```

**Option D:**
```
https://api.apollo.io/v1/mixed/search
```

---

### Fix 3: Try Different API Endpoint

**Instead of `/v1/mixed_people/search`, try:**

**People Search:**
```
https://api.apollo.io/v1/people/search
```

**Mixed Search (Alternative):**
```
https://api.apollo.io/v1/mixed/search
```

---

### Fix 4: Check Make.com Apollo.io Module Format

**Some Make.com modules require:**
- Just the endpoint path: `/v1/mixed_people/search`
- Others require full URL: `https://api.apollo.io/v1/mixed_people/search`

**Try both!**

---

## 📋 STEP-BY-STEP FIX

### Step 1: Update URL in "Make an API Call" Module

**Try these in order:**

1. **Full URL:**
   ```
   https://api.apollo.io/v1/mixed_people/search
   ```

2. **If that fails, try:**
   ```
   https://api.apollo.io/v1/people/search
   ```

3. **If that fails, try:**
   ```
   https://api.apollo.io/v1/contacts/search
   ```

### Step 2: Verify Method is POST

- **Method:** Should be `POST` (not GET)

### Step 3: Verify Body Format

**Body should be:**
```json
{
  "person_locations": ["California"],
  "page": 1,
  "per_page": 1
}
```

### Step 4: Test Again

Run the scenario and check if 404 is gone!

---

## 🔍 DEBUGGING

### What to Check in Make.com:

1. **Click on the Apollo.io module**
2. **Check the actual request being sent:**
   - Look for "Raw request" or "Request details"
   - See what URL it's actually calling
   - Verify it's using your API key

### Common Issues:

**Issue:** URL has trailing slash  
**Fix:** Remove trailing slash: `https://api.apollo.io/v1/mixed_people/search` (no `/` at end)

**Issue:** URL has extra path  
**Fix:** Make sure it's exactly: `/v1/mixed_people/search`

**Issue:** Wrong API version  
**Fix:** Apollo.io might use `/v1/` or just `/` - try without version: `https://api.apollo.io/mixed_people/search`

---

## 🎯 ALTERNATIVE: Use "List Contacts" Instead

**If search endpoints don't work, try a different approach:**

**Use:** `Apollo.io → CONTACTS → List Contacts`

**This might work as a trigger/action to get contacts, then filter them.**

**Configuration:**
- Might have filters for location, title, etc.
- Could be simpler than API call

---

## ✅ TEST CHECKLIST

- [ ] Tried full URL: `https://api.apollo.io/v1/mixed_people/search`
- [ ] Tried alternative: `https://api.apollo.io/v1/people/search`
- [ ] Verified Method is POST
- [ ] Verified Body is valid JSON
- [ ] Checked API key is correct
- [ ] Checked Apollo.io plan has API access

---

## 🚨 IF STILL 404

**Share this info:**
1. What exact URL you're using (screenshot if possible)
2. Apollo.io plan level
3. The raw request Make.com is sending (if visible)
4. Any other error details

**The endpoint might require different format or your plan might not have access to it!**

---

## 💡 QUICK FIX

**Try this EXACT URL:**
```
https://api.apollo.io/v1/mixed_people/search
```

**Method:** POST  
**Body:**
```json
{"page": 1, "per_page": 1}
```

**Start simple - if this works, add more filters!**
