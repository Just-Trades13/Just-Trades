# Sandbox Workflow Guide

**Purpose**: Safely develop new features without risking working code

---

## 🎯 When to Use Sandbox

Use a sandbox when:
- ✅ Adding new features that might affect existing code
- ✅ Experimenting with major refactoring
- ✅ Testing new approaches to existing problems
- ✅ Working on features that touch protected files
- ✅ Trying out new libraries or dependencies

**DO NOT use sandbox for:**
- ❌ Simple bug fixes (unless file is protected)
- ❌ Documentation updates
- ❌ Small, isolated changes

---

## 🚀 Creating a Sandbox

### Quick Start
```bash
# Create sandbox with default name (timestamp-based)
./create_sandbox.sh

# Create sandbox with custom name
./create_sandbox.sh my_feature_branch
```

### What Gets Copied
- ✅ Core backend files (`ultra_simple_server.py`)
- ✅ Templates (`templates/*.html`)
- ✅ Integration code (`phantom_scraper/*.py`)
- ✅ Static files
- ✅ Configuration files
- ✅ Documentation (read-only reference)

### What Doesn't Get Copied
- ❌ Database files (`.db`)
- ❌ Log files (`.log`)
- ❌ Virtual environment (`venv/`)
- ❌ Large documentation files
- ❌ Backup directories

---

## 📁 Sandbox Structure

```
sandboxes/
└── sandbox_20251225_120000/
    ├── ultra_simple_server.py
    ├── templates/
    │   ├── account_management.html
    │   ├── manual_copy_trader.html
    │   └── ...
    ├── phantom_scraper/
    │   └── tradovate_integration.py
    ├── docs_reference/          # Read-only protection docs
    │   ├── HANDOFF_DOCUMENT.md
    │   ├── WHAT_NOT_TO_DO.md
    │   └── ...
    ├── SANDBOX_README.md        # Sandbox-specific instructions
    └── .gitignore
```

---

## 🔧 Working in Sandbox

### 1. Navigate to Sandbox
```bash
cd sandboxes/sandbox_20251225_120000
```

### 2. Set Up Environment
```bash
# Create virtual environment (if needed)
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Make Changes
- Work freely in the sandbox
- Test your changes
- Reference `docs_reference/` for protection rules
- **Even in sandbox, respect protected file guidelines**

### 4. Test Thoroughly
```bash
# Run server in sandbox
python3 ultra_simple_server.py

# Test your changes
# Verify nothing breaks
```

---

## 🔄 Merging Back to Main

### Before Merging
1. ✅ Test all changes thoroughly
2. ✅ Review against protection rules
3. ✅ Check `WHAT_NOT_TO_DO.md` to avoid past mistakes
4. ✅ Get user approval for changes

### Merge Process

#### Option 1: Manual Copy (Recommended for Protected Files)
```bash
# Copy specific files back
cp sandboxes/sandbox_20251225_120000/templates/new_feature.html templates/

# Test in main project
# Commit if approved
```

#### Option 2: Git Merge (For Non-Protected Files)
```bash
# If sandbox is a git branch
git checkout main
git merge sandbox_20251225_120000
```

#### Option 3: Selective File Copy
```bash
# Copy only approved files
cp sandboxes/sandbox_20251225_120000/ultra_simple_server.py .
# Test, then commit
```

### ⚠️ Important Merge Rules

**NEVER merge:**
- ❌ Changes to `templates/account_management.html` without explicit permission
- ❌ Changes to account management functions without approval
- ❌ Untested changes
- ❌ Changes that break existing functionality

**ALWAYS:**
- ✅ Test merged changes in main project
- ✅ Verify protected files remain intact
- ✅ Check that backups are up to date
- ✅ Update documentation if needed

---

## 🛡️ Protection in Sandbox

Even in sandbox:
- **Respect protected file guidelines** (see `docs_reference/`)
- **Don't modify account management** unless explicitly working on it
- **Test thoroughly** before merging
- **Reference protection docs** before major changes

---

## 🗑️ Cleaning Up Sandboxes

### Keep Sandbox
- If work is ongoing
- If you might need to reference it

### Delete Sandbox
```bash
# Remove sandbox directory
rm -rf sandboxes/sandbox_20251225_120000

# Or keep for reference
mv sandboxes/sandbox_20251225_120000 sandboxes/archive/
```

---

## 📝 Best Practices

1. **One Feature Per Sandbox**: Don't mix multiple features
2. **Name Clearly**: Use descriptive names (`trailing_stop_fix`, `new_dashboard`)
3. **Test Before Merge**: Never merge untested code
4. **Respect Protection**: Even in sandbox, follow protection rules
5. **Document Changes**: Note what you changed and why
6. **Clean Up**: Delete old sandboxes when done

---

## 🚨 Emergency: Restore from Sandbox

If main project breaks:
```bash
# Restore from sandbox backup
cp sandboxes/sandbox_20251225_120000/ultra_simple_server.py .
cp sandboxes/sandbox_20251225_120000/templates/*.html templates/
# Test and commit
```

---

## 📚 Reference

- **Protection Rules**: See `docs_reference/WHAT_NOT_TO_DO.md`
- **Current State**: See `docs_reference/CURRENT_STATUS_SNAPSHOT.md`
- **Handoff Doc**: See `docs_reference/HANDOFF_DOCUMENT.md`

---

**Remember**: Sandbox is for safety, but protection rules still apply. When in doubt, ask before merging.

