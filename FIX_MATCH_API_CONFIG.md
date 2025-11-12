# 🔧 FIX: Apollo.io Match API Configuration

## ❌ ISSUES IN YOUR CONFIG

1. **URL is relative:** `/v1/people/match`
   - Should be: `https://api.apollo.io/v1/people/match`

2. **Body is wrong:** Using pagination parameters
   ```json
   {
     "page": 1,
     "per_page": 50
   }
   ```
   - Should use contact matching parameters!

---

## ✅ CORRECT CONFIGURATION

### URL:
```
https://api.apollo.io/v1/people/match
```
(Full URL, not relative path)

### Method:
```
POST
```

### Headers:
```
Content-Type: application/json
X-Api-Key: DtdKb5hTo_9GTtbohlNJ-Q
```

### Body (JSON):
```json
{
  "first_name": "{{21.first_name}}",
  "last_name": "{{21.last_name}}",
  "organization_name": "{{21.organization.name}}"
}
```

**OR if organization.name doesn't work, try:**
```json
{
  "first_name": "{{21.first_name}}",
  "last_name": "{{21.last_name}}",
  "organization_name": "{{21.organization_name}}"
}
```

---

## 📋 STEP-BY-STEP IN MAKE.COM

### Step 1: Fix URL

1. **Click the HTTP module** (between Module 21 and Module 2)
2. **Find "URL" field**
3. **Change from:** `/v1/people/match`
4. **Change to:** `https://api.apollo.io/v1/people/match`
5. **Click OK**

### Step 2: Fix Body

1. **Find "Body" or "Request Content" field**
2. **Change Body Type:** Select "Raw" or "JSON"
3. **Delete the current body:**
   ```json
   {
     "page": 1,
     "per_page": 50
   }
   ```

4. **Add correct body:**
   ```json
   {
     "first_name": "{{21.first_name}}",
     "last_name": "{{21.last_name}}",
     "organization_name": "{{21.organization.name}}"
   }
   ```

5. **To find correct field names:**
   - Click the mapping icon `{}`
   - Navigate to Module 21 (Iterator)
   - Find `first_name`, `last_name`, `organization.name`
   - Use those exact paths

6. **Click OK**

### Step 3: Verify Headers

**Headers should be:**
- `Content-Type`: `application/json`
- `X-Api-Key`: `DtdKb5hTo_9GTtbohlNJ-Q`

**If headers look different, fix them!**

---

## ✅ EXPECTED RESPONSE

**After fixing, the Match API will return:**
```json
{
  "person": {
    "id": "...",
    "first_name": "Mike",
    "last_name": "Braham",
    "email": "mike.braham@intempohealth.com",  // ✅ UNLOCKED!
    "organization_name": "Intempo Health",
    ...
  }
}
```

**Use `{{X.person.email}}` to get the unlocked email!**

(Where X = your HTTP module number)

---

## 🔄 THEN UPDATE OTHER MODULES

### Module 2 (OpenAI):
- Change input to use: `{{X.person.email}}` or `{{X.email}}`
- Check the response structure to see exact path

### Module 6 (Airtable Create):
- Contact Email field: Change to `{{X.person.email}}`

---

**Fix the URL and body, then test it!** 🔧

