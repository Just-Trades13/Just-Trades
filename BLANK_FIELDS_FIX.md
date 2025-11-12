# 🔧 FIX: Airtable Fields Are Blank

## 🎯 THE PROBLEM

Airtable creates/updates records but all fields are blank.

**This means:** Field mappings aren't working!

---

## 🔍 DEBUGGING STEPS

### Step 1: Check Module 3 Output (Parse JSON)

**This is CRITICAL!**

1. **Run scenario**
2. **Click Module 3** (Parse JSON)
3. **Look at output bundle**
4. **Check:** Do you see fields like:
   - `contact_email`
   - `contact_full_name`
   - `company`
   - etc.?

**If Module 3 output is blank or empty:**
- ❌ Problem is in Module 2 (OpenAI) or Module 3
- ✅ Fix Module 2 first, then Module 3

**If Module 3 has data:**
- ✅ Continue to Step 2

---

### Step 2: Check Module 6 or 7 Field Mappings

**Click Module 6 (Create) or Module 7 (Update):**

**Check the Record Fields section:**

**WRONG:**
```
Contact Email: (empty)
Contact Full Name: (empty)
Company: (empty)
```

**RIGHT:**
```
Contact Email: {{3.contact_email}}
Contact Full Name: {{3.contact_full_name}}
Company: {{3.company}}
```

**If fields are empty:** You need to map them!
**If fields have mappings:** Continue to Step 3

---

### Step 3: Verify Field Names Match

**In Module 6/7, check field names:**

**Airtable Field Name** must match **EXACTLY**:
- `Contact Email` (not "Email" or "contact_email")
- `Contact Full Name` (not "Full Name" or "contact_full_name")
- `Company` (not "Company Name" or "company")

**Case-sensitive!** Must match exactly!

---

## ✅ QUICK FIX

### In Module 6 (Create Record):

1. **Click Module 6**
2. **Scroll to "Record" section**
3. **For each field, map from Module 3:**

**Click each field and enter:**

```
Contact Email → {{3.contact_email}}
Contact Full Name → {{3.contact_full_name}}
First Name → {{3.first_name}}
Company → {{3.company}}
Contact Phone → {{3.contact_phone}}
Contact LinkedIN → {{3.contact_linkedin}}
Location City → {{3.location_city}}
Location State → {{3.location_state}}
Property City → {{3.property_city}}
Contact Role → {{3.contact_role}}
Industry → {{3.industry}}
Status → new
Source → apollo_io
Referral Link → {{3.referral_link}}
Channel → email
Notes → {{3.notes}}
```

**Important:**
- Use `{{3.field_name}}` format
- Field names must match Module 3 output exactly
- Select fields (Status, Source) need exact values

4. **Click "OK"**

---

### In Module 7 (Update Record):

**Same mapping, but:**
- Record ID: `{{4.id[0]}}`
- Only map fields you want to update

---

## 🚨 COMMON ISSUES

### Issue 1: Module 3 has no data

**Symptoms:**
- Module 3 output is empty
- Or fields don't exist

**Fix:**
1. Check Module 2 (OpenAI) output
2. Make sure Module 2 returns JSON
3. Check Module 3 JSON reference: `{{2.result}}`

---

### Issue 2: Field names don't match

**Symptoms:**
- Fields mapped but still blank
- Different field names

**Fix:**
1. Check Module 3 output field names
2. Match exactly (case-sensitive)
3. Common mistake: `contact_email` vs `Contact Email`

---

### Issue 3: Select field values don't match

**Symptoms:**
- Error: "Insufficient permissions to create new select option"
- Status/Source fields blank

**Fix:**
1. Go to Airtable
2. Check select field options
3. Use EXACT values:
   - Status: `new` (not "New" or "NEW")
   - Source: `apollo_io` (exact - must exist in Airtable)

---

## 🧪 TEST EACH MODULE

### Test 1: Module 3
**Run up to Module 3:**
- Check output bundle
- Verify all fields have data
- Note exact field names

### Test 2: Module 4
**Run up to Module 4:**
- Check if it finds duplicates
- Verify output structure

### Test 3: Module 6
**Run full scenario:**
- Check Module 6 input bundle
- Verify it receives Module 3 data
- Check field mappings

### Test 4: Airtable
**Check result:**
- New record created?
- Which fields populated?
- Which fields blank?

---

## 💡 QUICK TEST

**Run scenario, then:**

1. **Click Module 3** → Check output
2. **Click Module 6** → Check input bundle
3. **Compare:** Module 3 output vs Module 6 input
4. **Check:** Are field mappings using `{{3.*}}`?

**If Module 6 input is empty:**
- Problem is before Module 6
- Check Modules 1-3

**If Module 6 input has data but Airtable is blank:**
- Problem is field mappings
- Fix Module 6 mappings

---

## 📋 CHECKLIST

- [ ] Module 3 has data (check output bundle)
- [ ] Module 6 field mappings use `{{3.field_name}}`
- [ ] Field names match exactly (case-sensitive)
- [ ] Select field values match Airtable options
- [ ] Test run creates record
- [ ] Check Airtable - which fields are populated?

---

**Share:**
- What does Module 3 output show?
- What do Module 6 field mappings look like?
- Which fields ARE populated (if any)?

**This will help me fix it exactly!** 🔧

