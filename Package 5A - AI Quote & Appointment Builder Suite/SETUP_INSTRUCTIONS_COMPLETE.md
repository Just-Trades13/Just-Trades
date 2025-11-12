# Complete Make.com Setup Instructions for Package 5A (All Scenarios)

## 📋 IMPORTANT: JSON Parsing Pattern

**The JSON parsing reference varies by scenario based on the OpenAI module ID:**

- **Scenario 5A-A**: OpenAI module ID = 5, so use: `{{5.text.output[0].content[0].text}}`
- **Scenario 5A-B**: First OpenAI ID = 2, Second OpenAI ID = 5, so use: `{{2.text.output[0].content[0].text}}` and `{{5.text.output[0].content[0].text}}`
- **Scenario 5A-C**: OpenAI module ID = 2, so use: `{{2.text.output[0].content[0].text}}`
- **Scenario 5A-D**: First OpenAI ID = 3, Second OpenAI ID = 9, so use: `{{3.text.output[0].content[0].text}}` and `{{9.text.output[0].content[0].text}}`
- **Scenario 5A-E**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`
- **Scenario 5A-F**: OpenAI module ID = 3, so use: `{{3.text.output[0].content[0].text}}`

**The pattern is: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`**

---

## 🔧 Prerequisites

Before importing any scenario, ensure you have:

1. **Make.com Account** with appropriate plan
2. **Airtable Connection** configured (Base ID: `appo7Y0cbtd1wa8Ph`, Table ID: `tblmVnZaaWToTXxaR`)
3. **OpenAI Connection** configured with API key
4. **Gmail/Google Email Connection** configured
5. **Google Docs Connection** (requires OAuth setup)
6. **Form System** (Google Forms, Typeform, or webhook-capable system)
7. **Google Calendar Connection** (for Scenario 5A-C, optional)
8. **Quote Template** created in Google Docs (see `QUOTE_TEMPLATE_SETUP.md`)

---

## ⚠️ CRITICAL: Module Setup Requirements

**All scenarios use `gateway:CustomWebHook` as placeholders. You MUST replace or configure these after import:**

1. **Form Triggers**: Replace webhook with native form trigger OR keep webhook and configure form to send to webhook URL
2. **Google Docs**: Replace webhook with Google Docs "Create Document" module manually
3. **Google Calendar**: Replace webhook with Google Calendar modules manually (Scenario 5A-C)
4. **Schedule**: Replace webhook with Schedule module manually (Scenario 5A-F)

---

# 📘 SCENARIO 5A-A - Basic Quote Generator

## What This Scenario Does
Receives form/webhook data, generates AI-powered quote, creates Google Doc, sends email to client, and tracks in Airtable.

## Import Steps

1. **Import the Blueprint**
   - Go to Make.com → Scenarios → Create a new scenario
   - Click "Import" → Upload `Scenario 5A-A - Basic Quote Generator.blueprint.json`
   - Click "Import" button

2. **Configure Module 1: Form/Webhook Trigger**
   - **Option A (Keep Webhook)**: Configure your form to send data to webhook URL
   - **Option B (Replace with Form Trigger)**: Delete webhook, add native form trigger (Google Forms, Typeform, etc.)
   - **Expected fields**: `name`, `email`, `phone`, `company`, `service_type`, `requirements`, `budget_range`
   - Connect to Module 2 (Airtable Search)

3. **Configure Module 2: Airtable Search Records**
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - **Formula**: `{Contact Email} = '{{1.email}}'`
   - **Max Records**: 1
   - Click "OK"

4. **Configure Module 3: Router (New vs Existing)**
   - **Route**: If/Else
   - **Filter**: `{{2.id[0]}} is empty`
   - Click "OK"

