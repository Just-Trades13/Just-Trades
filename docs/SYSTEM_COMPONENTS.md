# System Components Reference — Just Trades Platform

> **Complete reference for all background daemons, services, and subsystem architecture.**
> **Last updated: Feb 24, 2026**

---

## Background Daemons (All Auto-Start on Deploy)

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

---

## Token Refresh Daemon (recorder_service.py ~302)

Three-tier refresh strategy:
1. **Primary**: `POST /v1/auth/renewaccesstoken` with refresh_token (Bearer auth)
2. **Secondary**: `TradovateAPIAccess.login(username, password)` if refresh token fails
3. **Tertiary**: Falls back to stored credentials (trades still execute via API Access)

Checks every 5 minutes. Triggers refresh if token expires within 30 minutes. On failure: logs warning, adds account to `_ACCOUNTS_NEED_REAUTH` set (visible at `/api/accounts/auth-status`).

---

## Position Reconciliation (recorder_service.py ~6384)

**DO NOT DISABLE.** This is the safety net for the entire trading system.

What it does every 5 minutes (safety net — WS position monitor is primary):
1. `reconcile_positions_with_broker()` — Syncs DB quantity/avg price with broker
2. `check_auto_flat_cutoff()` — Flattens positions after configured market hours
3. **AUTO-PLACES missing TP orders** — If TP recorded in DB but not found on broker, places it
4. Closes DB records when broker is flat
5. Updates DB to match broker's actual position quantity

---

## Paper Trading System (ultra_simple_server.py ~351)

- Separate database: `paper_trades` table (SQLite `paper_trades.db` or PostgreSQL)
- Called from webhook handler for recorders in `simulation_mode=1`
- Deduplication: `_paper_trade_dedup` prevents duplicate signals within 1.0 second
- Tracks: entry/exit price, P&L, TP/SL levels, MFE/MAE, commission, cumulative P&L
- **Non-blocking**: Paper trades NEVER block the broker pipeline (daemon threads only)

---

## TradingView WebSocket (recorder_service.py ~6659)

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

---

## Whop Sync Daemon (ultra_simple_server.py ~9239)

Polls every 30 seconds (`WHOP_SYNC_INTERVAL = 30`). Three-layer protection:
- **Layer 1**: Real-time Whop webhook (`/webhooks/whop`) — fires on purchase
- **Layer 2**: Sync daemon (30s poll) — catches missed webhooks, network failures
- **Layer 3**: Manual admin sync button

Email resend strategy:
- First sync: sends activation immediately
- If unactivated after 12 hours (`WHOP_RESEND_INTERVAL`): resends
- Stops after 3 days (`WHOP_RESEND_MAX_DAYS`)
- Tracks "stuck users" for admin review at `/api/admin/whop-sync-status`

---

## Shared WebSocket Connection Manager (ws_connection_manager.py)

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
6. Initial connection stagger: **0-30s random delay** per connection on startup
7. Max connection: 70 min (before 85-min token expiry), exponential backoff: 1→2→4→8...60s
8. Fresh token from DB before each reconnect
9. Dynamic subscription: new listener accounts trigger re-subscribe on next heartbeat

**Key Design:**
- Messages parsed ONCE in `SharedConnection._dispatch_message()`, pre-parsed items dispatched to all listeners
- Each listener's `on_message()` wrapped in try/except — one crashing listener doesn't affect others
- Thread-safe registration via `asyncio.run_coroutine_threadsafe()` from any thread
- `get_connection_manager()` returns singleton `TradovateConnectionManager`

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

---

## WebSocket Position Monitor (ws_position_monitor.py)

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

*Source: CLAUDE.md "SYSTEM COMPONENTS REFERENCE" section*
