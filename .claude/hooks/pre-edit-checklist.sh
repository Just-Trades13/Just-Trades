#!/bin/bash
# PRE-EDIT CHECKLIST HOOK — MECHANICAL GATE ENFORCEMENT
# Fires before EVERY Edit/Write on Python files
#
# SACRED FILES: physically BLOCKED unless approval file exists
# ALL .py FILES: checklist injected + diff-size limiter
# NON-PYTHON: pass silently

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

# ============================================================
# DIFF SIZE LIMITER — Rule 1: ONE change at a time
# Checked BEFORE approval so a too-large edit doesn't waste it
# ============================================================
EDIT_SIZE=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    ti = data.get('tool_input', {})
    old = ti.get('old_string', '')
    new = ti.get('new_string', '')
    content = ti.get('content', '')
    old_lines = len(old.split('\n')) if old else 0
    new_lines = len(new.split('\n')) if new else 0
    content_lines = len(content.split('\n')) if content else 0
    print(max(old_lines, new_lines, content_lines))
except:
    print('0')
" 2>/dev/null)

# Sacred files: hard block over 30 lines (BEFORE consuming approval)
if [ "$IS_SACRED" -eq 1 ] && [ "$EDIT_SIZE" -gt 30 ]; then
    echo "BLOCKED: Edit too large for sacred file ($EDIT_SIZE lines). Rule 1: ONE change at a time." >&2
    echo "Break this into smaller edits (max 30 lines per edit on sacred files)." >&2
    exit 2
fi

# Non-sacred Python files: warn over 50 lines
if [ "$IS_SACRED" -eq 0 ] && [ "$EDIT_SIZE" -gt 50 ]; then
    echo "WARNING: Large edit ($EDIT_SIZE lines). Rule 1: ONE change at a time. Consider splitting." >&2
fi

# ============================================================
# SACRED FILE GATE ENFORCEMENT — CANNOT BE BYPASSED
# ============================================================
APPROVAL_FILE="/tmp/claude_sacred_edit_approved"

if [ "$IS_SACRED" -eq 1 ]; then
    if [ -f "$APPROVAL_FILE" ]; then
        # Approval exists — consume it (one-time use, one edit only)
        rm -f "$APPROVAL_FILE"
        echo "SACRED EDIT APPROVED — one-time approval consumed. Next edit requires new approval." >&2
    else
        echo "BLOCKED: Sacred file edit without gate approval." >&2
        echo "" >&2
        echo "You MUST complete Gates 1-3 before editing sacred files:" >&2
        echo "  1. Show GATE 1 RECON block (Read full function, search CHANGELOG_RULES.md)" >&2
        echo "  2. Show GATE 2 INTENT block (before/after diff)" >&2
        echo "  3. Use AskUserQuestion for GATE 3 APPROVAL (user must say yes)" >&2
        echo "  4. Run: touch /tmp/claude_sacred_edit_approved" >&2
        echo "  5. Then retry the edit (approval is consumed after ONE edit)" >&2
        exit 2
    fi
fi

# ============================================================
# PRE-EDIT CHECKLIST — shown before every .py edit
# ============================================================
CHECKLIST="PRE-EDIT CHECKLIST ($(basename "$FILE_PATH")):
1. Did you READ the full function with the Read tool? (Not from memory)
2. Did you grep ALL instances of the pattern you're changing?
3. Are you changing ONE thing only?
4. No 'if value:' on numeric settings where 0 is valid — use 'is not None'
5. No 'use_websocket=True' — must be False (Rule 10)
6. py_compile will run AUTOMATICALLY after this edit (Gate 4)"

if [ "$IS_WS" -eq 1 ]; then
    CHECKLIST="$CHECKLIST
WEBSOCKET FILE — Rule 10b applies.
   - MANDATORY: Read docs/TRADESYNCER_PARITY_REFERENCE.md first
   - websockets.connect() must have max_size=10*1024*1024
   - syncrequest must have splitResponses: true"
fi

# Output checklist as stderr
echo "$CHECKLIST" >&2

# For sacred files: also run the sacred function guard
if [ "$IS_SACRED" -eq 1 ]; then
    echo "$INPUT" | /Users/mylesjadwin/just-trades-platform/.claude/hooks/guard-sacred-functions.sh
    exit $?
fi

# For non-sacred Python files: allow but with checklist shown
exit 0
