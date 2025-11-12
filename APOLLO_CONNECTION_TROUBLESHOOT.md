# Apollo.io Connection Troubleshooting - 404 Error

## ✅ Your Configuration is CORRECT

Your Make.com module shows:
- ✅ URL: `https://api.apollo.io/v1/mixed_people/search`
- ✅ Method: `POST`
- ✅ Headers: `Content-Type: application/json`
- ✅ Body: Valid JSON with HELOC search criteria

**Since the config is correct, the issue is with the connection or API key.**

---

## 🔍 Root Cause: Connection/API Key Issue

The Apollo.io module in Make.com handles authentication automatically through the **connection**. If you're getting 404, it's likely:

1. **API key not set in connection**
2. **API key is invalid/expired**
3. **API key from free plan** (endpoint requires paid)
4. **Connection not properly authenticated**

---

## ✅ Step-by-Step Fix

### Step 1: Check Your Apollo.io Connection

1. **In Make.com:**
   - Go to **Settings** → **Connections**
   - Or click **"Add"** next to connection dropdown in Module 1

2. **Find "My Apollo connection"**

3. **Click to edit/view:**
   - Check if API key field is filled
   - If empty → Add your API key
   - If filled → Might be wrong/expired

---

### Step 2: Get Fresh Apollo.io API Key

1. **Go to Apollo.io:**
   - https://app.apollo.io/settings/integrations
   - Or: Apollo.io → Settings → Integrations → API

2. **Create new API key:**
   - Click "Create API Key" or "Generate"
   - Give it a name (e.g., "Make.com")
   - **Copy it immediately** (you won't see it again)

3. **Verify key format:**
   - Should be alphanumeric string
   - No spaces or special characters
   - Usually 30-50 characters long

---

### Step 3: Update Connection in Make.com

1. **In Make.com → Settings → Connections:**

2. **Edit "My Apollo connection":**
   - Delete existing connection
   - Create new connection
   - Paste your new API key
   - Click "Save" or "Authorize"
   - Should show "Connected" status

3. **Or update existing:**
   - Click on connection
   - Update API key field
   - Save

---

### Step 4: Verify Apollo.io Plan

**This endpoint requires a PAID plan!**

1. **Check your plan:**
   - Go to: https://app.apollo.io/settings/billing
   - Verify you have:
     - ✅ **Basic Plan** ($49/month) or higher
     - ❌ **Free Plan** → Will return 404

2. **If you have free plan:**
   - **Option 1:** Upgrade to Basic ($49/month)
   - **Option 2:** Use webhook version (`Nelson_HELOC_Webhook_Blueprint.json`)

---

### Step 5: Test Again

1. **Save your connection changes**

2. **Run the scenario manually** (click "Run once")

3. **Check Module 1 output:**
   - Should return **200** (not 404)
   - Should have `people[]` array in response

---

## 🔍 Alternative: Use HTTP Module Instead

If the Apollo.io module keeps having issues, you can use the HTTP module directly:

1. **Delete the Apollo module**

2. **Add HTTP module:**
   - Search for "HTTP" → "Make an API Key Auth request"
   - Configure:
     - **URL:** `https://api.apollo.io/v1/mixed_people/search`
     - **Method:** `POST`
     - **API Key:** Your Apollo.io API key
     - **Header Name:** `X-Api-Key`
     - **Body:** Your JSON (same as before)

3. **This bypasses connection issues**

---

## 📋 Verification Checklist

After fixing, verify:

- [ ] **Connection:** "My Apollo connection" has valid API key
- [ ] **API Key:** Fresh, from paid Apollo.io account
- [ ] **Plan:** Paid plan (not free)
- [ ] **URL:** `https://api.apollo.io/v1/mixed_people/search`
- [ ] **Method:** `POST`
- [ ] **Headers:** `Content-Type: application/json`
- [ ] **Body:** Valid JSON

---

## ⚠️ Important Notes

1. **Free plan users:** This endpoint returns 404 even with correct config
2. **API keys expire:** Generate new one if old one doesn't work
3. **Connection vs HTTP:** Apollo module uses connection; HTTP module uses direct API key

---

**Most likely fix:** Update the API key in your Apollo.io connection with a fresh key from a paid account!

