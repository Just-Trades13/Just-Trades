# Clean Migration Guide - Just.Trades Platform Only

**Migrating ONLY the Just.Trades platform, excluding unrelated projects**

---

## 🎯 What This Migration Includes

### ✅ Core Platform Files (Included)

**Application Core:**
- `ultra_simple_server.py` - Main Flask server
- `templates/` - All web interface templates (dashboard, account management, manual trader, etc.)
- `static/` - Static assets (CSS, JavaScript, images)
- `phantom_scraper/` - Tradovate integration code
- `just_trades.db` - Database
- `requirements.txt` - Python dependencies
- `openapi.json` - Tradovate API specification

**Protection System:**
- `.cursorrules` - Cursor AI rules
- `.cursorignore` - Protected files list
- `.ai_rules` - AI rules
- All protection documentation (START_HERE.md, TAB_ISOLATION_MAP.md, etc.)

**Scripts:**
- `create_sandbox.sh` - Sandbox creation
- `protect_files.sh` - File protection
- `restart_server.sh` - Server restart
- `start_server.sh` - Server start

**Project Management:**
- `backups/` - Project backups
- `sandboxes/` - Sandbox environments
- `.git/` - Git repository (if exists)

**Documentation:**
- Platform documentation only
- Protection system docs
- Migration guides

---

## ❌ What This Migration Excludes

**Unrelated Projects:**
- ❌ Package folders (Package 2A, Package 3A, etc.)
- ❌ `pnl_test_project/` - Test project
- ❌ Apollo-related files and documentation
- ❌ Airtable-related files and documentation
- ❌ HELOC-related files and documentation
- ❌ Other unrelated markdown files
- ❌ Other test projects

**System Files:**
- ❌ `venv/` - Virtual environment (recreate in new location)
- ❌ `__pycache__/` - Python cache (regenerated)
- ❌ `*.pyc` - Compiled Python files

---

## 🚀 Quick Migration

### Run Clean Migration Script

```bash
# Make script executable (if not already)
chmod +x migrate_project_clean.sh

# Run migration (uses default: ~/just-trades-platform)
./migrate_project_clean.sh

# Or specify custom location
./migrate_project_clean.sh /path/to/new/location
```

---

## 📋 What Gets Copied

### Core Application
```
just-trades-platform/
├── ultra_simple_server.py      # Main server
├── templates/                  # Web interface
│   ├── dashboard.html
│   ├── account_management.html
│   ├── manual_copy_trader.html
│   ├── control_center.html
│   └── ...
├── static/                     # Static assets
├── phantom_scraper/           # Integration code
├── just_trades.db             # Database
├── requirements.txt           # Dependencies
└── openapi.json              # API spec
```

### Protection System
```
├── .cursorrules              # Cursor AI rules
├── .cursorignore             # Protected files
├── .ai_rules                 # AI rules
├── START_HERE.md            # Entry point
├── TAB_ISOLATION_MAP.md     # Tab isolation
└── [other protection docs]
```

### Scripts & Tools
```
├── create_sandbox.sh
├── protect_files.sh
├── restart_server.sh
└── start_server.sh
```

---

## ✅ Post-Migration Steps

### 1. Navigate to New Location
```bash
cd ~/just-trades-platform
# or
cd /Users/mylesjadwin/just-trades-platform
```

### 2. Verify Files
```bash
ls -la
# Should see only Just.Trades platform files
```

### 3. Recreate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Test Server
```bash
python3 ultra_simple_server.py
# Should start on http://localhost:8082
```

### 5. Update External References
- **ngrok**: Update configuration or restart
- **Bookmarks**: Update browser bookmarks
- **Scripts**: Update any scripts referencing old path

### 6. Open in Cursor
- Open new folder in Cursor
- All protection rules will still work automatically

---

## 🔍 Verification Checklist

After migration, verify:

- [ ] Only Just.Trades files present (no Package folders, no pnl_test_project)
- [ ] Server starts without errors
- [ ] Database accessible (`just_trades.db` exists)
- [ ] Templates load correctly
- [ ] Protection rules work (`.cursorrules` loaded)
- [ ] Git history intact (if `.git` was copied)
- [ ] No unrelated files in new location
- [ ] Virtual environment recreated
- [ ] Dependencies installed

---

## 🎯 Benefits of Clean Migration

✅ **Clean Environment** - Only Just.Trades platform files
✅ **No Clutter** - Unrelated projects stay in old location
✅ **Easy to Navigate** - Clear project structure
✅ **Better Organization** - Isolated from other work
✅ **Easier Backup** - Can backup entire clean folder
✅ **Easier Deployment** - Self-contained project

---

## 📝 Migration Log

After migration, check `MIGRATION_LOG.md` in the new location for:
- What was copied
- What was excluded
- Next steps
- Important notes

---

## ⚠️ Important Notes

1. **Old Location Preserved** - Old location still exists until you verify everything works
2. **Unrelated Files Stay** - Unrelated projects remain in old location
3. **Clean Start** - New location contains ONLY Just.Trades platform
4. **Protection Rules Work** - All protection rules still active in new location
5. **Git History** - Preserved if `.git` was copied

---

## 🔄 Rollback Plan

If something goes wrong:

1. **Old location still exists** - Can switch back
2. **Compare files** - Check what's different
3. **Restore from Git** - If git history was copied
4. **Re-migrate** - Run script again

---

**Last Updated**: December 2025  
**Status**: Ready for clean migration

