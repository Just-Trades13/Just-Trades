# Fix: Module Reference Number

## 🔍 THE ISSUE

In Make.com's UI, you see:
- **"HTTP 18"** (this means Module 18)
- **But template shows:** `{{json(if(1.body.people; 1.body.people[0]; {}))}}`

**The problem:** Template is trying to reference Module 1, but your HTTP module is actually Module 18!

---

## ✅ THE FIX

### Step 1: Find Your HTTP Module Number

Look at your scenario in Make.com:
- Find the HTTP module that calls Apollo.io API
- **Look at the number above the module icon**
- Is it Module 1? Module 18? Module something else?

### Step 2: Update the Template

In your **OpenAI module (Message 2, User message)**:

**OLD (WRONG):**
```
{{json(if(1.body.people; 1.body.people[0]; {}))}}
```

**NEW (CORRECT):**
```
{{json(if(18.body.people; 18.body.people[0]; {}))}}
```

**Change the number `1` to whatever your HTTP module number is!**

---

## 📋 EXAMPLES

| Your HTTP Module Number | Use This Template |
|-------------------------|-------------------|
| Module 1 | `{{json(if(1.body.people; 1.body.people[0]; {}))}}` |
| Module 18 | `{{json(if(18.body.people; 18.body.people[0]; {}))}}` |
| Module 3 | `{{json(if(3.body.people; 3.body.people[0]; {}))}}` |
| Module 15 | `{{json(if(15.body.people; 15.body.people[0]; {}))}}` |

---

## 🎯 QUICK FIX IN MAKE.COM

1. **Click Module 2** (OpenAI module)
2. **Click on "Message 2"** (User message)
3. **Click in "Text Content" field**
4. **Delete the current template**
5. **Type:** `{{json(if(18.body.people; 18.body.people[0]; {}))}}`
   - Replace `18` with YOUR HTTP module number!
6. **Click outside to save**
7. **Click "OK"** to close the message

---

## 🔍 HOW TO FIND YOUR MODULE NUMBER

In Make.com scenario view:
1. **Look at your HTTP module** (the one with Apollo.io configuration)
2. **Look above the module icon** - you'll see "HTTP [NUMBER]"
3. **That number** is what you use in the template!

**Example:**
- If you see "HTTP 18" → Use `18` in template
- If you see "HTTP 1" → Use `1` in template
- If you see "HTTP 5" → Use `5` in template

---

## ✅ TEST IT

After updating:

1. **Save the OpenAI module**
2. **Run the scenario** (click "Run once")
3. **Check Module 2 output:**
   - Should show AI-processed lead data
   - Should NOT show errors
4. **If still errors:** Check the module number again!

---

**Bottom line:** Change `1` to whatever number your HTTP module shows in Make.com! 🎯

