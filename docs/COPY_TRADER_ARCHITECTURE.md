# COPY TRADER ARCHITECTURE — Reference for Claude Code CLI

> **For**: Claude Code CLI agent working on `just-trades-platform`
> **Author**: Myles Jadwin (CEO, Just Trades Group) + Claude research
> **Date**: February 2026
> **Priority**: CRITICAL — this is the #1 product feature
> **Location**: Place in `docs/COPY_TRADER_ARCHITECTURE.md`

---

## 0. READ THIS FIRST — THE CORE RULE

**DO NOT use HTTP self-POST to copy trades to followers.**

The previous implementation tried to have the server POST to its own `/api/manual-trade` endpoint for each follower. This fails because:
- The internal request has no Flask session → 401 "Authentication required"
- Adding admin keys is a bandaid that introduces more failure modes
- It's architecturally wrong — Tradesyncer doesn't do this

**Instead: call the broker execution functions DIRECTLY in Python.**

Your server already has `_execute_projectx_trade()` and the Tradovate REST API order placement code as internal functions. The propagation function should import and call those directly — no HTTP, no auth gate, no session, no loopback.

```
WRONG (current):
  propagation thread → HTTP POST to own /api/manual-trade → auth gate → 401 ❌

RIGHT (Tradesyncer pattern):
  propagation thread → call _execute_projectx_trade() directly → broker API → ✅
  propagation thread → call tradovate_place_order() directly → broker API → ✅
```

---

## 1. TARGET ARCHITECTURE (MATCH TRADESYNCER)

### High-Level Data Flow
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
│  │  2. For each enabled follower:                             │  │
│  │     a. Calculate qty: leader_qty × multiplier              │  │
│  │     b. Map contract if cross-order (NQ → MNQ)              │  │
│  │     c. Get follower's broker credentials from DB           │  │
│  │     d. DIRECT CALL to broker execution function:           │  │
│  │        - ProjectX: _execute_projectx_trade(...)            │  │
│  │        - Tradovate: _place_tradovate_order(...)            │  │
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
| Manual Trade | User clicks BUY/SELL in copy trader UI | After leader trade succeeds, call `copy_to_followers()` in same thread or daemon thread |
| Auto-Copy | `ws_leader_monitor.py` detects fill via WebSocket | On fill event, call `copy_to_followers()` from the async handler |

Both paths call the **same** `copy_to_followers()` function. This function does NOT make HTTP requests to the Just Trades server. It calls broker APIs directly.

---

## 2. COPY ENGINE — THE FUNCTION TO BUILD

