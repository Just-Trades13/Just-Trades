# ✅ Import Checklist - Package 4A

## 🟢 What WILL Work Automatically

1. ✅ **All Module Names** - All modules use verified working identifiers
2. ✅ **Module Structure** - All flows are properly structured
3. ✅ **JSON Parsing References** - All JSON parse modules reference correct OpenAI module IDs
4. ✅ **Basic Connections** - Connection placeholders are set (you'll need to select your actual connections)
5. ✅ **Router Logic** - All conditional routing configured correctly

---

## 🟡 What NEEDS Configuration After Import

### 1. **Airtable Connection & Field Mapping** (All Scenarios)
- **Base ID**: `appo7Y0cbtd1wa8Ph` - Replace with YOUR Airtable base ID
- **Table ID**: `tblmVnZaaWToTXxaR` - Replace with YOUR table ID
- **Field IDs**: Field IDs are specific to YOUR Airtable base
  - Make.com will try to auto-map these, but **verify the field mappings are correct**
  - If fields don't match, manually map them in each Airtable module

**Required Airtable Fields**:
- `Contact Email` (Email type)
- `Contact Phone` (Phone number type)
- `Contact Full Name` (Single line text)
- `Contact Role` (Single line text)
- `Company` (Single line text)
- `Industry` (Single line text)
- `Status` (Single select)
- `Last Out Reach` (Date)
- `Reply Received` (Checkbox)
- `Meeting Booked` (Checkbox)
- `Do Not Contact` (Checkbox)
- `Email Campaign` (Single line text)
- `Notes` (Long text)

**Optional Fields**:
- `Reactivation Stage` (Single select: `stage_1`, `stage_2`, `stage_3`, `completed`) - For Scenario 4A-D
- `Lead Score` (Number) - For Scenario 4A-E
- `Engagement History` (Long text) - Optional for Scenario 4A-E

---

### 2. **OpenAI Connection** (All Scenarios Except Analytics)
- Connection placeholder is set, but you need to:
  - Select or create your OpenAI connection
  - Verify API key is valid
  - Verify model selection (should default to gpt-4o)
  - Verify format is set to JSON object

---

### 3. **Gmail/Google Email Connection** (All Scenarios)
- Connection placeholder is set, but you need to:
  - Select or create your Gmail connection
  - Authorize access to your Gmail account
  - Configure "To" email addresses (for Scenario 4A-F analytics)
  - Verify sender email is authenticated

---

### 4. **Twilio Modules** (CRITICAL - Scenarios Using SMS)
- **Status**: Twilio modules are NOT importable via JSON - they appear as "Module Not Found"
- **Action Required**:
  1. Delete the "Module Not Found" Twilio module after import
  2. Add Twilio "Create a Message" module manually in Make.com UI
  3. Configure Twilio connection (Account SID, Auth Token)
  4. Map fields:
     - **To**: Phone number field (e.g., `{{1.Contact Phone}}`)
     - **From**: Your Twilio phone number (e.g., `+1234567890`)
     - **Body**: Message text (include "Reply STOP to opt out.")
  5. Test SMS sending capability

**Scenarios Using Twilio**:
- Scenario 4A-A: Module 8 (SMS path)
- Scenario 4A-B: Module 11 (SMS path)
- Scenario 4A-C: Module 6 (SMS path)
- Scenario 4A-D: Module 9 (SMS path)
- Scenario 4A-E: Module 8 (SMS path)

---

### 5. **Schedule Module** (Scenario 4A-F)
- **Status**: Uses webhook as placeholder
- **Action Required**:
  1. Delete webhook module (Module 1)
  2. Add Schedule module manually
  3. Configure schedule (daily or weekly recommended)
  4. Connect to Module 2 (Airtable Search)

---

### 6. **Schedule Automation for Scenario 4A-D** (CRITICAL)
- **Status**: Requires separate schedule scenario to advance stages
- **Action Required**:
  Create a separate Make.com scenario with:
  1. Schedule trigger (daily at specific time)
  2. Airtable Search Records:
     - Find leads with `Reactivation Stage` = `stage_1` and `Last Out Reach` < TODAY() - 3
     - Update to `stage_2`
  3. Repeat for `stage_2` → `stage_3` (Day 7)

---

### 7. **Field Name Mappings** (All Scenarios)
Some field references use backticks like `{{1.Contact Full Name}}`:
- These should auto-map, but verify field names match your Airtable schema exactly
- Common fields needed (see list above)

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

3. **Configure OpenAI Connection** (if applicable)
   - Click on OpenAI module
   - Select/create your OpenAI connection
   - Verify model selection (should default to gpt-4o)
   - Verify API key is valid
   - Verify format is JSON object

4. **Configure Gmail/Google Email Connection**
   - Click on Gmail module
   - Select/create your Gmail connection
   - Authorize access
   - Configure recipient email addresses (for analytics)

5. **Configure Twilio Connection** (if using SMS)
   - Delete "Module Not Found" Twilio module
   - Add Twilio "Create a Message" module manually
   - Create Twilio connection
   - Enter Account SID and Auth Token
   - Update "From" phone number
   - Test connection

6. **Add Manual Modules** (if needed)
   - **Scenario 4A-F**: Add Schedule module (replace webhook)
   - **Scenario 4A-D**: Create separate schedule scenario for stage advancement

7. **Verify All Field Mappings**
   - Check each module for red error indicators
   - Verify dropdown fields show correct options
   - Test with sample data

8. **Run Test Execution**
   - Click "Run once" to test
   - Verify data flows correctly
   - Check for errors
   - Verify data appears correctly in Airtable

---

## ⚠️ Common Issues & Solutions

### Issue: "Airtable field not found"
**Solution**: Field names or IDs don't match. Manually map the correct fields in Make.com. Verify field names match exactly (case-sensitive).

### Issue: "Connection not configured"
**Solution**: Select or create the required connection for that service.

### Issue: JSON Parse error
**Solution**: 
- Verify OpenAI module executed successfully and returned JSON
- Check the JSON format matches expected structure
- Verify OpenAI module ID in JSON parse reference (see QUICK_REFERENCE_JSON_PARSING.md)

### Issue: Module shows red error
**Solution**: Click on the module and check what's required. Usually missing connection or field mapping.

### Issue: Email not sending
**Solution**: 
- Verify Gmail connection is authorized
- Check recipient email addresses are valid
- Verify sender email is authenticated (SPF/DKIM/DMARC)

### Issue: Twilio module shows "Module Not Found"
**Solution**: This is expected. Delete it and add Twilio "Create a Message" module manually.

### Issue: Schedule not triggering (Scenario 4A-F)
**Solution**: Replace webhook with Schedule module and configure schedule frequency.

### Issue: Stages not advancing (Scenario 4A-D)
**Solution**: Create separate schedule scenario to advance `Reactivation Stage` field.

### Issue: OpenAI returning errors
**Solution**: 
- Verify API key is valid
- Check API usage limits
- Verify model selection (gpt-4o recommended)
- Check input prompt length
- Verify format is set to JSON object

---

## ✅ Success Criteria

After configuration, you should see:
- ✅ No red error indicators on modules
- ✅ All connections show as "Connected"
- ✅ Field mappings show correct Airtable fields
- ✅ Test execution completes successfully
- ✅ Email/SMS messages send correctly (test with real contacts)
- ✅ Data appears correctly in Airtable after test run
- ✅ AI generates personalized messages correctly
- ✅ JSON parsing works correctly

---

## 🎯 Bottom Line

**Will everything work right now?** 

**Almost!** The blueprints are technically correct and will import successfully, but you'll need to:

1. ✅ Configure connections (Airtable, OpenAI, Gmail, Twilio if using SMS)
2. ✅ Verify field mappings match your Airtable schema
3. ✅ Update Airtable Base/Table IDs if different
4. ✅ Add Twilio modules manually (if using SMS scenarios)
5. ✅ Replace webhook with Schedule module (Scenario 4A-F)
6. ✅ Create schedule scenario for stage advancement (Scenario 4A-D)
7. ✅ Test each scenario with real data

**Estimated setup time**: 
- **First scenario**: 30-45 minutes (includes learning curve)
- **Subsequent scenarios**: 15-25 minutes each
- **After familiar**: 10-15 minutes each

The blueprints are **ready to import and configure** - they won't have module errors, but they need your specific connections, field mappings, and manual module setup to run.

---

## 📋 Quick Reference: Module Replacements Required

| Scenario | Replace This | With This | Notes |
|----------|--------------|-----------|-------|
| **4A-A** | Twilio Module (shows "Not Found") | Twilio "Create a Message" (manual) | SMS path only |
| **4A-B** | Twilio Module (shows "Not Found") | Twilio "Create a Message" (manual) | SMS path only |
| **4A-C** | Twilio Module (shows "Not Found") | Twilio "Create a Message" (manual) | SMS path only |
| **4A-D** | Twilio Module (shows "Not Found") | Twilio "Create a Message" (manual) | SMS path only |
| **4A-D** | (Create separate scenario) | Schedule automation | For stage advancement |
| **4A-E** | Twilio Module (shows "Not Found") | Twilio "Create a Message" (manual) | SMS path only |
| **4A-F** | Webhook (Module 1) | Schedule module | For automated reports |

---

**Last Updated**: 2025-01-XX  
**Package**: Package 4A - Lead Reactivation Suite

