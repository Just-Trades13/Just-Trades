#!/bin/bash
# Sandbox Creation Script
# Creates an isolated copy of the project for experimental work

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="Trading Projects"
SANDBOX_BASE="${SCRIPT_DIR}/sandboxes"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SANDBOX_NAME="${1:-sandbox_${TIMESTAMP}}"
SANDBOX_DIR="${SANDBOX_BASE}/${SANDBOX_NAME}"

echo "🔨 Creating sandbox: ${SANDBOX_NAME}"
echo "📁 Location: ${SANDBOX_DIR}"

# Create sandbox directory
mkdir -p "${SANDBOX_DIR}"

# Copy key files (exclude large/unnecessary files)
echo "📋 Copying project files..."

# Core backend
cp "${SCRIPT_DIR}/ultra_simple_server.py" "${SANDBOX_DIR}/" 2>/dev/null || true

# Templates
mkdir -p "${SANDBOX_DIR}/templates"
cp -r "${SCRIPT_DIR}/templates/"*.html "${SANDBOX_DIR}/templates/" 2>/dev/null || true

# Phantom scraper
mkdir -p "${SANDBOX_DIR}/phantom_scraper"
cp -r "${SCRIPT_DIR}/phantom_scraper/"*.py "${SANDBOX_DIR}/phantom_scraper/" 2>/dev/null || true

# Static files
if [ -d "${SCRIPT_DIR}/static" ]; then
    cp -r "${SCRIPT_DIR}/static" "${SANDBOX_DIR}/" 2>/dev/null || true
fi

# Configuration files
cp "${SCRIPT_DIR}/requirements.txt" "${SANDBOX_DIR}/" 2>/dev/null || true
cp "${SCRIPT_DIR}/.env" "${SANDBOX_DIR}/" 2>/dev/null || true

# Documentation (read-only reference)
mkdir -p "${SANDBOX_DIR}/docs_reference"
cp "${SCRIPT_DIR}/HANDOFF_DOCUMENT.md" "${SANDBOX_DIR}/docs_reference/" 2>/dev/null || true
cp "${SCRIPT_DIR}/CURRENT_STATUS_SNAPSHOT.md" "${SANDBOX_DIR}/docs_reference/" 2>/dev/null || true
cp "${SCRIPT_DIR}/WHAT_NOT_TO_DO.md" "${SANDBOX_DIR}/docs_reference/" 2>/dev/null || true
cp "${SCRIPT_DIR}/PRE_CHANGE_CHECKLIST.md" "${SANDBOX_DIR}/docs_reference/" 2>/dev/null || true

# Create sandbox README
cat > "${SANDBOX_DIR}/SANDBOX_README.md" << EOF
# Sandbox: ${SANDBOX_NAME}

**Created**: $(date)
**Purpose**: Experimental development environment

## ⚠️ IMPORTANT

This is a SANDBOX copy. Changes here do NOT affect the main project.

## Usage

1. Work in this directory
2. Test your changes thoroughly
3. When ready, merge approved changes back to main project
4. **DO NOT modify protected files** (see docs_reference/)

## Protected Files (Reference Only)

- \`templates/account_management.html\` - LOCKED baseline
- Account management functions in \`ultra_simple_server.py\`
- Core methods in \`phantom_scraper/tradovate_integration.py\`

## Merging Back

When ready to merge:
1. Review changes carefully
2. Test in main project
3. Use git or manual copy for approved changes
4. **Never merge changes to protected files without explicit permission**

## Documentation

See \`docs_reference/\` for protection rules and guidelines.
EOF

# Create .gitignore for sandbox
cat > "${SANDBOX_DIR}/.gitignore" << EOF
# Sandbox-specific ignores
*.db
*.log
__pycache__/
venv/
.env
EOF

echo ""
echo "✅ Sandbox created successfully!"
echo ""
echo "📝 Next steps:"
echo "   1. cd ${SANDBOX_DIR}"
echo "   2. Work on your changes"
echo "   3. Test thoroughly"
echo "   4. Merge approved changes back to main"
echo ""
echo "📚 Protection rules: See docs_reference/ directory"
echo ""

