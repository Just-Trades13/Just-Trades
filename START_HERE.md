# ⚠️ CRITICAL: READ THIS FIRST - MANDATORY FOR ALL AI ASSISTANTS

**THIS FILE MUST BE READ BEFORE ANY CODE CHANGES**

---

## 🚨 MANDATORY RULES - NO EXCEPTIONS

**If you are an AI assistant, chat context, or any automated system working on this codebase, you MUST:**

1. **READ THIS FILE FIRST** - Before making ANY changes
2. **READ `.cursorrules`** - Contains all protection rules
3. **READ `TAB_ISOLATION_MAP.md`** - **CRITICAL**: Only modify files for the tab you're working on
4. **READ `WHAT_NOT_TO_DO.md`** - Past mistakes to avoid
5. **READ `PRE_CHANGE_CHECKLIST.md`** - Mandatory checklist
6. **READ `ACCOUNT_MGMT_SNAPSHOT.md`** - Account management is LOCKED

---

## 🔒 PROTECTION RULES - ALWAYS ENFORCE

### Rule 1: Tab Isolation (MANDATORY)
- **ONLY modify files for the tab you're working on**
- **NEVER modify files from other tabs**
- **Check `TAB_ISOLATION_MAP.md`** before modifying ANY file
- **STOP if you're about to modify another tab's files**

### Rule 2: Protected Files (MANDATORY)
- `templates/account_management.html` - **LOCKED, DO NOT MODIFY**
- Account management functions - **PROTECTED**
- Core integration methods - **PROTECTED**
- **Check `.cursorignore`** for protected files
- **ASK permission** before modifying protected files

### Rule 3: Verify Before Fixing (MANDATORY)
- **VERIFY the problem exists** before fixing
- **DON'T fix things that aren't broken**
- **DON'T "improve" working code**
- **DON'T refactor without explicit request**

### Rule 4: One Change at a Time (MANDATORY)
- **Make ONE small change at a time**
- **Test after each change**
- **DON'T make multiple changes at once**
- **DON'T modify multiple tabs simultaneously**

---

## 🚨 RED FLAGS - STOP IMMEDIATELY

**STOP if:**
- 🔴 You're about to modify a file not in the tab's allowed list
- 🔴 You're about to "improve" code in another tab
- 🔴 You're about to modify a protected file without permission
- 🔴 User says "work on Tab A" but you're modifying Tab B
- 🔴 You think "this change would help other tabs too"
- 🔴 File is in `.cursorignore`
- 🔴 File is listed in `ACCOUNT_MGMT_SNAPSHOT.md`

**IF YOU SEE RED FLAGS:**
1. **STOP making changes immediately**
2. **ASK user for explicit permission**
3. **Reference protection documentation**
4. **Suggest using sandbox instead**

---

## 📋 MANDATORY CHECKLIST - BEFORE ANY CHANGE

- [ ] **Which tab am I working on?** (Check `TAB_ISOLATION_MAP.md`)
- [ ] **Is this file in that tab's allowed list?** (If no, STOP)
- [ ] **Is this file from another tab?** (If yes, STOP)
- [ ] **Is this file protected?** (Check `.cursorignore`, `ACCOUNT_MGMT_SNAPSHOT.md`)
- [ ] **Have I read `WHAT_NOT_TO_DO.md`?** (Read it first)
- [ ] **Have I read `PRE_CHANGE_CHECKLIST.md`?** (Read it first)
- [ ] **Have I verified the problem exists?** (Verify first)
- [ ] **Am I making minimal changes?** (One change at a time)
- [ ] **Am I about to modify another tab's files?** (If yes, STOP)

**If ANY checkbox is unchecked, STOP and complete it first.**

---

## 📚 REQUIRED READING (In Order)

