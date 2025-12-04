# 🚨 MANDATORY: READ BEFORE ANY CODE CHANGES 🚨

## ⛔ ABSOLUTE RULES - VIOLATION = BROKEN CODE

### RULE 1: NEVER MODIFY THESE FILES WITHOUT EXPLICIT USER PERMISSION
```
LOCKED FILES - DO NOT TOUCH:
├── ultra_simple_server.py          ← CORE SERVER - ASK FIRST
├── templates/manual_copy_trader.html   ← MANUAL TRADER - ASK FIRST
├── templates/account_management.html   ← ACCOUNT MGMT - NEVER TOUCH
├── templates/recorders.html            ← RECORDERS - ASK FIRST
├── templates/recorders_list.html       ← RECORDERS LIST - ASK FIRST
├── templates/dashboard.html            ← DASHBOARD - ASK FIRST
├── templates/control_center.html       ← CONTROL CENTER - ASK FIRST
└── just_trades.db                      ← DATABASE - NEVER MODIFY SCHEMA
```

### RULE 2: BEFORE ANY CHANGE, YOU MUST:
1. ✅ **ASK USER**: "I want to modify [filename]. Is this okay?"
2. ✅ **WAIT FOR APPROVAL** before touching any code
3. ✅ **EXPLAIN WHAT YOU WILL CHANGE** before changing it
4. ✅ **MAKE ONE SMALL CHANGE AT A TIME** - not bulk edits

### RULE 3: THINGS YOU MUST NEVER DO
- ❌ **NEVER** refactor code that's working
- ❌ **NEVER** "improve" or "clean up" existing code
- ❌ **NEVER** remove code you think is "unused"
- ❌ **NEVER** change indentation or formatting of working code
- ❌ **NEVER** modify files in other tabs while working on one tab
- ❌ **NEVER** add "helpful" features not explicitly requested
- ❌ **NEVER** change database schemas without explicit approval
- ❌ **NEVER** delete or overwrite backup files

### RULE 4: IF YOU BREAK SOMETHING
1. **STOP IMMEDIATELY**
2. **TELL THE USER WHAT YOU BROKE**
3. **RESTORE FROM BACKUP**: `backups/WORKING_STATE_DEC3_2025/`
4. **OR USE GIT**: `git checkout WORKING_DEC3_2025 -- <filename>`

---

## 🔒 WORKING STATE BACKUP (Dec 3, 2025)

**Everything below is CONFIRMED WORKING. Do not break it.**

### Backup Location
```
backups/WORKING_STATE_DEC3_2025/
├── ultra_simple_server.py
├── manual_copy_trader.html
├── recorders.html
├── recorders_list.html
├── dashboard.html
├── control_center.html
├── account_management.html
└── just_trades.db
```

### Git Tag
```bash
git tag WORKING_DEC3_2025
# To restore any file:
git checkout WORKING_DEC3_2025 -- templates/manual_copy_trader.html
```

---

## ✅ WHAT'S WORKING (DO NOT BREAK)

| Feature | Status | Files Involved |
|---------|--------|----------------|
| **Manual Trader** | ✅ Working | `manual_copy_trader.html`, server routes |
| **Live Position Cards** | ✅ Working | WebSocket `position_update` event |
| **Account PnL Display** | ✅ Working | `fetch_tradovate_pnl_sync()` |
| **Recorders Tab** | ✅ Working | `recorders.html`, `recorders_list.html` |
| **Webhook Signals** | ✅ Working | `/webhook/<token>` endpoint |
| **Trade Recording** | ✅ Working | `recorded_signals`, `recorded_trades` tables |
| **Dashboard** | ✅ Working | `dashboard.html` |
| **Control Center** | ✅ Working | `control_center.html` |
| **Account Management** | ✅ Working | `account_management.html` - NEVER TOUCH |
| **Tradovate OAuth** | ✅ Working | OAuth flow in server |
| **WebSocket Updates** | ✅ Working | `emit_realtime_updates()` |
| **Copy Trading** | ✅ Working | Copy trader logic in manual trader |

---

## 📋 TAB ISOLATION RULES

**When user says "work on X tab", ONLY modify files for that tab:**

| Tab | Allowed Files |
|-----|---------------|
| Manual Trader | `manual_copy_trader.html`, `/api/manual-trade` route |
| Recorders | `recorders.html`, `recorders_list.html`, recorder routes |
| Dashboard | `dashboard.html`, dashboard API routes |
| Control Center | `control_center.html`, control center routes |
| Account Management | **NEVER TOUCH** - It's locked |
| Settings | `settings.html` only |

**🚨 NEVER modify files from OTHER tabs while working on one tab!**

---

## 🛠️ HOW TO MAKE SAFE CHANGES

### Step 1: Ask Permission
```
"I need to modify [filename] to [do X]. Is this okay?"
```

### Step 2: Wait for User Approval
Do not proceed until user says "yes" or "go ahead"

### Step 3: Make ONE Small Change
- Edit only the specific lines needed
- Do not touch surrounding code
- Do not "improve" other parts

### Step 4: Test Immediately
- Verify the feature works
- Check server logs for errors
- Confirm no regressions

### Step 5: If Something Breaks
```bash
# Restore from backup
cp backups/WORKING_STATE_DEC3_2025/[filename] templates/[filename]

# Or use git
git checkout WORKING_DEC3_2025 -- [filename]
```

---

## 🚫 PAST MISTAKES (LEARN FROM THESE)

### Mistake 1: Bulk Refactoring
**What happened**: AI "improved" working code, broke everything
**Rule**: NEVER refactor working code

### Mistake 2: Modifying Multiple Tabs
**What happened**: AI fixed one tab but broke three others
**Rule**: ONE TAB AT A TIME

### Mistake 3: Changing Database Schema
**What happened**: AI added columns, broke existing queries
**Rule**: NEVER change schema without approval

### Mistake 4: Removing "Unused" Code
**What happened**: AI removed code it thought was unused, broke features
**Rule**: NEVER remove code you didn't write

### Mistake 5: Overwriting Backups
**What happened**: AI overwrote backup with broken code
**Rule**: NEVER modify backup files

---

## 📞 QUICK REFERENCE

### Restore Working State
```bash
# Restore single file
cp backups/WORKING_STATE_DEC3_2025/ultra_simple_server.py ./

# Restore all templates
cp backups/WORKING_STATE_DEC3_2025/*.html templates/

# Full git restore
git checkout WORKING_DEC3_2025
```

### Check Server Status
```bash
pgrep -f "python.*ultra_simple"  # Is server running?
tail -50 /tmp/server.log         # Recent logs
```

### Restart Server
```bash
pkill -f "python.*ultra_simple"
nohup python3 ultra_simple_server.py > /tmp/server.log 2>&1 &
```

---

## 🔐 CHECKSUMS (Verify File Integrity)

Run this to verify files haven't been corrupted:
```bash
md5 ultra_simple_server.py templates/*.html
```

Expected (Dec 3, 2025 working state):
- Store checksums after confirming working state

---

## ⚠️ FINAL WARNING

**This codebase has been broken multiple times by AI making unauthorized changes.**

**EVERY CHANGE REQUIRES:**
1. User permission
2. Clear explanation of what will change
3. Single-file, minimal edits
4. Immediate testing
5. Rollback plan ready

**If in doubt, ASK THE USER FIRST.**

---

*Last updated: Dec 3, 2025 - All features confirmed working*
*Backup tag: WORKING_DEC3_2025*
