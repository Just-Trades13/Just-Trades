# COPY TRADER ARCHITECTURE — Reference for Claude Code CLI

> **For**: Claude Code CLI agent working on `just-trades-platform`
> **Author**: Myles Jadwin (CEO, Just Trades Group) + Claude research
> **Date**: February 2026
> **Last Updated**: February 24, 2026
> **Priority**: CRITICAL — this is the #1 product feature
> **Status**: WORKING — Manual + Auto-copy confirmed working. Parallel execution + smart position sync (add/trim/reversal). WS connection stability confirmed with semaphore fix (20 connections, ZERO 429s). Feb 24, 2026

---

## 0. CURRENT STATE — WHAT'S WORKING (Feb 23, 2026)

### Manual Copy Trader — CONFIRMED WORKING
- User clicks BUY/SELL/CLOSE on Manual Copy Trader page
- Trade executes on leader account
- `_propagate_manual_trade_to_followers()` fires in a daemon thread
- All followers execute in PARALLEL via `ThreadPoolExecutor`
- Typical latency: ~300ms per follower (Tradovate API round-trip dominates)
- Loop prevention: `JT_COPY_` prefix on `cl_ord_id`

### Auto-Copy (WebSocket Leader Monitor) — CONFIRMED WORKING
- `ws_leader_monitor.py` connects to Tradovate WebSocket for each leader with `auto_copy_enabled=True`
- Detects fill events via `syncrequest` → `"e":"props"` → `entityType: "fill"`
- Copies to followers via HTTP POST to `/api/manual-trade` with admin key
- **All followers fire in PARALLEL via `asyncio.gather()`** — not sequential (commit `b26dc75`)
- **Position adds use delta qty** — leader Long 1→Long 2 = follower buys 1 more, NOT close+re-enter (commit `b97eb10`)
- Reload signal: toggling auto-mode triggers reconnect within 5 seconds

### Pipeline Separation — Webhook vs Copy Trader (Feb 23, 2026)
- Both propagation paths skip followers that have their own active webhook traders
- `get_subaccounts_with_active_traders()` in `copy_trader_models.py` — one DB query per propagation event
- Prevents double-fills when a follower account receives trades from BOTH pipelines
- Commit: `e46c4a4`

### Current Architecture: HTTP Self-POST with Admin Key
```
CURRENT (working):
  propagation thread → HTTP POST to own /api/manual-trade
    → X-Admin-Key header bypasses auth gate → trade executes → ✅

FUTURE OPTIMIZATION (not yet implemented):
  propagation thread → call broker execution function directly
    → skip HTTP overhead → ~50-80ms faster per follower
```

The HTTP self-POST pattern works because we added `X-Admin-Key` header bypass in
`_global_api_auth_gate()` (line ~3700). The admin key is read from `ADMIN_API_KEY` env var.

### Fixes Applied This Session (Feb 22-23, 2026)

