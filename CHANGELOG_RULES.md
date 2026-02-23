# PROTECTED CODE CHANGES — MANDATORY CHECK BEFORE EDITING

> **STOP. Before modifying ANY line in `recorder_service.py` or `ultra_simple_server.py`,
> search this file for the line number or feature area you're about to touch.
> If it's listed here, DO NOT change it unless the user explicitly approves.**

This file is the authoritative registry of every deliberate fix in production.
Each entry exists because reverting it caused (or would cause) real failures
for paying customers. These are NOT optional improvements — they are load-bearing fixes.

---

## How To Use This File

1. Before editing a line, `Ctrl+F` the line number or keyword
2. If the line is listed here → **DO NOT MODIFY** without explicit user approval
3. If you're restructuring a function that contains a protected line → **STOP and ASK**
4. If you're "cleaning up" or "improving" code near a protected line → **DON'T**
5. After deploying a new fix, **ADD IT HERE** with date, lines, and explanation

---

## recorder_service.py — Protected Changes

### DCA-Off Resets has_existing_position (Feb 18, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~2046-2049 |
| **Rule** | CLAUDE.md Rule 12 |
| **Commit** | `c75d7d4` |
| **What** | When `dca_enabled=False` and signal is same-direction, sets `has_existing_position = False` |
| **Why** | Without this, stale DB positions block the bracket order gate → REST market order instead of bracket |
| **Verified** | JADMGC: 3-contract bracket orders confirmed working |
| **NEVER** | Remove the `has_existing_position = False` line or add conditions that bypass it |

### Multiplier Scales Trim Contracts (Feb 18, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~2191 |
| **Rule** | CLAUDE.md Rule 13 |
| **Commit** | `201d498` |
| **What** | `leg_trim * account_multiplier` in the `trim_units == 'Contracts'` branch |
| **Why** | Without this, 5x multiplier with trim=1 gives legs of 1,1,13 instead of 5,5,5 |
| **Verified** | JADMNQ with 5x multiplier: correct trim quantities confirmed |
| **NEVER** | Use raw `leg_trim` without multiplier scaling in Contracts mode |

### Bracket Order Gate (Jan 27, 2026+)
| Field | Value |
|-------|-------|
| **Lines** | ~2123-2126 |
| **Rule** | CLAUDE.md Rule 10 |
| **What** | `use_bracket_order = (not has_existing_position and tp_ticks > 0)` |
| **Why** | First entry = bracket order (atomic). DCA = REST market + separate TP |
| **NEVER** | Remove the `not has_existing_position` check or force bracket for DCA |

### Multi-Bracket Uses REST Only (Feb 17, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~2218-2221 |
| **Rule** | MEMORY.md Bug #15 |
| **Commit** | `8f61062` |
| **What** | `place_bracket_order()` uses REST (`session.post`), NOT WebSocket |
| **Why** | WebSocket order placement was NEVER functional. REST is the only working path |
| **NEVER** | Add WebSocket-based order functions or switch bracket orders to WebSocket |

### Price Tick Rounding — TP (Multiple Locations)
| Field | Value |
|-------|-------|
| **Lines** | ~1622, ~2473, ~5900 |
| **Rule** | CLAUDE.md Rule 2 |
| **What** | `round(round(price / tick_size) * tick_size, 10)` |
| **Why** | DCA weighted averages are fractional. Tradovate REJECTS orders at invalid increments |
| **NEVER** | Remove rounding, use raw calculated prices, or "simplify" the double-round |

### Price Tick Rounding — SL
| Field | Value |
|-------|-------|
| **Lines** | ~1650, ~2642 |
| **Rule** | CLAUDE.md Rule 2 |
| **What** | Same `round(round(...))` pattern for stop-loss prices |
| **NEVER** | Same as TP — never remove rounding |

### DCA Cancel+Replace TP (Feb 7, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~2520-2526 (cancel old), ~2553-2568 (cancel ALL before new) |
| **Rule** | CLAUDE.md Rule 9 |
| **What** | Cancel ALL working TPs on broker, then place fresh TP |
| **Why** | `modifyOrder` is unreliable for bracket-managed orders. Cancel+replace is the safety net |
| **NEVER** | Switch to `modifyOrder`, skip the cancel step, or remove the broker query |