```python
def copy_to_followers(leader_id, symbol, side, quantity, risk_settings=None):
    """
    Copy a trade from leader to all enabled followers.
    
    Called by:
      1. Manual trade handler (after leader trade succeeds)
      2. WebSocket leader monitor (on fill event)
    
    This function calls broker execution functions DIRECTLY.
    It does NOT HTTP POST to the server's own endpoints.
    """
    from copy_trader_models import get_followers_for_leader, log_copy_trade
    import time
    import uuid
    
    logger.info(f"Copy engine: {side} {quantity} {symbol} from leader {leader_id}")
    
    followers = get_followers_for_leader(leader_id)
    if not followers:
        logger.info(f"Copy engine: leader {leader_id} has no enabled followers")
        return
    
    for follower in followers:
        start_ms = time.time() * 1000
        cl_ord_id = f"JT_COPY_{uuid.uuid4().hex[:12]}"
        
        try:
            # Calculate follower quantity
            multiplier = follower.get('multiplier', 1.0)
            follower_qty = max(1, int(round(quantity * multiplier)))
            
            # Map symbol if cross-order enabled
            follower_symbol = symbol  # TODO: contract mapping table
            
            # Get follower's broker type and credentials
            # follower dict should contain: account_id, subaccount_id, broker_type
            broker_type = follower.get('broker_type', 'projectx')
            
            if side.lower() == 'close':
                result = _close_follower_position(follower, follower_symbol, cl_ord_id)
            elif broker_type == 'projectx':
                result = _execute_projectx_copy(follower, follower_symbol, side, follower_qty, cl_ord_id)
            elif broker_type == 'tradovate':
                result = _execute_tradovate_copy(follower, follower_symbol, side, follower_qty, cl_ord_id)
            else:
                result = {'success': False, 'error': f'Unknown broker: {broker_type}'}
            
            latency_ms = int(time.time() * 1000 - start_ms)
            status = 'success' if result.get('success') else 'error'
            
            log_copy_trade(
                leader_id=leader_id,
                follower_id=follower['id'],
                symbol=follower_symbol,
                side=side,
                quantity=follower_qty,
                status=status,
                error_message=result.get('error', '') if status == 'error' else None,
                latency_ms=latency_ms,
                cl_ord_id=cl_ord_id
            )
            
            logger.info(f"Copy engine: follower {follower['id']} → {status} ({latency_ms}ms)")
            
        except Exception as e:
            latency_ms = int(time.time() * 1000 - start_ms)
            logger.error(f"Copy engine: follower {follower['id']} exception: {e}")
            log_copy_trade(
                leader_id=leader_id,
                follower_id=follower['id'],
                symbol=symbol,
                side=side,
                quantity=quantity,
                status='error',
                error_message=str(e)[:500],
                latency_ms=latency_ms,
                cl_ord_id=cl_ord_id
            )


def _execute_projectx_copy(follower, symbol, side, qty, cl_ord_id):
    """
    Place a trade on a ProjectX follower account.
    Calls the SAME internal function used by manual trading.
    Does NOT HTTP POST to /api/manual-trade.
    """
    # Get the follower's ProjectX auth token
    account_id = follower['account_id']
    subaccount_id = follower['subaccount_id']
    
    # Look up the user's ProjectX token from the accounts table
    # This needs the follower user's stored credentials
    token = _get_projectx_token_for_account(account_id)
    
    if not token:
        return {'success': False, 'error': 'No ProjectX token for follower account'}
    
    # Use the existing ProjectX trade execution logic
    # Map side to ProjectX format
    px_side = 'Buy' if side.lower() == 'buy' else 'Sell'
    
    # Call ProjectX Gateway API directly
    import requests
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    payload = {
        'accountId': int(subaccount_id),
        'contractId': _resolve_projectx_contract(symbol),
        'type': 2,  # Market order
        'side': 0 if px_side == 'Buy' else 1,
        'size': qty,
        'clOrdId': cl_ord_id
    }
    
    resp = requests.post(
        'https://gateway.projectx.com/api/Order/place',
        headers=headers,
        json=payload,
        timeout=30
    )
    
    if resp.status_code == 200:
        data = resp.json()
        return {'success': True, 'order_id': data.get('orderId')}
    else:
        return {'success': False, 'error': f'ProjectX {resp.status_code}: {resp.text[:200]}'}


def _execute_tradovate_copy(follower, symbol, side, qty, cl_ord_id):
    """
    Place a trade on a Tradovate follower account.
    Calls the Tradovate REST API directly.
    Does NOT HTTP POST to /api/manual-trade.
    """
    account_id = follower['account_id']
    subaccount_id = follower['subaccount_id']
    
    # Get Tradovate access token for this account
    token = _get_tradovate_token_for_account(account_id)
    
    if not token:
        return {'success': False, 'error': 'No Tradovate token for follower account'}
    
    import requests
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Determine API URL (live vs demo)
    base_url = _get_tradovate_base_url(account_id)  # live or demo
    
    payload = {
        'accountId': int(subaccount_id),
        'action': 'Buy' if side.lower() == 'buy' else 'Sell',
        'symbol': symbol,
        'orderQty': qty,
        'orderType': 'Market',
        'timeInForce': 'GTC',
        'isAutomated': True,
        'clOrdId': cl_ord_id
    }
    
    resp = requests.post(
        f'{base_url}/order/placeorder',
        headers=headers,
        json=payload,
        timeout=30
    )
    
    if resp.status_code == 200:
        data = resp.json()
        return {'success': True, 'order_id': data.get('orderId')}
    else:
        return {'success': False, 'error': f'Tradovate {resp.status_code}: {resp.text[:200]}'}


def _close_follower_position(follower, symbol, cl_ord_id):
    """Close/flatten a position on a follower account."""
    broker_type = follower.get('broker_type', 'projectx')
    
    if broker_type == 'projectx':
        token = _get_projectx_token_for_account(follower['account_id'])
        if not token:
            return {'success': False, 'error': 'No ProjectX token'}
        
        import requests
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        payload = {
            'accountId': int(follower['subaccount_id']),
            'contractId': _resolve_projectx_contract(symbol),
            'clOrdId': cl_ord_id
        }
        resp = requests.post(
            'https://gateway.projectx.com/api/Order/closecontractposition',
            headers=headers, json=payload, timeout=30
        )
        return {'success': resp.status_code == 200, 'error': resp.text[:200] if resp.status_code != 200 else None}
    
    elif broker_type == 'tradovate':
        token = _get_tradovate_token_for_account(follower['account_id'])
        if not token:
            return {'success': False, 'error': 'No Tradovate token'}
        
        import requests
        base_url = _get_tradovate_base_url(follower['account_id'])
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        
        # Find contractId for symbol
        contract_resp = requests.get(f'{base_url}/contract/find?name={symbol}', headers=headers, timeout=10)
        if contract_resp.status_code != 200:
            return {'success': False, 'error': f'Contract lookup failed: {contract_resp.text[:200]}'}
        
        contract_id = contract_resp.json().get('id')
        payload = {
            'accountId': int(follower['subaccount_id']),
            'contractId': contract_id,
            'admin': False
        }
        resp = requests.post(f'{base_url}/order/liquidateposition', headers=headers, json=payload, timeout=30)
        return {'success': resp.status_code == 200, 'error': resp.text[:200] if resp.status_code != 200 else None}
```

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

