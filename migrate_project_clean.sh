#!/bin/bash
# Clean Project Migration Script - Just.Trades Platform Only
# Moves ONLY the Just.Trades platform files, excluding unrelated projects

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_DIR="$SCRIPT_DIR"
PROJECT_NAME="just-trades-platform"
DEFAULT_NEW_LOCATION="$HOME/$PROJECT_NAME"

# Get target location from user or use default
TARGET_LOCATION="${1:-$DEFAULT_NEW_LOCATION}"

echo "🚀 Just.Trades Platform Migration (Clean)"
echo "=========================================="
echo ""
echo "Current location: $CURRENT_DIR"
echo "Target location:  $TARGET_LOCATION"
echo ""
echo "⚠️  This will copy ONLY Just.Trades platform files"
echo "    (excluding unrelated projects, packages, test files)"
echo ""

# Confirm migration
read -p "Do you want to migrate the Just.Trades platform to $TARGET_LOCATION? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ Migration cancelled."
    exit 0
fi

# Check if target exists
if [ -d "$TARGET_LOCATION" ]; then
    echo "⚠️  Target directory already exists: $TARGET_LOCATION"
    read -p "Do you want to overwrite it? (yes/no): " overwrite
    if [ "$overwrite" != "yes" ]; then
        echo "❌ Migration cancelled."
        exit 0
    fi
    echo "🗑️  Removing existing directory..."
    rm -rf "$TARGET_LOCATION"
fi

# Create target directory
echo "📁 Creating target directory..."
mkdir -p "$TARGET_LOCATION"

# ============================================
# CORE PLATFORM FILES - Just.Trades Only
# ============================================

echo ""
echo "📋 Copying Just.Trades platform files..."
echo ""

# Core server and application
echo "  → Core application files..."
[ -f "$CURRENT_DIR/ultra_simple_server.py" ] && cp "$CURRENT_DIR/ultra_simple_server.py" "$TARGET_LOCATION/"
[ -f "$CURRENT_DIR/requirements.txt" ] && cp "$CURRENT_DIR/requirements.txt" "$TARGET_LOCATION/"
[ -f "$CURRENT_DIR/openapi.json" ] && cp "$CURRENT_DIR/openapi.json" "$TARGET_LOCATION/"
[ -f "$CURRENT_DIR/.env" ] && cp "$CURRENT_DIR/.env" "$TARGET_LOCATION/" 2>/dev/null || true

# Templates (web interface)
echo "  → Web templates..."
[ -d "$CURRENT_DIR/templates" ] && cp -r "$CURRENT_DIR/templates" "$TARGET_LOCATION/"

# Static assets
echo "  → Static assets..."
[ -d "$CURRENT_DIR/static" ] && cp -r "$CURRENT_DIR/static" "$TARGET_LOCATION/"

# Core integration code
echo "  → Integration code..."
[ -d "$CURRENT_DIR/phantom_scraper" ] && cp -r "$CURRENT_DIR/phantom_scraper" "$TARGET_LOCATION/"

# Database
echo "  → Database..."
[ -f "$CURRENT_DIR/just_trades.db" ] && cp "$CURRENT_DIR/just_trades.db" "$TARGET_LOCATION/"
[ -f "$CURRENT_DIR/just_trades.db-journal" ] && cp "$CURRENT_DIR/just_trades.db-journal" "$TARGET_LOCATION/" 2>/dev/null || true
[ -f "$CURRENT_DIR/just_trades.db-wal" ] && cp "$CURRENT_DIR/just_trades.db-wal" "$TARGET_LOCATION/" 2>/dev/null || true

# Protection system files
echo "  → Protection system..."
[ -f "$CURRENT_DIR/.cursorrules" ] && cp "$CURRENT_DIR/.cursorrules" "$TARGET_LOCATION/"
[ -f "$CURRENT_DIR/.cursorignore" ] && cp "$CURRENT_DIR/.cursorignore" "$TARGET_LOCATION/"
[ -f "$CURRENT_DIR/.ai_rules" ] && cp "$CURRENT_DIR/.ai_rules" "$TARGET_LOCATION/"

# Just.Trades documentation (protection and platform docs only)
echo "  → Platform documentation..."
JUST_TRADES_DOCS=(
    "START_HERE.md"
    "TAB_ISOLATION_MAP.md"
    "TAB_ISOLATION_SUMMARY.md"
    "PROTECTION_SYSTEM.md"
    "QUICK_PROTECTION_REFERENCE.md"
    "ENFORCEMENT_GUARANTEE.md"
    "RULES_ENFORCEMENT_SUMMARY.md"
    "NEW_CHAT_START.md"
    "QUICK_START_TEMPLATE.txt"
    "HANDOFF_DOCUMENT.md"
    "CURRENT_STATUS_SNAPSHOT.md"
    "WHAT_NOT_TO_DO.md"
    "PRE_CHANGE_CHECKLIST.md"
    "ACCOUNT_MGMT_SNAPSHOT.md"
    "BACKUP_INDEX.md"
    "PROTECTION_SUMMARY.md"
    "SANDBOX_WORKFLOW.md"
    "MIGRATION_GUIDE.md"
    "README.md"
)

for doc in "${JUST_TRADES_DOCS[@]}"; do
    if [ -f "$CURRENT_DIR/$doc" ]; then
        cp "$CURRENT_DIR/$doc" "$TARGET_LOCATION/"
    fi
done

# Just.Trades scripts (platform and protection scripts only)
echo "  → Platform scripts..."
JUST_TRADES_SCRIPTS=(
    "create_sandbox.sh"
    "protect_files.sh"
    "unprotect_files.sh"
    "restart_server.sh"
    "start_server.sh"
)