5. **Configure Module 4: Airtable Create Record** (If path - new contact)
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph`
   - **Table**: `tblmVnZaaWToTXxaR`
   - Map fields:
     - **Contact Full Name**: `{{1.name}}`
     - **Contact Email**: `{{1.email}}`
     - **Contact Phone**: `{{1.phone}}`
     - **Company**: `{{1.company}}`
     - **Status**: `quote_requested`
     - **Notes**: `Quote request submitted via form. Service: {{1.service_type}}. Requirements: {{1.requirements}}`
   - Click "OK"

6. **Configure Module 5: OpenAI Create Model Response** (Else path - existing contact)
   - **Connection**: Your OpenAI connection
   - **Input**: Verify prompt includes all form data (name, company, service_type, requirements, budget_range)
   - **Model**: `gpt-4o`
   - **Format**: JSON Object
   - **Temperature**: 0.7
   - **Max Tokens**: 1000
   - Click "OK"

7. **Configure Module 6: Parse JSON**
   - **JSON**: Enter `{{5.text.output[0].content[0].text}}` (OpenAI module ID is 5)
   - **Data structure**: Should include `quote_title`, `introduction`, `services` (array), `total_price`, `terms`, `next_steps`
   - Click "OK"

8. **Replace Module 7: Google Docs Webhook with Native Module** (CRITICAL)
   - **Delete Module 7** (webhook placeholder)
   - Click "+" → Search "Google Docs"
   - Add **"Create a Document"** module
   - **Connection**: Create/select Google Docs connection (OAuth)
   - **Method**: "Copy Document" (to copy from template)
   - **Source Document**: Enter your quote template document ID (see `QUOTE_TEMPLATE_SETUP.md`)
   - **Title**: `Quote for {{1.company}}`
   - **Content**: Map quote data from `{{6}}` JSON structure
   - Connect to Module 8 (Email)
   - Click "OK"

9. **Configure Module 8: Gmail Send Email**
   - **Connection**: Your Gmail connection
   - **To**: `{{1.email}}`
   - **Subject**: `Quote for {{1.company}} - {{6.quote_title}}`
   - **Body Type**: HTML
   - **Content**: HTML template with quote details from `{{6}}`
   - Click "OK"

10. **Configure Module 9: Airtable Update Record**
    - **Connection**: Your Airtable connection
    - **Record ID**: `{{if({{2.id[0]}}; {{2.id[0]}}; {{4.id}})}}` (use existing or new record ID)
    - Map fields:
      - **Status**: `quote_sent`
      - **Notes**: `Quote generated and sent via Scenario 5A-A. Total: ${{6.total_price}}. Sent at {{now}}`
    - Click "OK"

11. **Test the Scenario**
    - Submit test form data or send webhook request
    - Verify quote is generated
    - Check Google Docs for created document
    - Verify email is sent
    - Check Airtable for updated record

---

# 📗 SCENARIO 5A-B - Smart Quote with Pricing Logic

## What This Scenario Does
Receives form data, analyzes pricing with AI (location, urgency, complexity), generates smart quote, creates document, and delivers via email.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 5A-B - Smart Quote with Pricing Logic.blueprint.json`

2. **Configure Module 1: Form/Webhook Trigger**
   - Same as Scenario 5A-A
   - **Additional fields**: `location`, `urgency` (for pricing multipliers)
   - Connect to Module 2 (OpenAI)

3. **Configure Module 2: OpenAI Create Model Response** (Pricing Analysis)
   - **Connection**: Your OpenAI connection
   - **Input**: Verify prompt includes location, urgency, service_type for pricing calculation
   - **Model**: `gpt-4o`
   - **Format**: JSON Object
   - **Output should include**: `base_price`, `location_multiplier`, `urgency_multiplier`, `complexity_factor`, `final_price`, `pricing_breakdown`, `recommended_tier`
   - Click "OK"

4. **Configure Module 3: Parse JSON** (Pricing)
   - **JSON**: Enter `{{2.text.output[0].content[0].text}}`
   - **Data structure**: Verify all pricing fields are accessible
   - Click "OK"

