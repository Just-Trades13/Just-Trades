# BUILD A TRADESYNCER COMPETITOR — COMPLETE REFERENCE

## WHAT THIS DOCUMENT IS
Feed this to Claude CLI alongside your Just Trades codebase. It contains everything needed to make Pro Copy Trader work like Tradesyncer: official Tradovate WebSocket protocol, reference implementation code, the complete Tradesyncer feature set to match, and the exact data flow architecture.

---

# PART 1: HOW TRADESYNCER ACTUALLY WORKS (REVERSE-ENGINEERED)

## Architecture
```
┌─────────────────────────────────────────────────────────┐
│                   TRADESYNCER CLOUD                      │
│                                                          │
│  ┌──────────────────┐     ┌──────────────────────────┐  │
│  │  WebSocket Pool   │     │   REST Execution Engine   │  │
│  │                    │     │                            │  │
│  │  Per-user WS to   │────▶│  On fill event detected:   │  │
│  │  Tradovate via    │     │  For each follower:        │  │
│  │  user/syncrequest │     │    POST order/placeorder   │  │
│  │                    │     │    with scaled qty +       │  │
│  │  Filters:          │     │    contract mapping        │  │
│  │  - fill events     │     │                            │  │
│  │  - order events    │     │  Log to copy_trade_log     │  │
│  │  - position events │     │  Update cockpit dashboard  │  │
│  └──────────────────┘     └──────────────────────────┘  │
│                                                          │
│  ┌──────────────────┐     ┌──────────────────────────┐  │
│  │  Risk Engine       │     │   Cockpit Dashboard       │  │
│  │                    │     │                            │  │
│  │  - Daily loss      │     │  - Real-time positions     │  │
│  │    limit per acct  │     │  - Account balances        │  │
│  │  - Max drawdown    │     │  - Open PNL per contract   │  │
│  │  - Session locks   │     │  - Copy log with status    │  │
│  │  - Follower        │     │  - Flatten buttons         │  │
│  │    protection      │     │  - Enable/disable toggles  │  │
│  └──────────────────┘     └──────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │                              │
         │ WebSocket (persistent)       │ REST API (per order)
         ▼                              ▼
┌──────────────┐              ┌──────────────────┐
│  TRADOVATE    │              │  TRADOVATE        │
│  Leader Acct  │              │  Follower Accts   │
│  (user trades │              │  (orders placed   │
│   on any      │              │   via REST API)   │
│   front-end)  │              │                   │
└──────────────┘              └──────────────────┘
```

## Tradesyncer Data Flow (step by step)
1. User connects Tradovate account via API key/secret
2. Tradesyncer authenticates → gets accessToken
3. Opens WebSocket to `wss://live.tradovateapi.com/v1/websocket`
4. Sends `authorize\n0\n\n{accessToken}`
5. On auth success → sends `user/syncrequest\n1\n\n{entityTypes:[...]}` 
6. Starts `[]` heartbeat every 2.5s
7. **LISTENS** for `"e":"props"` events with `entityType: "fill"` or `"order"`
8. On fill detected on leader account:
   - Check: is this OUR order? (loop prevention) → skip
   - Get symbol/action/qty from fill entity
   - For each enabled follower:
     - Calculate qty: leader_qty × follower_multiplier (or ratio)
     - Map contract if cross-order enabled (NQ → MNQ)
     - POST `order/placeorder` via REST to follower account
     - Log result (success/error, latency, order_id)
9. Dashboard updates in real-time via WebSocket to browser

---

# PART 2: TRADESYNCER FEATURE CHECKLIST (WHAT TO MATCH)