### Broker Query for TP Lookup (Feb 7, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~2559 (`get_orders` call) |
| **Rule** | CLAUDE.md Rule 4 |
| **What** | Queries broker directly for existing TPs instead of using DB `tp_order_id` |
| **Why** | `recorded_trades.tp_order_id` is shared across ALL accounts — last write wins |
| **NEVER** | Replace broker query with DB lookup for multi-account recorders |

### Flip Close Resting Order Cleanup (Feb 13, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~2076-2115 |
| **Commit** | `d531455` |
| **What** | On opposite-direction close, cancels ALL resting orders (TP, SL, trailing) + OCO + break-even |
| **Why** | Without this, old TP/SL orders survive the close and interfere with the next entry |
| **Verified** | Confirmed working on JADMGC |
| **NEVER** | Remove the cancel loop or skip OCO/break-even cleanup |

### env_label in enabled_accounts Logger (Feb 20, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~1338 |
| **Rule** | CLAUDE.md Rule 25 |
| **Commit** | `656683a` |
| **What** | Logger uses `{env_label}` (always defined at line 1283), NOT `{env}` (only defined in else-branch at line 1279) |
| **Why** | `env` was unbound when any of the first 4 branches matched. Crash caught by except → entire enabled_accounts parsing aborted → trader got 0 accounts → 0 trades silently |
| **NEVER** | Change `{env_label}` back to `{env}` or add any variable usage after the if-elif chain at lines 1265-1281 without verifying it's defined in ALL branches |

### Multiplier Applied to Quantity
| Field | Value |
|-------|-------|
| **Lines** | ~1757-1758 |
| **What** | `account_multiplier = float(trader.get('multiplier', 1.0))` then `adjusted_quantity = max(1, int(quantity * account_multiplier))` |
| **Why** | Per-account multiplier scales position size. Used everywhere downstream |
| **NEVER** | Use raw `quantity` instead of `adjusted_quantity` after this point |

### Broker-Verified Quantity Safety Net (Feb 20, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~2194-2206 |
| **Rule** | CLAUDE.md Rule 27 (pending) |
| **What** | When broker confirms NO position (`has_existing_position=False`) and signal is an entry (not CLOSE), overrides `adjusted_quantity` to `initial_position_size * account_multiplier` if it differs from current value |
| **Why** | DB/broker drift: stale `recorded_trades` records make Layer 1 (webhook handler) think DCA is active → passes `add_position_size` instead of `initial_position_size`. This safety net uses the already-fetched broker position check to correct the quantity. Zero new API calls. |
| **Verified** | Syntax verified. Awaiting live signal test. |
| **NEVER** | Remove this safety net or bypass it. If broker says flat, quantity MUST be initial_position_size. Do NOT add new API calls here — uses existing `get_positions()` result from line 2181 |

### SQL Placeholders in Reconciliation (Feb 23, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~5920 (ph definition), ~5997, ~6066, ~6101, ~6127, ~6155, ~6200 |
| **Rule** | CLAUDE.md Rule 4 |
| **Commit** | Phase 1 |
| **What** | Added `ph = '%s' if is_postgres else '?'` and replaced all hardcoded `?` in `reconcile_positions_with_broker()` |
| **Why** | Hardcoded `?` silently fails on PostgreSQL inside try/except — reconciliation queries returned nothing for every account |
| **NEVER** | Revert to hardcoded `?` or skip the `ph` variable. Every SQL query in this function MUST use `{ph}` |

### Symbol Matching in TP Detection (Feb 23, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~6172-6194 |
| **Rule** | CLAUDE.md Rule 15 |
| **Commit** | Phase 1 |
| **What** | Replaced hardcoded `'MNQ' in order_symbol` with `extract_symbol_root()` matching (3-char then 2-char). Tracks ALL TPs in `existing_tp_orders` list. Added `'Accepted'` to status check |
| **Why** | TP detection failed for EVERY non-MNQ symbol (GC, NQ, ES, etc.). Only MNQ accidentally matched because the hardcoded string was 'MNQ' |
| **NEVER** | Hardcode symbol names in matching logic. Always use `extract_symbol_root()` with Rule 15 fallback |