| Fix | Commit | What Was Wrong |
|-----|--------|---------------|
| Auth gate bypass | `03c5853` | Internal POST had no Flask session → 401 on every follower trade |
| Truthy dict bug | `b7529f9` | `if refreshed:` always True for non-empty dicts → overwrote valid tokens with expired ones |
| Token expiry correction | `b7529f9` | `timedelta(hours=24)` → `timedelta(minutes=85)` (Tradovate tokens expire in 90 min) |
| Parallel propagation | `22f32be` | Sequential for-loop → `ThreadPoolExecutor` — all followers fire simultaneously |
| Architecture doc + Gate 1 | `a66c0c9` | Added this doc to CLAUDE.md Gate 1 reference table |
| Leader lookup fallback | `2c7a9ba` | Server-side leader lookup when frontend doesn't send leader_id |
| Page init leader load | `a38b9b5` | `currentLeaderId` was null on page load → propagation skipped |
| Leader ID from frontend | `dd1cbea` | Frontend sends leader_id directly instead of fragile reverse-lookup |
| Diagnostic logging | `5510b9f` | Added logging to trace propagation flow |
| WS market-hours fix | `2c53a6d` | Dead-subscription reconnect skipped when futures market closed → no more 429 spam |
| WS 429 storm fix (dead-sub threshold + stagger + backoff) | `79e3f7b` | 10×30s dead-sub, 30s stagger, 30s dead-sub backoff — NEVER reduce these |
| Dead WS pool disabled (60s trade timeout fix) | `6efcbd5` | `get_pooled_connection()` returns None → REST-only path, no more lock contention |
| Toggle startup reset removal | `ef813fe` | `copy_trader_models.py` force-reset toggle OFF on every startup |
| Toggle optimistic UI | `d04ddbd` | Toggle text updates immediately instead of waiting for API response |
| Toggle race condition fix | `39b8122` | `masterToggleUserChanged` flag prevents stale GET from overwriting user click |
| Toggle missing import fix | `ce4e6a2` | `get_user_by_id` not imported in toggle handler → 500 error |
| FLASK_SECRET_KEY permanent | N/A (env var) | Sessions survive deploys — toggle POST no longer gets 401 |
| Auto-copy parallel (asyncio.gather) | `b26dc75` | Sequential for-loop → `asyncio.gather()` — all followers simultaneously |
| Position add-not-close | `b97eb10` | Same-side adds use delta qty instead of close+re-enter |
| Warning disclaimer | `24e1094` | Yellow warning box: don't mix copy trader with webhook strategies |
| **WS Connection Semaphore** | **`84d5091`** | **asyncio.Semaphore(2) + 3s sleep gates concurrent WS connects. THE definitive 429 fix. 20 connections, ZERO 429s. NEVER REMOVE.** |
| WS Legacy thresholds hardened | `84d5091` | All 4 dead-sub threshold locations updated to >= 10. DEPRECATED headers on legacy standalone classes. |
| Token refresh daemon PostgreSQL fix | `d457d44` | Was using sqlite3 in PostgreSQL production — tokens never refreshed |
| Unknown error diagnostic fix | `27c38c5` | run_async() exceptions now propagate real error messages instead of "Unknown error" |
| max_contracts DEFAULT 10→0 | `adb859b` | Migration silently capped ALL traders at 10 contracts. Fixed 172 traders. |

### Debugging Lessons Learned

**1. Auth Gate Blocks Internal Requests**
- `_global_api_auth_gate()` at line ~3700 blocks ALL `/api/` routes for unauthenticated requests
- Internal `requests.post()` from propagation thread has no Flask session cookies
- Fix: Include `X-Admin-Key` header from `ADMIN_API_KEY` env var
- This applies to BOTH `_propagate_manual_trade_to_followers()` AND `ws_leader_monitor.py`'s `_execute_follower_entry()`/`_execute_follower_close()`

**2. Truthy Dict Bug in Token Refresh**
- `refresh_access_token()` returns `{'success': False, 'error': '...'}` on failure
- `if refreshed:` checks truthiness — non-empty dicts are ALWAYS truthy
- This caused FAILED refreshes to overwrite valid OAuth tokens with expired ones
- AND set a 24-hour expiry (should be 85 min), preventing the refresh daemon from catching it
- Fix: `if refreshed and refreshed.get('success'):`
- **This is Rule 17 (dict.get default) applied to a different pattern — check success explicitly**

**3. Close "Succeeds" But Doesn't Actually Trade**
- `get_positions()` returns empty list `[]` on 401 (instead of raising an error)
- Close handler sees "no positions" → returns `success=True, message="No open position found"`
- This masks token expiry — Close appears to work when Sell fails
- Diagnosis: If Close succeeds but Sell fails with same token → token is expired

**4. Orphaned Follower Accounts**
- Follower account pointed to `accounts.id=591` which didn't exist in the DB
- All trades to that follower returned "Account not found"
- Leader 26 still referenced the deleted account → its followers were orphaned
- Fix: Delete orphaned follower_accounts, reassign to working leaders
- Prevention: Add FK constraint or cleanup job for follower→account references

**5. `railway run` Tests Local Machine, Not Production Container**
- `railway run python3 -c "import X"` runs on LOCAL Mac (Python 3.13)
- Production container runs Python 3.11 with different packages
- NEVER use `railway run` to verify production state
- Use `railway logs` or DB queries instead

---

## 1. TARGET ARCHITECTURE (FUTURE: DIRECT-CALL PATTERN)

### Performance Comparison

| Pattern | Latency Per Follower | Why |
|---------|---------------------|-----|
| HTTP self-POST (current) | ~300ms | HTTP overhead (~50-80ms) + Tradovate API (~200-250ms) |
| Direct function call (future) | ~220ms | Tradovate API only — skip HTTP/JSON/auth gate |

