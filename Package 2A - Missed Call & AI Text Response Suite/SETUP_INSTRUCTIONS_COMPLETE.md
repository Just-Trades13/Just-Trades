# Complete Make.com Setup Instructions for Package 2A (All Scenarios)

## 📋 IMPORTANT: JSON Parsing Pattern

**The JSON parsing reference varies by scenario based on the OpenAI module ID:**

- **Scenario 2A-A**: No OpenAI module (direct SMS response)
- **Scenario 2A-B**: OpenAI module ID = 4, so use: `{{4.text.output[0].content[0].text}}`
- **Scenario 2A-C**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`
- **Scenario 2A-D**: OpenAI module ID = 6, so use: `{{6.text.output[0].content[0].text}}`
- **Scenario 2A-E**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`
- **Scenario 2A-F**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`

**The pattern is: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`**

---

## 🔧 Prerequisites

Before importing any scenario, ensure you have:

1. **Make.com Account** with appropriate plan
2. **Airtable Connection** configured (Base ID: `appo7Y0cbtd1wa8Ph`, Table ID: `tblmVnZaaWToTXxaR`)
3. **OpenAI Connection** configured with API key
4. **Twilio Connection** configured with phone number (for SMS)
5. **Gmail/Google Email Connection** (for notifications - Scenarios E, F)

---

## ⚠️ CRITICAL: Twilio Webhook Setup

**All scenarios use `gateway:CustomWebHook` as placeholders. You MUST replace these with native Twilio triggers after import:**

1. **After importing**, delete the webhook module
2. **Add Twilio trigger** manually:
   - For **Scenario 2A-A, 2A-D**: Add "Status Callback" webhook or "Call Events" trigger
   - For **Scenarios 2A-B, 2A-C, 2A-E**: Add "Incoming SMS" trigger
3. **Configure Twilio webhook URL** in Twilio dashboard to point to your Make.com scenario
4. **Test** by sending a test SMS or making a test call

---

# 📘 SCENARIO 2A-A - Missed Call Text-Back

## What This Scenario Does
Detects missed calls via Twilio webhook, sends instant SMS response, and logs to Airtable.

## Import Steps

1. **Import the Blueprint**
   - Go to Make.com → Scenarios → Create a new scenario
   - Click "Import" → Upload `Scenario 2A-A - Missed Call Text-Back.blueprint.json`
   - Click "Import" button

2. **Replace Webhook with Twilio Trigger** (CRITICAL)
   - **Delete Module 1** (Webhook)
   - Click "+" → Search "Twilio"
   - Add **"Status Callback"** or **"Watch Calls"** trigger
   - **Connection**: Your Twilio connection
   - **Phone Number**: Your Twilio phone number
   - Connect this to Module 2 (Router)

3. **Configure Module 2: Router (Check Call Status)**
   - **Route**: If/Else
   - **Filter**: `{{1.CallStatus}} = "no-answer" OR {{1.CallStatus}} = "busy" OR {{1.CallStatus}} = "failed"`
   - Click "OK"

