#!/bin/bash
# File Unprotection Script
# Restores write permissions to protected files (use with caution!)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Protected files list (same as protect_files.sh)
PROTECTED_FILES=(
    "templates/account_management.html"
)

echo "⚠️  UNPROTECTING FILES - USE WITH CAUTION!"
echo ""
read -p "Are you sure you want to unprotect these files? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Cancelled. Files remain protected."
    exit 0
fi

echo ""
echo "🔓 Unprotecting files..."

for file in "${PROTECTED_FILES[@]}"; do
    filepath="${SCRIPT_DIR}/${file}"
    if [ -f "${filepath}" ]; then
        # Restore write permission
        chmod 644 "${filepath}"
        echo "    ✅ Unprotected: ${file}"
    else
        echo "    ⚠️  File not found: ${file}"
    fi
done

echo ""
echo "✅ Files unprotected!"
echo "⚠️  Remember to re-protect after making changes:"
echo "   ./protect_files.sh"

