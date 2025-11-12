# Complete Make.com Setup Instructions for Package 4A (All Scenarios)

## 📋 IMPORTANT: JSON Parsing Pattern

**The JSON parsing reference varies by scenario based on the OpenAI module ID:**

- **Scenario 4A-A**: OpenAI module ID = 3 (email path) or 6 (SMS path), so use: `{{3.text.output[0].content[0].text}}` or `{{6.text.output[0].content[0].text}}`
- **Scenario 4A-B**: Multiple OpenAI modules (3, 4, 5), parsed via modules 6, 7, 8 - check which branch is active
- **Scenario 4A-C**: OpenAI module ID = 2, so use: `{{2.text.output[0].content[0].text}}`
- **Scenario 4A-D**: Multiple OpenAI modules (3, 4, 5), parsed via module 6 with conditional logic
- **Scenario 4A-E**: OpenAI module ID = 3 (high) or 4 (medium), parsed via module 5 with conditional logic
- **Scenario 4A-F**: OpenAI module ID = 5, so use: `{{5.text.output[0].content[0].text}}`

**The pattern is: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`**

---

## 🔧 Prerequisites

Before importing any scenario, ensure you have:

1. **Make.com Account** with appropriate plan
2. **Airtable Connection** configured (Base ID: `appo7Y0cbtd1wa8Ph`, Table ID: `tblmVnZaaWToTXxaR`)
3. **OpenAI Connection** configured with API key
4. **Gmail/Google Email Connection** (for email reactivation)
5. **Twilio Connection** configured with phone number (optional - for SMS reactivation)
6. **Airtable Fields** set up:
   - Required: `Contact Email`, `Contact Phone`, `Contact Full Name`, `Company`, `Status`, `Last Out Reach`, `Reply Received`, `Do Not Contact`, `Email Campaign`, `Notes`
   - Optional for 4A-D: `Reactivation Stage` (with values: `stage_1`, `stage_2`, `stage_3`, `completed`)
   - Optional for 4A-E: `Lead Score` (number), `Engagement History` (text)

---

## ⚠️ CRITICAL: Module Setup Notes

**Twilio Modules**: Require manual setup after import (appear as "Module Not Found")
**Schedule Module**: Scenarios 4A-D and 4A-F use webhooks as placeholders - replace with Schedule module

---

# 📘 SCENARIO 4A-A - Basic Lead Reactivation

## What This Scenario Does
Triggers on leads not contacted in 30+ days, generates personalized reactivation message via AI, sends via email or SMS based on available contact info, and updates CRM.

## Import Steps

1. **Import the Blueprint**
   - Go to Make.com → Scenarios → Create a new scenario
   - Click "Import" → Upload `Scenario 4A-A - Basic Lead Reactivation.blueprint.json`
   - Click "Import" button

2. **Configure Module 1: Airtable Trigger Watch Records**
   - **Connection**: Your Airtable connection
   - **Base**: `appo7Y0cbtd1wa8Ph` (or your base ID)
   - **Table**: `tblmVnZaaWToTXxaR` (or your table ID)
   - **Formula**: `AND({Last Out Reach} < TODAY() - 30, {Reply Received} = 0, {Do Not Contact} = 0, OR({Contact Email} != "", {Contact Phone} != ""))`
   - **Max Records**: 10 (adjust for testing)
   - Click "OK"

3. **Configure Module 2: Router (Email vs SMS)**
   - **Route**: If/Else
   - **Filter**: `{{1.Contact Email}} != "" AND LENGTH({{1.Contact Email}}) > 5`
   - **If path**: Email route (Modules 3-5)
   - **Else path**: SMS route (Modules 6-8)
   - Click "OK"

4. **Configure Module 3: OpenAI (Email Path)**
   - **Connection**: Your OpenAI connection
   - **Input**: Verify prompt includes lead information
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - Click "OK"

5. **Configure Module 4: Parse JSON (Email Path)**
   - **JSON**: `{{3.text.output[0].content[0].text}}`
   - **Type**: AI JSON
   - Click "OK"

6. **Configure Module 5: Google Email Send**
   - **Connection**: Your Gmail/Google Email connection
   - **To**: `{{1.Contact Email}}`
   - **Subject**: `{{4.subject}}`
   - **Content**: HTML with `{{4.body}}`
   - **Body Type**: Raw HTML
   - Click "OK"

7. **Configure Module 6: OpenAI (SMS Path)**
   - **Connection**: Your OpenAI connection
   - **Input**: Verify prompt includes lead information
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - Click "OK"

8. **Configure Module 7: Parse JSON (SMS Path)**
   - **JSON**: `{{6.text.output[0].content[0].text}}`
   - **Type**: AI JSON
   - Click "OK"

9. **Configure Module 8: Twilio Create Message** (REQUIRES MANUAL SETUP)
   - **Delete** the "Module Not Found" Twilio module
   - Click "+" → Search "Twilio"
   - Add **"Create a Message"** module
   - **Connection**: Your Twilio connection
   - **To**: `{{1.Contact Phone}}`
   - **From**: Your Twilio phone number
   - **Body**: `{{7.message}} Reply STOP to opt out.`
   - Click "OK"

10. **Configure Module 9: Airtable Update Record**
    - **Connection**: Your Airtable connection
    - **Record ID**: `{{1.id}}`
    - Map fields:
      - **Email Campaign**: `reactivation_basic`
      - **Last Out Reach**: `{{now}}`
      - **Status**: `reactivation_sent`
      - **Notes**: Append reactivation note
    - Click "OK"

11. **Test the Scenario**
    - Ensure test leads meet trigger criteria in Airtable
    - Run scenario manually
    - Verify email/SMS sent
    - Check Airtable for updated records

---

# 📗 SCENARIO 4A-B - Smart Segmentation Reactivation

## What This Scenario Does
Triggers on segmented leads (cold_30d, no_reply_14d, no_show), generates segment-specific reactivation messages, and sends via optimal channel.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 4A-B - Smart Segmentation Reactivation.blueprint.json`

