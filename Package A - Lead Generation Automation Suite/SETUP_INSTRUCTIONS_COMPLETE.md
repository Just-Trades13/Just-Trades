# Complete Make.com Setup Instructions for All Scenarios (A-F)

## 📋 IMPORTANT: JSON Parsing Pattern

**The JSON parsing reference varies by scenario based on the OpenAI module ID:**

- **Scenario A**: Uses `openai-gpt-3:CreateCompletion` (different format - uses `{{2.result}}`)
- **Scenario B**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`
- **Scenario C**: OpenAI module ID = 2, so use: `{{2.text.output[0].content[0].text}}`
- **Scenario D**: First OpenAI ID = 2 (`{{2.text.output[0].content[0].text}}`), Second OpenAI ID = 5 (`{{5.text.output[0].content[0].text}}`)
- **Scenario E**: OpenAI module ID = 2, so use: `{{2.text.output[0].content[0].text}}`
- **Scenario F**: OpenAI module ID = 2, so use: `{{2.text.output[0].content[0].text}}`

**The pattern is: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`**

---

## 🔧 Prerequisites

Before importing any scenario, ensure you have:

1. **Make.com Account** with appropriate plan
2. **Airtable Connection** configured (Base ID: `appo7Y0cbtd1wa8Ph`, Table ID: `tblmVnZaaWToTXxaR`)
3. **OpenAI Connection** configured with API key
4. **Google Email/Gmail Connection** configured
5. **Twilio Connection** (only for Scenario E)

---

# 📘 SCENARIO A - Lead Data Processing & Import

## What This Scenario Does
Receives webhook data, processes it with AI to extract/format lead information, searches for duplicates, and creates/updates Airtable records.

## Import Steps

1. **Import the Blueprint**
   - Go to Make.com → Scenarios → Create a new scenario
   - Click "Import" → Upload `scenario A.blueprint.json`
   - Click "Import" button

