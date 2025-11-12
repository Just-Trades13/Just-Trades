# API Endpoints Documentation

Based on frontend code analysis and expected functionality from Trade Manager.

## Authentication Endpoints

### POST /api/auth/login/
**Purpose**: User login  
**Request Body**:
```json
{
  "username": "string",
  "password": "string"
}
```
**Response**:
```json
{
  "success": true,
  "user": {
    "username": "string",
    "email": "string",
    "admin": boolean,
    "DiscordID": "string",
    "access": "full",
    "signed": true,
    "is_email_verified": boolean,
    "sessionId": "string"
  },
  "csrf_token": "string"
}
```

### POST /api/auth/logout/
**Purpose**: User logout  
**Response**: `{ "success": true }`

### GET /api/auth/check-auth/
**Purpose**: Check if user is authenticated  
**Response**: `{ "isAuthenticated": boolean, "user": {...} }`

## Dashboard Endpoints

### GET /api/dashboard/summary/
**Purpose**: Get dashboard summary statistics  
**Headers**: `X-CSRFToken: <token>`  
**Response**:
```json
{
  "total_strategies": 0,
  "active_positions": 0,
  "total_pnl": 0.0,
  "today_pnl": 0.0
}
```

### GET /api/dashboard/analytics/
**Purpose**: Get dashboard analytics  
**Query Params**: `?startDate=...&endDate=...`  
**Response**: Analytics data object

## Trades Endpoints

### GET /api/trades/
**Purpose**: Get all trades  
**Query Params**:
- `usageType`: boolean (true)
- `user`: string (optional)
- `strategy`: string (optional)
- `symbol`: string (optional)
- `timeframe`: string (optional)
- `dateRange`: object (optional)

**Response**:
```json
{
  "trades": [
    {
      "id": "string",
      "created_at": "ISO date",
      "strategy_name": "string",
      "symbol": "string",
      "side": "BUY|SELL",
      "quantity": number,
      "entry_price": number,
      "exit_price": number,
      "pnl": number,
      "status": "open|closed"
    }
  ]
}
```

### GET /api/trades/open/
**Purpose**: Get open trades only  
**Query Params**: Same as `/api/trades/`  
**Response**: `{ "trades": [...] }`

### GET /api/trades/tickers/
**Purpose**: Get available tickers  
**Query Params**: `?strat=<strategy_name>`  
**Response**: `{ "tickers": ["MES1!", "MYM1!", ...] }`

### GET /api/trades/timeframes/
**Purpose**: Get available timeframes  
**Query Params**: `?strat=<strategy_name>`  
**Response**: `{ "timeframes": ["15s", "1m", "5m", ...] }`

### POST /api/trades/execute/
**Purpose**: Execute a trade  
**Request Body**:
```json
{
  "strategy": "string",
  "ticker": "string",
  "side": "BUY|SELL",
  "quantity": number,
  "price": number
}
```
**Response**: `{ "success": true, "trade_id": "string" }`

## Strategies Endpoints

### GET /api/strategies/
**Purpose**: Get all strategies  
**Query Params**:
- `val`: string (optional)
- `style`: string (optional)
- `manual`: boolean (optional)

**Response**: `{ "strategies": [...] }`

### GET /api/strategies/get-strat/
**Purpose**: Get specific strategy  
**Query Params**: `?strat=<name>&at=<boolean>`  
**Response**: Strategy object

### POST /api/strategies/
**Purpose**: Create new strategy  
**Request Body**: Strategy data object  
**Response**: `{ "success": true, "strategy": {...} }`

### PUT /api/strategies/{id}/
**Purpose**: Update strategy  
**Request Body**: Strategy data object  
**Response**: `{ "success": true }`

### DELETE /api/strategies/{id}/
**Purpose**: Delete strategy  
**Response**: `{ "success": true }`

## Accounts Endpoints

### GET /api/accounts/get-all-at-accounts/
**Purpose**: Get all accounts  
**Response**: `{ "accounts": [...] }`

### POST /api/accounts/add-tradovate/
**Purpose**: Add Tradovate account  
**Request Body**: Account credentials  
**Response**: `{ "success": true, "account": {...} }`

### POST /api/accounts/test-tradovate-connection/
**Purpose**: Test Tradovate connection  
**Request Body**: Account credentials  
**Response**: `{ "success": true, "connected": boolean }`

### PUT /api/accounts/{id}/
**Purpose**: Update account  
**Request Body**: Account data  
**Response**: `{ "success": true }`

### DELETE /api/accounts/{id}/
**Purpose**: Delete account  
**Response**: `{ "success": true }`

### POST /api/accounts/{id}/refresh/
**Purpose**: Refresh account subaccounts  
**Response**: `{ "success": true }`

## Profiles Endpoints

### GET /api/profiles/get-limits/
**Purpose**: Get user limits  
**Response**: Limits object

### GET /api/profiles/get-stat-config/
**Purpose**: Get statistics configuration  
**Response**: Configuration object

### POST /api/profiles/update-stat-config/
**Purpose**: Update statistics configuration  
**Request Body**: Configuration object  
**Response**: `{ "success": true }`

### GET /api/profiles/get-favorites/
**Purpose**: Get user favorites  
**Response**: `{ "favorites": [...] }`

### POST /api/profiles/set-favorites/
**Purpose**: Set user favorites  
**Request Body**: `{ "favorites": [...] }`  
**Response**: `{ "success": true }`

### GET /api/profiles/get-widget-info/
**Purpose**: Get widget information  
**Query Params**: Various filters  
**Response**: Widget data object

### GET /api/profiles/details/
**Purpose**: Get user profile details  
**Response**: User profile object

### POST /api/profiles/update-username/
**Purpose**: Update username  
**Request Body**: `{ "username": "string" }`  
**Response**: `{ "success": true }`

### POST /api/profiles/change-password/
**Purpose**: Change password  
**Request Body**: `{ "currentPassword": "string", "newPassword": "string", "confirmPassword": "string" }`  
**Response**: `{ "success": true }`

### POST /api/profiles/toggle-push-notification/
**Purpose**: Toggle push notifications  
**Response**: `{ "success": true, "enabled": boolean }`

### POST /api/profiles/toggle-discord-dm/
**Purpose**: Toggle Discord DMs  
**Response**: `{ "success": true, "enabled": boolean }`

## Recorder Endpoints

### POST /api/recorder/start/{strategyId}/
**Purpose**: Start recording a strategy  
**Response**: `{ "success": true }`

### POST /api/recorder/stop/{strategyId}/
**Purpose**: Stop recording a strategy  
**Response**: `{ "success": true }`

### GET /api/recorder/positions/{strategyId}/
**Purpose**: Get recorder positions  
**Response**: `{ "positions": [...] }`

## Discord Endpoints

### GET /api/discord/oauth/connect/
**Purpose**: Initiate Discord OAuth connection  
**Response**: Redirect to Discord OAuth or connection status

## System Endpoints

### GET /api/system/csrf-token/
**Purpose**: Get CSRF token  
**Response**: `{ "csrf_token": "string" }`

## Common Headers

All requests (except login) require:
- `X-CSRFToken: <token>` (from cookies or `/api/system/csrf-token/`)
- `Cookie: csrftoken=<token>`
- `Content-Type: application/json`

## Authentication

- **Session-based**: Uses sessionId stored in localStorage
- **CSRF Protection**: Token in cookies and headers
- **Credentials**: All requests use `withCredentials: true`