### High-Level Data Flow (Future)
```
┌──────────────────────────────────────────────────────────────┐
│                    JUST TRADES SERVER                          │
│                                                                │
│  TRIGGER SOURCES:                                              │
│  ┌────────────────────┐  ┌─────────────────────────────────┐  │
│  │  Manual Trade UI    │  │  WebSocket Leader Monitor       │  │
│  │  (user clicks BUY)  │  │  (auto-detects leader fills)    │  │
│  └─────────┬──────────┘  └──────────────┬──────────────────┘  │
│            │                             │                      │
│            ▼                             ▼                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              COPY ENGINE (Python function)                │  │
│  │                                                            │  │
│  │  Input: leader_id, symbol, side, quantity                  │  │
│  │                                                            │  │
│  │  1. get_followers_for_leader(leader_id)                    │  │
│  │  2. ThreadPoolExecutor for each enabled follower:          │  │
│  │     a. Calculate qty: leader_qty × multiplier              │  │
│  │     b. Map contract if cross-order (NQ → MNQ)              │  │
│  │     c. Get follower's broker credentials from DB           │  │
│  │     d. DIRECT CALL to broker execution function:           │  │
│  │        - ProjectX: _execute_projectx_trade(...)            │  │
│  │        - Tradovate: TradovateIntegration.place_order(...)  │  │
│  │     e. Log result to copy_trade_log                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│            │                             │                      │
│            ▼                             ▼                      │
│  ┌──────────────────┐          ┌────────────────────┐          │
│  │  ProjectX API     │          │  Tradovate REST API │          │
│  │  (follower accts)  │          │  (follower accts)   │          │
│  └──────────────────┘          └────────────────────┘          │
└──────────────────────────────────────────────────────────────┘
```

### Key Principle: TWO trigger paths, ONE execution engine

| Trigger | Source | How it enters the copy engine |
|---------|--------|-------------------------------|
| Manual Trade | User clicks BUY/SELL in copy trader UI | After leader trade succeeds, call `copy_to_followers()` in daemon thread |
| Auto-Copy | `ws_leader_monitor.py` detects fill via WebSocket | On fill event, call `copy_to_followers()` from the async handler |

Both paths call the **same** `copy_to_followers()` function. The future version calls broker APIs directly instead of HTTP self-POST.

### What Direct-Call Would Require
1. Create `copy_engine.py` with `copy_to_followers()` function
2. Implement `_get_tradovate_token_for_account(account_id)` — DB lookup + refresh if expired
3. Implement `_get_tradovate_base_url(account_id)` — demo vs live
4. For Tradovate: instantiate `TradovateIntegration` directly, call `place_order()` or `liquidate_position()`
5. For ProjectX: call existing `_execute_projectx_trade()` directly
6. Replace `_propagate_manual_trade_to_followers()` to use new engine
7. Replace `ws_leader_monitor.py` follower execution to use new engine
8. Remove HTTP self-POST and admin key header workaround

---

## 2. CURRENT IMPLEMENTATION — CODE LOCATIONS

### Manual Copy Propagation (`ultra_simple_server.py`)

| Line | What | Notes |
|------|------|-------|
| ~24000 | `_propagate_manual_trade_to_followers()` | Main propagation function |
| ~24018-24021 | Admin key header setup | `X-Admin-Key` from `ADMIN_API_KEY` env var |
| ~24023-24068 | `_copy_one_follower()` inner function | Handles one follower trade |
| ~24070-24072 | `ThreadPoolExecutor` parallel dispatch | All followers fire simultaneously |
| ~24077 | `manual_trade()` route | `/api/manual-trade` endpoint |
| ~24086-24087 | `cl_ord_id` and `leader_id` extraction | Loop prevention + propagation trigger |
| ~24107-24121 | Server-side leader lookup fallback | Finds leader if frontend didn't send leader_id |
| ~24382 | ProjectX success → propagation trigger | Daemon thread spawned |
| ~24788 | Tradovate success → propagation trigger | Daemon thread spawned |

### Auto-Copy WebSocket Monitor (`ws_leader_monitor.py`)

| Line | What | Notes |
|------|------|-------|
| ~80 | `_leader_reload_event` | Threading event for reload signal |
| ~466 | `JT_COPY_` loop prevention check | Skips fills from copy trades |
| ~692, ~720 | `platform_url` construction | Uses `127.0.0.1:{PORT}` (not localhost) |
| ~796 | `_run_leader_monitor()` | Main async event loop |
| ~841 | `asyncio.wait` with 5s timeout | Checks reload event periodically |
| follower execution | `_execute_follower_entry()` / `_execute_follower_close()` | HTTP POST with admin key header |

### Auth Gate (`ultra_simple_server.py`)

