# 📄 Google Docs Quote Template Setup Guide

This guide explains how to create and configure Google Docs templates for Package 5A quote generation scenarios.

---

## 🎯 Overview

Package 5A scenarios use Google Docs to create professional quote documents. You need to:

1. Create a quote template in Google Docs
2. Set up the template with placeholders or structure
3. Configure Make.com to use this template

---

## 📝 Step 1: Create Quote Template in Google Docs

### Basic Template Structure

1. **Go to Google Docs** (docs.google.com)
2. **Create a new document**
3. **Set up your template** with the following structure:

```
QUOTE DOCUMENT TEMPLATE

[Company Logo or Header]

QUOTE FOR: {{Client Name}}
COMPANY: {{Company Name}}
DATE: {{Date}}

---

INTRODUCTION
{{Quote Introduction}}

---

SERVICES PROVIDED
{{Service Description}}

---

PRICING BREAKDOWN
{{Pricing Details}}

Total: ${{Total Price}}

---

TERMS AND CONDITIONS
{{Terms}}

---

NEXT STEPS
{{Next Steps}}

---

CONTACT INFORMATION
Your Company Name
Email: your-email@example.com
Phone: (555) 123-4567
```

### Advanced Template (for Scenario 5A-B, 5A-E)

For scenarios with dynamic pricing or multiple options:

```
QUOTE OPTIONS - {{Company Name}}

[Introduction]

OPTION 1: BASIC PACKAGE
- Price: ${{Basic Price}}
- Features: {{Basic Features}}
- Best for: {{Basic Best For}}

OPTION 2: STANDARD PACKAGE
- Price: ${{Standard Price}}
- Features: {{Standard Features}}
- Best for: {{Standard Best For}}

OPTION 3: PREMIUM PACKAGE
- Price: ${{Premium Price}}
- Features: {{Premium Features}}
- Best for: {{Premium Best For}}

RECOMMENDATION: {{Recommendation}}
```

---

## 🔧 Step 2: Configure Template for Make.com

### Option A: Use Template as Base (Copy Method)

1. **Save your template** with a clear name like "Quote Template - Package 5A"
2. **Copy the document ID** from the URL:
   - URL format: `https://docs.google.com/document/d/DOCUMENT_ID/edit`
   - The `DOCUMENT_ID` is the long string between `/d/` and `/edit`
3. **Use this ID in Make.com** Google Docs "Copy Document" module

### Option B: Update Existing Document (Update Method)

1. **Create a template document** with placeholders
2. **Copy the document ID**
3. **Use Google Docs "Update Document" module** in Make.com
4. **Replace placeholders** with actual quote data

---

## 📋 Step 3: Set Up Google Docs Module in Make.com

After importing Package 5A scenarios, you'll need to:

### For "Create Document" (Recommended)

1. **Delete webhook placeholder** for Google Docs operations
2. **Add Google Docs "Create Document" module** manually
3. **Configure**:
   - **Connection**: Create/select Google Docs connection
   - **Method**: "Copy Document" (to copy from template)
   - **Source Document**: Enter your template document ID
   - **Title**: `Quote for {{1.company}}` (or use dynamic data)
   - **Content Mapping**: 
     - Use "Update Content" option to replace placeholders
     - Or use "Append Content" to add quote data

### Content Mapping Examples

**Simple Quote** (Scenario 5A-A):
```
Title: Quote for {{1.company}}
Content: {{6.quote_title}}

{{6.introduction}}

Services:
{{each({{6.services}}) as service}}
- {{service.service}}: {{service.description}} - ${{service.price}}
{{/each}}

Total: ${{6.total_price}}
```

**Advanced Quote** (Scenario 5A-E with comparison):
```
Title: Quote Options - {{1.company}}

{{4.basic.name}} - ${{4.basic.price}}
{{4.basic.description}}

{{4.standard.name}} - ${{4.standard.price}}
{{4.standard.description}}

{{4.premium.name}} - ${{4.premium.price}}
{{4.premium.description}}

Recommendation: {{4.recommendation}}
```

