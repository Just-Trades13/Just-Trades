# 📋 Airtable Setup Guide for Nelson HELOC Lead Capture

## 🎯 Quick Setup

**Created file**: `HELOC_Leads_Airtable.csv`

This CSV has all the fields your blueprint expects for Nelson's HELOC lead capture system.

---

## 📥 How to Import to Airtable

### Step 1: Create New Base
1. Go to [airtable.com](https://airtable.com)
2. Click **"+ Add a base"**
3. Choose **"Import a spreadsheet"**
4. Upload `HELOC_Leads_Airtable.csv`

### Step 2: Configure Field Types

After import, configure each field type in Airtable:

#### Core Fields
| Field Name | Type | Notes |
|------------|------|-------|
| **Lead ID** | Single line text | Auto-generated ULID |
| **Status** | Single select | Options: `new`, `contacted`, `qualified`, `closed` |
| **Contact Full Name** | Single line text | |
| **First Name** | Single line text | For personalization |
| **Contact Email** | Email | Used for duplicate detection |
| **Contact Phone** | Phone number | |
| **Contact LinkedIN** | URL | LinkedIn profile |
| **Company** | Single line text | |
| **Domain** | Single line text | Company website |
| **Industry** | Single line text | |
| **Employee Count** | Number | |
| **Contact Role** | Single line text | Job title |

#### Location Fields
| Field Name | Type | Notes |
|------------|------|-------|
| **Location City** | Single line text | |
| **Location State** | Single line text | State abbreviation |
| **Property City** | Single line text | HELOC-specific |

#### HELOC-Specific Fields
| Field Name | Type | Notes |
|------------|------|-------|
| **Referral Link** | URL | Nelson's HELOC signup link |
| **Channel** | Single select | Options: `email`, `sms`, `dm` |
| **Estimated Equity** | Number | Home equity estimate |

#### Tracking Fields
| Field Name | Type | Notes |
|------------|------|-------|
| **Source** | Single select | Options: `apollo_io`, `linkedin`, `website`, etc. |
| **Acquired At** | Date | When lead was captured |
| **Last Out Reach** | Date | Last contact date |
| **Tags** | Multiple select | HELOC tags: `heloc_prospect`, `home_owner`, `real_estate`, etc. |
| **Notes** | Long text | AI notes and observations |

#### Campaign Fields
| Field Name | Type | Notes |
|------------|------|-------|
| **UTM List ID** | Single line text | Tracking ID |
| **Email Campaign** | Single select | Campaign status |
| **Reply Received** | Checkbox | |
| **Meeting Completed** | Checkbox | |
| **Next Step** | Single line text | |
| **Meeting Link** | URL | Calendar link |

#### Sales Fields
| Field Name | Type | Notes |
|------------|------|-------|
| **Pipeline Value** | Currency | Dollar value |

---

## ⚙️ Field Configuration Details

### Select Fields Setup

#### Status
Options:
- `new`
- `contacted`
- `qualified`
- `converted`
- `closed_lost`

#### Source
Options:
- `apollo_io`
- `linkedin`
- `website`
- `referral`
- `other`

#### Channel
Options:
- `email`
- `sms`
- `dm`
- `call`

#### Tags (Multiple Select)
Options:
- `heloc_prospect`
- `home_owner`
- `property_owner`
- `real_estate`
- `construction`
- `finance`
- `high_priority`
- `responded`
- `meeting_scheduled`

#### Email Campaign
Options:
- `initial_outreach`
- `follow_up_1`
- `follow_up_2`
- `nurture`
- `closed`

---

## 🔗 Connect to Make.com

### Step 1: Get Your Base and Table IDs

1. **Base ID**: 
   - Go to your Airtable base
   - Click "Help" → "API documentation"
   - Find your **Base ID** (starts with `app...`)

2. **Table ID**:
   - In the same API docs
   - Find your **Table ID** (starts with `tbl...`)

### Step 2: Update Blueprint

Replace in `Nelson HELOC Lead Capture - CORRECTED.blueprint.json`:

**Module 4 (Search)**:
```json
"base": "YOUR_BASE_ID",
"table": "YOUR_TABLE_ID"
```

**Module 7 (Create)**:
```json
"base": "YOUR_BASE_ID",
"table": "YOUR_TABLE_ID"
```

**Module 9 (Update)**:
```json
"base": "YOUR_BASE_ID",
"table": "YOUR_TABLE_ID"
```

---

## 🧪 Test the Setup

### Test Data Example

After setup, your blueprint should populate:

```json
{
  "Lead ID": "01ABCD...",
  "Status": "new",
  "Company": "ABC Real Estate",
  "Contact Full Name": "John Smith",
  "First Name": "John",
  "Contact Email": "john@abcreal.com",
  "Contact Phone": "+1-555-123-4567",
  "Contact LinkedIN": "https://linkedin.com/in/johnsmith",
  "Location City": "Los Angeles",
  "Location State": "CA",
  "Property City": "Los Angeles",
  "Contact Role": "Real Estate Agent",
  "Industry": "Real Estate",
  "Source": "apollo_io",
  "Referral Link": "https://axenmortgageheloc.com/...",
  "Channel": "email",
  "Tags": ["heloc_prospect", "home_owner", "real_estate"],
  "Notes": "Generated from Apollo.io data"
}
```

---

## ✅ Checklist

- [ ] Import CSV to Airtable
- [ ] Configure all field types
- [ ] Set up Select field options
- [ ] Get Base ID and Table ID
- [ ] Update blueprint with IDs
- [ ] Test with Make.com scenario
- [ ] Verify data populates correctly

---

## 🚨 Troubleshooting

### Field Names Don't Match
**Problem**: Blueprint expects "Contact Full Name" but table has different name

**Fix**: In Make.com module configuration, manually map fields

### Select Options Not Showing
**Problem**: Data rejects select option

**Fix**: Ensure select options are created in Airtable BEFORE running scenario

### Duplicate Detection Not Working
**Problem**: Creates duplicate records

**Fix**: Check Module 4 search formula is correct:
```
{Contact Email} = '{{3.contact_email}}'
```

### Missing Data
**Problem**: Some fields are blank

**Fix**: Check Apollo.io data is being extracted properly by OpenAI

---

## 📚 Additional Resources

- **Airtable Help**: https://support.airtable.com/
- **Make.com Airtable Docs**: https://www.make.com/en/help/apps/airtable
- **Field Type Reference**: https://support.airtable.com/docs/field-types

---

**Your Airtable is now ready to receive HELOC leads from Apollo.io!** 🚀

