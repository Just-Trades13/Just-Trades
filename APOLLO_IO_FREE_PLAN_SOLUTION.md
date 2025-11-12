# Apollo.io Free Plan Solution - Nelson HELOC Lead Capture

## 🚨 The Problem

You received this error:
```
403 - api/v1/mixed_people/search is not accessible with this api_key on a free plan
```

**Apollo.io's `/v1/mixed_people/search` endpoint requires a paid plan** (starting at $49/month).

---

## ✅ Solution Options

### **Option 1: Use Webhook Version (FREE - RECOMMENDED)**

I've created **`Nelson_HELOC_Webhook_Blueprint.json`** that works with Apollo.io's FREE plan.

**How it works:**
1. Export leads from Apollo.io web interface (CSV or JSON)
2. Send leads to the webhook URL via Make.com
3. AI processes and saves to Airtable

**Benefits:**
- ✅ **FREE** - Works with Apollo.io free plan
- ✅ **Flexible** - Accepts leads from ANY source (Apollo.io, manual entry, other tools)
- ✅ **Easy setup** - Just import and get webhook URL

**Setup Steps:**
1. Import `Nelson_HELOC_Webhook_Blueprint.json` into Make.com
2. Get the webhook URL from Module 1
3. Send lead data as JSON to that URL
4. Done! Leads will be processed automatically

**Example Webhook Request:**
```json
{
  "first_name": "John",
  "last_name": "Smith",
  "email": "john@example.com",
  "phone": "555-1234",
  "organization_name": "ABC Realty",
  "title": "Real Estate Agent",
  "city": "Phoenix",
  "state": "AZ",
  "industry": "Real Estate"
}
```

**Using with Apollo.io:**
1. Go to Apollo.io → Search for leads
2. Export results as CSV or JSON
3. Use Make.com's "CSV parser" module to convert
4. Send each row to your webhook URL

---

### **Option 2: Upgrade Apollo.io Plan**

If you want automatic API access:

1. **Go to**: https://app.apollo.io/
2. **Upgrade to Basic Plan**: $49/month (or $59/month billed monthly)
3. **Get API Key**: Settings → Integrations → API
4. **Use**: `Nelson_HELOC_Blueprint.json` (the original version)

**What you get:**
- ✅ Direct API access to `/v1/mixed_people/search`
- ✅ Automatic lead generation without manual exports
- ✅ Higher API rate limits

---

## 📋 Comparison

| Feature | Webhook Version (FREE) | API Version (PAID) |
|---------|----------------------|-------------------|
| **Cost** | $0/month | $49+/month |
| **Setup Time** | 5 minutes | 5 minutes |
| **Lead Source** | Apollo.io exports + any source | Apollo.io API only |
| **Automation** | Manual export → webhook | Fully automatic |
| **Best For** | Starting out, testing | High volume, automation |

---

## 🚀 Quick Start (Webhook Version)

1. **Import Blueprint**
   - Import `Nelson_HELOC_Webhook_Blueprint.json` into Make.com
   - The webhook module will create a URL automatically

2. **Test the Webhook**
   - Copy the webhook URL from Module 1
   - Send a test request:
   ```bash
   curl -X POST YOUR_WEBHOOK_URL \
     -H "Content-Type: application/json" \
     -d '{
       "first_name": "Test",
       "last_name": "Lead",
       "email": "test@example.com",
       "organization_name": "Test Company",
       "city": "Phoenix",
       "state": "AZ"
     }'
   ```

3. **Connect Apollo.io Exports**
   - Export leads from Apollo.io (web interface)
   - Use Make.com's "CSV" or "JSON" parser modules
   - Send each lead to your webhook URL

---

## 📝 Files Created

1. **`Nelson_HELOC_Webhook_Blueprint.json`**
   - Webhook-based version (FREE)
   - Accepts flexible JSON input
   - Works with Apollo.io exports + any source

2. **`Nelson_HELOC_Blueprint.json`** (Original)
   - API-based version (requires paid Apollo.io)
   - Use this if you upgrade to paid plan

---

## 💡 Tips

- **For testing**: Use webhook version (free)
- **For production**: Upgrade Apollo.io if you need >100 leads/month
- **Hybrid approach**: Use Apollo.io free plan to search/filter, then export → webhook
- **Multiple sources**: Webhook version accepts leads from LinkedIn, Google Sheets, manual entry, etc.

---

## ❓ Need Help?

- **Webhook not working?** Check Make.com webhook URL is active
- **Leads not saving?** Verify Airtable connection in blueprint
- **OpenAI errors?** Check API key is set correctly

---

**Bottom Line:** Use the webhook version to get started for FREE. Upgrade to paid Apollo.io only if you need high-volume automated lead generation.