## Core Features (MUST HAVE — MVP)
- [x] **Connect Tradovate accounts** (API key auth)
- [ ] **Designate lead account** (one per user)
- [ ] **WebSocket monitoring** of leader via `user/syncrequest`
- [ ] **Auto-copy fills** to all enabled followers
- [ ] **Quantity multiplier** per follower (ratio copy)
- [ ] **Enable/disable** per follower account
- [ ] **Copy log** with status (filled/error/latency)
- [ ] **Loop prevention** (don't copy your own copies)
- [ ] **Flatten per account** (close positions + cancel orders)
- [ ] **Flatten all** (close everything across all accounts)
- [ ] **Manual trade** on leader propagates to followers
- [ ] **Close propagation** (leader closes → all followers close)

## Important Features (SHOULD HAVE — Phase 2)
- [ ] **Cross-order** (NQ leader → MNQ follower, with contract mapping)
- [ ] **Follower protection** (stop copying if follower hits risk limit)
- [ ] **Daily PNL tracking** per account
- [ ] **Open PNL** per contract per account (real-time)
- [ ] **Account balance** display
- [ ] **Open quantity** display per contract
- [ ] **Active side** (buy/sell) per account per contract
- [ ] **Session time locks** (don't copy outside trading hours)
- [ ] **Daily loss limit** per follower account → auto-disable
- [ ] **Max drawdown** per follower → auto-disable

## Nice to Have (Phase 3)
- [ ] **Copy groups** (multiple leader/follower groups)
- [ ] **Trading journal** with analytics (win rate, profit factor)
- [ ] **Economic calendar** integration
- [ ] **Bracket/OCO order** copying (copy SL/TP from leader)
- [ ] **Order modification** copying (leader moves SL → followers move SL)
- [ ] **Export copy log** to CSV
- [ ] **Fullscreen cockpit** mode
- [ ] **Hide sensitive info** toggle

---

# PART 3: OFFICIAL TRADOVATE WEBSOCKET PROTOCOL

## Endpoints

| Environment | Auth (REST) | WebSocket |
|-------------|-------------|-----------|
| Production | `https://live.tradovateapi.com/v1/auth/accesstokenrequest` | `wss://live.tradovateapi.com/v1/websocket` |
| Demo | `https://demo.tradovateapi.com/v1/auth/accesstokenrequest` | `wss://demo.tradovateapi.com/v1/websocket` |
| Staging (new) | `https://live-api.staging.ninjatrader.dev/v1/auth/accesstokenrequest` | `wss://live-api.staging.ninjatrader.dev/v1/websocket` |

## Auth Request Body
```json
{
  "name": "username",
  "password": "password",
  "appId": "your_app_id",
  "appVersion": "1.0",
  "sec": "your_secret_key",
  "cid": 0
}
```

## Custom Wire Protocol (NOT standard JSON WebSocket!)

| Direction | Type | Format | Example |
|-----------|------|--------|---------|
| Server→Client | Open frame | `o` | `o` |
| Client→Server | Auth | `authorize\n{reqId}\n\n{token}` | `authorize\n0\n\neyJ...` |
| Client→Server | API call | `{endpoint}\n{reqId}\n\n{jsonBody}` | `user/syncrequest\n1\n\n{...}` |
| Client→Server | Heartbeat | `[]` | `[]` |
| Server→Client | Response | `a[{jsonArray}]` | `a[{"i":0,"s":200}]` |
| Server→Client | Event | `a[{"e":"props","d":{...}}]` | see below |

## Connection Lifecycle (EXACT ORDER — CRITICAL)
```
1. Connect to wss://live.tradovateapi.com/v1/websocket
2. WAIT for server to send 'o' frame (DO NOT auth on 'onopen'!)
3. Send: authorize\n0\n\n{accessToken}
4. WAIT for: a[{"i":0,"s":200,...}]
5. Send: user/syncrequest\n1\n\n{"splitResponses":true,"entityTypes":["order","fill","position","orderStrategy"]}
6. Start heartbeat: send '[]' every 2500ms
7. Process incoming 'a[...]' messages for events
```

## Timing Constants
```
HEARTBEAT_INTERVAL    = 2500ms   (client sends '[]')
SERVER_TIMEOUT        = 10000ms  (no server message = dead)
TIMEOUT_CHECK         = 5000ms   (how often to check)
TOKEN_REFRESH         = 85 min   (before 90min expiry)
TOKEN_BUFFER          = 5 min    (start refresh early)
CONNECTION_TIMEOUT    = 10000ms  (max wait for connect)
INITIAL_RECONNECT     = 1000ms   (first retry delay)
MAX_RECONNECT_DELAY   = 60000ms  (cap)
MAX_RECONNECT_ATTEMPTS = 10
BACKOFF_JITTER        = 0-10%    (avoid thundering herd)
```

## Reconnection: Exponential Backoff
```
delay = min(initialDelay × 2^attempt, maxDelay) + random(0, delay × 0.1)
Attempt 1: ~1s, 2: ~2s, 3: ~4s, 4: ~8s, 5: ~16s, 6: ~32s, 7+: ~60s (capped)
```

---

# PART 4: USER/SYNCREQUEST — THE CORE ENDPOINT

## ONLY available via WebSocket (not REST)
## ONLY send ONCE per socket lifecycle (conformance requirement)

## Request
```
user/syncrequest\n1\n\n{"splitResponses":true,"entityTypes":["order","fill","position","orderStrategy"]}
```

### entityTypes for Copy Trading
Subscribe to: `order`, `fill`, `position`, `orderStrategy`
Ignore: `account`, `cashBalance`, `marginSnapshot`, `userProperty`, `accountRiskStatus`

(Subscribe to more if you want dashboard data like account balance)

## Event Structure
```json
{
  "e": "props",
  "d": {
    "entityType": "fill",
    "entity": {
      "id": 123456,
      "orderId": 789,
      "contractId": 1234,
      "timestamp": "2025-02-22T15:30:00.000Z",
      "tradeDate": {"year": 2025, "month": 2, "day": 22},
      "action": "Buy",
      "qty": 1,
      "price": 21500.25,
      "active": true,
      "finallyPaired": 0
    },
    "eventType": "Created"
  }
}
```

## What To Do With Each Event

| entityType | eventType | Action |
|------------|-----------|--------|
| `fill` | `Created` | **PRIMARY TRIGGER** — copy this trade to followers |
| `order` | `Created` | Track for reference / detect pending orders |
| `order` | `Updated` | May need to update follower orders (SL/TP moves) |
| `order` | `Cancelled` | Cancel corresponding follower orders |
| `position` | `Updated` | Verify sync, detect close (qty → 0) |
| `orderStrategy` | `Created` | Bracket order created — complex copy scenario |

## Fill Entity Fields
```json
{
  "id": 123456,          // unique fill ID
  "orderId": 789,        // parent order ID
  "orderStrategyId": null, // or integer if bracket
  "contractId": 1234,    // contract (use to get symbol)
  "timestamp": "...",    // fill time
  "action": "Buy",       // "Buy" or "Sell"
  "qty": 1,              // filled quantity
  "price": 21500.25,     // fill price
  "active": true,
  "finallyPaired": 0
}
```

---

# PART 5: OFFICIAL TYPESCRIPT REFERENCE (FROM partner.tradovate.com)

## This is the OFFICIAL code from Tradovate's partner documentation.
## Your Python implementation should match this protocol exactly.

### Message Handler (most important method)
```typescript
private handleMessage(data: WebSocket.Data): void {
    const rawMessage = data.toString();
    this.lastServerMessageTime = Date.now();

    // Handle 'o' frame
    if (rawMessage.length === 1) {
        if (rawMessage === 'o' && !this.authenticationSent) {
            // First 'o' frame → authenticate immediately
            this.authenticate();
            return;
        }
        if (rawMessage === 'o' && this.isAuthenticated) {
            this.sendHeartbeat();
            this.resetHeartbeatTimer();
        }
        return;
    }

    // Handle 'a[...]' responses
    if (rawMessage.startsWith('a[')) {
        const jsonPart = rawMessage.substring(1); // strip 'a'
        const messageArray: SocketMessage[] = JSON.parse(jsonPart);

        for (const msg of messageArray) {
            // Auth response (request ID 0)
            if (msg.i === 0 && !this.isAuthenticated) {
                if (msg.s === 200) {
                    this.isAuthenticated = true;
                    this.startHeartbeat();
                    // Send syncrequest ONCE
                    this.send('user/syncrequest', {
                        splitResponses: true,
                        entityTypes: ['order', 'fill', 'position', 'orderStrategy']
                    }, 1);
                } else {
                    console.error('Auth failed:', msg);
                    this.cleanup();
                }
            }
            // Props events (trade data)
            if (msg.e === 'props') {
                this.handlePropsEvent(msg.d);
            }
        }
        return;
    }
}
```

### Authentication
```typescript
private async authenticate(): Promise<void> {
    const accessToken = await this.tokenManager.getAccessToken();
    // Format: authorize\n{requestId}\n\n{accessToken}
    const authMessage = `authorize\n0\n\n${accessToken}`;
    this.ws.send(authMessage);
    this.authenticationSent = true;
}
```

### Send (generic endpoint caller via WebSocket)
```typescript
public send(endpoint: string, body?: any, requestId?: number): number {
    const reqId = requestId !== undefined ? requestId : this.requestIdCounter++;
    let message = `${endpoint}\n${reqId}\n\n`;
    if (body !== undefined) {
        message += typeof body === 'object' ? JSON.stringify(body) : body;
    }
    this.ws.send(message);
    return reqId;
}
```

### Heartbeat
```typescript
private sendHeartbeat(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('[]');
    }
}
// Called every 2500ms via setInterval after auth success
```

### Server Timeout Detection
```typescript
private checkServerTimeout(): void {
    const timeSinceLastMessage = Date.now() - this.lastServerMessageTime;
    if (timeSinceLastMessage > 10000) { // 10 seconds
        // Force close → triggers reconnection
        this.ws.close(4000, 'Server timeout');
    }
}
// Checked every 5000ms via setInterval
```

### Reconnection
```typescript
private calculateBackoffDelay(): number {
    const exponentialDelay = 1000 * Math.pow(2, this.reconnectAttempts);
    const cappedDelay = Math.min(exponentialDelay, 60000);
    const jitter = Math.random() * cappedDelay * 0.1;
    return Math.floor(cappedDelay + jitter);
}

private async handleReconnect(): Promise<void> {
    if (this.ws) {
        this.ws.removeAllListeners();
        if (this.ws.readyState === WebSocket.OPEN) {
            this.ws.close(1000, 'Reconnecting');
        }
        this.ws = null;
    }
    await this.tokenManager.getAccessToken(); // refresh if needed
    await this.connectWebSocket();
}
```

### Connection State Reset (on disconnect)
```typescript
private resetConnectionState(): void {
    this.isAuthenticated = false;
    this.authenticationSent = false;
    this.stopHeartbeat();
    this.lastServerMessageTime = Date.now();
}
```

---

# PART 6: PYTHON TRANSLATION FOR YOUR FLASK BACKEND

Your `ws_leader_monitor.py` uses Python `websockets` (asyncio). Here's how the protocol translates:

```python
import websockets
import json
import asyncio
import time

HEARTBEAT_INTERVAL = 2.5  # seconds
SERVER_TIMEOUT = 10.0      # seconds

class TradovateLeaderWS:
    def __init__(self, access_token, ws_url, on_trade_event):
        self.access_token = access_token
        self.ws_url = ws_url
        self.on_trade_event = on_trade_event
        self.ws = None
        self.authenticated = False
        self.auth_sent = False
        self.last_server_msg = time.time()
        self.request_id = 2  # 0=auth, 1=sync
        self.connected = False

    async def connect(self):
        """Main connection loop with reconnection."""
        while True:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    self.ws = ws
                    self.connected = True
                    self.authenticated = False
                    self.auth_sent = False
                    self.last_server_msg = time.time()

                    # Start heartbeat + timeout checker
                    hb_task = asyncio.create_task(self._heartbeat_loop())
                    timeout_task = asyncio.create_task(self._timeout_checker())

                    try:
                        async for message in ws:
                            await self._handle_message(message)
                    finally:
                        hb_task.cancel()
                        timeout_task.cancel()
                        self.connected = False

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.connected = False
                await asyncio.sleep(5)  # reconnect delay

    async def _handle_message(self, raw):
        """Parse Tradovate's custom wire protocol."""
        self.last_server_msg = time.time()

        # Server open frame
        if raw == 'o':
            if not self.auth_sent:
                auth_msg = f"authorize\n0\n\n{self.access_token}"
                await self.ws.send(auth_msg)
                self.auth_sent = True
            return

        # Array response
        if raw.startswith('a['):
            data = json.loads(raw[1:])  # strip 'a' prefix
            for item in data:
                # Auth response (requestId 0)
                if item.get('i') == 0 and not self.authenticated:
                    if item.get('s') == 200:
                        self.authenticated = True
                        # Send syncrequest ONCE
                        sync_body = json.dumps({
                            "splitResponses": True,
                            "entityTypes": ["order", "fill", "position", "orderStrategy"]
                        })
                        await self.ws.send(f"user/syncrequest\n1\n\n{sync_body}")
                    else:
                        raise Exception(f"Auth failed: {item}")

                # Props events (trade data)
                if item.get('e') == 'props':
                    d = item.get('d', {})
                    entity_type = d.get('entityType', '')
                    event_type = d.get('eventType', '')
                    entity = d.get('entity', {})

                    if entity_type == 'fill' and event_type == 'Created':
                        await self.on_trade_event('fill', entity)
                    elif entity_type == 'position' and event_type == 'Updated':
                        await self.on_trade_event('position', entity)
                    elif entity_type == 'order':
                        await self.on_trade_event('order', entity)

    async def _heartbeat_loop(self):
        """Send [] every 2.5 seconds."""
        while True:
            try:
                if self.ws and self.authenticated:
                    await self.ws.send('[]')
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            except Exception:
                break

    async def _timeout_checker(self):
        """Check for dead connection every 5 seconds."""
        while True:
            await asyncio.sleep(5)
            if time.time() - self.last_server_msg > SERVER_TIMEOUT:
                logger.error("Server timeout — closing connection")
                if self.ws:
                    await self.ws.close(4000, 'Server timeout')
                break

    async def close(self):
        if self.ws:
            await self.ws.close()
```

---

# PART 7: LOOP PREVENTION (CRITICAL)

## The Problem
Your system places order on follower account A via REST.
If user/syncrequest is also monitoring account A → sees your order as new event → copies again → infinite loop.

## Solution: clOrdId Prefix Tag
```python
COPY_ORDER_PREFIX = "JT_COPY_"

# PLACING follower orders: always tag
import uuid
cl_ord_id = f"JT_COPY_{uuid.uuid4().hex[:12]}"

# RECEIVING events: always check
def on_fill_event(fill_entity):
    # Need to look up the parent order's clOrdId
    order_id = fill_entity.get('orderId')
    # Fetch order details if needed
    order = get_order(order_id)
    if order and order.get('clOrdId', '').startswith('JT_COPY_'):
        return  # This is OUR order — skip
    # Else: this is a real user trade — copy it
```

## Additional Safety
- Maintain time-windowed set (60s) of order IDs placed by system
- Add order ID to set BEFORE placing order (WS event can arrive before REST response)
- Enforce: account can be leader OR follower, NEVER both
- Account-role enforcement at DB level with CHECK constraint

---

# PART 8: P-TICKET RATE LIMITING

When you hit Tradovate's rate limit:
```json
{"i": 5, "s": 200, "d": {"p-ticket": "abc123", "p-time": 5}}
```

**Handle it:**
1. Wait `p-time` seconds
2. Resend original request with `"p-ticket": "abc123"` in body
3. If `p-captcha` received → LOCKED OUT 1 HOUR → stop all requests

**For copy trading:** 20 followers = 20 REST calls. Space them if needed.

---

# PART 9: 4PM CT REPLAY WARNING

At daily session end (~4PM CT), Tradovate replays ALL session events through WebSocket.
**If not filtered, your system will re-execute the entire day's trades.**

## Detection strategies:
1. Track which fills you've already processed (fill ID set)
2. Check fill timestamp — ignore fills older than connection start time
3. After initial syncrequest, the first batch of events is the "replay" — mark them as historical
4. Use `splitResponses: true` to separate initial state dump from live events

---

# PART 10: TRADOVATE REST API — PLACING FOLLOWER ORDERS

## Place Market Order (for follower accounts)
```
POST https://live.tradovateapi.com/v1/order/placeorder
Authorization: Bearer {accessToken}
Content-Type: application/json

{
  "accountSpec": "DEMO12345",
  "accountId": 67890,
  "clOrdId": "JT_COPY_abc123def456",
  "action": "Buy",
  "symbol": "NQH5",
  "orderQty": 1,
  "orderType": "Market",
  "timeInForce": "GTC",
  "isAutomated": true
}
```

## Liquidate Position (for close propagation)
```
POST https://live.tradovateapi.com/v1/order/liquidateposition
Authorization: Bearer {accessToken}
Content-Type: application/json

{
  "accountId": 67890,
  "contractId": 1234,
  "admin": false
}
```

## Get Positions (verify sync)
```
GET https://live.tradovateapi.com/v1/position/list
Authorization: Bearer {accessToken}
```

## Find Contract by Symbol
```
GET https://live.tradovateapi.com/v1/contract/find?name=NQH5
Authorization: Bearer {accessToken}
```

---

# PART 11: WHAT'S BROKEN IN YOUR CURRENT IMPLEMENTATION

Based on the CLI session report, these were the 3 gaps fixed:

1. **PLATFORM_URL was `localhost:5000`** → Fixed to `127.0.0.1:{PORT}`
2. **Manual trade didn't propagate** → Added `_propagate_manual_trade_to_followers()`  
3. **Auto-mode toggle didn't reload** → Added `threading.Event` reload signal

## But "still not working" suggests deeper issues. Check these:

### Most Likely Failures (in order of probability)
1. **WebSocket never connects** — wrong URL, wrong auth format, or auth token expired
   - Check: Railway logs for "WebSocket connection established" or "Auth failed"
   - Common: Using old `wss://demo.tradovateapi.com` when account is live
   
2. **Auth works but syncrequest fails** — sent before auth confirmed, or sent twice
   - Check: "user/syncrequest" should only be sent AFTER `{"i":0,"s":200}` response
   - Common: Sending syncrequest on `onopen` instead of after auth success

3. **Events received but not parsed** — wrong message format parsing
   - Check: Are you stripping the `a` prefix before JSON.parse?
   - Common: Trying to parse `a[{"e":"props",...}]` as direct JSON (fails)

4. **Fill events received but trade not placed** — loop prevention too aggressive
   - Check: Is cl_ord_id check blocking legitimate fills?
   - Common: If you can't look up the parent order's clOrdId, you might be blocking everything

5. **Follower trade attempted but auth fails** — using leader's token for follower account
   - Check: Each Tradovate account needs its own access token
   - This is how Tradesyncer does it — separate API keys per connection

6. **Session/cookie issue** — `_propagate_manual_trade_to_followers` POSTs to `/api/manual-trade` but the internal request may not have a valid session
   - Check: Does your manual-trade endpoint require Flask session auth?
   - The internal loopback call won't have session cookies
   - Fix: Add an internal auth bypass for requests with `JT_COPY_` prefix

### CRITICAL CHECK: Does `/api/manual-trade` require session auth?
If YES → the propagation helper's HTTP POST will fail with 401 because the daemon thread doesn't have a Flask session. This would explain "still not working" — the leader trade succeeds (has session from browser), but follower copies fail silently because the internal POST has no session.

**Fix:** Either:
a) Pass a service token in the internal request header
b) Exempt `JT_COPY_` requests from session auth
c) Call the trade execution function directly instead of POSTing to the HTTP endpoint

