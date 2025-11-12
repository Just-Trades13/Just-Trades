# Fix 401 Invalid Authentication Token Error

## 🔴 The Error
```
[401] Invalid authentication token
```

This means your **API key is invalid, expired, or not set correctly**.

---

## 🔍 Which Module Is Failing?

**Check the error in Make.com:**
- Does it say which module failed?
- Check Module 1 (Apollo.io HTTP request)
- Check Module 2 (OpenAI)

---

## ✅ Fix Apollo.io API Key (Module 1)

### Step 1: Get Your Apollo.io API Key

1. **Go to Apollo.io:**
   - https://app.apollo.io/settings/integrations
   - Or: Apollo.io → Settings → Integrations → API

2. **Copy your API key:**
   - It should be a long alphanumeric string
   - No spaces, no quotes
   - If you don't have one, generate it

### Step 2: Add API Key to Module 1

1. **In Make.com, click Module 1** (HTTP request)
2. **Find "API Key" field**
3. **Paste your Apollo.io API key:**
   - No quotes: ❌ `"your-key-here"`
   - No spaces: ❌ `your key here`
   - Just the key: ✅ `yourkeyhere`
4. **Verify "Header Name" is:** `X-Api-Key`
5. **Click "OK" to save**

### Step 3: Test

- **Run the scenario manually**
- **Check Module 1 output:**
  - Should return 200 (not 401 or 403)
  - Should have `body.people[]` array

---

## ✅ Fix OpenAI API Key (Module 2)

### Step 1: Get Your OpenAI API Key

1. **Go to OpenAI:**
   - https://platform.openai.com/api-keys

2. **Create new API key:**
   - Click "Create new secret key"
   - Give it a name (e.g., "Make.com")
   - Copy it immediately (you won't see it again)
   - Starts with `sk-`

### Step 2: Update Connection in Make.com

1. **Go to Make.com → Settings → Connections**

2. **Delete existing OpenAI connection** (if any)

3. **Create new connection:**
   - Click "Add connection"
   - Search "OpenAI"
   - Select "OpenAI GPT-3"
   - Paste your API key
   - Click "Save" or "Authorize"
   - Should show "Connected"

### Step 3: Update Module 2

1. **Click Module 2** (OpenAI) in your scenario
2. **In "Connection" dropdown:**
   - Select your NEW OpenAI connection
3. **Verify model:** `gpt-3.5-turbo`
4. **Click "OK" to save**

---

## 🔍 Common Issues

### Issue: "API key format invalid"
- **Fix:** Remove any quotes, spaces, or extra characters
- **Apollo.io:** Just the key, nothing else
- **OpenAI:** Should start with `sk-`

### Issue: "API key expired"
- **Fix:** Generate a new API key
- **Apollo.io:** Go to Settings → Integrations → API → Generate new
- **OpenAI:** Go to API Keys → Create new secret key

### Issue: "Connection not found"
- **Fix:** Recreate the connection in Make.com
- **For OpenAI:** Delete and create new connection
- **For Apollo.io:** Make sure API key field is filled in Module 1

### Issue: "Wrong API key in wrong place"
- **Fix:** Double-check:
  - **Module 1** → Apollo.io API key
  - **Module 2** → OpenAI connection (with OpenAI API key)

---

## 🚀 Test After Fixing

1. **Run scenario manually** (click "Run once")
2. **Check Module 1:** Should return 200 with data
3. **Check Module 2:** Should process without 401 error
4. **Check Module 3+:** Should continue successfully

---

## ⚠️ Important Notes

- **API keys are sensitive** - don't share them
- **Each API key is unique** - can't reuse
- **Check billing** - API keys need active billing
- **Apollo.io:** Requires paid plan for `/v1/mixed_people/search` endpoint

---

**Most common issue:** API key field is empty or has wrong key. Double-check both Module 1 and Module 2!

