# Complete Make.com Setup Instructions for Package 3A (All Scenarios)

## 📋 IMPORTANT: JSON Parsing Pattern

**The JSON parsing reference varies by scenario based on the OpenAI module ID:**

- **Scenario 3A-A**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`
- **Scenario 3A-B**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`
- **Scenario 3A-C**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`
- **Scenario 3A-D**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`
- **Scenario 3A-E**: OpenAI module ID = 4, so use: `{{4.text.output[0].content[0].text}}`
- **Scenario 3A-F**: OpenAI module ID = 2, so use: `{{2.text.output[0].content[0].text}}`

**The pattern is: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`**

---

## 🔧 Prerequisites

Before importing any scenario, ensure you have:

1. **Make.com Account** with appropriate plan
2. **Airtable Connection** configured (Base ID: `appo7Y0cbtd1wa8Ph`, Table ID: `tblmVnZaaWToTXxaR`)
3. **OpenAI Connection** configured with API key
4. **Twilio Account** with Voice-enabled phone number
5. **Gmail/Google Email Connection** (for notifications - Scenarios D, E, F)
6. **Optional**: ElevenLabs or Play.ht API key for advanced TTS

---

## ⚠️ CRITICAL: Twilio Voice Setup (Required for All Scenarios)

**Voice calls require Twilio Studio Flow setup BEFORE importing scenarios:**

### Step 1: Create Twilio Studio Flow

1. **Go to Twilio Console** → Studio → Flows
2. **Create New Flow** → "AI Voice Receptionist"
3. **Add Widgets**:
   - **Trigger**: "Incoming Call"
   - **Gather Input**: Collect caller speech
   - **Set Transcription**: Enable transcription webhook
   - **Connect Call**: Optional - for human handoff

### Step 2: Configure Transcription Webhook

1. **In Studio Flow**, set transcription callback URL
2. **URL will be** your Make.com webhook URL (get this after importing scenario)
3. **Method**: POST
4. **Parameters**: TranscriptionText, CallSid, From, To, TranscriptionUrl

**See TWILIO_VOICE_SETUP.md for detailed Studio Flow setup**

### Step 3: Configure TTS (Text-to-Speech)

**Option A: Twilio Built-in TTS** (Easiest)
- Use `<Say>` widget in Studio Flow
- Pass AI response text as variable

**Option B: ElevenLabs/Play.ht** (Better Quality)
- Requires HTTP module in Make.com (add manually after import)
- Generate audio file via API
- Pass audio URL to Twilio

**See TWILIO_VOICE_SETUP.md for TTS setup details**

---

## 📘 SCENARIO 3A-A - Basic Voice Receptionist

## What This Scenario Does
Receives call transcription via webhook, processes with AI, generates response, and logs to CRM.

## Import Steps

1. **Import the Blueprint**
   - Go to Make.com → Scenarios → Create a new scenario
   - Click "Import" → Upload `Scenario 3A-A - Basic Voice Receptionist.blueprint.json`
   - Click "Import" button

2. **Configure Module 1: Webhook (Transcription Callback)**
   - **Keep the webhook module** (this receives transcription from Twilio)
   - Click on Module 1
   - **Copy the webhook URL** - you'll use this in Twilio Studio Flow
   - Click "OK"

3. **Configure Module 2: Airtable Search Records**
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Formula**: `{Contact Phone} = '{{1.From}}'`
   - **Max Records**: 1
   - Click "OK"

4. **Configure Module 3: OpenAI Create Model Response**
   - **Connection**: Your OpenAI connection
   - **Input**: Verify prompt contains transcription `{{1.TranscriptionText}}` and caller info
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **Temperature**: 0.7
   - **Max Tokens**: 300
   - Click "OK"

5. **Configure Module 4: Parse JSON**
   - **JSON**: Enter `{{3.text.output[0].content[0].text}}` (OpenAI module ID is 3)
   - **Data structure**: `response`, `intent`, `needs_followup`, `booking_requested`, `should_transfer`
   - Click "OK"

6. **Configure Module 5: Router (New vs Existing Contact)**
   - **Route**: If/Else
   - **Filter**: `{{2.id[0]}} is empty`
   - Click "OK"

7. **Configure Module 6: Airtable Create Record** (If path - new contact)
   - **Connection**: Your Airtable connection
   - Map fields:
     - **Contact Phone**: `{{1.From}}`
     - **Status**: `{{4.intent}}`
     - **Last Out Reach**: `{{now}}`
     - **Notes**: Voice call log with transcription and AI response
   - Click "OK"

8. **Configure Module 7: Airtable Update Record** (Else path - existing contact)
   - **Connection**: Your Airtable connection
   - **Record ID**: `{{2.id[0]}}`
   - Map fields:
     - **Status**: `{{4.intent}}`
     - **Last Out Reach**: `{{now}}`
     - **Notes**: Append voice call log
   - Click "OK"

9. **Set Up TTS Integration** (Manual - Required)
   - Add HTTP module after Module 4 (JSON Parse)
   - Configure ElevenLabs or Play.ht API call
   - OR configure Twilio Studio Flow to use `<Say>` widget with `{{4.response}}`
   - See TWILIO_VOICE_SETUP.md for details

10. **Configure Twilio Studio Flow**
    - Set transcription webhook URL to Module 1 webhook URL
    - Configure TTS to play AI response
    - Test with actual phone call

11. **Test the Scenario**
    - Make test call to Twilio number
    - Verify transcription received in Make.com
    - Check AI response generated correctly
    - Verify Airtable updated with call data
    - Test voice response plays back to caller

---

## 📗 SCENARIO 3A-B - Voice Receptionist with Booking

## What This Scenario Does
Handles voice calls, processes with AI, detects booking requests, collects booking details, creates calendar event, sends SMS confirmation.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 3A-B - Voice Receptionist with Booking.blueprint.json`

