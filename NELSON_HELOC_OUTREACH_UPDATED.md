# ✅ NELSON HELOC OUTREACH - BLUEPRINT UPDATED

## 🔄 CHANGES MADE

### **1. Scenario Name**
- Changed from: "scenario b"
- Changed to: "Nelson HELOC Outreach"

### **2. Airtable Trigger Filter**
- Added filter: `{Status} = 'new'`
- Only triggers for new leads (prevents duplicate emails)

### **3. OpenAI Prompt (Module 4)**
- **Updated to HELOC-focused:**
  - Personalizes for Home Equity Line of Credit services
  - Mentions location (city/state) for HELOC relevance
  - Focuses on home equity benefits
  - Includes Nelson's signature and contact info
  - Keeps it under 120 words

### **4. Email Module (Module 10)**
- **Recipient:** Changed to `{{1.`Contact Email`}}` (dynamic)
- **Subject:** "Unlock Your Home Equity - HELOC Opportunities for [City] Homeowners"
- **Content:** 
  - Uses OpenAI output: `{{4.text.output}}`
  - Includes HELOC signup button/link
  - Includes Nelson's signature and contact info
  - Professional HTML formatting

### **5. Airtable Update (Module 12)**
- **Email Campaign:** `heloc_initial_outreach`
- **Status:** `emailed`
- **Last Out Reach:** `{{now}}`
- **Next Step:** `Initial Email`

---

## 📋 BLUEPRINT FLOW

```
1. Airtable Watch Records (Status = "new")
   ↓
2. OpenAI Personalize HELOC Email
   ↓
3. Google Email Send
   → To: {{1.`Contact Email`}}
   → Subject: HELOC-specific
   → Content: Personalized + Signup Link
   ↓
4. Airtable Update Record
   → Status: "emailed"
   → Email Campaign: "heloc_initial_outreach"
   → Last Out Reach: current date
   → Next Step: "Initial Email"
```

---

## 🔧 CONFIGURATION NEEDED

### **Module 10 (Google Email):**
1. **From Address:** Set to `nmorales@nexamortgage.com` (or select from dropdown if connected)
2. **To:** Already set to `{{1.`Contact Email`}}`
3. **Subject:** Already configured
4. **Content:** Already configured with HELOC template

### **Module 4 (OpenAI):**
- Already configured with HELOC-specific prompt
- Uses `chatgpt-4o-latest` model
- Outputs personalized email content

### **Module 1 (Airtable Trigger):**
- Filter: `{Status} = 'new'` (only new leads)
- Watches: "Last Modified Time"
- Max Records: 10

---

## ⚠️ IMPORTANT NOTES

1. **Referral Link:**
   - Currently uses static link: `https://axenmortgageheloc.com/account/heloc/register-v2?referrer=55ac77e7-8bb0-48c5-92a8-65960f3efe42`
   - If you want to use individual referral links from Airtable, add a field to the trigger and use `{{1.referral_link}}` if it exists

2. **Email Filtering:**
   - Only sends to leads with Status = "new"
   - Make sure leads have valid email addresses

3. **OpenAI Output:**
   - Uses `{{4.text.output}}` to get the email body
   - If this doesn't work, try `{{4.output}}` or check Module 4's output bundle

4. **Gmail Connection:**
   - Make sure `nmorales@nexamortgage.com` is connected in Make.com
   - Google Email module needs proper OAuth connection

---

## 🧪 TESTING

1. **Create a test lead in Airtable:**
   - Status = "new"
   - Contact Email = your test email
   - Contact Full Name = test name
   - Location City = test city

2. **Manually trigger or wait for watch:**
   - Scenario should trigger automatically

3. **Check email:**
   - Verify personalized content
   - Verify HELOC signup link works
   - Verify signature

4. **Check Airtable:**
   - Status should be "emailed"
   - Email Campaign should be "heloc_initial_outreach"
   - Last Out Reach should be today's date

---

## 📝 CUSTOMIZATION OPTIONS

### **To use individual referral links from Airtable:**
1. Add "Referral Link" field to Module 1's watched fields
2. Change email content button link from static to: `{{1.`Referral Link`}}`

### **To add more personalization:**
- Update OpenAI prompt in Module 4 to include more lead fields
- Add more variables to email template

### **To change email subject:**
- Update Module 10's subject line
- Or make it dynamic based on lead data

---

**The blueprint is ready! Just make sure:**
- ✅ Gmail connection is set up for `nmorales@nexamortgage.com`
- ✅ OpenAI connection is working
- ✅ Airtable connection is configured
- ✅ Test with a new lead first!

