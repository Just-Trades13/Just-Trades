# Starting a New Chat Window - Quick Reference

**When opening a new chat window, reference these documents to ensure all protection rules are understood:**

---

## 🎯 Recommended: Single Document Reference

### **@START_HERE.md**

**This is the best single document to reference.** It contains:
- All mandatory protection rules
- Links to all other important documents
- Tab isolation rules
- Protection checklists
- Everything an AI assistant needs to know

**Usage in new chat:**
```
@START_HERE.md

[Your request here]
```

---

## 📚 Alternative: Multiple Document References

If you want to be extra explicit, you can reference multiple documents:

### **Option 1: Core Protection Rules**
```
@START_HERE.md @TAB_ISOLATION_MAP.md @.cursorrules
```

### **Option 2: Complete Context**
```
@START_HERE.md @TAB_ISOLATION_MAP.md @CURRENT_STATUS_SNAPSHOT.md @WHAT_NOT_TO_DO.md
```

### **Option 3: Full Protection System**
```
@START_HERE.md @TAB_ISOLATION_MAP.md @PROTECTION_SYSTEM.md @ACCOUNT_MGMT_SNAPSHOT.md
```

---

## 🚀 Quick Start Templates

### For General Work:
```
@START_HERE.md

I want to work on [tab name]. [Your request]
```

### For Account Management (Locked):
```
@START_HERE.md @ACCOUNT_MGMT_SNAPSHOT.md

I want to modify account management. [Your request]
```

### For Manual Trader:
```
@START_HERE.md @TAB_ISOLATION_MAP.md

I want to work on the manual trader tab. [Your request]
```

### For New Features:
```
@START_HERE.md @SANDBOX_WORKFLOW.md

I want to add a new feature. [Your request]
```

---

## 📋 Document Priority

**If you only reference ONE document, use:**
1. **`START_HERE.md`** - Contains everything, points to all other docs

**If you reference TWO documents, use:**
1. **`START_HERE.md`** - Core rules
2. **`TAB_ISOLATION_MAP.md`** - Tab isolation (critical)

**If you reference THREE documents, add:**
3. **`CURRENT_STATUS_SNAPSHOT.md`** - Current state

---

## 🎯 Project Name

**Project Name**: `Just.Trades Trading Platform`

**Workspace Path**: `/Users/mylesjadwin/Trading Projects`

**Main Entry Point**: `START_HERE.md`

---

## ✅ Recommended New Chat Template

**Copy and paste this template when starting a new chat:**

```
@START_HERE.md

Project: Just.Trades Trading Platform
Working on: [Tab name - e.g., "Manual Trader", "Account Management", etc.]

[Your request here]
```

---

## 📝 Example New Chat Starts

### Example 1: Working on Manual Trader
```
@START_HERE.md

Project: Just.Trades Trading Platform
Working on: Manual Trader tab

I want to fix the trailing stop feature.
```

### Example 2: Working on Account Management
```
@START_HERE.md @ACCOUNT_MGMT_SNAPSHOT.md

Project: Just.Trades Trading Platform
Working on: Account Management tab (LOCKED - need permission)

I want to add a new feature to account management.
```

### Example 3: General Question
```
@START_HERE.md

Project: Just.Trades Trading Platform

What's the current status of the trailing stop feature?
```

---

## 🛡️ What Gets Loaded Automatically

**Cursor AI automatically loads:**
- ✅ `.cursorrules` - Protection rules (automatic, no need to @ mention)
- ✅ Project context - From workspace

**You should explicitly reference:**
- ✅ `START_HERE.md` - For complete protection context
- ✅ `TAB_ISOLATION_MAP.md` - For tab-specific work
- ✅ Other docs as needed for specific context

---

## 💡 Pro Tips

1. **Always start with `@START_HERE.md`** - It contains everything
2. **Mention which tab you're working on** - Helps AI understand scope
3. **Reference specific docs if needed** - For locked files or specific features
4. **Cursor auto-loads `.cursorrules`** - But explicit reference ensures full context

---

**Last Updated**: December 2025  
**Status**: Active - Use this guide when starting new chats

