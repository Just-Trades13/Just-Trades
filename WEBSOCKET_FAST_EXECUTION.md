# WebSocket Fast Execution System

**Added:** January 15, 2026
**Status:** CRITICAL - DO NOT REMOVE

## Overview

This system provides 5-10x faster order execution by using persistent WebSocket connections to Tradovate instead of REST API calls.

| Method | Speed | Status |
|--------|-------|--------|
| REST API | ~1-2 seconds | Fallback |
| WebSocket | ~100-300ms | Primary |

## Components

### 1. websockets Library (requirements.txt)

```
websockets==12.0
```

**Purpose:** Enables Python WebSocket support for Tradovate API.

**Without it:** System silently falls back to REST API (slow).

### 2. WebSocket Connection Pool (recorder_service.py)

```python
_WS_POOL: Dict[int, Any] = {}
_WS_POOL_LOCK = threading.Lock()
```

**Purpose:** Stores persistent WebSocket connections by subaccount_id for reuse.

**Without it:** Each trade creates a new connection (1-2 sec overhead).

### 3. get_pooled_connection() Function (recorder_service.py)

```python
async def get_pooled_connection(subaccount_id: int, is_demo: bool, access_token: str):
```

**Purpose:** Returns existing WebSocket connection or creates new one and adds to pool.

**Location:** recorder_service.py, around line 148

### 4. WebSocket Keep-Alive Daemon (recorder_service.py)

```python
def start_websocket_keepalive_daemon():
```

**Purpose:** Background thread that:
- Runs every 30 seconds
- Pings all WebSocket connections to keep them alive
- Auto-reconnects dropped connections
- Prevents Tradovate from closing idle connections

**Location:** recorder_service.py, around line 378

**Without it:** Connections drop after ~30 seconds of inactivity, falling back to REST.

### 5. WebSocket Status Endpoint (ultra_simple_server.py)

```
GET /api/websocket-status
```

**Purpose:** Diagnostic endpoint to verify WebSocket connections are active.

**Response Example:**
```json
{
  "success": true,
  "websocket_orders_enabled": true,
  "connection_pool": {
    "size": 13,
    "connections": {
      "37783642": {"ws_connected": true, "has_websocket": true, "is_demo": true}
    }
  }
}
```

**Interpretation:**
- `ws_connected: true` = WebSocket active (FAST)
- `ws_connected: false` = Will fall back to REST (slow)
- `size: 0` = No active connections (normal if no recent trades)

### 6. TradovateIntegration WebSocket Config (phantom_scraper/tradovate_integration.py)

```python
self.use_websocket_orders = True
```

**Purpose:** Flag that enables WebSocket-first order routing.

**Location:** TradovateIntegration.__init__(), around line 45

## How It Works

1. **Signal received** via webhook
2. **execute_trade_simple()** called in recorder_service.py
3. **get_pooled_connection()** returns existing WebSocket or creates new
4. **place_order_smart()** tries WebSocket first
5. If WebSocket fails, **falls back to REST API**
6. **Keep-alive daemon** pings connections every 30 seconds
7. Dropped connections **auto-reconnect** on next ping cycle

## Verification

### Check WebSocket Status
```
https://justtrades-production.up.railway.app/api/websocket-status
```

### Check Railway Logs
Search for:
- `"via WebSocket"` = WebSocket was used (good)
- `"REST fallback"` = Fell back to REST (slow)
- `"WebSocket keep-alive daemon started"` = Daemon is running
- `"WebSocket reconnected"` = Auto-reconnected a dropped connection

## Troubleshooting

### All connections show ws_connected: false

1. Check if `websockets` is in requirements.txt
2. Check Railway logs for WebSocket errors
3. Verify tokens are valid (expired tokens can't authenticate WebSocket)

### Pool is always empty (size: 0)

1. Manual trades don't use the pool (only auto/webhook trades do)
2. Trigger a webhook signal to populate the pool
3. Check if get_pooled_connection() is being called

### Connections drop after 30 seconds

1. Verify keep-alive daemon is running (check logs)
2. Check for `"WebSocket keep-alive daemon started"` in logs
3. Daemon might not have started - check for import errors

## Files Involved

| File | Component |
|------|-----------|
| `requirements.txt` | `websockets==12.0` |
| `recorder_service.py` | Pool, get_pooled_connection, keep-alive daemon |
| `ultra_simple_server.py` | /api/websocket-status endpoint |
| `phantom_scraper/tradovate_integration.py` | WebSocket order methods |

## DO NOT REMOVE

This system is critical for fast order execution. Removing any component will cause:
- 5-10x slower order execution
- Higher latency between signal and fill
- Potential missed trades during fast market moves

---

*Last updated: January 15, 2026*
*Implemented by: Cursor AI with user approval*
