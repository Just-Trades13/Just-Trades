# Just Trades Platform — MASTER RULES & ARCHITECTURE

> **PRODUCTION STABLE STATE**: Tag `WORKING_FEB18_2026_DCA_SKIP_STABLE` @ commit `c75d7d4`
> **All 4 strats (JADNQ, JADMNQ, JADGC, JADMGC) verified identical bracket orders — Feb 18, 2026**
> **PAID USERS IN PRODUCTION — EVERY BROKEN DEPLOY COSTS REAL MONEY**

---

## RULE 0: CHECK CHANGELOG_RULES.md BEFORE ANY CODE EDIT

Before modifying ANY line in `recorder_service.py` or `ultra_simple_server.py`:
1. Open `CHANGELOG_RULES.md` in the repo root
2. Search for the line number or feature area you're about to touch
3. If it's listed → **DO NOT CHANGE IT** without explicit user approval
4. If restructuring a function containing a protected line → **STOP AND ASK**

This file exists because working fixes have been accidentally reverted multiple times,
causing failures for paying customers. It is the single source of truth for protected code.

---

## !! MANDATORY PROTOCOL — READ THIS BEFORE EVERY TASK !!

**This is not optional. This is not a guideline. This is a HARD REQUIREMENT for every single prompt.**

### BEFORE you edit ANY code:

1. **STATE your intent** — Tell the user exactly what you plan to change, which file, which function, and why. Do NOT start editing.
2. **AUTO-LOAD the relevant reference doc** — Based on what you're about to touch, READ the matching doc FIRST. This is not optional:

   | IF you're touching... | THEN READ this doc FIRST (use Read tool) |
   |----------------------|------------------------------------------|
   | `tradovate_integration.py` or Tradovate API calls | `docs/TRADOVATE_API_REFERENCE.md` |
   | `projectx_integration.py` or ProjectX API calls | `docs/PROJECTX_API_REFERENCE.md` |
   | `webull_integration.py` or Webull API calls | `docs/WEBULL_API_REFERENCE.md` |
   | Webhook handler, alert parsing, signal format | `docs/TRADINGVIEW_WEBHOOK_REFERENCE.md` |
   | Whop sync, membership parsing, `/webhooks/whop` | `docs/WHOP_API_REFERENCE.md` |
   | ANY SQL query, new column, migration, table change | `docs/DATABASE_SCHEMA.md` |
   | Deploying, env vars, Railway CLI, rollback | `docs/RAILWAY_DEPLOYMENT.md` |
   | Unsure about tick sizes, bracket syntax, debugging | `docs/CHEAT_SHEET.md` |

   **If the task involves multiple areas, read ALL relevant docs.** This takes 5 seconds and prevents hours of debugging.

3. **READ the full function/section** — You MUST use the Read tool on the target file and read the COMPLETE function you plan to modify. Not a summary. Not from memory. The actual current code. If you skip this, you WILL break something.
4. **CHECK which file you're touching** — If it's a CRITICAL file (see Sacred Files below), you MUST get explicit user approval before making ANY edit. Say: "This is a critical production file. Here's exactly what I want to change: [show diff]. Approve?"
5. **SHOW the exact change** — Before writing, tell the user the old code and the new code. No surprises.
6. **Make ONE minimal edit** — One change. Not two. Not "while I'm in here." ONE.
7. **VERIFY after editing** — After every edit, grep for undefined variables, check imports, and confirm no syntax errors.
8. **STOP and confirm** — After each change, stop. Tell the user what you did. Ask if they want to test before continuing. Do NOT chain multiple edits.

### IF the user asks for multiple changes:

- Create a numbered list of each change
- Do them ONE AT A TIME in separate edits
- After EACH edit, pause and report what was done
- NEVER batch changes into a single mega-edit

### IF the user asks about an API, broker, or integration:

- **Read the matching doc BEFORE answering.** Do not answer from memory. The docs contain production-verified gotchas, exact payloads, and lessons learned that your training data does NOT have.
- Example: "How does Tradovate handle trailing stops?" → Read `docs/TRADOVATE_API_REFERENCE.md` first, THEN answer.
- Example: "What format does TradingView send?" → Read `docs/TRADINGVIEW_WEBHOOK_REFERENCE.md` first, THEN answer.
- Example: "Why is Whop not syncing?" → Read `docs/WHOP_API_REFERENCE.md` first, THEN diagnose.

### IF you're unsure about ANYTHING:

- **ASK.** Do not guess. Do not assume. Do not "figure it out" by trying things.
- Wrong guesses in production = failed trades for paying customers

### WHAT HAPPENS WHEN YOU SKIP THIS PROTOCOL:

Every major outage in this platform's history happened because this protocol was skipped. See the disaster table at the bottom. 20+ incidents. Hours of recovery each time. Paying users affected.

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