2. **Configure Module 1: Airtable Trigger**
   - **Base**: Your Airtable base
   - **Table**: Your Airtable table
   - **Formula**: `AND({Do Not Contact} = 0, OR({Status} = "cold_30d", {Status} = "no_reply_14d", {Status} = "no_show"))`
   - **Max Records**: 10
   - Click "OK"

3. **Configure Module 2: Router (Segment Routing)**
   - **Route**: Switch
   - **Cases**:
     - Case 1: `{{1.Status}} = "cold_30d"` → Routes to Module 3
     - Case 2: `{{1.Status}} = "no_reply_14d"` → Routes to Module 4
     - Case 3: `{{1.Status}} = "no_show"` → Routes to Module 5
   - Click "OK"

4. **Configure Modules 3, 4, 5: OpenAI (Per Segment)**
   - Each generates segment-specific message
   - **Connection**: Your OpenAI connection
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - Verify prompts are segment-specific

5. **Configure Modules 6, 7, 8: Parse JSON**
   - **Module 6**: `{{3.text.output[0].content[0].text}}`
   - **Module 7**: `{{4.text.output[0].content[0].text}}`
   - **Module 8**: `{{5.text.output[0].content[0].text}}`

6. **Configure Module 9: Router (Channel Selection)**
   - **Route**: If/Else
   - **Filter**: `{{6.channel}} = "email" OR {{7.channel}} = "email"`
   - Routes to appropriate channel module

7. **Configure Module 10: Google Email Send** (If path)
   - **To**: `{{1.Contact Email}}`
   - **Subject**: Conditional based on segment
   - **Content**: HTML with conditional body
   - Click "OK"

8. **Configure Module 11: Twilio Create Message** (Else path - REQUIRES MANUAL SETUP)
   - Add Twilio module manually
   - **To**: `{{1.Contact Phone}}`
   - **From**: Your Twilio number
   - **Body**: `{{8.body}} Reply STOP to opt out.`

9. **Configure Module 12: Airtable Update**
   - **Record ID**: `{{1.id}}`
   - **Email Campaign**: `reactivation_segmented`
   - **Last Out Reach**: `{{now}}`
   - **Status**: `reactivation_sent`
   - **Notes**: Append segment-specific note

10. **Test the Scenario**
    - Create test leads with segment statuses in Airtable
    - Run scenario
    - Verify segment-specific messages sent correctly

---

# 📙 SCENARIO 4A-C - Reactivation with Booking

## What This Scenario Does
Triggers on inactive leads who haven't booked, generates reactivation message with booking CTA, sends via email or SMS, and tracks booking status.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 4A-C - Reactivation with Booking.blueprint.json`

2. **Configure Module 1: Airtable Trigger**
   - **Base**: Your Airtable base
   - **Table**: Your Airtable table
   - **Formula**: `AND({Last Out Reach} < TODAY() - 14, {Reply Received} = 0, {Meeting Booked} = 0, {Do Not Contact} = 0, OR({Contact Email} != "", {Contact Phone} != ""))`
   - **Max Records**: 10
   - Click "OK"