4. **Add Twilio Create Message Module** (CRITICAL - Module shows as "Not Found")
   - **Delete** the "Module Not Found" Twilio module (Module 3)
   - Click "+" → Search "Twilio"
   - Add **"Create a Message"** module
   - **Connection**: Create/select your Twilio connection
   - **To**: `{{1.From}}` (caller's phone number)
   - **From**: Your Twilio phone number (e.g., `+1234567890`)
   - **Body**: "Hi! Sorry we missed your call. How can we help you today? Reply to this message and we'll get back to you right away. Reply STOP to opt out."
   - Connect this module to Module 4 (Airtable Search)
   - Click "OK"

5. **Configure Module 4: Airtable Search Records**
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Formula**: `{Contact Phone} = '{{1.From}}'`
   - **Max Records**: 1
   - Click "OK"

6. **Configure Module 5: Router (Check if Record Exists)**
   - **Route**: If/Else
   - **Filter**: `{{4.id[0]}} is empty`
   - Click "OK"

7. **Configure Module 6: Airtable Create Record** (If path - new contact)
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - Map fields:
     - **Contact Phone**: `{{1.From}}`
     - **Status**: `missed_call_texted`
     - **Last Out Reach**: `{{now}}`
     - **Notes**: `Missed call detected at {{now}}. Text-back message sent via Scenario 2A-A.`
   - Click "OK"

8. **Configure Module 7: Airtable Update Record** (Else path - existing contact)
   - **Connection**: Your Airtable connection
   - **Record ID**: `{{4.id[0]}}`
   - Map fields:
     - **Status**: `missed_call_texted`
     - **Last Out Reach**: `{{now}}`
     - **Notes**: `Missed call detected at {{now}}. Text-back message sent via Scenario 2A-A.`
   - Click "OK"

9. **Test the Scenario**
   - Call your Twilio number and let it ring without answering
   - Verify SMS is sent to caller
   - Check Airtable for updated record

---

# 📗 SCENARIO 2A-B - AI Text Response Bot

## What This Scenario Does
Receives incoming SMS, processes with AI, generates intelligent response, sends SMS reply, and logs to CRM.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 2A-B - AI Text Response Bot.blueprint.json`

2. **Replace Webhook with Twilio Incoming SMS Trigger** (CRITICAL)
   - **Delete Module 1** (Webhook)
   - Click "+" → Search "Twilio"
   - Add **"Watch Incoming SMS"** or **"Incoming SMS"** trigger
   - **Connection**: Your Twilio connection
   - **Phone Number**: Your Twilio phone number
   - Connect this to Module 2 (Router)

3. **Configure Module 2: Router (Check for Opt-Out)**
   - **Route**: If/Else
   - **Filter**: `UPPER({{1.Body}}) CONTAINS "STOP" OR UPPER({{1.Body}}) CONTAINS "UNSUBSCRIBE" OR UPPER({{1.Body}}) CONTAINS "CANCEL"`
   - Click "OK"

4. **Configure Module 3: Airtable Search Records** (If path - not opt-out)
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Formula**: `{Contact Phone} = '{{1.From}}'`
   - **Max Records**: 1
   - Click "OK"

5. **Configure Module 4: OpenAI Create Model Response**
   - **Connection**: Your OpenAI connection
   - **Input**: Verify prompt contains customer message `{{1.Body}}` and phone `{{1.From}}`
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **Temperature**: 0.7
   - **Max Tokens**: 200
   - Click "OK"

6. **Configure Module 5: Parse JSON**
   - **JSON**: Enter `{{4.text.output[0].content[0].text}}` (OpenAI module ID is 4)
   - **Data structure**: `response`, `intent`, `needs_followup`, `booking_requested`
   - Click "OK"

7. **Configure Module 6: Twilio Create Message**
   - **Connection**: Your Twilio connection
   - **To**: `{{1.From}}`
   - **From**: `{{1.To}}` or your Twilio number
   - **Body**: `{{5.response}}`
   - Click "OK"

8. **Configure Module 7: Router (New vs Existing Contact)**
   - **Route**: If/Else
   - **Filter**: `{{3.id[0]}} is empty`
   - Click "OK"

9. **Configure Module 8: Airtable Create Record** (New contact)
   - **Connection**: Your Airtable connection
   - Map fields:
     - **Contact Phone**: `{{1.From}}`
     - **Status**: `{{5.intent}}`
     - **Last Out Reach**: `{{now}}`
     - **Notes**: SMS conversation log
   - Click "OK"

10. **Configure Module 9: Airtable Update Record** (Existing contact)
    - **Connection**: Your Airtable connection
    - **Record ID**: `{{3.id[0]}}`
    - Map fields:
      - **Status**: `{{5.intent}}`
      - **Last Out Reach**: `{{now}}`
      - **Notes**: Append SMS conversation
    - Click "OK"

11. **Configure Opt-Out Path** (Module 10, 11 - Else path from Module 2)
    - **Module 10**: Send opt-out confirmation SMS
    - **Module 11**: Update Airtable with `Do Not Contact = 1`

12. **Test the Scenario**
    - Send test SMS to your Twilio number
    - Verify AI response is generated and sent
    - Check Airtable for conversation log

---

# 📙 SCENARIO 2A-C - AI Text Bot with Booking

## What This Scenario Does
AI-powered SMS bot that detects booking intent, offers available times, confirms bookings, and integrates with calendar.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 2A-C - AI Text Bot with Booking.blueprint.json`

2. **Replace Webhook with Twilio Incoming SMS Trigger**
   - Delete webhook, add Twilio "Incoming SMS" trigger

3. **Configure Module 2: Airtable Search Records**
   - Search for existing contact by phone number

4. **Configure Module 3: OpenAI Create Model Response**
   - **Input**: Verify prompt includes available time slots
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **JSON Structure**: Should return `response`, `intent`, `booking_status`, `selected_time`, `needs_calendar_update`
   - Click "OK"

5. **Configure Module 4: Parse JSON**
   - **JSON**: `{{3.text.output[0].content[0].text}}` (OpenAI module ID is 3)
   - Click "OK"

6. **Configure Module 5: Twilio Create Message**
   - **Body**: `{{4.response}}`
   - Click "OK"

7. **Configure Module 6: Router (Check if Booking Confirmed)**
   - **Filter**: `{{4.needs_calendar_update}} = true`
   - Click "OK"

8. **Configure Module 7: Calendar Event** (Manual Setup Required)
   - **IMPORTANT**: Add Google Calendar "Create Event" module manually
   - **Connection**: Google Calendar connection
   - **Calendar**: Select your calendar
   - **Summary**: `Customer Appointment`
   - **Start**: Parse `{{4.selected_time}}` and format for calendar
   - **End**: Same as start + 1 hour
   - **Description**: `Appointment booked via SMS from {{1.From}}`

9. **Configure CRM Updates** (Modules 8, 9, 10)
   - Update Airtable with booking confirmation
   - Log booking time and status

10. **Test the Scenario**
    - Send SMS requesting booking
    - Verify AI offers times
    - Confirm booking
    - Check calendar for event (after manual setup)

---

# 📕 SCENARIO 2A-D - Missed Call with AI Follow-up

## What This Scenario Does
Combines missed call detection with AI-powered SMS conversation for complete customer engagement.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 2A-D - Missed Call with AI Follow-up.blueprint.json`

2. **Setup Two Webhooks/Triggers**:
   - **Module 1**: Replace with Twilio "Status Callback" or "Call Events" (missed calls)
   - **Module 4**: Replace with Twilio "Incoming SMS" trigger (replies)

3. **Configure Missed Call Flow** (Modules 1-3)
   - **Module 1**: Twilio missed call trigger
   - **Module 2**: Router checking call status
   - **Module 3**: Send immediate SMS text-back

4. **Configure AI Response Flow** (Modules 4-11)
   - **Module 4**: Twilio incoming SMS trigger
   - **Module 5**: Search Airtable for contact
   - **Module 6**: OpenAI with missed call context
   - **JSON Parse**: `{{6.text.output[0].content[0].text}}` (OpenAI module ID is 6)
   - **Module 8**: Send AI response via Twilio
   - **Modules 9-11**: Update CRM

5. **Test Both Flows**
   - Miss a call → Verify instant SMS sent
   - Reply to SMS → Verify AI response

---

# 📓 SCENARIO 2A-E - AI Text Bot with Knowledge Base

## What This Scenario Does
Enterprise AI SMS bot with FAQ knowledge base, lead scoring, and automatic high-priority lead alerts.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 2A-E - AI Text Bot with Knowledge Base.blueprint.json`

2. **Replace Webhook with Twilio Incoming SMS Trigger**
   - Delete webhook, add Twilio "Incoming SMS" trigger

3. **Configure Module 3: OpenAI Create Model Response**
   - **Input**: Verify knowledge base content (services, pricing, FAQs)
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **JSON Structure**: `response`, `intent`, `lead_score`, `qualified`, `booking_requested`, `needs_human`
   - Click "OK"

4. **Configure Module 4: Parse JSON**
   - **JSON**: `{{3.text.output[0].content[0].text}}` (OpenAI module ID is 3)
   - Click "OK"

5. **Configure Module 6: Router (High Priority Check)**
   - **Filter**: `{{4.needs_human}} = true OR {{4.lead_score}} >= 70`
   - Click "OK"

6. **Configure Module 7: Email Alert** (High priority path)
   - **To**: Your team email address
   - **Subject**: `High Priority Lead - SMS Conversation`
   - **Content**: HTML with lead details
   - Click "OK"

7. **Configure CRM Updates** (Modules 8-10)
   - Create/update Airtable with lead score and qualification status
   - Log full conversation

8. **Customize Knowledge Base**
   - Edit Module 3 input to update:
     - Services offered
     - Pricing tiers
     - Common FAQs
     - Industry-specific information

9. **Test the Scenario**
    - Send test SMS with pricing question
    - Verify AI responds with knowledge base info
    - Test high-priority trigger (lead score >= 70)
    - Verify email alert sent

---

# 📔 SCENARIO 2A-F - Analytics & Reporting

## What This Scenario Does
Aggregates call and SMS data, generates analytics reports, and sends summaries via email.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 2A-F - Analytics & Reporting.blueprint.json`

2. **Replace Webhook with Schedule Module** (CRITICAL)
   - **Delete Module 1** (Webhook)
   - Click "+" → Add **"Schedule"** module
   - **Schedule**: Daily at 9 AM or Weekly on Monday
   - Connect to Module 2

3. **Configure Module 2: Airtable Search Records**
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Formula**: `{Status} != ""`
   - **Max Records**: 1000 (adjust as needed)
   - Click "OK"

4. **Configure Module 3: OpenAI Create Model Response**
   - **Input**: Analytics prompt with record data
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **JSON Structure**: `total_leads`, `by_status`, `by_intent`, `recent_activity`, `conversion_rate`, `summary`
   - Click "OK"

5. **Configure Module 4: Parse JSON**
   - **JSON**: `{{3.text.output[0].content[0].text}}` (OpenAI module ID is 3)
   - Click "OK"

6. **Configure Module 5: Airtable Create Record** (Optional - Save report)
   - Save analytics summary to Airtable Notes field

7. **Configure Module 6: Email Report**
   - **To**: Your team email or dashboard email
   - **Subject**: `Weekly Analytics Report - {{now}}`
   - **Content**: HTML formatted with all metrics
   - Click "OK"

8. **Test the Scenario**
    - Run scenario once manually
    - Verify analytics calculated correctly
    - Check email report received

---

## 🔧 Common Configuration Issues

### Twilio Webhook Not Triggering
- Verify webhook URL in Twilio dashboard points to Make.com scenario
- Check Twilio phone number configuration
- Test webhook manually using Postman or curl

### OpenAI JSON Parse Error
- Verify OpenAI module executed successfully
- Check JSON format matches expected structure
- Verify module ID in JSON parse reference

### Airtable Field Mapping Errors
- Verify field names match your Airtable schema exactly
- Check for typos in field IDs
- Manually map fields if auto-mapping fails

---

## ✅ Success Checklist

After configuration, verify:
- ✅ All connections configured and tested
- ✅ Twilio triggers working (test with actual SMS/call)
- ✅ OpenAI generating valid JSON responses
- ✅ JSON parsing successful
- ✅ SMS messages sending correctly
- ✅ Airtable records updating
- ✅ Email notifications working (if applicable)

---

**Last Updated**: 2025-01-XX  
**Package**: Package 2A - Missed Call & AI Text Response Suite

