# 🔑 API Key Auth Request Setup - Perfect for Apollo.io!

## ✅ Use This Module!

**"Make an API Key Auth request"** is **PERFECT** for Apollo.io because:
- ✅ Built for API Key authentication (Apollo.io uses X-Api-Key)
- ✅ Handles authentication automatically
- ✅ Easier setup than regular HTTP module
- ✅ Less configuration needed

---

## 📋 Step-by-Step Configuration

### Step 1: Select the Module

You're already here! You see:
- **"Make an API Key Auth request"** (highlighted in purple)
- Click on it to configure

---

### Step 2: Configure the Module

After clicking "Make an API Key Auth request", you'll see configuration fields:

#### **API Key**
- **Field**: Enter your Apollo.io API key here
- **Get API key**: Apollo.io → Settings → Integrations → API → Connect → Copy key
- Paste your key in this field

#### **Header Name** (or API Key Header Name)
- **Default**: Usually `X-Api-Key` or `Authorization`
- **For Apollo.io**: Should be `X-Api-Key`
- If the default isn't `X-Api-Key`, change it to: `X-Api-Key`

#### **URL***
- **Enter**: `https://api.apollo.io/v1/mixed_people/search`
- This is the Apollo.io People Search API endpoint

#### **Method***
- **Select**: `POST` (from dropdown)
- Apollo.io requires POST for searching people

#### **Body Type** or **Request Body**
- **Select**: `JSON` (from dropdown)
- A text box will appear for JSON body

#### **Body** (JSON Content)
Paste this JSON:

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

#### **Parse Response**
- **Select**: `Yes` (if available)
- This automatically parses JSON so you can use `body.people[0]`

---

## ✅ Configuration Summary

Your "Make an API Key Auth request" module should have:

- ✅ **API Key**: `YOUR_APOLLO_API_KEY` (your actual key)
- ✅ **Header Name**: `X-Api-Key`
- ✅ **URL**: `https://api.apollo.io/v1/mixed_people/search`
- ✅ **Method**: `POST`
- ✅ **Body Type**: `JSON`
- ✅ **Body**: JSON with HELOC search criteria
- ✅ **Parse Response**: `Yes` (if option available)

---

## 🧪 Test It

1. **Click "Save"**
2. **Click "Run once"** button
3. **Check output**:
   - Should return Apollo.io API response
   - Should have `people` array with contact data
   - Status should be 200 (success)

---

## 📊 Expected Output Structure

After running, the module returns:

```json
{
  "people": [
    {
      "first_name": "Sarah",
      "last_name": "Johnson",
      "email": "sarah@example.com",
      "phone_numbers": [...],
      "organization_name": "ABC Property Management",
      "title": "Property Manager",
      "city": "Phoenix",
      "state": "AZ",
      "linkedin_url": "...",
      ...
    }
  ],
  "pagination": {...}
}
```

---

## 🔗 Connect to OpenAI Module

The API Key Auth module output structure is the same as regular HTTP module:

1. **Connect**: API Key Auth module → Module 2 (OpenAI)

2. **Update OpenAI User Message**:
   - Click Module 2 (OpenAI)
   - Find "User Message" field
   - Set to: `{{`1.body.people[0]`}}`
   - This tells OpenAI to use the first person from Apollo.io results

3. **Save**

---

## 🎯 Why This Module is Better

**"Make an API Key Auth request"** vs Regular HTTP:

| Feature | API Key Auth | Regular HTTP |
|---------|-------------|--------------|
| API Key Setup | ✅ Separate field | ❌ Manual header |
| Authentication | ✅ Automatic | ❌ Manual |
| Configuration | ✅ Easier | ❌ More steps |
| Best For | ✅ Apollo.io (API Key) | General APIs |

**This module is specifically designed for APIs like Apollo.io that use API key authentication!**

---

## ✅ After Setup Checklist

- [ ] API Key entered (your Apollo.io API key)
- [ ] Header Name = `X-Api-Key`
- [ ] URL = Apollo.io API endpoint
- [ ] Method = POST
- [ ] Body = JSON with search criteria
- [ ] Parse Response = Yes (if available)
- [ ] Connected to Module 2 (OpenAI)
- [ ] OpenAI User Message = `{{`1.body.people[0]`}}`
- [ ] Tested - returns person data
- [ ] Verified end-to-end flow works

---

**This is the perfect module for Apollo.io! Much easier than regular HTTP module.**

