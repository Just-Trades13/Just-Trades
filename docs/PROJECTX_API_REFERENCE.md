# ProjectX / TopstepX API Reference -- Just Trades Platform

> **This is the authoritative reference for ProjectX API integration.**
> Built from the Swagger spec, official docs, community SDKs, and production source code.
> Last verified: Feb 18, 2026
> Swagger Spec: https://api.topstepx.com/swagger/v1/swagger.json
> Official Docs: https://gateway.docs.projectx.com/
> API Version: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Base URLs & Connection](#base-urls--connection)
3. [Authentication](#authentication)
4. [Rate Limits](#rate-limits)
5. [Standard Response Format](#standard-response-format)
6. [Enums & Constants](#enums--constants)
7. [Account Management](#account-management)
8. [Contract Lookup](#contract-lookup)
9. [Order Placement](#order-placement)
10. [Bracket Orders](#bracket-orders)
11. [Order Management](#order-management)
12. [Position Management](#position-management)
13. [Trade History](#trade-history)
14. [Historical Market Data](#historical-market-data)
15. [WebSocket / SignalR](#websocket--signalr)
16. [Differences from Tradovate](#differences-from-tradovate)
17. [Production Gotchas](#production-gotchas)
18. [Complete Endpoint Reference](#complete-endpoint-reference)
19. [Community Resources](#community-resources)
20. [Just Trades Integration Notes](#just-trades-integration-notes)

---

## Overview

ProjectX is the underlying trading platform powering TopstepX, Apex, Blue Guardian, and other prop firms. The Gateway API uses REST architecture with JSON request/response bodies. Almost all endpoints use POST (the only exception is `GET /api/Status/ping`).

**Key facts:**
- 19 total endpoints (18 POST + 1 GET)
- Authentication uses JWT tokens (valid 24 hours)
- API subscription required: $29/mo ($14.50/mo with code "topstep" for 50% off, no expiration)
- No sandbox environment -- demo URLs work for all accounts (demo AND live/funded)
- VPS, VPN, and remote server use is prohibited by TopstepX ToS
- Topstep does NOT provide technical support for API implementation
- One API subscription applies across multiple TopstepX accounts

---

## Base URLs & Connection

### REST API

| Environment | Base URL | Notes |
|-------------|----------|-------|
| **TopstepX (production)** | `https://api.topstepx.com/api` | For TopstepX accounts (API key auth) |
| **Generic ProjectX (all firms)** | `https://gateway-api-demo.s2f.projectx.com/api` | Works for ALL accounts (demo AND live/funded) |
| **Generic ProjectX (live)** | ~~`https://gateway-api.s2f.projectx.com/api`~~ | **DEAD -- DNS NXDOMAIN as of Feb 2026** |

**IMPORTANT:** The "demo" gateway URL (`gateway-api-demo.s2f.projectx.com`) serves ALL accounts, including live/funded accounts. The "live" gateway URL is dead. Always use the demo gateway for generic ProjectX firms. The official docs at https://gateway.docs.projectx.com/docs/getting-started/connection-urls/ only list demo endpoints.

For TopstepX specifically, use `api.topstepx.com/api`.

### WebSocket (SignalR)

| Environment | Hub | URL |
|-------------|-----|-----|
| TopstepX | User Hub | `wss://rtc.topstepx.com/hubs/user` |
| TopstepX | Market Hub | `wss://rtc.topstepx.com/hubs/market` |
| Generic ProjectX | User Hub | `https://gateway-rtc-demo.s2f.projectx.com/hubs/user` |
| Generic ProjectX | Market Hub | `https://gateway-rtc-demo.s2f.projectx.com/hubs/market` |

### Password Auth (Application Login -- generic only)

| Environment | URL |
|-------------|-----|
| Generic ProjectX | `https://userapi-demo.s2f.projectx.com` |

TopstepX does NOT have a `/login` endpoint. Password auth for TopstepX goes through the generic `userapi-demo` endpoint.

### URL Building

```python
# TopstepX: base_url already includes /api
url = f"{self.base_url}/{endpoint}"          # https://api.topstepx.com/api/Order/place

# Other ProjectX firms: need /api prefix
url = f"{self.base_url}/api/{endpoint}"       # https://gateway-api-demo.s2f.projectx.com/api/Order/place
```

---

## Authentication

### Method 1: API Key Login (Required for Third-Party Apps)

Requires API subscription from ProjectX Dashboard ($14.50/mo with code "topstep").

**Endpoint:** `POST /api/Auth/loginKey`

**Request:**
```json
{
  "userName": "your_projectx_dashboard_username",
  "apiKey": "your-api-key-from-dashboard"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJSUzI1NiIs...",
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

**IMPORTANT:** The `userName` is your **ProjectX Dashboard** username, NOT your prop firm email. These are often different.

### Method 2: Application Login (Requires App Registration with ProjectX)

For registered applications with ProjectX-issued `appId` and `verifyKey`.

**Endpoint:** `POST /api/Auth/loginApp`

**Request:**
```json
{
  "userName": "user@email.com",
  "password": "your_password",
  "deviceId": "unique-device-identifier",
  "appId": "your_registered_app_id",
  "verifyKey": "your_verify_key"
}
```

**Response:** Same format as loginKey.

Without `appId`/`verifyKey`, password auth is NOT available. Users must use API Key auth.

### Using the Token

Include the token in all subsequent requests:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
Content-Type: application/json
Accept: application/json
```

### Token Lifecycle

- Tokens are valid for **24 hours**
- Refresh before expiry using the validate endpoint:

**Endpoint:** `POST /api/Auth/validate`

**Request:** No body required. Send with current Bearer token in Authorization header.

**Response:**
```json
{
  "success": true,
  "errorCode": 0,
  "errorMessage": null,
  "newToken": "eyJhbGciOiJSUzI1NiIs..."
}
```

Replace your stored token with `newToken` from the response.

### Logout

**Endpoint:** `POST /api/Auth/logout`

No request body required. Send with Bearer token.

### Auth Error Codes

| errorCode | Meaning |
|-----------|---------|
| 0 | Success |
| 3 | Invalid credentials (bad username or password/API key) |
| 4 | Invalid appId or verifyKey |

---

## Rate Limits

The API enforces rate limits on all authenticated requests.

| Endpoint | Limit |
|----------|-------|
| `POST /api/History/retrieveBars` | **50 requests / 30 seconds** |
| All other endpoints | **200 requests / 60 seconds** |

**When exceeded:** HTTP `429 Too Many Requests`

**Recovery:** Reduce request frequency and retry after a short delay. No specific backoff algorithm or retry-after header is documented.

---

## Standard Response Format

All API responses follow this wrapper structure:

```json
{
  "success": true,
  "errorCode": 0,
  "errorMessage": null,
  "<data_field>": ...
}
```

The `<data_field>` name varies by endpoint:

| Endpoint | Data Field |
|----------|------------|
| Auth/loginKey, Auth/loginApp | `token` |
| Auth/validate | `newToken` |
| Account/search | `accounts` (array) |
| Contract/search, Contract/available | `contracts` (array) |
| Contract/searchById | `contract` (object) |
| Order/place | `orderId` (integer) |
| Order/search, Order/searchOpen | `orders` (array) |
| Order/cancel, Order/modify | (no data field -- just success/error) |
| Position/searchOpen | `positions` (array) |
| Position/closeContract, partialCloseContract | (no data field -- just success/error) |
| Trade/search | `trades` (array) |
| History/retrieveBars | `bars` (array) |

**HTTP Status Codes:**

| Status | Meaning |
|--------|---------|
| 200 | Request processed (check `success` field for logical success/failure) |
| 401 | Authentication failure / invalid or expired token |
| 429 | Rate limit exceeded |

**ALWAYS check the `success` field** -- HTTP 200 does NOT guarantee the operation succeeded.

---

## Enums & Constants

### OrderType (from Swagger spec)

| Value | Name | Description | Used For |
|-------|------|-------------|----------|
| 0 | Unknown | Should not be used | -- |
| 1 | Limit | Executes at specified price or better | TP orders, limit entries |
| 2 | Market | Immediate execution at best available price | Entry orders |
| 3 | StopLimit | Becomes limit order when stop price reached | Combined stop+limit |
| 4 | Stop | Becomes market order when stop price reached | Fixed SL orders, SL brackets |
| 5 | TrailingStop | Dynamic stop that follows price movement | Trailing SL brackets |
| 6 | JoinBid | Joins the current best bid | Queue at bid |
| 7 | JoinAsk | Joins the current best ask | Queue at ask |

### OrderSide

| Value | Name | Description |
|-------|------|-------------|
| 0 | Bid (Buy) | Buy order |
| 1 | Ask (Sell) | Sell order |

### OrderStatus

| Value | Name | Description |
|-------|------|-------------|
| 0 | None | Undefined / not set |
| 1 | Open | Active working order on exchange |
| 2 | Filled | Completely executed |
| 3 | Cancelled | Cancelled by user or system |
| 4 | Expired | Expired (time-based) |
| 5 | Rejected | Rejected by exchange or risk system |
| 6 | Pending | Awaiting submission to exchange |
| 7 | PendingCancellation | Cancel request submitted, awaiting confirmation |
| 8 | Suspended | Suspended (bracket legs before entry fills) |

### PositionType

| Value | Name |
|-------|------|
| 0 | Undefined |
| 1 | Long |
| 2 | Short |

### AggregateBarUnit (for historical data)

| Value | Name |
|-------|------|
| 0 | Unspecified |
| 1 | Second |
| 2 | Minute |
| 3 | Hour |
| 4 | Day |
| 5 | Week |
| 6 | Month |

---

## Account Management

### Search Accounts

**Endpoint:** `POST /api/Account/search`

**Request:**
```json
{
  "onlyActiveAccounts": true
}
```

**Response:**
```json
{
  "accounts": [
    {
      "id": 536,
      "name": "TEST_ACCOUNT_1",
      "balance": 50000.00,
      "canTrade": true,
      "isVisible": true,
      "simulated": false
    }
  ],
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

**Account Object Fields:**

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique account identifier (used in all other endpoints as `accountId`) |
| name | string | Display name of the account |
| balance | decimal | Current account balance |
| canTrade | boolean | Whether the account is allowed to place trades |
| isVisible | boolean | Whether the account appears in the UI |
| simulated | boolean | Whether this is a simulated/demo account |

---

## Contract Lookup

### Contract ID Format

ProjectX uses a structured string-based contract ID format:

```
CON.F.US.{SYMBOL_CODE}.{EXPIRY}
```

**Examples:**

| Contract ID | Name | Description | tickSize | tickValue |
|-------------|------|-------------|----------|-----------|
| `CON.F.US.ENQ.U25` | NQU5 | E-mini NASDAQ-100: September 2025 | 0.25 | 5.00 |
| `CON.F.US.EP.M25` | ESM5 | E-mini S&P 500: June 2025 | 0.25 | 12.50 |
| `CON.F.US.GMET.J25` | MGCJ5 | Micro Gold: April 2025 | 0.10 | 1.00 |
| `CON.F.US.BP6.U25` | 6BU5 | British Pound: September 2025 | 0.0001 | 6.25 |

The `symbolId` field (e.g., `F.US.ENQ`) identifies the instrument family regardless of expiry month.

### List Available Contracts

**Endpoint:** `POST /api/Contract/available`

Returns the full list of tradeable contracts (28+ instruments typically).

**Request:**
```json
{
  "live": true
}
```

**Response:**
```json
{
  "contracts": [
    {
      "id": "CON.F.US.ENQ.U25",
      "name": "NQU5",
      "description": "E-mini NASDAQ-100: September 2025",
      "tickSize": 0.25,
      "tickValue": 5.00,
      "activeContract": true,
      "symbolId": "F.US.ENQ"
    }
  ],
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

### Search Contracts by Text

**Endpoint:** `POST /api/Contract/search`

Returns up to 20 matching contracts.

**Request:**
```json
{
  "searchText": "NQ",
  "live": false
}
```

**Response:** Same format as available contracts.

### Search Contract by ID

**Endpoint:** `POST /api/Contract/searchById`

**Request:**
```json
{
  "contractId": "CON.F.US.ENQ.H25"
}
```

**Response:**
```json
{
  "contract": {
    "id": "CON.F.US.ENQ.H25",
    "name": "NQH5",
    "description": "E-mini NASDAQ-100: March 2025",
    "tickSize": 0.25,
    "tickValue": 5.00,
    "activeContract": false,
    "symbolId": "F.US.ENQ"
  },
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

**Contract Object Fields:**

| Field | Type | Description |
|-------|------|-------------|
| id | string | Full contract identifier (e.g., `CON.F.US.ENQ.U25`) |
| name | string | Short trading symbol (e.g., `NQU5`) |
| description | string | Human-readable description (e.g., "E-mini NASDAQ-100: September 2025") |
| tickSize | decimal | Minimum price increment (e.g., 0.25 for NQ, 0.10 for GC) |
| tickValue | decimal | Dollar value per tick (e.g., 5.00 for NQ, 10.00 for GC) |
| activeContract | boolean | Whether the contract is currently active/tradeable |
| symbolId | string | Instrument family identifier (e.g., `F.US.ENQ`) |

---

## Order Placement

### Place an Order

**Endpoint:** `POST /api/Order/place`

**Full Request Schema (all fields):**
```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 2,
  "side": 0,
  "size": 1,
  "limitPrice": null,
  "stopPrice": null,
  "trailPrice": null,
  "customTag": null,
  "linkedOrderId": null,
  "stopLossBracket": null,
  "takeProfitBracket": null
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| accountId | integer | Yes | Account ID from Account/search |
| contractId | string | Yes | Full contract ID (e.g., `CON.F.US.ENQ.U25`) |
| type | integer | Yes | OrderType enum (1-7) |
| side | integer | Yes | 0=Buy, 1=Sell |
| size | integer | Yes | Number of contracts (positive) |
| limitPrice | decimal | Conditional | Required for Limit (1) and StopLimit (3) orders |
| stopPrice | decimal | Conditional | Required for Stop (4) and StopLimit (3) orders |
| trailPrice | decimal | Conditional | Trail distance for TrailingStop (5) orders |
| customTag | string | No | Custom identifier -- **must be unique across the account** |
| linkedOrderId | integer | No | For OCO relationships -- links this order to another |
| stopLossBracket | object | No | SL bracket (see [Bracket Orders](#bracket-orders)) |
| takeProfitBracket | object | No | TP bracket (see [Bracket Orders](#bracket-orders)) |

**Response:**
```json
{
  "orderId": 9056,
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

### Market Order Example

```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 2,
  "side": 0,
  "size": 1
}
```

### Limit Order Example (for TP)

```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 1,
  "side": 1,
  "size": 1,
  "limitPrice": 22200.00
}
```

### Stop Order Example (for SL)

```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 4,
  "side": 1,
  "size": 1,
  "stopPrice": 22100.00
}
```

### Stop-Limit Order Example

```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 3,
  "side": 1,
  "size": 1,
  "stopPrice": 22100.00,
  "limitPrice": 22095.00
}
```

### Trailing Stop Order Example

```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 5,
  "side": 1,
  "size": 1,
  "trailPrice": 10.0
}
```

---

## Bracket Orders

Bracket orders attach take-profit and/or stop-loss legs to an entry order. When the entry fills, the bracket legs become working orders (status transitions from Suspended (8) to Open (1)). They operate as OCO (One-Cancels-Other) -- when one bracket leg fills, the other is automatically cancelled.

### Bracket Object Structure

Both `stopLossBracket` and `takeProfitBracket` use the same structure:

```json
{
  "ticks": <integer>,
  "type": <OrderType integer>
}
```

| Field | Type | Description |
|-------|------|-------------|
| ticks | integer (int32) | Distance from entry price in ticks (signed -- see below) |
| type | integer | OrderType for the bracket leg |

### Tick Sign Convention (CRITICAL)

Ticks are **signed** -- the sign indicates direction relative to entry price:

**For `takeProfitBracket.ticks`:**

| Entry Side | Sign | Meaning |
|------------|------|---------|
| Buy (side=0) | **Positive** (+) | TP is ABOVE entry (price moves up in your favor) |
| Sell (side=1) | **Negative** (-) | TP is BELOW entry (price moves down in your favor) |

**For `stopLossBracket.ticks` (fixed stop, type=4):**

| Entry Side | Sign | Meaning |
|------------|------|---------|
| Buy (side=0) | **Negative** (-) | SL is BELOW entry (price moves down against you) |
| Sell (side=1) | **Positive** (+) | SL is ABOVE entry (price moves up against you) |

**For trailing stop (type=5):** Use **unsigned** (positive) ticks -- the platform determines direction from the position side.

```python
# Code pattern:
tp_sign = 1 if is_buy else -1
sl_sign = -1 if is_buy else 1

order["takeProfitBracket"] = {"ticks": tp_sign * abs(tp_ticks), "type": 1}

# Fixed stop:
order["stopLossBracket"] = {"ticks": sl_sign * abs(sl_ticks), "type": 4}

# Trailing stop: unsigned distance
order["stopLossBracket"] = {"ticks": abs(sl_ticks), "type": 5}
```

### Bracket Type Values

| Bracket | type Value | Why |
|---------|-----------|-----|
| Take Profit | 1 (Limit) | TP is a limit order at the target price |
| Stop Loss (fixed) | 4 (Stop) | SL is a stop-market order at the stop price |
| Stop Loss (trailing) | 5 (TrailingStop) | Trailing SL follows price by the tick distance |

### Complete Bracket Order Examples

**Buy 3 MNQ with 20-tick TP and 20-tick fixed SL:**
```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 2,
  "side": 0,
  "size": 3,
  "takeProfitBracket": {
    "ticks": 20,
    "type": 1
  },
  "stopLossBracket": {
    "ticks": -20,
    "type": 4
  }
}
```

**Sell 2 NQ with 30-tick TP and 15-tick trailing SL:**
```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 2,
  "side": 1,
  "size": 2,
  "takeProfitBracket": {
    "ticks": -30,
    "type": 1
  },
  "stopLossBracket": {
    "ticks": 15,
    "type": 5
  }
}
```

**Limit entry at 5600 with brackets:**
```json
{
  "accountId": 536,
  "contractId": "CON.F.US.EP.M25",
  "type": 1,
  "side": 0,
  "size": 1,
  "limitPrice": 5600.00,
  "takeProfitBracket": {
    "ticks": 20,
    "type": 1
  },
  "stopLossBracket": {
    "ticks": -10,
    "type": 4
  }
}
```

**Market entry with ONLY a trailing stop (no TP):**
```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 2,
  "side": 0,
  "size": 1,
  "stopLossBracket": {
    "ticks": 20,
    "type": 5
  }
}
```

### What Brackets Do NOT Support

1. **Multi-leg TP:** Only ONE take-profit bracket per order. Cannot split into multiple TP targets with different quantities. To achieve multi-leg TP, place entry order first, then manually place separate limit orders.
2. **Break-even:** No native break-even mechanism. Must be implemented as an external monitoring daemon that modifies the SL order when price reaches the trigger level.
3. **Per-leg quantity:** Bracket legs always use the same quantity as the entry order.
4. **autoBreakEven field:** Does not exist (unlike Tradovate).

### Manual OCO Linking (Alternative to Brackets)

For scenarios where brackets are insufficient (multi-leg TP, custom OCO groups):

1. Place entry order, get `orderId` from response
2. Place TP order with `linkedOrderId` referencing the SL order ID (or vice versa)
3. Linked orders form an OCO pair -- when one fills, the other auto-cancels

```json
{
  "accountId": 536,
  "contractId": "CON.F.US.ENQ.U25",
  "type": 1,
  "side": 1,
  "size": 1,
  "limitPrice": 21600.00,
  "linkedOrderId": 9058
}
```

---

## Order Management

### Cancel an Order

**Endpoint:** `POST /api/Order/cancel`

**Request:**
```json
{
  "accountId": 536,
  "orderId": 26974
}
```

**Response:**
```json
{
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

### Modify an Order

**Endpoint:** `POST /api/Order/modify`

Only include fields you want to change. `accountId` and `orderId` are always required.

**Request:**
```json
{
  "accountId": 536,
  "orderId": 26974,
  "size": 1,
  "limitPrice": null,
  "stopPrice": 1604.00,
  "trailPrice": null
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| accountId | integer | Yes | Account ID |
| orderId | integer | Yes | Order to modify |
| size | integer | No | New quantity (nullable) |
| limitPrice | decimal | No | New limit price (nullable) |
| stopPrice | decimal | No | New stop price (nullable) |
| trailPrice | decimal | No | New trail distance (nullable) |

**Response:**
```json
{
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

**NOTE:** Unlike Tradovate, ProjectX `Order/modify` is reliable and works for bracket-managed orders.

### Search Open Orders

**Endpoint:** `POST /api/Order/searchOpen`

Returns only orders with status Open (1).

**Request:**
```json
{
  "accountId": 536
}
```

**Response:**
```json
{
  "orders": [
    {
      "id": 26970,
      "accountId": 536,
      "contractId": "CON.F.US.EP.M25",
      "symbolId": "F.US.EP",
      "creationTimestamp": "2025-04-21T19:45:52.105808+00:00",
      "updateTimestamp": "2025-04-21T19:45:52.105808+00:00",
      "status": 1,
      "type": 4,
      "side": 1,
      "size": 1,
      "limitPrice": null,
      "stopPrice": 5138.000000000,
      "filledPrice": null,
      "fillVolume": 0,
      "customTag": null
    }
  ],
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

### Search Orders (Historical)

**Endpoint:** `POST /api/Order/search`

Returns orders within a time range, including filled and cancelled orders.

**Request:**
```json
{
  "accountId": 704,
  "startTimestamp": "2026-02-18T00:00:00Z",
  "endTimestamp": "2026-02-18T23:59:59Z"
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| accountId | integer | Yes | Account ID |
| startTimestamp | string (ISO 8601) | Yes | Start of time range |
| endTimestamp | string (ISO 8601) | No | End of time range (nullable) |

**Response:** Same structure as searchOpen, but includes orders of all statuses.

**Order Object Fields:**

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique order identifier |
| accountId | integer | Associated account |
| contractId | string | Full contract ID (e.g., `CON.F.US.EP.M25`) |
| symbolId | string | Instrument family ID (e.g., `F.US.EP`) |
| creationTimestamp | string (ISO 8601) | When the order was created |
| updateTimestamp | string (ISO 8601) | Last update time |
| status | integer | OrderStatus enum (0-8) |
| type | integer | OrderType enum (0-7) |
| side | integer | 0=Buy, 1=Sell |
| size | integer | Order quantity |
| limitPrice | decimal/null | Limit price (null if not applicable) |
| stopPrice | decimal/null | Stop price (null if not applicable) |
| filledPrice | decimal/null | Average fill price (null if not filled) |
| fillVolume | integer | Number of contracts filled |
| customTag | string/null | Custom identifier if set |

---

## Position Management

### Get Open Positions

**Endpoint:** `POST /api/Position/searchOpen`

**Request:**
```json
{
  "accountId": 536
}
```

**Response:**
```json
{
  "positions": [
    {
      "id": 6124,
      "accountId": 536,
      "contractId": "CON.F.US.GMET.J25",
      "creationTimestamp": "2025-04-21T19:52:32.175721+00:00",
      "type": 1,
      "size": 2,
      "averagePrice": 1575.750000000
    }
  ],
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

**Position Object Fields:**

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique position identifier |
| accountId | integer | Associated account |
| contractId | string | Full contract ID (e.g., `CON.F.US.GMET.J25`) |
| creationTimestamp | string (ISO 8601) | When the position was opened |
| type | integer | PositionType: 0=Undefined, 1=Long, 2=Short |
| size | integer | Number of contracts (**always positive**) |
| averagePrice | decimal | Average entry price (weighted if averaged in) |

**IMPORTANT:** Position `size` is always positive. The `type` field (1=Long, 2=Short) indicates direction. This differs from Tradovate where `netPos` is signed (positive=long, negative=short).

**Our existing code** references `netPos` and `netPrice` field names in the `ProjectXPositionSync` class. The actual Swagger spec uses `size`, `type`, and `averagePrice`. Check which fields your firm's API actually returns.

### Close Position (Full)

**Endpoint:** `POST /api/Position/closeContract`

Closes the entire position at market price.

**Request:**
```json
{
  "accountId": 536,
  "contractId": "CON.F.US.GMET.J25"
}
```

**Response:**
```json
{
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

### Close Position (Partial)

**Endpoint:** `POST /api/Position/partialCloseContract`

Closes a specified number of contracts at market price.

**Request:**
```json
{
  "accountId": 536,
  "contractId": "CON.F.US.GMET.J25",
  "size": 1
}
```

**Response:**
```json
{
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

---

## Trade History

### Search Trades

**Endpoint:** `POST /api/Trade/search`

Returns "half-turn" trades (individual fills, not round-trip P&L). The `profitAndLoss` field is null for opening fills and populated for closing fills.

**Request:**
```json
{
  "accountId": 536,
  "startTimestamp": "2025-04-21T00:00:00Z",
  "endTimestamp": "2025-04-21T23:59:59Z"
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| accountId | integer | Yes | Account ID |
| startTimestamp | string (ISO 8601) | Yes | Start of time range |
| endTimestamp | string (ISO 8601) | No | End of time range (nullable) |

**Response:**
```json
{
  "trades": [
    {
      "id": 12345,
      "accountId": 536,
      "contractId": "CON.F.US.ENQ.U25",
      "creationTimestamp": "2025-04-21T14:30:00Z",
      "price": 21500.250000000,
      "profitAndLoss": 125.00,
      "fees": 4.18,
      "side": 0,
      "size": 1,
      "voided": false,
      "orderId": 26970
    }
  ],
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

**Trade Object Fields:**

| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique trade identifier |
| accountId | integer | Associated account |
| contractId | string | Contract traded |
| creationTimestamp | string (ISO 8601) | Execution timestamp |
| price | decimal | Fill price |
| profitAndLoss | decimal/null | P&L (null for opening half-turn, populated for closing) |
| fees | decimal | Transaction costs/commissions |
| side | integer | 0=Buy, 1=Sell |
| size | integer | Quantity filled |
| voided | boolean | Whether the trade was voided/busted |
| orderId | integer | Parent order that generated this fill |

---

## Historical Market Data

### Retrieve Bars

**Endpoint:** `POST /api/History/retrieveBars`

**Rate limit:** 50 requests / 30 seconds (stricter than other endpoints).

**Request:**
```json
{
  "contractId": "CON.F.US.ENQ.U25",
  "live": false,
  "barUnit": 2,
  "barUnitNumber": 1,
  "startTimestamp": "2025-04-20T00:00:00Z",
  "endTimestamp": "2025-04-21T00:00:00Z"
}
```

**barUnit Values:**

| barUnit | Period | Example with barUnitNumber=5 |
|---------|--------|------------------------------|
| 1 | Second | 5-second bars |
| 2 | Minute | 5-minute bars |
| 3 | Hour | 5-hour bars |
| 4 | Day | 5-day bars |

**Response:**
```json
{
  "bars": [
    {
      "t": "2025-04-20T18:00:00Z",
      "o": 21500.25,
      "h": 21525.50,
      "l": 21490.00,
      "c": 21510.75,
      "v": 1250
    }
  ],
  "success": true,
  "errorCode": 0,
  "errorMessage": null
}
```

**Bar Fields:** `t`=timestamp, `o`=open, `h`=high, `l`=low, `c`=close, `v`=volume.

---

## WebSocket / SignalR

ProjectX uses **SignalR** (Microsoft's real-time communication framework) for WebSocket connections. This provides real-time updates for positions, orders, and market data without polling.

### Connection

Connect with the session token as a query parameter. Use `skip_negotiation: true` for direct WebSocket connection.

```
wss://gateway-rtc-demo.s2f.projectx.com/hubs/user?access_token=YOUR_TOKEN
```

### Hubs

| Hub | URL Path | Purpose |
|-----|----------|---------|
| User Hub | `/hubs/user` | Account updates, orders, positions, trades |
| Market Hub | `/hubs/market` | Quotes, market trades, depth/DOM data |

### User Hub Events (Server -> Client)

| Event Name | Data | Description |
|------------|------|-------------|
| `RealTimePosition` | Position object | Position created, updated, or closed |
| `RealTimeOrder` | Order object | Order status changed (placed, filled, cancelled) |
| `RealTimeBalance` | Balance object | Account balance updated |

### User Hub Methods (Client -> Server)

| Method | Args | Description |
|--------|------|-------------|
| `SubscribePositionUpdates` | `[]` | Start receiving position updates |
| `SubscribeOrderUpdates` | `[]` | Start receiving order updates |

### Market Hub Callbacks

| Callback | Description |
|----------|-------------|
| `on_quote_callback` | Real-time quote updates |
| `on_state_change_callback` | Connection state changes |

### Token Refresh for WebSocket

WebSocket connections must periodically refresh their token. Call `/api/Auth/validate` to get a new token, then update the stream:

```python
stream_instance.update_token(new_api_token)
```

### Python Example (using signalrcore)

```python
from signalrcore.hub_connection_builder import HubConnectionBuilder

connection = HubConnectionBuilder() \
    .with_url(f"https://gateway-rtc-demo.s2f.projectx.com/hubs/user?access_token={token}") \
    .with_automatic_reconnect({
        "type": "raw",
        "keep_alive_interval": 10,
        "reconnect_interval": 5,
        "max_attempts": 5
    }) \
    .build()

connection.on("RealTimePosition", lambda data: print(f"Position: {data}"))
connection.on("RealTimeOrder", lambda data: print(f"Order: {data}"))
connection.on("RealTimeBalance", lambda data: print(f"Balance: {data}"))

connection.start()
connection.send("SubscribePositionUpdates", [])
connection.send("SubscribeOrderUpdates", [])
```

---

## Differences from Tradovate

### Order Sides

| | Tradovate | ProjectX |
|-|-----------|----------|
| Buy | `"Buy"` (string) | `0` (integer) |
| Sell | `"Sell"` (string) | `1` (integer) |

### Order Types

| Type | Tradovate | ProjectX |
|------|-----------|----------|
| Market | `"Market"` (string) | `2` (integer) |
| Limit | `"Limit"` | `1` |
| Stop | `"Stop"` | `4` |
| StopLimit | `"StopLimit"` | `3` |
| TrailingStop | `"TrailingStopLoss"` | `5` |

### Position Fields

| Field | Tradovate | ProjectX |
|-------|-----------|----------|
| Direction + Quantity | `netPos` (signed: +long, -short) | `size` (always positive) + `type` (1=Long, 2=Short) |
| Average Price | `netPrice` | `averagePrice` |
| Contract ID | numeric integer | string (`CON.F.US.ENQ.U25`) |

### Contract Matching

- **Tradovate:** Numeric contract IDs. Direct integer comparison.
- **ProjectX:** String contract IDs. MUST use string comparison:
  ```python
  str(pos.get('contractId')) == str(contract_id)
  ```

### Bracket Orders

| Feature | Tradovate | ProjectX |
|---------|-----------|----------|
| Multi-leg TP | Supported (`brackets[]` array with per-leg qty) | **NOT supported** (single TP bracket only) |
| Trailing SL in bracket | `trailParams` object with offset/threshold | `stopLossBracket.type = 5` with tick distance |
| Break-even | Not native (monitor-based in our code) | **NOT supported** -- needs monitoring daemon |
| Bracket quantity | Per-leg custom quantity | Always matches entry quantity |
| Entry + bracket API | `orderStrategy/startOrderStrategy` | `Order/place` with inline bracket fields |
| TP/SL distance | Absolute price values | Ticks (signed integer) |
| Order modify for brackets | Unreliable (`modifyOrder` breaks bracket links) | Reliable (`Order/modify` works) |

### Authentication

| | Tradovate | ProjectX |
|-|-----------|----------|
| Method | OAuth2 + credentials + client ID/secret | JWT via API key or app login |
| Token lifetime | ~80 minutes | 24 hours |
| Token refresh | `/auth/renewaccesstoken` | `/api/Auth/validate` |
| Auth header | `Bearer {token}` | `Bearer {token}` |
| Cost | Free (included with account) | $14.50-29/mo subscription |

### API Architecture

| | Tradovate | ProjectX |
|-|-----------|----------|
| HTTP methods | Mixed (GET, POST, PUT, DELETE) | ALL POST (except /Status/ping) |
| Rate limits | Per-token, shared across accounts | 200 req/60s (50/30s for history) |
| WebSocket for orders | Custom protocol (never worked for us) | SignalR (functional for real-time events) |
| Position close | Market order on opposite side | Dedicated `/Position/closeContract` endpoint |
| Partial close | Reduce position via opposing order | Dedicated `/Position/partialCloseContract` |

### What ProjectX Does NOT Have (vs Tradovate)

1. **Multi-leg take profit** -- Cannot split TP into multiple targets with different quantities in a single bracket order
2. **Break-even orders** -- No native break-even mechanism
3. **autoBreakEven field** -- Does not exist
4. **orderStrategy/startOrderStrategy** -- Uses simpler `Order/place` with bracket fields instead
5. **Numeric contract IDs** -- Uses string-based contract IDs
6. **Signed position quantity** -- Uses separate `size` (unsigned) + `type` (direction)

### What ProjectX Has That Tradovate Does NOT

1. **Dedicated position close endpoints** -- `/Position/closeContract` and `/partialCloseContract`
2. **Inline bracket fields** -- `takeProfitBracket`/`stopLossBracket` directly on order placement (simpler than Tradovate's strategy mechanism)
3. **JoinBid / JoinAsk order types** -- Queue at best bid/ask automatically
4. **tickValue on contract object** -- Directly available (Tradovate requires separate product lookup)
5. **Reliable Order/modify** -- Works for bracket-managed orders (Tradovate's is unreliable)
6. **Simpler auth model** -- Single API key, 24-hour token, no client ID/secret dance

---

## Production Gotchas

These are lessons learned from the Just Trades production deployment:

1. **Live URLs are DEAD** -- Use demo URLs (`gateway-api-demo.s2f.projectx.com`) for ALL accounts including funded/live
2. **Contract matching needs str()** -- `contractId` is a string; always use `str()` on both sides of comparison
3. **Trailing stop uses unsigned ticks** -- Do NOT apply negative sign like fixed stop; platform determines direction from position side
4. **Password auth doesn't work for third-party apps** -- MUST use API key auth with `loginKey`
5. **TopstepX has different URL structure** -- Base URL already includes `/api` (`https://api.topstepx.com/api`), so don't double-add it
6. **API Key subscription required** -- $14.50/month per user, separate from the trading account itself
7. **All responses wrapped in success/errorCode/errorMessage** -- Always check the `success` boolean field, not just HTTP status
8. **ProjectX parity features are UNTESTED** -- Deployed to production but never confirmed with real signals (commit `c9f0a3d`)
9. **Position field names may vary** -- Swagger spec says `size`/`averagePrice`/`type`, but some older code references `netPos`/`netPrice` -- verify against actual API responses
10. **customTag must be unique per account** -- Reusing a customTag value may cause order rejection
11. **HTTP 200 does NOT mean success** -- The API returns 200 for logical failures too; always check `success` field in the JSON body

---

## Complete Endpoint Reference

All 19 endpoints in the ProjectX Gateway API (from Swagger spec):

| # | Method | Path | Operation ID | Description |
|---|--------|------|-------------|-------------|
| 1 | POST | `/api/Auth/loginKey` | Auth_LoginKey | Authenticate with API key |
| 2 | POST | `/api/Auth/loginApp` | Auth_LoginApp | Authenticate as registered application |
| 3 | POST | `/api/Auth/validate` | Auth_Validate | Validate/refresh session token |
| 4 | POST | `/api/Auth/logout` | Auth_Logout | End session |
| 5 | POST | `/api/Account/search` | Account_SearchAccounts | List trading accounts |
| 6 | POST | `/api/Contract/search` | Contract_SearchContracts | Search contracts by text (max 20 results) |
| 7 | POST | `/api/Contract/searchById` | Contract_SearchContractById | Get single contract by ID |
| 8 | POST | `/api/Contract/available` | Contract_AvailableContracts | List all available contracts |
| 9 | POST | `/api/Order/place` | Order_PlaceOrder | Place a new order (with optional brackets) |
| 10 | POST | `/api/Order/cancel` | Order_CancelOrder | Cancel an existing order |
| 11 | POST | `/api/Order/modify` | Order_ModifyOrder | Modify an existing order |
| 12 | POST | `/api/Order/search` | Order_SearchOrders | Search orders by time range |
| 13 | POST | `/api/Order/searchOpen` | Order_SearchOpenOrders | Get all open/working orders |
| 14 | POST | `/api/Position/searchOpen` | Position_SearchOpenPositions | Get open positions |
| 15 | POST | `/api/Position/closeContract` | Position_CloseContractPosition | Close entire position at market |
| 16 | POST | `/api/Position/partialCloseContract` | Position_PartialCloseContractPosition | Partially close position at market |
| 17 | POST | `/api/Trade/search` | Trade_SearchHalfTurnTrades | Search trade/fill history |
| 18 | POST | `/api/History/retrieveBars` | History_GetBars | Get historical OHLCV bars |
| 19 | GET | `/api/Status/ping` | Status_Ping | Health check |

---

## Community Resources

### Official Documentation
- [ProjectX Gateway API Docs](https://gateway.docs.projectx.com/) -- Official REST API documentation
- [ProjectX Help Center](https://help.projectx.com/) -- Platform guides and settings documentation
- [TopstepX API Access Guide](https://help.topstep.com/en/articles/11187768-topstepx-api-access) -- Setup instructions for TopstepX
- [Connection URLs](https://gateway.docs.projectx.com/docs/getting-started/connection-urls/) -- Official base URLs

### Python SDKs
- [project-x-py (PyPI)](https://pypi.org/project/project-x-py/) -- Full-featured async SDK with order management, v3.3.4
- [projectx-api (PyPI)](https://pypi.org/project/projectx-api/) -- Async SDK by rundef, supports `Environment.TOPSTEP_X`
- [tsxapi4py (GitHub)](https://github.com/mceesincus/tsxapi4py) -- TopstepX-specific Python wrapper with Pydantic v2, SignalR streaming

### GitHub
- [TopstepX GitHub Topic](https://github.com/topics/topstepx) -- Community projects tagged with topstepx

### Third-Party Integration Docs
- [PickMyTrade - ProjectX Setup Guide](https://docs.pickmytrade.io/docs/connect-projectx-to-topstep-api/) -- Step-by-step connection guide
- [PickMyTrade - OCO Brackets in TopstepX](https://docs.pickmytrade.io/docs/oco-brackets-in-topstepx/) -- Bracket order configuration
- [TradeSyncer - ProjectX Bracket Orders](https://help.tradesyncer.com/en/articles/11746420-projectx-bracket-orders-explained-position-brackets-vs-auto-oco-brackets) -- Position Brackets vs Auto-OCO
- [TradersPost - ProjectX Docs](https://docs.traderspost.io/docs/all-supported-connections/projectx) -- TradersPost integration reference

### Community
- Topstep Discord `#api-trading` channel -- API discussion and Q&A
- [ProjectX API Q&A Events](https://x.com/Topstep/status/1925211684018237593) -- Topstep hosts periodic Discord Q&A sessions

### Swagger / OpenAPI
- [TopstepX Swagger Spec](https://api.topstepx.com/swagger/v1/swagger.json) -- Machine-readable API definition (JSON)
- Swagger UI available at `https://api.topstepx.com/swagger/index.html` and `https://gateway-api-demo.s2f.projectx.com/swagger/index.html`

---

## Just Trades Integration Notes

These are specific to our implementation in `/phantom_scraper/projectx_integration.py`.

### URL Construction in Our Code

```python
# TopstepX: base_url = https://api.topstepx.com/api (already includes /api)
if self.prop_firm == 'topstep':
    url = f"{self.base_url}/{endpoint}"     # https://api.topstepx.com/api/Order/place

# Generic ProjectX: base_url = https://gateway-api-demo.s2f.projectx.com (no /api)
else:
    url = f"{self.base_url}/api/{endpoint}" # https://gateway-api-demo.s2f.projectx.com/api/Order/place
```

### Helper Methods in ProjectXIntegration

| Method | Returns | Notes |
|--------|---------|-------|
| `create_market_order(account_id, contract_id, side, quantity)` | Order dict | Accepts string sides ("Buy"/"Sell") |
| `create_limit_order(account_id, contract_id, side, quantity, price)` | Order dict | For TP orders |
| `create_stop_order(account_id, contract_id, side, quantity, stop_price)` | Order dict | For SL orders |
| `create_stop_limit_order(account_id, contract_id, side, quantity, stop_price, limit_price)` | Order dict | Combined stop+limit |
| `create_market_order_with_brackets(account_id, contract_id, side, quantity, tp_ticks, sl_ticks, trailing_stop)` | Order dict with brackets | Main bracket method |
| `create_limit_order_with_brackets(account_id, contract_id, side, quantity, price, tp_ticks, sl_ticks)` | Order dict with brackets | Limit entry + brackets |
| `place_order(order_data)` | Response dict | Submits any order dict to API |
| `cancel_order(account_id, order_id)` | bool | Cancels single order |
| `modify_order(order_id, new_price, new_size, new_stop_price)` | Response dict | Modifies existing order |
| `get_positions(account_id)` | List[dict] | Open positions |
| `get_orders(account_id, include_filled)` | List[dict] | Open or historical orders |
| `get_accounts(only_active)` | List[dict] | Trading accounts |
| `search_contracts(search_text, live)` | List[dict] | Contract search |
| `liquidate_position(account_id, contract_id)` | Response dict | Close entire position |
| `validate_session()` | bool | Refresh token |

### ProjectX API Methods Used in do_trade_projectx()

| Method | Purpose | Where Called |
|--------|---------|-------------|
| `get_positions(account_id)` | Check existing position for DCA/opposite detection | Position check block |
| `get_orders(account_id)` | Find working orders to cancel on DCA | DCA cancel+replace |
| `cancel_order(account_id, order_id)` | Cancel old TP/SL before placing new ones | DCA cancel+replace |
| `create_stop_order(...)` | Place DCA SL (fixed) | DCA SL block |
| `create_market_order_with_brackets(...)` | First entry with TP + SL | First entry block |
| `place_order(order_data)` | Submit any order to API | All order placements |

### Not Implemented for ProjectX (as of Feb 18, 2026)

- Break-even monitoring daemon
- Multi-leg TP (splitting position across multiple limit orders with OCO linking)
- `apply_risk_orders` equivalent (Tradovate-specific, needs ProjectX rewrite)
- Position reconciliation daemon (class exists as `ProjectXPositionSync` but not wired into main loop)
- Multiplier scaling verification for ProjectX bracket quantities

### Prop Firm Endpoint Mapping

| Firm | API Base | Notes |
|------|----------|-------|
| TopstepX | `https://api.topstepx.com/api` | Base URL already includes `/api` |
| Other ProjectX firms | `https://gateway-api-demo.s2f.projectx.com` | Needs `/api` prefix on endpoints |
| All firms (password auth) | `https://userapi-demo.s2f.projectx.com` | Generic user API |

---

*Source: projectx_integration.py @ /Users/mylesjadwin/just-trades-platform/phantom_scraper/projectx_integration.py*
*Swagger: https://api.topstepx.com/swagger/v1/swagger.json*
*Official docs: https://gateway.docs.projectx.com/*
*Python SDK docs: https://project-x-py.readthedocs.io/en/stable/api/trading.html*
