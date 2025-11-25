# 🔄 RESTORE FROM BASELINE - Quick Guide

**If another context window breaks things, use this to restore.**

---

## Quick Restore Steps

### 1. Read the Baseline
```bash
cat WORKING_STATE_BASELINE.md
```

### 2. Restore the File
```bash
cp templates/control_center.html.BACKUP templates/control_center.html
```

### 3. Verify Key Sections

#### Accounts (Lines 15-19):
```html
<select id="manualAccountSelect" required>
    <option value="">Select account...</option>
    <option value="1:26029294">Mark - DEMO4419847-2 (Demo)</option>
    <option value="1:544727">Mark - 1381296 (Live)</option>
</select>
```

#### Button Handlers (Lines 446-481):
- Must be in main DOMContentLoaded (line 413)
- Must have `e.preventDefault()`
- Must have console logging

### 4. Test
1. Refresh page (hard refresh: Cmd+Shift+R)
2. Check console: "Setting up button handlers"
3. Click Buy/Sell
4. Check console: "Buy button clicked" or "Sell button clicked"

---

## What to Check If It's Broken

### Accounts Missing?
- Check lines 17-18 have hardcoded accounts
- Check `loadAccountsForManualTrader()` isn't clearing them

### Buttons Not Working?
- Check button handlers are in main DOMContentLoaded (line 413)
- Check console for "Setting up button handlers"
- Check console for errors when clicking
- Verify `placeManualTrade()` function exists (line 559)

### No Console Logs?
- Check browser console is open (F12)
- Check JavaScript isn't blocked
- Check for syntax errors in console

---

## Files to Restore

1. `templates/control_center.html` - Main file
2. `templates/control_center.html.BACKUP` - Backup copy

---

**Quick Command:**
```bash
# Restore from backup
cp templates/control_center.html.BACKUP templates/control_center.html

# Verify accounts are hardcoded
grep -A 3 "manualAccountSelect" templates/control_center.html | head -5

# Verify button handlers exist
grep -A 5 "Manual Trader button handlers" templates/control_center.html
```

---

**Last Updated**: November 18, 2025
**Baseline**: WORKING_STATE_BASELINE.md


