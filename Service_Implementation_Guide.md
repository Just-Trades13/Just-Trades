## AI Automation Services – Implementation & Operations Guide

Audience: Agency owner and implementers. Goal: deploy fast, show ROI, charge monthly maintenance.

Table of Contents
- Core Offer & Packaging
- Onboarding & Compliance Accounts
- Airtable Data Design & Privacy
- Services 1–6 (detailed)
- Service Pricing Reference (market ranges)
- Make Patterns, Errors, Observability
- Make Blueprint Walkthroughs (scenario b, scenario c, scenario A)
- Deliverability & Legal
- Security, Retention, Backups
- QA Playbooks, Runbooks
- Niche Playbooks (HVAC, Med Spa, Roofing)
- Sales Ops (Pilot, SOW, Onboarding Forms)
- SLAs, SLOs, Reporting
- 30/60/90 Growth Roadmap

---

## Day-1 Quickstart (All Services)

Preflight Intake Form (copy/paste to form tool)
- Client Legal Name
- Primary Contact (name, email, phone)
- Website URL(s)
- Business Hours & Service Areas
- Base Pricing Ranges
- Top 15 FAQs (bulleted)
- Google Workspace Admin Email (for Calendar/Gmail auth)
- Domain DNS Access? (SPF/DKIM/DMARC for email; script for chat)
- Calendly/Calendar Link(s)
- Compliance: opt-in method, quiet hours, opt-out policy
- Escalation Contacts (ops, owner)

Accounts & Approvals Checklist
- Twilio
  - Upgrade account + payment method
  - Trust Center: Brand & Campaign approved (Customer Care / Conversational)
  - Buy SMS+Voice number; create Messaging Service; assign campaign
- Email
  - SPF, DKIM, DMARC published; Gmail OAuth tested from Make
- OpenAI
  - API key created; hard usage limits set; stored in Make vault
- Calendar
  - Google OAuth (read/write), dedicated service calendar created
- Airtable
  - Base duplicated from template; API connection tested

Environment Setup
- Duplicate Airtable base `Leads Manager AI CRM` + `Message Logs`
- Create Make folder per client; add Scenarios: MCTB, AI SMS, Chat Intake, Reactivation, Analytics Sync
- Provision Twilio number + Studio Flow; set status callbacks/webhooks to Make

Go-Live Order of Operations (48 hours)
- Day 1: Twilio (A2P + number + Studio), Make (MCTB + AI SMS), Calendar connection, Airtable logs
- Day 2: Chat widget install + training; Reactivation small cohort; Analytics dashboard; smoke tests

---

## 30-Minute Smoke Test Scripts (Per Service)

Missed-Call Text-Back
- Scenario: call number; do not answer
- Expect: SMS within 10s; if voicemail left, receive recording link
- Verify: `Message Logs` appended; Airtable `Status` updated; no double-send on replays

AI SMS Concierge
- Send 10 FAQ messages, 3 off-topic, 1 STOP
- Expect: concise answers, CTA for booking; STOP honored; DNC flagged
- Verify: logs, booking link works; rate-limit respected

Website Chat + Booking
- Open 3 pages; engage; ask 5 FAQs; book a slot
- Expect: correct answers; booking created; lead captured
- Verify: lead in Airtable; calendar hold

Lead Reactivation
- Trigger small sample (≤10 leads)
- Expect: sends within window; STOP honored; replies logged
- Verify: fields updated; zero sends to DNC

Voice Receptionist
- Call; test greeting, barge-in, route to booking or SMS summary
- Expect: latency <1.8s; transcript saved; booking path works

Analytics Dashboard
- Compare daily counts with Airtable raw
- Expect: data freshness <24h; funnel sums match

---

## Importable Assets & Templates