5. **Configure Module 4: Router** (Pricing Tier Routing)
   - **Route**: Switch
   - **Filter**: `{{3.recommended_tier}}`
   - Routes: `basic`, `standard`, `premium` (add routes as needed)
   - Click "OK"

6. **Configure Module 5: OpenAI Create Model Response** (Quote Generation)
   - **Connection**: Your OpenAI connection
   - **Input**: Includes pricing data from Module 3
   - **Model**: `gpt-4o`
   - **Format**: JSON Object
   - **Output should include**: Quote with pricing breakdown
   - Click "OK"

7. **Configure Module 6: Parse JSON** (Quote)
   - **JSON**: Enter `{{5.text.output[0].content[0].text}}`
   - Click "OK"

8. **Replace Module 7: Google Docs** (Same as Scenario 5A-A)
   - Replace webhook with Google Docs "Create Document" module
   - Use pricing data from `{{6}}` for document content

9. **Configure Module 8: Gmail Send Email**
   - Similar to Scenario 5A-A
   - Include pricing breakdown in email
   - Add booking link if applicable

10. **Configure Modules 9-12: Airtable Search and Update**
    - Same pattern as Scenario 5A-A
    - Include pricing tier information in Notes field

11. **Test the Scenario**
    - Test with different location/urgency combinations
    - Verify pricing multipliers are applied correctly

---

# 📙 SCENARIO 5A-C - Quote with Booking Integration

## What This Scenario Does
Generates quote, checks calendar availability, delivers quote with booking options, and auto-books on confirmation.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 5A-C - Quote with Booking Integration.blueprint.json`

2. **Configure Module 1: Form/Webhook Trigger**
   - Same as previous scenarios
   - Connect to Module 2 (OpenAI)

3. **Configure Module 2: OpenAI Create Model Response**
   - Generate quote with booking slots
   - Output should include `booking_slots` array
   - Click "OK"

4. **Configure Module 3: Parse JSON**
   - Parse quote JSON including booking slots
   - Click "OK"

5. **Replace Module 4: Google Calendar List Events** (CRITICAL)
   - **Delete webhook placeholder**
   - Add Google Calendar "List Events" module
   - **Connection**: Google Calendar connection
   - **Calendar**: Your calendar
   - **Time Min**: Current time
   - **Time Max**: 7 days from now
   - **Max Results**: 10
   - Click "OK"

6. **Replace Module 5: Google Docs** (Same as before)
   - Create quote document with booking options

7. **Configure Module 6: Gmail Send Email**
   - Include booking slots in email
   - Add booking link (Calendly or similar)
   - Click "OK"

8. **Configure Module 7: Booking Confirmation Webhook**
   - **Keep webhook** OR replace with Calendly/booking system webhook
   - **Expected fields**: `email`, `booking_time`, `booking_date`
   - Connect to Module 8 (Router)

9. **Configure Module 8: Router** (Verify Email Match)
   - **Route**: If/Else
   - **Filter**: `{{7.email}} = {{1.email}}`
   - Click "OK"

10. **Replace Module 9: Google Calendar Create Event** (CRITICAL)
    - **Delete webhook placeholder**
    - Add Google Calendar "Create Event" module
    - **Connection**: Google Calendar connection
    - **Calendar**: Your calendar
    - **Summary**: `Consultation - {{1.company}}`
    - **Start**: `{{7.booking_date}}T{{7.booking_time}}`
    - **End**: Same as start + 1 hour (adjust as needed)
    - Click "OK"

11. **Configure Modules 10-11: Airtable Update**
    - Update record with booking confirmation
    - Status: `quote_sent_booking_confirmed`
    - Include booking details in Notes

12. **Test the Scenario**
    - Test quote generation
    - Test calendar availability check
    - Test booking confirmation flow

---

# 📕 SCENARIO 5A-D - Multi-Step Quote Builder

## What This Scenario Does
Receives initial intake, determines if more info needed, sends follow-up questions, receives additional details, generates comprehensive quote.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 5A-D - Multi-Step Quote Builder.blueprint.json`

