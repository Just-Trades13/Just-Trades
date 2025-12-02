# Quick Protection Reference

**One-page guide for AI assistants and developers**

---

## 🚨 STOP BEFORE MODIFYING

**Check these FIRST:**
1. ✅ **IDENTIFY which tab** you're working on
2. ✅ **READ `TAB_ISOLATION_MAP.md`** - Which files belong to this tab?
3. ✅ Read `.cursorrules` (auto-loaded by Cursor)
4. ✅ Check `.cursorignore` - Is file listed?
5. ✅ Read `WHAT_NOT_TO_DO.md` - Am I repeating a mistake?
6. ✅ Read `PRE_CHANGE_CHECKLIST.md` - Have I verified the problem?
7. ✅ Check protection docs - Is file protected?
8. ✅ **Is this file in the tab's allowed list?** - If not, STOP

**If file is protected:**
- ⚠️ **WARN user** that file is protected
- ⚠️ **ASK for explicit permission**
- ⚠️ **Consider using sandbox** instead

**If file is from another tab:**
- ⚠️ **STOP IMMEDIATELY** - Do NOT modify other tabs' files
- ⚠️ **Only modify files for the tab you're working on**

---

## 🔒 Protected Files

### Fully Locked
- `templates/account_management.html` - **DO NOT MODIFY**

### Protected Functions
- Account management functions in `ultra_simple_server.py`
- Core methods in `phantom_scraper/tradovate_integration.py`

---

## 🛠️ Quick Commands

### Protect Files
```bash
./protect_files.sh      # Make protected files read-only
./unprotect_files.sh    # Restore write permissions (use with caution)
```

### Create Sandbox
```bash
./create_sandbox.sh my_feature    # Create isolated copy
cd sandboxes/my_feature            # Work in sandbox
```

### Restore from Backup
```bash
# From git tag
git checkout working-state-dec-2025

# From file backup
cp backups/2025-11-25/account_management.html templates/
```

---

## 📚 Full Documentation

- **Protection System**: `PROTECTION_SYSTEM.md`
- **Sandbox Workflow**: `SANDBOX_WORKFLOW.md`
- **What Not To Do**: `WHAT_NOT_TO_DO.md`
- **Pre-Change Checklist**: `PRE_CHANGE_CHECKLIST.md`
- **Account Baseline**: `ACCOUNT_MGMT_SNAPSHOT.md`
- **Current State**: `CURRENT_STATUS_SNAPSHOT.md`

---

## ✅ Protection Checklist

Before modifying ANY file:
- [ ] **Which tab am I working on?**
- [ ] **Is this file in that tab's allowed list?** (Check `TAB_ISOLATION_MAP.md`)
- [ ] **Is this file from another tab?** (If yes, STOP - do not modify)
- [ ] File not in `.cursorignore`?
- [ ] File not in protection docs?
- [ ] Read `WHAT_NOT_TO_DO.md`?
- [ ] Read `PRE_CHANGE_CHECKLIST.md`?
- [ ] Verified problem exists?
- [ ] Asked permission if protected?
- [ ] **Am I about to modify another tab's files?** (If yes, STOP)

---

**Remember**: When in doubt, ASK before modifying protected files.

