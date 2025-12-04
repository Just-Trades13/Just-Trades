# ⛔ WHAT NOT TO DO - LEARN FROM PAST MISTAKES ⛔

## This file documents ALL mistakes that have broken this codebase.
## READ THIS BEFORE MAKING ANY CHANGES.

---

## ❌ MISTAKE 1: Bulk Refactoring Working Code

**What happened:**
AI decided to "improve" code formatting, variable names, and structure across multiple files.
Result: Broke working features, introduced bugs, lost critical functionality.

**Rule:** 
NEVER refactor code that is working. If it works, leave it alone.

---

## ❌ MISTAKE 2: Modifying Multiple Tabs at Once

**What happened:**
User asked to fix something in Manual Trader tab.
AI also "helpfully" modified Dashboard and Control Center "to be consistent."
Result: Manual Trader fixed, but Dashboard and Control Center broken.

**Rule:**
ONE TAB AT A TIME. Only modify files belonging to the tab user requested.

---

## ❌ MISTAKE 3: Changing Database Schema

**What happened:**
AI added new columns to database tables without asking.
Result: Existing queries failed, data lost, features broken.

**Rule:**
NEVER modify database schema without explicit user approval.

---

## ❌ MISTAKE 4: Removing "Unused" Code

**What happened:**
AI identified code it thought was "dead" or "unused" and removed it.
Result: That code was actually used by other parts of the system. Features broke.

**Rule:**
NEVER remove code you didn't write. Even if it looks unused, it might be used elsewhere.

---

## ❌ MISTAKE 5: Making Unauthorized Changes

**What happened:**
AI made changes without asking user first.
Result: Working features broke, user had to spend hours debugging.

**Rule:**
ALWAYS ask before modifying any file. Wait for explicit "yes" before proceeding.

---

## ❌ MISTAKE 6: Overwriting Backup Files

**What happened:**
AI "helpfully" updated backup files with "current" code.
Result: Backups now contained broken code, no way to restore.

**Rule:**
NEVER modify or overwrite backup files in backups/ directory.

---

## ❌ MISTAKE 7: Changing Core Functions

**What happened:**
AI modified core functions like fetch_tradovate_pnl_sync() to "improve" them.
Result: Live positions stopped displaying, PnL calculations broke.

**Rule:**
NEVER modify core functions without explicit approval and thorough testing.

---

## ❌ MISTAKE 8: Ignoring Tab Isolation

**What happened:**
AI modified templates/account_management.html while working on Manual Trader.
Result: Account management completely broke, tokens stopped saving.

**Rule:**
STRICT TAB ISOLATION. Only modify files for the tab you're working on.

---

## ❌ MISTAKE 9: Adding "Helpful" Features

**What happened:**
AI added features it thought would be helpful, but were not requested.
Result: New features conflicted with existing ones, broke working functionality.

**Rule:**
ONLY implement what user explicitly requests. No "bonus" features.

---

## ❌ MISTAKE 10: Not Testing After Changes

**What happened:**
AI made changes and declared them "done" without verifying they worked.
Result: User discovered broken features later.

**Rule:**
ALWAYS verify changes work before declaring them complete.

---

## ✅ WHAT TO DO INSTEAD

1. **ASK FIRST**: "Can I modify [file] to [do X]?"
2. **WAIT FOR APPROVAL**: Do not proceed until user says yes
3. **MAKE ONE CHANGE**: Single file, single purpose
4. **TEST IMMEDIATELY**: Verify the change works
5. **REPORT RESULTS**: Tell user if it worked or failed
6. **IF BROKEN, RESTORE**: Use backups, do not try to "fix" blindly

---

## 🔧 RECOVERY PROCEDURE

If you broke something:

1. STOP making changes
2. Tell user what you broke
3. Restore from backup:
   cp backups/WORKING_STATE_DEC3_2025/[broken_file] ./
   OR
   git checkout WORKING_DEC3_2025 -- [broken_file]
4. Restart server if needed
5. Verify restoration worked

---

## 📅 WORKING STATE BACKUPS

| Date | Tag/Location | Status |
|------|--------------|--------|
| Dec 3, 2025 | backups/WORKING_STATE_DEC3_2025/ | ✅ All features working |
| Dec 3, 2025 | git tag WORKING_DEC3_2025 | ✅ All features working |

---

*Last updated: Dec 3, 2025*