Twilio Studio Flow (JSON template)
{
  "description": "MCTB with SMS + voicemail",
  "states": [
    {"name":"Trigger","type":"trigger","Transitions":[]},
    {"name":"Connect","type":"connect-call-to","properties":{"timeout":"25","record":"false"},"transitions":{"failed":"Send_Missed_SMS","noAnswer":"Send_Missed_SMS","busy":"Send_Missed_SMS"}},
    {"name":"Send_Missed_SMS","type":"send-message","properties":{"from":"{{flow.twilio_messaging_service_sid}}","to":"{{trigger.call.From}}","body":"Hi {{flow.business_name}}, sorry we missed your call. How can we help? Reply STOP to opt out."},"transitions":{"next":"Record_VM"}},
    {"name":"Record_VM","type":"record-voicemail","properties":{"maxLength":"60","trimSilence":"true"},"transitions":{"recordingComplete":"SMS_VM_Link"}},
    {"name":"SMS_VM_Link","type":"send-message","properties":{"from":"{{flow.twilio_messaging_service_sid}}","to":"{{trigger.call.From}}","body":"Thanks for the message—here’s the recording: {{widgets.Record_VM.RecordingUrl}}"}}
  ]
}

Email Templates (HTML snippets)
- Initial outreach (90–120 words), Follow-up (value add), Booking CTA button, Brand footer, Unsubscribe instruction

SMS Templates
- MCTB: “Hi {{Business}}, sorry we missed your call. How can we help? Reply STOP to opt out.”
- Reactivation: “Still interested in {{service}} this week? Happy to help. Reply STOP to opt out.”
- Help/STOP responses (compliance)

Make Module Templates
- Twilio Send Message: From = Messaging Service SID; To = {{webhook.body.From}}; Body = {{openai.output}}
- OpenAI Create Response: Model = gpt-4o; Temperature = 0.3; Max tokens = 300; Input = user body + business context
- Airtable Upsert: Match by phone/email; map logs with MessageSid/CallSid

---

## Role-Based SOPs

Implementer SOP
- Follow Day-1 Quickstart; use smoke tests; escalate failures with payload snapshots

Deliverability SOP
- Weekly: check Twilio error codes; reduce links; keep 1 URL; consistent template; validate A2P

Security SOP
- Store all API keys in Make vault; least-privilege OAuth; rotate keys quarterly; export data on termination

Support SOP
- SLA triage: critical (broken sends), major (deliverability drop), minor (content edits); status updates to client within SLA

---

## Troubleshooting Decision Trees

SMS not delivering
- Check delivery receipts (Twilio 30003/30007) → Simplify copy → Remove links → Verify A2P status → Distribute senders

OpenAI slow/failing
- Increase timeout → Retry/backoff → Fallback prompt → Temporary canned responses

Airtable API rate limits
- Batch writes → Limit per run → Add filters/views → Off-peak scheduling

Email in spam
- Authenticate domain → Reduce images/links → Change subject/snippets → Warmup gradually

### Core Offer (outcome-first)
- Turn missed calls and inbound interest into booked appointments in <5 minutes via SMS/chat/voice.
- Stackable modules: start with Missed-Call Text-Back, add AI SMS Concierge, Website Chat + Booking, Lead Reactivation, Voice Agent, Analytics.

### Pricing & Packaging
- Starter ($299–$499/mo + $500 setup): Missed-Call Text-Back + AI SMS FAQ, Airtable logging.
- Growth ($750–$1,500/mo + $1,000 setup): Starter + Website Chat + Calendar booking + Lead Reactivation.
- Pro ($2,000–$4,000/mo + $2,500 setup): Growth + Voice Agent + Analytics dashboard + priority support.
- Pilot (7–14 days): $0 setup, success = ≥5 qualified replies or ≥2 bookings. Cancel anytime during pilot = no charge.

### Onboarding Checklist (copy to form)
- Legal business name, website URL, logo.
- Business hours, service areas, price ranges, top FAQs (10–20), compliance notes.
- Google Calendar link (or Calendly), booking windows, team notification emails/phones.
- CRM preference (default Airtable). DNS access (for chat widget) if needed.

### Compliance & Accounts (detailed)
- Twilio A2P 10DLC
  - Trust Center → Register Brand (legal entity, EIN, address, website, contact).
  - Create Campaign: Customer Care / Conversational; add sample messages with STOP/HELP.
  - After approval, assign campaign to a Messaging Service; add your number(s) to Sender Pool.