### Cancel-Before-Place + Duplicate TP Cleanup (Feb 23, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~6197-6268 |
| **Rule** | CLAUDE.md Rule 8 (cancel+replace) |
| **Commit** | Phase 1 |
| **What** | (A) When `existing_tp_orders > 1`, cancels all but first (duplicate cleanup). (B) Before placing new TP, cancels ALL working limit orders matching TP direction + symbol. (C) Fixed `tick_size = 0.25` to use `TICK_SIZES.get()` with symbol root lookup |
| **Why** | Each 60s reconciliation cycle added a new TP without removing old ones. After 5 minutes, 5+ TPs existed at same price. When price hit TP level, ALL filled simultaneously → burst of fills → wrong position state |
| **NEVER** | Place a TP without first cancelling existing TPs. Never use hardcoded `tick_size = 0.25` |

### Reconciliation Sleep Downgraded to 300s (Feb 23, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~6586, ~6589 |
| **Rule** | Sacred function: `start_position_reconciliation()` — approved edit |
| **Commit** | Phase 2 |
| **What** | `time.sleep(60)` → `time.sleep(300)` in both try and except branches |
| **Why** | WS Position Monitor is now the primary sync mechanism (real-time). Reconciliation is the safety net — 5-min interval reduces API calls by 5x while WS monitor handles real-time sync |
| **NEVER** | Change back to 60s without confirming WS monitor is down. The aggressive polling was the ROOT CAUSE of TP stacking |

### WS-Connected Skip in Reconciliation (Feb 23, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~6213-6222 (inside reconcile_positions_with_broker) |
| **Commit** | Phase 2 |
| **What** | Before auto-TP placement, checks `is_position_ws_connected(recorder_id)`. If connected, skips TP placement and logs "WS connected — skipping auto-TP" |
| **Why** | When WS monitor handles real-time sync, reconciliation TP placement is redundant and was the source of TP stacking. Only falls back to REST TP placement when WS is disconnected |
| **NEVER** | Remove this check. The WS monitor is the primary TP tracking mechanism. Reconciliation only places TPs when WS is down |

---

## ultra_simple_server.py — Protected Changes

### DCA-Off Keeps initial_position_size (Feb 18, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~16675-16701 |
| **Rule** | CLAUDE.md Rule 12 |
| **Commit** | `c75d7d4` |
| **What** | Checks `trader.dca_enabled` / `recorder.avg_down_enabled` before setting `is_dca=True` |
| **Why** | Without this, any stale position triggers DCA path → wrong quantity (add_position_size instead of initial) |
| **Verified** | JADMGC: 3 contracts (initial) instead of 1 (add) |
| **NEVER** | Remove the `effective_dca` check or unconditionally set `is_dca=True` |

### Paper Trades as Daemon Thread (Critical)
| Field | Value |
|-------|-------|
| **Lines** | ~16255-16268 |
| **Rule** | MEMORY.md Bug #9 |
| **What** | Paper trades fire in `threading.Thread(..., daemon=True)` — non-blocking |
| **Why** | Feb 12 disaster: changing to synchronous caused 10x latency (1000-1500ms) |
| **NEVER** | Make paper trades synchronous, await them, or put them in the broker pipeline |

### Signal Tracking as Daemon Thread
| Field | Value |
|-------|-------|
| **Lines** | ~14696-14725 |
| **What** | Signal processor runs as background daemon thread with batch processing |
| **Why** | Same as paper trades — synchronous signal tracking blocks the pipeline |
| **NEVER** | Make signal tracking synchronous or inline it into the webhook handler |

### Broker Worker error=None Fix (Feb 13, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~14934 |
| **Commit** | `d6f5f4a` |
| **What** | `result.get('error') or 'Unknown error'` (NOT `result.get('error', 'Unknown error')`) |
| **Why** | `execute_trade_simple` sets `error: None` explicitly. `.get()` default only applies when key is MISSING |
| **NEVER** | Change back to `result.get('error', 'Unknown error')` — it crashes on `'string' in None` |