1. **`START_HERE.md`** - This file (you're reading it)
2. **`.cursorrules`** - Complete protection rules
3. **`TAB_ISOLATION_MAP.md`** - Tab-to-files mapping
4. **`WHAT_NOT_TO_DO.md`** - Past mistakes
5. **`PRE_CHANGE_CHECKLIST.md`** - Mandatory checklist
6. **`ACCOUNT_MGMT_SNAPSHOT.md`** - Locked baseline
7. **`CURRENT_STATUS_SNAPSHOT.md`** - Current state
8. **`QUICK_PROTECTION_REFERENCE.md`** - Quick reference

---

## 🛡️ PROTECTION LAYERS

This project has **7 layers of protection**:

1. **Tab Isolation** - Only modify files for the tab you're working on
2. **Cursor Rules** - AI assistant rules (`.cursorrules`)
3. **Cursor Ignore** - Protected files list (`.cursorignore`)
4. **File Permissions** - Read-only protection (`protect_files.sh`)
5. **Documentation Snapshots** - Locked baselines
6. **Git Tags & Backups** - Restore points
7. **Sandbox System** - Isolated development

**ALL layers must be respected. NO EXCEPTIONS.**

---

## ⚠️ CONSEQUENCES OF VIOLATING RULES

**If you violate these rules:**
- ❌ You will break working code
- ❌ You will cause regressions
- ❌ You will waste time fixing what you broke
- ❌ You will lose user trust

**The user cannot afford to break working code. These rules exist for a reason.**

---

## ✅ CORRECT WORKFLOW

### Example: User says "Fix trailing stop in manual trader"

**Step 1: Identify Tab**
- Tab: **Manual Trader** (`/manual-trader`)

**Step 2: Check Tab Isolation Map**
- Allowed files: `templates/manual_copy_trader.html`, `/api/manual-trade` endpoint
- Forbidden files: `templates/account_management.html`, `templates/control_center.html`

**Step 3: Verify Problem**
- Check if trailing stop is actually broken
- Don't fix if it's working

**Step 4: Make Minimal Change**
- Modify ONLY `templates/manual_copy_trader.html` and `/api/manual-trade` endpoint
- Do NOT touch other files
- Do NOT "improve" other tabs

**Step 5: Test**
- Test the change
- Verify nothing else broke

---

## 🚫 WRONG WORKFLOW (DON'T DO THIS)

### Example: User says "Fix trailing stop in manual trader"

**❌ WRONG:**
1. Modify `templates/manual_copy_trader.html` ✅
2. Also modify `templates/control_center.html` "to keep them consistent" ❌
3. Also "improve" account management "while you're at it" ❌
4. Refactor shared code "to make it better" ❌

**STOP - You're violating tab isolation and protection rules!**

---

## 📞 IF YOU'RE UNSURE

**When in doubt:**
1. **STOP making changes**
2. **ASK the user for clarification**
3. **Reference the protection documentation**
4. **Suggest using sandbox for experiments**
5. **NEVER assume it's okay to modify protected files**

---

## 🔄 ENFORCEMENT

**These rules are enforced by:**
- `.cursorrules` - Read by Cursor AI automatically
- `TAB_ISOLATION_MAP.md` - Tab isolation enforcement
- `.cursorignore` - Protected files list
- Documentation snapshots - Locked baselines
- Git tags - Restore points

**If you bypass these rules, you will break working code.**

---

## 📝 REMEMBER

1. **Tab isolation is MANDATORY** - Only modify files for the tab you're working on
2. **Protected files are LOCKED** - Don't modify without explicit permission
3. **Verify before fixing** - Don't fix things that aren't broken
4. **One change at a time** - Make minimal, focused changes
5. **When in doubt, ASK** - Don't assume it's okay

---

**THIS IS NOT OPTIONAL. THESE RULES MUST BE FOLLOWED BY ALL AI ASSISTANTS, CHAT CONTEXTS, AND AUTOMATED SYSTEMS.**

**Last Updated**: December 2025  
**Status**: ACTIVE - All AI assistants must read this first