- Email (Gmail/Workspace)
  - Ensure SPF, DKIM, DMARC on domain; avoid free @gmail.com senders for production.
  - Connect via Make “Google Email” with OAuth (least scopes) or via SMTP/SendGrid.
- OpenAI
  - Create API key; set hard usage limits; store in Make’s vault; select `gpt-4o` or `chatgpt-4o-latest`.
- Calendars
  - Use Google Calendar OAuth for read/write; restrict to a dedicated service calendar if possible.

### Airtable Schema (Base: `Leads Manager AI CRM`, Table: `Leads`)
- Text: Lead ID, Company, Domain, Notes, Industry, Contact Full Name, Contact Role, Contact Email, Contact Phone, Contact LinkedIN, Location City, Location State, Source, UTM List ID, Next Step, Meeting Link, Email Campaign.
- Number: Employee Count, Pipeline Value.
- Checkbox: Reply Received, Meeting Completed, Do Not Contact.
- Date (no time): Acquired At, Last Out Reach. Date/time: Last Modified Time (Airtable field type).
- Multiple select: Tags.
- Optional logs table: `Message Logs` (lead ref, direction, channel, body, SID, status, timestamp).

#### ID Strategy & Privacy
- Primary key: Airtable record ID; match by normalized phone (E.164) and/or email.
- Store `MessageSid`/`CallSid` on `Message Logs` for traceability.
- Minimize PII: store only name/phone/email; redact sensitive text before sending to OpenAI.

### Shared Stack
- Messaging/Voice: Twilio (A2P 10DLC for US long code). Number: SMS+Voice.
- Orchestration: Make (webhooks, Twilio, OpenAI, Airtable, Gmail).
- AI: OpenAI `gpt-4o` or `chatgpt-4o-latest`.
- Data: Airtable (and Google Looker Studio for dashboards).
- Website chat: Tidio/Intercom/Chatbase/HighLevel (pick one per client).

---

## Service 1: Missed-Call Text-Back (MCTB)
Outcome: When a call is missed, auto-SMS the caller, capture intent, and book or route.

Stack
- Twilio phone number (SMS+Voice) attached to a Messaging Service (A2P-approved, STOP/HELP handling).
- Twilio Studio Flow for voice leg; Make optional for logging/analytics.

Prereqs
- Twilio account upgraded + payment method.
- Trust Center: A2P Brand + Campaign (use “Customer Care/Conversational”), sample templates with opt-out.

Setup (Twilio)
1. Buy number: Phone Numbers → Buy → Capabilities SMS+Voice.
2. Messaging Service: Messaging → Create → add number to Sender Pool; assign A2P Campaign.
3. Inbound settings: Incoming Messages → Webhook (from Make) or leave none if pure Studio handles it.
4. Studio Flow: Incoming Call → Connect (ring team 20–30s). Timeout branch: Send Message to `{{trigger.call.From}}` via Messaging Service; Record Voicemail (60s); follow-up SMS with `{{widgets.record_voicemail.RecordingUrl}}`.
5. Assign Flow: Number → Voice → A call comes in → Studio Flow (MCTB).

Setup (Make – optional)
1. Webhooks → Custom webhook (name: `twilio_voice_status`), capture call events (status, From).
2. Twilio → Send a message: to `From`, body = missed-call SMS template (see below) if status ∈ [no-answer,busy,failed].
3. Airtable → Update `Leads` by Contact Phone; set Status=`called_missed`, Last Out Reach=`now`, log in `Message Logs`.

Status Callback Mapping (Twilio → Make)
- Fields: `From`, `To`, `CallSid`, `CallStatus`, `Timestamp`.
- Filter: trigger SMS when `CallStatus` in [no-answer, busy, failed]. Use `CallSid` to ensure idempotency.

Templates
- Initial SMS: “Hi {{Business}}, sorry we missed your call. How can we help? Reply STOP to opt out.”
- Voicemail sent: “Thanks for the message—here’s the recording: {{url}}. Prefer to text here?”

QA
- Call and don’t answer → receive SMS within 10s; leave voicemail → receive link; logs created.

KPIs
- % missed calls captured by SMS, replies started, bookings, opt-outs.

