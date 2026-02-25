# Just Trades Platform — MASTER RULES & ARCHITECTURE

> **PRODUCTION STABLE STATE**: Tag `WORKING_FEB24_2026_WS_SEMAPHORE_STABLE` @ commit `39103a3`
> **Pro Copy Trader FULLY WORKING — manual + auto-copy, parallel execution, position sync — Feb 23, 2026**
> **PAID USERS IN PRODUCTION — EVERY BROKEN DEPLOY COSTS REAL MONEY**

---

## MANDATORY GATE SYSTEM — ENFORCED BEFORE EVERY CODE EDIT

**You CANNOT use the Edit or Write tool on ANY existing file until you have passed the required gates.**
**Each gate requires a specific formatted output block visible to the user.**
**Skipping a gate = protocol violation. The user will reject edits that skip gates.**

30+ production disasters happened because similar protocols were written as prose and skimmed past.
This gate system exists because prose doesn't work. Formatted proof-of-completion does.

---

### GATE 1: RECON (Required for ALL edits)

Before editing ANY file, you MUST output this block with real values (not placeholders):

```
GATE 1 — RECON
File: [filename]
Function/section: [name or "new code at line X"]
CHANGELOG_RULES.md: [searched for X — no conflicts / conflict at line Y — STOP]
Reference doc: [read docs/X.md / N/A — not touching broker/SQL/deploy code]
Full function read: [Read tool lines X-Y / new file — N/A]
```

**GATE 1 rules:**
- `CHANGELOG_RULES.md` MUST be searched if editing `recorder_service.py`, `ultra_simple_server.py`, or `tradovate_integration.py`. If the area is protected → STOP and tell the user.
- Reference doc lookup table:

| IF you're touching... | THEN READ this doc FIRST |
|----------------------|--------------------------|
| `tradovate_integration.py` or Tradovate API | `docs/TRADOVATE_API_REFERENCE.md` |
| `projectx_integration.py` or ProjectX API | `docs/PROJECTX_API_REFERENCE.md` |
| `webull_integration.py` or Webull API | `docs/WEBULL_API_REFERENCE.md` |
| Webhook handler, alert parsing, signal format | `docs/TRADINGVIEW_WEBHOOK_REFERENCE.md` |
| Whop sync, membership parsing, `/webhooks/whop` | `docs/WHOP_API_REFERENCE.md` |
| ANY SQL query, new column, migration, table change | `docs/DATABASE_SCHEMA.md` |
| Deploying, env vars, Railway CLI, rollback | `docs/RAILWAY_DEPLOYMENT.md` |
| Tick sizes, bracket syntax, debugging | `docs/CHEAT_SHEET.md` |
| Monitoring, health checks, endpoint responses | `docs/MONITORING_ENDPOINTS.md` |
| Testing signals, verifying trades | `docs/TESTING_PROCEDURES.md` |
| Admin access, onboarding, permissions | `docs/ADMIN_ACCESS_POLICY.md` |
| Copy trader, follower propagation, leader monitor, `ws_leader_monitor.py` | `docs/COPY_TRADER_ARCHITECTURE.md` |
| Position monitor, `ws_position_monitor.py`, reconciliation sync | `docs/SYSTEM_COMPONENTS.md` "WebSocket Position Monitor" section |
| Multi-bracket orders, bracket builder, risk_config | `docs/MULTI_BRACKET_SYSTEM.md` |
| Background daemons, token refresh, reconciliation | `docs/SYSTEM_COMPONENTS.md` |
| Incident response, rollback procedures | `docs/INCIDENT_RESPONSE.md` |

- If task involves multiple areas, read ALL matching docs.
- "Full function read" means the Read tool was used on the actual file. Not from memory. Not summarized.

---

### GATE 2: INTENT (Required for sacred files only)

If editing `recorder_service.py`, `ultra_simple_server.py`, or `tradovate_integration.py`, you MUST output:

```
GATE 2 — INTENT (Sacred File)
What I will change: [1-2 sentence description]
Why: [reason]
Lines affected: [X-Y]
Sacred functions touched: [none / list them — if any, STOP]

BEFORE (lines X-Y):
[exact current code]

AFTER:
[exact proposed code]
```

**GATE 2 rules:**
- If ANY sacred function appears in the diff → STOP. Sacred functions: `execute_trade_simple()`, `do_trade_for_account()`, `process_webhook_directly()`, `start_position_reconciliation()`, `broker_execution_worker()`
- The before/after MUST be real code, not descriptions. The user needs to see the exact diff.
- Only ADD lines to sacred files. NEVER restructure, rename, reorder, or "improve" existing code.

---

### GATE 3: APPROVAL (Required for sacred files only)

After showing GATE 2, you MUST use the **AskUserQuestion tool** to get explicit approval:

```
"Approve this edit to [file]? [1-line summary of change]"
Options: "Yes, do it" / "No, don't edit"
```

**You CANNOT call Edit/Write on a sacred file until the user selects "Yes, do it."**
If the user selects "No" → do NOT retry the same edit. Ask what they want instead.

---

### GATE 4: VERIFY (Required after EVERY edit)

After every Edit or Write call, you MUST output:

```
GATE 4 — VERIFY
py_compile: [passed / FAILED — fix before continuing]
Undefined variables: [checked lines X-Y — none found / FOUND: var at line Z]
Sacred functions in diff: [0 / FOUND — rollback immediately]
SQL placeholders: [all use '%s'/'?' pattern / N/A — no SQL]
```