2. **Configure Modules 1-4** (Same as Scenario 3A-A)

3. **Configure Module 5: Router (Check Booking Confirmed)**
   - **Route**: If/Else
   - **Filter**: `{{4.booking_confirmed}} = true`
   - Click "OK"

4. **Configure Module 6: Router (New vs Existing Contact)**
   - **Route**: If/Else
   - **Filter**: `{{2.id[0]}} is empty`
   - Click "OK"

5. **Configure Module 7: Airtable Create Record** (Booking - New contact)
   - Map booking details from `{{4.booking_details}}`:
     - **Contact Full Name**: `{{4.booking_details.name}}`
     - **Status**: `booking_confirmed`
     - **Next Step**: `Appointment booked: {{4.booking_details.confirmed_slot}}`
   - Click "OK"

6. **Configure Module 8: Airtable Update Record** (Booking - Existing contact)
   - Similar to Module 7 but updates existing record
   - Click "OK"

7. **Add Google Calendar Module** (Manual - Required)
   - After Module 8, add **Google Calendar "Create Event"** module
   - **Connection**: Your Google Calendar connection
   - **Calendar**: Select calendar
   - **Title**: Appointment with {{4.booking_details.name}}
   - **Start Date/Time**: Parse from `{{4.booking_details.confirmed_slot}}`
   - **End Date/Time**: Add 30-60 minutes
   - **Description**: `Reason: {{4.booking_details.reason}}`
   - Click "OK"

8. **Configure Module 9: Twilio Create Message** (SMS Confirmation)
   - **Connection**: Your Twilio connection (add manually if shows "Not Found")
   - **To**: `{{1.From}}`
   - **From**: Your Twilio phone number
   - **Body**: Booking confirmation message with time slot
   - Click "OK"

9. **Configure Modules 10-11** (Non-booking path - same as 3A-A)

10. **Set Up TTS Integration** (Same as 3A-A)

11. **Test the Scenario**
    - Make test call requesting appointment
    - Verify AI collects booking details
    - Check calendar event created
    - Verify SMS confirmation sent

---

## 📘 SCENARIO 3A-C - Voice Receptionist with Call Routing