Maintenance
- Review delivery errors weekly; adjust timeout and SMS copy; rotate numbers if needed.

Compliance
- A2P-approved templates; STOP/UNSTOP/HELP implemented; quiet hours if required.

Pricing & Packaging (market)
- Setup: $0–$500 (often waived for pilot).
- Monthly: $299–$499 Starter tier common (aligned with “3 Simple Automations…” ref).
- Upsell path: add AI SMS Concierge (+$200–$500/mo) and Reactivation (+$200–$400/mo).

---

## Service 2: AI SMS Concierge
Outcome: Two-way SMS with AI to answer FAQs, qualify, and book on calendar.

Stack
- Twilio Messaging Service → Make → OpenAI → Twilio reply; Airtable logging.

Setup (Make)
1. Webhooks → Custom (`twilio_inbound_sms`); method POST, content x-www-form-urlencoded.
2. Router: If Body matches `STOP|UNSUBSCRIBE` (case-insensitive):
   - Airtable → mark Do Not Contact; Twilio → send compliance reply; STOP further messages.
3. OpenAI → Create model response:
   - Input: user Body + business FAQ context (Airtable fields/website scrape); instruction to keep answers short and offer booking CTA when appropriate.
4. Twilio → Send message: From=Messaging Service SID, To=`{{1.body.From}}`, Body=AI output.
5. Airtable → Upsert by Contact Phone; store inbound/outbound in `Message Logs`, update `Last Out Reach`.

Twilio Inbound Payload (reference)
- `Body`, `From`, `To`, `MessagingServiceSid`, `MessageSid`, `NumMedia` (if MMS)
- Persist `MessageSid` to prevent duplicate processing.

Prompt Skeleton
- System: “You are a helpful, concise SMS assistant for {{Business}}. Answer in ≤320 chars. If user intent includes booking, propose next 2 time slots from {{Calendar}}. If unsure, ask 1 clarifying question.”

Booking Options
- Calendar link (fastest): append `?source=sms` for attribution.
- API booking: Make step creates event after AI collects name/phone/email and two candidate times; SMS back confirmation.

QA
- Text number with 5–10 FAQs; verify concise, correct answers; test booking CTA and STOP.

KPIs
- First response time, conversations started, bookings, opt-out rate, CSAT (optional keyword-based).

Maintenance
- Weekly transcript review; add FAQs; adjust prompt; throttle if carrier warnings.

Pricing & Packaging (market)
- Setup: $500–$1,200 (prompt + FAQ build + testing).
- Monthly: $500–$1,200 (ref: “5 More Automations…” for conversational bots; “What 50 BO…” suggests $500–$1,000/mo typical).
- Add-ons: API booking (+$100–$300/mo), extra channels (WhatsApp/Facebook) (+$100–$200/mo).

---

## Service 3: Website Chat Widget + Booking
Outcome: 24/7 site chat answers FAQs, captures leads, books meetings.

Stack
- Widget (Tidio/Intercom/Chatbase/HL) + Make or vendor-native automations; Google Calendar or Calendly.

Setup
1. Install widget snippet on site (or inject via GTM).
2. Train on website URLs/FAQ doc; configure intents: quote request, schedule, directions, hours.
3. Booking: connect to Calendar; limit to business hours; capture name/email/phone before booking.
4. Lead sink: Send conversations/leads to Airtable `Leads` and `Message Logs` via Make or native webhook.

QA
- Test 10 FAQs; attempt booking; verify calendar holds and Airtable records.

KPIs
- Chat engagement rate, lead capture rate, bookings, time-to-first-response.

Maintenance
- Update knowledge base monthly; rotate proactive prompts; A/B test greeting.

Pricing & Packaging (market)
- Setup: $500–$2,000 (widget install + training + booking integration).
- Monthly: $350–$1,200 (ref: “What 50 BO…” chat/website bots); higher if multi-channel and SLAs.

---

## Service 4: Lead Reactivation (SMS/Email)
Outcome: Revive cold leads to book appointments with minimal human time.

Stack
- Airtable segmented lists → Make sequences → Twilio SMS / SendGrid (or Gmail) → OpenAI personalization.

