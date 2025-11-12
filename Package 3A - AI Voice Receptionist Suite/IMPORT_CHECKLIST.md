# ✅ Import Checklist - Package 3A

## 🟢 What WILL Work Automatically

1. ✅ **All Module Names** - All modules use verified working identifiers
2. ✅ **Module Structure** - All flows are properly structured
3. ✅ **JSON Parsing References** - All JSON parse modules reference correct OpenAI module IDs
4. ✅ **Basic Connections** - Connection placeholders are set (you'll need to select your actual connections)

## 🟡 What NEEDS Configuration After Import

### 1. **Twilio Voice Integration** (CRITICAL - All Scenarios)
- **Status**: All scenarios use `gateway:CustomWebHook` as placeholders for transcription webhooks
- **Action Required**:
  1. Set up **Twilio Studio Flow** (see TWILIO_VOICE_SETUP.md)
  2. Configure transcription webhook in Twilio to point to Make.com webhook URL
  3. Configure TTS (Text-to-Speech) integration (ElevenLabs, Play.ht, or Twilio built-in)
  4. Test with actual phone call

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

### 4. **TTS (Text-to-Speech) Integration** (CRITICAL - All Scenarios)
- **Status**: TTS modules are NOT included in blueprints - requires manual setup
- **Action Required**:
  1. Choose TTS service: ElevenLabs, Play.ht, or Twilio built-in TTS
  2. If using external TTS (ElevenLabs/Play.ht):
     - Add **HTTP - Make a Request** module after OpenAI response
     - Configure API endpoint and authentication
     - Generate audio URL
  3. If using Twilio built-in TTS:
     - Configure in Twilio Studio Flow using `<Say>` widget
     - Pass AI response text as variable
  4. Test TTS generation separately before full integration

### 5. **Gmail/Google Email Connection** (Scenarios 3A-D, 3A-E, 3A-F)
- Connection placeholder is set, but you need to:
  - Select or create your Gmail connection
  - Authorize access to your Gmail account
  - Configure "To" email addresses for notifications

### 6. **Google Calendar** (Scenario 3A-B Only)
- **Status**: Requires manual setup after import
- **Action Required**:
  1. Add Google Calendar "Create Event" module manually
  2. Configure Google Calendar connection
  3. Map booking time data to calendar event fields
  4. Test calendar event creation

### 7. **Twilio SMS Module** (Scenarios 3A-B, 3A-D, 3A-E)
- **Status**: Twilio SMS modules are NOT importable via JSON - they appear as "Module Not Found"
- **Action Required**:
  1. Delete the "Module Not Found" Twilio module after import
  2. Add Twilio "Create a Message" module manually in Make.com UI
  3. Configure Twilio connection (Account SID, Auth Token)
  4. Map fields:
     - **To**: Phone number field (e.g., `{{1.From}}`)
     - **From**: Your Twilio phone number
     - **Body**: Message text

### 8. **Schedule/Airtable Trigger** (Scenario 3A-F)
- **Status**: Uses Airtable trigger (can be replaced with Schedule module)
- **Action Required**:
  1. Keep Airtable trigger OR replace with Schedule module
  2. If using Schedule: Configure daily or weekly schedule
  3. Connect to Module 2 (OpenAI)

### 9. **Field Name Mappings** (All Scenarios)
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
  - `Pipeline Value`
  - `Do Not Contact`
  - `Last Out Reach`
  - `Notes`
  - `Next Step`
  - `Tags`

---

## 📝 Step-by-Step After Import

### For Each Scenario:

1. **Import the Blueprint** ✅ (Will work)

2. **Set Up Twilio Voice Integration** (CRITICAL)
   - Create Twilio Studio Flow (see TWILIO_VOICE_SETUP.md)
   - Configure transcription webhook to point to Make.com webhook URL
   - Test transcription webhook with actual call

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

5. **Set Up TTS Integration** (CRITICAL)
   - Choose TTS service
   - If external (ElevenLabs/Play.ht): Add HTTP module after OpenAI
   - If Twilio built-in: Configure in Studio Flow
   - Test TTS generation

6. **Configure Twilio SMS** (if applicable)
   - Delete "Module Not Found" Twilio module
   - Add Twilio "Create a Message" module manually
   - Configure connection and phone number

7. **Configure Gmail Connection** (if applicable)
   - Click on Gmail module
   - Select/create your Gmail connection
   - Authorize access
   - Configure recipient email addresses

8. **Add Manual Modules** (if needed)
   - **Scenario 3A-B**: Add Google Calendar "Create Event" module
   - **Scenario 3A-F**: Optionally add Schedule module

9. **Verify All Field Mappings**
   - Check each module for red error indicators
   - Verify dropdown fields show correct options
   - Test with sample data

10. **Test with Real Phone Call**
    - Make test call to Twilio number
    - Verify transcription received in Make.com
    - Check AI processing works correctly
    - Verify Airtable logs call data
    - Test TTS audio playback

---

## ⚠️ Common Issues & Solutions

### Issue: "Twilio transcription webhook not triggering"
**Solution**: 
- Verify Twilio Studio Flow is configured with transcription enabled
- Check webhook URL in Twilio dashboard points to Make.com scenario webhook
- Test webhook manually using Postman or curl
- Ensure Twilio phone number is configured correctly

### Issue: "TTS audio not generating"
**Solution**:
- Verify TTS API key is correct (ElevenLabs/Play.ht)
- Check HTTP module configuration (URL, headers, body)
- Test TTS API separately before integration
- Verify audio URL is returned correctly

### Issue: "Field not found" in Airtable
**Solution**: Field names or IDs don't match. Manually map the correct fields in Make.com.

### Issue: "Connection not configured"
**Solution**: Select or create the required connection for that service.

### Issue: JSON Parse error
**Solution**: 
- Verify OpenAI module executed successfully and returned JSON
- Check the JSON format matches expected structure
- Verify OpenAI module ID in JSON parse reference (see QUICK_REFERENCE_JSON_PARSING.md)

### Issue: Module shows red error
**Solution**: Click on the module and check what's required. Usually missing connection or field mapping.

### Issue: High latency in voice conversations
**Solution**: 
- Use Twilio built-in TTS for lower latency
- Optimize OpenAI prompts (shorter = faster)
- Consider streaming transcription if available
- Pre-generate common responses

### Issue: Call not being transcribed
**Solution**:
- Verify Twilio Studio Flow has transcription enabled
- Check transcription webhook URL is configured correctly
- Test transcription separately in Twilio Console

---

## ✅ Success Criteria

After configuration, you should see:
- ✅ No red error indicators on modules
- ✅ All connections show as "Connected"
- ✅ Field mappings show correct Airtable fields
- ✅ Twilio Studio Flow is active and handling calls
- ✅ Transcription webhooks are firing correctly
- ✅ TTS audio is generating successfully
- ✅ Test execution completes successfully
- ✅ Data appears correctly in Airtable after test call
- ✅ Voice responses play back correctly to caller

---

## 🎯 Bottom Line

**Will everything work right now?** 

**Almost!** The blueprints are technically correct and will import successfully, but you'll need to:

1. ✅ **Set up Twilio Studio Flow** (CRITICAL - see TWILIO_VOICE_SETUP.md)
2. ✅ Configure transcription webhooks to point to Make.com
3. ✅ Set up TTS integration (ElevenLabs/Play.ht or Twilio built-in)
4. ✅ Configure connections (Airtable, OpenAI, Twilio, Gmail)
5. ✅ Verify field mappings match your Airtable schema
6. ✅ Add manual modules (Calendar for 3A-B, SMS for applicable scenarios)
7. ✅ Update Airtable Base/Table IDs if different
8. ✅ Test each scenario with real phone calls

**Estimated setup time**: 
- **First scenario**: 60-90 minutes (includes Twilio Studio Flow setup)
- **Subsequent scenarios**: 30-45 minutes each
- **After familiar**: 20-30 minutes each

The blueprints are **ready to import and configure** - they won't have module errors, but they need:
- Your specific connections and field mappings
- Twilio Studio Flow setup (external to Make.com)
- Manual TTS integration
- Testing with real phone calls

---

## 📋 Quick Reference: Module Replacements Required

| Scenario | Replace This | With This |
|----------|--------------|-----------|
| **All** | Webhook (Module 1) | Twilio Transcription Webhook (configure in Twilio Studio Flow) |
| **3A-B, 3A-D, 3A-E** | Twilio Module (shows "Not Found") | Twilio "Create a Message" (manual) |
| **3A-B** | (Add manually) | Google Calendar "Create Event" |
| **All** | (Add manually) | TTS Integration (HTTP module or Twilio Studio Flow) |
| **3A-F** | Airtable Trigger | Schedule module (optional) |

---

**Last Updated**: 2025-01-XX  
**Package**: Package 3A - AI Voice Receptionist Suite  
**Note**: Voice integration is more complex than SMS - allow extra time for setup

