# 🔧 Troubleshoot: Apollo.io Match API Error

## 🎯 WHAT ERROR DID YOU GET?

**Common errors and fixes:**

### Error 1: "404 Not Found"
**Cause:** Wrong URL path  
**Fix:** Use relative path `/v1/people/match` (not full URL)

### Error 2: "400 Bad Request"
**Cause:** Missing or wrong body parameters  
**Fix:** Ensure body has `first_name`, `last_name`, `organization_name`

### Error 3: "401 Unauthorized"
**Cause:** API key wrong or missing  
**Fix:** Check X-Api-Key header

### Error 4: "422 Unprocessable Entity"
**Cause:** Invalid body format or missing fields  
**Fix:** Check body JSON structure

---

## ✅ CORRECT CONFIGURATION

### If Using Apollo.io Native Module:

**URL:** Use RELATIVE path
```
/v1/people/match
```

**NOT the full URL!** (The module adds the base URL automatically)

### If Using Generic HTTP Module:

**URL:** Use FULL URL
```
https://api.apollo.io/v1/people/match
```

---

## 📋 STEP-BY-STEP FIXES

### Fix 1: Check Module Type

**Are you using:**
- **Apollo.io "Make an API Call" module?** → Use relative path `/v1/people/match`
- **Generic HTTP "Make a Request" module?** → Use full URL `https://api.apollo.io/v1/people/match`

### Fix 2: URL Configuration

**For Apollo.io Module:**
1. Change URL to: `/v1/people/match`
2. Remove `https://api.apollo.io` prefix

**For HTTP Module:**
1. Keep URL as: `https://api.apollo.io/v1/people/match`
2. Ensure it's the full URL

### Fix 3: Body Configuration

**Required fields:**
```json
{
  "first_name": "{{21.first_name}}",
  "last_name": "{{21.last_name}}",
  "organization_name": "{{21.organization.name}}"
}
```

**Check:**
- Body type is "Raw" or "JSON"
- All three fields are present
- Field paths reference Module 21 correctly

### Fix 4: Headers

**Required headers:**
- `Content-Type`: `application/json`
- `X-Api-Key`: `DtdKb5hTo_9GTtbohlNJ-Q`

---

## 🔍 DEBUGGING STEPS

### Step 1: Check Error Message
**What exact error do you see?**
- Share the error message
- Check which module failed

### Step 2: Test Module 21 Output
**Before the HTTP module, check:**
- Click Module 21 (Iterator)
- Check output bundle
- Verify `first_name`, `last_name`, `organization.name` exist

### Step 3: Test HTTP Module Input
**Click HTTP module and check:**
- Input bundle shows correct data from Module 21
- Body fields are populated

### Step 4: Check HTTP Module Output
**After running, check:**
- Does it return `person` object?
- Does `person.email` exist?
- Or does it show an error?

---

## ✅ EXPECTED WORKING CONFIG

### Apollo.io Native Module:
```
Module Type: Apollo.io → Make an API Call
URL: /v1/people/match
Method: POST
Body:
{
  "first_name": "{{21.first_name}}",
  "last_name": "{{21.last_name}}",
  "organization_name": "{{21.organization.name}}"
}
```

### Generic HTTP Module:
```
Module Type: HTTP → Make a Request
URL: https://api.apollo.io/v1/people/match
Method: POST
Headers:
  Content-Type: application/json
  X-Api-Key: DtdKb5hTo_9GTtbohlNJ-Q
Body (Raw/JSON):
{
  "first_name": "{{21.first_name}}",
  "last_name": "{{21.last_name}}",
  "organization_name": "{{21.organization.name}}"
}
```

---

**Share the exact error message and I'll help you fix it!** 🔧