Setup
1. Segment: In Airtable create views: `Cold_30d`, `NoReply_14d`, `NoShow`, etc.
2. Make: Scheduler (daily) → List records from each view (cap per run) →
   - OpenAI: craft short, human-sounding message referencing last touch.
   - Twilio/Email: send with opt-out.
   - Update Airtable: Last Out Reach, Status, log message.
3. Replies: Webhook for inbound SMS or email → mark `Reply Received=1`, notify team.

Templates
- “Still interested in {{service}} for {{property/need}}? Happy to help this week. Reply STOP to opt out.”

KPIs
- Reactivation response rate, bookings recovered, revenue per reactivated lead.

Maintenance
- Rotate copy monthly; respect quiet hours; suppress DNC segment.

Pricing & Packaging (market)
- Setup: $0–$500 (list segmentation + sequences).
- Monthly: $200–$600 (ref: both “What 50 BO…” and “3 Simple Automations…” show this as an easy add-on).

---

## Service 5: AI Voice Receptionist (Advanced)
Outcome: Answer calls with natural voice, intake, route, or book.

Stack
- Twilio Voice media streams + VAPI/ElevenLabs/OpenAI STT/TTS (or Twilio Voice Intelligence), Make for logging.

Setup (high-level)
1. Choose platform (VAPI.ai recommended for speed) and voice (ElevenLabs/Play.ht).
2. Twilio → number → Voice webhook to platform endpoint.
3. Define call flow: greeting → FAQ/intent → booking/route → SMS summary.
4. Logging: post-call transcript + disposition to Airtable.

KPIs
- Call answer rate, successful intents, booked calls, handoff rate.

Maintenance
- Weekly transcript tuning; add intents; ensure latency <1.5s.

Compliance
- Add “This call may be handled by an AI assistant” where required.

Pricing & Packaging (market)
- Setup: $2,500–$10,000 (ref: “What 50 BO…” + “16 Insane…” voice agents; complexity-dependent).
- Monthly: $300–$1,200 (maintenance, prompt tuning, analytics, minutes not included).

---

## Service 6: Analytics Dashboard
Outcome: Clear ROI view for owners (calls → chats → bookings → revenue).

Stack
- Looker Studio + Google Sheets or direct Airtable connector.

Setup
1. Feed: Export `Message Logs`, `Leads`, bookings to Sheets (Make scheduled sync) or use connectors.
2. Build views: funnel, response time, daily bookings, opt-outs, campaign performance.
3. Share with viewer-only link; add filters by date, campaign, channel.

KPIs
- Response time trend, booking rate by channel, ROI snapshot.

Maintenance
- Validate data freshness weekly; adjust charts per client feedback.

Pricing & Packaging (market)
- Setup: $3,000–$5,000 (ref: “What 50 BO…” analytics dashboards).
- Monthly: $300–$600 (data freshness checks, enhancements).

---

## Make Scenario Notes (quick reference)
- Triggers: Webhooks (Twilio inbound SMS, status callbacks), Schedulers (cron), Airtable Watch Records.
- Best practices: cap operations/run, add filters, log all fails to an Airtable `Errors` table.
- OpenAI: temperature 0.2–0.5; keep responses concise; never send PII back.

### Error Handling Patterns
- Retry policy: 3 attempts with exponential backoff (1s, 2s, 4s). On final failure, write to Airtable `Errors` with payload snapshot and notify Slack/email.
- Idempotency: maintain a hash of (`MessageSid` or `CallSid` + action) in Airtable to avoid double sends.
- Throttling: insert Sleep 1000ms between Twilio sends per number; prefer Messaging Service to distribute load across numbers.

### Observability
- `Health` table: date, scenario name, run count, success count, fail count, avg latency.
- Heartbeat: scheduled scenario writes timestamp hourly; alert if stale > 2 hours.

### Module Field Maps (examples)
Twilio → Send a message
- From: Messaging Service SID (preferred) or specific number
- To: {{webhook.body.From}}
- Body: {{openai.output}} or static template

OpenAI → Create model response
- Model: gpt-4o / chatgpt-4o-latest
- Input: JSON or text combining user message and business context
- Temperature: 0.3–0.4; Max tokens: 200–400

