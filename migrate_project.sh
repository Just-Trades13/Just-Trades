#!/bin/bash
# Project Migration Script
# Moves Just.Trades Trading Platform to its own isolated folder

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_DIR="$SCRIPT_DIR"
PROJECT_NAME="just-trades-platform"
DEFAULT_NEW_LOCATION="$HOME/$PROJECT_NAME"

# Get target location from user or use default
TARGET_LOCATION="${1:-$DEFAULT_NEW_LOCATION}"

echo "🚀 Just.Trades Platform Migration"
echo "================================"
echo ""
echo "Current location: $CURRENT_DIR"
echo "Target location:  $TARGET_LOCATION"
echo ""

# Confirm migration
read -p "Do you want to migrate the project to $TARGET_LOCATION? (yes/no): " confirm
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

# Files/directories to move
ITEMS_TO_MOVE=(
    "ultra_simple_server.py"
    "templates"
    "phantom_scraper"
    "static"
    "backups"
    "sandboxes"
    "just_trades.db"
    "*.md"
    "*.sh"
    ".cursorrules"
    ".cursorignore"
    ".ai_rules"
    "requirements.txt"
    "openapi.json"
    "server.log"
    ".env"
    ".git"
)

# Copy project files
echo "📋 Copying project files..."
for item in "${ITEMS_TO_MOVE[@]}"; do
    if [ -e "$CURRENT_DIR/$item" ] || [ -d "$CURRENT_DIR/$item" ] || ls "$CURRENT_DIR/$item" 2>/dev/null | grep -q .; then
        echo "  → Copying $item..."
        if [ -d "$CURRENT_DIR/$item" ]; then
            cp -r "$CURRENT_DIR/$item" "$TARGET_LOCATION/" 2>/dev/null || true
        else
            cp "$CURRENT_DIR/$item" "$TARGET_LOCATION/" 2>/dev/null || true
        fi
    fi
done

# Copy all .md files explicitly
echo "  → Copying documentation files..."
find "$CURRENT_DIR" -maxdepth 1 -name "*.md" -type f -exec cp {} "$TARGET_LOCATION/" \;

# Copy all .sh files explicitly
echo "  → Copying script files..."
find "$CURRENT_DIR" -maxdepth 1 -name "*.sh" -type f -exec cp {} "$TARGET_LOCATION/" \;

# Create migration log
cat > "$TARGET_LOCATION/MIGRATION_LOG.md" << EOF
# Migration Log

**Migrated from**: $CURRENT_DIR
**Migrated to**: $TARGET_LOCATION
**Date**: $(date)
**Migration Script**: migrate_project.sh

## What Was Moved

- All project files and directories
- Documentation files (*.md)
- Script files (*.sh)
- Configuration files (.cursorrules, .cursorignore, .ai_rules)
- Database files (just_trades.db)
- Backups and sandboxes
- Git repository (.git)

## Next Steps

1. Navigate to new location: \`cd $TARGET_LOCATION\`
2. Verify files: \`ls -la\`
3. Test server: \`python3 ultra_simple_server.py\`
4. Update any external references (ngrok, bookmarks, etc.)
5. Remove old location if everything works (optional)

## Important Notes

- Old location still exists at: $CURRENT_DIR
- You can remove it after verifying the new location works
- Update any scripts or configurations that reference the old path
EOF

echo ""
echo "✅ Migration complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Navigate to new location:"
echo "      cd $TARGET_LOCATION"
echo ""
echo "   2. Verify files:"
echo "      ls -la"
echo ""
echo "   3. Test server:"
echo "      python3 ultra_simple_server.py"
echo ""
echo "   4. Update any external references:"
echo "      - ngrok configuration"
echo "      - Bookmarks"
echo "      - Any scripts referencing old path"
echo ""
echo "   5. Remove old location (after verification):"
echo "      rm -rf $CURRENT_DIR"
echo ""
echo "📋 Migration log saved to: $TARGET_LOCATION/MIGRATION_LOG.md"
echo ""

