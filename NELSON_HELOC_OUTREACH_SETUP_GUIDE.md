# 📧 Nelson HELOC Outreach - Make.com Setup Guide

## 🎯 Scenario Overview
This scenario sends automated HELOC outreach emails to leads from Airtable during business hours (Mon-Fri, 9 AM - 5 PM).

---

## 📋 Step-by-Step Setup

### **Step 1: Create New Scenario**
1. Go to Make.com
2. Click **"Create a new scenario"**
3. Name it: **"Nelson HELOC Outreach"**

---

### **Step 2: Add Module 1 - Airtable Trigger**

1. Click **"Add a module"**
2. Search for **"Airtable"** → Select **"Watch records"**
3. Configure:
   - **Base**: Select "Leads Manager AI CRM"
   - **Table**: Select "Leads"
   - **Trigger field**: Select "Last Modified Time"
   - **Label field**: Select "Status"
   - **Filter**: Add formula: `{Status} = 'new'`
   - **Limit**: 10

---

### **Step 3: Add Module 2 - Router (Business Hours Check)**

1. Click **"Add a module"** after Module 1
2. Search for **"Router"** → Select **"Basic Router"**
3. Click **"Add route"** to create 2 routes:

#### **Route 1: Business Hours (Send Email)**
- **Filter**: Click "Set conditions"
- **Add condition**: Use this formula:
  ```
  {{and(contains(["Mon", "Tue", "Wed", "Thu", "Fri"]; formatDate(now(); "E")); ge(toNumber(formatDate(now(); "HH")); 9); le(toNumber(formatDate(now(); "HH")); 17))}}
  ```
- This checks: Monday-Friday AND 9 AM - 5 PM

#### **Route 2: Outside Business Hours (Do Nothing)**
- Leave filter empty (this is the "else" route)

---

### **Step 4: Add Module 3 - Set Variable (Extract First Name)**

1. Inside **Route 1** of the Router, click **"Add a module"**
2. Search for **"Set variable"** → Select **"Set variable"**
3. Configure:
   - **Variable name**: `first_name`
   - **Variable lifetime**: "One cycle"
   - **Variable value**: 
     ```
     {{split(1.`Contact Full Name`; " ")[0]}}
     ```
   - This extracts the first name from the full name

---

### **Step 5: Add Module 4 - Send Email**

1. After Module 3, click **"Add a module"**
2. Search for **"Gmail"** or **"Google Email"** → Select **"Send an email"**
3. Connect your Gmail account (use `nmorales@nexamortgage.com` if available)
4. Configure:
   - **To**: `{{1.`Contact Email`}}`
   - **Subject**: `Unlock Your Home Equity - HELOC Opportunities`
   - **Body type**: **"Raw HTML"**
   - **Content**: Paste this HTML:

```html
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #ffffff;">
    <p>Hi {{3.first_name}},</p>
    <p>Many homeowners are discovering they can access cash from their home without touching their current mortgage rate.</p>
    <p>You can apply in 5 minutes & receive funding in as little as 5 days.</p>
    <p>No impact to your credit as a soft pull it utilized for pre-approval and your options.</p>
    <p>A system generated Appraised valuation means no appraisal to order value is instant.</p>
    <p>A HELOC (Home Equity Line of Credit) allows you to use your existing equity for:</p>
    <ul>
        <li>Paying off high-interest credit cards</li>
        <li>Home repairs & upgrades</li>
        <li>Business or investment opportunities</li>
    </ul>
    <div style="text-align: center; margin: 30px 0;">
        <a href="https://axenmortgageheloc.com/account/heloc/register-v2?referrer=55ac77e7-8bb0-48c5-92a8-65960f3efe42" style="background-color: #007bff; color: white; padding: 14px 28px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; font-size: 16px;">Start your secure application now</a>
    </div>
    <p>If you'd like me to help you personally, just reply YES.</p>
    <p>Nelson Morales<br>
    Mortgage Loan Originator — NMLS #1174028<br>
    Nexa Mortgage, LLC — NMLS #1660690<br>
    Equal Housing Lender<br>
    <br>
    C: 773-592-8213<br>
    <a href="mailto:nmorales@nexamortgage.com">nmorales@nexamortgage.com</a><br>
    <br>
    Verify my credentials:<br>
    <a href="https://nmlsconsumeraccess.org/TuringTestPage.aspx?ReturnUrl=/EntityDetails.aspx/COMPANY/1660690">https://nmlsconsumeraccess.org/TuringTestPage.aspx?ReturnUrl=/EntityDetails.aspx/COMPANY/1660690</a></p>
    <p style="font-size: 11px; color: #666; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">Disclosures: This is not a commitment to lend. Minimum and maximum loan amounts, rates, and terms may vary and are subject to qualification including income, credit, and property approval. All loan programs, terms, and interest rates are subject to change without notice. Conditions and restrictions apply. Equal Housing Lender. Nexa Mortgage, LLC is licensed in the states where required. If you are not the intended recipient or would like to opt out, please reply "STOP" to unsubscribe.</p>
</div>
```

---

### **Step 6: Add Module 5 - Update Airtable Record**

1. After Module 4 (still in Route 1), click **"Add a module"**
2. Search for **"Airtable"** → Select **"Update a record"**
3. Configure:
   - **Base**: "Leads Manager AI CRM"
   - **Table**: "Leads"
   - **Record ID**: `{{1.id}}`
   - **Fields to update**:
     - **Status**: `emailed`
     - **Email Campaign**: `heloc_initial_outreach`
     - **Last Out Reach**: `{{now}}`
     - **Next Step**: `Initial Email`

---

## 📊 Final Module Flow

```
Module 1: Airtable Watch Records (Trigger)
    ↓
Module 2: Router
    ├─→ Route 1: Business Hours (Mon-Fri, 9 AM - 5 PM)
    │       ├─→ Module 3: Set Variable (first_name)
    │       ├─→ Module 4: Send Email (Nelson's Template)
    │       └─→ Module 5: Update Airtable (Status = "emailed")
    │
    └─→ Route 2: Outside Business Hours
            (Do nothing - scenario ends)
```

---

## ⚠️ Important Notes

1. **Business Hours**: The router uses Make.com server time (UTC). Adjust the hours if needed:
   - Current: 9 AM - 5 PM UTC
   - If Nelson is in a different timezone, adjust the hours accordingly

2. **Gmail Connection**: Make sure you connect the correct Gmail account (`nmorales@nexamortgage.com`)

3. **Airtable Fields**: Ensure these fields exist in your Airtable:
   - `Status` (Select field with option "new" and "emailed")
   - `Email Campaign` (Text field)
   - `Last Out Reach` (Date field)
   - `Next Step` (Select or Text field)

4. **Testing**: 
   - Set a lead's Status to "new" in Airtable
   - Run the scenario manually
   - Check if email is sent and Airtable is updated

---

## ✅ Verification Checklist

- [ ] Module 1: Airtable trigger configured with `{Status} = 'new'` filter
- [ ] Module 2: Router has 2 routes (business hours + else)
- [ ] Module 3: Variable `first_name` extracts first name correctly
- [ ] Module 4: Email template includes `{{3.first_name}}` and all Nelson's info
- [ ] Module 5: Airtable updates Status, Email Campaign, Last Out Reach, and Next Step
- [ ] Scenario is saved and activated

---

## 🚀 You're Done!

Once all modules are connected and configured, save the scenario and activate it. It will automatically send emails to leads with Status = "new" during business hours.