Airtable → Create/Update
- Base: Leads Manager AI CRM
- Table: Leads / Message Logs
- Record: map fields; use phone/email for upsert

---

## Make Blueprint Walkthroughs (scenario b, scenario c, scenario A)

This section shows exactly how to import, reconnect, verify, and QA each scenario. Use it as a training guide for new team members.

### scenario b – Initial Outreach (Airtable → OpenAI → Gmail → Airtable)

Flow overview
- 1) Trigger: Airtable Watch Records (module: `airtable:TriggerWatchRecords`, id: 1)
- 2) OpenAI: Create Model Response (module: `openai-gpt-3:createModelResponse`, id: 4)
- 3) Gmail: Send Email (module: `google-email:sendAnEmail`, id: 10)
- 4) Airtable: Update Record (module: `airtable:ActionUpdateRecords`, id: 12)

Step-by-step
1) Airtable Trigger
   - Connection: your Airtable account
   - Base: `Leads Manager AI CRM`
   - Table: `Leads`
   - Trigger config: Label Field = `Status`, Trigger Field = `Last Modified Time`
   - View: optional, leave blank
   - Formula (recommended to avoid blasting):
     - Example: `AND({Email Campaign} = BLANK(), {Contact Email} != "")`
   - Limit: 10 (safe during early runs)

2) OpenAI – personalized email (id: 4)
   - Model: `chatgpt-4o-latest` (or `gpt-4o` if needed)
   - Input (prompt already provided in blueprint): references fields from step 1, e.g. `{{1.`Contact Full Name`}}`, `{{1.Company}}`, `{{1.Industry}}`, `{{1.`Location City`}}`, `{{1.`Contact Role`}}`
   - Store: true (optional)
   - Background: false
   - Truncation: auto
   - Create conversation: true

3) Gmail – send outbound email (id: 10)
   - Connection: Google Email (your sending identity)
   - To: CHANGE from hardcoded `espam@skillztech.net` → `{{1.`Contact Email`}}`
   - Subject: use variables or OpenAI output; keep <70 chars
   - Body type: `rawHtml`
   - Content: adapt HTML to include company/name; ensure the Calendly URL is yours

4) Airtable – update status (id: 12)
   - Base/Table: same as trigger
   - Record ID: `{{1.id}}`
   - Fields set:
     - `Email Campaign` = `initial outreach`
     - `Last Out Reach` = `{{now}}`
     - `Status` = `emailed`
   - UseColumnId: false, Typecast: false

Field references (common)
- Lead fields used by b: `Contact Full Name`, `Company`, `Industry`, `Location City`, `Contact Role`, `Contact Email`

QA checklist
- Run once with 1 record (your own test lead):
  - OpenAI output produced (short, under 100 words)
  - Email delivered to your inbox (not spam)
  - Airtable updated (`Email Campaign=initial outreach`, `Last Out Reach` set, `Status=emailed`)
- Set a formula filter to avoid reprocessing the same lead

Notes
- The blueprint JSON shows module ids (1,4,10,12) and maps. If mapping breaks after import, re-pick fields with Make’s variable picker.

---

### scenario c – Follow-up (Airtable → OpenAI → Gmail → Airtable)

Flow overview
- 1) Trigger: Airtable Watch Records (module: `airtable:TriggerWatchRecords`, id: 2)
- 2) OpenAI: Create Model Response (module: `openai-gpt-3:createModelResponse`, id: 3)
- 3) Gmail: Send Email (module: `google-email:sendAnEmail`, id: 6)
- 4) Airtable: Update Record (module: `airtable:ActionUpdateRecords`, id: 8)

Step-by-step
1) Airtable Trigger (id: 2)
   - Base: `Leads Manager AI CRM`; Table: `Leads`
   - Label Field: `Company`; Trigger Field: `Last Modified Time`
   - Formula (from blueprint):
     - `AND({Last Out Reach} < TODAY() - 5, {Reply Received} = 0, {Email Campaign} = "initial outreach")`
   - Limit: 10

