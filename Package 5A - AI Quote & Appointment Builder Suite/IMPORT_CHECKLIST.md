# ✅ Import Checklist - Package 5A

## 🟢 What WILL Work Automatically

1. ✅ **All Module Names** - All modules use verified working identifiers
2. ✅ **Module Structure** - All flows are properly structured
3. ✅ **JSON Parsing References** - All JSON parse modules reference correct OpenAI module IDs
4. ✅ **Basic Connections** - Connection placeholders are set (you'll need to select your actual connections)

## 🟡 What NEEDS Configuration After Import

### 1. **Form/Webhook Triggers** (CRITICAL - All Scenarios)
- **Status**: All scenarios use `gateway:CustomWebHook` as placeholders
- **Action Required**:
  1. **Option A**: Keep webhook and configure your form to send data to the webhook URL
  2. **Option B**: Delete webhook module and add native form trigger:
     - Google Forms trigger (if using Google Forms)
     - Typeform trigger (if using Typeform)
     - Other form platform triggers
  3. Map form fields to webhook/trigger output
  4. Test with actual form submission

### 2. **Airtable Connection & Field Mapping** (All Scenarios)
- **Base ID**: `appo7Y0cbtd1wa8Ph` - Replace with YOUR Airtable base ID
- **Table ID**: `tblmVnZaaWToTXxaR` - Replace with YOUR table ID
- **Field IDs**: Field IDs are specific to YOUR Airtable base
  - Make.com will try to auto-map these, but **verify the field mappings are correct**
  - If fields don't match, manually map them in each Airtable module

### 3. **OpenAI Connection** (All Scenarios)
- Connection placeholder is set, but you need to:
  - Select or create your OpenAI connection
  - Verify API key is valid
  - Verify model selection (should default to gpt-4o)
  - Verify response format is set to JSON Object

### 4. **Google Docs Modules** (CRITICAL - Most Scenarios)
- **Status**: Google Docs modules are NOT importable via JSON - they appear as webhooks
- **Action Required**:
  1. Delete the webhook module (placeholder for Google Docs) after import
  2. Add Google Docs "Create Document" module manually in Make.com UI
  3. Configure Google Docs connection
  4. Set document template ID (see `QUOTE_TEMPLATE_SETUP.md` for template creation)
  5. Map quote data to document fields
  6. Configure document title and content mapping
  7. Test document creation

### 5. **Gmail/Google Email Connection** (All Scenarios)
- Connection placeholder is set, but you need to:
  - Select or create your Gmail connection
  - Authorize access to your Gmail account
  - Configure "To" email addresses (will use form/webhook data)
  - Customize email subject and body templates

### 6. **Google Calendar** (Scenario 5A-C Only)
- **Status**: Requires manual setup after import
- **Action Required**:
  1. Delete webhook placeholder for calendar operations
  2. Add Google Calendar "List Events" module manually (for availability checking)
  3. Add Google Calendar "Create Event" module manually (for booking)
  4. Configure Google Calendar connection
  5. Map booking time data to calendar event fields
  6. Test calendar event creation

### 7. **Schedule Module** (Scenario 5A-F Only)
- **Status**: Uses webhook as placeholder
- **Action Required**:
  1. Delete webhook module
  2. Add Schedule module manually
  3. Configure daily or weekly schedule
  4. Connect to Module 2 (Airtable Search)

### 8. **Field Name Mappings** (All Scenarios)
Some field references use exact field names from webhook/form data:
- Verify webhook/form output fields match what scenarios expect:
  - `name`, `email`, `phone`, `company`
  - `service_type`, `requirements`, `budget_range`
  - `location`, `urgency` (for Scenario 5A-B)
  - `additional_details`, `answers` (for Scenario 5A-D)
- Common Airtable fields needed:
  - `Contact Full Name`
  - `Contact Email`
  - `Contact Phone`
  - `Company`
  - `Status`
  - `Notes`

---

## 📝 Step-by-Step After Import

### For Each Scenario:

1. **Import the Blueprint** ✅ (Will work)

2. **Replace Webhook with Form Trigger** (CRITICAL)
   - **Option A**: Keep webhook and configure form to send to webhook URL
   - **Option B**: Delete webhook module
   - Add appropriate form trigger (Google Forms, Typeform, etc.)
   - Configure connection and map form fields
   - Connect to next module in flow

3. **Configure Airtable Connection**
   - Click on any Airtable module
   - Select/create your Airtable connection
   - Update Base ID if different
   - Update Table ID if different
   - **Verify field mappings** match your schema

4. **Configure OpenAI Connection**
   - Click on OpenAI module
   - Select/create your OpenAI connection
   - Verify model selection (should default to gpt-4o)
   - Verify API key is valid
   - Verify response format is "JSON Object"

5. **Configure Google Docs Connection** (Most Scenarios)
   - Delete webhook placeholder for Google Docs operations
   - Add Google Docs "Create Document" module manually
   - Create Google Docs connection (OAuth)
   - Set document template ID
   - Map quote data to document content
   - Test document creation
   - See `QUOTE_TEMPLATE_SETUP.md` for template setup

6. **Configure Gmail Connection**
   - Click on Gmail module
   - Select/create your Gmail connection
   - Authorize access
   - Configure recipient email (will use `{{1.email}}` from form)
   - Customize email subject and HTML body

7. **Add Manual Modules** (if needed)
   - **Scenario 5A-C**: Add Google Calendar "List Events" and "Create Event" modules
   - **Scenario 5A-F**: Add Schedule module
   - **Scenario 5A-B**: May need Google Sheets for advanced pricing (optional)

8. **Verify All Field Mappings**
   - Check each module for red error indicators
   - Verify dropdown fields show correct options
   - Test with sample data from form/webhook

9. **Run Test Execution**
   - Click "Run once" to test
   - Submit test form data or send webhook request
   - Check for errors
   - Verify:
     - Quote is generated correctly
     - Google Doc is created (if applicable)
     - Email is sent successfully
     - Airtable record is created/updated

---

## ⚠️ Common Issues & Solutions

### Issue: "Google Docs module not found"
**Solution**: 
- Google Docs modules cannot be imported via JSON
- Delete webhook placeholder
- Add Google Docs "Create Document" module manually
- See `QUOTE_TEMPLATE_SETUP.md` for setup

### Issue: "Quote template not found"
**Solution**:
- Create quote template in Google Docs first
- Copy template document ID
- Set template ID in Google Docs module
- See `QUOTE_TEMPLATE_SETUP.md` for details

### Issue: "JSON Parse error"
**Solution**: 
- Check OpenAI module ID matches JSON parse reference
- Verify OpenAI response format is set to "JSON Object"
- See `QUICK_REFERENCE_JSON_PARSING.md` for correct references

### Issue: "Airtable field errors"
**Solution**: 
- Verify field names match your Airtable schema exactly
- Check field types (text, number, date, etc.)
- Use Airtable's field picker in Make.com to select correct fields

### Issue: "Email not sending"
**Solution**:
- Verify Gmail connection is authorized
- Check "To" email address is correct
- Verify email content doesn't contain invalid HTML
- Test with simple text first

### Issue: "Form data not mapping correctly"
**Solution**:
- Verify form field names match webhook expected fields
- Check webhook output structure in Make.com
- Use Make.com's data mapper to properly map fields
- Test webhook with Postman or similar tool

---

## 🔧 Pre-Import Setup Checklist

Before importing, ensure you have:

- [ ] Make.com account with appropriate plan
- [ ] Airtable account with base created
- [ ] OpenAI API key
- [ ] Gmail/Google Workspace account
- [ ] Google Docs account (for quote templates)
- [ ] Form system configured (Google Forms, Typeform, or webhook-capable)
- [ ] Quote template created in Google Docs (see `QUOTE_TEMPLATE_SETUP.md`)
- [ ] Google Calendar access (for Scenario 5A-C)

---

## 📚 Additional Resources

- **Template Setup**: See `QUOTE_TEMPLATE_SETUP.md` for Google Docs template creation
- **JSON Parsing**: See `QUICK_REFERENCE_JSON_PARSING.md` for parsing patterns
- **Module Reference**: See `VERIFIED_MAKE_COM_MODULES.md` for module details
- **Setup Instructions**: See `SETUP_INSTRUCTIONS_COMPLETE.md` for detailed setup

---

**Last Updated**: 2025-01-XX  
**Package**: Package 5A - AI Quote & Appointment Builder Suite

