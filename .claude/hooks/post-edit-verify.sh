#!/bin/bash
# POST-EDIT VERIFY HOOK — MECHANICAL GATE 4 ENFORCEMENT
# Fires AFTER every Edit/Write on Python files
# Auto-runs py_compile — cannot be skipped

INPUT=$(cat)

# Parse file_path from the tool input
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
        exit 0
        ;;
esac

# Run py_compile automatically — Gate 4
RESULT=$(python3 -c "import py_compile, sys; py_compile.compile(sys.argv[1], doraise=True)" "$FILE_PATH" 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "GATE 4 FAILED — py_compile error on $(basename "$FILE_PATH"):" >&2
    echo "$RESULT" >&2
    echo "" >&2
    echo "FIX THIS IMMEDIATELY. Do not make any other changes until this compiles." >&2
else
    echo "GATE 4 PASSED — py_compile OK: $(basename "$FILE_PATH")" >&2
fi

# Always exit 0 — postToolUse can't undo edits, but the feedback is visible
exit 0
