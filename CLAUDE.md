# Just Trades Platform — MASTER RULES & ARCHITECTURE

> **PRODUCTION STABLE STATE**: Tag `WORKING_FEB18_2026_DCA_SKIP_STABLE` @ commit `c75d7d4`
> **All 4 strats (JADNQ, JADMNQ, JADGC, JADMGC) verified identical bracket orders — Feb 18, 2026**

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

## RULE 1: NEVER TOUCH THE SACRED FUNCTIONS

These 5 functions are the beating heart of the platform. Do NOT refactor, rename, reorganize, "improve", or modify them without **explicit user permission for the specific change**:

| Function | File | What It Does |
|----------|------|--------------|
| `execute_trade_simple()` | `recorder_service.py` | Entire trade execution flow |
| `do_trade_for_account()` | `recorder_service.py` | Per-account broker execution |
| `process_webhook_directly()` | `ultra_simple_server.py` | Webhook → broker queue pipeline |
| `start_position_reconciliation()` | `recorder_service.py` | Keeps DB in sync with broker (runs every 60s) |
| `start_websocket_keepalive_daemon()` | `recorder_service.py` | Keeps WebSocket connections alive |

**What "don't touch" means:**
- No renaming variables
- No reordering logic
- No "cleanup" or "readability improvements"
- No adding error handling you think is missing
- No extracting helper functions
- If you need to ADD something, add it — don't restructure what's there

---

## RULE 2: ALWAYS ROUND PRICES TO TICK SIZE

Any code that calculates a price for Tradovate (TP, SL, or any limit/stop order) **MUST** round to the instrument's tick size:

```python
price = round(round(price / tick_size) * tick_size, 10)
```

**Why:** DCA weighted averages produce fractional prices (e.g., 25074.805555556). MNQ requires 0.25 increments. Tradovate REJECTS orders at invalid price increments. This bug caused TP orders to silently fail on DCA entries, leaving positions unprotected.

**Applied at:** TP calc (~1958), SL calc (~2128), reconciliation TP (~5332)

---

## RULE 3: ALWAYS USE POSTGRESQL-SAFE SQL PLACEHOLDERS

```python
placeholder = '%s' if is_using_postgres() else '?'
cursor.execute(f'SELECT * FROM table WHERE id = {placeholder}', (value,))
```

**NEVER** hardcode `?` in SQL queries. Production runs PostgreSQL. `?` silently fails — the query returns nothing instead of raising an error. This caused TP order lookups to silently return NULL, leading to duplicate TP orders stacking up.

**Check before committing:** `grep -n "'" recorder_service.py | grep "?"` to find remaining hardcoded `?`

---

## RULE 4: NEVER TRUST recorded_trades.tp_order_id FOR MULTI-ACCOUNT

The `recorded_trades` table has **NO** `subaccount_id` column. The `tp_order_id` field is shared across ALL accounts on a recorder. For multi-account recorders (like JADVIX with 7+ accounts), the last account to store its TP overwrites everyone else's.

**For DCA:** SKIP the DB `tp_order_id` lookup. Query the broker directly:
```python
all_orders = await tradovate.get_orders(account_id=str(account_id))
for order in all_orders:
    if order['ordStatus'] == 'Working' and order['action'] == tp_action:
        # This is the real TP for THIS account
```

**For reconciliation:** VALIDATE `accountId` matches before using a DB-stored `tp_order_id`.

---

## RULE 5: enabled_accounts MUST INCLUDE ALL SETTINGS

The per-account dictionary builder at `recorder_service.py` ~line 1138-1182 builds the config each account uses during execution. If a setting is missing from this dict, it silently falls back to defaults or NULL.

