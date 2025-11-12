# Fix: Airtable 401 Invalid Authentication Token

## ✅ GOOD NEWS!

You got to Airtable! This means:
- ✅ HTTP module (Apollo.io) is working
- ✅ OpenAI module is working
- ✅ Data processing is working
- ❌ Airtable connection/API key is wrong

---

## 🔧 QUICK FIX

### Step 1: Get Your Airtable Personal Access Token

1. **Go to:** https://airtable.com/account
2. **Scroll to:** "Personal access tokens"
3. **Click:** "Create new token"
4. **Give it a name:** "Make.com HELOC"
5. **Set scopes:**
   - ✅ **schema.bases:read**
   - ✅ **data.records:read**
   - ✅ **data.records:write**
6. **Grant access to:**
   - Select your base: "Leads Manager AI CRM" or your base name
7. **Click:** "Create token"
8. **Copy the token** immediately (you won't see it again)

---

### Step 2: Update Airtable Connection in Make.com

1. **Go to Make.com → Settings → Connections**

2. **Find Airtable connection:**
   - If exists → Click to edit
   - If not → Click "Add connection"

3. **Enter your credentials:**
   - **Personal Access Token:** Paste your token
   - **Click "Save"** or "Authorize"
   - **Should show:** "Connected"

---

### Step 3: Update All Airtable Modules

**In your scenario, update:**

**Module 4 (Search Records):**
1. Click Module 4
2. In "Connection" dropdown → Select your Airtable connection
3. **Verify:**
   - Base: `appo7Y0cbtd1wa8Ph`
   - Table: `tblmVnZaaWToTXxaR`
4. Click "OK"

**Module 6 (Create Record):**
1. Click Module 6
2. In "Connection" dropdown → Select your Airtable connection
3. **Verify base/table**
4. Click "OK"

**Module 7 (Update Records):**
1. Click Module 7
2. In "Connection" dropdown → Select your Airtable connection
3. **Verify base/table**
4. Click "OK"

---

## 🔍 VERIFY BASE ID AND TABLE ID

Your Airtable modules should have:

**Base ID:** `appo7Y0cbtd1wa8Ph`

**Table ID:** `tblmVnZaaWToTXxaR`

**How to verify:**
1. Go to your Airtable base
2. Look at URL: `https://airtable.com/appXXXXXXXXXXXXX/...`
3. The base ID is in the URL after `/app`
4. Click on your table, check URL for table ID

---

## 🚀 TEST AGAIN

After fixing:

1. **Save scenario**
2. **Click "Run once"**
3. **Should work now!**

---

## ⚠️ COMMON ISSUES

### Issue: "Base not found"
- **Fix:** Check Base ID is correct
- **Get it from:** Airtable URL after `/app`

### Issue: "Table not found"
- **Fix:** Check Table ID is correct
- **Get it from:** Airtable table URL

### Issue: "Access denied"
- **Fix:** Token doesn't have access to this base
- **Solution:** Regenerate token with correct base selected

---

**Fix the Airtable connection and it will work!** ✅

