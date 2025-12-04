# Project Migration Guide

**Moving Just.Trades Trading Platform to its own isolated folder**

---

## 🎯 Goal

Move the project from:
- **Current**: `/Users/mylesjadwin/Trading Projects`

To its own isolated folder:
- **Recommended**: `~/just-trades-platform` or `/Users/mylesjadwin/just-trades-platform`

---

## 🚀 Quick Migration

### Option 1: Automated Script (Recommended)

```bash
# Make script executable
chmod +x migrate_project.sh

# Run migration (uses default: ~/just-trades-platform)
./migrate_project.sh

# Or specify custom location
./migrate_project.sh /path/to/new/location
```

### Option 2: Manual Migration

```bash
# 1. Create new directory
mkdir -p ~/just-trades-platform
cd ~/just-trades-platform

# 2. Copy project files
cp -r "/Users/mylesjadwin/Trading Projects"/* .

# 3. Copy hidden files
cp -r "/Users/mylesjadwin/Trading Projects"/.cursor* .
cp -r "/Users/mylesjadwin/Trading Projects"/.ai_rules .
cp -r "/Users/mylesjadwin/Trading Projects"/.git .

# 4. Verify
ls -la
```

---

## 📋 What Gets Moved

### Core Files
- ✅ `ultra_simple_server.py` - Main server
- ✅ `templates/` - All HTML templates
- ✅ `phantom_scraper/` - Integration code
- ✅ `static/` - Static assets
- ✅ `just_trades.db` - Database

### Configuration
- ✅ `.cursorrules` - Cursor AI rules
- ✅ `.cursorignore` - Protected files
- ✅ `.ai_rules` - AI rules
- ✅ `.env` - Environment variables
- ✅ `requirements.txt` - Dependencies

### Documentation
- ✅ All `*.md` files - Documentation
- ✅ `START_HERE.md` - Entry point
- ✅ `TAB_ISOLATION_MAP.md` - Tab isolation
- ✅ All protection docs

### Scripts & Tools
- ✅ All `*.sh` files - Scripts
- ✅ `create_sandbox.sh` - Sandbox creation
- ✅ `protect_files.sh` - File protection
- ✅ `migrate_project.sh` - Migration script

### Backups & Sandboxes
- ✅ `backups/` - File backups
- ✅ `sandboxes/` - Sandbox environments

### Git Repository
- ✅ `.git/` - Git history and tags

---

## ⚠️ What Doesn't Get Moved

### Excluded (by default)
- ❌ `venv/` - Virtual environment (recreate in new location)
- ❌ `__pycache__/` - Python cache (regenerated)
- ❌ `*.pyc` - Compiled Python files
- ❌ `node_modules/` - Node modules (if any)
- ❌ Large test files or temporary files

**Note**: You can manually copy these if needed, but it's recommended to recreate them.

---

## 🔧 Post-Migration Steps

### 1. Navigate to New Location
```bash
cd ~/just-trades-platform
# or
cd /Users/mylesjadwin/just-trades-platform
```

### 2. Verify Files
```bash
ls -la
# Should see all project files
```

### 3. Recreate Virtual Environment (if needed)
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

#### Update ngrok (if using)
```bash
# Update ngrok config or restart with new path
ngrok http 8082
```

#### Update Bookmarks
- Update browser bookmarks to new location
- Update any saved URLs

#### Update Scripts
- Check for any scripts that reference old path
- Update paths in configuration files

### 6. Update Cursor Workspace
- Open new folder in Cursor
- Cursor will automatically detect `.cursorrules`
- All protection rules will still work

### 7. Remove Old Location (Optional)
```bash
# Only after verifying everything works!
rm -rf "/Users/mylesjadwin/Trading Projects"
```

---

## 📝 Path References to Check

After migration, check these files for hardcoded paths:

### Files That Might Have Paths
- `ultra_simple_server.py` - Check for any hardcoded paths
- `.env` - Check for path references
- `server.log` - Log file location
- Any custom scripts

### Files That Should Be Fine
- ✅ `.cursorrules` - No paths, relative references
- ✅ `TAB_ISOLATION_MAP.md` - No paths, relative references
- ✅ `START_HERE.md` - No paths, relative references
- ✅ Most documentation - Relative references

---

## 🛡️ Protection Rules Still Work

**All protection rules will still work after migration:**
- ✅ `.cursorrules` - Automatically loaded by Cursor
- ✅ `START_HERE.md` - Still the entry point
- ✅ `TAB_ISOLATION_MAP.md` - Still enforces tab isolation
- ✅ All protection mechanisms - Still active

**No changes needed to protection system!**

---

## 🔄 Rollback Plan

If something goes wrong:

### Option 1: Keep Both Locations
- Old location still exists
- Can switch back if needed
- Compare files if issues arise

### Option 2: Restore from Git
```bash
cd ~/just-trades-platform
git status
git checkout .
# Restore any changes
```

### Option 3: Re-migrate
```bash
# Run migration script again
./migrate_project.sh
```

---

## ✅ Verification Checklist

After migration, verify:

- [ ] All files copied successfully
- [ ] Server starts without errors
- [ ] Database accessible (`just_trades.db` exists)
- [ ] Templates load correctly
- [ ] Protection rules still work (`.cursorrules` loaded)
- [ ] Git history intact (`git log` works)
- [ ] Documentation accessible
- [ ] Scripts executable (`./create_sandbox.sh` works)
- [ ] No broken paths in code
- [ ] External references updated (ngrok, bookmarks)

---

## 📞 Troubleshooting

### Issue: Server won't start
- Check Python path: `which python3`
- Recreate venv: `python3 -m venv venv`
- Install dependencies: `pip install -r requirements.txt`

### Issue: Database not found
- Check `just_trades.db` exists
- Check file permissions
- May need to recreate if corrupted

### Issue: Templates not loading
- Check `templates/` directory exists
- Check Flask template path
- Verify file permissions

### Issue: Protection rules not working
- Check `.cursorrules` exists in new location
- Restart Cursor
- Open new folder in Cursor workspace

---

## 🎯 Recommended New Location

**Best Practice**: Use a dedicated folder in your home directory:

```bash
~/just-trades-platform
# or
/Users/mylesjadwin/just-trades-platform
```

**Benefits:**
- ✅ Isolated from other projects
- ✅ Easy to find
- ✅ Clean organization
- ✅ No conflicts with other projects

---

**Last Updated**: December 2025  
**Status**: Ready for migration