2. **Configure Module 1: Webhook**
   - Click on the **Webhook** module
   - If a webhook URL appears, copy it (you'll use this to send data)
   - If it says "Create webhook", click it to generate a new webhook URL
   - **Expected webhook fields:**
     - `company`, `contact_name`, `email`, `phone`, `linkedin`, `location`, `industry`, `role`, `employee_count`, `notes`

3. **Configure Module 2: OpenAI Chat Completion**
   - Click on the **OpenAI** module
   - Select your **OpenAI connection** (or create one if needed)
   - **Model**: Select "gpt-4o" from dropdown
   - **Select Method**: Choose "Create a Chat Completion (GPT and o1 models)"
   - **System Message**: This should already be filled, but verify it contains the data extraction instructions
   - **User Message**: Should be `{{1}}` (references webhook data)
   - **Response Format**: Set to "Text"
   - **Max Tokens**: 1000
   - **Temperature**: 1
   - Click "OK"

4. **Configure Module 3: Parse JSON**
   - Click on the **Parse JSON** module
   - **JSON**: Enter `{{2.result}}` (Note: Scenario A uses CreateCompletion which outputs to `result`, not `text.output`)
   - **Data structure**: Click "Add" → Choose "AI JSON" or create custom structure with fields:
     - `lead_id`, `source`, `acquired_at`, `company`, `domain`, `industry`, `employee_count`, `contact_full_name`, `contact_role`, `contact_email`, `contact_phone`, `contact_linkedin`, `location_city`, `location_state`, `status`, `utm_list_id`, `tags` (array), `notes`
   - Click "OK"

5. **Configure Module 4: Airtable Search Records**
   - Click on the **Airtable Search Records** module
   - Select your **Airtable connection** → Choose base "Leads Manager AI CRM"
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Formula**: `{Contact Email} = '{{3.contact_email}}'`
   - **Max Records**: 1
   - Click "OK"

6. **Configure Module 5: Router**
   - Click on the **Router** module
   - **Route**: Select "If/Else"
   - **Condition**: `{{4.id}}` is empty (if no record found)
   - Click "OK"

7. **Configure Module 6: Airtable Create Record** (If path)
   - Click on the **Airtable Create Record** module
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - Map all fields from `{{3.}}` (parsed JSON):
     - **Contact Full Name**: `{{3.contact_full_name}}`
     - **Company**: `{{3.company}}`
     - **Contact Email**: `{{3.contact_email}}`
     - **Contact Phone**: `{{3.contact_phone}}`
     - **Contact LinkedIn**: `{{3.contact_linkedin}}`
     - **Location City**: `{{3.location_city}}`
     - **Location State**: `{{3.location_state}}`
     - **Industry**: `{{3.industry}}`
     - **Employee Count**: `{{3.employee_count}}`
     - **Tags**: `{{3.tags}}`
     - **Status**: `{{3.status}}`
     - **Notes**: `{{3.notes}}`
     - Map all other required fields
   - Click "OK"

8. **Configure Module 7: Airtable Update Record** (Else path)
   - Click on the **Airtable Update Record** module
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Record ID**: `{{4.id[0]}}`
   - **Fields**: Update with new data from `{{3.}}`
   - Click "OK"

9. **Test the Scenario**
   - Click "Run once" to test
   - Send test data to the webhook URL:
     ```json
     {
       "company": "Test Company",
       "contact_name": "John Doe",
       "email": "john@test.com",
       "phone": "+1234567890",
       "linkedin": "https://linkedin.com/in/johndoe",
       "location": "Los Angeles, CA",
       "industry": "Technology",
       "role": "CEO",
       "employee_count": "50",
       "notes": "Interested in automation"
     }
     ```
   - Verify the scenario executes successfully

---

# 📗 SCENARIO B - Initial Outreach Email

## What This Scenario Does
Watches Airtable for new leads, validates email, generates personalized outreach email with AI, sends email, and updates Airtable.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario B - Initial Outreach.blueprint.json`

2. **Configure Module 1: Airtable Watch Records**
   - Click on **Airtable Watch Records** module
   - **Connection**: Select your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Label Field**: `Company`
   - **Trigger Field**: `Last Modified Time`
   - **Filter Formula**: `AND({Status} = "new", {Contact Email} != "", {Do Not Contact} = 0)`
   - **Max Records**: 10
   - Click "OK"

3. **Configure Module 2: Router (Email Validation)**
   - Click on **Router** module
   - **Route**: Select "If/Else"
   - **Filter**: `{{1.Contact Email}} != "" AND {{1.Contact Email}} CONTAINS "@" AND LENGTH({{1.Contact Email}}) > 5`
   - Click "OK"

4. **Configure Module 3: OpenAI Create Model Response**
   - Click on **OpenAI** module
   - **Connection**: Select your OpenAI connection
   - **Input**: The prompt should already be set, but verify it references:
     - `{{1.Contact Full Name}}`
     - `{{1.Company}}`
     - `{{1.Industry}}`
     - `{{1.Location City}}`, `{{1.Location State}}`
     - `{{1.Contact Role}}`
     - `{{1.Employee Count}}`
     - `{{1.Notes}}`
   - **Model**: `gpt-4o`
   - **Format**: Select "JSON object"
   - **Store Conversation**: Yes
   - **Create Conversation**: Yes
   - Click "OK"

5. **Configure Module 4: Parse JSON**
   - Click on **Parse JSON** module
   - **JSON**: Enter `{{3.text.output[0].content[0].text}}` (OpenAI module ID is 3)
   - **Data structure**: Click "Add" → Select "AI JSON" or create structure:
     - `subject` (text)
     - `body` (text)
   - Click "OK"

6. **Configure Module 5: Google Email Send**
   - Click on **Google Email Send** module
   - **Connection**: Select your Gmail/Google Email connection
   - **To**: `{{1.Contact Email}}` (wrap in array brackets: `["{{1.Contact Email}}"]`)
   - **Subject**: `{{4.subject}}`
   - **Content**: Should contain HTML template with `{{4.body}}`
   - **Body Type**: Select "Raw HTML"
   - Click "OK"

7. **Configure Module 6: Airtable Update Record**
   - Click on **Airtable Update Record** module
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Record ID**: `{{1.id}}`
   - **Fields to Update**:
     - **Email Campaign**: `"initial outreach"`
     - **Last Out Reach**: `{{now}}`
     - **Status**: `"emailed"`
   - Click "OK"

8. **Test the Scenario**
   - Create a test record in Airtable with Status = "new" and a valid Contact Email
   - Save the record
   - The scenario should trigger automatically

---

# 📙 SCENARIO C - Follow-up Email

## What This Scenario Does
Watches for leads that haven't replied after 5+ days, generates follow-up email, sends it, and updates Airtable.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario C - Follow-up Email.blueprint.json`

2. **Configure Module 1: Airtable Watch Records**
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Filter Formula**: `AND({Last Out Reach} < TODAY() - 5, {Reply Received} = 0, {Email Campaign} = "initial outreach", {Do Not Contact} = 0, {Contact Email} != "")`
   - **Max Records**: 10
   - Click "OK"

3. **Configure Module 2: OpenAI Create Model Response**
   - **Connection**: Your OpenAI connection
   - **Input**: Verify it references `{{1.Company}}`, `{{1.Contact Full Name}}`, etc.
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - Click "OK"

4. **Configure Module 3: Parse JSON**
   - **JSON**: Enter `{{2.text.output[0].content[0].text}}` (OpenAI module ID is 2)
   - **Data structure**: `subject` and `body` fields
   - Click "OK"

5. **Configure Module 4: Google Email Send**
   - **To**: `{{1.Contact Email}}`
   - **Subject**: `{{3.subject}}`
   - **Content**: HTML template with `{{3.body}}`
   - **Body Type**: Raw HTML
   - Click "OK"

6. **Configure Module 5: Airtable Update Record**
   - **Record ID**: `{{1.id}}`
   - **Email Campaign**: `"follow_up_1"`
   - **Last Out Reach**: `{{now}}`
   - **Status**: `"follow_up_sent"`
   - Click "OK"

---

# 📕 SCENARIO D - Smart Lead Enrichment & Outreach

## What This Scenario Does
Enriches lead data with AI (domain, company name, industry, tags), then sends personalized outreach using enriched data.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario D - Smart Enrichment.blueprint.json`

2. **Configure Module 1: Airtable Watch Records**
   - **Filter Formula**: `AND({Status} = "new", {Contact Email} != "", {Domain} = "", {Do Not Contact} = 0)`
   - **Max Records**: 5
   - Click "OK"

3. **Configure Module 2: OpenAI (Enrichment)**
   - **Input**: Contains enrichment prompt
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **Create Conversation**: No
   - Click "OK"

4. **Configure Module 3: Parse JSON (Enrichment Data)**
   - **JSON**: `{{2.text.output[0].content[0].text}}`
   - **Data structure**: `domain`, `company`, `industry`, `tags` (array), `employee_count_estimate`
   - Click "OK"

5. **Configure Module 4: Airtable Update Record (Save Enrichment)**
   - **Record ID**: `{{1.id}}`
   - Map enriched fields:
     - **Domain**: `{{3.domain}}`
     - **Company**: `{{3.company}}`
     - **Industry**: `{{3.industry}}`
     - **Tags**: `{{3.tags}}`
     - **Employee Count**: `{{3.employee_count_estimate}}`
   - Click "OK"

6. **Configure Module 5: OpenAI (Email Generation)**
   - **Input**: Uses enriched data `{{3.domain}}`, `{{3.company}}`, etc.
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **Create Conversation**: Yes
   - Click "OK"

7. **Configure Module 6: Parse JSON (Email Data)**
   - **JSON**: `{{5.text.output[0].content[0].text}}` (Second OpenAI module ID is 5)
   - **Data structure**: `subject`, `body`
   - Click "OK"

8. **Configure Module 7: Google Email Send**
   - **To**: `{{1.Contact Email}}`
   - **Subject**: `{{6.subject}}`
   - **Content**: HTML with `{{6.body}}`
   - **Body Type**: Raw HTML
   - Click "OK"

9. **Configure Module 8: Airtable Update Record**
   - **Record ID**: `{{1.id}}`
   - **Email Campaign**: `"initial outreach"`
   - **Last Out Reach**: `{{now}}`
   - **Status**: `"emailed"`
   - Click "OK"

---

# 📔 SCENARIO E - Multi-Channel Follow-up Sequence

## What This Scenario Does
Uses AI to determine email vs SMS strategy, sends multi-channel follow-up, updates Airtable.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario E - Multi-Channel Sequence.blueprint.json`

2. **Configure Module 1: Airtable Watch Records**
   - **Filter Formula**: `AND({Last Out Reach} < TODAY() - 7, {Reply Received} = 0, {Email Campaign} IN ["initial outreach", "follow_up_1"], {Do Not Contact} = 0, {Contact Email} != "", {Contact Phone} != "")`
   - **Max Records**: 5
   - Click "OK"

3. **Configure Module 2: OpenAI Create Model Response**
   - **Input**: Multi-channel strategy prompt
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **Output should include**: `channel_order`, `email_subject`, `email_body`, `sms_body`
   - Click "OK"

4. **Configure Module 3: Parse JSON**
   - **JSON**: `{{2.text.output[0].content[0].text}}`
   - **Data structure**:
     - `channel_order` (array)
     - `email_subject` (text)
     - `email_body` (text)
     - `sms_body` (text)
   - Click "OK"

5. **Configure Module 4: Router (Channel Decision)**
   - **Route**: If/Else
   - **Filter**: `{{3.channel_order[0]}} = "email"`
   - Click "OK"

6. **Configure Module 5: Google Email Send** (If path)
   - **To**: `{{1.Contact Email}}`
   - **Subject**: `{{3.email_subject}}`
   - **Content**: HTML with `{{3.email_body}}`
   - **Body Type**: Raw HTML
   - Click "OK"

7. **Configure Module 6: Twilio Create Message** (Else path)
   - **Connection**: Create/select Twilio connection
   - **Action**: "Create a Message"
   - **To**: `{{1.Contact Phone}}`
   - **From**: Your Twilio phone number (e.g., `+1234567890`)
   - **Body**: `{{3.sms_body}}`
   - Click "OK"

8. **Configure Module 7: Airtable Update Record**
   - **Record ID**: `{{1.id}}`
   - **Email Campaign**: `"multi_channel_followup"`
   - **Last Out Reach**: `{{now}}`
   - **Status**: `"contacted"`
   - Click "OK"

---

# 📓 SCENARIO F - Reply Detection & Auto-Response

## What This Scenario Does
Receives email via webhook, analyzes reply with AI, updates Airtable, sends auto-response.

## ⚠️ IMPORTANT SETUP NOTE
This scenario uses a webhook trigger, but you'll need to manually replace it with a Gmail trigger in Make.com after import.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario F - Reply Detection.blueprint.json`

2. **Replace Webhook with Gmail Trigger** (CRITICAL STEP)
   - **Delete Module 1** (Webhook)
   - Click "+" → Search "Gmail"
   - Add **"Watch new emails"** trigger
   - **Connection**: Your Gmail connection
   - **Folder**: Select "Inbox"
   - **Filter**: `from:your-outreach-email@domain.com` (optional)
   - **Mark email as read**: Yes
   - Connect this to Module 2 (OpenAI)

3. **Configure Module 2: OpenAI Create Model Response**
   - **Connection**: Your OpenAI connection
   - **Input**: Should reference email fields (if using Gmail trigger, use `{{1.from}}`, `{{1.subject}}`, `{{1.text}}`, etc.)
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **Expected output**: `is_reply`, `sentiment`, `intent`, `topics`, `action`, `response_message`
   - Click "OK"

4. **Configure Module 3: Parse JSON**
   - **JSON**: `{{2.text.output[0].content[0].text}}`
   - **Data structure**:
     - `is_reply` (boolean)
     - `sentiment` (text)
     - `intent` (text)
     - `topics` (array)
     - `action` (text)
     - `response_message` (text)
   - Click "OK"

5. **Configure Module 4: Router (Is Reply Check)**
   - **Route**: If/Else
   - **Filter**: `{{3.is_reply}} = true`
   - Click "OK"

6. **Configure Module 5: Airtable Search Records**
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Formula**: `{Contact Email} = '{{1.from}}'` (or Gmail equivalent)
   - **Max Records**: 1
   - Click "OK"

7. **Configure Module 6: Router (Action Routing)**
   - **Route**: Switch
   - **Filter**: `{{3.action}}`
   - **Routes**: acknowledge, send_info, schedule_call, unsubscribe, escalate
   - Click "OK"

8. **Configure Module 7: Airtable Update Record**
   - **Record ID**: `{{5.id[0]}}`
   - **Reply Received**: `true`
   - **Status**: `"replied_{{3.sentiment}}"`
   - **Notes**: `"Reply: {{1.body}}\nIntent: {{3.intent}}\nTopics: {{3.topics}}"`
   - Click "OK"

9. **Configure Module 8: Google Email Send**
   - **To**: `{{1.from}}`
   - **Subject**: `Re: {{1.subject}}`
   - **Content**: HTML with `{{3.response_message}}`
   - **Body Type**: Raw HTML
   - Click "OK"

10. **Configure Module 9: Airtable Update Record**
    - **Record ID**: `{{5.id[0]}}`
    - **Email Campaign**: `"auto_response_sent"`
    - **Status**: `"awaiting_response"`
    - Click "OK"

---

## 🎯 General Troubleshooting Tips

1. **JSON Parsing Errors**
   - Verify the OpenAI module ID matches the reference in Parse JSON
   - Ensure OpenAI format is set to "JSON object"
   - Check that the prompt explicitly asks for JSON output

2. **Airtable Connection Issues**
   - Verify Base ID and Table ID are correct
   - Check field names match exactly (case-sensitive)
   - Ensure "Use Column IDs" is set correctly

3. **Email Sending Issues**
   - Verify Gmail connection is authorized
   - Check email addresses are in correct format
   - Ensure "Raw HTML" is selected for HTML emails

4. **Router Logic Errors**
   - Double-check filter conditions
   - Verify data types match (text vs boolean vs number)
   - Test with sample data first

5. **Module Not Found Errors**
   - All scenarios use only verified modules
   - If you see this error, check you're using the latest blueprint files

---

## ✅ Verification Checklist

After setting up each scenario:

- [ ] All connections are configured (Airtable, OpenAI, Gmail, Twilio if needed)
- [ ] All module IDs are correctly referenced in JSON parsing
- [ ] Airtable base and table IDs are correct
- [ ] Field names match your Airtable schema
- [ ] Test run executes without errors
- [ ] Data flows correctly through all modules
- [ ] Emails/SMS send successfully
- [ ] Airtable records update correctly

---

**Need Help?** Refer to the VERIFIED_MAKE_COM_MODULES.md file for module reference.

