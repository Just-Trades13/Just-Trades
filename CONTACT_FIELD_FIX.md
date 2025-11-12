# Fix: Airtable Contact Full Name Field Error

## 🔴 THE ERROR
```
[422] Unknown field names: contact full name
```

## ❌ THE PROBLEM

Your Airtable table doesn't have a field named **"Contact Full Name"**.

The blueprint is searching for duplicates using:
```
{Contact Full Name} = '{{3.contact_full_name}}'
```

But that field doesn't exist in your Airtable table!

---

## ✅ THE FIX

**Change to search by email instead of name!**

### In Module 4 (Airtable Search Records):

1. **Click Module 4** in Make.com
2. **Find "Formula" field**
3. **Change from:**
   ```
   {Contact Full Name} = '{{3.contact_full_name}}'
   ```
4. **Change to:**
   ```
   {Contact Email} = '{{3.contact_email}}'
   ```
5. **Click "OK"**

---

## 🎯 WHY EMAIL IS BETTER

**Searching by email is better because:**
- ✅ More unique (less duplicates)
- ✅ More reliable
- ✅ Standard practice in CRM systems
- ✅ Email is always available from Apollo.io

**Names can be:**
- Duplicated (many people named "John Smith")
- Have variations ("John", "Johnny", "Jonathan")
- Have typos or spacing issues

---

## ✅ ALTERNATIVE: Use the field name you have

**Check your Airtable table:**

If your field is named differently, use that name instead:

- `{Full Name}` instead of `{Contact Full Name}`
- `{Name}` instead of `{Contact Full Name}`
- `{Contact Name}` instead of `{Contact Full Name}`

**Just use whatever the exact field name is in your table!**

---

## 📋 HOW TO FIND YOUR FIELD NAMES

1. **Go to your Airtable table**
2. **Look at the column headers**
3. **See what the contact name field is actually called**
4. **Use that exact name** in the formula

---

**Change the formula to use email or the correct field name!** ✅

