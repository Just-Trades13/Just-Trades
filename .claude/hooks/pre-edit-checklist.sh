#!/bin/bash
# PRE-EDIT CHECKLIST HOOK
# Fires before EVERY Edit/Write on Python files
# Injects the checklist as feedback to Claude

INPUT=$(cat)

# Parse file_path from the hook JSON
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    ti = data.get('tool_input', {})
    print(ti.get('file_path', ''))
except:
    print('')
" 2>/dev/null)

# Only check Python files
case "$FILE_PATH" in
    *.py)
        ;;
    *)
        exit 0  # Not a Python file, allow silently
        ;;
esac

# Determine if sacred file
IS_SACRED=0
case "$FILE_PATH" in
    *recorder_service.py|*ultra_simple_server.py|*tradovate_integration.py)
        IS_SACRED=1
        ;;
esac

# Determine if WebSocket file
IS_WS=0
case "$FILE_PATH" in
    *ws_connection_manager.py|*ws_position_monitor.py|*ws_leader_monitor.py|*live_max_loss_monitor.py)
        IS_WS=1
        ;;
esac

# Build checklist message
CHECKLIST="PRE-EDIT CHECKLIST ($(basename "$FILE_PATH")):
1. Did you READ the full function with the Read tool? (Not from memory)
2. Did you grep ALL instances of the pattern you're changing?
3. Are you changing ONE thing only?
4. No 'if value:' on numeric settings where 0 is valid — use 'is not None'
5. No 'use_websocket=True' — must be False (Rule 10)
6. Will you run py_compile after this edit?"

if [ "$IS_SACRED" -eq 1 ]; then
    CHECKLIST="$CHECKLIST
SACRED FILE — Gates 1-5 ALL required.
   - Show GATE 1 RECON block before this edit
   - Search CHANGELOG_RULES.md for conflicts
   - Show GATE 2 INTENT with before/after diff
   - Get GATE 3 APPROVAL from user
   - Run py_compile for GATE 4 VERIFY"
fi

if [ "$IS_WS" -eq 1 ]; then
    CHECKLIST="$CHECKLIST
WEBSOCKET FILE — Rule 10b applies.
   - MANDATORY: Read docs/TRADESYNCER_PARITY_REFERENCE.md first
   - websockets.connect() must have max_size=10*1024*1024
   - syncrequest must have splitResponses: true"
fi

# Output as stderr (shown to Claude as feedback)
echo "$CHECKLIST" >&2

# For sacred files: also run the sacred function guard
if [ "$IS_SACRED" -eq 1 ]; then
    echo "$INPUT" | /Users/mylesjadwin/just-trades-platform/.claude/hooks/guard-sacred-functions.sh
    exit $?
fi

# For non-sacred Python files: allow but with checklist shown
exit 0
