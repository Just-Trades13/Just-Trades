# Just.Trades Trading Platform

⚠️ **CRITICAL FOR AI ASSISTANTS**: **READ `START_HERE.md` FIRST** - Mandatory protection rules before any code changes.

---

## 🚨 FOR AI ASSISTANTS / CHAT CONTEXTS

**BEFORE MAKING ANY CHANGES, YOU MUST READ:**

1. **`START_HERE.md`** - ⚠️ **READ THIS FIRST** - Mandatory rules
2. **`.cursorrules`** - Complete protection rules
3. **`TAB_ISOLATION_MAP.md`** - **CRITICAL**: Only modify files for the tab you're working on
4. **`WHAT_NOT_TO_DO.md`** - Past mistakes to avoid
5. **`PRE_CHANGE_CHECKLIST.md`** - Mandatory checklist

**THESE RULES ARE MANDATORY. NO EXCEPTIONS.**

---

## 🛡️ Protection System

This project has **7 layers of protection** to prevent breaking working code:

1. **Tab Isolation** - Only modify files for the tab you're working on
2. **Cursor Rules** - AI assistant rules
3. **Cursor Ignore** - Protected files list
4. **File Permissions** - Read-only protection
5. **Documentation Snapshots** - Locked baselines
6. **Git Tags & Backups** - Restore points
7. **Sandbox System** - Isolated development

**See `PROTECTION_SYSTEM.md` for complete documentation.**

---

## 📋 Quick Start

### For Developers
```bash
# Install dependencies
pip install -r requirements.txt

# Start server
python3 ultra_simple_server.py

# Server runs on http://localhost:8082
```

### For AI Assistants
1. **Read `START_HERE.md`** - Mandatory rules
2. **Check `TAB_ISOLATION_MAP.md`** - Which files belong to which tab
3. **Follow protection rules** - Don't break working code
4. **Use sandbox** - For experimental work (`./create_sandbox.sh`)

---

## 🎯 Project Structure

### Tabs/Pages
- **Account Management** (`/accounts`) - **LOCKED** - Baseline saved
- **Manual Trader** (`/manual-trader`) - Manual trading interface
- **Control Center** (`/control-center`) - Live trading panel
- **Dashboard** (`/dashboard`) - Analytics dashboard
- **Strategies** (`/strategies`) - Strategy management
- **Recorders** (`/recorders`) - Recorder management
- **Traders** (`/traders`) - Trader management
- **Settings** (`/settings`) - Settings page

**See `TAB_ISOLATION_MAP.md` for complete file mappings.**

---

## 🔒 Protected Files

- `templates/account_management.html` - **LOCKED** - Do not modify
- Account management functions - **PROTECTED**
- Core integration methods - **PROTECTED**

**See `ACCOUNT_MGMT_SNAPSHOT.md` for locked baseline.**

---

## 📚 Documentation

### Protection System
- **`START_HERE.md`** - ⚠️ **READ FIRST** - Mandatory rules
- **`TAB_ISOLATION_MAP.md`** - Tab-to-files mapping
- **`PROTECTION_SYSTEM.md`** - Complete protection guide
- **`QUICK_PROTECTION_REFERENCE.md`** - Quick reference
- **`SANDBOX_WORKFLOW.md`** - Sandbox usage guide

### Project Documentation
- **`HANDOFF_DOCUMENT.md`** - Main handoff document
- **`CURRENT_STATUS_SNAPSHOT.md`** - Current state
- **`WHAT_NOT_TO_DO.md`** - Past mistakes
- **`PRE_CHANGE_CHECKLIST.md`** - Mandatory checklist

---

## 🚨 Important Rules

1. **Tab Isolation** - Only modify files for the tab you're working on
2. **Protected Files** - Don't modify without explicit permission
3. **Verify Before Fixing** - Don't fix things that aren't broken
4. **One Change at a Time** - Make minimal, focused changes
5. **When in Doubt, ASK** - Don't assume it's okay

---

## 🛠️ Tools

### Protection Scripts
```bash
# Protect files (make read-only)
./protect_files.sh

# Unprotect files (restore write permissions)
./unprotect_files.sh

# Create sandbox for experiments
./create_sandbox.sh my_feature
```

### Restore from Backup
```bash
# From git tag
git checkout working-state-dec-2025

# From file backup
cp backups/2025-11-25/account_management.html templates/
```

---

## ⚠️ For AI Assistants

**THIS IS CRITICAL:**

- **READ `START_HERE.md` FIRST** - Before any code changes
- **FOLLOW TAB ISOLATION** - Only modify files for the tab you're working on
- **RESPECT PROTECTED FILES** - Don't modify without permission
- **VERIFY BEFORE FIXING** - Don't fix things that aren't broken
- **MAKE MINIMAL CHANGES** - One change at a time

**These rules are MANDATORY. Violating them will break working code.**

---

## 📞 Support

- **Protection Rules**: See `START_HERE.md` and `PROTECTION_SYSTEM.md`
- **Tab Isolation**: See `TAB_ISOLATION_MAP.md`
- **Sandbox Usage**: See `SANDBOX_WORKFLOW.md`

---

**Last Updated**: December 2025  
**Status**: Active - All protection systems enabled