---

# PART 12: CONFORMANCE TESTING REQUIREMENTS

Tradovate requires these for partner API access (you need to pass these):

### Stage 2: WebSocket Management
- ✅ WebSocket connects and authenticates
- ✅ Auth fails properly with invalid token
- ✅ Heartbeats sent every 2.5s
- ✅ Only ONE syncrequest per socket lifecycle
- ✅ Events processed with idempotency
- ✅ P-Ticket rate limiting handled
- ✅ Auto-reconnection after disconnect
- ✅ Re-auth after reconnection
- ✅ State recovery after reconnection

### Key Conformance Rules
1. **ONE syncrequest per socket** — sending multiple = violation
2. **Heartbeat timing** — must be ~2.5s, not faster
3. **Idempotency** — processing same event twice must not duplicate orders
4. **Error handling** — must not crash on malformed data

---

# PART 13: CONTRACT MAPPING (FOR CROSS-ORDER FEATURE)

Tradesyncer supports copying between different contract sizes:

| Leader Contract | Follower Contract | Ratio |
|----------------|-------------------|-------|
| NQ (full) | MNQ (micro) | 1 NQ = 10 MNQ |
| ES (full) | MES (micro) | 1 ES = 10 MES |
| YM (full) | MYM (micro) | 1 YM = 10 MYM |
| RTY (full) | M2K (micro) | 1 RTY = 10 M2K |

