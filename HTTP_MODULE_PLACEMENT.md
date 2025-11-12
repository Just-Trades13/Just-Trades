# ✅ HTTP Module Placement Guide

## 🎯 CORRECT FLOW

**Apollo.io MUST be first (it's the trigger):**

```
Module 20: Apollo.io (Trigger - First Module)
    ↓
Module 21: Iterator (BasicFeeder - Loops through people array)
    ↓
Module X: HTTP → Match API (Unlocks emails) ← ADD HERE
    ↓
Module 2: OpenAI (Extracts data)
```

---

## 📋 WHERE TO PLACE HTTP MODULE

**HTTP module should be:**
- ✅ **AFTER** Module 21 (Iterator)
- ✅ **BEFORE** Module 2 (OpenAI)
- ✅ **NOT before** Module 20 (Apollo - trigger must be first)

---

## 🔧 STEP-BY-STEP PLACEMENT

### Step 1: Identify Your Modules

**In Make.com, find:**
- **Module 20:** Apollo.io Search (trigger - first module)
- **Module 21:** Iterator/BasicFeeder (loops through people)
- **Module 2:** OpenAI (processes data)

### Step 2: Find the Connection Point

**Look for the arrow/connection:**
- From Module 21 → To Module 2
- **Click the "+" button on this connection/arrow**

**OR:**
- Click on Module 21
- Look for output/next module area
- Click "+" to add new module

### Step 3: Add HTTP Module

1. **Click "+" between Module 21 and Module 2**
2. **Search:** "HTTP" or "Make a Request"
3. **Select:** HTTP → Make a Request (or similar)
4. **Add it**

### Step 4: Connect Modules

**Ensure connections:**
- Module 21 → HTTP Module (auto-connects when you add it)
- HTTP Module → Module 2 (may need to manually connect)

**If Module 2 already connects from Module 21:**
- Disconnect Module 21 → Module 2
- Connect: Module 21 → HTTP → Module 2

---

## ✅ VERIFY PLACEMENT

**Check your flow:**
- ✅ Apollo (20) is first
- ✅ Iterator (21) comes after Apollo
- ✅ HTTP module comes after Iterator
- ✅ OpenAI (2) comes after HTTP module
- ✅ All modules connected with arrows

**If HTTP module is in wrong place:**
- Drag it to the correct position
- Or delete and re-add in correct spot

---

## 🔍 TROUBLESHOOTING

### If HTTP Module Still Can't See Module 21:

**Try these references:**

**Option 1: Use previous module reference**
```
{{previous.first_name}}
{{previous.last_name}}
```

**Option 2: Use data mapper**
1. Click `{}` icon in HTTP body
2. Click "Previous module" or navigate
3. Select fields directly (avoids module number issues)

**Option 3: Check actual module number**
- Module numbers might have changed after adding HTTP module
- HTTP module might now be Module 22
- Check what Module 21 actually is in your flow

---

## 📋 HTTP MODULE CONFIGURATION

**Once placed correctly, configure:**

### URL:
```
/v1/people/match
```
(Relative path - Make.com adds base URL)

### Method:
```
POST
```

### Body:
```json
{
  "first_name": "{{21.first_name}}",
  "last_name": "{{21.last_name}}",
  "organization_name": "{{21.organization.name}}"
}
```

**Use data mapper `{}` to select from Module 21!**

---

**Place HTTP module AFTER Module 21, and it will work!** ✅