| Line | What | Notes |
|------|------|-------|
| ~3700-3724 | `_global_api_auth_gate()` | `@app.before_request` — blocks unauthenticated `/api/` |
| ~3710 | `_API_PUBLIC_PREFIXES` check | Whitelisted paths skip auth |
| ~3714-3717 | `X-Admin-Key` check | Internal requests use this to bypass auth |

### Token Refresh (`ultra_simple_server.py`)

| Line | What | Notes |
|------|------|-------|
| ~24201-24229 | `do_refresh_tokens()` | Fixed: checks `refreshed.get('success')`, uses 85-min expiry |

### Copy Trader Models (`copy_trader_models.py`)

| Function | What |
|----------|------|
| `get_followers_for_leader(leader_id)` | Returns list of enabled follower dicts |
| `get_leaders_for_user(user_id)` | Returns all leaders for a user |
| `get_leader_for_account(user_id, account_id, subaccount_id)` | Reverse lookup — find leader by account |
| `log_copy_trade(...)` | Writes to `copy_trade_log` table |
| `get_subaccounts_with_active_traders(subaccount_ids)` | Returns set of subaccount_ids that have active webhook traders — pipeline separation |
| `get_copy_trade_history(leader_id)` | Reads copy log for UI display |

### Frontend (`templates/manual_copy_trader.html`)

| Feature | Notes |
|---------|-------|
| Leader account selector | Dropdown of user's leader accounts |
| `currentLeaderId` | Set on page load from first leader, sent with every trade |
| Copy trade log panel | Shows recent copy trades with status, latency, error messages |
| Auto-mode toggle | Enables/disables WebSocket monitoring per leader |

---

## 3. LOOP PREVENTION

### The Problem
When the copy engine places an order on a follower account, the WebSocket leader monitor might also be watching that account. If it sees the fill and tries to copy it again → infinite loop.

### Solution: clOrdId Prefix
```python
COPY_ORDER_PREFIX = "JT_COPY_"

# PLACING follower orders — always tag:
cl_ord_id = f"JT_COPY_{uuid.uuid4().hex[:12]}"

# RECEIVING events — always check:
def on_fill_event(fill_entity, order):
    if order.get('clOrdId', '').startswith('JT_COPY_'):
        return  # This is a copy trade — do NOT re-copy
```

### Additional Safety
- Time-windowed dedup set (60s) of fill IDs already processed
- DB constraint: account can be leader OR follower for a given leader, never both roles
- Update dedup set BEFORE placing order (WS event may arrive before REST response)
- Manual trades from UI have no `cl_ord_id` → propagation triggers
- Follower trades get `cl_ord_id = "JT_COPY_xxx"` → propagation skipped

---

## 4. TRADOVATE WEBSOCKET PROTOCOL (FOR AUTO-COPY)

### Endpoints

| Environment | REST Auth | WebSocket |
|-------------|-----------|-----------|
| Live | `https://live.tradovateapi.com/v1/auth/accesstokenrequest` | `wss://live.tradovateapi.com/v1/websocket` |
| Demo | `https://demo.tradovateapi.com/v1/auth/accesstokenrequest` | `wss://demo.tradovateapi.com/v1/websocket` |

### Custom Wire Protocol (NOT standard JSON WebSocket!)

| Direction | Format | Example |
|-----------|--------|---------|
| Server→Client | Open frame | `o` |
| Client→Server | Auth | `authorize\n0\n\n{accessToken}` |
| Client→Server | API call | `{endpoint}\n{requestId}\n\n{jsonBody}` |
| Client→Server | Heartbeat | `[]` |
| Server→Client | Response | `a[{jsonArray}]` |

### Connection Lifecycle (EXACT ORDER — CRITICAL)
```
1. Connect to wss://live.tradovateapi.com/v1/websocket
2. WAIT for server 'o' frame (DO NOT auth on onopen!)
3. Send: authorize\n0\n\n{accessToken}
4. WAIT for: a[{"i":0,"s":200}]  (auth success)
5. Send: user/syncrequest\n1\n\n{"splitResponses":true,"entityTypes":["order","fill","position"]}
6. Start heartbeat: send '[]' every 2500ms
7. Listen for a[...] messages with "e":"props"
```

### CRITICAL RULES
- **ONE syncrequest per socket lifecycle** — sending multiple is a conformance violation
- **Wait for 'o' frame** before sending auth
- **Heartbeat every 2.5 seconds** — `[]` (empty JSON array)
- **Server timeout: 10 seconds** — if no message for 10s, connection is dead → reconnect
- **Token expires ~90 minutes** — must refresh and reconnect
- **requestId 0 = auth, 1 = syncrequest** — auto-increment from 2

