# Verified Make.com Modules (From Your Working Scenarios)

This document lists all modules that are **confirmed working** based on your successfully imported scenarios.

## ✅ VERIFIED WORKING MODULES

### Airtable
- `airtable:TriggerWatchRecords` (v3) - Trigger on record changes
- `airtable:ActionSearchRecords` (v3) - Search records
- `airtable:ActionCreateRecord` (v3) - Create new record
- `airtable:ActionUpdateRecords` (v3) - Update existing records

### OpenAI
- `openai-gpt-3:CreateCompletion` (v1) - Legacy completion API
- `openai-gpt-3:createModelResponse` (v1) - New chat completion API (recommended)

### Google Email / Gmail
- `google-email:sendAnEmail` (v4) - Send emails via Gmail/Google Workspace

### Gateway / Webhooks
- `gateway:CustomWebHook` (v1) - Custom webhook trigger

### JSON Processing
- `json:ParseJSON` (v1) - Parse JSON strings into data structures
  - Use `type: 197771` for AI-generated JSON
  - Include restore metadata for proper UI recognition

### Built-in Modules
- `builtin:BasicRouter` (v1) - Route data based on conditions (if-else, switch)

### Twilio
- `twilio:CreateMessage` - Send SMS messages (Create a Message action)

## ❌ MODULES THAT DON'T EXIST OR DON'T WORK

Based on your error reports, these modules **do NOT work**:

- `schedule:Scheduler` - ❌ Not found
- `google-email:ListMessages` - ❌ Not found
- `google-email:GetAMessage` - ❌ Not found
- `google-email:SearchMessages` - ❌ Not found
- `google-email:WatchEmails` - ❌ Not found
- `google-email:GetAnEmail` - ❌ Not found
- `text:TextParser` - ❌ Not found
- `delay:Delay` - ❌ Not found
- `tools:SetVariable` - ❌ Not found (may work in UI but not in JSON import)
- `flowcontrol:Sleep` - ❌ Not found

## 📝 RECOMMENDATIONS

### For Email Triggers (Reply Detection)
**Problem**: Make.com doesn't seem to support Gmail email triggers in JSON blueprints.

**Solutions**:
1. **Use Webhook** (current approach in Scenario F): Import with `gateway:CustomWebHook`, then manually replace with Gmail trigger in Make.com UI
2. **Use Airtable Trigger**: Instead of watching emails directly, use an external service (like Google Apps Script) to forward emails to Airtable, then trigger from Airtable
3. **Manual Setup**: After import, delete webhook and manually add Gmail trigger in Make.com's visual interface

### For Scheduling/Delays
**Problem**: No verified schedule/timer modules found in working scenarios.

**Solutions**:
1. **Use Airtable + Time-based Formula**: Trigger from Airtable using time-based formulas
2. **Remove Delays**: Many workflows don't actually need delays - execute immediately
3. **Manual Setup**: Add schedule triggers manually in Make.com UI after import

### For Text Parsing
**Problem**: `text:TextParser` doesn't exist.

**Solution**: Use `json:ParseJSON` - Modify AI prompts to return JSON instead of plain text.

## 🔍 MODULE NAMING PATTERN

From analyzing your working scenarios, the pattern is:
- Format: `app-name:ModuleName` (camelCase for module name)
- Version: Usually `version: 1` or `version: 3` for Airtable
- Examples:
  - `airtable:ActionUpdateRecords`
  - `google-email:sendAnEmail` (lowercase for module)
  - `openai-gpt-3:createModelResponse`

## 📚 BEST PRACTICES

1. **Always use JSON output from AI**: Configure OpenAI to return JSON, then parse with `json:ParseJSON`
2. **Use Airtable triggers**: Very reliable for time-based and condition-based triggers
3. **Test in UI first**: Some modules work in the UI but not in JSON imports
4. **Webhook as fallback**: Use `gateway:CustomWebHook` for triggers that don't import, then replace manually

## 🔄 UPDATED SCENARIOS

All updated scenarios (D, E, F) now use only verified modules:
- ✅ `airtable:TriggerWatchRecords` for triggers
- ✅ `openai-gpt-3:createModelResponse` for AI
- ✅ `json:ParseJSON` for parsing
- ✅ `google-email:sendAnEmail` for sending emails
- ✅ `gateway:CustomWebHook` for triggers that require manual setup

