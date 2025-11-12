# 📋 Body Type Configuration for Apollo.io

## What You're Seeing

The "Body type" dropdown shows:
- Empty
- Raw
- Application/x-www-form-urlencoded
- Multipart/form-data

**You need to select "Raw"** for JSON data.

---

## Step-by-Step:

### 1. Select "Raw"
- **Click the dropdown** (Body type field)
- **Select "Raw"** from the list
- After selecting "Raw", a text box should appear for the body content

### 2. Enter JSON Body
After selecting "Raw", you'll see a text box. **Paste this JSON**:

```json
{
  "q_keywords": "homeowner property owner",
  "person_titles": ["Property Manager", "Real Estate Agent", "Homeowner"],
  "person_locations": ["Arizona", "California", "Florida", "Texas", "Nevada"],
  "organization_industries": ["Real Estate", "Construction", "Property Management"],
  "page": 1,
  "per_page": 1
}
```

### 3. Content Type (If Asked)
If there's a "Content Type" or "MIME Type" field that appears:
- Select or enter: `application/json`

But don't worry - you already set the `Content-Type: application/json` header earlier, so "Raw" with that header is correct!

---

## Why "Raw"?
- **Raw** = Send body as-is (like JSON text)
- **Application/x-www-form-urlencoded** = Form data (not what we need)
- **Multipart/form-data** = File uploads (not what we need)

**"Raw" is correct for JSON!**

---

## Complete Setup Checklist

- [x] API Key: Your Apollo.io API key
- [x] Header Name: X-Api-Key  
- [x] URL: https://api.apollo.io/v1/mixed_people/search
- [x] Method: POST
- [ ] **Body type: Raw** ← Select this now
- [ ] **Body: Paste JSON** ← After selecting Raw
- [ ] Save

---

**Select "Raw" and paste the JSON body - that's it!**

