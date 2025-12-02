# Backup Index - All Saved States

This document tracks all backups and snapshots of the working codebase.

---

## Git Tags

### `working-state-dec-2025`
- **Date**: December 2025
- **Description**: Working state snapshot - Manual trader, account management, risk controls (TP/SL working, trailing/breakeven in progress)
- **Restore**: `git checkout working-state-dec-2025`

---

## File Backups

### `backups/2025-11-25/`
- **Date**: November 25, 2025
- **Purpose**: Account Management baseline (DO NOT TOUCH)
- **Files**:
  - `account_management.html`
  - `ultra_simple_server.py`
- **Reference**: `ACCOUNT_MGMT_SNAPSHOT.md`

### `backups/YYYY-MM-DD/` (Daily Backups)
- **Purpose**: Daily backups of all key files
- **Files**:
  - `ultra_simple_server.py`
  - `templates/manual_copy_trader.html`
  - `templates/account_management.html`
  - `templates/control_center.html`
  - `templates/layout.html`
  - `phantom_scraper/tradovate_integration.py`

---

## Documentation Snapshots

### `HANDOFF_DOCUMENT.md`
- **Purpose**: Main handoff document with current state
- **Last Updated**: December 2025
- **Status**: ✅ Updated with current features

### `WHAT_NOT_TO_DO.md`
- **Purpose**: Lessons learned - what NOT to do
- **Status**: ✅ Current

### `PRE_CHANGE_CHECKLIST.md`
- **Purpose**: Mandatory checklist before making changes
- **Status**: ✅ Current

### `ACCOUNT_MGMT_SNAPSHOT.md`
- **Purpose**: Account management baseline (DO NOT TOUCH)
- **Status**: ✅ Locked baseline

### `CURRENT_STATUS_SNAPSHOT.md`
- **Purpose**: Comprehensive current state snapshot
- **Status**: ✅ Just created (December 2025)

---

## How to Restore

### Restore from Git Tag
```bash
git checkout working-state-dec-2025
```

### Restore from File Backup
```bash
cp backups/YYYY-MM-DD/ultra_simple_server.py .
cp backups/YYYY-MM-DD/templates/*.html templates/
cp backups/YYYY-MM-DD/phantom_scraper/tradovate_integration.py phantom_scraper/
```

### Restore Account Management Baseline
```bash
cp backups/2025-11-25/account_management.html templates/
cp backups/2025-11-25/ultra_simple_server.py .
```

---

## Key Files to Always Backup

1. `ultra_simple_server.py` - Main backend
2. `templates/manual_copy_trader.html` - Manual trader UI
3. `templates/account_management.html` - Account management UI
4. `templates/control_center.html` - Control center
5. `templates/layout.html` - Base layout
6. `phantom_scraper/tradovate_integration.py` - Tradovate integration

---

**Last Updated**: December 2025

