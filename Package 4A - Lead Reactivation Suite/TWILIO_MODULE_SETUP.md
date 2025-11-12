# Twilio Module Setup Guide - Package 4A

## ⚠️ IMPORTANT: Twilio Modules Require Manual Setup

**Twilio modules cannot be imported via JSON blueprint**. After importing Package 4A scenarios, you must manually add and configure Twilio modules.

---

## 📋 Scenarios Using Twilio in Package 4A

The following scenarios use Twilio for SMS reactivation (optional - email path is also available):

- **Scenario 4A-A**: SMS path (Module 8)
- **Scenario 4A-B**: SMS path (Module 11)
- **Scenario 4A-C**: SMS path (Module 6)
- **Scenario 4A-D**: SMS path (Module 9)
- **Scenario 4A-E**: SMS path (Module 8)

**Note**: All scenarios also support email reactivation. Twilio is only needed if you want SMS functionality.

---

## 🔧 Step-by-Step Setup

### Step 1: Delete "Module Not Found" Twilio Module

After importing a scenario:

1. Look for the Twilio module that shows **"Module Not Found"** or red error indicator
2. **Delete this module** (it cannot be configured)
3. Note which module number it was (for reference)

---

### Step 2: Add Twilio "Create a Message" Module

1. Click **"+"** button where the deleted module was
2. Search for **"Twilio"**
3. Select **"Create a Message"** module
4. Connect to the previous module in the flow

---

### Step 3: Configure Twilio Connection

1. **Create New Connection** (if you don't have one):
   - Click "Add" or "Create Connection"
   - Enter your **Twilio Account SID**
   - Enter your **Twilio Auth Token**
   - Click "Save"

2. **Or Select Existing Connection**:
   - Select your existing Twilio connection from dropdown

**Where to Find Twilio Credentials**:
- Log into [Twilio Console](https://console.twilio.com/)
- Go to **Account** → **API Keys & Tokens**
- Copy **Account SID** and **Auth Token**

---

### Step 4: Configure Message Fields

In the Twilio "Create a Message" module, configure:

1. **To** (Phone Number):
   - Map from previous module: `{{1.Contact Phone}}` (or appropriate field)
   - **Format**: Must be E.164 format (e.g., `+1234567890`)
   - Include country code: `+1` for US/Canada

2. **From** (Your Twilio Number):
   - Enter your Twilio phone number: `+1234567890`
   - Must be a number you own in Twilio
   - Use Messaging Service SID if configured

3. **Body** (Message Text):
   - Map from previous module: `{{7.message}}` (or appropriate parsed JSON field)
   - **IMPORTANT**: Always include opt-out text: ` Reply STOP to opt out.`
   - Keep under 1600 characters (Twilio limit)

**Example Body Mapping**:
```
{{7.message}} Reply STOP to opt out.
```

---

### Step 5: Test the Connection

1. **Save** the module configuration
2. **Run** a test execution of the scenario
3. **Verify** SMS is sent to test phone number
4. **Check** Twilio console for message status

---

## 📱 Twilio Account Setup (If New)

If you don't have a Twilio account yet:

1. **Sign Up**: Go to [twilio.com](https://www.twilio.com/try-twilio)
2. **Get Phone Number**:
   - Go to **Phone Numbers** → **Buy a Number**
   - Select country and capabilities (SMS)
   - Purchase number
3. **Get Credentials**:
   - Go to **Account** → **API Keys & Tokens**
   - Copy Account SID and Auth Token

---

## 🔒 Compliance & Best Practices

### Opt-Out Handling
- **Always include**: "Reply STOP to opt out." in SMS body
- Handle STOP replies in a separate scenario (see Package 2A for reference)
- Update Airtable `Do Not Contact` field when STOP received

### TCPA Compliance
- **Consent Required**: Only send SMS to leads who have opted in
- **Clear Identification**: Include business name in messages
- **Opt-Out Easy**: Always provide opt-out instructions

### Quiet Hours
Consider adding time-based filters to respect quiet hours:
- Avoid sending SMS between 9 PM - 8 AM (local time)
- Use Router module to check time before sending

### Rate Limiting
- **Twilio Limits**: Monitor your sending rate
- **Costs**: Twilio charges per SMS (~$0.0075 per message)
- **Daily Limits**: Respect daily sending limits to avoid spam filters

---

## 💰 Cost Considerations

**Twilio SMS Pricing** (approximate):
- **US/Canada**: ~$0.0075 per SMS
- **International**: Varies by country
- **Receive SMS**: Usually free or included

**Package 4A Usage**:
- Scenarios send reactivation SMS (not high-volume)
- Estimate: 10-100 SMS per day depending on reactivation volume
- Monthly cost: ~$5-50 for typical usage

---

## 🧪 Testing Checklist

Before going live:

- [ ] Twilio connection configured correctly
- [ ] Test SMS sent successfully
- [ ] Phone number format correct (E.164)
- [ ] Message body includes opt-out text
- [ ] Test opt-out handling (reply STOP)
- [ ] Verify Airtable updates correctly
- [ ] Check Twilio console for delivery status
- [ ] Test with real phone number

---

## ⚠️ Common Issues & Solutions

### Issue: "Twilio module shows 'Not Found'"
**Solution**: This is expected. Delete it and add "Create a Message" module manually.

### Issue: "Invalid phone number format"
**Solution**: Use E.164 format: `+1234567890` (include country code).

### Issue: "Unauthorized" error
**Solution**: Verify Account SID and Auth Token are correct in connection settings.

### Issue: "SMS not sending"
**Solution**:
- Check Twilio account has credits
- Verify phone number is SMS-enabled
- Check for errors in Twilio console

### Issue: "Message body too long"
**Solution**: Twilio limit is 1600 characters. Shorten message or split into multiple messages.

---

## 📚 Additional Resources

- **Twilio Documentation**: [twilio.com/docs](https://www.twilio.com/docs)
- **Twilio Console**: [console.twilio.com](https://console.twilio.com/)
- **Package 2A Reference**: See Package 2A for SMS reply handling and opt-out automation

---

## 🔄 Integration with Package 4A Scenarios

### Scenario 4A-A
- **Module Location**: Module 8 (SMS path)
- **Body Mapping**: `{{7.message}} Reply STOP to opt out.`
- **To Mapping**: `{{1.Contact Phone}}`

### Scenario 4A-B
- **Module Location**: Module 11 (SMS path)
- **Body Mapping**: `{{8.body}} Reply STOP to opt out.`
- **To Mapping**: `{{1.Contact Phone}}`

### Scenario 4A-C
- **Module Location**: Module 6 (SMS path)
- **Body Mapping**: `{{3.sms_message}} {{3.booking_link}} Reply STOP to opt out.`
- **To Mapping**: `{{1.Contact Phone}}`

### Scenario 4A-D
- **Module Location**: Module 9 (SMS path)
- **Body Mapping**: `{{6.sms_message}} Reply STOP to opt out.`
- **To Mapping**: `{{1.Contact Phone}}`

### Scenario 4A-E
- **Module Location**: Module 8 (SMS path)
- **Body Mapping**: `{{5.sms_message}} Reply STOP to opt out.`
- **To Mapping**: `{{1.Contact Phone}}`

---

**Last Updated**: 2025-01-XX  
**Package**: Package 4A - Lead Reactivation Suite