---

## 🎨 Step 4: Template Formatting Tips

### Professional Formatting

1. **Use Headings**: Structure with H1, H2, H3 for clear hierarchy
2. **Add Spacing**: Use line breaks and dividers for readability
3. **Include Logo**: Add your company logo in header
4. **Professional Fonts**: Use Arial, Helvetica, or Times New Roman
5. **Color Scheme**: Use professional colors (black, dark blue, gray)
6. **Tables**: Use tables for pricing breakdowns
7. **Footer**: Include contact information and terms

### Example Formatting

```
QUOTE DOCUMENT

─────────────────────────────────────
YOUR COMPANY NAME
Email: contact@company.com
Phone: (555) 123-4567
─────────────────────────────────────

QUOTE FOR: {{Client Name}}
COMPANY: {{Company Name}}
QUOTE DATE: {{Date}}
QUOTE #: {{Quote Number}}

─────────────────────────────────────

[Main Content Here]

─────────────────────────────────────

This quote is valid for 30 days.
Terms: Payment due within 15 days of acceptance.
```

---

## 🔄 Step 5: Testing Template

### Test Process

1. **Run test execution** in Make.com scenario
2. **Check Google Docs** for created document
3. **Verify**:
   - Document title is correct
   - All data is populated
   - Formatting looks professional
   - Placeholders are replaced

### Troubleshooting

**Issue**: Template not copying correctly
- **Solution**: Verify document ID is correct
- Check Google Docs connection permissions
- Ensure template document is accessible

**Issue**: Content not mapping correctly
- **Solution**: Verify JSON data structure
- Check field references match quote JSON structure
- Use Make.com data mapper to preview data

**Issue**: Formatting lost
- **Solution**: Google Docs "Create Document" may lose some formatting
- Consider using "Update Document" instead
- Or manually format after document creation

---

## 📊 Step 6: Export as PDF (Optional)

### Option A: Manual Export
- After quote is generated, manually export as PDF
- Attach PDF to email in separate step

### Option B: Automated PDF Export
- Use Google Drive API to export document as PDF
- Requires additional Make.com module setup
- Can be attached directly to email

---

## 🎯 Template Examples by Scenario

### Scenario 5A-A (Basic Quote)
- Simple template with introduction, services, pricing, terms
- Single pricing tier
- Straightforward layout

### Scenario 5A-B (Smart Pricing)
- Template includes pricing breakdown
- Shows multipliers (location, urgency, complexity)
- Includes recommended tier

### Scenario 5A-C (With Booking)
- Includes booking options/calendar slots
- Booking link prominently displayed
- Consultation time options

### Scenario 5A-D (Multi-Step)
- Detailed proposal format
- Executive summary
- Deliverables list
- Timeline section
- Comprehensive pricing

### Scenario 5A-E (Comparison)
- Three-tier comparison layout
- Side-by-side feature comparison
- Recommendation section
- Clear pricing for each tier

### Scenario 5A-F (Analytics)
- Report format
- Summary statistics
- Insights section
- Recommendations
- Charts/visualizations (if possible)

---

## ✅ Checklist

Before using Package 5A scenarios:

- [ ] Quote template created in Google Docs
- [ ] Template ID copied and saved
- [ ] Template formatted professionally
- [ ] Placeholders identified (if using Update method)
- [ ] Google Docs connection configured in Make.com
- [ ] Test execution completed successfully
- [ ] Template output reviewed and approved

---

## 📚 Additional Resources

- **Google Docs API Documentation**: https://developers.google.com/docs/api
- **Make.com Google Docs Module Help**: Check Make.com documentation
- **Template Examples**: See Package 5A scenario blueprints for content structure

---

**Last Updated**: 2025-01-XX  
**Package**: Package 5A - AI Quote & Appointment Builder Suite

