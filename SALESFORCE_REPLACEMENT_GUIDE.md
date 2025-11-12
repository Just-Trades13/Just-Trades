# 🔄 Replacing Airtable with Salesforce in Make.com

## 📋 Overview

Your blueprint currently uses **3 Airtable modules** that need to be replaced:
1. **Module 4**: Airtable Search Records (find duplicates)
2. **Module 7**: Airtable Create Record (new lead)
3. **Module 9**: Airtable Update Record (existing lead)

---

## 🔧 Make.com Salesforce Setup

### Prerequisites

1. **Salesforce Connection**:
   - Go to Make.com → Connections
   - Add "Salesforce" connection
   - Authenticate with your Salesforce credentials
   - Select the correct environment (Production/Sandbox)

2. **Know Your Salesforce Object**:
   - Usually "Lead" or "Contact"
   - Note the object name (e.g., "Lead", "Contact", "Custom Lead")

---

## 🎯 Module Replacements

### Module 4: Replace "Airtable Search Records"

**New Module**: `salesforce:SearchesAdvancedSearchRecords`

**Configuration**:
1. **Connection**: Your Salesforce connection
2. **Object**: `Lead` (or your custom object)
3. **Formula** (SOSL): 
   ```
   FIND '{{3.contact_email}}' IN EMAIL FIELDS RETURNING Lead(Id, Email, FirstName, LastName) LIMIT 1
   ```
   Or using SOQL:
   ```
   SELECT Id, Email, FirstName, LastName FROM Lead WHERE Email = '{{3.contact_email}}' LIMIT 1
   ```

**Fields to return**: `Id`, `Email`, `FirstName`, `LastName`, `Company`

---

### Module 7: Replace "Airtable Create Record"

**New Module**: `salesforce:CreateLead` (or `CreateRecord`)

**Configuration**:
1. **Connection**: Your Salesforce connection
2. **Object Type**: `Lead`
3. **Map fields**:
   - `FirstName`: `{{3.first_name}}`
   - `LastName`: `{{3.contact_full_name}}` (or parse from full name)
   - `Email`: `{{3.contact_email}}`
   - `Phone`: `{{3.contact_phone}}`
   - `Company`: `{{3.company}}`
   - `City`: `{{3.location_city}}`
   - `State`: `{{3.location_state}}`
   - `Title`: `{{3.contact_role}}`
   - `Industry`: `{{3.industry}}`
   - `LeadSource`: `Apollo.io`
   - `Description`: `{{3.notes}}`
   - `Status`: `Open - Not Contacted`

---

### Module 9: Replace "Airtable Update Record"

**New Module**: `salesforce:UpdateLead` (or `UpdateRecord`)

**Configuration**:
1. **Connection**: Your Salesforce connection
2. **Object Type**: `Lead`
3. **Record ID**: `{{4.Id}}` (from Module 4 search)
4. **Map fields**:
   - `Description`: Append `{{3.notes}}`
   - `LastActivityDate`: `{{now}}`
   - (Any other fields you want to update)

---

## 📝 Field Mapping Reference

### Airtable → Salesforce

| Airtable Field | Salesforce Field | Notes |
|----------------|------------------|-------|
| `contact_full_name` | `FirstName` + `LastName` | Parse if needed |
| `first_name` | `FirstName` | |
| `contact_email` | `Email` | Used for duplicate check |
| `contact_phone` | `Phone` | |
| `company` | `Company` | Required for Leads |
| `location_city` | `City` | |
| `location_state` | `State` | |
| `contact_role` | `Title` | |
| `industry` | `Industry` | |
| `notes` | `Description` | |
| `source` | `LeadSource` | |
| `status` | `Status` | |
| `referral_link` | `Description` or Custom Field | |
| `utm_list_id` | Custom Field | |

---

## 🔍 Salesforce Search Options

### Option 1: SOSL Search (Search All Objects)

**Best for**: Finding leads across multiple objects

```
FIND '{{3.contact_email}}' IN EMAIL FIELDS 
RETURNING Lead(Id, Email, FirstName, LastName), 
           Contact(Id, Email, FirstName, LastName)
LIMIT 1
```

### Option 2: SOQL Query (Specific Object)

**Best for**: Searching only Leads

```
SELECT Id, Email, FirstName, LastName, Company 
FROM Lead 
WHERE Email = '{{3.contact_email}}' 
LIMIT 1
```

### Option 3: Make.com "Search Records" Module

**Easier**: Use Make.com's built-in search module

**Configuration**:
1. **Search for**: `Email = '{{3.contact_email}}'`
2. **Object**: `Lead`
3. **Return**: First record only

---

## ✅ Checklist

**Before starting**:
- [ ] Salesforce connection configured in Make.com
- [ ] Know your Salesforce object name (Lead/Contact)
- [ ] Test Salesforce connection
- [ ] Know your field names (they might differ from Airtable)

**Replacements**:
- [ ] Replace Module 4: Airtable Search → Salesforce Search
- [ ] Replace Module 7: Airtable Create → Salesforce Create
- [ ] Replace Module 9: Airtable Update → Salesforce Update
- [ ] Update all field mappings
- [ ] Test with a sample record

**Testing**:
- [ ] Run scenario with test data
- [ ] Verify search works
- [ ] Verify create works
- [ ] Verify update works
- [ ] Check for duplicate handling

---

## 🎯 Example: Updated Module 4 (Search)

```json
{
    "id": 4,
    "module": "salesforce:ActionSearchRecords", // or salesforce:SearchesAdvancedSearchRecords
    "version": 1,
    "parameters": {
        "__IMTCONN__": YOUR_SALESFORCE_CONNECTION_ID
    },
    "mapper": {
        "searchFor": "Email = '{{3.contact_email}}'",
        "object": "Lead",
        "limit": 1
    }
}
```

---

## 🚨 Common Issues

### Issue: "Field not found"
**Fix**: Check Salesforce object field names (use exact API names)

### Issue: "Required field missing"
**Fix**: Ensure required fields are mapped (e.g., `Company` for Leads)

### Issue: "Duplicate detection not working"
**Fix**: Use exact email match in search formula

### Issue: "Can't update record"
**Fix**: Ensure Record ID is correct and not null

---

## 📚 Resources

- **Salesforce Object Reference**: https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/
- **Make.com Salesforce Docs**: https://www.make.com/en/help/apps/salesforce
- **SOSL Syntax**: https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/sforce_api_calls_sosl_syntax.htm
- **SOQL Syntax**: https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/sforce_api_calls_soql_syntax.htm

---

## 🔧 Quick Start

**Simplest approach**: Use Make.com's "Search Records" module for searching and "Create/Update Record" for data manipulation.

**Steps**:
1. Delete Airtable modules (4, 7, 9)
2. Add Salesforce modules in the same positions
3. Configure with your connection
4. Map the fields
5. Test!

---

**Need help with a specific module? Share the module number and what you're seeing!** 🚀