for script in "${JUST_TRADES_SCRIPTS[@]}"; do
    if [ -f "$CURRENT_DIR/$script" ]; then
        cp "$CURRENT_DIR/$script" "$TARGET_LOCATION/"
        chmod +x "$TARGET_LOCATION/$script"
    fi
done

# Project backups and sandboxes (Just.Trades related)
echo "  → Project backups and sandboxes..."
[ -d "$CURRENT_DIR/backups" ] && cp -r "$CURRENT_DIR/backups" "$TARGET_LOCATION/"
[ -d "$CURRENT_DIR/sandboxes" ] && cp -r "$CURRENT_DIR/sandboxes" "$TARGET_LOCATION/"

# Git repository (if exists)
echo "  → Git repository..."
if [ -d "$CURRENT_DIR/.git" ]; then
    cp -r "$CURRENT_DIR/.git" "$TARGET_LOCATION/"
    echo "    ✅ Git history preserved"
fi

# Log files (if needed)
echo "  → Log files..."
[ -f "$CURRENT_DIR/server.log" ] && cp "$CURRENT_DIR/server.log" "$TARGET_LOCATION/" 2>/dev/null || true
[ -f "$CURRENT_DIR/ngrok.log" ] && cp "$CURRENT_DIR/ngrok.log" "$TARGET_LOCATION/" 2>/dev/null || true
[ -f "$CURRENT_DIR/ngrok_url.txt" ] && cp "$CURRENT_DIR/ngrok_url.txt" "$TARGET_LOCATION/" 2>/dev/null || true

# ============================================
# EXCLUDED - Not Part of Just.Trades Platform
# ============================================
# These are intentionally NOT copied:
# - Package folders (Package 2A, 3A, etc.)
# - pnl_test_project/
# - Apollo-related files
# - Airtable-related files
# - HELOC-related files
# - Other unrelated markdown files
# - Other test projects
# - venv/ (recreate in new location)

# Create migration log
cat > "$TARGET_LOCATION/MIGRATION_LOG.md" << EOF
# Migration Log - Just.Trades Platform

**Migrated from**: $CURRENT_DIR
**Migrated to**: $TARGET_LOCATION
**Date**: $(date)
**Migration Script**: migrate_project_clean.sh

## What Was Moved (Just.Trades Platform Only)

### Core Application
- ✅ ultra_simple_server.py - Main Flask server
- ✅ templates/ - Web interface templates
- ✅ static/ - Static assets (CSS, JS, images)
- ✅ phantom_scraper/ - Tradovate integration code
- ✅ just_trades.db - Database
- ✅ requirements.txt - Python dependencies
- ✅ openapi.json - Tradovate API specification

### Protection System
- ✅ .cursorrules - Cursor AI rules
- ✅ .cursorignore - Protected files list
- ✅ .ai_rules - AI rules
- ✅ All protection documentation (START_HERE.md, TAB_ISOLATION_MAP.md, etc.)

### Scripts & Tools
- ✅ create_sandbox.sh - Sandbox creation
- ✅ protect_files.sh - File protection
- ✅ restart_server.sh - Server restart
- ✅ start_server.sh - Server start

### Project Management
- ✅ backups/ - Project backups
- ✅ sandboxes/ - Sandbox environments
- ✅ .git/ - Git repository (if exists)

### Documentation
- ✅ Platform documentation only
- ✅ Protection system docs
- ✅ Migration guides

## What Was Excluded (Not Part of Just.Trades)

- ❌ Package folders (Package 2A, 3A, etc.)
- ❌ pnl_test_project/
- ❌ Apollo-related files
- ❌ Airtable-related files
- ❌ HELOC-related files
- ❌ Other unrelated projects
- ❌ Test files not part of platform
- ❌ venv/ (recreate in new location)

## Next Steps

1. Navigate to new location: \`cd $TARGET_LOCATION\`
2. Verify files: \`ls -la\`
3. Recreate virtual environment: \`python3 -m venv venv\`
4. Install dependencies: \`pip install -r requirements.txt\`
5. Test server: \`python3 ultra_simple_server.py\`
6. Update external references (ngrok, bookmarks, etc.)
7. Remove old location if everything works (optional)

## Important Notes

- Old location still exists at: $CURRENT_DIR
- Only Just.Trades platform files were copied
- Unrelated projects remain in old location
- You can remove old location after verification
- Update any scripts or configurations that reference the old path
EOF

echo ""
echo "✅ Clean migration complete!"
echo ""
echo "📊 Summary:"
echo "   ✅ Just.Trades platform files copied"
echo "   ✅ Protection system included"
echo "   ✅ Documentation included"
echo "   ❌ Unrelated projects excluded"
echo ""
echo "📝 Next steps:"
echo "   1. Navigate to new location:"
echo "      cd $TARGET_LOCATION"
echo ""
echo "   2. Verify files:"
echo "      ls -la"
echo ""
echo "   3. Recreate virtual environment:"
echo "      python3 -m venv venv"
echo "      source venv/bin/activate"
echo "      pip install -r requirements.txt"
echo ""
echo "   4. Test server:"
echo "      python3 ultra_simple_server.py"
echo ""
echo "   5. Update external references:"
echo "      - ngrok configuration"
echo "      - Bookmarks"
echo "      - Any scripts referencing old path"
echo ""
echo "📋 Migration log saved to: $TARGET_LOCATION/MIGRATION_LOG.md"
echo ""

