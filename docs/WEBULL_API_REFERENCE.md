# Webull OpenAPI Reference — Just Trades Platform

> Built from production source code (webull_integration.py)
> Official docs: https://developer.webull.com/api-doc/
> Last verified: Feb 18, 2026

---

## BASE URLs

| Service | URL |
|---------|-----|
| **OpenAPI** | `https://openapi.webull.com` |
| **Legacy API** | `https://api.webull.com/api` |

---

## AUTHENTICATION

### Requirements
- Webull brokerage account with **$5,000+ minimum**
- API access approval (1-2 business days)
- App Key + App Secret from Webull API Management

### Login

```
POST https://openapi.webull.com/openapi/account/token
```

```json
{
    "app_key": "your-app-key",
    "app_secret": "your-app-secret"
}
```

**Response:**
```json
{
    "access_token": "eyJhbG...",
    "expires_in": 86400
}
```

Token valid for **24 hours** (86400 seconds).

### Request Signing (HMAC-SHA256)

All requests must include these headers:
```
Content-Type: application/json
Accept: application/json
x-app-key: {app_key}
x-timestamp: {unix_timestamp_ms}
x-signature: {hmac_sha256}
Authorization: Bearer {access_token}
```

Signature formula:
```python
message = f"{timestamp}{method}{path}{body}"
signature = hmac.new(app_secret.encode(), message.encode(), hashlib.sha256).hexdigest()
```

---

## CONSTANTS

### Order Types
| Type | Value |
|------|-------|
| Market | `"MARKET"` |
| Limit | `"LIMIT"` |
| Stop | `"STOP"` |
| Stop-Limit | `"STOP_LIMIT"` |
| Trailing Stop | `"TRAILING_STOP"` |

### Order Sides
| Side | Value |
|------|-------|
| Buy | `"BUY"` |
| Sell | `"SELL"` |

### Time in Force
| TIF | Value | Meaning |
|-----|-------|---------|
| Day | `"DAY"` | Expires end of day |
| GTC | `"GTC"` | Good 'til cancelled |
| IOC | `"IOC"` | Immediate or cancel |
| FOK | `"FOK"` | Fill or kill |

**Note:** Webull uses STRINGS for types/sides (like Tradovate), not integers (like ProjectX).

---

## ACCOUNT MANAGEMENT

### Get Accounts

```
GET https://openapi.webull.com/openapi/account/list
```

### Get Account Info

```
GET https://openapi.webull.com/openapi/account/{account_id}
```

---

## ORDER PLACEMENT

### Place Order

```
POST https://openapi.webull.com/trade/order/place
```

```json
{
    "account_id": "ACC123",
    "stock_order": {
        "client_order_id": "jt_1708300000000",
        "side": "BUY",
        "order_type": "MARKET",
        "instrument_id": "INS456",
        "qty": 1,
        "tif": "DAY"
    }
}
```

**For Limit orders, add:**
```json
"limit_price": "150.00"
```

**For Stop orders, add:**
```json
"stop_price": "145.00"
```

**Response (success):**
```json
{
    "success": true,
    "order_id": "ORD789",
    "data": {}
}
```

### Cancel Order

```
POST https://openapi.webull.com/trade/order/cancel
```

```json
{
    "account_id": "ACC123",
    "order_id": "ORD789"
}
```

---

## POSITION MANAGEMENT

### Get Positions

```
GET https://openapi.webull.com/openapi/account/{account_id}/positions
```

### Get Orders

```
GET https://openapi.webull.com/openapi/account/{account_id}/orders?status=WORKING
```

Status filters: `WORKING`, `FILLED`, `CANCELLED`

---

## INSTRUMENT SEARCH

```
GET https://openapi.webull.com/openapi/instrument/search?keyword=AAPL
```

Returns instrument details including `instrument_id` required for placing orders.

---

## KEY DIFFERENCES FROM TRADOVATE/PROJECTX

| Feature | Tradovate | ProjectX | Webull |
|---------|-----------|----------|--------|
| Asset type | Futures | Futures (prop) | Stocks, Options, Futures, Crypto |
| Auth | OAuth credentials | API Key | App Key + Secret (HMAC) |
| Order types | Strings | Integers | Strings |
| Sides | Strings | Integers | Strings |
| Bracket orders | Native (orderStrategy) | Native (takeProfitBracket) | **Not native** — requires separate TP/SL |
| ID field | `orderId` (int) | `orderId` (int) | `order_id` (string) |
| Instrument ref | `symbol` (string) | `contractId` (string) | `instrument_id` (string) |

---

## SUPPORTED ASSET TYPES
- US Stocks & ETFs
- Options
- Futures
- Crypto

---

*Source: webull_integration.py in just-trades-platform/phantom_scraper/*
*Official docs: https://developer.webull.com/api-doc/*
