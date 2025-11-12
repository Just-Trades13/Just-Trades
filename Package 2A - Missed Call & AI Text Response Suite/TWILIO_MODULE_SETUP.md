# ⚠️ Twilio Module Setup Guide

## Critical Issue: Twilio Modules Not Importable via JSON

**Problem**: When importing Package 2A scenarios, Twilio modules appear as **"Module Not Found"** with identifier `twilio:CreateMessage`.

**Root Cause**: Twilio modules, like Gmail modules, cannot be imported via JSON blueprint format in Make.com. They must be added manually after import.

---

## ✅ Solution: Manual Module Setup

### Step-by-Step Instructions

1. **Import the Blueprint**
   - Import the scenario as normal
   - You will see "Module Not Found" for Twilio modules - this is expected

2. **Delete the "Module Not Found" Module**
   - Click on the grey "Module Not Found" module
   - Delete it (or it may auto-disconnect)

3. **Add Twilio Module Manually**
   - Click the "+" button where the Twilio module should be
   - Search for "Twilio"
   - Select **"Create a Message"** from the Twilio actions
   - Position it in the flow where the old module was

4. **Configure the Twilio Module**
   - **Connection**: Create or select your Twilio connection
     - Enter Account SID
     - Enter Auth Token
   - **To**: Map to the phone number field (e.g., `{{1.From}}`)
   - **From**: Enter your Twilio phone number (e.g., `+1234567890`)
   - **Body**: Enter your message text or map from previous module

5. **Connect to Next Module**
   - Connect the Twilio module output to the next module in the flow
   - Verify the flow connections are correct

---

## 📋 Scenarios Requiring Twilio Setup

All Package 2A scenarios (except Scenario 2A-F) require Twilio module manual setup:

| Scenario | Number of Twilio Modules | Module IDs to Replace |
|----------|--------------------------|----------------------|
| **2A-A** | 1 | Module 3 |
| **2A-B** | 1 | Module 6 |
| **2A-C** | 1 | Module 5 |
| **2A-D** | 1 | Module 8 |
| **2A-E** | 1 | Module 5 |
| **2A-F** | 0 | N/A |

---

## 🔍 How to Identify Twilio Modules

In the imported scenario, look for:
- Grey circular modules with red exclamation mark
- Text "Module Not Found"
- Identifier `twilio:CreateMessage`

These need to be replaced with the manual Twilio module.

---

## ✅ Verification

After manual setup, verify:
- ✅ Twilio connection is configured and tested
- ✅ "To" field maps to correct phone number source
- ✅ "From" field has your Twilio phone number
- ✅ "Body" field has message text or maps correctly
- ✅ Module is connected properly in the flow
- ✅ No red error indicators on the module

---

## 🎯 Quick Reference

**Module Name in Make.com UI**: `Twilio - Create a Message`  
**Action**: Sends SMS messages  
**Required Fields**: To, From, Body  
**Connection Required**: Yes (Twilio Account SID + Auth Token)

---

**Note**: This manual setup is a limitation of Make.com's JSON import system. Once set up manually, the module will work perfectly and be saved with your scenario.

