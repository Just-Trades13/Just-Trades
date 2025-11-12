# Fix OpenAI 403 Error in Make.com

## 🔴 The Error
```
[403] Invalid permissions, or the requested model was not found
```

This appears at Airtable but is actually an **OpenAI error** from Module 2.

---

## ✅ Quick Fix in Make.com

### Step 1: Check OpenAI Module (Module 2)

1. **Open your scenario** in Make.com
2. **Click on Module 2** (OpenAI module)
3. **Check the "Model" dropdown:**
   - Should show: `gpt-3.5-turbo`
   - If it shows `gpt-4o` or another model, change it to `gpt-3.5-turbo`

### Step 2: Verify OpenAI Connection

1. **Click on Module 2**
2. **Check "Connection" dropdown**
3. **If connection is missing:**
   - Click "Add connection"
   - Enter your OpenAI API key
   - Get it from: https://platform.openai.com/api-keys
   - Test the connection

### Step 3: Check Model Availability

The blueprint was updated to use `gpt-3.5-turbo` which should work for all accounts.

**If `gpt-3.5-turbo` doesn't work, try:**
- `gpt-3.5-turbo-0125` (specific version)
- `gpt-4-turbo-preview` (if you have GPT-4 access)
- `gpt-4` (if available)

**To check what models you have access to:**
1. Go to: https://platform.openai.com/account/usage
2. Check available models in your account
3. Select one of those in Make.com

---

## 🔍 Troubleshooting Checklist

### ✅ OpenAI API Key
- [ ] API key is valid and active
- [ ] API key has billing set up (no credit issues)
- [ ] API key hasn't been deleted or rotated

### ✅ Model Access
- [ ] Selected model is available in your account
- [ ] Model name is spelled correctly (case-sensitive)
- [ ] You have permissions for the selected model

### ✅ Connection in Make.com
- [ ] OpenAI connection is configured
- [ ] Connection is not expired
- [ ] Connection has correct API key

---

## 🚀 After Fixing OpenAI

Once OpenAI module works:
1. **Run the scenario manually** to test
2. **Check Module 2 output** - should show AI response
3. **Check Module 3** (Parse JSON) - should parse successfully
4. **Airtable modules** should then work correctly

---

## 📝 Quick Model Change in Make.com

**If you need to change the model:**

1. Click **Module 2** (OpenAI)
2. Find **"Model"** dropdown
3. Select: **`gpt-3.5-turbo`**
4. Click **"OK"** to save
5. Run scenario again

---

## ⚠️ Common Issues

**Issue**: Still getting 403 after changing to `gpt-3.5-turbo`
- **Fix**: Check your OpenAI account has access to models at: https://platform.openai.com/account/usage

**Issue**: Error appears at Airtable but is actually OpenAI
- **Fix**: Fix OpenAI module first, then Airtable will work

**Issue**: Connection seems fine but still errors
- **Fix**: Delete and re-add the OpenAI connection in Make.com

---

**Once OpenAI is fixed, Airtable will automatically work!**