2) OpenAI – follow-up draft (id: 3)
   - Model: `gpt-4o`
   - Input (from blueprint): references company, notes, industry, days since last contact (`{{2.`Last Out Reach`}}` is used as a value in prompt)
   - Keep tone professional, add value/insight, keep Calendly link consistent

3) Gmail – send follow-up (id: 6)
   - To: `{{2.`Contact Email`}}`
   - Subject: references `{{2.`Contact Full Name`}}` or company
   - Body type: `rawHtml`
   - Content: HTML from blueprint; ensure your Calendly link is correct; include sender signature

4) Airtable – update flags (id: 8)
   - Base/Table: same; Record ID: `{{2.id}}`
   - Fields set (as in blueprint):
     - `Email Campaign` (e.g., `follow_up_1`)
     - `Last Out Reach` = `{{2.`Last Out Reach`}}` (you can set to `{{now}}` if desired so next cadence computes from send time)
     - `Status` = `follow_up_sent`

Field references (common)
- Lead fields used by c: `Company`, `Notes`, `Industry`, `Contact Full Name`, `Contact Email`, `Last Out Reach`, `Reply Received`, `Email Campaign`

QA checklist
- Adjust formula window temporarily (e.g., `TODAY()-0`) for testing; then restore to `-5`
- Confirm email received; Airtable marks follow-up; formula prevents immediate re-trigger

---

### scenario A – Reusable Pattern (Template)

Use this skeleton to build new outreach/ops scenarios (e.g., reactivation, appointment reminders):

Flow pattern
- 1) Trigger: Airtable Watch Records (filtered view or formula)
- 2) Enrichment/LLM: OpenAI Create Model Response (optional)
- 3) Channel: Twilio SMS or Gmail Send Email (or both via Router)
- 4) Persistence: Airtable Update/Create logs

Implementation steps
1) Airtable Trigger
   - Base/Table as above, limit 10 during testing
   - Formula examples:
     - Reactivation: `AND({Reply Received}=0, {Last Out Reach} <= TODAY()-14, {Contact Email} != "")`
     - No-shows: `AND({Meeting Completed}=0, {Next Step}="no_show_followup")`
2) OpenAI (optional)
   - Model: `gpt-4o`
   - Prompt: short, value-forward, with 1 CTA; keep ≤320 chars for SMS
3) Channel
   - Twilio SMS: From = Messaging Service SID; To = phone; Body = OpenAI or template
   - Email: To = `Contact Email`; HTML body; include brand footer and opt-out language where applicable
4) Persistence
   - Update `Last Out Reach`, `Status`, optionally increment a counter (e.g., `Follow-up Count`)
   - Append `Message Logs` row (direction, channel, body, timestamp, SID)

QA & safety
- Add max sends per run in Make; throttle rate; respect STOP/DNC
- Test with your personal contact first

---

Troubleshooting (common across all blueprints)
- Variable references show as null: reselect fields via picker after reconnecting connections
- Email lands in spam: authenticate domain (SPF/DKIM/DMARC), reduce links, tighten subject
- Too many records processed: use formula/view filters, limit to 10 while validating

## SMS Compliance Snippets
- HELP: “{{Business}}: We’re here to help. Reply STOP to opt out. Msg&data rates may apply.”
- STOP: honor immediately; mark DNC; return “You’re opted out and won’t receive further messages.”
- Quiet hours: set send windows per client locale.

## Deliverability & Legal (expanded)
- Avoid link shorteners; keep 1 link max; keep messages under ~320 chars.
- Keep consistent sender identity and templates; sudden content shifts can trigger filters.
- Respect TCPA and regional laws; record opt-ins where applicable; maintain suppression lists.

Attribution & UTM
- Append `?source=sms` or `?utm_source=sms&utm_medium=concierge&utm_campaign={{campaign}}` to booking links.
- Log UTM in Airtable `Message Logs` for channel ROI.

## SLAs (internal)
- Response to client requests: <1 business day; critical issues: same day.
- Uptime target (flows): 99% monthly; incident comms within 4 hours.
- Monthly maintenance: copy refresh, FAQ updates, dashboard check, A2P health.

