# Fix: Function 'json' not found

## 🔴 THE ERROR
```
Failed to map '1.content': Function 'json' not found!
```

## ❌ THE PROBLEM

Make.com **doesn't have a `json()` function** in templates!

**Current template (WRONG):**
```
{{json(if(1.body.people; 1.body.people[0]; {}))}}
```

---

## ✅ THE FIX

### Option 1: Remove json() (RECOMMENDED)

**Use this instead:**
```
{{if(18.body.people; 18.body.people[0]; {})}}
```

**Replace `18` with your HTTP module number!**

### Option 2: Direct Path (Simpler, but may error if empty)

**If you're sure the array exists:**
```
{{18.body.people[0]}}
```

**Replace `18` with your HTTP module number!**

---

## 🎯 HOW TO FIX IN MAKE.COM

1. **Click Module 2** (OpenAI module)
2. **Click "Message 2"** (User message)
3. **In "Text Content" field, replace:**
   - **OLD:** `{{json(if(1.body.people; 1.body.people[0]; {}))}}`
   - **NEW:** `{{if(18.body.people; 18.body.people[0]; {})}}`
4. **Replace `18` with your actual HTTP module number!**
5. **Click outside to save**
6. **Click "OK"**

---

## 📋 QUICK REFERENCE

| Your HTTP Module | Use This Template |
|------------------|-------------------|
| Module 1 | `{{if(1.body.people; 1.body.people[0]; {})}}` |
| Module 18 | `{{if(18.body.people; 18.body.people[0]; {})}}` |
| Module 5 | `{{if(5.body.people; 5.body.people[0]; {})}}` |
| Module X | `{{if(X.body.people; X.body.people[0]; {})}}` |

**Just replace X with your HTTP module number!**

---

## ⚠️ IMPORTANT NOTES

1. **No json() function** - Make.com doesn't support it
2. **Module number must match** - Use your actual HTTP module number
3. **if() handles empty arrays** - Returns `{}` if `people` doesn't exist
4. **Direct path is simpler** - But may error if array is empty

---

## ✅ WHAT THE TEMPLATE DOES

**`{{if(18.body.people; 18.body.people[0]; {})}}` means:**
- **If** `18.body.people` exists → return `18.body.people[0]` (first person)
- **Else** → return `{}` (empty object)

This safely handles cases where:
- Apollo.io returns no results
- HTTP request fails
- Array is empty

---

**Remove `json()` from the template and it will work!** ✅