### Break-Even Monitor Only for Trailing+BE Combo (Feb 18, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~2259-2293 |
| **Commit** | `410fd40` |
| **What** | Safety-net monitor only registers when `trailing_stop_bool=True` AND `break_even_ticks > 0` |
| **Why** | When native bracket BE is active (no trailing stop), monitor is unnecessary. Saves an API call (get_positions) per entry |
| **NEVER** | Remove the `trailing_stop_bool` guard — would re-add unnecessary API calls and potential double-execution |

### Signal Tracking Respects DCA Flag (Feb 18, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~16933 (function def), ~16983-17019 (same-side branch), ~17086 (Thread args) |
| **Rule** | CLAUDE.md Rule 14 |
| **Commit** | `ee54f60` |
| **What** | `_bg_signal_tracking` receives `t_is_dca` param. When DCA off + same direction: close old record, open fresh one. When DCA on: stack (existing behavior) |
| **Why** | Without this, every same-direction signal inserted a NEW `status='open'` record without closing the old one. Stale records piled up (12+ for JADMNQ), polluting the position detection at line ~16633 which reads `recorded_trades` to determine existing position. Stale records caused downstream quantity/bracket issues |
| **Verified** | Cleaned 47 stale recorded_trades + 4 recorder_positions for JADNQ/JADMNQ/JADGC/JADMGC |
| **NEVER** | Remove the `t_is_dca` check or unconditionally insert DCA adds. The signal tracking MUST close old same-side records when DCA is off |

### DCA Field Name Bridging — avg_down_enabled → dca_enabled (Feb 19, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~13531-13532 (create), ~13784-13788 (update) |
| **Rule** | CLAUDE.md Rule 24 |
| **Commit** | `d3e714d` |
| **What** | Create: `dca_enabled = bool(avg_down_enabled) if avg_down_enabled is not None else bool(rec_avg_down_enabled)`. Update: accepts either `dca_enabled` or `avg_down_enabled` field name |
| **Why** | Frontend sends `avg_down_enabled`, backend column is `dca_enabled`. Without bridging, DCA is ALWAYS False regardless of UI toggle |
| **Verified** | JADVIX DCA confirmed LIVE — consolidating TPs + correct size |
| **NEVER** | Remove the `avg_down_enabled` fallback, hardcode `dca_enabled = False`, or assume the frontend field name matches the DB column |

### JADVIX DCA Auto-Enable on Startup (Feb 19, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~8956-8980 |
| **Rule** | CLAUDE.md Rule 24 |
| **Commit** | `bda90af` |
| **What** | `UPDATE traders SET dca_enabled = TRUE WHERE recorder_id IN (SELECT id FROM recorders WHERE UPPER(name) LIKE '%JADVIX%')` |
| **Why** | Business requirement: ALL JADVIX traders MUST have DCA on for ALL users. Startup auto-fix ensures this on every deploy |
| **NEVER** | Remove this startup fix. All JADVIX strategies require DCA enabled. This is not optional. |

### Pro Copy Trader Route Gating (Feb 22, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~12429 (`@feature_required('recorders')` on /recorders), ~12522 (/recorders/new), ~12553 (/recorders/<id>), ~19178 (`@feature_required('auto_trader')` on /traders), ~19815 (`@feature_required('control_center')` on /control-center) |
| **Commit** | `7954eb2` |
| **What** | `@feature_required` decorators gate recorder, trader, and control center routes for pro_copy_trader tier |
| **Why** | Pro Copy Trader ($100/mo) only gets copy trading features. Without decorators, they can access recorders/traders/control center via direct URL |
| **NEVER** | Remove these decorators. They enforce the tier pricing model |

### User Delete Cascade (Feb 19, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~6203-6230 (admin_delete_user) |
| **Rule** | CLAUDE.md Rule 26 |
| **Commit** | `a40fc07` |
| **What** | Cascade deletes all child records (support_messages, recorded_trades, recorded_signals, recorder_positions, traders, support_tickets, recorders, strategies, push_subscriptions, accounts) then nullifies audit columns before deleting user |
| **Why** | PostgreSQL enforces FK constraints. Direct `DELETE FROM users` fails with `accounts_user_id_fkey` violation |
| **NEVER** | Remove any child table from the cascade. If adding a new table with user_id FK, ADD it to this cascade list |

