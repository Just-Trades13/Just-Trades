# Tradovate API Reference -- Just Trades Platform

> **This is the authoritative reference for Tradovate API integration.**
> Built from production-verified source code + official docs + community findings.
> Last verified: Feb 18, 2026

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Base URLs](#2-base-urls)
3. [Rate Limits](#3-rate-limits)
4. [Order Types and Placement](#4-order-types-and-placement)
5. [Bracket Orders / Order Strategies](#5-bracket-orders--order-strategies)
6. [Position Management](#6-position-management)
7. [Order Management](#7-order-management)
8. [Account Management](#8-account-management)
9. [Contract / Product Lookup](#9-contract--product-lookup)
10. [WebSocket API](#10-websocket-api)
11. [Error Codes and Handling](#11-error-codes-and-handling)
12. [Important Gotchas](#12-important-gotchas)
13. [Tick Size Reference Table](#13-tick-size-reference-table)
14. [Quick Reference: Python Examples](#14-quick-reference-python-examples)
15. [Sources](#15-sources)

---

## 1. Authentication

Tradovate supports two authentication methods: **Credentials Auth** (username/password + API keys) and **OAuth** (three-step redirect flow). Our system uses Credentials Auth.

### 1.1 Credentials Authentication (`/auth/accesstokenrequest`)

This is the primary method for automated systems. POST to the access token endpoint with your credentials.

**Endpoint:** `POST {base_url}/auth/accesstokenrequest`

**Request Body (with Client ID/Secret):**

```json
{
    "name": "your_username",
    "password": "your_password",
    "appId": "Just.Trade",
    "appVersion": "1.0.0",
    "cid": "your_client_id",
    "sec": "your_client_secret"
}
```

**Alternative (without Client ID/Secret -- uses deviceId):**

```json
{
    "name": "your_username",
    "password": "your_password",
    "appId": "YourAppName",
    "appVersion": "1.0.0",
    "deviceId": "a-unique-uuid-string"
}
```

**Required Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Tradovate username |
| `password` | string | Tradovate password |
| `appId` | string | Your registered application ID |
| `appVersion` | string | Application version string |
| `cid` | string | Client ID (from API key registration) -- OR use `deviceId` |
| `sec` | string | Client secret (from API key registration) -- OR use `deviceId` |
| `deviceId` | string | UUID device identifier (alternative to cid/sec) |

**Successful Response (HTTP 200):**

```json
{
    "accessToken": "eyJhbGciOiJ...",
    "mdAccessToken": "...",
    "refreshToken": "...",
    "expirationTime": "2026-02-18T12:00:00Z",
    "expiresIn": 5400,
    "userId": 12345,
    "name": "your_username"
}
```

**Failed Response (HTTP 200 with error -- Tradovate returns 200 even on auth failure!):**

```json
{
    "errorText": "Invalid credentials",
    "errorCode": "InvalidCredentials"
}
```

**IMPORTANT:** Always check for `errorText` in the response body, even on HTTP 200. Tradovate commonly returns errors inside a 200 response.

**Key Auth Fields:**
- `accessToken` -- Use this for ALL API requests (orders, positions, accounts)
- `mdAccessToken` -- For market data WebSocket ONLY. Ignore for order operations.
- `expiresIn` -- Token lifespan in seconds (typically 5400 = 90 minutes)

### 1.2 Token Renewal (`/auth/renewAccessToken`)

Access tokens expire after approximately **90 minutes** (5400 seconds). Renew before expiration.

**Endpoint:** `POST {base_url}/auth/renewAccessToken`

**Headers:**
```
Authorization: Bearer <current_access_token>
Content-Type: application/json
```

**Request Body:** Empty (no body required). The current access token in the Authorization header is all that's needed.

**Response:**
```json
{
    "accessToken": "eyJhbGciOiJ..._new_token",
    "expiresIn": 5400
}
```

**Best practice:** Renew the token approximately 10-15 minutes before expiration. If renewal returns 401, the token has already expired and you must re-authenticate with full credentials.

**Our implementation:** `_ensure_valid_token()` checks expiry before every request. On 401, the system attempts one refresh + retry cycle before failing.

### 1.3 OAuth Flow (Three-Step)

OAuth is for third-party applications requesting user authorization:

1. **Redirect user** to Tradovate's OAuth URL with your `client_id` and `redirect_uri`
2. **User authorizes** the app and is redirected back with a single-use `code` parameter
3. **Exchange code for token** via `POST /auth/oauthtoken`

OAuth token exchange endpoint (live): `https://live-api-d.tradovate.com/auth/oauthtoken`

### 1.4 Using the Access Token

All authenticated requests must include the token as a Bearer token:

```
Authorization: Bearer eyJhbGciOiJ...your_access_token
Content-Type: application/json
```

### 1.5 Key Auth Gotchas

- **Demo and Live use DIFFERENT tokens** -- you cannot use a demo token on live endpoints, or vice versa
- Token refresh can fail if the original credentials are invalid or the token is already expired
- `mdAccessToken` is for market data WebSocket ONLY -- use `accessToken` for everything else
- Our code tries live endpoint first, then falls back to demo if live fails

---

## 2. Base URLs

### REST API

| Environment | Base URL |
|-------------|----------|
| **Live** | `https://live.tradovateapi.com/v1` |
| **Demo** | `https://demo.tradovateapi.com/v1` |

### WebSocket API

| Environment | URL |
|-------------|-----|
| **Live** | `wss://live.tradovateapi.com/v1/websocket` |
| **Demo** | `wss://demo.tradovateapi.com/v1/websocket` |

### Market Data WebSocket

| Environment | URL |
|-------------|-----|
| **Live** | `wss://md.tradovateapi.com/v1/websocket` |
| **Demo** | `wss://md-demo.tradovateapi.com/v1/websocket` |

**CRITICAL:** Demo positions and orders exist ONLY on the demo API. Live positions exist ONLY on the live API. Do NOT make cross-environment calls -- they will return empty results or 401/403 errors.

**IMPORTANT:** Our system uses REST exclusively for all order operations. WebSocket pool exists in code but was NEVER functional for order placement (Rule 10).

---

## 3. Rate Limits

### 3.1 Limits

| Scope | Limit | Notes |
|-------|-------|-------|
| **Per hour** | 5,000 requests (rolling 60-minute window) | Official documented limit |
| **Per minute** | ~80 requests (derived from hourly) | Practical working limit |
| **Per second** | Undocumented but enforced | Burst protection |
| **Concurrent connections** | 1 (standard), 2 (Dual Connections subscription) | HTTP 408 if exceeded |

### 3.2 What Counts as a Request

Every API action counts toward the limit:
- Placing an order = 1 request
- Modifying an order = 1 request
- Cancelling an order = 1 request
- Querying positions = 1 request
- Querying orders = 1 request
- Each reconnection attempt consumes a `user/syncRequest`
- Token renewal = 1 request

### 3.3 Rate Limit Scope: Per Token AND Per IP

Rate limits apply at multiple levels:
- **Per access token**: All accounts sharing the same OAuth/credentials token share ONE rate limit. If you have 7 subaccounts on the same token, 7 simultaneous order placements = 7 requests against the same quota.
- **Per IP address**: Multiple computers or services on the same IP share the same IP-based rate limit.

**This is the single most important rate limit fact for multi-account systems (Rule 16).** JADVIX with 7 accounts = 7x API calls against the same 80/min quota. Adding "just one extra broker query per account" multiplies by the number of accounts.

### 3.4 When You Exceed the Limit

1. **First offense:** Server responds with `429 Too Many Requests`. Requests are blocked for approximately 20-30 seconds.
2. **Repeated violations:** Tradovate issues a **P-ticket (penalty ticket)**, resulting in severely reduced or completely blocked API access for an extended period.
3. **Excessive reconnections:** Rapidly connecting/disconnecting triggers rate limits via `usersync` requests.

### 3.5 Our Rate Limit Handling

On HTTP 429, our code retries with exponential backoff:
```
Retry 1: wait 1s
Retry 2: wait 2s
Retry 3: wait 4s
Retry 4: wait 8s
Retry 5: wait 16s (give up after this)
```

### 3.6 Best Practices

- Use market orders when possible (execute instantly, minimal API overhead)
- Minimize order modifications -- each modify is a separate request
- Batch position/order queries where possible (use `/order/list` instead of individual `/order/item` calls)
- Maintain stable connections -- avoid frequent login/logout cycles
- Before adding ANY new broker API call, count how many times it will execute per signal across ALL accounts
- Use "Market Execution Only" mode where possible to reduce broker-side processing

---

## 4. Order Types and Placement

### 4.1 Place Order Endpoint

**Endpoint:** `POST {base_url}/order/placeorder`

All individual order types use this single endpoint. The `orderType` field determines behavior.

### 4.2 Market Order

Executes immediately at the best available price.

```json
{
    "accountId": 12345,
    "accountSpec": "DEMO12345",
    "action": "Buy",
    "symbol": "NQH6",
    "orderQty": 1,
    "orderType": "Market",
    "timeInForce": "Day",
    "isAutomated": true
}
```

### 4.3 Limit Order

Rests at a specific price until filled or cancelled.

```json
{
    "accountId": 12345,
    "accountSpec": "DEMO12345",
    "action": "Sell",
    "symbol": "NQH6",
    "orderQty": 1,
    "orderType": "Limit",
    "price": 22200.00,
    "timeInForce": "GTC",
    "isAutomated": true
}
```

**Note:** `price` MUST be on a valid tick boundary for the instrument.

### 4.4 Stop Order

Triggers a market order when price reaches the stop level.

```json
{
    "accountId": 12345,
    "accountSpec": "DEMO12345",
    "action": "Sell",
    "symbol": "NQH6",
    "orderQty": 1,
    "orderType": "Stop",
    "stopPrice": 22100.00,
    "timeInForce": "GTC",
    "isAutomated": true
}
```

### 4.5 Stop Limit Order

Triggers a limit order when price reaches the stop level. Contains two price components.

```json
{
    "accountId": 12345,
    "accountSpec": "DEMO12345",
    "action": "Sell",
    "symbol": "NQH6",
    "orderQty": 1,
    "orderType": "StopLimit",
    "stopPrice": 22000.00,
    "price": 21995.00,
    "timeInForce": "GTC",
    "isAutomated": true
}
```

- `stopPrice` -- trigger price (when hit, limit order is placed)
- `price` -- the limit price for the resulting order

### 4.6 Trailing Stop Order

Stop price trails the market price by a fixed offset.

```json
{
    "accountId": 12345,
    "accountSpec": "DEMO12345",
    "action": "Sell",
    "symbol": "NQH6",
    "orderQty": 1,
    "orderType": "TrailingStop",
    "stopPrice": 22000.00,
    "pegDifference": 10.0,
    "timeInForce": "GTC",
    "isAutomated": true
}
```

| Field | Description |
|-------|-------------|
| `pegDifference` | Trail offset in **price points** (not ticks) |
| `stopPrice` | Initial stop price (required by Tradovate) |

### 4.7 Common Fields Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `accountSpec` | string | Yes | Account name (from `/account/list` `name` field) |
| `accountId` | integer | Yes | Account entity ID (from `/account/list` `id` field) |
| `action` | string | Yes | `"Buy"` or `"Sell"` |
| `symbol` | string | Yes | Contract symbol (e.g., `"NQH6"`, `"MGCJ6"`) |
| `orderQty` | integer | Yes | Number of contracts |
| `orderType` | string | Yes | `"Market"`, `"Limit"`, `"Stop"`, `"StopLimit"`, `"TrailingStop"` |
| `price` | float | Limit/StopLimit | Limit price (must be on tick boundary) |
| `stopPrice` | float | Stop/StopLimit/TrailingStop | Stop trigger price |
| `pegDifference` | float | TrailingStop | Trail offset in price points |
| `timeInForce` | string | Yes | `"Day"`, `"GTC"` (Good Til Cancel), `"GTD"` (Good Til Date) |
| `isAutomated` | boolean | Recommended | `true` for API-placed orders. Must be boolean, not string. |
| `clOrdId` | string | Optional | Client order ID for tagging/reconciliation |
| `expireTime` | string | GTD only | Expiration timestamp for GTD orders |

### 4.8 Successful placeOrder Response

```json
{
    "orderId": 789456123,
    "accountId": 12345,
    "contractId": 2345678,
    "timestamp": "2026-02-18T10:30:00.000Z",
    "action": "Buy",
    "ordStatus": "Working",
    "orderType": "Limit",
    "price": 22200.00,
    "orderQty": 1,
    "filledQty": 0,
    "avgFillPrice": 0
}
```

Key response fields:
- `orderId` -- unique order identifier (use for cancel/modify operations)
- `ordStatus` -- `"Working"`, `"Filled"`, `"Cancelled"`, `"Rejected"`, `"Expired"`, `"Suspended"`
- `filledQty` -- number of contracts filled so far
- `avgFillPrice` -- average fill price (populated after fill)
- `failureText` / `errorText` -- present if the order was rejected

### 4.9 Error Response (HTTP 200 with error)

```json
{
    "failureText": "Insufficient margin",
    "details": "..."
}
```

---

## 5. Bracket Orders / Order Strategies

Bracket orders combine an entry order with exit orders (take-profit and stop-loss) in a single API call. This is the most complex and most important endpoint for automated trading.

### 5.1 Start Order Strategy Endpoint

**Endpoint:** `POST {base_url}/orderStrategy/startOrderStrategy`

This creates a complete bracket order: entry + TP + SL in one atomic call. Tradovate manages the OCO relationship between exit legs automatically (when TP fills, SL is cancelled and vice versa).

### 5.2 orderStrategyTypeId Values

| ID | Type | Description |
|----|------|-------------|
| **2** | Bracket | The built-in bracket strategy. This is currently the **only supported** order strategy type. |

### 5.3 Single-Bracket Payload (1 TP + 1 SL)

```json
{
    "accountId": 12345,
    "accountSpec": "DEMO12345",
    "symbol": "MNQH6",
    "orderStrategyTypeId": 2,
    "action": "Buy",
    "params": "{\"entryVersion\":{\"orderQty\":3,\"orderType\":\"Market\",\"timeInForce\":\"Day\"},\"brackets\":[{\"qty\":3,\"profitTarget\":5.0,\"stopLoss\":-12.5,\"trailingStop\":false}]}"
}
```

**CRITICAL:** `params` is a **stringified JSON** -- you must `json.dumps()` the params object, not pass it as a nested dict.

### 5.4 The `params` Object Structure (Before Stringification)

```json
{
    "entryVersion": {
        "orderQty": 3,
        "orderType": "Market",
        "timeInForce": "Day"
    },
    "brackets": [
        {
            "qty": 3,
            "profitTarget": 5.0,
            "stopLoss": -12.5,
            "trailingStop": false
        }
    ]
}
```

### 5.5 Multi-Leg Bracket Order (Multiple TP Targets)

This is the key to scaling out of positions. Each element in the `brackets` array is a separate exit leg with its own quantity, TP, SL, and optional trailing behavior.

**Example: 3 TP legs with autoTrail on the runner**

Params object (before `JSON.stringify`):

```json
{
    "entryVersion": {
        "orderQty": 15,
        "orderType": "Market",
        "timeInForce": "Day"
    },
    "brackets": [
        {
            "qty": 5,
            "profitTarget": 5.0,
            "stopLoss": -12.5,
            "trailingStop": false
        },
        {
            "qty": 5,
            "profitTarget": 12.5,
            "stopLoss": -12.5,
            "trailingStop": false
        },
        {
            "qty": 5,
            "profitTarget": 25.0,
            "stopLoss": -12.5,
            "trailingStop": false,
            "autoTrail": {
                "stopLoss": 5.0,
                "trigger": 7.5,
                "freq": 0.25
            }
        }
    ]
}
```

Complete request payload:

```json
{
    "accountId": 12345,
    "accountSpec": "DEMO12345",
    "symbol": "MNQH6",
    "orderStrategyTypeId": 2,
    "action": "Buy",
    "params": "{\"entryVersion\":{\"orderQty\":15,\"orderType\":\"Market\",\"timeInForce\":\"Day\"},\"brackets\":[{\"qty\":5,\"profitTarget\":5.0,\"stopLoss\":-12.5,\"trailingStop\":false},{\"qty\":5,\"profitTarget\":12.5,\"stopLoss\":-12.5,\"trailingStop\":false},{\"qty\":5,\"profitTarget\":25.0,\"stopLoss\":-12.5,\"trailingStop\":false,\"autoTrail\":{\"stopLoss\":5.0,\"trigger\":7.5,\"freq\":0.25}}]}"
}
```

### 5.6 Strategy Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `accountId` | integer | Yes | Account entity ID (from `/account/list` `id` field) |
| `accountSpec` | string | Yes | Account name (from `/account/list` `name` field) |
| `symbol` | string | Yes | Contract symbol |
| `orderStrategyTypeId` | integer | Yes | Always `2` for bracket orders |
| `action` | string | Yes | `"Buy"` or `"Sell"` for the entry |
| `params` | string | Yes | **Stringified JSON** -- must be `json.dumps()` of the params object |

### 5.7 Entry Version Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `orderQty` | integer | Yes | Total entry quantity (should equal sum of all bracket leg quantities) |
| `orderType` | string | Yes | `"Market"` or `"Limit"` |
| `timeInForce` | string | Yes | `"Day"` or `"GTC"` |
| `price` | float | Limit only | Entry limit price (must be on tick boundary) |

### 5.8 Bracket Leg Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `qty` | integer | Yes | Contracts for this exit leg |
| `profitTarget` | float | Yes | TP delta in **POINTS** from entry. Direction-signed (see below). |
| `stopLoss` | float | Yes | SL delta in **POINTS** from entry. Direction-signed (see below). |
| `trailingStop` | boolean | No | `true` for immediate trailing stop behavior on the SL leg |
| `autoTrail` | object | No | Trailing-after-profit configuration (see below) |

### 5.9 autoTrail Object (Trailing Stop After Profit)

The autoTrail converts a fixed stop to a trailing stop after a profit threshold is reached.

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `stopLoss` | float | POINTS | Trailing distance (how far the trail follows price) |
| `trigger` | float | POINTS | Profit threshold before trailing activates |
| `freq` | float | POINTS | Granularity of trailing updates (set to tick_size for every-tick updates) |

**All autoTrail values are in raw price differences (POINTS), NOT ticks.** They must be divisible by the instrument's tick size.

**Important:** When using `autoTrail`, set `trailingStop` to `false` in the bracket config. The autoTrail replaces the fixed stop with a trailing stop once the trigger is hit.

**Example:** On MNQ (tick_size=0.25), trail 20 ticks after 30 ticks of profit, updating every tick:
```json
{
    "autoTrail": {
        "stopLoss": 5.0,
        "trigger": 7.5,
        "freq": 0.25
    }
}
```

### 5.10 Direction-Aware Signs (CRITICAL)

The sign of `profitTarget` and `stopLoss` depends on the entry direction:

| Direction | profitTarget | stopLoss |
|-----------|-------------|----------|
| **Buy (Long)** | **Positive** (price goes UP to TP) | **Negative** (price goes DOWN to SL) |
| **Sell (Short)** | **Negative** (price goes DOWN to TP) | **Positive** (price goes UP to SL) |

**Example -- Buy NQ at 22000, TP 40 ticks above, SL 50 ticks below:**
- `profitTarget`: `+10.0` (40 ticks x 0.25 tick_size)
- `stopLoss`: `-12.5` (50 ticks x 0.25 tick_size)

**Example -- Sell NQ at 22000, TP 40 ticks below, SL 50 ticks above:**
- `profitTarget`: `-10.0`
- `stopLoss`: `+12.5`

### 5.11 Converting Ticks to Points

Tradovate bracket API expects **POINTS** (price difference), not ticks. Convert using the instrument's tick size:

```python
points = ticks * tick_size
```

Examples:
- NQ: 40 ticks x 0.25 = **10.0 points**
- GC: 50 ticks x 0.10 = **5.0 points**
- CL: 100 ticks x 0.01 = **1.0 points**
- ZB: 10 ticks x 0.03125 = **0.3125 points**

### 5.12 Break-Even in Brackets

**NOT supported in bracket orders.** Tradovate returns error: `"Stop and Stop/Limit breakeven supported only"`.

Break-even must be implemented as a separate monitor that watches the position and modifies/cancels the SL order after the price threshold is reached. Our system handles this via a safety-net monitor in `recorder_service.py`.

### 5.13 Bracket Order Response

```json
{
    "orderStrategy": {
        "id": 99999,
        "accountId": 12345,
        "orderStrategyTypeId": 2,
        "status": "ActiveStrategy"
    }
}
```

The response may also include `orderId` for the entry order. The exit orders (TP/SL) are managed internally by the strategy and can be found via `/order/list`.

**Check for errors even on HTTP 200:**
```json
{
    "errorText": "Invalid or missed parameters"
}
```

### 5.14 OSO Orders (Order-Sends-Order)

An alternative approach using absolute prices instead of relative deltas. The entry order triggers bracket legs on fill.

**Endpoint:** `POST {base_url}/order/placeOSO`

```json
{
    "accountSpec": "DEMO12345",
    "accountId": 12345,
    "action": "Sell",
    "symbol": "ESH6",
    "orderQty": 1,
    "orderType": "Limit",
    "price": 5788.75,
    "timeInForce": "GTC",
    "isAutomated": true,
    "bracket1": {
        "action": "Buy",
        "orderType": "Stop",
        "stopPrice": 5791.75
    },
    "bracket2": {
        "action": "Buy",
        "orderType": "Limit",
        "price": 5768.75
    }
}
```

- `bracket1`: Stop-loss leg (uses `stopPrice`)
- `bracket2`: Take-profit leg (uses `price` for Limit)
- Brackets activate only after the primary order fills
- Prices are **absolute** (not relative deltas like in `startOrderStrategy`)

### 5.15 OCO Orders (One-Cancels-Other)

Two orders where filling one cancels the other. Used for exit orders on existing positions.

**Endpoint:** `POST {base_url}/order/placeOCO`

```json
{
    "accountSpec": "DEMO12345",
    "accountId": 12345,
    "action": "Sell",
    "symbol": "NQH6",
    "orderQty": 1,
    "orderType": "Limit",
    "price": 22200.00,
    "isAutomated": true,
    "other": {
        "action": "Sell",
        "orderType": "Stop",
        "stopPrice": 21800.00
    }
}
```

- Primary order: Take-profit (Limit)
- `other`: Stop-loss (Stop)
- When one fills, the other is automatically cancelled

**IMPORTANT:** Use `json=payload` in Python requests, NOT `data=payload`. The endpoint requires proper JSON content-type encoding.

### 5.16 Choosing the Right Approach

| Scenario | Method | Why |
|----------|--------|-----|
| First entry (no position) | `startOrderStrategy` | Entry + exits in one atomic call |
| DCA entry (existing position) | `placeorder` (market) + separate TP | Can't use brackets on existing position |
| Limit entry with brackets | `placeOSO` | Absolute prices for pending entry |
| Exit pair on existing position | `placeOCO` | TP/SL pair with auto-cancel |

### 5.17 modifyOrderStrategy

**Endpoint:** `POST {base_url}/orderStrategy/modifyOrderStrategy`

**Poorly documented.** The only known schema:
```json
{
    "orderStrategyId": 60783294,
    "command": "string",
    "customTag50": "string"
}
```

The `command` format is undocumented. Community recommendation: cancel individual bracket legs and place new ones instead. Our system uses CANCEL + REPLACE exclusively (Rule 8).

---

## 6. Position Management

### 6.1 List All Positions

**Endpoint:** `GET {base_url}/position/list`

Returns all positions across all accounts for the authenticated token.

**Response:**
```json
[
    {
        "id": 456789,
        "accountId": 12345,
        "contractId": 2345678,
        "timestamp": "2026-02-18T10:30:00.000Z",
        "tradeDate": {
            "year": 2026,
            "month": 2,
            "day": 18
        },
        "netPos": 3,
        "netPrice": 22050.25,
        "bought": 3,
        "boughtValue": 66150.75,
        "sold": 0,
        "soldValue": 0
    }
]
```

Key fields:
- `netPos` -- net position size (positive = long, negative = short, 0 = flat)
- `netPrice` -- average entry price (weighted average for DCA entries)
- `contractId` -- use with `/contract/item` to resolve to symbol name
- `accountId` -- which account holds this position

### 6.2 Find Position by Contract

**Endpoint:** `GET {base_url}/position/find?name={symbol}`

### 6.3 Get Position by ID

**Endpoint:** `GET {base_url}/position/item?id={position_id}`

### 6.4 Liquidate Position

Close a position at market and cancel all related working orders.

**Endpoint:** `POST {base_url}/order/liquidateposition`

```json
{
    "accountId": 12345,
    "contractId": 2345678,
    "admin": false
}
```

**IMPORTANT:** This endpoint requires `contractId` (integer), NOT the symbol string. Use `/contract/find?name={symbol}` first to resolve the contract ID.

**Do NOT include `customTag50` in the request** -- it causes 404 responses.

---

## 7. Order Management

### 7.1 List All Orders

**Endpoint:** `GET {base_url}/order/list`

Returns all orders (working, filled, cancelled) for the authenticated token across all accounts.

**Account-scoped:** `GET {base_url}/account/{accountId}/orders`

**CRITICAL:** When using the fallback `/order/list` for multi-account systems, you MUST filter by `accountId` to avoid cross-account order confusion.

**Response (each order):**
```json
{
    "id": 789456,
    "orderId": 789456,
    "accountId": 12345,
    "contractId": 2345678,
    "action": "Sell",
    "orderType": "Limit",
    "price": 22200.00,
    "stopPrice": null,
    "orderQty": 1,
    "filledQty": 0,
    "avgFillPrice": 0,
    "ordStatus": "Working",
    "timeInForce": "GTC",
    "isAutomated": true
}
```

`ordStatus` values: `"Working"`, `"Filled"`, `"Cancelled"`, `"Rejected"`, `"Expired"`, `"Suspended"`, `"Completed"`

### 7.2 Get Single Order

**Endpoint:** `GET {base_url}/order/item?id={orderId}`

Returns full details for a specific order including all fields.

### 7.3 Cancel Order

**Endpoint:** `POST {base_url}/order/cancelorder`

```json
{
    "orderId": 789456
}
```

Minimal payload -- only `orderId` is required.

**IMPORTANT:** Check `ordStatus` before cancelling. Attempting to cancel a `"Filled"` or already `"Cancelled"` order returns `401 Access Denied`.

### 7.4 Modify Order

**Endpoint:** `POST {base_url}/order/modifyorder`

```json
{
    "orderId": 789456,
    "orderQty": 2,
    "orderType": "Limit",
    "price": 22250.00,
    "timeInForce": "GTC",
    "isAutomated": true
}
```

**Required fields for modify:**

| Field | Required | Notes |
|-------|----------|-------|
| `orderId` | Yes | The order to modify |
| `orderQty` | Yes | Must always be included |
| `orderType` | Yes | Must match the existing order type |
| `timeInForce` | Yes | Must match the existing TIF |
| `isAutomated` | Recommended | Boolean |

For stop orders, include `stopPrice`. For limit orders, include `price`.

**WARNING (Rule 8):** `modifyOrder` is UNRELIABLE for bracket-managed orders.

Known issues:
- Returns HTTP 200 with only `{"commandId": 12345}` -- command was QUEUED but NOT necessarily applied
- Returns success but the order price/qty is unchanged
- Community forums confirm this is a systemic issue

**Production-proven approach:** CANCEL + REPLACE
1. Cancel ALL working TP orders for the account/symbol
2. Place fresh TP orders at the new price with updated quantities
3. Never attempt to modify bracket-managed exit orders

### 7.5 Get Fills

**Endpoint:** `GET {base_url}/fill/list`

Query parameters: `?accountId={id}` and/or `?orderId={id}`

**Response:**
```json
[
    {
        "id": 123456,
        "orderId": 789456,
        "contractId": 2345678,
        "timestamp": "2026-02-18T10:30:00.000Z",
        "action": "Buy",
        "qty": 1,
        "price": 22050.25,
        "active": true
    }
]
```

---

## 8. Account Management

### 8.1 List Accounts

**Endpoint:** `GET {base_url}/account/list`

Returns all accounts (including subaccounts) for the authenticated user.

**Response:**
```json
[
    {
        "id": 12345,
        "name": "DEMO12345",
        "userId": 67890,
        "accountType": "Customer",
        "active": true,
        "clearingHouseId": 1,
        "riskCategoryId": 2,
        "autoLiqProfileId": 1,
        "marginAccountType": "Speculator",
        "legalStatus": "Individual"
    }
]
```

Key fields:
- `id` -- the integer account ID (used as `accountId` in order placement)
- `name` -- the account name/spec (used as `accountSpec` in order placement)

### 8.2 Get Account by ID

**Endpoint:** `GET {base_url}/account/{accountId}`

### 8.3 Get Subaccounts

**Endpoint:** `GET {base_url}/account/{accountId}/subaccounts`

---

## 9. Contract / Product Lookup

### 9.1 Find Contract by Symbol

**Endpoint:** `GET {base_url}/contract/find?name={symbol}`

Example: `GET {base_url}/contract/find?name=NQH6`

**Response:**
```json
{
    "id": 2345678,
    "name": "NQH6",
    "contractMaturityId": 12345,
    "status": "Active",
    "providerTickSize": 0.25
}
```

Key fields:
- `id` -- contract entity ID (used for `contractId` in liquidation, position lookup)
- `name` -- symbol name
- `providerTickSize` -- tick size for this specific contract

### 9.2 Get Contract by ID

**Endpoint:** `GET {base_url}/contract/item?id={contractId}`

Useful for resolving a `contractId` (from position data) back to a symbol name.

### 9.3 Product Lookup

Products are the base instruments (NQ, ES, GC). Contracts are specific expiration months (NQH6, ESM6, GCJ6).

**Endpoint:** `GET {base_url}/product/find?name={productSymbol}`

Returns product metadata including tick size and point value.

---

## 10. WebSocket API

### 10.1 What WebSocket Is For

The Tradovate WebSocket API is designed for:
- **Real-time user events**: Subscribing to `user/syncRequest` for position changes, order fills, cash balance updates
- **Market data streaming**: Receiving quotes, DOM data, chart data, and histograms
- **Reactive data consumption**: Listening for position updates after order placement instead of polling

### 10.2 What WebSocket Is NOT For (In This System)

While the Tradovate WebSocket API technically supports order placement (any REST endpoint is available via WebSocket), **our system uses REST exclusively for all order operations (Rule 10).**

**Why:**
- The WebSocket connection pool was NEVER reliably functional in production (Bug #15)
- REST provides clearer request/response semantics for critical order operations
- WebSocket order placement had silent failures that were difficult to detect
- REST errors are easier to log, retry, and debug
- No reliable way to match responses to requests over WebSocket

### 10.3 WebSocket Connection

1. Connect to WebSocket URL (see Base URLs section)
2. Authenticate by sending the access token
3. Send heartbeat (`[]` -- empty JSON array) every 2.5 seconds to keep alive

### 10.4 WebSocket Message Format

```json
{
    "n": "order/placeOrder",
    "o": {
        "accountSpec": "DEMO12345",
        "accountId": 12345,
        "action": "Buy",
        "symbol": "NQH6",
        "orderQty": 1,
        "orderType": "Market",
        "timeInForce": "Day",
        "isAutomated": true
    }
}
```

- `n` -- operation name (same path as REST endpoint)
- `o` -- operation payload (same structure as REST request body)

### 10.5 Market Data WebSocket

For streaming market data, connect to the market data WebSocket:
- Demo: `wss://md-demo.tradovateapi.com/v1/websocket`
- Live: `wss://md.tradovateapi.com/v1/websocket`

Subscribe to specific contracts for quotes, DOM, or chart data.

### 10.6 Why NOT WebSocket for Orders (Detailed)

- WebSocket responses have ambiguous/inconsistent format
- Success: may return `{"s": "ok"}` or `{"orderId": ...}` or just `{"commandId": ...}`
- Error: may return `{"s": "error", "d": "..."}` or `{"error": "..."}`
- No reliable correlation between requests and responses in a high-throughput system
- REST provides deterministic HTTP status codes + response bodies

---

## 11. Error Codes and Handling

### 11.1 HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| **200** | Success (BUT check body for `errorText`!) | Parse response; check `errorText`, `failureText` |
| **401** | Unauthorized / Access Denied | Token expired: call `/auth/renewAccessToken`. If that fails, re-authenticate. |
| **403** | Forbidden | Account type mismatch (live token on demo endpoint or vice versa) |
| **404** | Not Found | Invalid endpoint path, or entity does not exist |
| **408** | Request Timeout | Exceeded max concurrent connections (standard: 1, dual: 2) |
| **429** | Too Many Requests | Rate limit exceeded. Back off and retry with exponential backoff. |

### 11.2 Response-Level Errors (Inside HTTP 200)

Tradovate frequently returns HTTP 200 with an error in the response body:

```json
{"errorText": "Invalid or missed parameters"}
```

```json
{"failureText": "No quote available", "failureReason": "NoQuote"}
```

**ALWAYS check for `errorText`, `failureText`, and `failureReason` in every response, even on HTTP 200.**

### 11.3 Common Error Messages

| Error | Cause | Fix |
|-------|-------|-----|
| `"Invalid or missed parameters"` | Malformed bracket params, missing required fields, `params` not stringified | Verify `params` is `json.dumps()`'d; check all required fields |
| `"No quote available"` | Market is closed or no data subscription | Cannot place market orders or trailing stops when market is closed |
| `"Access is denied"` | Token expired, or trying to cancel filled/cancelled order | Renew token; check `ordStatus` before cancel |
| `"Expired Access Token"` | Token past 90-minute lifespan | Call `/auth/renewAccessToken` or re-authenticate |
| `"current price outside the price limits set"` | Price violates exchange limits | Check exchange price limits |
| `"Stop and Stop/Limit breakeven supported only"` | Tried to use native break-even in bracket order | Implement break-even as separate monitor |
| `"Invalid price increment"` | Price not on tick boundary | Round: `round(round(price / tick_size) * tick_size, 10)` |
| `"Insufficient margin"` | Account lacks margin for the order size | Reduce position size or fund account |
| `"Request Timeout"` (408) | Too many concurrent connections | Close other sessions or get Dual Connections |
| `"Too Many Requests"` (429) | Rate limit exceeded | Exponential backoff retry |

### 11.4 Modify Order Silent Failures

`modifyOrder` may return HTTP 200 with only `{"commandId": 12345}` without actually applying the change. This happens when:
- The order was filled between your query and modify
- The order is managed by a bracket strategy
- The modification conflicts with strategy rules

**Always verify modifications** by fetching the order afterward with `/order/item` and comparing actual vs expected values.

### 11.5 Our Error Handling Strategy

| HTTP Status | Our Response |
|-------------|--------------|
| 200 + `orderId` | Success -- return order data |
| 200 + `errorText` | Rejected -- return error |
| 200 + `failureText` | API failure -- return error |
| 401 | Refresh token, retry once. If still 401, return auth error. |
| 408 | Return connection limit error |
| 429 | Exponential backoff (1s, 2s, 4s, 8s, 16s), 5 retries max |

---

## 12. Important Gotchas

### 12.1 Rate Limits Are Per Token, Not Per Account
All accounts sharing the same Tradovate token share ONE rate limit. 7 accounts = 7x API calls against the same quota. What looks like "+1 call" is really "+7 calls." (Rule 16)

### 12.2 Prices Must Be on Tick Boundaries
Tradovate REJECTS limit and stop orders at invalid price increments. Every calculated price must be rounded:
```python
price = round(round(price / tick_size) * tick_size, 10)
```
DCA weighted averages produce fractional prices (e.g., 25074.805) that are NOT on tick boundaries. (Rule 3)

### 12.3 The `params` Field Must Be Stringified
In `startOrderStrategy`, the `params` field MUST be a JSON string, not a nested object:
```python
# CORRECT
strategy_payload["params"] = json.dumps(params_object)

# WRONG -- will fail with "Invalid or missed parameters"
strategy_payload["params"] = params_object
```

### 12.4 Bracket Values Are in POINTS, Not Ticks
Convert: `points = ticks * tick_size`. All bracket fields (`profitTarget`, `stopLoss`, `autoTrail.*`) use price-point deltas.

### 12.5 HTTP 200 Does NOT Mean Success
Tradovate returns HTTP 200 for many error conditions. Always check the response body for `errorText`, `failureText`, or missing expected fields like `orderId`.

### 12.6 modifyOrder is Unreliable for Bracket Exits
DCA updates to bracket-managed TP/SL orders should use CANCEL + REPLACE (place fresh order), never `modifyOrder`. (Rule 8)

### 12.7 Demo vs Live API Are Completely Separate
Different base URLs, different tokens, different data. Demo positions exist only on demo; live only on live. No cross-environment queries.

### 12.8 Token Expires After 90 Minutes
Proactively renew approximately 10-15 minutes before expiration. If renewal returns 401, the token is dead -- re-authenticate with full credentials.

### 12.9 `isAutomated` Must Be Boolean
The `isAutomated` field must be a proper boolean (`true`/`false`), not a string (`"true"`/`"false"`).

### 12.10 Concurrent Connection Limit
Standard Tradovate subscriptions allow only 1 concurrent connection. Logging into the Tradovate UI while your API is connected will disconnect the API (HTTP 408). Purchase "Dual Connections" for 2 concurrent connections.

### 12.11 Symbol Root Extraction (Rule 15)
Futures symbols: `{ROOT}{MONTH}{YEAR}` (e.g., `GCJ6`, `NQH6`, `MGCJ6`). Root can be 2 or 3+ characters. Month letter (F/G/H/J/K/M/N/Q/U/V/X/Z) is NOT part of the root.

```python
# CORRECT: Try 3-char match first, then 2-char
alpha = ''.join(c for c in symbol if c.isalpha()).upper()
tick_size = tick_sizes.get(alpha[:3]) or tick_sizes.get(alpha[:2]) or 0.25

# WRONG (Bug #20): Always takes first 3 alpha chars
# GCJ6 -> "GCJ" -> NOT in dict -> wrong default 0.25 (GC is actually 0.10)
```

Month codes: F(Jan), G(Feb), H(Mar), J(Apr), K(May), M(Jun), N(Jul), Q(Aug), U(Sep), V(Oct), X(Nov), Z(Dec)

### 12.12 Break-Even NOT Supported in Brackets
Native break-even in bracket orders is not supported. Must implement as a separate position monitor.

### 12.13 Order Strategy vs Individual Orders
- **Strategy** (`startOrderStrategy`): Entry + exits in one call. Tradovate manages OCO. Best for first entries.
- **Individual orders** (`placeOrder`): Separate calls. You manage relationships. Required for DCA.
- **OSO** (`placeOSO`): Entry with brackets using absolute prices. Good for limit entries.
- **OCO** (`placeOCO`): Two exit orders with auto-cancel. Good for exits on existing positions.

### 12.14 Contract ID vs Symbol
Some endpoints (like `liquidateposition`) require `contractId` (integer), not the symbol string. Always resolve with `/contract/find?name={symbol}` first.

### 12.15 Do NOT Include customTag50 in liquidatePosition
Including `customTag50` in the liquidation request causes 404 responses. Only send `accountId`, `contractId`, and `admin`.

---

## 13. Tick Size Reference Table

All prices sent to Tradovate MUST be on valid tick boundaries.

```python
price = round(round(price / tick_size) * tick_size, 10)
```

### Index Futures

| Symbol | Product | Tick Size | Point Value | Tick Value |
|--------|---------|-----------|-------------|------------|
| **ES** | E-mini S&P 500 | 0.25 | $50.00 | $12.50 |
| **MES** | Micro E-mini S&P 500 | 0.25 | $5.00 | $1.25 |
| **NQ** | E-mini Nasdaq-100 | 0.25 | $20.00 | $5.00 |
| **MNQ** | Micro E-mini Nasdaq-100 | 0.25 | $2.00 | $0.50 |
| **YM** | E-mini Dow | 1.0 | $5.00 | $5.00 |
| **MYM** | Micro E-mini Dow | 1.0 | $0.50 | $0.50 |
| **RTY** | E-mini Russell 2000 | 0.1 | $50.00 | $5.00 |
| **M2K** | Micro E-mini Russell 2000 | 0.1 | $5.00 | $0.50 |

### Metals

| Symbol | Product | Tick Size | Point Value | Tick Value |
|--------|---------|-----------|-------------|------------|
| **GC** | Gold | 0.10 | $100.00 | $10.00 |
| **MGC** | Micro Gold | 0.10 | $10.00 | $1.00 |
| **SI** | Silver | 0.005 | $5,000.00 | $25.00 |
| **SIL** | Micro Silver (1000 oz) | 0.005 | $1,000.00 | $5.00 |
| **HG** | Copper | 0.0005 | $25,000.00 | $12.50 |
| **PL** | Platinum | 0.10 | $50.00 | $5.00 |

### Energies

| Symbol | Product | Tick Size | Point Value | Tick Value |
|--------|---------|-----------|-------------|------------|
| **CL** | Crude Oil | 0.01 | $1,000.00 | $10.00 |
| **MCL** | Micro Crude Oil | 0.01 | $100.00 | $1.00 |
| **NG** | Natural Gas | 0.001 | $10,000.00 | $10.00 |
| **HO** | Heating Oil | 0.0001 | $42,000.00 | $4.20 |
| **RB** | RBOB Gasoline | 0.0001 | $42,000.00 | $4.20 |

### Treasuries

| Symbol | Product | Tick Size | Point Value | Tick Value |
|--------|---------|-----------|-------------|------------|
| **ZB** | 30-Year T-Bond | 0.03125 (1/32) | $1,000.00 | $31.25 |
| **ZN** | 10-Year T-Note | 0.015625 (1/64) | $1,000.00 | $15.625 |
| **ZF** | 5-Year T-Note | 0.0078125 (1/128) | $1,000.00 | $7.8125 |
| **ZT** | 2-Year T-Note | 0.0078125 (1/128) | $2,000.00 | $15.625 |

### Currencies / Dollar Index

| Symbol | Product | Tick Size | Point Value | Tick Value |
|--------|---------|-----------|-------------|------------|
| **DX** | US Dollar Index | 0.005 | $1,000.00 | $5.00 |

### Crypto

| Symbol | Product | Tick Size | Point Value | Tick Value |
|--------|---------|-----------|-------------|------------|
| **BTC** | Bitcoin | 5.0 | $5.00 | $25.00 |
| **MBT** | Micro Bitcoin | 5.0 | $0.10 | $0.50 |
| **ETH** | Ether | 0.25 | $50.00 | $12.50 |
| **MET** | Micro Ether | 0.25 | $0.50 | $0.125 |

### Grains

| Symbol | Product | Tick Size | Point Value | Tick Value |
|--------|---------|-----------|-------------|------------|
| **ZC** | Corn | 0.25 | $50.00 | $12.50 |
| **ZS** | Soybeans | 0.25 | $50.00 | $12.50 |
| **ZW** | Wheat | 0.25 | $50.00 | $12.50 |
| **ZM** | Soybean Meal | 0.10 | $100.00 | $10.00 |
| **ZL** | Soybean Oil | 0.01 | $600.00 | $6.00 |

### Softs

| Symbol | Product | Tick Size | Point Value | Tick Value |
|--------|---------|-----------|-------------|------------|
| **KC** | Coffee | 0.05 | $375.00 | $18.75 |
| **CT** | Cotton | 0.01 | $500.00 | $5.00 |
| **SB** | Sugar | 0.01 | $1,120.00 | $11.20 |

---

## 14. Quick Reference: Python Examples

### Authenticate

```python
import aiohttp
import json

BASE_URL = "https://live.tradovateapi.com/v1"

async def authenticate(session, username, password, cid, sec):
    async with session.post(
        f"{BASE_URL}/auth/accesstokenrequest",
        json={
            "name": username,
            "password": password,
            "appId": "MyTradingApp",
            "appVersion": "1.0.0",
            "cid": cid,
            "sec": sec
        }
    ) as resp:
        data = await resp.json()
        if "errorText" in data:
            raise Exception(f"Auth failed: {data['errorText']}")
        return data["accessToken"]
```

### Place a Market Order

```python
async def place_market_order(session, token, account_id, account_spec, symbol, side, qty):
    async with session.post(
        f"{BASE_URL}/order/placeorder",
        json={
            "accountId": account_id,
            "accountSpec": account_spec,
            "action": side,        # "Buy" or "Sell"
            "symbol": symbol,      # e.g. "NQH6"
            "orderQty": int(qty),
            "orderType": "Market",
            "timeInForce": "Day",
            "isAutomated": True
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    ) as resp:
        data = await resp.json()
        if data.get("errorText") or data.get("failureText"):
            raise Exception(f"Order failed: {data}")
        return data
```

### Place a Multi-TP Bracket Order

```python
async def place_bracket_order(session, token, account_id, account_spec, symbol,
                               side, tp_legs, sl_ticks, tick_size):
    """
    Place a bracket order with multiple TP legs.

    Args:
        tp_legs: List of (qty, tp_ticks) tuples for each TP leg
        sl_ticks: Stop loss in ticks (same for all legs)
        tick_size: Instrument tick size (e.g., 0.25 for NQ)
    """
    is_long = side.upper() == "BUY"

    brackets = []
    for leg_qty, tp_ticks in tp_legs:
        tp_points = tp_ticks * tick_size
        sl_points = sl_ticks * tick_size
        brackets.append({
            "qty": int(leg_qty),
            "profitTarget": float(tp_points if is_long else -tp_points),
            "stopLoss": float(-sl_points if is_long else sl_points),
            "trailingStop": False
        })

    total_qty = sum(leg_qty for leg_qty, _ in tp_legs)

    params = {
        "entryVersion": {
            "orderQty": int(total_qty),
            "orderType": "Market",
            "timeInForce": "Day"
        },
        "brackets": brackets
    }

    async with session.post(
        f"{BASE_URL}/orderStrategy/startOrderStrategy",
        json={
            "accountId": account_id,
            "accountSpec": account_spec,
            "symbol": symbol,
            "orderStrategyTypeId": 2,
            "action": side,
            "params": json.dumps(params)  # MUST be stringified
        },
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    ) as resp:
        data = await resp.json()
        if data.get("errorText"):
            raise Exception(f"Bracket failed: {data['errorText']}")
        return data
```

### Place a Bracket Order with autoTrail on Runner

```python
async def place_bracket_with_trail(session, token, account_id, account_spec, symbol,
                                     side, tick_size):
    """Buy 3 NQ: TP1 at 20 ticks, TP2 at 40 ticks, TP3 runner with trailing stop."""
    is_long = side.upper() == "BUY"
    sign = 1.0 if is_long else -1.0

    params = {
        "entryVersion": {"orderQty": 3, "orderType": "Market", "timeInForce": "Day"},
        "brackets": [
            {
                "qty": 1,
                "profitTarget": sign * 20 * tick_size,
                "stopLoss": -sign * 40 * tick_size,
                "trailingStop": False
            },
            {
                "qty": 1,
                "profitTarget": sign * 40 * tick_size,
                "stopLoss": -sign * 40 * tick_size,
                "trailingStop": False
            },
            {
                "qty": 1,
                "profitTarget": sign * 100 * tick_size,
                "stopLoss": -sign * 40 * tick_size,
                "trailingStop": False,
                "autoTrail": {
                    "stopLoss": 20 * tick_size,   # Trail distance: 20 ticks
                    "trigger": 30 * tick_size,     # Start trailing after 30 ticks profit
                    "freq": tick_size              # Update every tick
                }
            }
        ]
    }

    async with session.post(
        f"{BASE_URL}/orderStrategy/startOrderStrategy",
        json={
            "accountId": account_id,
            "accountSpec": account_spec,
            "symbol": symbol,
            "orderStrategyTypeId": 2,
            "action": side,
            "params": json.dumps(params)
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    ) as resp:
        data = await resp.json()
        if data.get("errorText"):
            raise Exception(f"Bracket failed: {data['errorText']}")
        return data
```

### Cancel an Order

```python
async def cancel_order(session, token, order_id):
    async with session.post(
        f"{BASE_URL}/order/cancelorder",
        json={"orderId": order_id},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    ) as resp:
        return resp.status == 200
```

### Get Positions (Open Only)

```python
async def get_open_positions(session, token, account_id=None):
    async with session.get(
        f"{BASE_URL}/position/list",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    ) as resp:
        positions = await resp.json()
        # Filter to open positions only
        open_pos = [p for p in positions if p.get("netPos", 0) != 0]
        # Optionally filter by account
        if account_id:
            open_pos = [p for p in open_pos if p.get("accountId") == account_id]
        return open_pos
```

### Get Orders for an Account

```python
async def get_account_orders(session, token, account_id):
    async with session.get(
        f"{BASE_URL}/order/list",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    ) as resp:
        all_orders = await resp.json()
        # CRITICAL: Filter by account to avoid cross-account confusion
        return [o for o in all_orders if o.get("accountId") == account_id]
```

### Resolve Contract ID from Symbol

```python
async def get_contract_id(session, token, symbol):
    async with session.get(
        f"{BASE_URL}/contract/find",
        params={"name": symbol},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    ) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data.get("id")
        return None
```

### Liquidate a Position

```python
async def liquidate_position(session, token, account_id, symbol):
    contract_id = await get_contract_id(session, token, symbol)
    if not contract_id:
        raise Exception(f"Could not resolve contract ID for {symbol}")

    async with session.post(
        f"{BASE_URL}/order/liquidateposition",
        json={
            "accountId": account_id,
            "contractId": contract_id,
            "admin": False
        },
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    ) as resp:
        return await resp.json()
```

---

## 15. Sources

### Official Documentation
- [Tradovate API Documentation](https://api.tradovate.com/)
- [Tradovate Partner API - Access Token Request](https://partner.tradovate.com/api/rest-api-endpoints/authentication/access-token-request)
- [Tradovate Partner API - Auth Overview](https://partner.tradovate.com/overview/quick-setup/auth-overview)
- [Tradovate GitHub - Example API FAQ](https://github.com/tradovate/example-api-faq)
- [Tradovate GitHub - REST vs WebSocket API](https://github.com/tradovate/example-api-faq/blob/main/docs/RestApiVsWebSocketApi.md)
- [Tradovate Support - API Access](https://support.tradovate.com/s/article/Tradovate-API-Access)
- [Tradovate Support - Reset API Limits](https://support.tradovate.com/s/article/Tradovate-Reset-API-Limits-Too-Many-Requests)

### Community / Forum
- [Starting Strategies Through API](https://community.tradovate.com/t/starting-strategies-through-api/2625)
- [Trouble Submitting Bracket Order via API](https://community.tradovate.com/t/trouble-submitting-bracket-order-via-api/3513)
- [startOrderStrategy Multi-bracket Error](https://community.tradovate.com/t/startorderstrategy-multi-bracket-error/6786)
- [Place a TP + SL Order via API](https://community.tradovate.com/t/place-a-tp-sl-order-via-api/8537)
- [OSO/OCO/Bracket Orders](https://community.tradovate.com/t/oso-oco-bracket-orders/10272)
- [Trouble with placeOCO](https://community.tradovate.com/t/trouble-with-order-placeoco/5823)
- [Convert Stop to Trailing Stop After Profit](https://community.tradovate.com/t/convert-stop-to-trailing-stop-after-profit/4805)
- [Creating Bracket Order with Trailing Stop](https://community.tradovate.com/t/creating-an-bracket-order-with-trailing-stop/11356)
- [Understanding Tradovate Rate Limits](https://community.tradovate.com/t/understanding-tradovates-rate-limits/2120)
- [API Rate Limit Question](https://community.tradovate.com/t/api-rate-limit-question/3545)
- [API Order Failures](https://community.tradovate.com/t/api-order-failures/4098)
- [modifyOrderStrategy Command Schema](https://community.tradovate.com/t/modifyorderstrategy-command-schema/4529)
- [modifyOrder Fails to Move Stop Order](https://community.tradovate.com/t/modifyorder-fails-to-move-stop-order-but-returns-success-s-200/4641)
- [Contract Information (Symbol)](https://community.tradovate.com/t/contract-information-symbol/8231)
- [API JSON Syntax](https://community.tradovate.com/t/api-json-syntax/2773)

### Third-Party Analysis
- [TradeSyncer - Understanding Tradovate API Limits](https://help.tradesyncer.com/en/articles/11110392-understanding-tradovate-api-limits-what-they-are-how-to-avoid-them)
- [CrossTrade - Understanding Tradovate API Rate Limits](https://crosstrade.io/blog/understanding-tradovate-api-rate-limits/)
- [PickMyTrade - Tradovate Order Rejected Guide](https://blog.pickmytrade.trade/tradovate-order-rejected-2025-causes-fixes-guide/)
- [PickMyTrade - Mastering OCO Orders](https://blog.pickmytrade.trade/mastering_oco_orders_in_tradovate/)

### Production Code
- `just-trades-platform/phantom_scraper/tradovate_integration.py` -- Production-verified API integration
- `just-trades-platform/phantom_scraper/recorder_service.py` -- Trade execution engine with bracket builder

---

*Last updated: Feb 18, 2026*
*Production stable tag: WORKING_FEB18_2026_DCA_SKIP_STABLE @ c75d7d4*
*Source: Official docs + community forums + production-tested code in Just Trades Platform*