### Event Structure (what you receive)
```json
a[{
  "e": "props",
  "d": {
    "entityType": "fill",
    "entity": {
      "id": 123456,
      "orderId": 789,
      "contractId": 1234,
      "timestamp": "2025-02-22T15:30:00.000Z",
      "action": "Buy",
      "qty": 1,
      "price": 21500.25
    },
    "eventType": "Created"
  }
}]
```

### Message Parsing
```python
raw = await ws.recv()

if raw == 'o':
    # Server open frame or heartbeat
    if not auth_sent:
        await ws.send(f"authorize\n0\n\n{access_token}")
        auth_sent = True
    return

if raw.startswith('a['):
    data = json.loads(raw[1:])  # STRIP 'a' PREFIX before parsing
    for item in data:
        if item.get('i') == 0 and item.get('s') == 200:
            # Auth success → send syncrequest
            ...
        if item.get('e') == 'props':
            entity_type = item['d']['entityType']
            event_type = item['d']['eventType']
            if entity_type == 'fill' and event_type == 'Created':
                # NEW FILL → trigger copy engine
                fill = item['d']['entity']
                copy_to_followers(leader_id, symbol, fill['action'], fill['qty'])
```

### Reconnection: Exponential Backoff with Jitter
```python
delay = min(1000 * 2**attempt, 60000) + random(0, delay * 0.1)
# Attempt 1: ~1s, 2: ~2s, 3: ~4s, 4: ~8s, ..., 7+: ~60s (capped)
```

### 4PM CT Replay Warning
At daily session end (~4PM CT), Tradovate replays ALL session events through WebSocket. Filter by:
1. Track processed fill IDs in a set
2. Ignore fills with timestamp before connection start time
3. `splitResponses: true` separates initial state dump from live events

### P-Ticket Rate Limiting
```json
// Rate limit response:
{"i": 5, "d": {"p-ticket": "abc123", "p-time": 5}}

// Fix: wait p-time seconds, resend with p-ticket in body
// If p-captcha received → locked out 1 hour
```

---

## 5. TRADESYNCER FEATURE PARITY CHECKLIST

### MVP (Phase 1) — STATUS

- [x] Connect broker accounts (Tradovate + ProjectX via API keys)
- [x] Designate ONE lead account per user
- [x] Auto-copy leader fills to followers via WebSocket monitor — **WORKING Feb 23**
- [x] Manual trade on leader propagates to followers — **WORKING Feb 23**
- [x] Quantity multiplier per follower (ratio copy)
- [x] Enable/disable per follower
- [x] Close propagation (leader closes → all followers close) — **WORKING Feb 23**
- [x] Copy log with status (success/error), latency, error message
- [x] Loop prevention (JT_COPY_ clOrdId prefix)
- [ ] Flatten per account (close positions + cancel orders)
- [ ] Flatten all (global)