### MVP (Phase 1 — get this working first)
- [ ] Connect broker accounts (Tradovate + ProjectX via API keys)
- [ ] Designate ONE lead account per user
- [ ] Auto-copy leader fills to followers via WebSocket monitor
- [ ] Manual trade on leader propagates to followers
- [ ] Quantity multiplier per follower (ratio copy)
- [ ] Enable/disable per follower
- [ ] Close propagation (leader closes → all followers close)
- [ ] Copy log with status (success/error), latency, error message
- [ ] Loop prevention (JT_COPY_ clOrdId prefix)
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

---

## 6. CONTRACT MAPPING TABLE (FOR CROSS-ORDER)

| Full Contract | Micro Contract | Multiplier |
|--------------|----------------|------------|
| NQ | MNQ | 10× |
| ES | MES | 10× |
| YM | MYM | 10× |
| RTY | M2K | 10× |
| GC | MGC | 10× |
| CL | MCL | 10× |

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

### Existing Tables (already in copy_trader_models.py)

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
    created_at TIMESTAMP DEFAULT NOW()
);

-- Copy trade log
CREATE TABLE copy_trade_log (
    id SERIAL PRIMARY KEY,
    leader_id INTEGER,
    follower_id INTEGER,
    symbol TEXT,
    side TEXT,
    quantity INTEGER,
    status TEXT,          -- 'success' or 'error'
    error_message TEXT,
    latency_ms INTEGER,
    cl_ord_id TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Schema Additions Needed

```sql
-- Add broker_type to follower_accounts (know which API to call)
ALTER TABLE follower_accounts ADD COLUMN broker_type TEXT DEFAULT 'projectx';

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

## 8. HELPER FUNCTIONS NEEDED

These functions need to exist or be created:

```python
def _get_projectx_token_for_account(account_id):
    """Look up the stored ProjectX JWT for a given account.
    The accounts table stores tokens from login.
    Return the token string or None."""
    pass

def _get_tradovate_token_for_account(account_id):
    """Look up the stored Tradovate access token for a given account.
    May need to refresh if expired (90-min lifetime).
    Return the token string or None."""
    pass

def _get_tradovate_base_url(account_id):
    """Return 'https://live.tradovateapi.com/v1' or 
    'https://demo.tradovateapi.com/v1' based on account type."""
    pass

def _resolve_projectx_contract(symbol):
    """Convert symbol like 'MNQH6' to ProjectX contract ID 
    like 'CON.F.US.ENQ.M25'. Use contract/available endpoint."""
    pass
```

---

## 9. WHAT THE CLI SHOULD DO

1. **Create `copy_engine.py`** — new file with `copy_to_followers()` and the broker-specific execution functions. This is the central copy engine.

2. **Modify `ultra_simple_server.py`** — replace `_propagate_manual_trade_to_followers()` to call `copy_to_followers()` directly instead of HTTP POST.

3. **Modify `ws_leader_monitor.py`** — on fill events, call `copy_to_followers()` instead of HTTP POST to `/api/manual-trade`.

4. **Add `broker_type` column** to `follower_accounts` table so the copy engine knows which API to call.

5. **Implement token lookup functions** — `_get_projectx_token_for_account()` and `_get_tradovate_token_for_account()` need to query the accounts/credentials tables.

6. **Test with one leader + one ProjectX follower first** — simplest case, validate the direct-call pattern works before scaling.

---

## 10. COMMON PITFALLS

| Pitfall | Consequence | Prevention |
|---------|-------------|------------|
| HTTP self-POST for copies | 401 auth failure | Direct function call (Section 0) |
| No loop prevention | Infinite copy loop | JT_COPY_ prefix check (Section 3) |
| 4PM CT replay | Re-executes entire day | Fill ID dedup set (Section 4) |
| Token expiry (90min) | WebSocket silently dies | Token refresh timer (Section 4) |
| currentLeaderId null on page load | Propagation skips | Load leader from DB on init |
| Follower is also a leader | Cross-copy loop | DB constraint: exclusive roles |
| Rate limit (p-ticket) | Orders rejected | Queue with backoff (Section 4) |
| Wrong contract for follower | Trade wrong instrument | Contract mapping table (Section 6) |
