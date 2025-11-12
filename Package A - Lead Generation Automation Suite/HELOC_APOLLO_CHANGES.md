# 🔄 HELOC Apollo.io Integration - Changes Summary

## What Was Changed

### ✅ Module 1: Webhook → Apollo.io Search People

**Before:**
- Module: `gateway:CustomWebHook`
- Triggered by external webhook calls
- Expected input: Generic lead data JSON

**After:**
- Module: `apollo-io:SearchPeople`
- Searches Apollo.io database for HELOC prospects
- Output: Array of people matching search criteria

**Key Fields Changed:**
- Input interface now expects Apollo.io structure:
  - `people[]` array
  - Each person has: `first_name`, `last_name`, `email`, `phone_numbers[]`, `organization_name`, `title`, `city`, `state`, `linkedin_url`, `industry`

---

### ✅ Module 2: AI Processing - HELOC Focused

**System Prompt Updated:**
- **Before**: Generic LinkedIn/phantom scraper data extraction
- **After**: Apollo.io-specific field mappings + HELOC industry focus

**New HELOC Industry Mappings:**
- Real Estate → `real_estate`
- Construction → `construction`
- Property Management → `real_estate`
- Home Services → `real_estate`
- Financial Services → `finance`
- Banking → `finance`
- Mortgage → `finance`
- Insurance → `finance`

**New HELOC Tags:**
- `heloc_prospect` (all Apollo.io leads)
- `home_owner`
- `property_owner`
- `high_equity`
- `real_estate`, `construction`, `finance`, `mortgage`
- `property_manager`, `realtor`

**Source Changed:**
- Before: `"source": "linkedin"`
- After: `"source": "apollo_io"`

**User Message:**
- Before: `{{`1`}}` (webhook data)
- After: `{{`1.people[0]`}}` (first person from Apollo.io results)

---

### ✅ UTM List ID

**Before:**
```json
"utm_list_id": "pb-run-2025-01-25-1320"
```

**After:**
```json
"utm_list_id": "heloc-apollo-{{DATE}}"
```

---

## Apollo.io Data Structure Mapping

| Apollo.io Field | Mapped To | Notes |
|----------------|-----------|-------|
| `organization_name` | `company` | Primary company field |
| `first_name` + `last_name` | `contact_full_name` | Combined by AI |
| `email` | `contact_email` | Direct mapping |
| `phone_numbers[0].sanitized_number` | `contact_phone` | First phone number |
| `linkedin_url` | `contact_linkedin` | Direct mapping |
| `city` | `location_city` | Direct mapping |
| `state` | `location_state` | Converted to abbreviation |
| `title` | `contact_role` | Job title |
| `industry` | `industry` | Mapped to HELOC categories |

---

## Configuration Requirements

### Apollo.io Setup
1. **Account Required**: Paid Apollo.io plan (People Search API requires paid tier)
2. **API Key**: Get from Apollo.io → Settings → Integrations → API
3. **Connection**: Add in Make.com → Connections → Apollo.io

### Search Criteria (Configure in Module 1)
- **Person Titles**: Property Manager, Real Estate Agent, etc.
- **Industries**: Real Estate, Construction, Property Management
- **Locations**: Target cities/states for HELOC prospects
- **Keywords**: "homeowner", "property owner", etc.

---

## Testing Checklist

- [ ] Apollo.io module connects successfully
- [ ] Search returns results
- [ ] AI extracts `first_name` and `last_name` correctly
- [ ] AI combines names into `contact_full_name`
- [ ] Phone number extracted from `phone_numbers` array
- [ ] HELOC industry mappings work (Real Estate → real_estate)
- [ ] HELOC tags added (`heloc_prospect`, etc.)
- [ ] Source field = "apollo_io"
- [ ] Leads created in Airtable correctly
- [ ] Duplicate detection works (by `contact_full_name`)

---

## File Locations

- **Blueprint**: `Scenario A - HELOC Lead Capture (Apollo.io).blueprint.json`
- **Setup Guide**: `HELOC_APOLLO_SETUP.md`
- **This Summary**: `HELOC_APOLLO_CHANGES.md`

---

## Next Steps After Import

1. **Configure Apollo.io Connection** in Make.com
2. **Set Search Criteria** for HELOC prospects
3. **Test with Single Search** (run once)
4. **Add Schedule Trigger** (optional - for automatic runs)
5. **Connect to HELOC Website** (optional - trigger from form submissions)

---

**Version**: 1.0  
**Created**: 2025-01-25  
**Purpose**: HELOC Lead Generation via Apollo.io