## What This Scenario Does
Handles voice calls, processes with AI, qualifies caller needs, routes to appropriate department/agent.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 3A-C - Voice Receptionist with Call Routing.blueprint.json`

2. **Configure Modules 1-4** (Same as Scenario 3A-A)

3. **Configure Module 5: Router (Check Should Transfer)**
   - **Route**: Switch
   - **Filter**: `{{4.should_transfer}} = true`
   - Click "OK"

4. **Configure Module 6: Router (Route by Department)**
   - **Route**: Switch
   - **Filter**: `{{4.transfer_department}}`
   - **Routes**: Sales, Support, Billing, Technical
   - Click "OK"

5. **Configure Transfer Logic**
   - Each route should update Airtable with routing decision
   - Update Studio Flow to transfer call to appropriate number
   - Transfer number comes from `{{4.transfer_number}}`

6. **Configure Modules 7-10** (CRM logging - similar to 3A-A)

7. **Set Up Twilio Call Transfer**
   - In Studio Flow, configure `<Dial>` widget
   - Use `{{4.transfer_number}}` from Make.com
   - Or use static numbers per department

8. **Test the Scenario**
    - Make test calls with different needs
    - Verify AI routes correctly
    - Check call transferred to right department

---

## 📗 SCENARIO 3A-D - Advanced Voice Receptionist

## What This Scenario Does
Enterprise voice assistant with knowledge base, multi-turn conversations, lead scoring, advanced booking/routing, follow-up automation.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 3A-D - Advanced Voice Receptionist.blueprint.json`

2. **Configure Modules 1-4** (Similar to 3A-A, but with enhanced prompt)

3. **Configure Enhanced AI Prompt** (Module 3)
   - Verify prompt includes knowledge base information
   - Includes lead scoring logic
   - Multi-turn conversation handling
   - Advanced booking and routing

4. **Configure Module 5: Router (Booking Confirmed)**
   - Handles confirmed bookings
   - Updates Airtable with lead score and qualifiers

5. **Configure Module 6: Router (Should Transfer)**
   - Handles call routing
   - Updates with lead score

6. **Configure Modules 7-10** (CRM updates with enhanced data)

7. **Configure Module 12-13** (Follow-up automation)
   - Router checks if follow-up needed
   - Sends email if method is "email"

8. **Test the Scenario**
    - Test knowledge base queries
    - Verify lead scoring works
    - Check multi-turn conversations
    - Test booking and routing

---

## 📘 SCENARIO 3A-E - Voice Receptionist with Transcription

## What This Scenario Does
Receives full call transcription, summarizes with AI, extracts action items, logs to CRM, sends follow-up.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 3A-E - Voice Receptionist with Transcription.blueprint.json`

2. **Configure Module 1: Webhook (Call Completion)**
   - Receives call completion event from Twilio
   - Contains CallSid, duration, recording URL

3. **Configure Module 2: Webhook (Transcription Ready)**
   - Receives transcription webhook from Twilio
   - Contains TranscriptionText, TranscriptionUrl

4. **Configure Module 3: Airtable Search** (Find contact)

5. **Configure Module 4: OpenAI Create Model Response**
   - **Input**: Full call transcript for summarization
   - **Model**: `gpt-4o`
   - **Format**: JSON object with summary, action items, insights
   - Click "OK"

6. **Configure Module 5: Parse JSON**
   - **JSON**: `{{4.text.output[0].content[0].text}}` (OpenAI module ID is 4)
   - **Data structure**: Summary, key_points, action_items, call_quality_score, etc.

7. **Configure Modules 6-8** (CRM logging with full transcript)

8. **Configure Module 9: Router (Follow-up Check)**
   - Checks if follow-up required

9. **Configure Module 10: Email Follow-up** (If needed)
   - Sends summary email to caller

11. **Configure Module 11: SMS Follow-up**
    - Sends SMS with call summary

12. **Test the Scenario**
    - Make test call
    - Verify transcription received
    - Check AI summary generated
    - Verify CRM updated with full transcript
    - Test follow-up sent

---

## 📗 SCENARIO 3A-F - Voice Analytics & Reporting

## What This Scenario Does
Aggregates call data from Airtable, analyzes with AI, generates insights and recommendations, sends email report.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 3A-F - Voice Analytics & Reporting.blueprint.json`

