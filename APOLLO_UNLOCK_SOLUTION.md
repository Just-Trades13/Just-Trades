# ✅ SOLUTION: Apollo.io Email Unlock

## 🎉 DISCOVERY

**The `/v1/people/match` API unlocks emails automatically!**

**Test Results:**
- ✅ Search API: Returns locked emails (`email_not_unlocked@domain.com`)
- ✅ Match API: Unlocks email (`mike.braham@intempohealth.com`) 🎉
- **Cost:** Consumes credits (~$0.10-0.50 per unlock)

---

## 🔧 HOW IT WORKS

### Current Flow (Emails Locked):
```
Module 20: Apollo Search → Returns locked emails
Module 21: Iterator → Processes locked emails
Module 2: OpenAI → Extracts locked email
Module 6: Airtable → Saves locked email
```

### Enhanced Flow (Emails Unlocked):
```
Module 20: Apollo Search → Returns contacts (locked emails)
Module 21: Iterator → Loops through contacts
🆕 Module X: Apollo Match → Unlocks email (consumes credits)
Module 2: OpenAI → Extracts REAL unlocked email
Module 6: Airtable → Saves real email
```

---

## 📋 APOLLO.IO MATCH API

**Endpoint:** `https://api.apollo.io/v1/people/match`  
**Method:** POST  
**Headers:**
- `Content-Type: application/json`
- `X-Api-Key: YOUR_API_KEY`

**Request Body:**
```json
{
  "first_name": "Mike",
  "last_name": "Braham",
  "organization_name": "Intempo Health"
}
```

**Response:**
```json
{
  "person": {
    "email": "mike.braham@intempohealth.com",  // ✅ UNLOCKED!
    "first_name": "Mike",
    "last_name": "Braham",
    ...
  }
}
```

**This automatically unlocks the email and consumes credits!**

---

## 🔧 ADDING TO YOUR BLUEPRINT

### Step 1: Add HTTP Module After Module 21 (Iterator)

**Add a new HTTP module between Module 21 and Module 2:**

1. **Module Type:** HTTP → Make a Request
2. **URL:** `https://api.apollo.io/v1/people/match`
3. **Method:** POST
4. **Headers:**
   - `Content-Type`: `application/json`
   - `X-Api-Key`: `DtdKb5hTo_9GTtbohlNJ-Q` (your API key)
5. **Body:**
   ```json
   {
     "first_name": "{{21.first_name}}",
     "last_name": "{{21.last_name}}",
     "organization_name": "{{21.organization.name}}"
   }
   ```

**This will unlock the email and return it in the response!**

---

### Step 2: Update Module 2 to Use Unlocked Email

**In Module 2 (OpenAI), change the input to use unlocked email:**

**Current:** Uses `{{21.email}}` (locked)  
**New:** Uses `{{X.email}}` (where X is the new HTTP module number)

**OR:** Use `{{X.person.email}}` depending on response structure

---

### Step 3: Update Module 6 to Use Unlocked Email

**In Module 6 (Airtable Create), update email field:**

**Current:** `{{21.email}}` (locked)  
**New:** `{{X.person.email}}` (unlocked)

---

## 💰 CREDIT COST

**Each unlock consumes credits:**
- ~$0.10 - $0.50 per email unlock
- Depends on your Apollo plan
- Credits are consumed automatically
- No additional setup needed

**If you run out of credits:**
- Unlock will fail
- Blueprint will continue but email stays locked
- Add more credits to Apollo account

---

## ✅ BENEFITS

1. **Automatic Unlocking:** No manual steps
2. **Real Emails:** Get actual email addresses
3. **Credits Work:** Uses your existing credits
4. **Seamless:** Works within your current flow

---

## 📋 QUICK SETUP IN MAKE.COM

### Add HTTP Module:

1. **Click "+" between Module 21 and Module 2**
2. **Search:** "HTTP" → "Make a Request"
3. **Configure:**
   - **URL:** `https://api.apollo.io/v1/people/match`
   - **Method:** POST
   - **Headers:**
     - `Content-Type`: `application/json`
     - `X-Api-Key`: `DtdKb5hTo_9GTtbohlNJ-Q`
   - **Body Type:** Raw / JSON
   - **Body:**
     ```json
     {
       "first_name": "{{21.first_name}}",
       "last_name": "{{21.last_name}}",
       "organization_name": "{{21.organization.name}}"
     }
     ```
4. **Click OK**

### Update Module 2:

1. **Click Module 2 (OpenAI)**
2. **Find input field** (where you use `{{21.email}}`)
3. **Change to:** `{{X.person.email}}` (X = HTTP module number)
4. **Click OK**

### Update Module 6:

1. **Click Module 6 (Airtable Create)**
2. **Find "Contact Email" field**
3. **Change from:** `{{21.email}}`
4. **Change to:** `{{X.person.email}}` (X = HTTP module number)
5. **Click OK**

---

## ⚠️ NOTES

1. **Credits Required:** Each unlock costs credits
2. **Rate Limits:** Don't unlock too many at once
3. **Failures:** If unlock fails, email stays locked
4. **Optional:** You can add Router to skip if unlock fails

---

**Add the HTTP module and emails will unlock automatically using your credits!** 🎉

