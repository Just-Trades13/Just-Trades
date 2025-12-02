# Protection System Documentation

**Purpose**: Comprehensive guide to the codebase protection system

---

## 🛡️ Protection Layers

### Layer 1: Cursor Rules (`.cursorrules`)
- **Location**: Root directory
- **Purpose**: Instructs AI assistants on protection rules
- **Effect**: AI reads these rules before making changes
- **Status**: ✅ Active

### Layer 2: Cursor Ignore (`.cursorignore`)
- **Location**: Root directory
- **Purpose**: Lists files that should not be modified
- **Effect**: AI assistants should skip these files
- **Status**: ✅ Active

### Layer 3: File Permissions (`protect_files.sh`)
- **Location**: Root directory
- **Purpose**: Makes protected files read-only
- **Effect**: Prevents accidental modifications
- **Usage**: `./protect_files.sh` to protect, `./unprotect_files.sh` to unprotect
- **Status**: ✅ Available

### Layer 4: Documentation Snapshots
- **Files**: `ACCOUNT_MGMT_SNAPSHOT.md`, `CURRENT_STATUS_SNAPSHOT.md`
- **Purpose**: Documents locked baselines
- **Effect**: Reference for what should not change
- **Status**: ✅ Active

### Layer 5: Git Tags & Backups
- **Git Tags**: `working-state-dec-2025` (and future tags)
- **Backups**: `backups/YYYY-MM-DD/` directories
- **Purpose**: Restore points for working code
- **Status**: ✅ Active

### Layer 6: Sandbox System
- **Location**: `sandboxes/` directory
- **Purpose**: Isolated environment for experiments
- **Effect**: Safe testing without affecting main code
- **Status**: ✅ Available

---

## 🔒 Protected Files

### Fully Locked (Read-Only)
- `templates/account_management.html` - Account management baseline

### Protected Functions (Can Modify File, But Not These Functions)
- `ultra_simple_server.py`:
  - `fetch_and_store_tradovate_accounts()` - Account fetching
  - OAuth callback and connection endpoints
  - Account management API endpoints

- `phantom_scraper/tradovate_integration.py`:
  - Core authentication methods
  - Token refresh logic
  - Account listing methods

### Protected Documentation (Reference Only)
- `ACCOUNT_MGMT_SNAPSHOT.md` - Account management baseline
- `WHAT_NOT_TO_DO.md` - Lessons learned
- `PRE_CHANGE_CHECKLIST.md` - Mandatory checklist
- `CURRENT_STATUS_SNAPSHOT.md` - Current state

---

## 🚀 Usage Guide

### For AI Assistants

**Before making ANY changes:**
1. Read `.cursorrules` (automatically loaded)
2. Check `.cursorignore` for protected files
3. Read `WHAT_NOT_TO_DO.md` for past mistakes
4. Read `PRE_CHANGE_CHECKLIST.md` for mandatory steps
5. Check if file is in protection docs
6. If protected, ask user for explicit permission

**When modifying protected files:**
1. ⚠️ WARN user that file is protected
2. Ask for explicit permission
3. Reference protection documentation
4. Suggest sandbox if appropriate
5. Make minimal, focused changes
6. Test thoroughly

### For Developers

**Protecting Files:**
```bash
# Make files read-only
./protect_files.sh

# Files are now protected
# To unprotect (if needed):
./unprotect_files.sh
```

**Creating Sandbox:**
```bash
# Create sandbox for new feature
./create_sandbox.sh my_new_feature

# Work in sandbox
cd sandboxes/my_new_feature

# Test, then merge approved changes
```

**Restoring from Backup:**
```bash
# From git tag
git checkout working-state-dec-2025

# From file backup
cp backups/2025-11-25/account_management.html templates/
```

---

## 📋 Protection Checklist

### Before Modifying Any File:

