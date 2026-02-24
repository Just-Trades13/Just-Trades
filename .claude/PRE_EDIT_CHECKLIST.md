# PRE-EDIT CHECKLIST — Read Before EVERY Edit

## STOP. Answer these before editing:

1. [ ] Did I READ the full function I'm about to modify? (Read tool, not memory)
2. [ ] Did I search CHANGELOG_RULES.md for this area? (Sacred files ONLY)
3. [ ] Did I read the matching reference doc? (See Gate 1 lookup table in CLAUDE.md)
4. [ ] Is this a sacred file? → Gates 1-5 ALL required. Show RECON block.
5. [ ] Am I changing ONE thing? Or am I bundling?
6. [ ] Did I grep ALL instances of the pattern I'm fixing? (Not just the one that's failing)
7. [ ] Am I using `if value:` on a numeric setting where 0 is valid? → Use `is not None`
8. [ ] Does my new code have `use_websocket=True`? → MUST be False (Rule 10)
9. [ ] Am I adding a new API call per account? → Count total calls x accounts (Rule 16)
10. [ ] After this edit, will I run py_compile? (MANDATORY)

## If editing WebSocket code:
- [ ] Did I read docs/TRADESYNCER_PARITY_REFERENCE.md? (Rule 10b — MANDATORY)
- [ ] Does websockets.connect() have max_size=10*1024*1024? (Rule 37)

## If ANY answer is NO → STOP and do it first.