### Phase 2 — Important Features
- [ ] Cross-order contract mapping (NQ → MNQ, ES → MES)
- [ ] Follower protection (auto-disable on risk limit breach)
- [ ] Daily PNL tracking per account
- [ ] Open PNL per contract (real-time)
- [ ] Account balance display
- [ ] Daily loss limit per follower → auto-disable
- [ ] Max drawdown per follower → auto-disable
- [ ] Session time locks (don't copy outside hours)

### Phase 3 — Nice to Have
- [ ] Copy groups (multiple independent leader→follower sets)
- [ ] Trading journal with analytics (win rate, profit factor)
- [ ] Bracket/OCO order copying (replicate SL/TP from leader)
- [ ] Order modification copying (leader moves SL → followers follow)
- [ ] Export copy log to CSV
- [ ] Fullscreen cockpit mode
- [ ] Direct function call pattern (replace HTTP self-POST, ~50-80ms faster)

---

## 6. CONTRACT MAPPING TABLE (FOR CROSS-ORDER)

| Full Contract | Micro Contract | Multiplier |
|--------------|----------------|------------|
| NQ | MNQ | 10x |
| ES | MES | 10x |
| YM | MYM | 10x |
| RTY | M2K | 10x |
| GC | MGC | 10x |
| CL | MCL | 10x |

```sql
CREATE TABLE contract_mapping (
    id SERIAL PRIMARY KEY,
    source_symbol VARCHAR(20) NOT NULL,
    target_symbol VARCHAR(20) NOT NULL,
    qty_multiplier REAL DEFAULT 10.0
);
```

---

## 7. DATABASE SCHEMA REFERENCE

### Existing Tables (in copy_trader_models.py)

```sql
-- Leader accounts
CREATE TABLE leader_accounts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    subaccount_id TEXT NOT NULL,
    label TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    auto_copy_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Follower accounts
CREATE TABLE follower_accounts (
    id SERIAL PRIMARY KEY,
    leader_id INTEGER REFERENCES leader_accounts(id),
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    subaccount_id TEXT NOT NULL,
    label TEXT,
    multiplier REAL DEFAULT 1.0,
    is_enabled BOOLEAN DEFAULT TRUE,
    max_position_size INTEGER,
    copy_tp BOOLEAN DEFAULT TRUE,
    copy_sl BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Copy trade log
CREATE TABLE copy_trade_log (
    id SERIAL PRIMARY KEY,
    leader_id INTEGER,
    follower_id INTEGER,
    leader_order_id TEXT,
    follower_order_id TEXT,
    symbol TEXT,
    side TEXT,
    leader_quantity INTEGER,
    follower_quantity INTEGER,
    leader_price REAL,
    follower_price REAL,
    status TEXT,          -- 'filled' or 'error'
    error_message TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Schema Additions Needed (Future)

```sql
-- Add broker_type to follower_accounts (know which API to call for direct-call pattern)
ALTER TABLE follower_accounts ADD COLUMN broker_type TEXT DEFAULT 'tradovate';

-- Add contract mapping for cross-order
CREATE TABLE contract_mapping (
    id SERIAL PRIMARY KEY,
    source_symbol VARCHAR(20) NOT NULL,
    target_symbol VARCHAR(20) NOT NULL,
    qty_multiplier REAL DEFAULT 10.0,
    UNIQUE(source_symbol, target_symbol)
);

-- Add risk limits to follower_accounts
ALTER TABLE follower_accounts ADD COLUMN daily_loss_limit REAL;
ALTER TABLE follower_accounts ADD COLUMN max_drawdown REAL;
ALTER TABLE follower_accounts ADD COLUMN is_locked_out BOOLEAN DEFAULT FALSE;
ALTER TABLE follower_accounts ADD COLUMN lockout_reason TEXT;
```

---

## 8. COMMON PITFALLS — PRODUCTION-VERIFIED

| # | Pitfall | Consequence | Prevention | Commit |
|---|---------|-------------|------------|--------|
| 1 | Internal POST has no Flask session | 401 "Authentication required" on every follower trade | Add `X-Admin-Key` header to internal requests | `03c5853` |
| 2 | `if refreshed:` on dict return value | Non-empty dict always truthy → overwrites valid tokens | Use `if refreshed and refreshed.get('success'):` | `b7529f9` |
| 3 | Token expiry set to 24 hours | Tradovate tokens expire in 90 min → refresh daemon skips expired tokens | Use `timedelta(minutes=85)` | `b7529f9` |
| 4 | `get_positions()` returns `[]` on 401 | Close appears to "succeed" when token is actually expired | Check Sell AND Close — if Sell fails, Close "success" is fake | `b7529f9` |
| 5 | Orphaned follower → deleted account | "Account not found" on every trade to that follower | Validate follower account_id exists before trading | DB cleanup |
| 6 | Sequential follower loop | N followers = N × 300ms total latency | `ThreadPoolExecutor(max_workers=len(followers))` | `22f32be` |
| 7 | `currentLeaderId` null on page load | Propagation skipped — leader trades don't copy | Load leader from DB on init, send with every request | `a38b9b5` |
| 8 | PLATFORM_URL defaults to localhost | Internal HTTP POST unreachable in production | Use `127.0.0.1:{PORT}` (Railway sets PORT) | `e67add9` |
| 9 | No loop prevention | Infinite copy loop (follower fill → re-copy → infinite) | `cl_ord_id.startswith('JT_COPY_')` check | existing |
| 10 | 4PM CT replay | Re-executes entire day's trades on followers | Fill ID dedup set + timestamp filtering | existing |
| 11 | Auto-mode toggle doesn't reconnect | New leaders not picked up until existing connection drops | Reload event with 5s timeout on `asyncio.wait` | `4f854c5` |
| 12 | `railway run` tests local, not container | Package version mismatches, wrong Python version | Use `railway logs` for production verification | lesson |
| 13 | Follower also has webhook trader | Double-fills — one from copy, one from webhook pipeline | `get_subaccounts_with_active_traders()` skips overlapping followers | `e46c4a4` |
| 14 | Toggle startup force-reset | Toggle always shows "Disabled" after deploy | Remove startup UPDATE that sets `copy_trader_enabled='false'` | `ef813fe` |
| 15 | GET/POST race condition on toggle | Stale GET response overwrites user's click | `masterToggleUserChanged` flag — GET callback skips if user already clicked | `39b8122` |
| 16 | Missing import in route handler | `NameError: get_user_by_id` → 500 on POST | Import inside try block, not at module level (sacred file — minimal edit) | `ce4e6a2` |
| 17 | `FLASK_SECRET_KEY` auto-generated | Sessions die on every deploy, all POSTs fail | Set as PERMANENT Railway env var — never auto-generate in production | env var |
| 18 | Sequential auto-copy follower loop | Rapid leader trades queue up, followers fall behind | `asyncio.gather()` for parallel execution | `b26dc75` |
| 19 | Close+re-enter on position add | Follower briefly has no position, extra commission | Detect same-side add/trim, use delta qty | `b97eb10` |
| 20 | WS reconnect during market-closed hours | 429 rate limit errors from unnecessary reconnects | `_is_futures_market_likely_open()` check before reconnect | `2c53a6d` |
| 21 | WS dead-sub threshold too aggressive (3×30s) | 16+ connections ALL reconnect simultaneously → Tradovate HTTP 429 storm cycling every 90s | Threshold: 10×30s (300s). Initial stagger: 0-30s. Dead-sub backoff: min 30s + 0-15s jitter. **NEVER reduce these values.** | `79e3f7b` |
| 22 | Dead WebSocket pool blocks ALL trades | `get_pooled_connection()` tried `_ensure_websocket_connected()` (NEVER functional). `_WS_POOL_LOCK` blocked all coroutines → every trade hit 60s async timeout | `return None` at top of function → REST-only path | `6efcbd5` |
| 23 | **16+ WS connections connect simultaneously** | `asyncio.create_task()` launches ALL reconnects at once → Tradovate HTTP 429 rate limit. Bug #38 fix (thresholds alone) was INSUFFICIENT. | **`asyncio.Semaphore(2)`** in `_run_connection()` wrapping `conn.connect()` + 3s `asyncio.sleep()`. Only 2 connections can attempt at any time. **NEVER REMOVE THIS SEMAPHORE.** | `84d5091` |
| 24 | Token refresh daemon uses sqlite3 | Production uses PostgreSQL — `sqlite3.connect()` fails silently, tokens never refresh → expire → 401 on all API calls | Use PostgreSQL connection pool from existing `get_db_connection()` | `d457d44` |
| 25 | "Unknown error" masks ALL failures | `run_async()` caught exceptions but returned generic error dict. Real errors invisible. | Propagate actual exception message to result dict | `27c38c5` |
| 26 | `max_contracts` DEFAULT 10 silently caps traders | Migration added column with `DEFAULT 10` → ALL new traders limited to 10 contracts with no warning | Migration to reset to 0 (unlimited). Always check what DEFAULT you set on new columns. | `adb859b` |

---

## 9. LEADER/FOLLOWER SETUP — CURRENT PRODUCTION (Feb 23, 2026)

### User 3 (Myles) Test Setup

**Leaders:**
| Leader ID | Account | Subaccount | Label | Auto-Copy |
|-----------|---------|------------|-------|-----------|
| 1 | 590 | 40089666 | jtmj - DEMO1732704 | ON |
| 2 | 427 | 26029294 | Mark - DEMO4419847-2 | OFF |
| 26 | 591 | 39312931 | Test - DEMO6561713 | ON (BROKEN — account 591 deleted) |

**Followers for Leader 1 (DEMO1732704):**
| Follower | Account | Label | Enabled |
|----------|---------|-------|---------|
| 1 | 590:288605 | jtmj - 1127512 (Live) | **DISABLED** (safety) |
| 3 | 427:26029294 | Mark - DEMO4419847-2 | YES |
| 58 | 598:41332021 | test reno - DEMO6762488 | YES |

**Followers for Leader 2 (DEMO4419847-2):**
| Follower | Account | Label | Enabled |
|----------|---------|-------|---------|
| 5 | 590:40089666 | jtmj - DEMO1732704 | YES |
| 6 | 590:288605 | jtmj - 1127512 (Live) | DISABLED |
| 8 | 427:544727 | Mark - 1381296 (Live) | DISABLED |
| 59 | 598:41332021 | test reno - DEMO6762488 | YES |

**Cross-follower pattern:** Trading from leader 1 (704) → copies to 47-2 and 488. Trading from leader 2 (47-2) → copies to 704 and 488. All 3 demos covered regardless of which leader account is used.

---

## 10. TESTING PROCEDURES

### Manual Copy Trader Test
1. Open Manual Copy Trader page
2. Select a leader account from dropdown
3. Click BUY or SELL on a symbol (e.g., MNQH6)
4. Check copy trade log panel for follower entries
5. Verify: all followers show status=filled, similar latency (~300ms)
6. Click CLOSE to flatten all positions
7. Verify: close propagated to all followers

### Auto-Copy Test
1. Ensure leader has `auto_copy_enabled = TRUE`
2. Place a trade directly in Tradovate (not through Just Trades)
3. Check `railway logs` for `"leader_monitor"` detecting the fill
4. Check copy_trade_log for follower entries
5. Verify: followers got the same trade

### Verification Queries
```sql
-- Check latest copy trades
SELECT id, leader_id, follower_id, symbol, side, status, latency_ms, error_message, created_at
FROM copy_trade_log ORDER BY id DESC LIMIT 10;

-- Check follower setup for a leader
SELECT f.id, f.account_id, f.subaccount_id, f.label, f.is_enabled, f.multiplier
FROM follower_accounts f WHERE f.leader_id = 2 AND f.is_enabled = TRUE;

-- Check leader auto-copy status
SELECT id, label, auto_copy_enabled, is_active FROM leader_accounts WHERE user_id = 3;
```

### API Test (with admin key)
```bash
# Place a test sell on leader 2
curl -X POST https://justtrades.app/api/manual-trade \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: YOUR_KEY" \
  -d '{"account_subaccount":"427:26029294","symbol":"MNQH6","side":"Sell","quantity":1,"leader_id":2}'

# Check copy log
curl https://justtrades.app/api/copy-trader/leaders/2/log \
  -H "X-Admin-Key: YOUR_KEY"
```

---

## 11. POSITION SYNC LOGIC — ADD/TRIM/REVERSAL (Feb 23, 2026)

### The Problem (Bug #33)
When the leader adds to a position (Long 1 → Long 2), the original code CLOSED the follower's position then re-entered with the full target quantity. This caused:
- Brief gap with no position (risk exposure)
- Extra commission (two trades instead of one)
- Confusing fill history

### The Fix: Delta-Based Position Sync

`_copy_fill_to_followers()` in `ws_leader_monitor.py` (line ~1065) now detects five scenarios:

| Scenario | Detection | Follower Action | Risk Config |
|----------|-----------|-----------------|-------------|
| **ENTRY** (from flat) | `leader_was_flat` and `leader_target_qty > 0` | Fresh entry with full qty | Leader's TP/SL copied |
| **CLOSE** (to flat) | `follower_target_qty == 0` | `_execute_follower_close()` | None |
| **ADD** (same side, higher qty) | `leader_target_side == leader_prev_side` and `target > prev` | Entry for DIFFERENCE only | None (no TP/SL on adds) |
| **TRIM** (same side, lower qty) | `leader_target_side == leader_prev_side` and `target < prev` | Opposite-side entry for DIFFERENCE | None |
| **REVERSAL** (side change) | `leader_target_side != leader_prev_side` | Close + re-enter full target | Leader's TP/SL copied |

### Key Implementation Details

```python
# Variables from fill_data (set by _process_fill)
leader_prev = fill_data.get('leader_prev_position', {'side': '', 'qty': 0})
leader_pos = fill_data.get('leader_position', {'side': '', 'qty': 0})

# Per-follower calculation
follower_prev_qty = max(1, int(round(leader_prev_qty * multiplier)))
follower_target_qty = max(1, int(round(leader_target_qty * multiplier)))

# Both are capped by max_position_size if set
if max_pos > 0:
    follower_prev_qty = min(follower_prev_qty, max_pos)
    follower_target_qty = min(follower_target_qty, max_pos)

# Delta
add_qty = follower_target_qty - follower_prev_qty   # positive = add
trim_qty = follower_prev_qty - follower_target_qty   # positive = trim
```

### NEVER:
- Close + re-enter for same-side position changes
- Forget to apply multiplier to BOTH target and previous qty
- Forget to cap BOTH with max_position_size
- Send risk_config (TP/SL) on adds/trims — only on fresh entries from flat