**Must include ALL of these:**
- `initial_position_size`, `add_position_size`, `recorder_id`
- `sl_type`, `sl_amount`, `sl_enabled`, `trail_trigger`, `trail_freq`
- `tp_targets`, `break_even_enabled`, `break_even_ticks`, `break_even_offset`
- `dca_enabled`, `custom_ticker`, `add_delay`, `signal_cooldown`
- `max_signals_per_session`, `max_daily_loss`
- `time_filter_*` (all time filter fields)
- `trim_units`

**When adding a new setting:** Add it to BOTH the enabled_accounts builder AND the legacy single-account path (~line 1187-1222).

---

## RULE 6: ONE CHANGE AT A TIME, TEST AFTER EACH

The worst disasters happened when 5+ changes were made at once. Make one change, test it, confirm it works, then move to the next. If something breaks with one change, you know exactly what caused it.

**Before ANY code change:**
1. State what you want to change and why
2. Get explicit approval
3. Make the minimal edit
4. Verify syntax: `python3 -c "import py_compile; py_compile.compile('file.py', doraise=True)"`
5. Commit before moving on

---

## RULE 7: NEVER REFACTOR OR "IMPROVE" WORKING CODE

Do not:
- Remove code you think is "unused" — it might be used in a path you haven't traced
- Rename variables for "clarity"
- Add type hints, docstrings, or comments to code you didn't write
- Extract "helper functions" from working inline code
- "Simplify" conditional logic
- Add error handling for scenarios that haven't caused problems