**GATE 4 rules:**
- `py_compile` must actually be run via Bash tool (not assumed).
- Undefined variable check: trace every variable in new/modified code through all if/elif/else branches (Rule 25).
- If py_compile fails → fix immediately before any other action.

---

### GATE 5: CHECKPOINT (Required after EVERY commit)

After every `git commit`, you MUST output:

```
GATE 5 — CHECKPOINT
Commit: [hash] [first line of message]
Files changed: [list]
Want to test before next change? Pausing for confirmation.
```

**Then STOP. Do NOT proceed to the next edit until the user responds.**
The user may say "continue", "test first", or "stop here". Respect their choice.

---

### Gate Requirements by File Type

| File Type | Gate 1 | Gate 2 | Gate 3 | Gate 4 | Gate 5 |
|-----------|--------|--------|--------|--------|--------|
| Sacred files (`recorder_service.py`, `ultra_simple_server.py`, `tradovate_integration.py`) | REQUIRED | REQUIRED | REQUIRED | REQUIRED | REQUIRED |
| Other Python files (`account_activation.py`, `user_auth.py`, etc.) | REQUIRED | skip | skip | REQUIRED | REQUIRED |
| Templates (HTML) | REQUIRED | skip | skip | skip | REQUIRED |
| New files | REQUIRED | skip | skip | REQUIRED | REQUIRED |
| Documentation (CLAUDE.md, docs/) | skip | skip | skip | skip | skip |

### Multiple Changes

When a task requires multiple edits:
1. List all planned edits upfront as a numbered list
2. Execute them ONE AT A TIME — each edit goes through its own gate sequence
3. GATE 5 (checkpoint) after each commit — the user decides when to continue
4. NEVER batch unrelated changes into one commit

### API / Integration Questions

Before answering ANY question about a broker, webhook format, or integration:
- Read the matching reference doc from the table in GATE 1. Do not answer from memory.
- The docs contain production-verified gotchas that training data does not have.

### When Unsure

**ASK.** Do not guess. Wrong guesses in production = failed trades for paying customers.

---

## SACRED FILES — REQUIRE EXPLICIT APPROVAL FOR ANY EDIT

These files are the live production trading engine. Editing them without care has caused **every major outage** in this platform's history.

| File | Lines | What It Does | LOCK LEVEL |
|------|-------|--------------|------------|
| `recorder_service.py` | ~7.7K | Trading engine, execution, TP/SL, DCA, brackets | **CRITICAL — ASK BEFORE ANY EDIT** |
| `ultra_simple_server.py` | ~28K | Flask server, webhook pipeline, broker workers | **CRITICAL — ASK BEFORE ANY EDIT** |
| `tradovate_integration.py` | ~2.3K | Tradovate API, REST orders, bracket builder | **CRITICAL — ASK BEFORE ANY EDIT** |

**Before editing ANY of these files, you MUST:**
1. Read the FULL function you plan to modify (not just the lines around the change)
2. State EXACTLY what you're changing and why
3. Show the before/after diff
4. Get explicit "yes, do it" from the user
5. Make the minimal edit — ADD lines, do NOT restructure existing code

### Sacred Functions — NEVER refactor, rename, reorganize, or restructure

| Function | File | What It Does |
|----------|------|--------------|
| `execute_trade_simple()` | `recorder_service.py` | Entire trade execution flow |
| `do_trade_for_account()` | `recorder_service.py` | Per-account broker execution |
| `process_webhook_directly()` | `ultra_simple_server.py` | Webhook → broker queue pipeline |
| `start_position_reconciliation()` | `recorder_service.py` | Keeps DB in sync with broker |
| `broker_execution_worker()` | `ultra_simple_server.py` | Processes broker execution queue |

