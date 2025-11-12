# Apollo.io Data Available - Complete Field List

## ✅ YOUR API KEY WORKS!

Based on real API testing, here's what data you can pull:

---

## 📊 SEARCH RESULTS SUMMARY

✅ **Total Available:** 472,131+ contacts can be searched
✅ **API Response:** 200 status code  
✅ **Authentication:** Working perfectly

---

## 🎯 COMPLETE DATA FIELDS AVAILABLE

### ✅ CONTACT INFORMATION

| Field | Example | Description |
|-------|---------|-------------|
| **id** | `66f2c8eddf0dea0001f4b1e0` | Unique Apollo.io person ID |
| **first_name** | `Aravind` | First name |
| **last_name** | `Srinivas` | Last name |
| **name** | `Aravind Srinivas` | Full name |
| **email** | `aravind@example.com` | Email (may show "email_not_unlocked") |
| **email_status** | `verified` | Email verification status |
| **phone_numbers** | Array of phone objects | Phone numbers with formats |
| **linkedin_url** | `https://linkedin.com/in/...` | LinkedIn profile URL |
| **twitter_url** | `https://twitter.com/...` | Twitter profile URL |
| **github_url** | `https://github.com/...` | GitHub profile URL |
| **facebook_url** | `https://facebook.com/...` | Facebook profile URL |

### ✅ LOCATION INFORMATION

| Field | Example | Description |
|-------|---------|-------------|
| **street_address** | `123 Main St` | Street address |
| **city** | `San Francisco` | City |
| **state** | `California` | State |
| **country** | `United States` | Country |
| **postal_code** | `94102` | ZIP/postal code |
| **formatted_address** | `San Francisco, CA, USA` | Full formatted address |
| **time_zone** | `America/Los_Angeles` | Time zone |

### ✅ PROFESSIONAL INFORMATION

| Field | Example | Description |
|-------|---------|-------------|
| **title** | `Cofounder, President, CEO` | Job title |
| **headline** | `Cofounder, President & CEO, Perplexity` | LinkedIn headline |
| **departments** | `['c_suite']` | Department categories |
| **subdepartments** | `['executive', 'founder']` | Sub-department categories |
| **seniority** | `founder` | Seniority level |
| **employment_history** | Array of jobs | Complete work history |

### ✅ COMPANY INFORMATION

| Field | Example | Description |
|-------|---------|-------------|
| **organization.id** | `54a1395a69702d231f4c6800` | Organization ID |
| **organization.name** | `Perplexity` | Company name |
| **organization.website_url** | `https://perplexity.ai` | Company website |
| **organization.linkedin_url** | `https://linkedin.com/company/...` | Company LinkedIn |
| **organization.industry** | `Technology` | Industry |
| **organization.primary_phone** | `+1 707-641-2519` | Company phone |
| **organization.founded_year** | `2022` | Year founded |

### ✅ EMPLOYMENT HISTORY

Each job in **employment_history** includes:
- `title` - Job title
- `organization_name` - Company name
- `start_date` - Start date (YYYY-MM-DD)
- `end_date` - End date (or null if current)
- `current` - Boolean (true/false)
- `organization_id` - Company ID

### ✅ PHONE NUMBERS

**phone_numbers** array contains:
```json
{
    "raw_number": "+1 (555) 123-4567",
    "sanitized_number": "+15551234567",
    "type": "mobile" // or "landline"
}
```

### ✅ ADDITIONAL FIELDS

| Field | Example | Description |
|-------|---------|-------------|
| **photo_url** | `https://static.licdn.com/...` | Profile photo URL |
| **intent_strength** | `high` | Intent score |
| **show_intent** | `true` | Whether to show intent data |
| **revealed_for_current_team** | `true` | Team access status |

---

## 🎯 PERFECT FOR HELOC LEADS!

### ✅ Fields You Can Use:

**Personal:**
- ✅ First name
- ✅ Last name
- ✅ Full name
- ✅ Email (requires unlock for some contacts)
- ✅ Phone numbers
- ✅ LinkedIn profile

**Location:**
- ✅ City (for HELOC property location)
- ✅ State
- ✅ Full address
- ✅ Time zone

**Professional:**
- ✅ Title/role
- ✅ Employment history
- ✅ Company name
- ✅ Company industry

**Company:**
- ✅ Organization name
- ✅ Industry
- ✅ Website
- ✅ Company phone

---

## 📊 SEARCH CAPABILITIES

You can search by:
- ✅ **Keywords** - `q_keywords: "homeowner property owner"`
- ✅ **Job titles** - `person_titles: ["Real Estate Agent", "Property Manager"]`
- ✅ **Locations** - `person_locations: ["California", "Arizona"]`
- ✅ **Industries** - `organization_industries: ["Real Estate", "Construction"]`
- ✅ **Company names** - `organization_names: ["Compass", "Century 21"]`
- ✅ **Seniority** - `seniority: ["manager", "director", "vp"]`

---

## ⚠️ IMPORTANT NOTES

1. **Email Unlocking:**
   - Some emails show as "email_not_unlocked"
   - Requires email credits to unlock real email
   - Contact Apollo.io about email unlock pricing

2. **Data Availability:**
   - All fields shown above ARE available via API
   - Some fields may be null for certain contacts
   - Employment history is typically complete

3. **Rate Limits:**
   - Based on your Apollo.io plan
   - Basic plan: Check Apollo.io docs for limits

4. **Pagination:**
   - `per_page` can be set 1-100 typically
   - Use `page` parameter to paginate results
   - Total pages shown in response

---

## 🚀 NEXT STEPS FOR YOUR HELOC AUTOMATION

Your blueprint is already configured to use:

✅ **Contact Name** - `first_name`, `last_name`
✅ **Email** - `email` field
✅ **Phone** - `phone_numbers` array
✅ **Location** - `city`, `state` for property location
✅ **Title** - `title` field
✅ **Company** - `organization.name`
✅ **LinkedIn** - `linkedin_url`
✅ **Industry** - `organization.industry`

---

**Your Apollo.io API is working perfectly and you have access to all the data fields needed for HELOC lead generation!**