---

## RULE 11: RECOVERY PROTOCOL

```bash
git reset --hard WORKING_FEB18_2026_DCA_SKIP_STABLE   # CURRENT stable
git reset --hard WORKING_FEB18_2026_FULL_AUDIT_STABLE  # Pre-DCA fix fallback
git reset --hard WORKING_FEB17_2026_MULTI_BRACKET_STABLE  # Pre-audit fallback
git reset --hard WORKING_FEB7_2026_PRODUCTION_STABLE   # THE BLUEPRINT
git push -f origin main  # CAUTION: force push — only if resetting
```

**Git Tags (Recovery Points):**

| Tag | Commit | Description |
|-----|--------|-------------|
| `WORKING_FEB18_2026_DCA_SKIP_STABLE` | `c75d7d4` | **CURRENT** — DCA-off bracket fix + multiplier trim scaling |
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
- WebSocket pool code exists but was NEVER functional — system uses REST API
- TP operations: asyncio.Lock per account/symbol prevents race conditions

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
curl -s "https://justtrades.app/api/broker-execution/status"
curl -s "https://justtrades.app/api/broker-execution/failures?limit=20"
curl -s "https://justtrades.app/api/webhook-activity?limit=10"
curl -s "https://justtrades.app/api/raw-webhooks?limit=10"
curl -s "https://justtrades.app/api/admin/max-loss-monitor/status"
curl -s "https://justtrades.app/api/run-migrations"
```

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

**Pattern:** 20 disasters in ~2.5 months. Average recovery: 2-4 hours each. Almost every one was caused by either (a) editing without reading, (b) batching changes, or (c) restructuring working code.

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

---

## API & PLATFORM DOCUMENTATION — READ BEFORE TOUCHING BROKER CODE

**Before working on ANY broker-specific code, READ the relevant doc first.**

| Doc | Path | When to Read |
|-----|------|-------------|
| **Tradovate API** | `docs/TRADOVATE_API_REFERENCE.md` | Editing tradovate_integration.py, bracket orders, REST calls, tick sizes |
| **ProjectX API** | `docs/PROJECTX_API_REFERENCE.md` | Editing projectx_integration.py, order types, bracket format |
| **Webull API** | `docs/WEBULL_API_REFERENCE.md` | Editing webull_integration.py, HMAC signing, order placement |
| **TradingView Webhooks** | `docs/TRADINGVIEW_WEBHOOK_REFERENCE.md` | Webhook handler, alert format, placeholders, retry behavior |
| **Whop API** | `docs/WHOP_API_REFERENCE.md` | Whop sync daemon, webhook handler, membership parsing |
| **Database Schema** | `docs/DATABASE_SCHEMA.md` | ANY SQL query, new columns, migrations, table structure |
| **Railway Deployment** | `docs/RAILWAY_DEPLOYMENT.md` | Deploying, env vars, rollback, monitoring endpoints |
| **Cheat Sheet** | `docs/CHEAT_SHEET.md` | Quick reference for common operations, tick sizes, debugging |

**Key API differences to remember:**
- **Tradovate**: OAuth + REST, bracket `params` = stringified JSON, values in POINTS
- **ProjectX**: API Key, integer order types/sides, inline bracket fields, values in TICKS
- **Webull**: App Key/Secret + HMAC-SHA256, NO native brackets
- **TradingView**: 3-second timeout, 15/3min rate limit, always return 200 immediately
- **Whop**: v1 REST = objects, v2/v5 webhooks = strings, always use `isinstance()` checks

---

## DETAILED DOCUMENTATION

- **`CHANGELOG_RULES.md`** — **MANDATORY** protected code registry. Check BEFORE any edit (Rule 0)

Memory files (in `~/.claude/projects/-Users-mylesjadwin/memory/`):
- `MEMORY.md` — Master learnings file (loaded into every session)
- `WHY_IT_WORKS.md` — Logic document: what broke, why it's fixed, how to preserve it
- `feb7_production_stable_blueprint.md` — Full blueprint with every code location and commit
- `feb6_dca_tp_fix_details.md` — DCA/TP fix history (Bugs 1-4 detailed chain of failure)
- `multi_bracket_stable.md` — Multi-bracket order system architecture and code locations
- `projectx_feature_parity.md` — ProjectX parity features, API methods, testing checklist
- `pre_discord_extraction_snapshot.md` — File checksums and sacred function locations snapshot

---

*Last updated: Feb 18, 2026*
*Production stable tag: WORKING_FEB18_2026_DCA_SKIP_STABLE @ c75d7d4*
*Total rules: 23 | Total documented disasters: 20 | Paid users in production: YES*
*Documentation: 8 reference docs in /docs/ | CHANGELOG_RULES.md | Memory: 7 files in ~/.claude/memory/*
