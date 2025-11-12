# 📥 Import Instructions - Nelson HELOC Lead Capture

## ✅ YOUR BLUEPRINT IS READY!

**File:** `Nelson_HELOC_Blueprint_READY_TO_IMPORT.json`

**Size:** ~189KB
**Format:** Valid Make.com blueprint JSON
**Status:** ✅ Ready to import

---

## 🎯 HOW TO IMPORT INTO MAKE.COM

### Step 1: Go to Make.com
1. **Login** to your Make.com account
2. Go to **"Scenarios"** in the left menu
3. Click **"Create a new scenario"** button

### Step 2: Import Blueprint
1. Click **"Import"** button (top right or in menu)
2. Select **"Import from file"**
3. Click **"Choose file"** or drag & drop
4. **Upload:** `Nelson_HELOC_Blueprint_READY_TO_IMPORT.json`
5. Click **"Import"**

### Step 3: Wait for Import
- Make.com will parse the blueprint
- Modules will appear in your scenario
- You'll see: "Scenario imported successfully"

---

## ⚙️ CONFIGURE CONNECTIONS

After import, you need to set 2 connections:

### ✅ Connection 1: OpenAI

1. **Click Module 2** (OpenAI module)
2. In **"Connection"** dropdown:
   - If you have a connection → Select it
   - If not → Click **"Add connection"**
3. **Enter your OpenAI API key:**
   - Get from: https://platform.openai.com/api-keys
   - Paste the key (starts with `sk-`)
   - Click **"Save"**
4. **Verify model:** `gpt-3.5-turbo`
5. Click **"OK"**

### ✅ Connection 2: Airtable

1. **Click Module 4** (Airtable Search Records)
2. In **"Connection"** dropdown:
   - If you have a connection → Select it
   - If not → Click **"Add connection"**
3. **Enter your Airtable credentials:**
   - Get from: https://airtable.com/account
   - Paste your Personal Access Token
   - Click **"Save"**
4. **Verify Base and Table:**
   - Base: `appo7Y0cbtd1wa8Ph`
   - Table: `tblmVnZaaWToTXxaR`
5. Click **"OK"**

### ✅ Repeat for Module 6 & 7
- **Module 6** (Airtable Create) - set same Airtable connection
- **Module 7** (Airtable Update) - set same Airtable connection

---

## 🔧 CONFIGURE MODULE 3 (Parse JSON)

1. **Click Module 3** (Parse JSON)
2. **In "Data structure" dropdown:**
   - Select **"AI JSON"** (if available)
   - OR click **"Create new"**
3. **If creating new:**
   - Click **"Add"** to create structure
   - The blueprint already has all field definitions
   - Make.com will auto-suggest from JSON input
4. Click **"OK"**

---

## ✅ VERIFY CONFIGURATION

Before running, check:

### Module 1 (HTTP - Make an API Key Auth request)
- [x] URL: `https://api.apollo.io/v1/mixed_people/search`
- [x] Method: `POST`
- [x] API Key: **Pre-filled** (`DtdKb5hTo_9GTtbohlNJ-Q`)
- [x] Body: HELOC search criteria
- [x] Parse Response: `Yes`

### Module 2 (OpenAI)
- [x] Connection: Set
- [x] Model: `gpt-3.5-turbo`
- [x] User message: Configured

### Module 3 (Parse JSON)
- [x] Data structure: Selected

### Module 4-7 (Airtable & Router)
- [x] Connections: Set
- [x] Base/Table: Configured

---

## 🚀 TEST THE SCENARIO

### Step 1: Save Scenario
1. Click **"Save scenario"** button
2. Give it a name: "Nelson HELOC Lead Capture"

### Step 2: Run Test
1. Click **"Run once"** button
2. Watch the execution progress
3. Check each module output

### Step 3: Check Results

**Module 1 Output:**
- Should return **200** status
- Should have `people[]` array
- Contains lead data

**Module 2 Output:**
- AI-processed JSON
- All HELOC fields filled

**Module 3 Output:**
- Parsed structured data
- Ready for Airtable

**Module 4-7:**
- Search for duplicates
- Create or update record
- Saved to Airtable

### Step 4: Verify in Airtable
1. Go to your Airtable base
2. Check table: `tblmVnZaaWToTXxaR`
3. **Should see new lead record!**

---

## 🔒 SECURITY: REGENERATE API KEY

**⚠️ IMPORTANT:** The API key in the blueprint was shared publicly!

**After successful test:**

1. **Go to:** https://app.apollo.io/settings/integrations → API
2. **Delete old API key:** `DtdKb5hTo_9GTtbohlNJ-Q`
3. **Create new API key**
4. **Update Module 1** in Make.com with new key
5. **Save scenario**

---

## 📊 WHAT THE AUTOMATION DOES

1. **Search Apollo.io** for HELOC prospects
2. **AI Process** the lead data
3. **Parse JSON** to structured format
4. **Check Airtable** for duplicates
5. **Create new** or **Update existing** lead
6. **Save** to your CRM automatically

**Trigger Options:**
- **Manual:** Run "Run once" anytime
- **Scheduled:** Set to run hourly/daily
- **Webhook:** Trigger from external system

---

## 🐛 TROUBLESHOOTING

### Error: "Module not found"
- Some modules require manual setup after import
- See module-specific guides

### Error: "Connection failed"
- Check API keys are correct
- Verify connections are saved

### Error: "Parse JSON structure"
- Select "AI JSON" type
- Or create structure manually

### Error: "Airtable not found"
- Verify Base ID is correct
- Check table ID matches
- Ensure Airtable connection has access

### Error: "No leads found"
- Apollo.io search returned 0 results
- Adjust search criteria in Module 1 Body
- Try different keywords/locations

---

## 📞 NEED HELP?

Check these guides:
- `APOLLO_MODULE_SETUP_STEPS.md`
- `HTTP_MODULE_SETUP_COMPLETE.md`
- `OPENAI_CONNECTION_FIX.md`
- `401_ERROR_FIX.md`
- `APOLLO_404_FIX.md`

---

## ✅ SUCCESS CHECKLIST

After successful import and test:

- [ ] Blueprint imported successfully
- [ ] All connections configured
- [ ] Module 3 data structure set
- [ ] Test run completed successfully
- [ ] New lead appears in Airtable
- [ ] API key regenerated for security
- [ ] Scenario saved and named
- [ ] Automation scheduled (if desired)

---

**Your HELOC lead generation automation is ready! 🎉**

