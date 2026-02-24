# Just Trades Platform — MASTER RULES & ARCHITECTURE

> **PRODUCTION STABLE STATE**: Tag `WORKING_FEB23_2026_COPY_TRADER_STABLE` @ commit `98021d6`
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
| Position monitor, `ws_position_monitor.py`, reconciliation sync | CLAUDE.md "WebSocket Position Monitor" section |

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
- If ANY sacred function appears in the diff → STOP. Sacred functions: `execute_trade_simple()`, `do_trade_for_account()`, `process_webhook_directly()`, `start_position_reconciliation()`, `start_websocket_keepalive_daemon()`, `broker_execution_worker()`
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
| `start_websocket_keepalive_daemon()` | `recorder_service.py` | Keeps WebSocket connections alive |
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

**What happened when these protections didn't exist (Feb 24, 2026 — 7 bugs in 12 hours):**
- 16+ connections all reconnected simultaneously → Tradovate HTTP 429 rate limit storm
- 429 storm cycled every 90 seconds for HOURS
- ALL Pro Copy Trader functionality was DOWN (leader monitor couldn't receive fills)
- ALL position monitors were DOWN (no real-time broker sync)
- Recovery required adding the semaphore — the SINGLE MOST IMPORTANT LINE OF CODE in the WS system

**Tradovate WebSocket protocol constants (from TRADESYNCER_PARITY_REFERENCE.md Part 3):**
```
HEARTBEAT_INTERVAL    = 2500ms  (client sends '[]')
SERVER_TIMEOUT        = 10000ms (no server message = dead)
TOKEN_REFRESH         = 85 min  (before 90min expiry)
INITIAL_RECONNECT     = 1000ms  (first retry delay)
MAX_RECONNECT_DELAY   = 60000ms (cap)
BACKOFF_JITTER        = 0-10%   (avoid thundering herd)
```

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

**Git Tags (Recovery Points):**

| Tag | Commit | Description |
|-----|--------|-------------|
| `WORKING_FEB24_2026_WS_SEMAPHORE_STABLE` | TBD | **CURRENT** — WS semaphore fix + 7 critical Feb 24 fixes (Bugs #34-40) |
| `WORKING_FEB23_2026_COPY_TRADER_STABLE` | `98021d6` | Pre-Feb24 fallback — Copy Trader working but no WS stability fixes |
| `WORKING_FEB20_2026_BROKER_QTY_SAFETY_NET` | `bb1a183` | Broker-verified qty safety net + brevo pin (+ `5b6be75`) |
| `WORKING_FEB20_2026_DCA_FIELD_FIX_STABLE` | `656683a` | DCA field fix, env crash fix, JADVIX auto-enable, cascade delete |
| `WORKING_FEB18_2026_DCA_SKIP_STABLE` | `c75d7d4` | DCA-off bracket fix + multiplier trim scaling |
| `WORKING_FEB18_2026_FULL_AUDIT_STABLE` | `fbd705d` | Pre-DCA-fix fallback (audit cleanup) |
| `WORKING_FEB18_2026_TIME_FILTER_STABLE` | `9470ca5` | Time filter status on Control Center |
| `WORKING_FEB17_2026_MULTI_BRACKET_STABLE` | `8f61062` | Native multi-bracket orders |
| `WORKING_FEB16_2026_WHOP_SYNC_STABLE` | `ce19d18` | Whop sync daemon, CSRF fix |
| `WORKING_FEB12_2026_SPEED_RESTORED_STABLE` | `c63de44` | Speed restored, affiliate added |
| `WORKING_FEB7_2026_PRODUCTION_STABLE` | `b475574` | **THE BLUEPRINT** — production stable, demo+live flawless |

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

**Why this exists:** JADMGC had a stale DB position. With DCA off, it got downgraded from a 3-contract bracket order to a 1-contract REST market order with wrong TP handling. Both layers were treating "existing position" as "must be DCA" regardless of the DCA setting.

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

**Why this exists:** A 5x multiplier with 3 TP legs of 1 contract each produced legs of 1, 1, 13 instead of 5, 5, 5. The contract trim values were not being scaled.

**Rule:** Any time a raw contract count from settings is used in execution, check if it needs `* account_multiplier`. The Percent path works automatically because it calculates off `adjusted_quantity`.

---

## RULE 14: SIGNAL TRACKING MUST RESPECT DCA STATUS (Feb 18, 2026)

The `_bg_signal_tracking()` background thread in `ultra_simple_server.py` (~line 16933) writes to `recorded_trades`. The main webhook handler at line ~16633 reads `recorded_trades` to detect existing positions. **These two must stay in sync.**

**When DCA is OFF and same-direction signal arrives:**
- Close the old `recorded_trades` record (`status='closed'`, `exit_reason='new_entry'`)
- Insert a fresh record with the new entry price and quantity
- This prevents stale open records from piling up

**When DCA is ON and same-direction signal arrives:**
- Insert a new DCA add record (existing behavior — stack positions)

**Why this exists:** Without this, every same-direction signal on a DCA-off strategy inserted a NEW `status='open'` row without closing the old one. JADMNQ accumulated 12 stale open records. When the main handler queried `recorded_trades` for position detection, it found these stale records, which influenced quantity logic and bracket decisions even though DCA was off.

**The `is_dca` flag is passed from the main handler** (where it's already correctly computed at line ~16724-16748) to the background thread via the Thread args at line ~17086.

**NEVER** remove the `t_is_dca` parameter or unconditionally insert DCA add records. If this is reverted, stale records will accumulate and pollute position detection within hours.

---

## RULE 15: TICK SIZE LOOKUP — HANDLE 2-LETTER SYMBOL ROOTS

Futures contract names: `{ROOT}{MONTH}{YEAR}` (e.g., `GCJ6`, `NQH6`, `MGCJ6`). Root can be 2 or 3+ chars. Month letter (H/J/K/M/N/Q/U/V/X/Z) is NOT part of the root.

When looking up tick_size: try 3-char match first, then 2-char match. First match wins. Default 0.25 is WRONG for many symbols:
- GC = 0.10, CL = 0.01, SI = 0.005, HG = 0.0005, NG = 0.001
- **Affected 2-letter symbols**: GC, CL, SI, HG, PL, NG, HO, RB, ZB, ZN, ZF, ZT, DX, KC, CT, SB, YM

---

## RULE 16: TRADOVATE API RATE LIMITS ARE PER TOKEN, NOT PER ACCOUNT

All accounts sharing the same Tradovate token share ONE rate limit. JADVIX with 7 accounts = 7x API calls against the SAME token quota.

**NEVER** add "just one extra broker query per account" — it multiplies by the number of accounts. What seems like +1 call is actually +7 calls against a shared rate limit.

**Before adding ANY new broker API call**, count how many times it will execute per signal across all accounts.

---

## RULE 17: dict.get() DEFAULT IS IGNORED WHEN KEY EXISTS WITH None VALUE

```python
# WRONG — returns None if key exists with value None:
result.get('error', 'Unknown error')

# RIGHT — handles both missing key AND None value:
result.get('error') or 'Unknown error'
```

`execute_trade_simple` initializes `result = {'error': None}`. The key EXISTS with value None, so `.get('error', 'Unknown error')` returns None, not 'Unknown error'. This caused `TypeError: argument of type 'NoneType' is not iterable` in broker_execution_worker.

**Rule:** When a dict might have explicit None values, ALWAYS use `or` instead of the default parameter.

---

## RULE 18: TEMPLATE JS MUST MATCH SERVER API ENDPOINTS

When restoring server code from a git tag or older commit, template `fetch()` calls may not match the server's `@app.route()` definitions.

**Example:** `admin_affiliates.html` called `/api/admin/affiliates/{id}/approve` but server only had `/api/admin/affiliates/{id}/status`.

**After any server restore or route change:**
1. Grep templates for `fetch(` calls
2. Verify each URL has a matching `@app.route()` in the server
3. Check HTTP methods match (POST vs PUT vs PATCH)

---

## RULE 19: POSITION SIZE NULL FALLBACK CHAIN — EXPLICIT VALUES ONLY

Trader settings override recorder defaults. NULL falls back to recorder value. Template `{{ field or 1 }}` displays NULL as "1" in the UI — user sees "1" but system uses the recorder's value (which might be 2).

**Rule:** Always set explicit values on traders. Never rely on NULL fallback. When creating/updating traders, ensure `initial_position_size` and `add_position_size` are set to actual numbers, not NULL.

---

## RULE 20: NEVER ADD SIGNAL BLOCKING TO WEBHOOK HANDLER OR BROKER WORKER

On Feb 17, 2026, adding signal blocking ("set on queue" + "clear on failure") to `ultra_simple_server.py` caused bracket orders to STOP WORKING. Root cause was never identified. Reverting the changes fixed it immediately.

**Rule:** Do NOT modify the webhook handler or broker worker to add signal blocking, dedup, or mutex logic. If signal blocking is needed, implement it in a SEPARATE layer (e.g., Redis, a pre-queue filter) that does NOT touch the sacred functions.

---

## RULE 21: VERIFY RAILWAY ENVIRONMENT VARIABLES WITH FULL VALUES

Railway's table display TRUNCATES long values. `WHOP_API_KEY` showed 42 chars but the full key is 73 chars.

**After setting any Railway env var:**
```bash
railway variables --kv  # Shows FULL values, not truncated
```

**Never trust the Railway dashboard table** for long values (API keys, secrets, tokens).

---

## RULE 22: ALWAYS TEST EXTERNAL API RESPONSES WITH REAL CURL BEFORE WRITING PARSING CODE

On Feb 16, 2026, code assumed Whop `membership.product` was a dict `{"id": "prod_xxx"}` — it's actually a **string** `"prod_xxx"`. Code assumed `membership.user` was a dict with email — it's a string user ID. Email is a top-level field: `membership.email`.

**Rule:** Before writing code that parses ANY external API response:
1. Make a real curl/httpie call to the API
2. Print the actual response structure
3. Check if fields are strings, dicts, arrays, or null
4. Use `isinstance()` checks for polymorphic fields

---

## RULE 23: CSRF EXEMPT LIST MUST COVER ALL EXTERNAL POST ENDPOINTS

The `_CSRF_EXEMPT_PREFIXES` list must include EVERY route that receives POST requests from external services (webhooks, OAuth callbacks, payment processors).

**Current exempt prefixes that MUST exist:**
- `/webhook/` — TradingView webhooks (singular)
- `/webhooks/` — Whop webhooks (plural with S)
- `/oauth/` — OAuth callbacks

**After adding any new external POST endpoint:** Add its prefix to `_CSRF_EXEMPT_PREFIXES` and test with a real POST from the external service.

---

## RULE 24: FRONTEND/BACKEND FIELD NAME MISMATCH — DCA TOGGLE (Feb 19, 2026)

The frontend (`traders.html` line 314) sends `avg_down_enabled`. The backend (`ultra_simple_server.py` trader create/update) reads `dca_enabled`. These are DIFFERENT field names for the SAME setting.

**What broke:** The create trader endpoint checked `dca_enabled` from the request body — it was always `None` because the frontend sent `avg_down_enabled`. Then `if dca_enabled is None: dca_enabled = False` hardcoded it to False. DCA was ALWAYS off regardless of UI toggle.

**Fix (3 places):**
1. **Create trader** (`ultra_simple_server.py` ~line 13531): Bridges `avg_down_enabled` → `dca_enabled`, falls back to recorder's `avg_down_enabled`
2. **Update trader** (`ultra_simple_server.py` ~line 13784): Accepts EITHER `dca_enabled` or `avg_down_enabled` field name
3. **Startup auto-fix** (`ultra_simple_server.py` ~line 8956): `UPDATE traders SET dca_enabled=TRUE WHERE recorder linked to JADVIX recorders` — ensures all JADVIX traders have DCA on every deploy

**NEVER remove the startup auto-fix.** All JADVIX strategies REQUIRE DCA enabled for all users. This is a business requirement.

**Rule:** When adding new settings, ALWAYS verify the HTML form field name matches the Python request.form/request.json key. Check: `grep -n 'name=' templates/traders.html | grep avg` vs `grep -n 'avg_down\|dca_enabled' ultra_simple_server.py`

---

## RULE 25: VARIABLE MUST BE DEFINED IN ALL BRANCHES BEFORE USE (Feb 20, 2026)

Python raises `UnboundLocalError: cannot access local variable` when a variable is assigned in only SOME branches of an if-elif-else chain but used AFTER the chain unconditionally.

**What broke:** `recorder_service.py` line 1338 logged `{env}`, but `env` was only assigned in the `else` branch (line 1279). When accounts had `acct.environment` set (first branch), `env` was never defined. The `except` at line 1339 caught the crash silently → the entire `enabled_accounts` parsing failed → trader got **zero accounts to execute on** → 0 trades placed.

**Fix:** Changed `{env}` to `{env_label}` which is defined at line 1283 unconditionally.

**Rule:** After writing ANY if-elif-else chain, check that EVERY variable used AFTER the chain is defined in ALL branches (or before the chain). Pay special attention to logger lines that reference variables from branching logic.

**Detection:** `python3 -c "import py_compile; py_compile.compile('file.py', doraise=True)"` does NOT catch this — it's a runtime error, not a syntax error. Must trace the code path manually.

---

## RULE 26: ADMIN DELETE MUST CASCADE CHILD RECORDS (Feb 19, 2026)

PostgreSQL enforces foreign key constraints. `DELETE FROM users WHERE id = ?` will FAIL with `foreign key constraint violation` if the user has records in child tables.

**What broke:** Admin panel user delete (`/admin/users`) only did `DELETE FROM users` without cleaning child records first. Got `accounts_user_id_fkey` violation error.

**Fix:** Cascade deletion in dependency order before deleting user:
```
support_messages → recorded_trades → recorded_signals → recorder_positions → traders →
support_tickets → recorders → strategies → push_subscriptions → accounts →
(nullify: announcements.created_by, affiliate_applications.reviewed_by) → users
```

**Rule:** When deleting a parent record, ALWAYS delete/nullify ALL child records first. Use `%s`/`?` placeholder pattern (Rule 4). If adding a new table with a `user_id` foreign key, ADD it to the cascade deletion list in `admin_delete_user()`.

---

## DEPLOYED FEATURES (Stable, Confirmed Working)

| Feature | Commit | Date | Status |
|---------|--------|------|--------|
| Flip close cleanup (cancels resting orders) | `d531455` | Feb 13 | Confirmed on JADMGC |
| NoneType crash fix (`or` instead of default) | `d6f5f4a` | Feb 13 | Working |
| Whop sync daemon (30s poll, auto-create accounts) | `ce19d18` | Feb 16 | Working |
| CSRF fix for Whop webhooks | `ce19d18` | Feb 16 | Working |
| Native multi-bracket orders (multi-leg TP + trail) | `8f61062` | Feb 17 | Confirmed LIVE |
| Time filter status on Control Center | `9470ca5` | Feb 18 | Working |
| DCA-off bracket fix | `c75d7d4` | Feb 18 | Confirmed on all 4 recorders |
| Multiplier trim scaling | `201d498` | Feb 18 | Confirmed |
| ProjectX parity (opposite block, DCA SL, trailing) | `c9f0a3d` | Feb 13 | **UNTESTED** |
| User delete cascade (all child tables) | `a40fc07` | Feb 19 | Working |
| Insider signals admin bypass | `4e95998` | Feb 19 | Working |
| DCA field name fix (avg_down_enabled → dca_enabled) | `d3e714d` | Feb 19 | **Confirmed LIVE** |
| SSE real-time price streaming to dashboard | `8641182` | Feb 20 | Working |
| TradingView WebSocket JWT auth fix (was crashing) | `d43cd0c` | Feb 20 | **Needs verification** |
| JADVIX DCA auto-enable on startup | `bda90af` | Feb 19 | **Confirmed LIVE** |
| env UnboundLocalError fix in enabled_accounts | `656683a` | Feb 20 | Working |
| Tick size 2-letter symbol root fix (GC, CL, SI) | `656683a` | Feb 20 | Working |
| Broker-verified quantity safety net (DB/broker drift) | `bb1a183` | Feb 20 | Working |
| Brevo v1 pin + start.sh runtime install (activation emails) | `5b6be75` | Feb 21 | **Confirmed working** |
| Pro Copy Trader pricing card + sidebar gating + route locks | `99f990c` | Feb 22 | Working |
| TOS + Risk Disclosure updated with Goldman-reviewed legal language | `993d8b5` | Feb 22 | Working |
| Forgot password system (Brevo email + token reset, 1hr expiry) | `bd95145`..`9f8a7e1` | Feb 22 | **Needs verification** |
| Pro Copy Trader: PLATFORM_URL fix (localhost→127.0.0.1:PORT) | `e67add9` | Feb 22 | Working |
| Pro Copy Trader: Manual trade follower propagation (BUY/SELL/CLOSE) | `aa176a4` | Feb 22 | **Confirmed working** |
| Pro Copy Trader: Auto-mode toggle reload signal (5s pickup) | `4f854c5` | Feb 22 | Working |
| Pro Copy Trader: Auth gate bypass (X-Admin-Key for internal requests) | `03c5853` | Feb 23 | **Confirmed working** |
| Pro Copy Trader: Token refresh truthy dict fix + 85-min expiry | `b7529f9` | Feb 23 | **Confirmed working** |
| Pro Copy Trader: Parallel follower propagation (ThreadPoolExecutor) | `22f32be` | Feb 23 | **Confirmed working** |
| Pro Copy Trader: Cross-leader loop prevention (time-based dedup) | `e6fe62d` | Feb 23 | **CRITICAL FIX** |
| Pro Copy Trader: Pipeline separation (skip followers with webhook traders) | `e46c4a4` | Feb 23 | Working |
| TP Order Stacking Fix: SQL placeholders in reconciliation | Phase 1 | Feb 23 | **Confirmed working** |
| TP Order Stacking Fix: Symbol matching + status list | Phase 1 | Feb 23 | **Confirmed working** |
| TP Order Stacking Fix: Cancel-before-place + duplicate cleanup | Phase 1 | Feb 23 | **Confirmed working** |
| WebSocket Position Monitor (`ws_position_monitor.py`) | `636ae87` | Feb 23 | **Confirmed working** |
| WS Position Monitor startup integration | `fb4c67e` | Feb 23 | **Confirmed working** |
| Reconciliation downgraded to 5-min safety net | Phase 2 | Feb 23 | Working |
| WS monitors: market-hours reconnect fix | `2c53a6d` | Feb 23 | **Confirmed working** |
| Copy trader toggle: remove startup force-OFF reset | `ef813fe` | Feb 23 | **Confirmed working** |
| Copy trader toggle: optimistic UI + race condition fix | `39b8122` | Feb 23 | **Confirmed working** |
| Copy trader toggle: missing get_user_by_id import fix | `ce4e6a2` | Feb 23 | **Confirmed working** |
| FLASK_SECRET_KEY set as permanent Railway env var | N/A | Feb 23 | **CRITICAL — sessions survive deploys** |
| Auto-copy: parallel follower execution (asyncio.gather) | `b26dc75` | Feb 23 | **Confirmed working** |
| Auto-copy: add-to-position instead of close+re-enter | `b97eb10` | Feb 23 | **Confirmed working** |
| Copy trader: warning disclaimer (don't mix with webhooks) | `24e1094` | Feb 23 | Working |
| Paper trading accuracy: multiplier, DCA-off, trader overrides, trim scaling | `32ad0ab`..`a819a22` | Feb 23 | **Needs verification** |
| Shared WS Connection Manager (1-2 connections instead of 6-12) | `f1795c3` | Feb 23 | **Confirmed working** |
| WS Connection Manager: 429 storm fix (10x30s dead-sub, 30s stagger, 30s backoff) | `79e3f7b` | Feb 24 | **Confirmed working — ZERO 429s post-deploy** |
| Dead WebSocket pool disabled (`get_pooled_connection()` returns None) | `6efcbd5` | Feb 24 | **CRITICAL — eliminates 60s trade timeouts** |
| WS Connection Semaphore: asyncio.Semaphore(2) + 3s spacing on connects | `84d5091` | Feb 24 | **CRITICAL — stops 429 storm. NEVER REMOVE.** |
| WS Legacy dead-sub thresholds hardened to >= 10 in ALL 4 locations | `84d5091` | Feb 24 | **Confirmed working** |
| Token refresh daemon PostgreSQL fix (was sqlite3 in production) | `d457d44` | Feb 24 | **Confirmed working** |
| Unknown error diagnostic fix (propagates run_async exceptions) | `27c38c5` | Feb 24 | **Confirmed working** |
| max_contracts DEFAULT 10→0 migration (uncapped 172 traders) | `adb859b` | Feb 24 | **CRITICAL — silent trade cap removed** |

---

## MULTI-BRACKET ORDER SYSTEM (Feb 17-18)

### How It Works
One REST API call creates the entire bracket: entry + multiple TP legs + SL (fixed or trailing).

```
risk_config built in ultra_simple_server.py (~16829-16914)
  → take_profit: [{ticks, trim}, {ticks, trim}, ...]
  → trail: {trigger, frequency}
  → stop_loss: {ticks, type}
  → break_even: {enabled, ticks, offset}
  → trim_units: "Contracts" or "Percent"
```

### Critical Code Locations

**recorder_service.py (bracket builder):**
| Line | What | DO NOT TOUCH |
|------|------|-------------|
| ~2089 | `has_multi_tp` detection | Gate for multi-bracket path |
| ~2094-2097 | `use_bracket_order` gate | Must NOT have `not has_multi_tp` |
| ~2100-2141 | Trail/autoTrail/break-even extraction | Reads risk_config |
| ~2143-2182 | Multi-bracket leg builder | Builds multi_brackets_list |
| ~2189-2197 | `place_bracket_order()` call | Passes multi_brackets param |

**tradovate_integration.py (REST order builder):**
| Line | What | DO NOT TOUCH |
|------|------|-------------|
| ~1840-2080 | `place_bracket_order()` | Universal REST bracket builder |
| ~1916-1962 | Multi-bracket mode | Builds brackets[] from multi_brackets param |
| ~2005-2012 | Strategy payload | accountId, symbol, orderStrategyTypeId=2 |
| ~2022-2042 | REST POST + response parsing | orderStrategy/startOrderStrategy |

**ultra_simple_server.py (risk_config builder):**
| Line | What |
|------|------|
| ~16829-16914 | risk_config builder (take_profit, trail, stop_loss, break_even) |
| ~16919-16951 | broker_task queued with risk_config |
| ~14597 | Broker worker extracts risk_config |
| ~14659 | Passes risk_config to execute_trade_simple() |

---

## RULE 27: TRADINGVIEW SESSION COOKIES REQUIRED FOR REAL-TIME PRICES (Feb 20, 2026)

The TradingView WebSocket provides real-time CME market data to the dashboard, paper trading TP/SL monitor, and SSE price stream. It has **two auth levels**:

- **Premium JWT** (~100ms real-time) — requires valid session cookies in `accounts.tradingview_session`
- **Public fallback** (10-15 min delayed) — `"unauthorized_user_token"` when cookies missing/expired

**How it works:**
1. `get_tradingview_session()` reads `tradingview_session` JSON from `accounts` table
2. `get_tradingview_auth_token(session)` fetches `https://www.tradingview.com/chart/` with those cookies
3. Extracts JWT from HTML via regex: `"auth_token":"([^"]+)"`
4. JWT sent via `set_auth_token` WebSocket protocol message

**If JWT extraction fails, system SILENTLY falls back to delayed data.** No error, no alert — just stale prices everywhere.

**Cookie format in DB:** `{"sessionid": "xxx", "sessionid_sign": "yyy"}`

**Cookies expire** ~every 3 months. When prices become stale, CHECK COOKIES FIRST:
```sql
SELECT id, name, tradingview_session FROM accounts WHERE tradingview_session IS NOT NULL LIMIT 1;
```

**To update cookies:** Get `sessionid` and `sessionid_sign` from browser (Chrome DevTools → Application → Cookies → tradingview.com), then:
```sql
UPDATE accounts SET tradingview_session = '{"sessionid":"NEW_VALUE","sessionid_sign":"NEW_VALUE"}' WHERE id = 459;
```
Then redeploy (`railway up`) to restart the WebSocket with new JWT.

**Two TradingView WebSocket connections exist:**
1. `tv_price_service.py` — `TradingViewTicker` class, tracks 20 default symbols, feeds paper engine
2. `ultra_simple_server.py` — `connect_tradingview_websocket()`, feeds `_market_data_cache` for dashboard/SSE/TP-SL monitor

Both need the same session cookies. Both extract JWT the same way. Both fall back to delayed if JWT fails.

**NEVER:**
- Remove the JWT auth — cookies are the ONLY way to get real-time CME data via TradingView
- Pass cookies in WebSocket `additional_headers` — crashes on websockets 15+ (BaseEventLoop error)
- Send `"unauthorized_user_token"` when JWT is available — that's delayed data

---

## RULE 28: BROKER-VERIFIED QUANTITY SAFETY NET (Feb 20, 2026)

The webhook handler (`ultra_simple_server.py`) uses `recorded_trades` (DB) to detect existing positions and decide DCA vs fresh entry. But the DB can drift from broker reality (stale records, overnight carries, missed closes). When the DB says "in position" but the broker is actually flat, the webhook handler passes `add_position_size` instead of `initial_position_size`.

**Safety net** in `recorder_service.py` (~line 2194-2206): After the existing `get_positions()` broker check (line 2181), if broker confirms NO position and the signal is an entry (not CLOSE/FLATTEN/EXIT):
- Recalculates quantity as `initial_position_size * account_multiplier`
- Overrides `adjusted_quantity` if it differs from what Layer 1 passed
- Logs `BROKER/DB MISMATCH` warning when override fires

**Zero new API calls** — uses the existing `get_positions()` result that was already fetched for DCA detection.

**Two-layer protection against DB/broker drift:**
1. **Root cause** (Rule 14): Signal tracking closes old records when DCA off → prevents stale record pileup
2. **Safety net** (this rule): Even if stale records exist, broker verification catches the wrong quantity before execution

**NEVER:**
- Remove this safety net — it's the last line of defense against DB drift causing wrong sizing
- Add new API calls in this section — uses existing broker data only (Rule 16)
- Move this check AFTER the DCA logic — it must run BEFORE the DCA decision at line 2208

---

## RULE 29: PIN ALL PYTHON PACKAGE VERSIONS — ESPECIALLY brevo-python (Feb 21, 2026)

**What happened:** `brevo-python` was unpinned in `requirements.txt`. When Docker cache was busted, pip pulled **v4.0.5** instead of v1.x. Version 4.x completely removed the `brevo_python.rest` module, `TransactionalEmailsApi`, `Configuration`, and `SendSmtpEmail` classes our code uses. Every activation email failed with `ImportError` caught as "brevo-python not installed" — a misleading error message that sent debugging in the wrong direction for hours.

**Timeline of the disaster:**
1. **Feb 15**: `brevo-python` added to `requirements.txt` (unpinned)
2. **~Feb 16-17**: Deployed via method that installed v1.x → emails worked
3. **~Feb 20**: Docker cache busted → pip pulled v4.0.5 → `from brevo_python.rest import ApiException` raised `ImportError` → ALL activation emails failed silently
4. **Feb 21**: 3 users stuck (laserodkod88287, shumate105, supremerunz1121) with 8,800+ orphaned activation tokens from Whop sync daemon retrying every 30 seconds
5. **Feb 21**: Root cause found — pinned to `brevo-python<2.0.0` → emails confirmed working

**What we tried that DIDN'T work (and why):**
1. **Added comment to requirements.txt** to change file hash → Docker cache bust. **Failed**: Railway's Docker builder may use content-addressable caching that survived the change.
2. **Updated `BUILD_DATE` env in Dockerfile** → Only busts layers BELOW it. Pip install is ABOVE `BUILD_DATE`, so it stayed cached. This was the SAME mistake made on Feb 16 (commit `1a5e5e3`) — BUILD_DATE is at line 23, pip install at line 15.
3. **Added explicit `RUN pip install brevo-python`** after BUILD_DATE → Installed v4.0.5 (latest), not v1.x. Package installed but API incompatible.
4. **Added `pip install brevo-python` to start.sh** → Also installed v4.0.5 at runtime. Same API incompatibility.

**What ACTUALLY fixed it:**
- Pinned `brevo-python<2.0.0` in requirements.txt, Dockerfile, AND start.sh
- The start.sh runtime install is the belt-and-suspenders guarantee (bypasses all Docker caching)

**Dockerfile cache lesson — BUILD_DATE position matters:**
```dockerfile
COPY requirements.txt .          # Line 14 — cached by file hash
RUN pip install -r requirements  # Line 15 — cached if line 14 cached
ENV BUILD_DATE=2026-02-21        # Line 23 — ONLY busts lines BELOW this
COPY . .                         # Line 28 — busted by BUILD_DATE
```
Changing BUILD_DATE does NOT bust the pip install layer above it. To bust pip install, you must change the actual `requirements.txt` content OR the `RUN pip install` instruction text.

**`railway run` runs LOCALLY, not in the container:**
- `railway run python3 -c "import brevo_python"` tests your LOCAL Mac (Python 3.13)
- The deployed container runs Python 3.11 with its own site-packages
- NEVER trust `railway run` for verifying what's installed in production
- Use `railway logs` to check runtime behavior instead

**Rules for the future:**
1. **ALWAYS pin package versions** in requirements.txt — never use bare `package-name`
2. **Pin with upper bound** (`<2.0.0`) not exact version, to allow patch updates
3. **After adding ANY new package**, verify it works in production via `railway logs`, NOT `railway run`
4. **start.sh runtime install** is the safety net — keep `python -m pip install "brevo-python<2.0.0"` in start.sh
5. **If a package has "not installed" error**, check the INSTALLED VERSION first — it might be installed but API-incompatible

**NEVER:**
- Remove the version pin from `brevo-python<2.0.0`
- Upgrade to brevo-python v2+ without rewriting `account_activation.py` to use the new API
- Trust `railway run` to test what's in the production container
- Use `pip install --quiet ... 2>/dev/null` when debugging — it hides all errors
- Assume BUILD_DATE busts pip install cache (it doesn't — it's below the pip layer)

---

## RULE 30: DIAGNOSE BEFORE YOU FIX — MANDATORY DEBUG CHECKLIST (Feb 21, 2026)

**Why this rule exists:** On Feb 21, 2026, 4 consecutive fix attempts failed for the Brevo email issue because each "fix" was applied before the root cause was identified. The error said "brevo-python not installed" — the actual problem was v4 API incompatibility. Hours wasted on Docker cache busting when a 30-second version check would have found the real issue.

**This is the #1 pattern behind wasted debugging time in this project.** Jumping to a fix before understanding the problem.

### BEFORE attempting ANY fix, complete ALL 4 steps:

**Step 1: GET THE EXACT ERROR**
- Do NOT trust catch-all error messages (e.g., "not installed" might mean "wrong version")
- Read the actual exception, not the except handler's message
- If the error is inside a `try/except` that masks it, temporarily check logs for the real traceback
- Ask: "What EXACTLY is failing?" — not "What does the error message SAY is failing?"

**Step 2: VERIFY IN THE REAL ENVIRONMENT**
- **`railway run` runs on your LOCAL Mac** — it does NOT test the production container
- **`railway logs`** is the ONLY way to see what's happening in production
- If you need to test a Python import or value in production, add a temporary log line — don't trust local commands
- Ask: "Am I testing the ACTUAL environment where this runs?"

**Step 3: CHECK STATE BEFORE ASSUMING**
- If "not installed" → check what version IS installed (`pip show`, `pip list`)
- If "not found" → check if it exists under a different name/path
- If "failed" → check if it partially succeeded
- If "no data" → check if the data exists but in a different format
- Ask: "What is the CURRENT state?" — not "What do I THINK the state is?"

**Step 4: STATE YOUR DIAGNOSIS BEFORE WRITING CODE**
- Tell the user: "I believe the root cause is X because Y"
- If you can't state the root cause with confidence, YOU DON'T UNDERSTAND THE PROBLEM YET
- Get confirmation before writing any fix
- Ask: "Can I explain WHY this is broken, not just WHAT is broken?"

### If you skip these steps:
You will waste hours applying fixes to symptoms instead of causes. Every multi-attempt debugging session in this project's history (Brevo: 4 attempts, DCA: 3 layers, TP orders: 2 days) happened because diagnosis was skipped.

**One correct diagnosis > four fast fixes.**

---

## RULE 31: NEW FEATURE DOCUMENTATION CHECKLIST

When adding ANY new feature to the platform, complete ALL of these documentation steps before considering the work done:

1. **Update CLAUDE.md** — Add feature to the Deployed Features table with commit hash, date, and status
2. **Update relevant docs** — If the feature touches a broker, webhook, DB schema, or deployment, update the matching doc in `/docs/`
3. **Add to CHANGELOG_RULES.md** — If the feature modifies `recorder_service.py`, `ultra_simple_server.py`, or `tradovate_integration.py`, add the protected lines
4. **Update recovery tags** — If the commit is a new stable state, create a git tag and update CLAUDE.md Rule 11
5. **Update MEMORY.md** — If a new bug pattern was discovered, add it to the Critical Bug Patterns section
6. **Test with real signal** — Before documenting as "Working", confirm with a real webhook test. Mark as "UNTESTED" if not verified.
7. **Document settings** — If the feature adds new settings (DB columns, env vars, config fields), add them to DATABASE_SCHEMA.md and the enabled_accounts checklist (Rule 6)

**This checklist prevents documentation drift** — the #1 cause of "rebuild difficulty" in this project.

---

## RULE 32: INTERNAL HTTP REQUESTS MUST INCLUDE ADMIN KEY (Feb 23, 2026)

When the server makes HTTP requests to its own `/api/` endpoints (e.g., copy trader propagation POSTing to `/api/manual-trade`), the `_global_api_auth_gate()` at line ~3700 will block with 401 because internal `requests.post()` calls have no Flask session cookies.

**What broke:** ALL 16 copy trader follower trades returned `{"error":"Authentication required"}`. The propagation function (`_propagate_manual_trade_to_followers`) POSTed to `/api/manual-trade` without any auth — the `before_request` handler rejected every one.

**Fix:** Include `X-Admin-Key` header with value from `ADMIN_API_KEY` env var:
```python
_headers = {}
_admin_key = os.environ.get('ADMIN_API_KEY')
if _admin_key:
    _headers['X-Admin-Key'] = _admin_key
resp = requests.post(url, json=payload, headers=_headers, timeout=30)
```

**Applies to:**
- `_propagate_manual_trade_to_followers()` in `ultra_simple_server.py` (manual copy)
- `_execute_follower_entry()` in `ws_leader_monitor.py` (auto-copy)
- `_execute_follower_close()` in `ws_leader_monitor.py` (auto-copy close)
- ANY future code that makes internal HTTP requests to `/api/` routes

**Also beware: truthy dict check on token refresh results.**
`refresh_access_token()` returns `{'success': False, 'error': '...'}` on failure. Checking `if refreshed:` is ALWAYS True because non-empty dicts are truthy. Must use `if refreshed and refreshed.get('success'):`. This is a variant of Rule 17 (dict.get default ignored).

**NEVER:**
- Make internal `/api/` requests without `X-Admin-Key` header
- Use `if result:` to check success of a function that returns a dict — always check `.get('success')`
- Set Tradovate token expiry to 24 hours — they expire in 90 minutes. Use `timedelta(minutes=85)`

---

## RULE 33: FLASK_SECRET_KEY MUST BE PERMANENT ENV VAR (Feb 23, 2026)

`app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_hex(32)` generates a NEW random key on every deploy if the env var is not set. This invalidates ALL Flask sessions — every user gets logged out, every POST requiring `session.get('user_id')` fails with 401.

**What broke:** Copy trader toggle POST returned 500 because `session.get('user_id')` returned None after a deploy. The toggle handler couldn't authenticate the user. Combined with 3 other bugs (startup reset, race condition, missing import), the toggle was completely non-functional.

**Fix:** Set `FLASK_SECRET_KEY` as a permanent Railway env var (64-char hex string). Sessions now survive deploys.

**NEVER:**
- Remove `FLASK_SECRET_KEY` from Railway env vars
- Change the key value (logs out all active users)
- Use `secrets.token_hex()` as default in production — auto-generated keys die on restart

---

## RULE 34: AUTO-COPY POSITION SYNC — ADD/TRIM, DON'T CLOSE+RE-ENTER (Feb 23, 2026)

When the leader adds to a position (e.g., Long 1 → Long 2), the follower must ADD the difference (buy 1 more), NOT close the existing position and re-enter with the full target quantity.

**What broke:** The position sync `else` branch in `_copy_fill_to_followers()` (ws_leader_monitor.py ~line 1065) always did: close follower → enter target qty. For adds, this meant: sell 1, then buy 2 — two trades instead of one, a brief period with no position, and unnecessary commission.

**Three sync modes (ws_leader_monitor.py ~line 1065-1098):**

| Scenario | Leader Position Change | Follower Action |
|----------|----------------------|-----------------|
| **ADD** | Same side, higher qty (Long 1 → Long 2) | Buy the DIFFERENCE (1 more) |
| **TRIM** | Same side, lower qty (Long 3 → Long 1) | Sell the DIFFERENCE (2) |
| **REVERSAL** | Different side (Long 2 → Short 1) | Close + re-enter (correct behavior) |
| **ENTRY** | From flat (Flat → Long 2) | Fresh entry with risk config |
| **CLOSE** | To flat (Long 2 → Flat) | Close all |

**Key variables:** `leader_prev` (from fill_data), `leader_target_qty/side`, `follower_prev_qty = leader_prev_qty * multiplier`

**NEVER:**
- Close + re-enter for same-side position changes (costs extra commission, creates gap)
- Forget to apply `multiplier` to both target AND previous qty when calculating delta
- Forget to apply `max_pos` cap to both target AND previous qty

---

## RULE 35: AUTO-COPY FOLLOWERS MUST EXECUTE IN PARALLEL (Feb 23, 2026)

Both copy trader propagation paths MUST execute all followers simultaneously, never sequentially.

| Path | Parallel Method | Where |
|------|----------------|-------|
| **Manual copy** (UI button) | `ThreadPoolExecutor(max_workers=len(followers))` | `ultra_simple_server.py` `_propagate_manual_trade_to_followers()` |
| **Auto-copy** (WebSocket fill) | `asyncio.gather(*[_copy_one_follower(f) for f in followers])` | `ws_leader_monitor.py` `_copy_fill_to_followers()` |

**What broke:** Auto-copy had `for follower in followers:` — each follower's HTTP POST (3-5s) waited for the previous one. 5 followers = 15-25s per fill. Rapid trades from the leader queued up behind the per-leader lock, causing followers to fall minutes behind.

**NEVER:**
- Use a sequential `for` loop for follower execution — always parallel
- Remove the per-leader asyncio.Lock entirely (it prevents dedup issues) — just make execution inside it fast
- Add `await` calls inside a sequential loop for follower trades

---

## WHOP INTEGRATION (Feb 16)

**Sync Daemon:** Polls Whop API every 30 seconds, creates Just Trades accounts for new memberships, sends welcome emails.

**Critical Whop API gotchas:**
- `membership.product` is a **string** `"prod_xxx"`, NOT a dict
- `membership.user` is a **string** user ID, NOT a dict
- Email is a **top-level field**: `membership.email`
- Webhook route is `/webhooks/whop` (plural S) — must be in CSRF exempt list

**Three-layer protection:**
1. Whop webhook (real-time on purchase)
2. Sync daemon (30s poll catches missed webhooks)
3. Manual sync button in admin panel

---

## PROJECTX INTEGRATION (Feb 13 — UNTESTED)

**Status:** Deployed but NOT tested with real signals. Revert: `git revert c9f0a3d`

**Features added to `do_trade_projectx()` only:**
- Opposite signal blocking (blocks when DCA/avg_down enabled, caps qty otherwise)
- DCA stop loss placement (fixed + trailing)
- Trailing stop on first entry bracket

**ProjectX API specifics:**
- Sides: 0=Buy, 1=Sell (numeric)
- ORDER_TYPE_TRAILING_STOP = 5
- Contract matching: `str(pos.get('contractId')) == str(contract_id)` (type safety required)
- Methods: `get_positions()`, `get_orders()`, `cancel_order()`, `create_stop_order()`, `create_market_order_with_brackets()`

**NOT implemented for ProjectX:** Break-even, multi-leg TP, apply_risk_orders equivalent

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
- WebSocket pool code DISABLED (`get_pooled_connection()` returns None, commit `6efcbd5`) — system uses REST API. NEVER re-enable.
- TP operations: asyncio.Lock per account/symbol prevents race conditions
- **Shared WS Connection Manager**: ONE WebSocket per Tradovate token (~16-20 connections for 27 accounts), all monitors register as listeners. Messages parsed once, dispatched to all listeners. Listener errors isolated (try/except per listener). **Connection semaphore** (`asyncio.Semaphore(2)`) limits concurrent connects to 2 at a time with 3s spacing — NEVER REMOVE (Bug #40).
- **REFERENCE DOC**: `docs/TRADESYNCER_PARITY_REFERENCE.md` has the COMPLETE Tradovate WebSocket protocol, timing constants, reconnection strategy, and copy trader architecture. READ IT before touching ANY WebSocket code.

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

---

## SYSTEM COMPONENTS REFERENCE

### Background Daemons (All Auto-Start on Deploy)

| Daemon | File | Line | Interval | Critical? | What It Does |
|--------|------|------|----------|-----------|-------------|
| **Token Refresh** | recorder_service.py | ~302 | 5 min | YES | Refreshes Tradovate OAuth tokens before expiry (30-min window) |
| **Position Reconciliation** | recorder_service.py | ~6384 | 300 sec (5 min) | **CRITICAL** | Syncs DB with broker, auto-places missing TPs, enforces auto-flat |
| **Daily State Reset** | recorder_service.py | ~6324 | 60 sec (checks) | YES | Clears stale positions/trades at market open (LIVE recorders only) |
| **TP/SL Polling** | recorder_service.py | ~6138 | 1 sec / 10 sec | YES | Fallback price polling when WebSocket unavailable |
| **Position Drawdown** | recorder_service.py | ~6513 | 1 sec / 5 sec | No | Tracks worst/best unrealized P&L for risk management |
| **TradingView WebSocket** | recorder_service.py | ~6659 | Continuous | YES | Real-time CME prices for TP/SL monitoring and dashboard |
| **WebSocket Prewarm** | recorder_service.py | ~280 | Once (startup) | No | Pre-establishes Tradovate WebSocket connections |
| **Bracket Fill Monitor** | recorder_service.py | ~6433 | 5-10 sec | No | Currently DISABLED — bracket fill detection handled by TP/SL polling |
| **Whop Sync** | ultra_simple_server.py | ~9239 | 30 sec | No | Polls Whop API, creates accounts, sends activation emails |
| **Shared WS Manager** | ws_connection_manager.py | — | Continuous | **CRITICAL** | ONE WebSocket per token, shared by all monitors. Eliminates 429 rate limits (Rule 16) |
| **Position WS Monitor** | ws_position_monitor.py | — | Continuous | YES | Real-time position/fill/order sync — listener on shared WS manager |
| **Leader WS Monitor** | ws_leader_monitor.py | — | Continuous | YES | Pro Copy Trader auto-copy — listener on shared WS manager |
| **Max Loss Monitor** | live_max_loss_monitor.py | — | Continuous | YES | Max daily loss breach detection — listener on shared WS manager (Tradovate) + REST polling (ProjectX) |

**All daemons are daemon threads** (`daemon=True`) — they terminate automatically when the main process exits. NEVER change them to non-daemon or synchronous (Bug #9: 100% outage from exactly this).

### Token Refresh Daemon (recorder_service.py ~302)

Three-tier refresh strategy:
1. **Primary**: `POST /v1/auth/renewaccesstoken` with refresh_token (Bearer auth)
2. **Secondary**: `TradovateAPIAccess.login(username, password)` if refresh token fails
3. **Tertiary**: Falls back to stored credentials (trades still execute via API Access)

Checks every 5 minutes. Triggers refresh if token expires within 30 minutes. On failure: logs warning, adds account to `_ACCOUNTS_NEED_REAUTH` set (visible at `/api/accounts/auth-status`).

### Position Reconciliation (recorder_service.py ~6384)

**DO NOT DISABLE.** This is the safety net for the entire trading system.

What it does every 5 minutes (safety net — WS position monitor is primary):
1. `reconcile_positions_with_broker()` — Syncs DB quantity/avg price with broker
2. `check_auto_flat_cutoff()` — Flattens positions after configured market hours
3. **AUTO-PLACES missing TP orders** — If TP recorded in DB but not found on broker, places it
4. Closes DB records when broker is flat
5. Updates DB to match broker's actual position quantity

### Paper Trading System (ultra_simple_server.py ~351)

- Separate database: `paper_trades` table (SQLite `paper_trades.db` or PostgreSQL)
- Called from webhook handler for recorders in `simulation_mode=1`
- Deduplication: `_paper_trade_dedup` prevents duplicate signals within 1.0 second
- Tracks: entry/exit price, P&L, TP/SL levels, MFE/MAE, commission, cumulative P&L
- **Non-blocking**: Paper trades NEVER block the broker pipeline (daemon threads only)

### TradingView WebSocket (recorder_service.py ~6659)

Two connections exist (both use identical auth):
1. `recorder_service.py` — Feeds `_market_data_cache` for position tracking, TP/SL monitoring
2. `ultra_simple_server.py` — Feeds dashboard SSE price stream and paper trading engine

Authentication flow:
1. Read `tradingview_session` JSON from `accounts` table: `{"sessionid": "xxx", "sessionid_sign": "yyy"}`
2. Fetch `https://www.tradingview.com/chart/` with cookies
3. Extract JWT via regex: `"auth_token":"([^"]+)"`
4. Send `set_auth_token` WebSocket protocol message

Data quality:
- **Premium JWT** (~100ms real-time) — requires valid session cookies
- **Public fallback** (10-15 min delayed) — `"unauthorized_user_token"` when cookies missing/expired
- **Silent degradation** — no error or alert when falling back to delayed data

Protocol: Custom TradingView format with `~m~` delimiters. Subscribes via `quote_add_symbols`. Receives `qsd` (quote stream data) messages with symbol prices.

### Whop Sync Daemon (ultra_simple_server.py ~9239)

Polls every 30 seconds (`WHOP_SYNC_INTERVAL = 30`). Three-layer protection:
- **Layer 1**: Real-time Whop webhook (`/webhooks/whop`) — fires on purchase
- **Layer 2**: Sync daemon (30s poll) — catches missed webhooks, network failures
- **Layer 3**: Manual admin sync button

Email resend strategy:
- First sync: sends activation immediately
- If unactivated after 12 hours (`WHOP_RESEND_INTERVAL`): resends
- Stops after 3 days (`WHOP_RESEND_MAX_DAYS`)
- Tracks "stuck users" for admin review at `/api/admin/whop-sync-status`

### Shared WebSocket Connection Manager (ws_connection_manager.py)

Consolidates ALL Tradovate WebSocket connections into ONE connection per unique token. Three services register as listeners on the shared connections:

```
BEFORE: 6-12 WebSocket connections (caused HTTP 429 rate limits)
  ws_position_monitor.py  → 1-2 connections (one per token)
  ws_leader_monitor.py    → 1-3 connections (one per leader)
  live_max_loss_monitor.py → 3-7 connections (one per account)

AFTER: ~20 WebSocket connections (one per unique Tradovate OAuth token)
  ws_connection_manager.py → SharedConnection per token
    → PositionMonitorListener (position/fill/order sync)
    → LeaderMonitorListener (copy trade fill/order detection)
    → MaxLossMonitorListener (cashBalance breach detection)

NOTE: Each Tradovate account has its OWN unique OAuth token (token_key = last 8 chars).
27 accounts across 16+ unique tokens = 16-20 connections. NOT "1-2" as originally planned.
This is WHY the connection semaphore exists — see below.
```

**Wire Protocol (in SharedConnection):**
1. Connect to `wss://demo.tradovateapi.com/v1/websocket` (or live)
2. Wait for `o` frame → send `authorize\n0\n\n{token}` → wait for `a[{"i":0,"s":200}]`
3. Send `user/syncrequest` with UNION of all listener accounts (no entityTypes filter — all types sent)
4. Heartbeat `[]` every 2.5s, server timeout 10s
5. Dead subscription detection: **10 x 30s windows (300s)** with 0 data during market hours = reconnect
   - NEVER reduce below 10 windows — 3 windows caused 429 storms across 16+ connections (Bug #38)
   - Dead-sub reconnect uses minimum 30s backoff + 0-15s jitter (NOT the normal 1s reset)
6. Initial connection stagger: **0-30s random delay** per connection on startup (prevents simultaneous 429)
   - NEVER reduce below 30s — 16+ connections need wide spread for Tradovate WS rate limits
7. Max connection: 70 min (before 85-min token expiry), exponential backoff: 1→2→4→8...60s
8. Fresh token from DB before each reconnect
9. Dynamic subscription: new listener accounts trigger re-subscribe on next heartbeat

**Key Design:**
- Messages parsed ONCE in `SharedConnection._dispatch_message()`, pre-parsed items dispatched to all listeners
- Each listener's `on_message()` wrapped in try/except — one crashing listener doesn't affect others
- Thread-safe registration via `asyncio.run_coroutine_threadsafe()` from any thread
- `get_connection_manager()` returns singleton `TradovateConnectionManager`

**Connection Semaphore (Bug #40, Feb 24, 2026) — THE MOST CRITICAL PROTECTION:**
```python
# In ws_connection_manager.py __init__:
self._connect_semaphore = None  # initialized as asyncio.Semaphore(2) in _run_manager()

# In _run_connection(), wraps conn.connect():
async with self._connect_semaphore:
    success = await conn.connect()
    await asyncio.sleep(3)  # pause before releasing semaphore
```
- Limits concurrent Tradovate WebSocket connection attempts to 2 at a time
- 16+ connections all connecting simultaneously overwhelms Tradovate rate limits (HTTP 429)
- The semaphore ONLY gates the connect attempt — `conn.run()` (the long-running receive loop) is OUTSIDE the semaphore
- 3-second sleep after each attempt ensures the next waiter doesn't immediately slam Tradovate
- **CONFIRMED WORKING**: Post-deploy logs show 8 connections authenticating in 12 seconds, pairs ~3s apart, ZERO 429s
- **NEVER remove the semaphore** — without it, 16+ simultaneous WebSocket connects = instant 429 storm
- **NEVER increase semaphore above 2** — Tradovate rejects with HTTP 429 if too many connect at once
- **NEVER remove the 3-second sleep** — it's the minimum spacing needed between connection attempts

**NEVER (429 Storm Prevention — Bugs #38 + #40, Feb 24, 2026):**
- NEVER reduce dead-subscription threshold below 10 windows (300s) — was 3 (90s), caused 16+ connections to all reconnect simultaneously → Tradovate HTTP 429 rate limit → cycling reconnect storm every 90s
- NEVER reduce initial connection stagger below 30s — was 10s, too tight for 16+ connections
- NEVER reset backoff to 1s after dead-subscription disconnect — use minimum 30s + 0-15s jitter
- NEVER reduce reconnect jitter below 15s — was 5s, insufficient spread for 16+ simultaneous reconnects
- NEVER remove `asyncio.Semaphore(2)` from `_run_connection()` — this is THE fix that prevents 429 storms (Bug #40, commit `84d5091`)
- NEVER increase the semaphore value above 2 — Tradovate's rate limit can't handle more than 2 simultaneous WS connects
- NEVER remove the `await asyncio.sleep(3)` inside the semaphore block — it spaces out connection attempts
- Thin market hours (weekends, 5-6 PM ET) produce 0 data messages by design — this is NORMAL, not a dead subscription
- NEVER use the legacy standalone classes (`AccountGroupConnection` in ws_position_monitor.py, `LeaderMonitor` in ws_leader_monitor.py) — they are DEPRECATED dead code kept only for emergency rollback. Production uses `PositionMonitorListener` and `LeaderMonitorListener` on the shared manager.
- The `>= 10` threshold is enforced in ALL 4 locations: ws_connection_manager.py (lines 374, 679), ws_leader_monitor.py (line 846), ws_position_monitor.py (line 298). If you change ONE, change ALL FOUR.

**WHY the WebSocket Connection Manager Keeps Breaking (LEARN THIS):**
1. Each Tradovate account has a UNIQUE OAuth token → token_key = last 8 chars of token
2. 27 accounts across 16+ unique tokens = 16-20 simultaneous WebSocket connections
3. During thin market hours (late night, weekends) ALL connections get 0 data messages
4. Dead-subscription detection fires on ALL connections within seconds of each other
5. Without the semaphore, ALL 16+ connections try to reconnect at the SAME TIME
6. Tradovate's WebSocket endpoint rate-limits with HTTP 429
7. 429 rejection → exponential backoff → connections come back → 0 data again → repeat
8. This creates a cycling 429 storm that can last HOURS
9. The semaphore (max 2 concurrent + 3s spacing) ensures orderly reconnection
10. The 300s dead-sub threshold (vs 90s) gives more time for thin-market data to arrive
11. The 30-44s reconnect jitter spreads out reconnection attempts over ~15 seconds
12. **Reference**: `docs/TRADESYNCER_PARITY_REFERENCE.md` Part 3 has the official Tradovate WS protocol timing constants

**Public API:**
```python
manager = get_connection_manager()            # Singleton
manager.start()                               # Start daemon thread (idempotent)
manager.register_listener(token, is_demo, subaccount_ids, listener, db_account_ids)
manager.unregister_listener(listener_id)
manager.get_status() -> Dict                  # Status for monitoring endpoints
manager.is_connected_for_account(sub_id) -> bool
```

**Startup Order** (in `ultra_simple_server.py`):
1. `get_connection_manager().start()` — starts daemon thread with event loop
2. `start_live_max_loss_monitor()` — registers MaxLossMonitorListener(s)
3. `start_leader_monitor()` — registers LeaderMonitorListener(s)
4. `start_position_monitor()` — registers PositionMonitorListener(s)

### WebSocket Position Monitor (ws_position_monitor.py)

Real-time broker sync for ALL active Tradovate/NinjaTrader accounts. Keeps `recorder_positions` and `recorded_trades` in perfect sync with broker state, eliminating reliance on 5-minute reconciliation polling.

**Architecture:** Registers `PositionMonitorListener` on the shared connection manager (one listener per token group). No standalone WebSocket connections.

**Three Event Handlers:**

| Entity Type | Handler | DB Table Updated | What It Does |
|-------------|---------|------------------|-------------|
| `position` | `_handle_position_event()` | `recorder_positions` | Syncs `netPos`, `netPrice` with DB |
| `fill` | `_handle_fill_event()` | `recorded_trades` | Detects TP/SL fills, closes trade records |
| `order` | `_handle_order_event()` | `recorded_trades.tp_order_id` | Tracks TP order IDs, detects cancellations |

**Public API:**
```python
start_position_monitor()                      # Register listeners with shared manager
stop_position_monitor()                       # Unregister listeners
get_position_monitor_status() -> Dict         # Status dict for monitoring
is_position_ws_connected(recorder_id) -> bool # Used by reconciliation to skip auto-TP
```

**Key Implementation Details:**
- `_sub_to_recorders`: `Dict[int, List[int]]` — subaccount_id → [recorder_ids] (one-to-many mapping)
- Symbol resolution: REST `contract/item` call with cache (same as `ws_leader_monitor.py`)
- DB writes use `_get_pg_connection()` + `%s` placeholders (PostgreSQL only — production-only feature)
- All DB updates are idempotent — safe to receive same event twice
- SQL query uses `LOWER(a.broker)` for case-insensitive matching (broker column stores 'Tradovate' with capital T)
- `subaccount_id` lives on `traders` table, NOT `accounts` table (despite `accounts` also having one)

**Relationship to Reconciliation:**
- Position WS Monitor is the PRIMARY sync mechanism (real-time)
- Reconciliation daemon (`start_position_reconciliation()`) is the SAFETY NET (every 5 minutes)
- When WS monitor is connected for a recorder, reconciliation skips auto-TP placement for that recorder
- If WS monitor is down, reconciliation auto-TP logic continues as before

---

## USER ONBOARDING FLOW — COMPLETE LIFECYCLE

### Step 1: Purchase (Whop)

User purchases subscription on Whop marketplace. Whop fires webhook to `/webhooks/whop`.

**What can fail:** Webhook 403'd if `/webhooks/` not in CSRF exempt list (Bug #12). Whop API key truncated in Railway (Bug #13).

### Step 2: Account Creation

`auto_create_user_from_whop(email, whop_user_id)` in `account_activation.py` (~line 357):
1. Check if user exists by email (idempotent)
2. If new: generate temp username (`whop_{8_random_chars}`), random password
3. Call `create_user()` → insert into `users` table
4. Auto-approve via `approve_user(user.id)`
5. Generate 72-hour activation token
6. Send activation email via Brevo

**What can fail:** brevo-python version mismatch (Bug #24 — must pin <2.0.0). Email failure does NOT break account creation (try/except).

### Step 3: Activation Email

Sent via Brevo API (`account_activation.py` ~line 239):
- Uses `brevo_python.TransactionalEmailsApi` (v1.x API)
- HTML template with dark theme and blue "ACTIVATE MY ACCOUNT" button
- Activation URL: `{PLATFORM_URL}/activate?token={token}`
- Token expires in 72 hours

**What can fail:** brevo-python v4 breaks imports (Rule 29). BREVO_API_KEY env var missing. Email marked as spam.

### Step 4: User Activation

User clicks activation link → `/activate?token={token}`:
1. Validate token (not expired, not used)
2. User sets custom username and password
3. Account marked as activated
4. Redirect to login

### Step 5: Login

`/login` (POST) — session-based authentication:
1. Validate username/password
2. Store `user_id` in Flask session
3. Redirect to dashboard

**Forgot password flow:** `/login` → "Forgot password?" link → `/forgot-password` → enter email → Brevo sends reset email with 1-hour token → `/reset-password?token=xxx` → set new password → redirect to login. Never reveals if email exists (always generic success). Rate limited to 3 requests per email per hour. Previous tokens invalidated on new request. Token functions in `account_activation.py`, routes in `ultra_simple_server.py` (lines ~6120-6207), templates: `forgot_password.html`, `reset_password.html`.

### Step 6: Broker Authentication

User connects their broker account:
- **Tradovate/NinjaTrader**: OAuth flow → `/api/oauth/callback` → stores token in `accounts.tradovate_token`
- **ProjectX**: API key entered directly → stored in `accounts.projectx_api_key`
- **Webull**: App key/secret entered → stored in `accounts.webull_app_key/secret`

**What can fail:** OAuth callback not in CSRF exempt list. Token storage fails. Tradovate credentials invalid.

### Step 7: Trader Setup

User creates a trader linking their account to a recorder:
- `POST /api/traders` with `recorder_id`, `account_id`, risk settings
- Settings inherited from recorder where not overridden (NULL fallback chain — Rule 19)
- **DCA field name bridge**: Frontend sends `avg_down_enabled`, backend stores as `dca_enabled` (Rule 24)
- JADVIX traders auto-fixed to `dca_enabled=TRUE` on every deploy

### Step 8: First Trade

TradingView alert fires → `POST /webhook/{webhook_token}`:
1. 10 webhook workers parse signal in <50ms
2. `process_webhook_directly()` finds recorder, applies filters, builds risk_config
3. Signal queued to `broker_execution_queue`
4. 10 broker workers pick up, call `execute_trade_simple()`
5. `do_trade_for_account()` runs per account simultaneously via `asyncio.gather()`
6. First entry: bracket order (entry + TP + SL in one REST call)
7. DCA entry: REST market order + separate cancel/replace TP

**What can fail:** See the 30 past disasters table. Most common: tick rounding (Rule 3), SQL placeholders (Rule 4), field name mismatches (Rule 24).

---

## PRODUCTION STRATEGY CONFIG SNAPSHOT

> **WARNING:** These settings are stored in the PostgreSQL database on Railway. If the database is lost, these configs are gone forever. This section documents the config structure and known production values.

### How to Extract Current Configs

```bash
# Connect to production PostgreSQL
railway connect postgres

# Export all recorder configs
SELECT id, name, symbol, initial_position_size, add_position_size,
       tp_units, trim_units, tp_targets, sl_enabled, sl_amount, sl_units,
       sl_type, trail_trigger, trail_freq, avg_down_enabled,
       avg_down_amount, avg_down_point, avg_down_units,
       break_even_enabled, break_even_ticks, break_even_offset,
       add_delay, signal_cooldown, max_signals_per_session,
       max_daily_loss, time_filter_1_enabled, time_filter_1_start,
       time_filter_1_stop, auto_flat_after_cutoff, custom_ticker,
       inverse_strategy, recording_enabled
FROM recorders WHERE recording_enabled = TRUE ORDER BY name;

# Export all trader overrides
SELECT t.id, t.recorder_id, r.name as recorder_name, t.account_id,
       t.enabled, t.multiplier, t.initial_position_size, t.add_position_size,
       t.dca_enabled, t.tp_targets, t.sl_enabled, t.sl_amount, t.sl_type,
       t.trail_trigger, t.trail_freq, t.break_even_enabled,
       t.break_even_ticks, t.break_even_offset, t.max_daily_loss
FROM traders t JOIN recorders r ON t.recorder_id = r.id
WHERE t.enabled = TRUE ORDER BY r.name;
```

### Production Recorder Configs (Snapshot: Feb 21, 2026)

> **Run `/api/admin/export-configs` to get the latest values. This snapshot may be outdated.**

#### JADNQ V.2 (ID: 71) — NQ E-mini Nasdaq
```
initial_position_size: 1    add_position_size: 0
tp_targets: [{"ticks": 200, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: true   sl_amount: 50   sl_type: Trail   trail_trigger: 0   trail_freq: 0
avg_down_enabled: false   break_even_enabled: false
time_filters: disabled   max_daily_loss: 0   auto_flat: false
Active traders: 7 (multipliers: 1x, 1x, 1x, 1x, 1x, 1x, 3x init/multi-TP)
```

#### JADMNQ V.2 (ID: 70) — MNQ Micro Nasdaq
```
initial_position_size: 1    add_position_size: 0
tp_targets: [{"ticks": 200, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: true   sl_amount: 50   sl_type: Trail   trail_trigger: 0   trail_freq: 0
avg_down_enabled: false   break_even_enabled: false
time_filters: disabled   max_daily_loss: 0   auto_flat: false
Active traders: 3 (multipliers: 1x, 20x, 1x live)
NOTE: One live trader (id 1490) has time_filter_1 enabled: 9:30AM-3:00PM
```

#### JADVIX Medium Risk V.2 (ID: 67) — DCA Strategy
```
initial_position_size: 1    add_position_size: 1
tp_targets: [{"ticks": 50, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: false   sl_amount: 0   sl_type: Fixed
avg_down_enabled: true   avg_down_amount: 0   avg_down_point: 0
break_even_enabled: false
time_filters: disabled   max_daily_loss: 0   auto_flat: false
Active traders: 4 (multipliers: 1x, 1x, 2.5x, 1x) — ALL have dca_enabled=true
```

#### JADVIX HIGH RISK V.2 (ID: 68) — Aggressive DCA Strategy
```
initial_position_size: 1    add_position_size: 1
tp_targets: [{"ticks": 20, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: false   sl_amount: 0   sl_type: Fixed
avg_down_enabled: true   avg_down_amount: 0   avg_down_point: 0
break_even_enabled: false
time_filters: disabled   max_daily_loss: 0   auto_flat: false
Active traders: 2 (multipliers: 1x, 30x) — ALL have dca_enabled=true
```

#### MGC-C1MIN (ID: 69) — Micro Gold 1-Min
```
initial_position_size: 1    add_position_size: 1
tp_targets: [{"ticks": 20, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: false   sl_amount: 0   sl_type: Fixed
avg_down_enabled: false   break_even_enabled: false
time_filters: disabled   max_daily_loss: 400   auto_flat: false
Active traders: 0
```

#### Key Patterns Across All Strategies
- **JADVIX (DCA on)**: No SL, smaller TP (20-50 ticks), avg_down_enabled=true
- **JAD NQ/MNQ (DCA off)**: Trail SL 50 ticks, large TP (200 ticks), avg_down_enabled=false
- **MGC**: Micro Gold with $400 daily loss limit, no active traders currently
- **Multipliers in use**: 1x (most), 2.5x, 3x (multi-TP), 20x, 30x
- **trim: 100** = 100% of position on single TP (full close)

### Config Structure Reference

Each recorder has these settings (see `docs/DATABASE_SCHEMA.md` for full schema):

**Position Settings:**
- `initial_position_size` — Contracts for first entry (default: 2)
- `add_position_size` — Contracts for DCA adds (default: 2)

**TP Settings:**
- `tp_units` — `'Ticks'`, `'Points'`, or `'Percent'`
- `trim_units` — `'Contracts'` or `'Percent'` (Contracts mode MUST scale by multiplier — Rule 13)
- `tp_targets` — JSON array: `[{"ticks": 20, "trim": 1}, {"ticks": 50, "trim": 1}]`

**SL Settings:**
- `sl_enabled` — 0/1
- `sl_amount` — Distance in `sl_units`
- `sl_units` — `'Ticks'`, `'Points'`, or `'Percent'`
- `sl_type` — `'Fixed'` or `'Trailing'`
- `trail_trigger` — Ticks before trail activates
- `trail_freq` — Trail update frequency in ticks

**DCA Settings:**
- `avg_down_enabled` — 0/1 (maps to trader `dca_enabled` — Rule 24)
- `avg_down_amount` — Contracts per DCA add
- `avg_down_point` — Distance to trigger DCA
- `avg_down_units` — `'Ticks'` or `'Points'`

**Break-Even:**
- `break_even_enabled` — 0/1
- `break_even_ticks` — Ticks in profit to move SL to break-even
- `break_even_offset` — Offset from entry (usually 0)

**Filters:**
- `add_delay` — Seconds between DCA entries (default: 1)
- `signal_cooldown` — Seconds between signals (default: 0)
- `max_signals_per_session` — 0 = unlimited
- `max_daily_loss` — Dollar amount, 0 = disabled
- `time_filter_1_start/end/enabled` — Trading hours window 1
- `time_filter_2_start/end/enabled` — Trading hours window 2
- `auto_flat_after_cutoff` — Flatten position after time window

**Trader-Level Overrides:**
All settings above can be overridden per trader. NULL = use recorder value. The `multiplier` field (default 1.0) scales ALL quantities for that account.

### JADVIX Startup Auto-Fix

**Location:** `ultra_simple_server.py` lines ~5651 and ~9068

On every deploy, automatically sets `dca_enabled=TRUE` on all traders linked to recorders with "JADVIX" in the name. This is a business requirement — all JADVIX strategies require DCA enabled for all users.

**NEVER remove this auto-fix.** It prevents the DCA field name mismatch (Rule 24) from disabling DCA on new traders.

---

## SUPPORTED BROKERS

| Broker | Status | Auth Type | Notes |
|--------|--------|-----------|-------|
| **Tradovate** | Working | OAuth + Credentials | Primary broker, full integration |
| **NinjaTrader** | Working | Same as Tradovate | Uses Tradovate API backend |
| **ProjectX/TopstepX** | Working | API Key | Prop firm support |
| **Webull** | Working | App Key/Secret | Stocks, options, futures |
| **Rithmic** | Coming Soon | - | Not implemented |

---

## POSTGRESQL COMPATIBILITY

```python
is_postgres = is_using_postgres()
placeholder = '%s' if is_postgres else '?'
enabled_value = 'TRUE' if is_postgres else '1'
```

---

## DEPLOYMENT

- **Production**: Railway — auto-deploys from `main` branch pushes
- **Manual deploy**: `railway up` (uploads code directly, bypasses git)
- **Local dev**: `python3 ultra_simple_server.py` → `http://localhost:5000`

---

## MONITORING ENDPOINTS

```bash
# Core health
curl -s "https://justtrades.app/health"
curl -s "https://justtrades.app/status"
curl -s "https://justtrades.app/health/detailed"           # Admin/API key required

# Broker execution
curl -s "https://justtrades.app/api/broker-execution/status"
curl -s "https://justtrades.app/api/broker-execution/failures?limit=20"
curl -s "https://justtrades.app/api/broker-queue/stats"

# Webhook activity
curl -s "https://justtrades.app/api/webhook-activity?limit=10"
curl -s "https://justtrades.app/api/raw-webhooks?limit=10"

# TradingView WebSocket
curl -s "https://justtrades.app/api/tradingview/status"
curl -s "https://justtrades.app/api/tradingview/auth-status"

# Account health
curl -s "https://justtrades.app/api/accounts/auth-status"
curl -s "https://justtrades.app/api/admin/max-loss-monitor/status"
curl -s "https://justtrades.app/api/admin/whop-sync-status"

# Paper trading & market data
curl -s "https://justtrades.app/api/paper-trades/service-status"
curl -s "https://justtrades.app/api/market-data/status"

# Thread health
curl -s "https://justtrades.app/api/thread-health"           # Admin/API key required

# Database
curl -s "https://justtrades.app/api/run-migrations"          # Admin/API key required
```

For complete endpoint details with response payloads, see `docs/MONITORING_ENDPOINTS.md`.

---

## DAILY MONITORING CHECKLIST (Pre-Market)

Run these checks before market open each trading day. Order matters — earlier checks catch issues that affect later ones.

### 1. Service Health
```bash
curl -s "https://justtrades.app/health" | python3 -m json.tool
```
**Healthy:** `"status": "ok"`. **Unhealthy:** Connection refused or error → Railway service down. Fix: `railway restart` or check `railway logs --tail`.

### 2. Broker Execution Workers
```bash
curl -s "https://justtrades.app/api/broker-execution/status" | python3 -m json.tool
```
**Healthy:** `broker_execution.workers_alive` = 10, `queue_size` = 0. **Unhealthy:** Workers < 10 or queue growing → restart service. Queue > 0 before market open → stale items, investigate.

### 3. Recent Failures
```bash
curl -s "https://justtrades.app/api/broker-execution/failures?limit=20" | python3 -m json.tool
```
**Healthy:** Empty or old failures only. **Unhealthy:** Recent failures with `"error": "token expired"` → check auth status. `"error": "rate limit"` → too many accounts on one token (Rule 16).

### 4. Tradovate Token Status
```bash
curl -s "https://justtrades.app/api/accounts/auth-status" | python3 -m json.tool
```
**Healthy:** `"all_accounts_valid": true`. **Unhealthy:** Accounts in `accounts_needing_reauth` → user needs to re-login via OAuth, or token refresh daemon has failed.

### 5. TradingView WebSocket (Real-Time Prices)
```bash
curl -s "https://justtrades.app/api/tradingview/status" | python3 -m json.tool
```
**Healthy:** `"websocket_connected": true`, `"jwt_token_valid": true`, `cached_prices` has recent timestamps. **Unhealthy:** `jwt_token_valid: false` → session cookies expired (~every 3 months). Update cookies per Rule 27.

### 6. Whop Sync Daemon
```bash
curl -s "https://justtrades.app/api/admin/whop-sync-status" | python3 -m json.tool
```
**Healthy:** `last_run` within 60 seconds, `stuck_users` = 0. **Unhealthy:** `last_run` > 5 minutes old → daemon stopped, restart service. `stuck_users` > 0 → manual email needed.

### 7. Webhook Activity (Last 24h)
```bash
curl -s "https://justtrades.app/api/webhook-activity?limit=50" | python3 -m json.tool
```
**Healthy:** `success_rate` > 95%, recent timestamps. **Unhealthy:** Low success rate → check failures. No recent webhooks during market hours → TradingView alerts may have stopped.

### 8. Thread Health
```bash
curl -s "https://justtrades.app/api/thread-health" | python3 -m json.tool
```
**Healthy:** All expected daemons running. **Unhealthy:** Missing threads → service needs restart.

### 9. Railway Logs (Quick Scan)
```bash
railway logs --tail 2>/dev/null | head -50
```
**Healthy:** Normal trade execution logs, no tracebacks. **Unhealthy:** `NameError`, `ImportError`, `TypeError` → code bug deployed. Roll back immediately.

### 10. Max Loss Monitor
```bash
curl -s "https://justtrades.app/api/admin/max-loss-monitor/status" | python3 -m json.tool
```
**Healthy:** No breaches. **Unhealthy:** `daily_loss_breach_count` > 0 → traders hitting loss limits, verify this is working correctly.

---

## INCIDENT RESPONSE PLAYBOOK

### Severity Levels

| Level | Definition | Response Time | Example |
|-------|-----------|---------------|---------|
| **SEV-1** | Total outage — NO trades executing | Immediate | NameError in sacred function, all workers dead |
| **SEV-2** | Degraded — Some trades failing | < 15 min | Token expired on one account, wrong position sizes |
| **SEV-3** | Single user — One account affected | < 1 hour | User's broker auth expired, trader disabled |

### SEV-1: Total Outage Response

**Symptoms:** No trades executing, all webhooks failing, service returning 500s.

**Step 1: Diagnose (< 2 minutes)**
```bash
# Check if service is up
curl -s "https://justtrades.app/health"

# Check logs for crash
railway logs --tail

# Check broker workers
curl -s "https://justtrades.app/api/broker-execution/status"
```

**Step 2: Immediate Rollback (if code change caused it)**
```bash
git reset --hard WORKING_FEB20_2026_BROKER_QTY_SAFETY_NET
git push -f origin main
# Wait ~90 seconds for Railway auto-deploy
```

**Step 3: Verify Recovery**
```bash
curl -s "https://justtrades.app/api/broker-execution/status"
# Confirm workers_alive = 10, queue_size = 0
```

**Step 4: Post-Incident**
- Check for missed signals during outage: `curl -s "https://justtrades.app/api/raw-webhooks?limit=50"`
- Check for orphaned positions: `curl -s "https://justtrades.app/api/broker-execution/failures?limit=50"`
- Position reconciliation daemon will auto-sync DB within 5 minutes (WS position monitor syncs in real-time)

### SEV-2: Degraded Performance

**Symptoms:** Some trades failing, high latency, wrong position sizes, TP/SL not placing.

**Common causes and fixes:**

| Symptom | Likely Cause | Diagnosis | Fix |
|---------|-------------|-----------|-----|
| Token expired errors | Token refresh daemon failed | `/api/accounts/auth-status` | User re-OAuth, or restart service |
| Wrong position sizes | Multiplier not applied, DCA mismatch | Check trader settings in DB | Verify multiplier, dca_enabled |
| TP/SL rejected | Price not on tick boundary | Check `broker-execution/failures` | Tick rounding bug (Rule 3) |
| High latency (>500ms) | Background thread changed to sync | Check logs for timing | Revert to stable tag |
| Queue growing | Workers stuck or dead | `/api/broker-execution/status` | `railway restart` |

### SEV-3: Single User Issue

**Symptoms:** One account not trading, one user can't log in, one trader getting wrong sizes.

**Diagnosis flow:**
1. Check trader enabled: `SELECT enabled FROM traders WHERE account_id = X`
2. Check account token: `/api/accounts/auth-status`
3. Check specific recorder: `/api/recorders/{id}/execution-status`
4. Check broker state: `/api/traders/{id}/broker-state`

### Common Failure Scenarios

**Scenario: Stale Records Polluting Position Detection**
```sql
-- Diagnosis: Find stale open records
SELECT id, recorder_id, ticker, side, status, entry_time
FROM recorded_trades WHERE status = 'open' ORDER BY entry_time;

-- Fix: Close stale records
UPDATE recorded_trades SET status = 'closed', exit_reason = 'manual_cleanup'
WHERE status = 'open' AND entry_time < NOW() - INTERVAL '24 hours';
```

**Scenario: Orphaned TP Orders on Broker**
```sql
-- Position reconciliation (runs automatically every 5 min) handles this
-- WS position monitor handles this in real-time
-- Manual trigger if needed:
curl -s "https://justtrades.app/api/run-migrations"
-- Then wait for next reconciliation cycle (5 min) or WS monitor (real-time)
```

**Scenario: Whop Users Not Getting Emails**
1. Check Whop sync: `curl -s "https://justtrades.app/api/admin/whop-sync-status"`
2. Check Brevo: Is `BREVO_API_KEY` set? Is brevo-python pinned <2.0.0?
3. Check stuck users: Look at `stuck_users` in sync status
4. Manual resend: Admin panel → Users → Resend activation

**Scenario: TradingView Prices Stale (10-15 min delay)**
1. Check: `curl -s "https://justtrades.app/api/tradingview/status"`
2. If `jwt_token_valid: false`: Session cookies expired
3. Fix: Get new cookies from browser, update DB (see Rule 27), redeploy

### Rollback Beyond Code

Sometimes the issue isn't just code — it's data state. After a code rollback:

1. **Stale DB records**: Check and clean `recorded_trades` with `status='open'` that shouldn't be
2. **Redis state**: `railway restart` clears in-memory state (signal tracking, dedup caches)
3. **Broker positions**: WS position monitor syncs in real-time; reconciliation safety net runs every 5 minutes
4. **Orphaned activation tokens**: Clean with `DELETE FROM activation_tokens WHERE expires_at < NOW()`

---

## WHAT'S WORKING (28 Settings Verified)

**Execution**: Enable/disable, initial/add position size, multiplier, max contracts
**TP**: Targets (ticks + trim %), units (Ticks/Points/Percent), trim_units (Contracts/Percent)
**SL**: Enable/amount, units, type (Fixed/Trailing), trail trigger/freq
**Risk**: Break-even (toggle/ticks/offset), DCA (amount/point/units)
**Filters**: Signal cooldown, max signals/session, max daily loss, add delay, time filters 1&2
**Other**: Custom ticker, inverse strat, auto flat after cutoff

---

## PAST DISASTERS — WHY EVERY RULE EXISTS

**Read this table. Every rule was written in blood (lost money, lost time, lost users).**

| # | Date | What Happened | Root Cause | Rule | Recovery Time |
|---|------|---------------|------------|------|---------------|
| 1 | Dec 4, 2025 | AI bulk-modified 3 files, deleted template | Batched changes | Rule 1 | Hours |
| 2 | Jan 12, 2026 | 15+ "improvements" → cascading failures | Refactored working code | Rule 2 | Hours |
| 3 | Jan 27, 2026 | 40% trade failures, missing credentials | Settings not in enabled_accounts | Rule 6 | Hours |
| 4 | Jan 28, 2026 | `failed_accounts` undefined, 30+ failures | Restructured try block | Rule 2 | Hours |
| 5 | Feb 6, 2026 | TP orders piling up (3-5 per position) | SQL `?` on PostgreSQL + cross-account TP ID | Rules 4, 5 | 2 days |
| 6 | Feb 6, 2026 | Wrong position sizes (2 instead of 1) | NULL masking in UI + missing fields in enabled_accounts | Rules 6, 19 | Hours |
| 7 | Feb 7, 2026 | TP rejected on DCA (fractional price) | Not rounding to tick_size | Rule 3 | Hours |
| 8 | Feb 7, 2026 | Cross-account TP contamination | DB has no subaccount_id column | Rule 5 | Hours |
| 9 | Feb 10, 2026 | **100% trade failure** — NameError | Rewrote override block, dropped `trader_initial_size`/`trader_add_size` | Rule 2, Sacred | Hours |
| 10 | Feb 12, 2026 | **100% OUTAGE 4+ HOURS** — mega-commit | Bundled affiliate + engine changes, background→sync, undefined `meta` | Rules 1, 2, 20 | **4+ hours** |
| 11 | Feb 13, 2026 | TypeError: `'string' in None` | dict.get() returns None when key exists with None value | Rule 17 | Hours |
| 12 | Feb 16, 2026 | Whop webhooks silently 403'd ALL day | CSRF exempt list had `/webhook/` not `/webhooks/` | Rule 23 | Hours |
| 13 | Feb 16, 2026 | Whop API calls all 401 Unauthorized | Railway env var truncated (42 of 73 chars) | Rule 21 | Hours |
| 14 | Feb 16, 2026 | Whop memberships all skipped silently | API response format wrong (string vs dict) | Rule 22 | Hours |
| 15 | Feb 17, 2026 | WebSocket multi-bracket silently failed | WebSocket pool was NEVER functional | Rule 10 | Hours |
| 16 | Feb 17, 2026 | Bracket orders stopped after signal blocking | Signal blocking changes in webhook handler | Rule 20, Sacred | Hours |
| 17 | Feb 18, 2026 | DCA-off got 1 contract instead of 3 | Two layers reacted to stale position when DCA off | Rule 12 | Hours |
| 18 | Feb 18, 2026 | Multiplier not applied to trim qty (1,1,13 instead of 5,5,5) | Raw contract count not scaled by multiplier | Rule 13 | Hours |
| 19 | Feb 18, 2026 | 12+ stale open records polluted position detection | Signal tracking ignored DCA off status | Rule 14 | Hours |
| 20 | Feb 18, 2026 | GC TPs 2.5x too far from entry | 2-letter symbol root GC→GCJ (3 chars) missed tick_sizes dict | Rule 15 | Hours |
| 21 | Feb 19, 2026 | DCA toggle ON had no effect — always False | Frontend sends `avg_down_enabled`, backend reads `dca_enabled` — field name mismatch | Rule 24 | Hours |
| 22 | Feb 20, 2026 | Trader 1359 got 0 accounts → 0 trades silently | `env` variable only defined in else-branch, crash caught by except → enabled_accounts parse failed | Rule 25 | Hours |
| 23 | Feb 19, 2026 | Admin user delete failed — FK constraint | `DELETE FROM users` without cascading child records first | Rule 26 | Hours |
| 24 | Feb 20-21, 2026 | **ALL activation emails failed for 2 days** — 3 users stuck, 8800+ orphaned tokens | `brevo-python` unpinned → Docker cache bust pulled v4.0.5 → `brevo_python.rest` module removed in v4 → `ImportError` logged as "not installed" (misleading). 4 failed fix attempts before finding root cause. `railway run` tested LOCAL Mac, not container. | Rule 29 | **Hours (multi-attempt)** |
| 25 | Feb 22-23, 2026 | Copy trader: ALL 16 follower trades returned "Authentication required" | Internal `requests.post()` to `/api/manual-trade` had no Flask session → `_global_api_auth_gate()` blocked with 401. Fix: `X-Admin-Key` header. | Rule 32 | Hours |
| 26 | Feb 23, 2026 | Copy trader: Token refresh overwrites valid tokens with expired ones | `if refreshed:` checks dict truthiness — non-empty `{'success': False}` is always True. Also set 24hr expiry (should be 85min). | Rule 17, 32 | Hours |
| 27 | Feb 23, 2026 | Copy trader: Follower trades executed sequentially (~600ms for 2 followers) | Simple `for follower in followers:` loop — each waited for previous to complete | `22f32be` | Minutes |
| 28 | Feb 23, 2026 | **Copy trader: 46 FILLS PER ACCOUNT — infinite cross-leader loop** | Tradovate WebSocket fill events do NOT include `clOrdId` → `JT_COPY_` prefix check never fires → cross-linked leaders (A↔B both leader AND follower) cascade fills infinitely. 3 NQ signals → 46 fills each on 3 demo accounts. | `e6fe62d` | Minutes |
| 29 | Feb 23, 2026 | TP orders stacking 5+ deep — burst fills on TP hit | Three compounding bugs: (1) SQL `?` silently fails on PostgreSQL, (2) hardcoded `'MNQ'` in symbol matching, (3) no cancel-before-place. Each 60s reconciliation cycle added another TP. | Phase 1 fixes | Hours |
| 30 | Feb 23, 2026 | Position monitor never started — placed in wrong file | `ws_position_monitor` startup in `recorder_service.py` `initialize()` which only runs under `__name__=='__main__'` — but recorder_service.py is always imported as a module. Also: SQL referenced `a.subaccount_id` (doesn't exist on accounts table), and `broker IN ('tradovate')` was case-sensitive but DB stores `'Tradovate'`. | `fb4c67e`, `636ae87` | Hours |
| 31 | Feb 23, 2026 | Copy trader toggle stuck "Disabled" — 4 compounding bugs | (1) `copy_trader_models.py` force-reset toggle OFF on every startup, (2) GET/POST race condition overwrites user click, (3) `get_user_by_id` not imported in toggle handler → 500, (4) `FLASK_SECRET_KEY` not set → sessions invalidated on every deploy | Rules 32, 33, 34 | Hours |
| 32 | Feb 23, 2026 | Auto-copy followers sequential — rapid trades queue up | `for follower in followers:` in `_copy_fill_to_followers()` → each follower waited for previous HTTP round-trip. 5 followers × 3-5s = 15-25s per fill. | `b26dc75` | Minutes |
| 33 | Feb 23, 2026 | Auto-copy close+re-enter on position add — follower gets closed then reopened | Position sync `else` branch always closed follower then re-entered target qty. Leader Long 1→Long 2 = follower sells 1, buys 2 instead of just buying 1 more. | `b97eb10` | Minutes |
| 34 | Feb 24, 2026 | **WS Connection Manager 429 storm — 16+ connections cycling every 90s** | Dead-subscription threshold too aggressive (3×30s=90s). During thin market hours, ALL connections hit 0 data → all reconnect simultaneously → Tradovate HTTP 429 → backoff → recover → 90s later repeat. Initial stagger (10s) too tight for 16 connections. Backoff reset to 1s after dead-sub disconnect. | `79e3f7b` | Hours |
| 35 | Feb 24, 2026 | **ALL trades 60-second timeout — dead WebSocket pool blocks entire pipeline** | `get_pooled_connection()` in recorder_service.py called `_ensure_websocket_connected()` which was NEVER functional (Rule 10). `_WS_POOL_LOCK` (asyncio.Lock) held during hanging connection attempt, blocking ALL account coroutines in `asyncio.gather()`. Every trade hit 60s timeout in `async_utils.py`. | `6efcbd5` | Hours |
| 36 | Feb 24, 2026 | **Token refresh daemon uses sqlite3 in PostgreSQL production** | `refresh_oauth_tokens()` used `sqlite3.connect()` instead of PostgreSQL connection pool. Tokens never refreshed → expired → 401s on all API calls. | `d457d44` | Hours |
| 37 | Feb 24, 2026 | **max_contracts DEFAULT 10 silently caps ALL traders** | Migration added `max_contracts` column with `DEFAULT 10`. New traders silently capped at 10 contracts. 172 traders affected. | `adb859b` | Hours |
| 38 | Feb 24, 2026 | **"Unknown error" masks EVERY failure — no diagnostics possible** | `run_async()` caught exceptions but returned generic `{'error': 'Unknown error'}`. Real errors (timeouts, 401s, connection failures) all looked identical. | `27c38c5` | Hours |
| 39 | Feb 24, 2026 | **429 storm PERSISTS after Bug #34 fix — 16+ connections still connect simultaneously** | Bug #34 fix (thresholds + stagger + backoff) was insufficient alone. When ALL 16+ connections hit dead-sub detection and enter reconnect simultaneously, `asyncio.create_task()` launches all of them at once. The 0-30s startup stagger only applies on initial boot — reconnects have no stagger. Tradovate rejects with HTTP 429 → cycle repeats indefinitely. | `84d5091` | Hours |
| 40 | Feb 24, 2026 | **COMPLETE FIX: asyncio.Semaphore(2) gates concurrent WS connection attempts** | Added `asyncio.Semaphore(2)` in `_run_connection()` wrapping `conn.connect()` + 3s sleep. Only 2 connections can attempt Tradovate WS connect at any time. Post-deploy: 8 connections authenticated in 12s, pairs ~3s apart, ZERO 429s. Also hardened legacy dead code thresholds (4 locations). THE definitive fix for the WS 429 storm. | `84d5091` | **Fix confirmed immediately** |

**Pattern:** 40 disasters in ~3 months. Average recovery: 2-4 hours each. Almost every one was caused by either (a) editing without reading, (b) batching changes, (c) restructuring working code, (d) field name mismatches between frontend and backend, (e) auth/session assumptions for internal requests, (f) dead code that silently blocks live paths (#35), or (g) concurrent connection attempts without rate limiting (#39-40).

**Feb 24 Session — THE WORST DAY (7 bugs in 12 hours):**
Bugs #34-40 were all discovered and fixed in a single session. The cascading failures:
1. Token refresh daemon was sqlite3 (never refreshed tokens in production)
2. max_contracts DEFAULT 10 silently capped every trader
3. "Unknown error" masked all diagnostics — couldn't see real errors
4. Dead WebSocket pool blocked ALL trades with 60s timeouts
5. WS connection manager 429 storm from aggressive dead-sub detection
6. 429 storm PERSISTED because the initial fix (thresholds) wasn't enough without a semaphore
7. Legacy dead code had old thresholds that could re-trigger the storm if accidentally activated
**Lesson:** When multiple systems fail simultaneously, fix the DIAGNOSTIC infrastructure first (Bug #38 = error visibility), then work outward from the most critical path (Bug #35 = trade execution), then fix the auxiliary systems (Bugs #34, #39-40 = WS stability).

**Near-miss prevented:** Webhook + copy trader pipeline overlap (4 follower accounts had both active webhook traders AND copy follower links). Would have caused double-fills. Fixed proactively with pipeline separation (`e46c4a4`) before any incident occurred.

---

## COMMON ANTI-PATTERNS — STOP YOURSELF IF YOU'RE ABOUT TO DO ANY OF THESE

1. **"While I'm in here, let me also..."** → NO. One change. Commit. Test. Next change.
2. **"This code is messy, let me clean it up"** → NO. Messy but working > clean but broken.
3. **"I'll just restructure this section for clarity"** → NO. This is how Bug #9 happened (100% outage).
4. **"I don't need to read the whole function"** → YES YOU DO. This is how Bug #7 happened (dropped variables).
5. **"Let me change this from background thread to synchronous"** → NO. This is how Bug #10 happened (10x latency).
6. **"I'll add some error handling here"** → Only if the user asked for it. Otherwise NO.
7. **"This variable name should be more descriptive"** → NO. Don't rename anything in sacred functions.
8. **"Let me extract a helper function"** → NO. Inline working code stays inline.
9. **"I'll combine these two commits into one"** → NO. One commit = one concern. Always.
10. **"I tested locally, should be fine in production"** → NO. PostgreSQL != SQLite. Railway != localhost.
11. **"I'll change the WebSocket connection code without reading TRADESYNCER_PARITY_REFERENCE.md"** → ABSOLUTELY NOT. Read `docs/TRADESYNCER_PARITY_REFERENCE.md` first. Every time. This doc has the OFFICIAL Tradovate WS protocol. Bugs #34, #37, #38, #39, #40 ALL happened because this doc wasn't consulted. The semaphore, dead-sub thresholds, heartbeat timing, reconnection strategy — it's ALL documented there.
12. **"The dead-sub threshold is too conservative, let me lower it"** → NO. 3 windows caused a 429 storm across 16+ connections. 10 windows is the MINIMUM. Read Bug #34 and #38.
13. **"I'll connect all WebSockets at once for faster startup"** → NO. This is EXACTLY how Bug #39/#40 happened. The semaphore limits to 2 concurrent connects + 3s spacing. NEVER REMOVE IT.

---

## API & PLATFORM DOCUMENTATION — READ BEFORE TOUCHING BROKER CODE

**Before working on ANY broker-specific code, READ the relevant doc first.**

| Doc | Path | When to Read |
|-----|------|-------------|
| **Tradovate API** | `docs/TRADOVATE_API_REFERENCE.md` | Editing tradovate_integration.py, bracket orders, REST calls, tick sizes |
| **TradeSyncer Parity (WS Protocol)** | `docs/TRADESYNCER_PARITY_REFERENCE.md` | **ANY WebSocket code**, ws_connection_manager.py, ws_leader_monitor.py, ws_position_monitor.py, copy trader, reconnection, heartbeat timing, syncrequest protocol. **MANDATORY READ before touching WS code.** |
| **ProjectX API** | `docs/PROJECTX_API_REFERENCE.md` | Editing projectx_integration.py, order types, bracket format |
| **Webull API** | `docs/WEBULL_API_REFERENCE.md` | Editing webull_integration.py, HMAC signing, order placement |
| **TradingView Webhooks** | `docs/TRADINGVIEW_WEBHOOK_REFERENCE.md` | Webhook handler, alert format, placeholders, retry behavior |
| **Whop API** | `docs/WHOP_API_REFERENCE.md` | Whop sync daemon, webhook handler, membership parsing |
| **Database Schema** | `docs/DATABASE_SCHEMA.md` | ANY SQL query, new columns, migrations, table structure |
| **Railway Deployment** | `docs/RAILWAY_DEPLOYMENT.md` | Deploying, env vars, rollback, monitoring endpoints |
| **Cheat Sheet** | `docs/CHEAT_SHEET.md` | Quick reference for common operations, tick sizes, debugging |
| **Monitoring Endpoints** | `docs/MONITORING_ENDPOINTS.md` | Health checks, status endpoints, response payloads, alert thresholds |
| **Testing Procedures** | `docs/TESTING_PROCEDURES.md` | End-to-end test signals, regression checklist, verification steps |

**Key API differences to remember:**
- **Tradovate**: OAuth + REST, bracket `params` = stringified JSON, values in POINTS
- **ProjectX**: API Key, integer order types/sides, inline bracket fields, values in TICKS
- **Webull**: App Key/Secret + HMAC-SHA256, NO native brackets
- **TradingView**: 3-second timeout, 15/3min rate limit, always return 200 immediately
- **Whop**: v1 REST = objects, v2/v5 webhooks = strings, always use `isinstance()` checks

---

## EXTERNAL DEPENDENCIES & FULL RECOVERY REFERENCE

> **If the database, Railway project, or TradingView alerts were lost, this section has everything needed to rebuild.**

### TradingView Alert Configuration

Each active recorder needs a TradingView alert pointing to its webhook URL. If alerts are lost, recreate them using this reference.

**Webhook URL pattern:** `https://justtrades.app/webhook/{webhook_token}`

**Alert message template (paste into TradingView Alert Message field):**
```json
{
    "action": "{{strategy.order.action}}",
    "ticker": "{{ticker}}",
    "contracts": {{strategy.order.contracts}},
    "price": {{strategy.order.price}},
    "position": "{{strategy.market_position}}",
    "time": "{{timenow}}"
}
```

**Active alerts needed (one per recorder):**

| Recorder | Symbol | Webhook Token Source | Chart/Indicator |
|----------|--------|---------------------|-----------------|
| JADNQ V.2 (ID: 71) | NQ (E-mini Nasdaq) | `SELECT webhook_token FROM recorders WHERE id=71` | User's NQ strategy |
| JADMNQ V.2 (ID: 70) | MNQ (Micro Nasdaq) | `SELECT webhook_token FROM recorders WHERE id=70` | Same strategy, micro contract |
| JADVIX Medium Risk V.2 (ID: 67) | MNQ | `SELECT webhook_token FROM recorders WHERE id=67` | VIX-based DCA strategy |
| JADVIX HIGH RISK V.2 (ID: 68) | MNQ | `SELECT webhook_token FROM recorders WHERE id=68` | Aggressive VIX DCA |
| MGC-C1MIN (ID: 69) | MGC (Micro Gold) | `SELECT webhook_token FROM recorders WHERE id=69` | 1-minute gold strategy |

**TradingView alert settings:**
- Condition: Per strategy's Pine Script logic
- Frequency: "Once per bar close" (safest — avoids 15/3min rate limit)
- Expiration: Set to far future or "Open-ended" if available
- Webhook URL: `https://justtrades.app/webhook/{token}` (HTTPS only, ports 80/443)
- **Account requirement:** TradingView Plus or higher + 2FA enabled

**If alerts auto-disabled (silent):** TradingView disables alerts after 15 triggers in 3 minutes with NO notification. Monitor via `/api/webhook-activity` — if no signals during market hours, check TradingView alerts first.

### Railway Environment Variables (Complete Reference)

**CRITICAL — Production will not function without these:**

| Variable | Length | Source | What It Does |
|----------|--------|--------|-------------|
| `DATABASE_URL` | ~100+ | Railway auto-set | PostgreSQL connection string |
| `REDIS_URL` | ~50+ | Railway auto-set | Redis for caching, paper trades, signal dedup |
| `BREVO_API_KEY` | ~40+ | [Brevo dashboard](https://app.brevo.com/) → SMTP & API → API Keys | Activation email sending (brevo-python <2.0.0) |
| `TRADOVATE_API_CID` | ~4-5 | Tradovate developer portal | Client ID (can be overridden per account in DB) |
| `TRADOVATE_API_SECRET` | ~36 | Tradovate developer portal | Client secret (can be overridden per account in DB) |

**HIGHLY RECOMMENDED:**

| Variable | Source | What It Does |
|----------|--------|-------------|
| `ADMIN_API_KEY` | Self-generated | API key for admin endpoints (`/health/detailed`, `/api/broker-execution/*`, etc.) |
| `FLASK_SECRET_KEY` | Self-generated (64-char hex) | Flask session encryption. If missing, auto-generates on each deploy (logs out all users) |
| `WHOP_API_KEY` | [Whop dashboard](https://dash.whop.com/) → API → Company API Key | **Must be full 73 chars** — Railway truncates in UI (Rule 21) |
| `WHOP_WEBHOOK_SECRET` | Whop dashboard → Webhooks → Signing Secret | **Must be full value** — verify with `railway variables --kv` |

**OPTIONAL (feature-specific):**

| Variable | Source | What It Does |
|----------|--------|-------------|
| `BREVO_SENDER_EMAIL` | Your domain | From address for emails (default: `noreply@justtrades.com`) |
| `PLATFORM_URL` | — | Base URL for activation links (default: `https://www.justtrades.app`) |
| `DISCORD_BOT_TOKEN` | Discord developer portal | Discord notifications (if enabled) |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Generated via `web-push` | Web push notifications |
| `FINNHUB_API_KEY` | Finnhub.io | Stock market data for dashboard |
| `OAUTH_REDIRECT_DOMAIN` | — | Override OAuth callback domain (default: auto-detected) |

**Verification after setting:**
```bash
railway variables --kv  # ALWAYS use --kv to see full values (not truncated table)
```

### Whop Product ID Mapping

Hardcoded in `whop_integration.py` lines 42-46 (NOT an env var):

| Whop Product ID | Plan Slug | Plan Name | Price |
|----------------|-----------|-----------|-------|
| `prod_PLACEHOLDER_COPY` | `pro_copy_trader` | Pro Copy Trader | $100/mo |
| `prod_l3u1RLWEjMIS7` | `platform_basic` | Basic+ | $200/mo |
| `prod_3RCOfsuDNX4cs` | `platform_premium` | Premium+ | $500/mo |
| `prod_oKaNSNRKgxXS3` | `platform_elite` | Elite+ | $1000/mo |

**TODO:** Replace `prod_PLACEHOLDER_COPY` with real Whop product ID once created. Update in `whop_integration.py` line 44 AND line 660.

**Plan features** (defined in `subscription_models.py` lines 56-126):
- **Pro Copy Trader**: Copy trading only, 10 broker accounts, 1 leader + 10 followers, NO recorders/traders/control center
- **Basic+**: Platform access, 5 broker accounts, unlimited strategies
- **Premium+**: + Quant screener, insider signals, premium strategies (JADNQ, JADVIX), 10 accounts
- **Elite+**: + API access, ALL 13 strategies, 25 accounts

**If Whop products change:** Update `WHOP_PRODUCT_MAP` dict in `whop_integration.py`, update `PLAN_FEATURES` in `subscription_models.py`, commit, deploy.

### Database Backup & Restore

The PostgreSQL database on Railway contains ALL user data, account configs, trade history, and broker tokens. **If this is lost, everything is lost.**

**Export current configs (automated):**
```bash
curl -s "https://justtrades.app/api/admin/export-configs?api_key=YOUR_KEY" > config_backup_$(date +%Y%m%d).json
```

**Full database backup:**
```bash
# Via Railway CLI
railway connect postgres
# Then in psql:
\copy (SELECT * FROM recorders) TO '/tmp/recorders_backup.csv' CSV HEADER;
\copy (SELECT * FROM traders) TO '/tmp/traders_backup.csv' CSV HEADER;
\copy (SELECT * FROM users) TO '/tmp/users_backup.csv' CSV HEADER;
\copy (SELECT * FROM accounts) TO '/tmp/accounts_backup.csv' CSV HEADER;

# Or full pg_dump (from local machine with Railway credentials)
pg_dump "$DATABASE_URL" > full_backup_$(date +%Y%m%d).sql
```

**Railway automatic backups:** Railway manages PostgreSQL backups automatically. Check Railway dashboard → Database → Backups for point-in-time recovery.

### TradingView Session Cookies (Rule 27)

Expire ~every 3 months. When prices on dashboard become stale (10-15 min delayed):

1. Open Chrome → tradingview.com → login to premium account
2. DevTools (F12) → Application → Cookies → `tradingview.com`
3. Copy `sessionid` and `sessionid_sign` values
4. Update database:
```sql
UPDATE accounts SET tradingview_session = '{"sessionid":"NEW_VALUE","sessionid_sign":"NEW_VALUE"}' WHERE id = 459;
```
5. Redeploy: `git push origin main` or `railway restart`
6. Verify: `curl -s "https://justtrades.app/api/tradingview/status"` → `jwt_token_valid: true`

### Complete Platform Recovery Checklist

If rebuilding from scratch:

1. **Deploy code** — `git clone` + `railway up` or connect Railway to GitHub repo
2. **Set env vars** — All CRITICAL + RECOMMENDED vars above via `railway variables --set`
3. **Run migrations** — `curl -s "https://justtrades.app/api/run-migrations"`
4. **Restore DB** — Import from backup or recreate recorders/traders from Production Config Snapshot
5. **Whop integration** — Set `WHOP_API_KEY` + `WHOP_WEBHOOK_SECRET`, verify at `/api/whop/status`
6. **Broker auth** — Users re-authenticate via OAuth (tokens can't be transferred)
7. **TradingView alerts** — Recreate per the table above with correct webhook tokens
8. **TradingView cookies** — Extract and insert per Rule 27
9. **Verify** — Run Daily Monitoring Checklist (all 10 items)
10. **Test** — Send a test webhook per `docs/TESTING_PROCEDURES.md`

---

## ADMIN ACCESS & ONBOARDING

> **Full policy: `docs/ADMIN_ACCESS_POLICY.md`**

### Two-Stage Access Model

| Stage | Access | Can Do | Can't Do |
|-------|--------|--------|----------|
| **Stage 1: Read-Only** | `CLAUDE_ADMIN_REFERENCE.md` + Claude Code | Monitor, diagnose, learn system | Edit code, deploy, restart, modify DB |
| **Stage 2: Repo Access** | Full GitHub repo + Claude Code | Submit PRs, review code | Push to main (branch protection required) |

### Stage 1 Safety Guarantees

Admins in Stage 1 cannot harm production because:
- **No repo** — can't edit code
- **No Railway CLI link** — can't restart, redeploy, or change env vars
- **No git credentials** — can't push anything
- **No DB credentials** — can't run SQL against production
- **Reference file sanitized** — all destructive commands removed

### Stage 2 Requirements (Before Granting Repo Access)

- [ ] Admin completed Stage 1 learning period
- [ ] Admin demonstrates understanding of the 31 rules and sacred files
- [ ] Branch protection configured on `main` (require PR + owner approval)
- [ ] Admin added as GitHub collaborator (Write, not Admin)
- [ ] All changes go through PRs — owner reviews before merge

### Admin Reference Files (Not in Repo)

| File | Purpose |
|------|---------|
| `CLAUDE_ADMIN_REFERENCE.md` | Read-only system manual (sanitized CLAUDE.md) |
| `README_FOR_ADMINS.md` | Setup guide for Claude Code + quick reference |

When CLAUDE.md is updated, regenerate `CLAUDE_ADMIN_REFERENCE.md` by stripping destructive commands and sending to all active admins.

---

## DETAILED DOCUMENTATION

- **`CHANGELOG_RULES.md`** — **MANDATORY** protected code registry. Enforced by Gate 1 — must be searched before any sacred file edit

Memory files (in `~/.claude/projects/-Users-mylesjadwin/memory/`):
- `MEMORY.md` — Master learnings file (loaded into every session)
- `WHY_IT_WORKS.md` — Logic document: what broke, why it's fixed, how to preserve it
- `feb7_production_stable_blueprint.md` — Full blueprint with every code location and commit
- `feb6_dca_tp_fix_details.md` — DCA/TP fix history (Bugs 1-4 detailed chain of failure)
- `multi_bracket_stable.md` — Multi-bracket order system architecture and code locations
- `projectx_feature_parity.md` — ProjectX parity features, API methods, testing checklist
- `pre_discord_extraction_snapshot.md` — File checksums and sacred function locations snapshot

---

*Last updated: Feb 23, 2026*
*Production stable tag: WORKING_FEB23_2026_COPY_TRADER_STABLE @ 98021d6*
*Total rules: 35 | Total documented disasters: 33 | Paid users in production: YES*
*Documentation: 11 reference docs in /docs/ | CHANGELOG_RULES.md | Memory: 9 files in ~/.claude/memory/*