Implementation: Store a `contract_map` table:
```sql
CREATE TABLE contract_mapping (
    id SERIAL PRIMARY KEY,
    source_symbol VARCHAR(20) NOT NULL,
    target_symbol VARCHAR(20) NOT NULL,
    qty_multiplier REAL DEFAULT 10.0
);
-- Example: NQ → MNQ with 10x multiplier
INSERT INTO contract_mapping VALUES (1, 'NQ', 'MNQ', 10.0);
```

When copying: 
```python
if cross_order_enabled:
    mapped = get_contract_mapping(leader_symbol)
    if mapped:
        follower_symbol = mapped.target_symbol
        follower_qty = leader_qty * mapped.qty_multiplier * follower_multiplier
```

---

# SUMMARY: WHAT TO TELL CLI

"Read TRADESYNCER_PARITY_REFERENCE.md. The Pro Copy Trader WebSocket leader monitoring is not working. Use the official Tradovate protocol from this doc to verify and fix ws_leader_monitor.py. Key things to check:

1. Is the WebSocket connection following the EXACT protocol? (wait for 'o', then auth, then syncrequest)
2. Is the 'a[' prefix being stripped before JSON parsing?
3. Is the syncrequest only sent ONCE after auth success?
4. Is heartbeat sending '[]' every 2.5 seconds?
5. CRITICAL: Does the internal POST to /api/manual-trade for follower propagation have valid auth? (Flask session issue)
6. Check Railway logs for any error messages from the WebSocket monitor.

The reference TypeScript code from Tradovate's official partner docs is in this file — match the Python implementation to it exactly."