2. **Configure Module 1: Airtable Watch Records**
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Label Field**: `Last Modified Time`
   - **Trigger Field**: `Last Modified Time`
   - **Formula**: `AND(ISNOTBLANK({Notes}), CONTAINS({Notes}, "VOICE CALL") OR CONTAINS({Notes}, "CallSid"))`
   - **Limit**: 100
   - Click "OK"

   **OR Replace with Schedule Module**:
   - Delete Airtable trigger
   - Add Schedule module
   - Configure daily or weekly schedule

3. **Configure Module 2: OpenAI Create Model Response**
   - **Input**: Call data from Airtable for analysis
   - **Model**: `gpt-4o`
   - **Format**: JSON object with analytics
   - Click "OK"

4. **Configure Module 3: Parse JSON**
   - **JSON**: `{{2.text.output[0].content[0].text}}` (OpenAI module ID is 2)
   - **Data structure**: Analytics JSON structure

5. **Configure Module 4: Email Report**
   - **Connection**: Your Gmail connection
   - **To**: Your email address
   - **Subject**: Voice Call Analytics Report - {{now}}
   - **Body**: HTML formatted report from parsed JSON
   - Click "OK"

6. **Test the Scenario**
    - Run once manually
    - Verify analytics generated
    - Check email report received

---

## 🔧 General Configuration Notes

### TTS Integration (All Scenarios)

**Option 1: Twilio Built-in TTS** (Recommended for beginners)
1. In Twilio Studio Flow, add `<Say>` widget
2. Use variable from Make.com: `{{MakeWebhook.response}}`
3. Configure voice: "alice", "polly", etc.

**Option 2: ElevenLabs API** (Better quality)
1. After Module 4 (JSON Parse), add HTTP module
2. **Method**: POST
3. **URL**: `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`
4. **Headers**: `xi-api-key: YOUR_KEY`, `Content-Type: application/json`
5. **Body**: `{"text": "{{4.response}}", "model_id": "eleven_monolingual_v1"}`
6. Store audio URL and pass to Twilio Studio Flow

### Twilio Studio Flow Setup

1. **Create Flow** in Twilio Console
2. **Set Trigger**: Incoming Call
3. **Add Gather Widget**: Collect caller speech
4. **Set Transcription**: Enable with webhook URL = Make.com webhook
5. **Receive Webhook**: Call Make.com for AI processing
6. **Play Response**: Use TTS to speak AI response
7. **Loop**: Return to Gather for multi-turn conversation

See TWILIO_VOICE_SETUP.md for detailed Studio Flow configuration.

---

## ✅ Testing Checklist

For each scenario, verify:
- ✅ Scenario imports without errors
- ✅ All connections configured
- ✅ Twilio Studio Flow active
- ✅ Transcription webhook receives data
- ✅ OpenAI processes transcription correctly
- ✅ JSON parsing works
- ✅ TTS generates audio (or Twilio says response)
- ✅ Airtable logs data correctly
- ✅ Voice response plays to caller
- ✅ Call flow works end-to-end

---

## ⚠️ Common Issues

### Issue: Transcription not received
**Solution**: Check Twilio Studio Flow transcription webhook URL points to Make.com webhook

### Issue: High latency
**Solution**: Use Twilio built-in TTS, optimize OpenAI prompts, consider streaming

### Issue: TTS not working
**Solution**: Verify API keys, test TTS separately, check audio URL format

### Issue: Call not looping for conversation
**Solution**: Configure Studio Flow to loop back to Gather widget after response

---

**Last Updated**: 2025-01-XX  
**Package**: Package 3A - AI Voice Receptionist Suite  
**Note**: Voice integration requires Twilio Studio Flow - see TWILIO_VOICE_SETUP.md for detailed setup

