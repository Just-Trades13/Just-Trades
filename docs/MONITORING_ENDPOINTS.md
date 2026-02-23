# Monitoring Endpoints Reference — Just Trades Platform

> **Complete reference for all health, status, and monitoring endpoints.**
> **Use this doc when building alerts, dashboards, or debugging production issues.**
> **Last updated: Feb 23, 2026**

---

## ENDPOINT SUMMARY

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/health` | GET | None | Simple health check (Railway) |
| `/status` | GET | None | Full system status |
| `/health/detailed` | GET | Admin/API key | Complete health diagnostic |
| `/api/broker-execution/status` | GET | Admin/API key | Broker worker status and queue |
| `/api/broker-execution/failures` | GET | Admin/API key | Recent execution failures |
| `/api/broker-queue/stats` | GET | None | Real-time broker queue statistics |
| `/api/broker-queue/clear-cache` | POST | Admin/API key | Clear broker cache |
| `/api/webhook-activity` | GET | Admin/API key | Webhook processing log |
| `/api/raw-webhooks` | GET | Admin/API key | Raw webhook payloads (pre-filter) |
| `/api/tradingview/status` | GET | None | TradingView WebSocket status |
| `/api/tradingview/auth-status` | GET | None | TradingView session cookie status |
| `/api/tradingview/refresh` | POST | None | Force TradingView reconnect |
| `/api/accounts/auth-status` | GET | None | Broker auth token health |
| `/api/admin/max-loss-monitor/status` | GET | Login | Max daily loss breach monitor |
| `/api/admin/whop-sync-status` | GET | API key | Whop sync daemon health |
| `/api/admin/dashboard-stats` | GET | Login | Admin dashboard overview |
| `/api/paper-trades/service-status` | GET | None | Paper trading service status |
| `/api/market-data/status` | GET | None | Market data and cached prices |
| `/api/thread-health` | GET | Admin/API key | Background thread status |
| *Position Monitor* | *Logs* | *N/A* | *`position_monitor` logger in Railway logs (no dedicated endpoint yet); thread visible via `/api/thread-health`* |
| `/api/recorders/<id>/execution-status` | GET | None | Per-recorder execution capability |
| `/api/traders/<id>/broker-state` | GET | None | Live broker state for a trader |
| `/api/account/<id>/broker-state` | GET | None | Live broker state for an account |
| `/api/run-migrations` | POST | Admin/API key | Run pending DB migrations |

---

## CORE HEALTH ENDPOINTS

### GET /health

Simple health check for Railway's health monitoring.

**Auth:** None
**Response:**
```json
{
  "status": "ok",
  "service": "just-trades",
  "purpose": "Trading automation platform",
  "port": 5000,
  "timestamp": "2026-02-21T14:30:00Z"
}
```

**Alert threshold:** Any non-200 response = service down. Railway uses this for auto-restart.

---

### GET /status

Full system status including WebSocket, positions, and trades.

**Auth:** None
**Response:**
```json
{
  "open_trades": 3,
  "indexed_positions": 5,
  "indexed_trades": 142,
  "websocket_connected": true,
  "subscribed_symbols": ["NQ", "ES", "GC", "MNQ", "MGC", "CL"],
  "cached_prices": {
    "NQ": {"last": 21534.75, "updated": "2026-02-21T14:30:00Z"},
    "GC": {"last": 2945.30, "updated": "2026-02-21T14:30:00Z"}
  },
  "timestamp": "2026-02-21T14:30:00Z"
}
```

**Alert thresholds:**
- `websocket_connected: false` → TradingView WebSocket down, prices may be stale
- `cached_prices` timestamps > 15 minutes old during market hours → data feed issue

---

### GET /health/detailed

Complete health diagnostic including DB pool, queue sizes, and thread counts.

**Auth:** `@admin_or_api_key_required`
**Response:** Detailed JSON with database pool status, memory usage, thread counts, and all subsystem health indicators.

---

## BROKER EXECUTION ENDPOINTS

### GET /api/broker-execution/status

The most important monitoring endpoint. Shows broker worker health, queue status, and live execution stats.

**Auth:** `@admin_or_api_key_required`
**Response:**
```json
{
  "external_engine_mode": false,
  "fast_webhook": {
    "workers_alive": 10,
    "total_processed": 1543,
    "avg_latency_ms": 42
  },
  "broker_execution": {
    "workers_alive": 10,
    "queue_size": 0,
    "total_processed": 892,
    "total_failures": 3,
    "avg_execution_ms": 168
  },
  "traders": {
    "total_enabled": 45,
    "total_accounts": 12
  },
  "signal_blocking": {
    "currently_blocked": []
  }
}
```

**Alert thresholds:**
- `broker_execution.workers_alive` < 10 → Workers died, restart service
- `broker_execution.queue_size` > 0 (outside market hours) → Stale items in queue
- `broker_execution.queue_size` > 50 (during market hours) → Backlog, possible deadlock
- `fast_webhook.avg_latency_ms` > 200 → Something blocking webhook pipeline

---

### GET /api/broker-execution/failures

Recent trade execution failures with error details.

**Auth:** `@admin_or_api_key_required`
**Query params:** `?limit=20` (default 20)
**Response:**
```json
{
  "failures": [
    {
      "timestamp": "2026-02-21T14:25:00Z",
      "recorder_name": "JADNQ",
      "trader_id": 1359,
      "account_id": 456,
      "error": "Token expired - needs re-authentication",
      "symbol": "NQH6",
      "action": "buy"
    }
  ]
}
```

**Common errors and fixes:**
| Error | Cause | Fix |
|-------|-------|-----|
| `Token expired` | Tradovate OAuth token expired | User re-authenticates via OAuth |
| `Rate limit exceeded` | Too many API calls per token (Rule 16) | Reduce broker queries |
| `Invalid price increment` | TP/SL not on tick boundary (Rule 3) | Fix tick rounding |
| `Account not found` | Wrong subaccount_id | Check account configuration |
| `Insufficient funds` | Account balance too low | User adds funds |

---

### GET /api/broker-queue/stats

Real-time broker API queue statistics.

**Auth:** None
**Response:**
```json
{
  "queue_size": 0,
  "processing_rate": 12.5,
  "success_rate": 99.2
}
```

---

### POST /api/broker-queue/clear-cache

Clears broker price, position, and order caches. Use when cached data seems stale.

**Auth:** `@admin_or_api_key_required`
**Response:**
```json
{
  "success": true,
  "message": "All broker caches cleared"
}
```

---

## WEBHOOK MONITORING

### GET /api/webhook-activity

Recent webhook processing log with success/failure statistics.

**Auth:** `@admin_or_api_key_required`
**Query params:** `?limit=10` (default 10)
**Response:**
```json
{
  "stats": {
    "total": 150,
    "success": 142,
    "failed": 5,
    "blocked": 3,
    "success_rate": 94.7
  },
  "activity": [
    {
      "timestamp": "2026-02-21T14:30:00Z",
      "recorder_name": "JADNQ",
      "action": "buy",
      "ticker": "NQH6",
      "status": "success",
      "latency_ms": 45,
      "traders_notified": 7
    }
  ]
}
```

**Alert thresholds:**
- `success_rate` < 90% → Investigate failures
- `blocked` count rising → Check time filters, cooldown settings
- No activity during market hours → TradingView alerts may have stopped

---

### GET /api/raw-webhooks

Raw webhook payloads BEFORE any filtering. Essential for debugging "webhook not arriving" issues.

**Auth:** `@admin_or_api_key_required`
**Query params:** `?limit=10` (default 10)
**Response:**
```json
{
  "total": 200,
  "action_breakdown": {
    "buy": 85,
    "sell": 72,
    "closelong": 20,
    "closeshort": 18,
    "close": 5
  },
  "webhooks": [
    {
      "timestamp": "2026-02-21T14:30:00Z",
      "webhook_token": "abc-123-def",
      "raw_body": "{\"action\":\"buy\",\"ticker\":\"NQH6\",\"price\":21500.00}",
      "source_ip": "52.89.214.238"
    }
  ]
}
```

**Use case:** When a signal appears in raw-webhooks but not in webhook-activity, the webhook was received but filtered out (time filter, cooldown, disabled recorder, etc.).

---

## TRADINGVIEW WEBSOCKET

### GET /api/tradingview/status

TradingView WebSocket connection health and cached price data.

**Auth:** None
**Response:**
```json
{
  "websocket_connected": true,
  "subscribed_symbols": ["NQ", "ES", "GC", "MNQ", "MGC", "CL", "SI", "MES"],
  "cached_prices": {
    "NQ": {"last": 21534.75, "updated": "2026-02-21T14:30:00Z"},
    "GC": {"last": 2945.30, "updated": "2026-02-21T14:30:00Z"}
  },
  "session_updated_at": "2026-02-20T10:00:00Z",
  "auto_refresh_enabled": true,
  "jwt_token_valid": true
}
```

**Alert thresholds:**
- `websocket_connected: false` → WebSocket disconnected, using polling fallback
- `jwt_token_valid: false` → Session cookies expired, prices delayed 10-15 min (Rule 27)
- Price `updated` > 60s old during market hours → Data feed stale

---

### GET /api/tradingview/auth-status

TradingView session cookie and authentication details.

**Auth:** None
**Response:**
```json
{
  "has_credentials": true,
  "session_file_exists": true,
  "cookies_valid": true,
  "auto_refresh_enabled": true,
  "message": "TradingView session active with valid JWT"
}
```

---

### POST /api/tradingview/refresh

Force TradingView session cookie refresh and WebSocket reconnect.

**Auth:** None
**Response:**
```json
{
  "success": true,
  "message": "TradingView session refreshed, WebSocket reconnecting"
}
```

---

## ACCOUNT HEALTH

### GET /api/accounts/auth-status

Lists all accounts and their broker authentication status.

**Auth:** None
**Response:**
```json
{
  "all_accounts_valid": false,
  "accounts_needing_reauth": [
    {
      "id": 123,
      "name": "Demo Account 1",
      "status": "expired",
      "action": "Re-authenticate via OAuth"
    }
  ],
  "count": 1
}
```

**Alert threshold:** `all_accounts_valid: false` → Some accounts can't trade until re-authenticated.

---

### GET /api/admin/max-loss-monitor/status

Real-time monitoring of traders hitting their max daily loss limit.

**Auth:** `@login_required`
**Response:**
```json
{
  "monitored_traders": 45,
  "daily_loss_breach_count": 2,
  "breach_details": [
    {
      "trader_id": 1359,
      "recorder_name": "JADNQ",
      "max_daily_loss": 1000.00,
      "current_daily_loss": -1250.00,
      "status": "breached"
    }
  ]
}
```

---

## WHOP SYNC

### GET /api/admin/whop-sync-status

Whop sync daemon health and statistics.

**Auth:** API key
**Response:**
```json
{
  "last_run": "2026-02-21T14:29:30Z",
  "last_synced": 0,
  "last_resent": 0,
  "total_synced": 47,
  "total_resent": 12,
  "sync_interval_seconds": 30,
  "pending_resends": 0,
  "stuck_users": []
}
```

**Alert thresholds:**
- `last_run` > 5 minutes old → Sync daemon stopped, restart service
- `stuck_users` not empty → Users haven't activated in 3+ days, may need manual intervention
- `pending_resends` > 10 → Many users not activating, check email deliverability

---

## ADMIN DASHBOARD

### GET /api/admin/dashboard-stats

Overview statistics for the admin dashboard.

**Auth:** `@login_required`
**Response:**
```json
{
  "user_count": 52,
  "total_users": 60,
  "approved_users": 52,
  "recorders": 8,
  "strategies": 5,
  "affiliated": 3,
  "daily_pnl": 1250.00
}
```

---

## PAPER TRADING & MARKET DATA

### GET /api/paper-trades/service-status

Paper trading service health.

**Auth:** None
**Response:**
```json
{
  "v2_database_exists": true,
  "total_paper_trades": 342,
  "open_count": 5,
  "closed_count": 337,
  "last_close_time": "2026-02-21T14:15:00Z"
}
```

---

### GET /api/market-data/status

Available market data tokens and cached price information.

**Auth:** None
**Response:**
```json
{
  "available_tokens": 8,
  "last_update": "2026-02-21T14:30:00Z",
  "cached_prices": {
    "NQ": 21534.75,
    "ES": 6120.50,
    "GC": 2945.30
  },
  "symbol_count": 8
}
```

---

## THREAD HEALTH

### GET /api/thread-health

Status of all background daemon threads.

**Auth:** `@admin_or_api_key_required`
**Response:** JSON with status for each background thread (running/stopped/error).

**Alert threshold:** Any expected thread showing "stopped" → restart service.

---

## WEBSOCKET POSITION MONITOR

### Monitoring via Railway Logs

The WebSocket Position Monitor logs to the `position_monitor` logger. Filter Railway logs:

```bash
railway logs -n 5000 --filter "position_monitor"
```

**Healthy startup sequence:**
```
position_monitor - INFO - Position WebSocket monitor daemon thread started
position_monitor - INFO - Starting Position WebSocket Monitor...
position_monitor - INFO - Built subaccount->recorder map: 18 subaccounts, 19 recorder mappings
position_monitor - INFO - Account groups query returned 13 rows
position_monitor - INFO - Position monitor: 12 token group(s), 13 total accounts
position_monitor - INFO - [...tokenKey] Connecting to Tradovate (N accounts, demo/live)
position_monitor - INFO - [...tokenKey] Authenticated
position_monitor - INFO - [...tokenKey] Subscribed to sync for accounts [IDs]
```

**Healthy runtime messages (every 30s per connection):**
```
position_monitor - INFO - [...tokenKey] WS stats: 12 msgs (0 data) in 30s
```

**Event messages (real-time):**
```
position_monitor - INFO - [...tokenKey] Position event: account=26029294 symbol=MNQH6 netPos=1 netPrice=24893.0
position_monitor - INFO - [...tokenKey] Fill event: account=26029294 ...
```

**Error indicators:**
| Log Message | Meaning | Fix |
|-------------|---------|-----|
| `Error loading account groups: column X does not exist` | SQL query references wrong table/column | Fix SQL in ws_position_monitor.py |
| `No active Tradovate accounts for position monitoring` | Query returned 0 rows — check broker filter, token validity | Verify accounts have `tradovate_token` set and `broker = 'Tradovate'` |
| `Auth failed — no s:200 response` | Token expired or invalid | Token refresh daemon should handle, or user needs re-OAuth |
| `No data for 3 consecutive windows` | Dead subscription | Auto-reconnects |
| `Connection error: ...` | Network issue | Auto-reconnects with exponential backoff |
| `Position WebSocket monitor failed to start` | Import or startup error | Check Railway build logs for missing dependencies |

**Alert thresholds:**
- No `position_monitor` log entries at all after deploy → Monitor didn't start (check startup location)
- `Error loading account groups` repeating → SQL bug
- `No active Tradovate accounts` repeating → No valid tokens or broker column mismatch
- `Auth failed` across all connections → Token refresh daemon broken
- `No data for 3 consecutive windows` on active account → Possible Tradovate API issue

---

## PER-ENTITY DEBUGGING

### GET /api/recorders/{id}/execution-status

Why a specific recorder might not be executing trades.

**Auth:** None
**Response:**
```json
{
  "enabled_accounts_count": 7,
  "missing_traders": [],
  "issues": [],
  "execution_capability": "full"
}
```

**Use case:** When a specific recorder's trades aren't executing, this endpoint shows if traders are missing, accounts are disconnected, or other issues exist.

---

### GET /api/traders/{id}/broker-state

Live broker positions and working orders for a specific trader.

**Auth:** None
**Response:** Actual positions and orders from the broker API (not DB cache). Use for debugging position mismatches.

---

### GET /api/account/{id}/broker-state

Live broker state for an entire account.

**Auth:** None
**Response:** All positions and orders for the account from the broker API.

---

## DATABASE MANAGEMENT

### POST /api/run-migrations

Run pending database migrations.

**Auth:** `@admin_or_api_key_required`
**Response:**
```json
{
  "success": true,
  "migrations": [
    {"table": "traders", "column": "new_column", "status": "added"},
    {"table": "recorders", "column": "other_column", "status": "already_exists"}
  ]
}
```

---

## AUTHENTICATION TYPES

| Auth Level | How to Access | Endpoints |
|-----------|---------------|-----------|
| **None** | Direct access | `/health`, `/status`, `/api/tradingview/*`, `/api/market-data/*`, `/api/paper-trades/*`, `/api/accounts/auth-status`, per-entity debugging |
| **Login required** | Flask session cookie | `/api/admin/dashboard-stats`, `/api/admin/max-loss-monitor/status` |
| **Admin/API key** | Admin session OR `?api_key=X` query param | `/health/detailed`, `/api/broker-execution/*`, `/api/webhook-activity`, `/api/raw-webhooks`, `/api/thread-health`, `/api/run-migrations` |
| **API key only** | `?api_key=X` query param | `/api/admin/whop-sync-status` |

---

## RECOMMENDED ALERT THRESHOLDS

| Metric | Warning | Critical | Source Endpoint |
|--------|---------|----------|----------------|
| Service health | N/A | Non-200 response | `/health` |
| Broker workers alive | < 10 | < 5 | `/api/broker-execution/status` |
| Queue depth | > 10 | > 50 | `/api/broker-execution/status` |
| Webhook success rate | < 95% | < 80% | `/api/webhook-activity` |
| TradingView WebSocket | disconnected | disconnected > 5 min | `/api/tradingview/status` |
| JWT valid | false (delayed prices) | false > 1 hour | `/api/tradingview/status` |
| Token auth | 1+ accounts expired | All accounts expired | `/api/accounts/auth-status` |
| Whop sync age | > 2 min | > 5 min | `/api/admin/whop-sync-status` |
| Stuck users | > 0 | > 5 | `/api/admin/whop-sync-status` |
| Execution failures | > 0 in last hour | > 10 in last hour | `/api/broker-execution/failures` |
| Webhook latency | > 100ms avg | > 500ms avg | `/api/broker-execution/status` |

---

*Source: Production endpoint exploration of Just Trades platform. All endpoints verified against ultra_simple_server.py.*
