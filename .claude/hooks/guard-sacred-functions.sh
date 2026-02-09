#!/bin/bash
# GUARD HOOK: Blocks edits to sacred functions without explicit approval
# This runs BEFORE any Edit/Write tool call on critical files
#
# Sacred functions that must not be modified without permission:
#   - execute_trade_simple()
#   - do_trade_for_account()
#   - process_webhook_directly()
#   - start_position_reconciliation()
#   - start_websocket_keepalive_daemon()

# Read the tool input from stdin
INPUT=$(cat)

# Get the file being edited
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

# Only check critical files
case "$FILE_PATH" in
    *recorder_service.py|*ultra_simple_server.py|*tradovate_integration.py)
        ;;
    *)
        exit 0  # Not a critical file, allow
        ;;
esac

# Get the old_string being replaced (for Edit tool)
OLD_STRING=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('old_string', ''))
except:
    print('')
" 2>/dev/null)

# Check if the edit touches a sacred function signature or core logic
SACRED_PATTERNS=(
    "def execute_trade_simple"
    "def do_trade_for_account"
    "def process_webhook_directly"
    "def start_position_reconciliation"
    "def start_websocket_keepalive_daemon"
)

for pattern in "${SACRED_PATTERNS[@]}"; do
    if echo "$OLD_STRING" | grep -q "$pattern"; then
        echo "BLOCKED: Attempted to modify sacred function: $pattern"
        echo "These functions are protected by Rule 1 in CLAUDE.md."
        echo "Get explicit user permission for the SPECIFIC change before proceeding."
        exit 2
    fi
done

# Check for common anti-patterns
if echo "$OLD_STRING" | grep -q "nonlocal is_dca"; then
    echo "BLOCKED: Do not use 'nonlocal is_dca' — use local copies (Rule 8)"
    exit 2
fi

# Check for hardcoded ? placeholders in SQL (Rule 3)
NEW_STRING=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('new_string', ''))
except:
    print('')
" 2>/dev/null)

if echo "$NEW_STRING" | grep -qE "execute\(.*['\"].*\?.*['\"]"; then
    # Check if it's using the placeholder pattern (safe) or hardcoded ? (unsafe)
    if ! echo "$NEW_STRING" | grep -qE "(placeholder|ph|_ph)"; then
        echo "WARNING: Possible hardcoded '?' in SQL query. Production uses PostgreSQL."
        echo "Use: placeholder = '%s' if is_using_postgres() else '?'"
        echo "See Rule 3 in CLAUDE.md."
        # Warning only, don't block — there are legitimate uses of ?
    fi
fi

exit 0