**"Don't touch" means:**
- No renaming variables
- No reordering logic
- No "cleanup" or "readability improvements"
- No adding error handling you think is missing
- No extracting helper functions
- If you need to ADD something, add it at the appropriate location — don't restructure what's there
- NEVER rewrite a section — only ADD lines (see Bug #7: Override Rewrite)

---

## RULE 1: ONE CHANGE AT A TIME, TEST AFTER EACH

This is the single most important rule. Every mega-outage happened because multiple changes were batched.

**Workflow:**
1. Make ONE change
2. Verify syntax: `python3 -c "import py_compile; py_compile.compile('file.py', doraise=True)"`
3. Commit with a descriptive message
4. Tell the user to test with a real signal if it's a trading code change
5. ONLY after confirmation, move to the next change

**NEVER:**
- Bundle a feature addition with a "cleanup" of existing code
- Touch files unrelated to the current task
- Make "improvements" you noticed while working on something else

---

## RULE 2: NEVER REFACTOR OR "IMPROVE" WORKING CODE

Do not:
- Remove code you think is "unused" — it might be used in a path you haven't traced
- Rename variables for "clarity"
- Add type hints, docstrings, or comments to code you didn't write
- Extract "helper functions" from working inline code
- "Simplify" conditional logic
- Change background threads to synchronous (this caused a 100% outage — Bug #9)
- Downgrade pool sizes, remove safety nets, or strip settings
- Add instrumentation (step_timer/with_timeout) to sacred functions

**The ONLY valid reasons to touch working code:**
1. User explicitly asked for a specific change
2. A bug is confirmed and you're fixing it
3. A new feature requires adding to existing code (ADD, don't restructure)

---

## RULE 3: ALWAYS ROUND PRICES TO TICK SIZE

Any code that calculates a price for Tradovate (TP, SL, or any limit/stop order) **MUST** round to the instrument's tick size:

```python
price = round(round(price / tick_size) * tick_size, 10)
```

**Why:** DCA weighted averages produce fractional prices. Tradovate REJECTS orders at invalid price increments. This leaves positions unprotected.

---

## RULE 4: ALWAYS USE POSTGRESQL-SAFE SQL PLACEHOLDERS

```python
placeholder = '%s' if is_using_postgres() else '?'
cursor.execute(f'SELECT * FROM table WHERE id = {placeholder}', (value,))
```

**NEVER** hardcode `?`. Production is PostgreSQL. `?` silently fails inside try/except.

---

## RULE 5: NEVER TRUST recorded_trades.tp_order_id FOR MULTI-ACCOUNT

`recorded_trades` has NO `subaccount_id` column. For DCA: query the broker directly, skip DB lookup.

---

## RULE 6: enabled_accounts MUST INCLUDE ALL SETTINGS

Per-account dict builder at `recorder_service.py` ~line 1138-1182. Missing settings silently fall back to defaults.

**Must include:** initial_position_size, add_position_size, recorder_id, sl_type, sl_amount, sl_enabled, trail_trigger, trail_freq, tp_targets, break_even_enabled/ticks/offset, dca_enabled, custom_ticker, add_delay, signal_cooldown, max_signals_per_session, max_daily_loss, time_filter_*, trim_units

---

## RULE 7: PYTHON VARIABLE SCOPING IN ASYNC

`nonlocal` in parallel async tasks = shared state bugs. Each task MUST use LOCAL copies:
```python
is_dca_local = is_dca  # local copy per task, NOT nonlocal
```

---

## RULE 8: DCA USES CANCEL + REPLACE, NEVER MODIFY

Tradovate's `modifyOrder` is unreliable for bracket-managed orders. DCA TP updates: cancel ALL working TPs → place fresh TP.

---

## RULE 9: BRACKET ORDERS FOR FIRST ENTRY ONLY (WHEN DCA IS ON)

| Scenario | Method | Why |
|----------|--------|-----|
| First entry (no position) | Bracket order (entry + TP in one call) | Faster, atomic |
| DCA entry (existing position, DCA ON) | REST market order + separate TP | Can't update existing position's TP via bracket |
| Same-direction signal (DCA OFF) | Bracket order (fresh entry) | DCA off = ignore position state |

**Never** use bracket orders for DCA entries. But when DCA is OFF, every same-direction signal is treated as a fresh entry with its own bracket order.

---

## RULE 10: ALL TRADOVATE ORDERS USE REST, NEVER WEBSOCKET

WebSocket pool was NEVER functional. ALL orders go through REST (`session.post`). NEVER add new WebSocket-based order functions.
`get_pooled_connection()` in recorder_service.py now returns `None` immediately (commit `6efcbd5`). The dead pool code tried `_ensure_websocket_connected()` which hung indefinitely, held `_WS_POOL_LOCK`, and blocked ALL trades with 60-second timeouts (Bug #35). NEVER re-enable this function.

---

## RULE 10b: WEBSOCKET CONNECTION STABILITY — READ BEFORE TOUCHING ANY WS CODE (Feb 24, 2026)

**MANDATORY**: Before modifying ANY file that touches WebSocket connections, READ `docs/TRADESYNCER_PARITY_REFERENCE.md` first. This doc has the complete Tradovate WebSocket protocol (wire format, heartbeat timing, reconnection strategy, syncrequest conformance rules).

**Files covered by this rule:**
- `ws_connection_manager.py` — Shared connection manager (THE critical infrastructure)
- `ws_position_monitor.py` — Position/fill/order sync
- `ws_leader_monitor.py` — Copy trade fill/order detection
- `live_max_loss_monitor.py` — Max loss cashBalance breach detection

**Current protection stack (ALL of these exist for a reason — NEVER REMOVE ANY):**
1. `asyncio.Semaphore(2)` in `_run_connection()` — limits concurrent WS connects to 2 (Bug #40)
2. `await asyncio.sleep(3)` inside semaphore block — 3s spacing between connection attempts (Bug #40)
3. Dead-sub threshold `>= 10` windows (300s) — prevents premature reconnect (Bug #38)
4. `_is_futures_market_likely_open()` — suppresses reconnect during market-closed hours (Bug #37)
5. Initial connection stagger 0-30s random delay — prevents simultaneous boot connections (Bug #38)
6. Dead-sub reconnect minimum backoff 30s + 0-15s jitter — prevents rapid reconnect cycling (Bug #38)
7. Heartbeat `[]` every 2.5s, server timeout 10s — per Tradovate protocol spec
8. 70-min max connection lifetime (before 85-min token expiry) — prevents auth failures

**Tradovate WebSocket protocol constants (from TRADESYNCER_PARITY_REFERENCE.md Part 3):**
```
HEARTBEAT_INTERVAL    = 2500ms  (client sends '[]')
SERVER_TIMEOUT        = 10000ms (no server message = dead)
TOKEN_REFRESH         = 85 min  (before 90min expiry)
INITIAL_RECONNECT     = 1000ms  (first retry delay)
MAX_RECONNECT_DELAY   = 60000ms (cap)
BACKOFF_JITTER        = 0-10%   (avoid thundering herd)
```

**Connection Semaphore (Bug #40) — THE MOST CRITICAL PROTECTION:**
- `asyncio.Semaphore(2)` limits concurrent Tradovate WS connection attempts to 2
- 3-second sleep after each attempt before releasing semaphore
- `conn.run()` is OUTSIDE the semaphore — we don't hold it during receive loop
- **NEVER remove the semaphore, increase above 2, or remove the 3s sleep**

**NEVER (429 Storm Prevention — Bugs #38 + #40):**
- NEVER reduce dead-subscription threshold below 10 windows (300s)
- NEVER reduce initial connection stagger below 30s
- NEVER reset backoff to 1s after dead-subscription disconnect
- NEVER remove `asyncio.Semaphore(2)` from `_run_connection()`
- NEVER increase the semaphore value above 2
- NEVER remove the `await asyncio.sleep(3)` inside the semaphore block
- The `>= 10` threshold is enforced in ALL 4 locations: ws_connection_manager.py (lines 374, 679), ws_leader_monitor.py (line 846), ws_position_monitor.py (line 298). Change ONE = change ALL FOUR.

> **Full WS connection manager architecture**: See `docs/SYSTEM_COMPONENTS.md`

---

## RULE 11: RECOVERY PROTOCOL

```bash
git reset --hard WORKING_FEB24_2026_WS_SEMAPHORE_STABLE     # CURRENT — WS semaphore + 7 critical fixes
git reset --hard WORKING_FEB23_2026_COPY_TRADER_STABLE     # Pre-Feb24 fallback — copy trader working but no WS stability
git reset --hard WORKING_FEB20_2026_BROKER_QTY_SAFETY_NET  # Pre-copy-trader fallback (+ brevo fix 5b6be75)
git reset --hard WORKING_FEB20_2026_DCA_FIELD_FIX_STABLE   # Pre-safety-net fallback
git reset --hard WORKING_FEB18_2026_DCA_SKIP_STABLE        # Pre-DCA-field-fix fallback
git reset --hard WORKING_FEB18_2026_FULL_AUDIT_STABLE      # Pre-DCA-off fix fallback
git reset --hard WORKING_FEB17_2026_MULTI_BRACKET_STABLE   # Pre-audit fallback
git reset --hard WORKING_FEB7_2026_PRODUCTION_STABLE       # THE BLUEPRINT
git push -f origin main  # CAUTION: force push — only if resetting
```

> **Full recovery reference (env vars, DB backup, TradingView alerts)**: See `docs/RECOVERY_REFERENCE.md`

---

## RULE 12: DCA OFF MEANS IGNORE POSITION STATE (Feb 18, 2026)

When `dca_enabled=False` (and recorder `avg_down_enabled=False`), existing position state must be **completely ignored** for same-direction signals. Two layers enforce this:

**Layer 1** — `process_webhook_directly()` in `ultra_simple_server.py` (~line 16611-16637):
- Checks `trader.dca_enabled` → falls back to `recorder.avg_down_enabled`
- Only sets `is_dca=True` and switches to `add_position_size` when DCA is actually enabled
- When DCA off: keeps `initial_position_size` (e.g., 3 contracts, not 1)

**Layer 2** — `do_trade_for_account()` in `recorder_service.py` (~line 2036-2049):
- When same-direction + DCA off: sets `has_existing_position = False`
- This allows the bracket gate at line ~2122 (`not has_existing_position and tp_ticks > 0`) to pass
- Result: fresh bracket order with full TP/SL strategy

**NEVER revert this behavior.** If DCA is off, position state is irrelevant for same-direction signals.

---

## RULE 13: MULTIPLIER MUST SCALE ALL QUANTITIES (Feb 18, 2026)

The `account_multiplier` (trader.multiplier) scales the entry quantity: `adjusted_quantity = quantity * account_multiplier`. But it must **also** scale any absolute contract quantities used in TP trim legs.

**Bracket trim calculation** in `recorder_service.py` (~line 2190-2193):
```python
# Contracts mode — MUST scale by multiplier
elif trim_units == 'Contracts':
    leg_qty = min(max(1, int(round(leg_trim * account_multiplier))), remaining_qty)

# Percent mode — already correct (uses adjusted_quantity which includes multiplier)
else:
    leg_qty = max(1, int(round(adjusted_quantity * (leg_trim / 100.0))))
```

**Rule:** Any time a raw contract count from settings is used in execution, check if it needs `* account_multiplier`. The Percent path works automatically because it calculates off `adjusted_quantity`.

---

## RULE 14: SIGNAL TRACKING MUST RESPECT DCA STATUS (Feb 18, 2026)

The `_bg_signal_tracking()` background thread in `ultra_simple_server.py` (~line 16933) writes to `recorded_trades`. The main webhook handler at line ~16633 reads `recorded_trades` to detect existing positions. **These two must stay in sync.**

**When DCA is OFF and same-direction signal arrives:**
- Close the old `recorded_trades` record (`status='closed'`, `exit_reason='new_entry'`)
- Insert a fresh record with the new entry price and quantity

**When DCA is ON and same-direction signal arrives:**
- Insert a new DCA add record (existing behavior — stack positions)

**NEVER** remove the `t_is_dca` parameter or unconditionally insert DCA add records.

---

## RULE 15: TICK SIZE LOOKUP — HANDLE 2-LETTER SYMBOL ROOTS

Futures contract names: `{ROOT}{MONTH}{YEAR}` (e.g., `GCJ6`, `NQH6`, `MGCJ6`). Root can be 2 or 3+ chars. Month letter (H/J/K/M/N/Q/U/V/X/Z) is NOT part of the root.

When looking up tick_size: try 3-char match first, then 2-char match. First match wins. Default 0.25 is WRONG for many symbols:
- GC = 0.10, CL = 0.01, SI = 0.005, HG = 0.0005, NG = 0.001

---

## RULE 16: TRADOVATE API RATE LIMITS ARE PER TOKEN, NOT PER ACCOUNT

All accounts sharing the same Tradovate token share ONE rate limit. JADVIX with 7 accounts = 7x API calls against the SAME token quota.

**NEVER** add "just one extra broker query per account" — it multiplies by the number of accounts. **Before adding ANY new broker API call**, count how many times it will execute per signal across all accounts.

---

## RULE 17: dict.get() DEFAULT IS IGNORED WHEN KEY EXISTS WITH None VALUE

```python
# WRONG — returns None if key exists with value None:
result.get('error', 'Unknown error')

# RIGHT — handles both missing key AND None value:
result.get('error') or 'Unknown error'
```

**Rule:** When a dict might have explicit None values, ALWAYS use `or` instead of the default parameter.

---

## RULE 18: TEMPLATE JS MUST MATCH SERVER API ENDPOINTS

When restoring server code from a git tag, template `fetch()` calls may not match `@app.route()` definitions. **After any server restore or route change:** grep templates for `fetch(` calls and verify each URL has a matching route.

---

## RULE 19: POSITION SIZE NULL FALLBACK CHAIN — EXPLICIT VALUES ONLY

Trader settings override recorder defaults. NULL falls back to recorder value. Template `{{ field or 1 }}` displays NULL as "1" in the UI. **Rule:** Always set explicit values on traders. Never rely on NULL fallback.

---

## RULE 20: NEVER ADD SIGNAL BLOCKING TO WEBHOOK HANDLER OR BROKER WORKER

On Feb 17, 2026, adding signal blocking to `ultra_simple_server.py` caused bracket orders to STOP WORKING. Root cause was never identified. Reverting fixed it immediately.

**Rule:** Do NOT modify the webhook handler or broker worker to add signal blocking, dedup, or mutex logic. If needed, implement in a SEPARATE layer.

---

## RULE 21: VERIFY RAILWAY ENVIRONMENT VARIABLES WITH FULL VALUES

Railway's table display TRUNCATES long values. **After setting any Railway env var:**
```bash
railway variables --kv  # Shows FULL values, not truncated
```

---

## RULE 22: ALWAYS TEST EXTERNAL API RESPONSES WITH REAL CURL BEFORE WRITING PARSING CODE

Before writing code that parses ANY external API response:
1. Make a real curl/httpie call to the API
2. Print the actual response structure
3. Check if fields are strings, dicts, arrays, or null
4. Use `isinstance()` checks for polymorphic fields

---

## RULE 23: CSRF EXEMPT LIST MUST COVER ALL EXTERNAL POST ENDPOINTS

The `_CSRF_EXEMPT_PREFIXES` list must include EVERY route that receives POST requests from external services.

**Current exempt prefixes that MUST exist:**
- `/webhook/` — TradingView webhooks (singular)
- `/webhooks/` — Whop webhooks (plural with S)
- `/oauth/` — OAuth callbacks

---

## RULE 24: FRONTEND/BACKEND FIELD NAME MISMATCH — DCA TOGGLE (Feb 19, 2026)

Frontend (`traders.html` line 314) sends `avg_down_enabled`. Backend reads `dca_enabled`. These are DIFFERENT field names for the SAME setting. Bridge exists in create/update trader endpoints. JADVIX startup auto-fix forces `dca_enabled=TRUE` on every deploy.

**Rule:** When adding new settings, ALWAYS verify the HTML form field name matches the Python request key.

---

## RULE 25: VARIABLE MUST BE DEFINED IN ALL BRANCHES BEFORE USE (Feb 20, 2026)

Python raises `UnboundLocalError` when a variable is assigned in only SOME branches of if-elif-else but used AFTER the chain unconditionally.

**Rule:** After writing ANY if-elif-else chain, check that EVERY variable used AFTER the chain is defined in ALL branches. `py_compile` does NOT catch this — it's a runtime error.

---

## RULE 26: ADMIN DELETE MUST CASCADE CHILD RECORDS (Feb 19, 2026)

PostgreSQL enforces foreign key constraints. When deleting a parent record, ALWAYS delete/nullify ALL child records first. If adding a new table with a `user_id` foreign key, ADD it to the cascade deletion list in `admin_delete_user()`.

---

## RULE 27: TRADINGVIEW SESSION COOKIES REQUIRED FOR REAL-TIME PRICES (Feb 20, 2026)

The TradingView WebSocket provides real-time CME market data. It has **two auth levels**:
- **Premium JWT** (~100ms real-time) — requires valid session cookies in `accounts.tradingview_session`
- **Public fallback** (10-15 min delayed) — `"unauthorized_user_token"` when cookies missing/expired

**If JWT extraction fails, system SILENTLY falls back to delayed data.** No error, no alert.

**Cookie format in DB:** `{"sessionid": "xxx", "sessionid_sign": "yyy"}`

**Cookies expire** ~every 3 months. When prices become stale, CHECK COOKIES FIRST.

**NEVER:**
- Remove the JWT auth — cookies are the ONLY way to get real-time CME data
- Pass cookies in WebSocket `additional_headers` — crashes on websockets 15+
- Send `"unauthorized_user_token"` when JWT is available

---

## RULE 28: BROKER-VERIFIED QUANTITY SAFETY NET (Feb 20, 2026)

Safety net in `recorder_service.py` (~line 2194-2206): After `get_positions()` broker check, if broker confirms NO position and the signal is an entry, recalculates quantity as `initial_position_size * account_multiplier`. Zero new API calls — uses existing result.

**NEVER** remove this safety net or add new API calls in this section.

---

## RULE 29: PIN ALL PYTHON PACKAGE VERSIONS — ESPECIALLY brevo-python (Feb 21, 2026)

`brevo-python` was unpinned. Docker cache bust pulled v4.0.5 which removed all v1 APIs. ALL activation emails failed for 2 days.

**Rules:**
1. **ALWAYS pin package versions** in requirements.txt — never use bare `package-name`
2. **Pin with upper bound** (`<2.0.0`) not exact version
3. **start.sh runtime install** is the safety net — keep it
4. **`railway run` runs LOCALLY, not in the container** — use `railway logs` to verify production
5. **NEVER** remove the version pin from `brevo-python<2.0.0`

---

## RULE 30: DIAGNOSE BEFORE YOU FIX — MANDATORY DEBUG CHECKLIST (Feb 21, 2026)

### BEFORE attempting ANY fix, complete ALL 4 steps:

1. **GET THE EXACT ERROR** — Not the catch-all message. Read the actual exception.
2. **VERIFY IN THE REAL ENVIRONMENT** — `railway run` runs locally. `railway logs` shows production.
3. **CHECK STATE BEFORE ASSUMING** — If "not installed" → check what version IS installed.
4. **STATE YOUR DIAGNOSIS BEFORE WRITING CODE** — "I believe the root cause is X because Y"

**One correct diagnosis > four fast fixes.**

---

## RULE 31: NEW FEATURE DOCUMENTATION CHECKLIST

When adding ANY new feature:
1. Update CLAUDE.md — Add to Deployed Features reference (`docs/DEPLOYED_FEATURES.md`)
2. Update relevant docs in `/docs/`
3. Add to CHANGELOG_RULES.md if modifying sacred files
4. Create git tag if new stable state
5. Update MEMORY.md if new bug pattern discovered
6. Test with real signal before marking "Working"
7. Document new settings in DATABASE_SCHEMA.md

---

## RULE 32: INTERNAL HTTP REQUESTS MUST INCLUDE ADMIN KEY (Feb 23, 2026)

When the server makes HTTP requests to its own `/api/` endpoints, `_global_api_auth_gate()` blocks with 401. Include `X-Admin-Key` header with value from `ADMIN_API_KEY` env var.

**Applies to:** All internal HTTP requests to `/api/` routes (manual copy, auto-copy, any future code).

**Also beware: truthy dict check on token refresh results.** `{'success': False}` is truthy. Must use `if refreshed and refreshed.get('success'):`.

**NEVER:**
- Make internal `/api/` requests without `X-Admin-Key` header
- Use `if result:` to check success of a function returning a dict — always check `.get('success')`
- Set Tradovate token expiry to 24 hours — they expire in 90 minutes. Use `timedelta(minutes=85)`

---

## RULE 33: FLASK_SECRET_KEY MUST BE PERMANENT ENV VAR (Feb 23, 2026)

Auto-generated keys die on restart, invalidating ALL sessions. `FLASK_SECRET_KEY` MUST be a permanent Railway env var.

---

## RULE 34: AUTO-COPY POSITION SYNC — ADD/TRIM, DON'T CLOSE+RE-ENTER (Feb 23, 2026)

| Scenario | Leader Position Change | Follower Action |
|----------|----------------------|-----------------|
| **ADD** | Same side, higher qty | Buy the DIFFERENCE |
| **TRIM** | Same side, lower qty | Sell the DIFFERENCE |
| **REVERSAL** | Different side | Close + re-enter |
| **ENTRY** | From flat | Fresh entry with risk config |
| **CLOSE** | To flat | Close all |

**NEVER** close + re-enter for same-side position changes.

---

## RULE 35: AUTO-COPY FOLLOWERS MUST EXECUTE IN PARALLEL (Feb 23, 2026)

| Path | Parallel Method |
|------|----------------|
| **Manual copy** | `ThreadPoolExecutor(max_workers=len(followers))` |
| **Auto-copy** | `asyncio.gather(*[_copy_one_follower(f) for f in followers])` |

**NEVER** use a sequential `for` loop for follower execution.

---

## RULE 36: NEVER USE PYTHON FALSY CHECKS FOR NUMERIC SETTINGS WHERE 0 IS VALID (Feb 24, 2026)

Python's `if 0:` is False. `0 or default` returns `default`. `int(0 or 1)` returns 1.

**Dangerous patterns — NEVER use these for numeric settings:**
```python
# WRONG — 0 falls back to default:
quantity = int(value) if value else 1
quantity = int(value or 1)
if trader_initial_size:  # False when 0

# RIGHT — explicit None check:
if value is not None and int(value) > 0:
    quantity = int(value)
```

**Applies to:** `initial_position_size`, `add_position_size`, `multiplier`, `max_contracts`, `sl_amount`, and ANY other numeric setting where 0 is valid.

---

## RULE 37: WEBSOCKET LIBRARY DEFAULTS — ALWAYS CHECK max_size AND SET splitResponses (Feb 24, 2026)

**Required settings on ALL `websockets.connect()` calls to Tradovate:**
```python
websocket = await websockets.connect(
    ws_url,
    max_size=10 * 1024 * 1024,  # 10 MB — default 1MB is too small
    ping_interval=None,
    ping_timeout=None,
    close_timeout=5,
)
```

**Required in ALL `user/syncrequest` bodies:**
```python
sync_body = json.dumps({
    "accounts": [int(sid) for sid in account_ids],
    "splitResponses": True,  # Break initial sync dump into smaller chunks
})
```

**NEVER** use default `max_size` (1 MB) or omit `splitResponses: true`.

---

## WHOP INTEGRATION

> **Full reference:** See `docs/WHOP_API_REFERENCE.md`

**Critical gotchas:** `membership.product` is a string, `membership.user` is a string, email is a top-level field. Webhook route is `/webhooks/whop` (plural S).

---

## PROJECTX INTEGRATION

> **Full reference:** See `docs/PROJECTX_API_REFERENCE.md`

**Status:** Deployed but NOT tested with real signals. Features: opposite signal blocking, DCA SL, trailing stop.

---

## ARCHITECTURE — HOW IT WORKS

### Signal-to-Trade Flow
```
TradingView Alert → POST /webhook/{token}
  ↓
10 Fast Webhook Workers (parallel, <50ms response)
  ↓
process_webhook_directly() — dedup, parse, find recorder, calc TP/SL
  ↓
broker_execution_queue
  ↓
10 HIVE MIND Broker Workers (parallel)
  ↓
execute_trade_simple() — find ALL traders → filter
  ↓
asyncio.gather() → do_trade_for_account() per account SIMULTANEOUSLY
  ↓
REST API → Tradovate → Order filled → TP/SL placed
```

### Key Architecture Constraints (DO NOT CHANGE)
- 10 fast webhook workers → broker_execution_queue → 10 broker workers
- Paper trades: **daemon thread (fire-and-forget), NEVER blocks broker pipeline**
- Signal tracking: **daemon thread, NEVER blocks broker pipeline**
- WebSocket pool code DISABLED (`get_pooled_connection()` returns None) — system uses REST API. NEVER re-enable.
- TP operations: asyncio.Lock per account/symbol prevents race conditions
- **Shared WS Connection Manager**: ONE WebSocket per Tradovate token (~16-20 connections for 27 accounts). **Connection semaphore** (`asyncio.Semaphore(2)`) limits concurrent connects — NEVER REMOVE (Bug #40).
- **REFERENCE DOC**: `docs/TRADESYNCER_PARITY_REFERENCE.md` has the COMPLETE Tradovate WebSocket protocol.

### Critical Code Locations (recorder_service.py)

| Line | What | Rule |
|------|------|------|
| ~870 | Find traders for recorder | SQL query, enabled filter |
| ~934-1068 | Trader-level filters | add_delay, cooldown, max_signals, max_loss, time |
| ~1072-1186 | enabled_accounts mode | Per-account dict — ALL settings (Rule 6) |
| ~1187-1222 | Legacy single-account mode | Fetches creds from accounts table |
| ~1655-1663 | DCA detection | Same direction + dca_enabled → is_dca_local (Rule 12) |
| ~1697-1761 | Bracket order (first entry) | Entry + TP in one REST call (Rule 9) |
| ~1842-1900 | Position fetch after entry | DCA: get weighted avg from broker |
| ~1951-1969 | TP price calculation | MUST round to tick_size (Rule 3) |
| ~1983-2013 | TP lookup for DCA | Skip DB, use broker query (Rule 5) |
| ~2040-2053 | Cancel ALL existing TPs | Per-account broker query (Rule 8) |
| ~2076-2098 | TP placement with retry | 10 attempts, exponential backoff |
| ~2118-2140 | SL price calculation | **MUST round to tick_size** (Rule 3) |
| ~2172-2212 | Multi-bracket TP leg builder | Trim qty calculation — **MUST use multiplier** (Rule 13) |
| ~2188-2201 | TP order ID storage | Best-effort, shared across accounts |

### Database

- **Local**: `just_trades.db` (SQLite)
- **Production**: PostgreSQL on Railway
- **All SQL MUST work on BOTH** (Rule 4)
- `recorded_trades` has NO `subaccount_id` column (Rule 5)

### Key Tables
```sql
users (id, username, email, password_hash, is_admin, is_approved, ...)
accounts (id, user_id, name, broker, auth_type, environment, tradovate_token, ...)
recorders (id, user_id, name, webhook_token, symbol, tp_ticks, sl_ticks, ...)
traders (id, user_id, recorder_id, account_id, enabled, multiplier, ...)
recorded_trades (id, recorder_id, ticker, side, entry_price, exit_price, pnl, status, tp_order_id, ...)
recorder_positions (id, recorder_id, ticker, side, total_quantity, avg_entry_price, ...)
```

### PostgreSQL Compatibility

```python
is_postgres = is_using_postgres()
placeholder = '%s' if is_postgres else '?'
enabled_value = 'TRUE' if is_postgres else '1'
```

### Deployment

- **Production**: Railway — auto-deploys from `main` branch pushes
- **Manual deploy**: `railway up` (uploads code directly, bypasses git)
- **Local dev**: `python3 ultra_simple_server.py` → `http://localhost:5000`

### Monitoring

> **Full endpoint reference:** See `docs/MONITORING_ENDPOINTS.md`

```bash
curl -s "https://justtrades.app/health"
curl -s "https://justtrades.app/status"
curl -s "https://justtrades.app/api/broker-execution/status"
curl -s "https://justtrades.app/api/broker-execution/failures?limit=20"
curl -s "https://justtrades.app/api/tradingview/status"
curl -s "https://justtrades.app/api/accounts/auth-status"
```

---

## COMMON ANTI-PATTERNS — STOP YOURSELF IF YOU'RE ABOUT TO DO ANY OF THESE

1. **"While I'm in here, let me also..."** → NO. One change. Commit. Test. Next change.
2. **"This code is messy, let me clean it up"** → NO. Messy but working > clean but broken.
3. **"I'll just restructure this section for clarity"** → NO. This is how Bug #9 happened (100% outage).
4. **"I don't need to read the whole function"** → YES YOU DO. This is how Bug #7 happened.
5. **"Let me change this from background thread to synchronous"** → NO. Bug #10 (10x latency).
6. **"I'll add some error handling here"** → Only if the user asked for it. Otherwise NO.
7. **"This variable name should be more descriptive"** → NO. Don't rename anything in sacred functions.
8. **"Let me extract a helper function"** → NO. Inline working code stays inline.
9. **"I'll combine these two commits into one"** → NO. One commit = one concern. Always.
10. **"I tested locally, should be fine in production"** → NO. PostgreSQL != SQLite. Railway != localhost.
11. **"I'll change the WebSocket connection code without reading TRADESYNCER_PARITY_REFERENCE.md"** → ABSOLUTELY NOT. Read it first. Every time.
12. **"The dead-sub threshold is too conservative, let me lower it"** → NO. 3 windows caused a 429 storm. 10 is the MINIMUM.
13. **"I'll connect all WebSockets at once for faster startup"** → NO. Bug #39/#40. Semaphore limits to 2 + 3s spacing. NEVER REMOVE.
14. **"This value is 0, so `if value:` will handle it"** → NO. `if 0:` is False. Bug #41. Use `is not None and int(x) > 0`.
15. **"I only need to fix the 2 calls that are failing right now"** → NO. Bug #43: first fix left 15 more. `grep -n` ALL instances.
16. **"The default websockets max_size (1MB) should be fine"** → NO. Bug #44. Always set `max_size=10*1024*1024`.
17. **"I'll add `use_websocket=True` to this new _smart() call"** → ABSOLUTELY NOT. Rule 10: ALL Tradovate orders use REST.

---

## REFERENCE DOCUMENTATION INDEX

| Doc | Path | Content |
|-----|------|---------|
| **Tradovate API** | `docs/TRADOVATE_API_REFERENCE.md` | REST API, bracket format, tick sizes |
| **TradeSyncer/WS Protocol** | `docs/TRADESYNCER_PARITY_REFERENCE.md` | **MANDATORY before WS code** — wire format, timing, reconnection |
| **ProjectX API** | `docs/PROJECTX_API_REFERENCE.md` | Order types, bracket format, API differences |
| **Webull API** | `docs/WEBULL_API_REFERENCE.md` | HMAC signing, order placement |
| **TradingView Webhooks** | `docs/TRADINGVIEW_WEBHOOK_REFERENCE.md` | Alert format, placeholders, retry behavior |
| **Whop API** | `docs/WHOP_API_REFERENCE.md` | Membership parsing, webhook format |
| **Database Schema** | `docs/DATABASE_SCHEMA.md` | Tables, columns, migrations |
| **Railway Deployment** | `docs/RAILWAY_DEPLOYMENT.md` | Deploy, env vars, rollback |
| **Cheat Sheet** | `docs/CHEAT_SHEET.md` | Quick reference, tick sizes, debugging |
| **Monitoring Endpoints** | `docs/MONITORING_ENDPOINTS.md` | Health checks, alert thresholds, daily checklist |
| **Testing Procedures** | `docs/TESTING_PROCEDURES.md` | End-to-end test signals, regression checklist |
| **Admin Access Policy** | `docs/ADMIN_ACCESS_POLICY.md` | Two-stage access model, safety guarantees |
| **Copy Trader Architecture** | `docs/COPY_TRADER_ARCHITECTURE.md` | Manual/auto-copy, leader/follower, dedup |
| **Deployed Features** | `docs/DEPLOYED_FEATURES.md` | Feature history table, supported brokers |
| **System Components** | `docs/SYSTEM_COMPONENTS.md` | Background daemons, WS manager, position monitor |
| **Multi-Bracket System** | `docs/MULTI_BRACKET_SYSTEM.md` | Bracket builder code locations |
| **Production Configs** | `docs/PRODUCTION_CONFIGS.md` | Strategy config snapshots, settings reference |
| **Incident Response** | `docs/INCIDENT_RESPONSE.md` | SEV levels, rollback procedures |
| **Recovery Reference** | `docs/RECOVERY_REFERENCE.md` | Env vars, DB backup, TradingView alerts, full rebuild |
| **Past Disasters** | `docs/PAST_DISASTERS.md` | 44 disasters table, patterns, lessons |
| **CHANGELOG_RULES.md** | `CHANGELOG_RULES.md` | **MANDATORY** — protected code registry (Gate 1) |

### Memory Files

Memory files (in `~/.claude/projects/-Users-mylesjadwin/memory/`):
- `MEMORY.md` — Master learnings file (loaded into every session)
- `WHY_IT_WORKS.md` — Logic document: what broke, why it's fixed, how to preserve it
- `feb7_production_stable_blueprint.md` — Full blueprint with every code location and commit
- `copy_trader_debug.md` — Copy trader debugging notes
- `bug_patterns_archive.md` — Bugs 1-24 detailed patterns

---

*Last updated: Feb 24, 2026 (evening session)*
*Production stable tag: WORKING_FEB24_2026_WS_SEMAPHORE_STABLE*
*Total rules: 37 + Rule 10b (WS Stability) | Total documented disasters: 48 | Paid users in production: YES*
*Reference docs: 20 in /docs/ | CHANGELOG_RULES.md | Memory: 9 files in ~/.claude/memory/*