### Multiplier Persisted on Trader Create (Feb 22, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~13784-13786 |
| **Rule** | CLAUDE.md Rule 13 |
| **What** | `create_multiplier = float(data.get('multiplier', 1.0))` used in `initial_enabled_accounts` JSON instead of hardcoded `1.0` |
| **Why** | Frontend sends multiplier on create, but server ignored it and hardcoded 1.0. Users who set 5x multiplier at creation time got 1x execution. Only fixed on subsequent edits (PUT path was already correct). |
| **Verified** | Syntax passes. Frontend (`traders.html` line 2384) now sends `multiplier: account.multiplier` in POST body |
| **NEVER** | Hardcode `'multiplier': 1.0` in `initial_enabled_accounts`. Always read from request data |

### CSRF Exempt Prefixes (Feb 16, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~3262-3267 |
| **Commit** | `ce19d18` |
| **What** | Must include `/webhook/` AND `/webhooks/` (plural) |
| **Why** | Whop webhook route is `/webhooks/whop` — without `/webhooks/` prefix, all Whop POSTs get 403'd |
| **NEVER** | Remove `/webhooks/` from the exempt list or consolidate to just `/webhook/` |

### Position WebSocket Monitor Startup (Feb 23, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~34003-34009 |
| **Commit** | `fb4c67e` |
| **What** | `from ws_position_monitor import start_position_monitor; start_position_monitor()` in try/except block, right after leader monitor startup |
| **Why** | Position monitor MUST be started from ultra_simple_server.py (main process), NOT recorder_service.py. recorder_service.py's initialize() only runs under `if __name__=='__main__'` which never fires — it's always imported as a module |
| **NEVER** | Move this startup to recorder_service.py. It will silently not execute. Must stay in ultra_simple_server.py alongside ws_leader_monitor startup |

---

## tradovate_integration.py — Protected Changes

### Symbol Root Extraction for Tick Size Lookup (Feb 18, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~1874-1882 |
| **What** | Matches symbol alpha chars against tick_sizes dict: try 3-char first, then 2-char. Replaces blind `[:3]` slice |
| **Why** | 2-letter symbols like GC: `GCJ6` → `GCJ` → missed dict → default 0.25 instead of 0.10 → all bracket TPs/SLs 2.5x too far |
| **Verified** | All 12 symbol variants (GC, MGC, NQ, MNQ, ES, MES, CL, MCL, SI, ZB, YM, MYM) resolve correctly |
| **NEVER** | Revert to `[:3]` slice. NEVER change the default fallback without checking ALL 2-letter symbols |

### Native Break-Even in Bracket Orders (Feb 18, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~1978-1985 (single-bracket), ~1941-1947 (multi-bracket) |
| **Commit** | `410fd40` |
| **What** | Adds `breakeven` and `breakevenPlus` params to bracket order — ALWAYS positive, NEVER with `trailingStop: true` |
| **Why** | Native BE is faster than safety-net monitor (no extra API calls, no polling). Forum-confirmed: values must be positive on both sides |
| **Guard** | `not trailing_stop` check prevents combining with trailingStop (Tradovate rejects this combination) |
| **NEVER** | Use negative/signed values for breakeven/breakevenPlus. NEVER send breakeven when trailingStop is true |

---

## projectx_integration.py — Protected Changes

### Trailing Stop Bracket Ticks Must Be Signed (Feb 18, 2026)
| Field | Value |
|-------|-------|
| **Lines** | ~1116-1118 |
| **What** | Trailing stop bracket uses `sl_sign * abs(int(sl_ticks))` — signed, not unsigned |
| **Why** | ProjectX API requires negative ticks when longing, positive when shorting — same as fixed stops |
| **Error if reverted** | `"Rejected (Invalid stop loss ticks (50). Ticks should be less than zero when longing.)"` |
| **Matches Tradovate** | Tradovate signs SL delta the same way: `-sl_points` for long, `+sl_points` for short |
| **NEVER** | Use `abs()` for trailing stop ticks — unsigned values are rejected by ProjectX API |

---

## Architectural Invariants — NEVER Change These

