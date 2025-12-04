# Tab Isolation System - Summary

**CRITICAL RULE**: When working on a tab, ONLY modify files for that tab. Never touch other tabs' files.

---

## ✅ What's Been Created

### 1. Tab Isolation Map
- ✅ `TAB_ISOLATION_MAP.md` - Complete mapping of tabs to their files
- ✅ Lists allowed files for each tab
- ✅ Lists forbidden files (other tabs' files)
- ✅ Identifies shared files that need special permission

### 2. Updated Cursor Rules
- ✅ `.cursorrules` - Enhanced with mandatory tab isolation rules
- ✅ Clear examples of correct vs. wrong behavior
- ✅ Red flags to stop immediately

### 3. Updated Quick Reference
- ✅ `QUICK_PROTECTION_REFERENCE.md` - Includes tab isolation checklist

---

## 🎯 How It Works

### When User Says: "Fix trailing stop in manual trader"

**✅ CORRECT Workflow:**
1. Identify tab: **Manual Trader** (`/manual-trader`)
2. Check `TAB_ISOLATION_MAP.md`:
   - ✅ Allowed: `templates/manual_copy_trader.html`, `/api/manual-trade` endpoint
   - ❌ Forbidden: `templates/account_management.html`, `templates/control_center.html`
3. Modify ONLY allowed files
4. Do NOT touch forbidden files

**❌ WRONG Workflow:**
1. Identify tab: **Manual Trader**
2. Modify `templates/manual_copy_trader.html` ✅
3. Also modify `templates/control_center.html` "to keep them consistent" ❌
4. **STOP** - You're modifying another tab's files!

---

## 🚨 Tab Isolation Rules

### Mandatory Rules:
1. **Identify the tab** you're working on
2. **Check `TAB_ISOLATION_MAP.md`** for allowed files
3. **ONLY modify files** listed for that tab
4. **NEVER modify files** from other tabs
5. **NEVER "improve"** other tabs "while you're at it"
6. **WARN user** if you need to modify shared files
7. **ASK permission** before touching forbidden files

### Red Flags - STOP:
- 🔴 Modifying a file not in the tab's allowed list
- 🔴 "Improving" code in another tab "while you're at it"
- 🔴 Modifying shared files without explicit permission
- 🔴 User says "work on Tab A" but you're modifying Tab B

---

## 📋 Tab List

1. **Account Management** (`/accounts`) - **LOCKED**
2. **Manual Trader** (`/manual-trader`)
3. **Control Center** (`/control-center`)
4. **Dashboard** (`/dashboard`)
5. **Strategies** (`/strategies`)
6. **Recorders** (`/recorders`)
7. **Traders** (`/traders`)
8. **Settings** (`/settings`)

See `TAB_ISOLATION_MAP.md` for complete file mappings.

---

## 🛡️ Shared Files (Handle with Caution)

- `templates/layout.html` - Used by ALL tabs
- `ultra_simple_server.py` - Shared functions
- `phantom_scraper/tradovate_integration.py` - Core integration
- `static/` - Shared assets

**Rule**: Only modify if user **explicitly requests** it.

---

## 📚 Documentation

- **Full Map**: `TAB_ISOLATION_MAP.md`
- **Cursor Rules**: `.cursorrules` (includes tab isolation)
- **Quick Reference**: `QUICK_PROTECTION_REFERENCE.md`
- **Protection System**: `PROTECTION_SYSTEM.md`

---

**Status**: ✅ Active - All AI assistants must follow tab isolation rules

