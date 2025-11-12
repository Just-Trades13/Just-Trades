# Missing Authentication Header - Apollo.io

## 📦 What Your Input Bundle Shows

Your input bundle shows Make.com is preparing:
- ✅ URL: Correct
- ✅ Method: POST
- ✅ Headers: Content-Type: application/json
- ✅ Body: Valid JSON

**But it's missing the authentication header!**

---

## ❌ The Problem

Apollo.io requires an **`X-Api-Key`** header with your API key.

**Your input bundle shows:**
```json
"headers": [
    {
        "key": "Content-Type",
        "value": "application/json"
    }
]
```

**Missing:**
```json
{
    "key": "X-Api-Key",
    "value": "your-api-key-here"
}
```

---

## ✅ Why This Happens

The Apollo.io module in Make.com should **automatically** add the `X-Api-Key` header from your connection.

**If it's not showing up, it means:**
1. **Connection has no API key** → Add it
2. **API key is invalid/expired** → Regenerate
3. **Connection not properly authenticated** → Recreate connection

---

## 🔧 How to Fix

### Step 1: Check Apollo.io Connection

1. **In Make.com:**
   - Go to **Settings** → **Connections**
   - Find **"My Apollo connection"**

2. **Click to edit/view:**
   - Look for **"API Key"** or **"Authentication"** field
   - Is it filled? → Might be wrong
   - Is it empty? → Add your API key

---

### Step 2: Get Fresh API Key

1. **Go to Apollo.io:**
   - https://app.apollo.io/settings/integrations
   - Click **"API"** section

2. **Generate new API key:**
   - Click **"Create API Key"** or **"Generate"**
   - Name it: "Make.com"
   - **Copy it immediately** (you won't see it again)

---

### Step 3: Update Connection

**Option A: Update Existing Connection**

1. **In Make.com → Settings → Connections**
2. **Click "My Apollo connection"**
3. **Update API key field:**
   - Paste your new API key
   - Click **"Save"**
4. **Verify:** Should show "Connected" status

**Option B: Create New Connection**

1. **Delete existing connection**
2. **Create new:**
   - Click **"Add connection"**
   - Search **"Apollo"**
   - Enter your API key
   - Click **"Save"**
3. **Update Module 1:**
   - Select the new connection

---

### Step 4: Verify

After updating connection:

1. **Run scenario again**
2. **Check input bundle** (if you can see it)
3. **Should now include:**
   ```json
   {
       "key": "X-Api-Key",
       "value": "your-actual-api-key"
   }
   ```
4. **Response should be 200** (not 404)

---

## 🔍 Alternative: Manual HTTP Module

If Apollo.io module keeps having issues, use HTTP module directly:

1. **Delete Apollo module**
2. **Add HTTP module:**
   - Search: **"HTTP - Make an API Key Auth request"**
   - **URL:** `https://api.apollo.io/v1/mixed_people/search`
   - **Method:** `POST`
   - **API Key:** Your Apollo.io API key
   - **Header Name:** `X-Api-Key`
   - **Body:** Your JSON (same as before)

This way you control the auth header directly.

---

## 📋 Verification

After fixing connection, verify:

- [ ] **Connection has API key** filled in
- [ ] **Connection status:** "Connected"
- [ ] **Module 1 uses correct connection**
- [ ] **Input bundle shows X-Api-Key header** (if visible)
- [ ] **Response is 200** (not 404)

---

## ⚠️ Important Notes

1. **Free plan users:** Even with correct API key, `/v1/mixed_people/search` returns 404
2. **API keys expire:** Generate new one if old doesn't work
3. **Connection vs Manual:** Apollo module auto-adds auth; HTTP module you add manually

---

**Bottom line:** Your API key isn't being added to the request. Fix the connection in Make.com with a valid API key!