2. **Configure Module 1: Initial Intake Webhook**
   - **Fields**: `name`, `email`, `company`, `service_type`, `initial_requirements`
   - Connect to Module 2 (Airtable Create)

3. **Configure Module 2: Airtable Create Record**
   - Create lead with status `quote_in_progress`
   - Store initial requirements
   - Click "OK"

4. **Configure Module 3: OpenAI Create Model Response** (Determine if More Info Needed)
   - **Input**: Analyze initial requirements
   - **Output**: `needs_more_info` (boolean), `follow_up_questions` (array), `reason`
   - **Format**: JSON Object
   - Click "OK"

5. **Configure Module 4: Parse JSON**
   - Parse AI response
   - Click "OK"

6. **Configure Module 5: Router** (Check if More Info Needed)
   - **Route**: If/Else
   - **Filter**: `{{4.needs_more_info}} = true`
   - Click "OK"

7. **Configure Module 6: Gmail Send Email** (Follow-up Questions - If path)
   - **To**: `{{1.email}}`
   - **Subject**: `Quick Questions to Complete Your Quote - {{1.company}}`
   - **Body**: Include `{{4.follow_up_questions}}` array
   - Add form link for submitting answers
   - Click "OK"

8. **Configure Module 7: Additional Details Webhook** (Second Form)
   - **Keep webhook** OR replace with form trigger
   - **Expected fields**: `email`, `additional_details`, `answers`
   - Connect to Module 8 (Airtable Search)

9. **Configure Module 8: Airtable Search Records**
   - **Formula**: `{Contact Email} = '{{7.email}}' AND {Status} = 'quote_in_progress'`
   - Connect to Module 9 (OpenAI)

10. **Configure Module 9: OpenAI Create Model Response** (Generate Comprehensive Quote)
    - **Input**: Include initial requirements from Airtable record + additional details
    - **Output**: Comprehensive quote with executive summary, deliverables, timeline, pricing
    - **Format**: JSON Object
    - Click "OK"

11. **Configure Module 10: Parse JSON**
    - Parse comprehensive quote JSON
    - Click "OK"

12. **Replace Module 11: Google Docs** (Same as before)
    - Create detailed proposal document

13. **Configure Module 12: Gmail Send Email**
    - Send comprehensive quote
    - Include all quote sections

14. **Configure Module 13: Airtable Update Record**
    - Status: `quote_sent`
    - Include comprehensive quote details in Notes

15. **Test the Scenario**
    - Test initial intake
    - Test follow-up question flow
    - Test comprehensive quote generation

---

# 📔 SCENARIO 5A-E - Advanced Quote with Comparison

## What This Scenario Does
Generates three-tier quote options (Basic, Standard, Premium), creates comparison document, delivers via email, tracks preference.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 5A-E - Advanced Quote with Comparison.blueprint.json`

2. **Configure Module 1: Form/Webhook Trigger**
   - Same as Scenario 5A-A
   - Additional field: `budget_range` (for routing)
   - Connect to Module 2 (Airtable Search)

3. **Configure Module 2: Airtable Search Records**
   - Same as Scenario 5A-A
   - Connect to Module 3 (OpenAI)

4. **Configure Module 3: OpenAI Create Model Response** (Generate Three Tiers)
   - **Input**: Include service_type, requirements, budget_range
   - **Output**: Three quote tiers with comparison
   - **Format**: JSON Object
   - **Structure**: `basic`, `standard`, `premium` objects, each with `name`, `description`, `features`, `price`, `best_for`
   - Also include: `comparison_notes`, `recommendation`
   - Click "OK"

5. **Configure Module 4: Parse JSON**
   - Parse comparison quote JSON
   - Click "OK"

6. **Configure Module 5: Router** (Budget-based Routing - Optional)
   - **Route**: Switch
   - **Filter**: `{{1.budget_range}}`
   - Routes: `low`, `medium`, `high`
   - This can be used to highlight specific tier

7. **Replace Module 6: Google Docs** (Same as before)
   - Create comparison document
   - Format as side-by-side comparison

8. **Configure Module 7: Gmail Send Email**
   - **Subject**: `Your Quote Options - {{1.company}}`
   - **Body**: HTML with three-tier comparison layout
   - Include recommendation
   - Add booking link

9. **Configure Modules 8-10: Airtable Create/Update**
   - Same pattern as Scenario 5A-A
   - Status: `quote_options_sent`
   - Notes: Include all three tier prices and recommendation

10. **Test the Scenario**
    - Test three-tier generation
    - Verify comparison document format
    - Test email delivery with all options

---

# 📓 SCENARIO 5A-F - Quote Analytics & Tracking

## What This Scenario Does
Runs on schedule, aggregates quote data, analyzes performance, generates report, sends analytics email.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 5A-F - Quote Analytics & Tracking.blueprint.json`

