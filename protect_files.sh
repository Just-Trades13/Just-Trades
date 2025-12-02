#!/bin/bash
# File Protection Script
# Makes protected files read-only and creates backups

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/backups/protected_$(date +%Y%m%d_%H%M%S)"

# Protected files list
PROTECTED_FILES=(
    "templates/account_management.html"
)

echo "🛡️  Protecting critical files..."
echo "📁 Backup location: ${BACKUP_DIR}"
mkdir -p "${BACKUP_DIR}"

# Backup and protect files
for file in "${PROTECTED_FILES[@]}"; do
    filepath="${SCRIPT_DIR}/${file}"
    if [ -f "${filepath}" ]; then
        echo "  📋 Backing up: ${file}"
        mkdir -p "${BACKUP_DIR}/$(dirname "${file}")"
        cp "${filepath}" "${BACKUP_DIR}/${file}"
        
        # Make read-only (remove write permission)
        chmod 444 "${filepath}"
        echo "    ✅ Protected: ${file} (read-only)"
    else
        echo "    ⚠️  File not found: ${file}"
    fi
done

echo ""
echo "✅ Protection complete!"
echo ""
echo "📝 To unprotect a file (if needed):"
echo "   chmod 644 ${SCRIPT_DIR}/templates/account_management.html"
echo ""
echo "📦 Backup saved to: ${BACKUP_DIR}"