| What | Current | Why | Disaster If Changed |
|------|---------|-----|---------------------|
| Paper trades | Daemon thread (fire-and-forget) | Non-blocking | 10x latency (Feb 12) |
| Signal tracking | Daemon thread (batch processor) | Non-blocking | Pipeline blocked |
| Bracket orders | REST API only | WebSocket never worked | Orders fail silently |
| DCA TP updates | Cancel + Replace (never modify) | modifyOrder unreliable | Duplicate/orphaned TPs |
| All prices | Rounded to tick_size | Tradovate rejects invalid | Orders rejected |
| SQL placeholders | `%s` (postgres) / `?` (sqlite) | Production is PostgreSQL | Silent query failure |
| TP lookup (DCA) | Broker query, not DB | DB tp_order_id shared | Cross-account contamination |
| DCA off | Ignore position state | Position irrelevant | Wrong qty + no bracket |
| Trim contracts | Scale by multiplier | Raw trim ignores multiplier | Wrong TP leg sizes |
| SL ticks signing | Signed for both brokers | Negative for long, positive for short | ProjectX rejects unsigned trailing stops |
| Native break-even | ALWAYS positive, NEVER with trailingStop | Tradovate API requirement | Bracket rejected or wrong BE direction |
| BE safety-net monitor | Only when trailing+BE combo | Native handles non-trailing | Extra API calls, potential double-execution |
| Signal tracking DCA | Close old + open fresh when DCA off | Prevents stale record pileup | Stale records pollute position detection → wrong qty |
| Symbol root extraction | Try 3-char then 2-char against dict | 2-letter symbols (GC, CL, SI) include month letter in blind [:3] | Wrong tick_size → TPs/SLs placed at wrong distances |
| DCA field name bridge | `avg_down_enabled` → `dca_enabled` on create/update | Frontend and DB use different names | DCA always False → no TP consolidation |
| JADVIX DCA auto-enable | Startup UPDATE on every deploy | Business requirement for all JADVIX users | DCA off → bracket-only, no consolidation |
| User delete cascade | Delete all child tables before users | PostgreSQL FK constraints | Admin can't delete users |
| enabled_accounts logger | Uses `env_label` not `env` | `env` only defined in else-branch | Silent 0-account failure for traders |
| Broker qty safety net | Override to initial_position_size when broker flat | DB/broker drift gives wrong DCA qty | Users get add_position_size on fresh entry → wrong contract count |
| Pro Copy Trader route gating | `@feature_required` on /recorders, /traders, /control-center | Tier enforcement for $100 plan | Copy-only users access recorder/trader features they didn't pay for |
| Sidebar `is_copy_only` gating | `layout.html` greys out locked nav items | Visual indication of tier limits | Users click locked features, get confused by redirect |
| TOS governing law | `terms.html` Section 15: Illinois + federal law | Goldman-reviewed legal requirement | Wrong jurisdiction for disputes |
| TOS jury trial waiver | `terms.html` Section 16: waiver + arbitration opt-out | Goldman-reviewed legal requirement | Users retain jury trial right |
| TOS limitation of liability | `terms.html` Section 18: 18.1-18.3 detailed caps | Goldman-reviewed — 3-month cap, intentional risk allocation | Unlimited liability exposure |
| Risk Disclosure disclaimers | `risk_disclosure.html` Sections 11-17: platform overview, TradingView, hypothetical, testimonials, automation | Goldman-reviewed legal requirement | Missing legally required disclosures |
| Contact email | `legal@justtrades.app` in both terms.html and risk_disclosure.html | Canonical legal contact | Users email non-existent address |
| Multiplier on create | Read from request, not hardcoded 1.0 | Frontend sends multiplier per account | Users get 1x execution despite setting 5x at creation |
| WS Position Monitor startup | ultra_simple_server.py, NOT recorder_service.py | recorder_service.py is imported, never __main__ | Monitor silently never starts |
| Position WS Monitor | One WebSocket per token, LOWER() on broker match | Rule 16, broker column is 'Tradovate' (capital T) | Either rate limit hit or no connections found |
| subaccount_id for traders | Use `t.subaccount_id` from traders table | Column exists on traders AND accounts with different meanings | SQL error, no accounts loaded |