3. **Configure Module 2: OpenAI**
   - **Connection**: Your OpenAI connection
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **Input**: Verify prompt includes booking CTA and available times
   - Click "OK"

4. **Configure Module 3: Parse JSON**
   - **JSON**: `{{2.text.output[0].content[0].text}}`
   - **Type**: AI JSON
   - Click "OK"

5. **Configure Module 4: Router (Email vs SMS)**
   - **Route**: If/Else
   - **Filter**: `{{1.Contact Email}} != "" AND LENGTH({{1.Contact Email}}) > 5`
   - Click "OK"

6. **Configure Module 5: Google Email Send** (If path)
   - **To**: `{{1.Contact Email}}`
   - **Subject**: `{{3.subject}}`
   - **Content**: HTML with booking link and suggested times
   - **Body Type**: Raw HTML
   - Click "OK"

7. **Configure Module 6: Twilio Create Message** (Else path - REQUIRES MANUAL SETUP)
   - Add Twilio module manually
   - **To**: `{{1.Contact Phone}}`
   - **From**: Your Twilio number
   - **Body**: `{{3.sms_message}} {{3.booking_link}} Reply STOP to opt out.`

8. **Configure Module 7: Airtable Update**
   - **Record ID**: `{{1.id}}`
   - **Email Campaign**: `reactivation_booking`
   - **Last Out Reach**: `{{now}}`
   - **Status**: `reactivation_booking_sent`
   - **Notes**: Include booking link and suggested times

9. **Test the Scenario**
    - Verify booking links are correct
    - Test with sample leads
    - Verify booking tracking in Airtable

---

# 📕 SCENARIO 4A-D - Multi-Touch Reactivation Sequence

## What This Scenario Does
Manages 3-stage reactivation sequence (stage_1, stage_2, stage_3), sends stage-appropriate messages with timing, tracks sequence progress, and stops on reply.

## ⚠️ IMPORTANT: This Scenario Requires Schedule Automation