## QA Playbooks (detailed)
MCTB
- Test matrix: no-answer, busy, failed; voicemail present/absent; duplicate prevention; logs persisted.
AI SMS
- 10 FAQ intents, 3 off-topic, 1 profanity filter, STOP/HELP; calendar booking path; DNC flagging.
Chat
- Load on 3 site pages; proactive greet; knowledge gaps; booking creation; lead write to Airtable.
Reactivation
- Segment correctness; send windows; caps; suppression (DNC, opt-outs, recent replies).
Voice
- Greeting, barge-in, disambiguation, transfer; latency under 1.8s; SMS summary.
Analytics
- Data freshness; funnel sums match raw counts; attribution UTM shows in bookings.

## Runbooks
Carrier Filtering
- Check Twilio error codes (30003/30007); simplify copy; remove links; reduce frequency; request A2P review.
OpenAI Degradation
- Switch to cached responses; increase timeout to 30s; if persistent, fallback to rules template.
Airtable API Overuse
- Batch writes; schedule off-peak; add view filters; archive old logs monthly to separate table.

## QA Checklist (before go-live)
- A2P approved and linked; STOP/HELP tested; booking tested; logs created.
- Opt-out honored; quiet hours respected; error paths retried/logged.

## Go-Live Plan (48 hours)
Day 1: Provision Twilio + A2P, attach Messaging Service, build MCTB + AI SMS Concierge, connect Calendar, set logs.
Day 2: Install chat, run reactivation (small batch), create dashboard, live tests with client.

## Weekly Report Template
- Missed calls captured: X | SMS convos: X | Bookings: X | Avg response time: Xs | Opt-outs: X
- Highlights: what worked, what’s next. Issues: deliverability/latency.

## Upsell Roadmap (30/60/90)
- 30: Stabilize SMS flows; confirm ROI; add chat widget.
- 60: Reactivation sequences; add dashboard.
- 90: Add voice agent; expand campaigns; raise to Growth/Pro.

## Niche Playbooks
HVAC
- Priorities: emergency dispatch, same-day slots, maintenance plans.
- Scripts: “We can send a tech today between 2–4pm or 4–6pm. Which works?”
- Reactivation: seasonal tune-ups; filter replacement reminders.

Med Spa
- Priorities: safety/contraindications, consultation booking, before/after guidance.
- Scripts: “We start at $X; exact quote after consult. Would you like Tue 2pm or Wed 10am?”
- Compliance: avoid PHI; use ranges not exact diagnosis language.

Roofing
- Priorities: storm damage, insurance assistance, materials (asphalt/metal), timeline.
- Scripts: “Free on-site estimate. We can come Thu morning or Fri afternoon—what’s best?”
- Reactivation: post-storm neighborhood sweeps.

## Sales Ops Assets
Pilot Terms (client-facing)
- 7–14 days; no setup fee; success criteria: 2+ bookings or 5+ qualified replies; cancel anytime during pilot.

SOW Outline
- Objectives & scope by tier; deliverables; timeline; compliance; data/SLA; termination & data export.

Onboarding Form Fields
- Business details, hours, service areas, base pricing, top FAQs, brand tone, calendar links, escalation contacts, DNS access (if chat).

## Service Pricing Reference (market ranges)
Note: Ranges synthesized from referenced materials; set pricing by complexity and ROI.

- Missed-Call Text-Back: $0–$500 setup; $299–$499/mo (3 Simple Automations)
- AI SMS Concierge (SMS/Website): $500–$1,200 setup; $500–$1,200/mo (5 More Automations; 50 BO)
- Website Chat + Booking: $500–$2,000 setup; $350–$1,200/mo (50 BO)
- Lead Reactivation: $0–$500 setup; $200–$600/mo (50 BO)
- AI Voice Receptionist: $2,500–$10,000 setup; $300–$1,200/mo (50 BO; 16 Insane)
- Analytics Dashboard: $3,000–$5,000 setup; $300–$600/mo (50 BO)

Tiered Packaging (example)
- Starter ($299–$499/mo): MCTB + logs
- Growth ($750–$1,500/mo): Starter + AI SMS + Chat + Booking + Reactivation
- Pro ($2,000–$4,000/mo): Growth + Voice + Analytics + priority SLAs


