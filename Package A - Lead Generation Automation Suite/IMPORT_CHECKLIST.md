# ✅ Import Checklist - What Works vs What Needs Configuration

## 🟢 What WILL Work Automatically

1. ✅ **All Module Names** - All modules use verified working identifiers
2. ✅ **Module Structure** - All flows are properly structured
3. ✅ **JSON Parsing References** - All JSON parse modules reference correct OpenAI module IDs
4. ✅ **Basic Connections** - Connection placeholders are set (you'll need to select your actual connections)

## 🟡 What NEEDS Configuration After Import

### 1. **Airtable Connection & Field Mapping** (All Scenarios)
- **Base ID**: `appo7Y0cbtd1wa8Ph` - Replace with YOUR Airtable base ID
- **Table ID**: `tblmVnZaaWToTXxaR` - Replace with YOUR table ID
- **Field IDs**: Field IDs like `fldFU5cYbHBHmTpHr` are specific to YOUR Airtable base
  - Make.com will try to auto-map these, but **verify the field mappings are correct**
  - If fields don't match, manually map them in each Airtable module

### 2. **OpenAI Connection** (All Scenarios)
- Connection placeholder is set, but you need to:
  - Select or create your OpenAI connection
  - Verify API key is valid

### 3. **Gmail/Google Email Connection** (Scenarios B, C, D, E, F)
- Connection placeholder is set, but you need to:
  - Select or create your Gmail connection
  - Authorize access to your Gmail account

### 4. **Twilio Connection** (Scenario E Only)
- Connection needs to be created:
  - Create Twilio connection
  - Configure "From" phone number (replace `+1234567890`)
  - Verify Twilio credentials

### 5. **Scenario F - Gmail Trigger** (Special Case)
- **IMPORTANT**: The blueprint has a webhook trigger
- **You MUST manually replace it**:
  1. Delete the webhook module (Module 1)
  2. Add "Gmail - Watch new emails" trigger
  3. Configure Gmail connection
  4. Connect to Module 2 (OpenAI)

### 6. **Field Name Mappings** (All Scenarios)
Some field references use backticks like `{{1.Contact Full Name}}`:
- These should auto-map, but verify field names match your Airtable schema exactly
- Common fields needed:
  - `Contact Full Name`
  - `Contact Email`
  - `Contact Phone`
  - `Contact Role`
  - `Location City`
  - `Location State`
  - `Company`
  - `Industry`
  - `Employee Count`
  - `Status`
  - `Do Not Contact`
  - `Last Out Reach`
  - `Reply Received`
  - `Email Campaign`
  - `Notes`

---

## 📝 Step-by-Step After Import

### For Each Scenario:

1. **Import the Blueprint** ✅ (Will work)
2. **Configure Airtable Connection**
   - Click on any Airtable module
   - Select/create your Airtable connection
   - Update Base ID if different
   - Update Table ID if different
   - **Verify field mappings** match your schema

3. **Configure OpenAI Connection**
   - Click on OpenAI module
   - Select/create your OpenAI connection
   - Verify model selection (should default to gpt-4o)

4. **Configure Gmail Connection** (if applicable)
   - Click on Gmail module
   - Select/create your Gmail connection
   - Authorize access

5. **Configure Twilio** (Scenario E only)
   - Click on Twilio module
   - Create Twilio connection
   - Update "From" phone number

6. **Verify All Field Mappings**
   - Check each module for red error indicators
   - Verify dropdown fields show correct options
   - Test with sample data

7. **Run Test Execution**
   - Click "Run once" to test
   - Check for errors
   - Verify data flows correctly

---

## ⚠️ Common Issues & Solutions

### Issue: "Field not found" in Airtable
**Solution**: Field names or IDs don't match. Manually map the correct fields in Make.com.

### Issue: "Connection not configured"
**Solution**: Select or create the required connection for that service.

### Issue: JSON Parse error
**Solution**: Verify OpenAI module executed successfully and returned JSON. Check the JSON format matches expected structure.

### Issue: Module shows red error
**Solution**: Click on the module and check what's required. Usually missing connection or field mapping.

---

## ✅ Success Criteria

After configuration, you should see:
- ✅ No red error indicators on modules
- ✅ All connections show as "Connected"
- ✅ Field mappings show correct Airtable fields
- ✅ Test execution completes successfully
- ✅ Data appears correctly in Airtable after test run

---

## 🎯 Bottom Line

**Will everything work right now?** 

**Almost!** The blueprints are technically correct and will import successfully, but you'll need to:

1. ✅ Configure connections (Airtable, OpenAI, Gmail, Twilio)
2. ✅ Verify field mappings match your Airtable schema
3. ✅ Replace Scenario F webhook with Gmail trigger
4. ✅ Update Airtable Base/Table IDs if different
5. ✅ Test each scenario

**Estimated setup time**: 15-30 minutes per scenario (first time), 5-10 minutes after you're familiar.

The blueprints are **ready to import and configure** - they won't have module errors, but they need your specific connections and field mappings to run.