2. **Replace Module 1: Schedule Trigger** (CRITICAL)
   - **Delete webhook placeholder**
   - Click "+" → Search "Schedule"
   - Add **"Schedule"** module
   - **Frequency**: Daily or Weekly
   - **Time**: Choose preferred time (e.g., 9:00 AM)
   - **Timezone**: Your timezone
   - Connect to Module 2 (Airtable Search)
   - Click "OK"

3. **Configure Module 2: Airtable Search Records**
   - **Connection**: Your Airtable connection
   - **Formula**: `OR({Status} = "quote_sent", {Status} = "quote_accepted", {Status} = "quote_declined", {Status} = "quote_options_sent")`
   - **Max Records**: 100 (or more if needed)
   - **Sort**: By "Last Modified Time" descending
   - Click "OK"

4. **Configure Module 3: OpenAI Create Model Response** (Analytics Analysis)
   - **Input**: Aggregate quote data summary from Airtable
   - **Output**: Analytics report with metrics
   - **Format**: JSON Object
   - **Structure**: `total_quotes_sent`, `quotes_accepted`, `quotes_declined`, `quotes_pending`, `acceptance_rate`, `average_quote_value`, `average_conversion_time`, `best_performing_service`, `insights` (array), `recommendations` (array), `period`
   - Click "OK"

5. **Configure Module 4: Parse JSON**
   - Parse analytics JSON
   - Click "OK"

6. **Replace Module 5: Google Docs** (Analytics Report)
   - Create analytics report document
   - Include charts/visualizations if possible
   - Format as professional report

7. **Configure Module 6: Gmail Send Email**
   - **To**: Your email address (or team email)
   - **Subject**: `Quote Analytics Report - {{now}}`
   - **Body**: HTML report with all metrics
   - Include insights and recommendations
   - Attach Google Doc if possible

8. **Test the Scenario**
    - Run test execution manually
    - Verify analytics are calculated correctly
    - Check report document
    - Verify email delivery

---

## 🎯 General Configuration Tips

### Google Docs Template Setup
- See `QUOTE_TEMPLATE_SETUP.md` for detailed template creation
- Create templates before setting up scenarios
- Test template copying manually first

### OpenAI Prompt Customization
- All prompts can be customized for your business
- Adjust temperature for more/less creative quotes
- Modify JSON output structure as needed

### Email Templates
- Customize HTML email templates
- Add your branding
- Include booking links where applicable
- Test email formatting in different email clients

### Airtable Field Mapping
- Verify all field names match your Airtable schema
- Add custom fields as needed
- Use field picker in Make.com to avoid typos

---

## ✅ Testing Checklist

For each scenario:
- [ ] Import successful
- [ ] All webhooks replaced with native modules
- [ ] All connections configured
- [ ] Field mappings verified
- [ ] Test execution successful
- [ ] Quote generated correctly
- [ ] Google Doc created (if applicable)
- [ ] Email sent successfully
- [ ] Airtable record updated
- [ ] All data flows correctly

---

**Last Updated**: 2025-01-XX  
**Package**: Package 5A - AI Quote & Appointment Builder Suite

