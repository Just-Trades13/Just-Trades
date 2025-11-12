# Fill Out HTTP Module - Step by Step

## 📋 Your API Key
```
DtdKb5hTo_9GTtbohlNJ-Q
```

---

## ✅ Fill Out Each Field

### Step 1: URL Field

**Location:** "URL *" (empty text input field)

**What to enter:**
```
https://api.apollo.io/v1/mixed_people/search
```

**OR just the path:**
```
/v1/mixed_people/search
```

**Important:** NO trailing slash (`/`) at the end!

---

### Step 2: Method

**Location:** "Method *" dropdown (currently shows "GET")

**What to do:**
1. Click the dropdown
2. Change from "GET" to: **"POST"**

**Why:** Apollo.io search requires POST to send body data.

---

### Step 3: Headers

**Location:** "Headers" section (has "+ Add a header" link)

**You need to add TWO headers:**

#### Header 1: Content-Type
1. Click **"+ Add a header"**
2. In the row that appears:
   - **Name field:** Type `Content-Type`
   - **Value field:** Type `application/json`
3. Click outside or tab to confirm

#### Header 2: X-Api-Key
1. Click **"+ Add a header"** again (second time)
2. In the new row:
   - **Name field:** Type `X-Api-Key`
   - **Value field:** Type `DtdKb5hTo_9GTtbohlNJ-Q`

**You should now have TWO headers in your list.**

---

### Step 4: Query String

**Location:** "Query String" section

**What to do:**
- **Leave this EMPTY**
- Don't click "+ Add parameter"
- We're sending data in the body, not query parameters

---

### Step 5: Body Type

**Location:** "Body type" dropdown (currently empty)

**What to do:**
1. Click the dropdown
2. Select: **"Raw"**
3. A large text area will appear below

---

### Step 6: Body (JSON)

**Location:** Text area that appeared after selecting "Raw"

**What to paste:**
Click in the text area and paste this EXACT JSON:

```json
{
  "q_keywords": "homeowner property owner",
  "person_titles": [
    "Property Manager",
    "Real Estate Agent",
    "Real Estate Developer",
    "Construction Manager",
    "Homeowner",
    "Property Owner"
  ],
  "person_locations": [
    "Arizona",
    "California",
    "Florida",
    "Texas",
    "Nevada"
  ],
  "organization_industries": [
    "Real Estate",
    "Construction",
    "Property Management",
    "Home Services"
  ],
  "page": 1,
  "per_page": 1
}
```

**Important:**
- Make sure ALL quotes are straight (`"`), not curly (`"`)
- No extra spaces before or after
- Valid JSON format

---

### Step 7: Parse Response

**Location:** "Parse response" section (currently has "No" selected)

**What to do:**
1. Click the **"Yes"** radio button
2. Select: **"Yes"**

**Why:** This allows Make.com to automatically parse the JSON response.

---

### Step 8: Advanced Settings

**Location:** Toggle switch at bottom

**What to do:**
- **Leave it OFF**

---

### Step 9: Save

**Location:** Bottom buttons

**What to do:**
1. Review all fields above
2. Click **"Save"** button (purple, bottom right)

---

## 📋 Quick Checklist Before Saving

Verify you have:

- [ ] **URL:** `https://api.apollo.io/v1/mixed_people/search` (or `/v1/mixed_people/search`)
- [ ] **Method:** `POST` (not GET)
- [ ] **Headers:** TWO headers added
  - [ ] `Content-Type: application/json`
  - [ ] `X-Api-Key: DtdKb5hTo_9GTtbohlNJ-Q`
- [ ] **Query String:** Empty
- [ ] **Body Type:** `Raw` selected
- [ ] **Body:** JSON pasted (all HELOC search criteria)
- [ ] **Parse Response:** `Yes` selected
- [ ] **Advanced Settings:** Off

---

## 🚀 After Saving

1. **Click "Save"**
2. **Run the scenario** (click "Run once" or the play button)
3. **Check the output:**
   - Should return **200 status**
   - Should have `people[]` array with lead data
4. **If errors:**
   - **401:** API key wrong → Check the key
   - **403:** Free plan → Need paid plan
   - **404:** URL wrong → Check URL

---

## ⚠️ Important Notes

1. **API Key:** Make sure `X-Api-Key` header is EXACTLY: `DtdKb5hTo_9GTtbohlNJ-Q`
2. **JSON Format:** Make sure body is valid JSON
3. **Parse Response:** Must be "Yes" for other modules to work
4. **Method:** Must be "POST", not "GET"

---

**Fill out all fields above and click Save!** ✅