**The only valid reasons to touch working code:**
1. User explicitly asked for a specific change
2. A bug is confirmed and you're fixing it
3. A new feature requires adding to existing code (ADD, don't restructure)

---

## RULE 8: PYTHON VARIABLE SCOPING IN ASYNC

`nonlocal` in parallel async tasks = shared state bugs. When using `asyncio.gather()` to run tasks in parallel, each task **MUST** use LOCAL copies of variables:

```python
# WRONG:
is_dca = True  # shared across all parallel tasks
async def do_trade(): nonlocal is_dca  # BUG: race condition

# RIGHT:
is_dca_local = is_dca  # local copy per task
```

---

## RULE 9: DCA USES CANCEL + REPLACE, NEVER MODIFY

Tradovate's `modifyOrder` is unreliable for bracket-managed orders. DCA TP updates use:
1. Cancel ALL working TPs on the account (broker query)
2. Place a fresh TP at the new price

**Never** try to modify an existing TP order in place. The cancel+replace at line ~2040 is the safety net.

---

## RULE 10: BRACKET ORDERS FOR FIRST ENTRY ONLY (WHEN DCA IS ON)

| Scenario | Method | Why |
|----------|--------|-----|
| First entry (no position) | Bracket order (entry + TP in one call) | Faster, atomic |
| DCA entry (existing position, DCA ON) | REST market order + separate TP | Can't update existing position's TP via bracket |
| Same-direction signal (DCA OFF) | Bracket order (fresh entry) | DCA off = ignore position state |

**Never** use bracket orders for DCA entries. But when DCA is OFF, every same-direction signal is treated as a fresh entry with its own bracket order.

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

## RULE 11: RECOVERY PROTOCOL

If anything breaks, restore to the known-good state:

```bash
# Full reset to production stable
git reset --hard WORKING_FEB7_2026_PRODUCTION_STABLE

# Restore single file
git checkout WORKING_FEB7_2026_PRODUCTION_STABLE -- recorder_service.py

# Deploy
git push -f origin main   # CAUTION: force push — only if resetting

# Create backup before risky changes
git stash push -m "backup before changes"
```

**Git Tags (Recovery Points):**

| Tag | Commit | Description |
|-----|--------|-------------|
| `WORKING_FEB18_2026_DCA_SKIP_STABLE` | `c75d7d4` | **CURRENT** — DCA-off bracket fix + multiplier trim scaling |
| `WORKING_FEB18_2026_FULL_AUDIT_STABLE` | `fbd705d` | Pre-DCA-fix fallback (audit cleanup) |
| `WORKING_FEB18_2026_TIME_FILTER_STABLE` | `9470ca5` | Time filter status on Control Center |
| `WORKING_FEB17_2026_MULTI_BRACKET_STABLE` | `8f61062` | Native multi-bracket orders |
| `WORKING_FEB7_2026_PRODUCTION_STABLE` | `b475574` | **THE BLUEPRINT** — production stable, demo+live flawless |

---

## ARCHITECTURE — HOW IT WORKS

### Signal-to-Trade Flow
```
TradingView Alert → POST /webhook/{token}
  ↓
10 Fast Webhook Workers (parallel, <50ms response to TradingView)
  ↓
process_webhook_directly() — dedup, parse, find recorder, calc TP/SL
  ↓
broker_execution_queue
  ↓
10 HIVE MIND Broker Workers (parallel)
  ↓
execute_trade_simple() — find ALL traders for recorder → filter
  ↓
asyncio.gather() → do_trade_for_account() per account SIMULTANEOUSLY
  ↓
Pre-warmed WebSocket → Tradovate API → Order filled → TP/SL placed
```

### Core Files

| File | Lines | Purpose | LOCK LEVEL |
|------|-------|---------|------------|
| `ultra_simple_server.py` | ~28K | Flask server, webhook, UI, risk calc | CRITICAL |
| `recorder_service.py` | ~7.7K | Trading engine, execution, TP/SL, DCA | CRITICAL |
| `tradovate_integration.py` | ~2.3K | Tradovate API, WebSocket, orders | CRITICAL |
| `templates/traders.html` | - | Trader create/edit page | MODERATE |
| `templates/recorders.html` | - | Recorder create/edit page | MODERATE |

### Critical Code Locations (recorder_service.py)

| Line | What | Rule |
|------|------|------|
| ~870 | Find traders for recorder | SQL query, enabled filter |
| ~934-1068 | Trader-level filters | add_delay, cooldown, max_signals, max_loss, time |
| ~1072-1186 | enabled_accounts mode | Per-account dict — ALL settings (Rule 5) |
| ~1187-1222 | Legacy single-account mode | Fetches creds from accounts table |
| ~1655-1663 | DCA detection | Same direction + dca_enabled → is_dca_local (Rule 12) |
| ~1697-1761 | Bracket order (first entry) | Entry + TP in one WebSocket call (Rule 10) |
| ~1842-1900 | Position fetch after entry | DCA: get weighted avg from broker |
| ~1951-1969 | TP price calculation | **MUST round to tick_size** (Rule 2) |
| ~1983-2013 | TP lookup for DCA | **Skip DB, use broker query** (Rule 4) |
| ~2040-2053 | Cancel ALL existing TPs | Per-account broker query (Rule 9) |
| ~2076-2098 | TP placement with retry | 10 attempts, exponential backoff |
| ~2118-2140 | SL price calculation | **MUST round to tick_size** (Rule 2) |
| ~2172-2212 | Multi-bracket TP leg builder | Trim qty calculation — **MUST use multiplier** (Rule 13) |
| ~2188-2201 | TP order ID storage | Best-effort, shared across accounts |

### Database

- **Local**: `just_trades.db` (SQLite)
- **Production**: PostgreSQL on Railway
- **All SQL MUST work on BOTH** (Rule 3)
- `recorded_trades` has NO `subaccount_id` column (Rule 4)

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

## WHAT'S WORKING (28 Settings Verified)

**Execution**: Enable/disable, initial/add position size, multiplier, max contracts
**TP**: Targets (ticks + trim %), units (Ticks/Points/Percent), trim_units (Contracts/Percent)
**SL**: Enable/amount, units, type (Fixed/Trailing), trail trigger/freq
**Risk**: Break-even (toggle/ticks/offset), DCA (amount/point/units)
**Filters**: Signal cooldown, max signals/session, max daily loss, add delay, time filters 1&2
**Other**: Custom ticker, inverse strat, auto flat after cutoff

## WHAT'S NOT WORKING (Marked "Coming Soon" in UI)
Ticker filter, Timeframe filter, Option Premium filter, Direction filter,
Nickname, Strategy Description, Discord Channel, Private toggle, Manual Strategy toggle

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

# String defaults in ALTER TABLE
if is_postgres:
    cursor.execute("ALTER TABLE t ADD COLUMN x TEXT DEFAULT 'value'")
else:
    cursor.execute('ALTER TABLE t ADD COLUMN x TEXT DEFAULT "value"')
```

---

## DEPLOYMENT

- **Production**: Railway — auto-deploys from `main` branch pushes
- **Manual deploy**: `railway up` (uploads code directly, bypasses git)
- **Local dev**: `python3 ultra_simple_server.py` → `http://localhost:5000`

---

## MONITORING ENDPOINTS

```bash
# System status (workers, queues, connections)
curl -s "https://justtrades-production.up.railway.app/api/broker-execution/status"

# Recent failures
curl -s "https://justtrades-production.up.railway.app/api/broker-execution/failures?limit=20"

# Webhook activity
curl -s "https://justtrades-production.up.railway.app/api/webhook-activity?limit=10"

# Raw webhooks received
curl -s "https://justtrades-production.up.railway.app/api/raw-webhooks?limit=10"

# Max loss monitor
curl -s "https://justtrades-production.up.railway.app/api/admin/max-loss-monitor/status"

# Recorder settings
curl -s "https://justtrades-production.up.railway.app/api/recorders/18"

# Run database migrations
curl -s "https://justtrades-production.up.railway.app/api/run-migrations"
```

---

## PAST DISASTERS — WHY THE RULES EXIST

| Date | What Happened | What We Learned | Rule |
|------|---------------|-----------------|------|
| Dec 4, 2025 | AI bulk-modified 3 files, deleted a template | ONE change at a time | Rule 6 |
| Jan 12, 2026 | 15+ "improvements" → cascading failures | Don't improve working code | Rule 7 |
| Jan 27, 2026 | 40% trade failures from missing credentials | Both auth paths need creds | Rule 5 |
| Jan 28, 2026 | `failed_accounts` undefined — 30+ failures | Don't restructure try blocks | Rule 7 |
| Feb 6, 2026 | TP orders piling up (3-5 per position) | Store tp_order_id, fix SQL | Rules 3, 4 |
| Feb 6, 2026 | Wrong position sizes (NULL masking) | Explicit values, not NULL | Rule 5 |
| Feb 7, 2026 | Cross-account TP contamination | Use broker query, not DB | Rule 4 |
| Feb 7, 2026 | TP rejected on DCA (fractional price) | Always round to tick_size | Rule 2 |
| Feb 18, 2026 | DCA-off got 1-contract REST instead of 3-contract bracket | DCA off = ignore position state | Rule 12 |
| Feb 18, 2026 | 5x multiplier produced TP legs 1,1,13 instead of 5,5,5 | Multiplier must scale all quantities | Rule 13 |
| Feb 18, 2026 | JADMNQ got 1-contract order instead of 3 — signal tracking piled up 12 stale open records | Signal tracking must respect DCA flag, close old records when DCA off | Rule 14 |

---

## DETAILED DOCUMENTATION

- **`CHANGELOG_RULES.md`** — **MANDATORY** protected code registry. Check BEFORE any edit (Rule 0)
- `memory/WHY_IT_WORKS.md` — Logic document: what broke, why it's fixed, how to preserve it
- `memory/feb7_production_stable_blueprint.md` — Full blueprint with every code location and commit
- `memory/feb6_dca_tp_fix_details.md` — DCA/TP fix history

---

*Last updated: Feb 18, 2026*
*Production stable tag: WORKING_FEB18_2026_DCA_SKIP_STABLE @ c75d7d4*
