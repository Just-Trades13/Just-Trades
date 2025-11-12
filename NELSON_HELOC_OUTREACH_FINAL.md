# ✅ NELSON HELOC OUTREACH - FINAL SETUP

## 🎯 BLUEPRINT UPDATED

The blueprint has been updated with:
1. **Nelson's exact email template** (no AI generation)
2. **Business hours filtering** (Mon-Fri, 9 AM - 5 PM)
3. **First name personalization** (extracted from Contact Full Name)
4. **Direct email sending** (no OpenAI module)

---

## 📋 FLOW STRUCTURE

```
Module 1: Airtable Trigger (Status = 'new')
    ↓
Module 2: Router (Business Hours Check)
    ├─→ Route 1: Business Hours (Mon-Fri, 9 AM - 5 PM)
    │   ├─→ Module 3: Set Variable (first_name)
    │   ├─→ Module 4: Send Email (Nelson's Template)
    │   └─→ Module 12: Update Airtable (Status = 'emailed')
    └─→ Route 2: Outside Business Hours (No Action)
```

---

## 🔧 CONFIGURATION NEEDED

### **1. Router Business Hours Filter**
**Location:** Module 2 → Route 1 Filter

**Current Filter:**
```
{{and(contains(["Mon", "Tue", "Wed", "Thu", "Fri"]; formatDate(now(); "E")); ge(toNumber(formatDate(now(); "HH")); 9); le(toNumber(formatDate(now(); "HH")); 17))}}
```

**What it checks:**
- Weekday is Monday-Friday
- Hour is 9 AM - 5 PM (9-17 in 24-hour format)

**To adjust hours:**
- Change `9` to your start hour (e.g., `8` for 8 AM)
- Change `17` to your end hour (e.g., `18` for 6 PM)
- Timezone: Uses Make.com's server timezone (typically UTC)

---

### **2. Email Template**
**Location:** Module 4 → Content

**Template includes:**
- Personalized greeting: `Hi {{3.first_name}}`
- Nelson's HELOC messaging
- Signup link: `https://axenmortgageheloc.com/account/heloc/register-v2?referrer=55ac77e7-8bb0-48c5-92a8-65960f3efe42`
- Nelson's signature and contact info
- Disclosures and opt-out

**Subject Line:**
```
Unlock Your Home Equity - HELOC Opportunities
```

---

### **3. Airtable Update**
**Location:** Module 12

**Updates:**
- `Status`: "emailed"
- `Email Campaign`: "heloc_initial_outreach"
- `Last Out Reach`: Current timestamp
- `Next Step`: "Initial Email"

---

## ⚠️ IMPORTANT NOTES

### **Business Hours**
- **Current timezone:** Make.com server time (typically UTC)
- **To use Nelson's timezone:** May need to adjust hours or use timezone conversion
- **Example:** If Nelson is in CST (UTC-6), adjust hours:
  - 9 AM CST = 3 PM UTC
  - 5 PM CST = 11 PM UTC
  - So filter would be: `ge(toNumber(formatDate(now(); "HH")); 15); le(toNumber(formatDate(now(); "HH")); 23)`

### **Email Sending**
- **From:** Uses Gmail connection for `nmorales@nexamortgage.com`
- **To:** Dynamic - uses `{{1.`Contact Email`}}`
- **Rate Limits:** Make.com free plan = 1,000 operations/month
- **Gmail Limits:** Google's sending limits apply

### **Testing**
1. **Test during business hours first**
2. **Test with your own email** (add it as a test lead in Airtable)
3. **Check spam folder** - HELOC emails often go to spam
4. **Verify first_name extraction** - Check Module 3 output

---

## 📝 POST-IMPORT STEPS

### **1. Configure Gmail Connection**
- Module 4 requires Gmail connection
- Connect `nmorales@nexamortgage.com` account
- Grant necessary permissions

### **2. Test Business Hours Filter**
- Run scenario manually during business hours
- Run scenario manually outside business hours
- Verify only sends during business hours

### **3. Verify First Name Extraction**
- Check Module 3 output after running
- Ensure `{{3.first_name}}` contains correct first name
- If issues, adjust split function

### **4. Test Email Sending**
- Send test email to yourself first
- Verify formatting (HTML rendering)
- Check all links work
- Verify signature and disclosures

---

## 🐛 TROUBLESHOOTING

### **Emails Not Sending**
- **Check Router:** Is it business hours?
- **Check Airtable Filter:** Is Status = 'new'?
- **Check Gmail Connection:** Is it connected?
- **Check Rate Limits:** Has Make.com limit been reached?

### **Wrong Time**
- Make.com uses UTC time by default
- Adjust hours in filter for your timezone
- Or use timezone conversion function

### **First Name Wrong**
- Check Module 3 output
- Adjust split function if needed
- Format: `{{split(1.`Contact Full Name`; " ")[0]}}`

### **Duplicate Emails**
- Airtable filter should prevent (Status = 'new')
- If still sending duplicates, check:
  - Status is updating correctly
  - No duplicate records in Airtable
  - Make.com isn't re-running old executions

---

## ✅ CHECKLIST

- [ ] Gmail connection configured for nmorales@nexamortgage.com
- [ ] Business hours filter tested (during and outside hours)
- [ ] First name extraction verified
- [ ] Test email sent successfully
- [ ] HTML formatting correct
- [ ] All links work
- [ ] Airtable updates correctly
- [ ] No duplicate emails being sent

---

## 📄 FILES

- **Blueprint:** `scenario b.blueprint-2.json`
- **This Guide:** `NELSON_HELOC_OUTREACH_FINAL.md`

---

**Ready to import and configure!** 🚀