- [ ] Is file in `.cursorignore`? → **STOP, ask permission**
- [ ] Is file listed in `ACCOUNT_MGMT_SNAPSHOT.md`? → **STOP, ask permission**
- [ ] Is file mentioned in protection docs? → **STOP, ask permission**
- [ ] Have I read `WHAT_NOT_TO_DO.md`? → **Read it first**
- [ ] Have I read `PRE_CHANGE_CHECKLIST.md`? → **Read it first**
- [ ] Is this a major change? → **Consider using sandbox**
- [ ] Have I verified the problem exists? → **Verify first**

### If File is Protected:

- [ ] Have I asked user for explicit permission? → **Ask first**
- [ ] Have I warned user about protection? → **Warn them**
- [ ] Should I use sandbox instead? → **Consider sandbox**
- [ ] Am I making minimal changes? → **Keep it minimal**

---

## 🔄 Workflow Examples

### Example 1: Adding New Feature

```bash
# 1. Create sandbox
./create_sandbox.sh new_dashboard

# 2. Work in sandbox
cd sandboxes/new_dashboard
# Make changes, test

# 3. Merge approved changes
cp templates/new_dashboard.html ../templates/
# Test in main, commit
```

### Example 2: Fixing Bug in Protected File

```bash
# 1. Check if file is protected
grep "account_management.html" .cursorignore
# → File is protected

# 2. Ask user for permission
# "File is protected. May I modify it to fix [bug]?"

# 3. If approved, unprotect temporarily
./unprotect_files.sh

# 4. Make minimal fix
# Edit file

# 5. Test thoroughly

# 6. Re-protect
./protect_files.sh
```

### Example 3: Emergency Restore

```bash
# Main project broke, restore from backup
git checkout working-state-dec-2025

# Or restore specific file
cp backups/2025-11-25/account_management.html templates/
```

---

## 🛠️ Maintenance

### Adding New Protected Files

1. Add to `.cursorignore`
2. Add to `protect_files.sh` script
3. Document in `PROTECTION_SYSTEM.md`
4. Create snapshot if needed
5. Update `.cursorrules` if needed

### Updating Protection Rules

1. Update `.cursorrules` with new rules
2. Update `.cursorignore` with new files
3. Update `protect_files.sh` script
4. Update this documentation
5. Commit changes

### Creating New Snapshots

1. Create snapshot document (e.g., `FEATURE_SNAPSHOT.md`)
2. Add to `.cursorignore`
3. Create backup in `backups/`
4. Create git tag
5. Update `BACKUP_INDEX.md`

---

## 🚨 Emergency Procedures

### If Protected File Was Modified

1. **STOP** making changes
2. **RESTORE** from backup:
   ```bash
   cp backups/YYYY-MM-DD/filename.ext .
   ```
3. **VERIFY** restoration worked
4. **INFORM** user what happened
5. **REVIEW** what went wrong

### If Main Project Broke

1. **STOP** making changes
2. **RESTORE** from git tag:
   ```bash
   git checkout working-state-dec-2025
   ```
3. **TEST** that restore worked
4. **INFORM** user
5. **IDENTIFY** what broke
6. **FIX** in sandbox first, then merge

---

## 📚 Reference Documents

- **`.cursorrules`** - AI assistant rules
- **`.cursorignore`** - Protected files list
- **`WHAT_NOT_TO_DO.md`** - Past mistakes
- **`PRE_CHANGE_CHECKLIST.md`** - Mandatory checklist
- **`ACCOUNT_MGMT_SNAPSHOT.md`** - Account management baseline
- **`CURRENT_STATUS_SNAPSHOT.md`** - Current state
- **`SANDBOX_WORKFLOW.md`** - Sandbox usage guide
- **`BACKUP_INDEX.md`** - Backup locations

---

## ✅ Protection Status

- ✅ Cursor rules active
- ✅ Cursor ignore active
- ✅ File protection scripts ready
- ✅ Documentation snapshots created
- ✅ Git tags created
- ✅ Backups system active
- ✅ Sandbox system ready

---

**Last Updated**: December 2025  
**Status**: All protection layers active

