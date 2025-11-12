# 📧 HELOC Outreach Scenario - Planning Document

## 🎯 SCENARIO PURPOSE

Create an automated outreach scenario that:
1. **Reads leads** from Airtable (same table as lead capture)
2. **Sends personalized outreach** with Nelson's HELOC signup links
3. **Tracks outreach** in Airtable (updates status, dates, etc.)
4. **Uses referral links** already stored in the contact table

---

## 📋 INFORMATION NEEDED FROM YOU

### **1. Outreach Channel**
- [ ] Email (via Gmail/SendGrid/Mailchimp?)
- [ ] SMS (via Twilio?)
- [ ] LinkedIn Messages (via PhantomBuster/Phantombuster?)
- [ ] Multiple channels?

### **2. Nelson's Contact Information**
- **Email From Address:** ________________
- **Email Signature:** ________________
- **Phone Number:** ________________
- **LinkedIn Profile:** ________________

### **3. HELOC Signup Links**
- **Referral Link Format:** (I see `referral_link` field in table)
  - Current format: `https://axenmortgageheloc.com/account/heloc/register-v2?referrer=55ac77e7-8bb0-48c5-92a8-65960f3efe42`
  - Is this correct? Should each lead get unique link?

### **4. Email/SMS Content**
- **Subject Line Template:** ________________
- **Email Body Template:** ________________
- **SMS Message Template:** ________________
- **Personalization Fields:** (First Name, Property City, etc.)

### **5. Lead Filtering Criteria**
- **Which leads to contact?**
  - [ ] Status = "new"
  - [ ] Status = "new" OR "emailed" (follow-ups)
  - [ ] All leads
  - [ ] Custom filter: ________________

- **Exclusions:**
  - [ ] Skip if "Reply Received" = true
  - [ ] Skip if "Email Campaign" already sent
  - [ ] Skip if no email address
  - [ ] Custom: ________________

### **6. Send Schedule**
- [ ] Send immediately when lead is added
- [ ] Send on schedule (daily batch)
- [ ] Send based on Airtable filter/view
- [ ] Manual trigger

### **7. Tracking Requirements**
- **Update Airtable fields:**
  - [ ] Status → "emailed"
  - [ ] Last Out Reach → current date
  - [ ] Email Campaign → campaign name
  - [ ] Next Step → "Initial Email" or "Follow Up 1"
  - [ ] Other: ________________

---

## 🔄 PROPOSED SCENARIO FLOW

### **Option A: Email Outreach**
```
1. Airtable: Watch for New Records (or Search Records)
   ↓
2. Router: Filter Leads (Status = "new", has email, etc.)
   ↓
3. OpenAI: Personalize Email Content
   (Uses: first_name, property_city, referral_link, etc.)
   ↓
4. Email Service: Send Personalized Email
   (Gmail/SendGrid/Mailchimp)
   ↓
5. Airtable: Update Record
   (Status → "emailed", Last Out Reach → now, etc.)
```

### **Option B: SMS Outreach**
```
1. Airtable: Watch for New Records
   ↓
2. Router: Filter Leads (Status = "new", has phone, etc.)
   ↓
3. OpenAI: Personalize SMS Message
   ↓
4. Twilio: Send SMS
   ↓
5. Airtable: Update Record
```

### **Option C: Multi-Channel Sequence**
```
1. Airtable: Watch for New Records
   ↓
2. Router: Filter Leads
   ↓
3. Router: Channel Selection
   ├─→ Email Path
   │   ├─→ OpenAI Personalize
   │   ├─→ Send Email
   │   └─→ Update Airtable
   └─→ SMS Path
       ├─→ OpenAI Personalize
       ├─→ Send SMS
       └─→ Update Airtable
```

---

## 📊 AIRTABLE FIELDS TO USE

From your working blueprint, these fields are available:
- `Contact Email` - For email outreach
- `Contact Phone` - For SMS outreach
- `First Name` - Personalization
- `Property City` - Personalization
- `Location City` - Personalization
- `Referral Link` - Signup link
- `Status` - Filter and update
- `Last Out Reach` - Track when contacted
- `Email Campaign` - Track campaign name
- `Next Step` - Track sequence position

---

## 🎨 CONTENT TEMPLATE STRUCTURE

**Email Template Placeholders:**
```
Subject: [PERSONALIZED SUBJECT]

Hi {{first_name}},

[PERSONALIZED GREETING based on property_city]

[HELOC VALUE PROPOSITION]

Sign up here: {{referral_link}}

Best regards,
Nelson Morales
AXEN MORTGAGE / NEXA MORTGAGE LLC
[Contact Info]
```

**SMS Template Placeholders:**
```
Hi {{first_name}}! Nelson here from AXEN MORTGAGE. 
Ready to unlock your home equity? 
Sign up: {{referral_link}}
```

---

## ⚙️ CONFIGURATION CHECKLIST

- [ ] Email service connection (Gmail/SendGrid/etc.)
- [ ] SMS service connection (Twilio/etc.)
- [ ] OpenAI connection (for personalization)
- [ ] Airtable connection (same as lead capture)
- [ ] Personalization prompts/templates
- [ ] Lead filtering logic
- [ ] Update tracking logic
- [ ] Error handling (email bounces, etc.)

---

## 📝 NEXT STEPS

**Please provide:**
1. ✅ Outreach channel preference
2. ✅ Nelson's contact info (email, phone, signature)
3. ✅ Email/SMS templates/content
4. ✅ Lead filtering criteria
5. ✅ Send schedule preference
6. ✅ Any branding/messaging guidelines

Once I have this, I'll build the complete blueprint! 🚀

