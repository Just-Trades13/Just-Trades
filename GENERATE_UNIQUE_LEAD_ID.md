# 🔧 FIX: Generate Unique Lead IDs

## ❌ PROBLEM

**Apollo.io person IDs are PERMANENT:**
- Same person = Same ID always
- Run 1: Person gets ID `62d4844bef7fac00010aa738`
- Run 2: Same person still has ID `62d4844bef7fac00010aa738`
- Module 4 finds existing record → Updates it

**Solution: Generate unique Lead IDs for each run!**

---

## ✅ SOLUTION: Update OpenAI to Generate Unique Lead ID

### Option 1: Use Timestamp + Apollo ID

**Update Module 2 system message:**

**Find this line:**
```
"lead_id": "{{ULID}}",
```

**Change to:**
```
"lead_id": "apollo_{{3.lead_id}}_{{NOW}}",
```

**OR if you want to use Apollo ID directly:**
- Check Module 2 user message - it receives person data
- Extract the Apollo `id` field: `{{21.array[0].id}}`
- Use that as base, but add timestamp

**Better: Update the system message to generate unique ID:**

**In the system message, change:**
```
"lead_id": "{{ULID}}",
```

**To:**
```
"lead_id": "Use the 'id' field from the input person data, then append '_' and current timestamp in format YYYYMMDDHHmmss. Example: if input id is '62d4844bef7fac00010aa738', output should be '62d4844bef7fac00010aa738_20251102120000'",
```

**OR simpler - just use Apollo ID + timestamp:**

**Update system message to:**
```
"lead_id": "Use {{id}}_{{timestamp}} where id is from input person and timestamp is current time YYYYMMDDHHmmss",
```

---

### Option 2: Use Make.com Functions in System Message

**Actually, you can't use Make.com functions in OpenAI prompt.**

**Better: Tell OpenAI to generate unique ID based on input:**

**In Module 2 system message, update this section:**

**Current:**
```
"lead_id": "{{ULID}}",
```

**Change to instructions:**
```
IMPORTANT: For lead_id, use the 'id' field from the input person data and append '_run' + current timestamp.
Format: {person_id}_run{YYYYMMDDHHmmss}
Example: If person id is '62d4844bef7fac00010aa738', use '62d4844bef7fac00010aa738_run20251102120000'
```

---

### Option 3: Add Module Between 3 and 4 to Generate Unique ID

**Add "Set Variable" or "Data > Set Variable" module after Module 3:**

1. **Add module after Module 3**
2. **Type:** "Set Variable" or "Data > Set Variable"
3. **Variable name:** `unique_lead_id`
4. **Variable value:** `{{3.lead_id}}_{{NOW}}` or `{{3.lead_id}}_{{timestamp}}`
5. **Update Module 4** to search by this unique ID
6. **Update Module 6** to use this unique ID

**This generates:**
- `62d4844bef7fac00010aa738_20251102120000`
- `64ccd7227a554900015b15d7_20251102120001`
- etc.

**Each run gets different timestamp → Different Lead IDs!**

---

## 🎯 RECOMMENDED: Option 3 (Add Variable Module)

### Step-by-Step:

**Step 1: Add Variable Module**

1. **Add module after Module 3** (Parse JSON)
2. **Search for:** "Set Variable" or "Data > Set Variable"
3. **Variable name:** `unique_lead_id`
4. **Variable value:** `{{3.lead_id}}_{{NOW}}`
   - OR: `{{3.lead_id}}_{{timestamp}}`
   - This creates unique ID per run

**Step 2: Update Module 4**

1. **Click Module 4** (Airtable Search)
2. **Formula:** Change to `{Lead ID} = '{{unique_lead_id}}'`
   - OR if variable is in different module: `{{MODULE_NUMBER.unique_lead_id}}`

**Step 3: Update Module 6**

1. **Click Module 6** (Create Record)
2. **Find "Lead ID" field**
3. **Change from:** `{{3.lead_id}}`
4. **Change to:** `{{unique_lead_id}}`

**Step 4: Test**

- Run scenario
- Each person gets unique Lead ID with timestamp
- Module 4 won't find duplicates
- Module 6 creates new records!

---

## ✅ QUICK FIX: Update System Message

**Easier: Just update the OpenAI prompt instruction:**

**In Module 2 system message, find:**
```
"lead_id": "{{ULID}}",
```

**Replace the entire template with instructions:**

```
For lead_id, combine the person's 'id' field from the input with current timestamp.
Format: {id}_run{YYYYMMDDHHmmss}
Example input id '62d4844bef7fac00010aa738' → output '62d4844bef7fac00010aa738_run20251102120000'
```

**Then in the JSON template, use:**
```
"lead_id": "Use format: {input_id}_run{timestamp}",
```

**OpenAI will generate unique IDs based on timestamp!**

---

**Try Option 3 first - add Variable module to generate unique Lead IDs!** 🚀