**You need to set up a separate schedule scenario** to advance leads through stages:
- Day 0: Set `Reactivation Stage` = `stage_1` for qualifying leads
- Day 3: Advance `stage_1` → `stage_2`
- Day 7: Advance `stage_2` → `stage_3`

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 4A-D - Multi-Touch Reactivation Sequence.blueprint.json`

2. **Configure Module 1: Airtable Trigger**
   - **Base**: Your Airtable base
   - **Table**: Your Airtable table
   - **Formula**: `AND({Do Not Contact} = 0, OR({Reactivation Stage} = "stage_1", {Reactivation Stage} = "stage_2", {Reactivation Stage} = "stage_3"), {Reply Received} = 0)`
   - **Max Records**: 10
   - Click "OK"

3. **Configure Module 2: Router (Stage Routing)**
   - **Route**: Switch
   - **Cases**:
     - Case 1: `{{1.Reactivation Stage}} = "stage_1"`
     - Case 2: `{{1.Reactivation Stage}} = "stage_2"`
     - Case 3: `{{1.Reactivation Stage}} = "stage_3"`
   - Click "OK"

4. **Configure Modules 3, 4, 5: OpenAI (Per Stage)**
   - Module 3: Stage 1 message (gentle re-engagement)
   - Module 4: Stage 2 message (new angle)
   - Module 5: Stage 3 message (final touch)
   - **Connection**: Your OpenAI connection
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - Click "OK"

5. **Configure Module 6: Parse JSON**
   - **JSON**: Conditional based on stage: `{{IF({{1.Reactivation Stage}} = "stage_1", {{3.text.output[0].content[0].text}}, IF({{1.Reactivation Stage}} = "stage_2", {{4.text.output[0].content[0].text}}, {{5.text.output[0].content[0].text}})}}`
   - **Type**: AI JSON
   - Click "OK"

6. **Configure Module 7: Router (Channel Selection)**
   - **Route**: If/Else
   - **Filter**: `{{6.channel}} = "email"`

7. **Configure Module 8: Google Email Send** (If path)
   - **To**: `{{1.Contact Email}}`
   - **Subject**: `{{6.subject}}`
   - **Content**: HTML with stage-specific message
   - Click "OK"

8. **Configure Module 9: Twilio Create Message** (Else path - REQUIRES MANUAL SETUP)
   - Add Twilio module manually
   - **To**: `{{1.Contact Phone}}`
   - **Body**: `{{6.sms_message}} Reply STOP to opt out.`

9. **Configure Module 10: Router (Final Stage Check)**
   - **Route**: If/Else
   - **Filter**: `{{1.Reactivation Stage}} = "stage_3"`

10. **Configure Module 11: Airtable Update** (Advance Stage)
    - **Record ID**: `{{1.id}}`
    - **Reactivation Stage**: `{{IF({{1.Reactivation Stage}} = "stage_1", "stage_2", IF({{1.Reactivation Stage}} = "stage_2", "stage_3", "completed"))}}`
    - **Last Out Reach**: `{{now}}`
    - **Email Campaign**: `reactivation_multitouch_stage_{{6.stage}}`
    - **Status**: `reactivation_stage_{{6.stage}}_sent`
    - Click "OK"

11. **Configure Module 12: Airtable Update** (Complete Sequence)
    - **Record ID**: `{{1.id}}`
    - **Reactivation Stage**: `completed`
    - **Status**: `reactivation_completed`
    - Click "OK"

12. **Set Up Schedule Automation** (CRITICAL)
    - Create separate scenario with Schedule trigger
    - Daily schedule to advance stages:
      - Find leads with `Reactivation Stage` = `stage_1` and `Last Out Reach` < TODAY() - 3
      - Update to `stage_2`
    - Repeat for `stage_2` → `stage_3` (Day 7)

13. **Test the Scenario**
    - Set test lead to `Reactivation Stage` = `stage_1`
    - Run scenario
    - Verify stage advancement
    - Test all 3 stages

---

# 📔 SCENARIO 4A-E - Advanced Reactivation with Scoring

## What This Scenario Does
Triggers on high/medium-score leads, analyzes lead value with AI, generates personalized reactivation strategy, and sends via optimal channel.

## ⚠️ IMPORTANT: Requires Lead Score Field

**Airtable must have**:
- `Lead Score` field (number type)
- `Engagement History` field (text type, optional)

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 4A-E - Advanced Reactivation with Scoring.blueprint.json`

2. **Configure Module 1: Airtable Trigger**
   - **Base**: Your Airtable base
   - **Table**: Your Airtable table
   - **Formula**: `AND({Do Not Contact} = 0, {Lead Score} >= 50, {Last Out Reach} < TODAY() - 21, {Reply Received} = 0)`
   - **Max Records**: 10
   - Click "OK"

3. **Configure Module 2: Router (Score Routing)**
   - **Route**: Switch
   - **Cases**:
     - Case 1: `{{1.Lead Score}} >= 75` (high priority)
     - Case 2: `{{1.Lead Score}} >= 50 AND {{1.Lead Score}} < 75` (medium priority)
   - Click "OK"

4. **Configure Modules 3, 4: OpenAI (Per Priority)**
   - Module 3: High-score analysis and strategy
   - Module 4: Medium-score analysis and strategy
   - **Connection**: Your OpenAI connection
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **Input**: Verify prompts include lead score and engagement history
   - Click "OK"

5. **Configure Module 5: Parse JSON**
   - **JSON**: Conditional: `{{IF({{1.Lead Score}} >= 75, {{3.text.output[0].content[0].text}}, {{4.text.output[0].content[0].text}})}}`
   - **Type**: AI JSON
   - Click "OK"

6. **Configure Module 6: Router (Channel Selection)**
   - **Route**: If/Else
   - **Filter**: `{{5.best_channel}} = "email"`

7. **Configure Module 7: Google Email Send** (If path)
   - **To**: `{{1.Contact Email}}`
   - **Subject**: `{{5.subject}}`
   - **Content**: HTML with priority and strategy info
   - Click "OK"

8. **Configure Module 8: Twilio Create Message** (Else path - REQUIRES MANUAL SETUP)
   - Add Twilio module manually
   - **To**: `{{1.Contact Phone}}`
   - **Body**: `{{5.sms_message}} Reply STOP to opt out.`

9. **Configure Module 9: Airtable Update**
   - **Record ID**: `{{1.id}}`
   - **Email Campaign**: `reactivation_scored_{{5.priority}}`
   - **Last Out Reach**: `{{now}}`
   - **Status**: `reactivation_scored_sent`
   - **Notes**: Include analysis and strategy
   - Click "OK"

10. **Test the Scenario**
    - Create test leads with Lead Score values
    - Run scenario
    - Verify priority-based messaging

---

# 📓 SCENARIO 4A-F - Reactivation Analytics & Reporting

## What This Scenario Does
Aggregates reactivation campaign data from last 30 days, analyzes performance with AI, and generates comprehensive analytics report via email.

## ⚠️ IMPORTANT: Requires Schedule Module

**Replace webhook with Schedule module** for automated daily/weekly reports.

## Import Steps

1. **Import the Blueprint**
   - Upload `Scenario 4A-F - Reactivation Analytics & Reporting.blueprint.json`

2. **Replace Webhook with Schedule Module** (CRITICAL)
   - **Delete Module 1** (Webhook)
   - Click "+" → Search "Schedule"
   - Add **"Schedule"** trigger
   - **Schedule**: Daily or weekly (recommended: weekly on Monday)
   - Connect to Module 2

3. **Configure Module 2: Airtable Search (All Reactivations)**
   - **Connection**: Your Airtable connection
   - **Base**: Your Airtable base
   - **Table**: Your Airtable table
   - **Formula**: `AND({Email Campaign} CONTAINS "reactivation", {Last Out Reach} >= TODAY() - 30)`
   - **Max Records**: 500
   - Click "OK"

4. **Configure Module 3: Airtable Search (Replies)**
   - **Connection**: Your Airtable connection
   - **Formula**: `AND({Email Campaign} CONTAINS "reactivation", {Last Out Reach} >= TODAY() - 30, {Reply Received} = 1)`
   - **Max Records**: 500
   - Click "OK"

5. **Configure Module 4: Airtable Search (Bookings)**
   - **Connection**: Your Airtable connection
   - **Formula**: `AND({Email Campaign} CONTAINS "reactivation", {Last Out Reach} >= TODAY() - 30, {Meeting Booked} = 1)`
   - **Max Records**: 500
   - Click "OK"

6. **Configure Module 5: OpenAI Analytics**
   - **Connection**: Your OpenAI connection
   - **Model**: `gpt-4o`
   - **Format**: JSON object
   - **Input**: Verify prompt includes all metrics (sent, replies, bookings, rates)
   - Click "OK"

7. **Configure Module 6: Parse JSON**
   - **JSON**: `{{5.text.output[0].content[0].text}}`
   - **Type**: AI JSON
   - Click "OK"

8. **Configure Module 7: Google Email Send**
   - **Connection**: Your Gmail connection
   - **To**: Your email address (e.g., `your-email@domain.com`)
   - **Subject**: `📊 Reactivation Campaign Analytics - {{now}}`
   - **Content**: HTML report with metrics, insights, recommendations
   - **Body Type**: Raw HTML
   - Click "OK"

9. **Test the Scenario**
    - Run scenario manually
    - Verify report email received
    - Check metrics accuracy

---

## 📋 General Configuration Tips

### Airtable Field Setup
Ensure these fields exist in your Airtable base:
- ✅ `Contact Email` (Email type)
- ✅ `Contact Phone` (Phone number type)
- ✅ `Contact Full Name` (Single line text)
- ✅ `Contact Role` (Single line text)
- ✅ `Company` (Single line text)
- ✅ `Industry` (Single line text)
- ✅ `Status` (Single select with options: `cold_30d`, `no_reply_14d`, `no_show`, `reactivation_sent`, etc.)
- ✅ `Last Out Reach` (Date)
- ✅ `Reply Received` (Checkbox)
- ✅ `Meeting Booked` (Checkbox)
- ✅ `Do Not Contact` (Checkbox)
- ✅ `Email Campaign` (Single line text)
- ✅ `Notes` (Long text)
- ✅ `Reactivation Stage` (Single select: `stage_1`, `stage_2`, `stage_3`, `completed`) - For Scenario 4A-D
- ✅ `Lead Score` (Number) - For Scenario 4A-E
- ✅ `Engagement History` (Long text) - Optional for Scenario 4A-E

### Twilio Setup (For SMS Scenarios)
See `TWILIO_MODULE_SETUP.md` for detailed Twilio configuration.

### Testing Best Practices
1. **Start with Test Data**: Create test leads in Airtable that match trigger criteria
2. **Run Manually First**: Use "Run once" to test before enabling schedule
3. **Check Each Module**: Verify data flows correctly through each step
4. **Verify Output**: Check email/SMS received, Airtable updated correctly
5. **Monitor Costs**: Track OpenAI API usage and Twilio SMS costs

---

**Last Updated**: 2025-01-XX  
**Package**: Package 4A - Lead Reactivation Suite

