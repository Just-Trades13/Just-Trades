# Master API Summary - Trade Manager Replica

**Last Updated**: 2025-11-06  
**Status**: Complete API Discovery - Ready for Implementation

---

## 📊 API Endpoints Overview

### ✅ **Authentication & System** (3 endpoints)
### ✅ **Dashboard** (6 endpoints)
### ✅ **Strategies** (6 endpoints)
### ✅ **Accounts** (1 endpoint + WebSocket)
### ✅ **Trades** (4 endpoints)
### ✅ **Profiles** (5 endpoints)
### ✅ **Settings** (Expected - not captured yet)

**Total Discovered**: 25+ endpoints

---

## 🔐 Authentication & System

### 1. **POST /api/auth/login/**
**Status**: ✅ Complete  
**Purpose**: User login with reCAPTCHA  
**Request**:
```json
{
  "username": "J.T.M.J",
  "password": "Greens13",
  "captchaToken": "reCAPTCHA_v2_token"
}
```
**Response**:
```json
{
  "user": {
    "username": "J.T.M.J",
    "email": "just.trades.chicago@gmail.com",
    "admin": false,
    "DiscordID": "963881348039340122",
    "access": "full",
    "signed": true,
    "is_email_verified": true
  }
}
```
**Key Points**:
- Requires reCAPTCHA v2 token
- Returns user object (no `success` flag)
- No `sessionId` in response (set via cookie)

---

### 2. **GET /api/auth/check-auth/**
**Status**: ✅ Complete  
**Purpose**: Check authentication status  
**Response**:
```json
{
  "user": {
    "username": "J.T.M.J",
    "email": "just.trades.chicago@gmail.com",
    "admin": false,
    "DiscordID": "963881348039340122",
    "access": "full",
    "signed": true,
    "is_email_verified": true,
    "sessionId": "xvr5dwrjc8maxncrgtm2vk7snr6c1h35"
  }
}
```
**Key Points**:
- Called on every page load
- Returns `sessionId` in response
- Returns 401 if not authenticated

---

### 3. **GET /api/system/csrf-token**
**Status**: ✅ Complete  
**Purpose**: Get CSRF token for API requests  
**Response**:
```json
{
  "csrfToken": "AFCv3Riih2UPg6x2CSwCy6JtEGzNrzgKIIp8GlKTo1gQ6QSJSp8fP955cDEAPhUN"
}
```
**Key Points**:
- Called on app initialization
- Token used in `X-CSRFToken` header
- Required for all POST/PUT/DELETE requests

---

## 📊 Dashboard

### 4. **GET /api/dashboard/summary/**
**Status**: ✅ Complete  
**Purpose**: Get dashboard summary statistics  
**Response**:
```json
{
  "active_positions": 0,
  "today_pnl": 0,
  "total_pnl": 0,
  "total_strategies": 0
}
```

---

### 5. **GET /api/trades/?usageType=true**
**Status**: ✅ Complete  
**Purpose**: Get all trades (with optional filters)  
**Query Parameters**:
- `usageType`: boolean (true for recorded strategies)
- `user`: string (filter by user)
- `strategy`: string (filter by strategy)
- `symbol`: string (filter by symbol)
- `timeframe`: string (filter by timeframe)

**Response**:
```json
{
  "trades": [
    {
      "id": 123,
      "strategy_name": "JADNQ",
      "symbol": "NQ",
      "side": "BUY",
      "quantity": 1,
      "entry_price": 15000.50,
      "exit_price": 15050.00,
      "pnl": 49.50,
      "status": "closed",
      "created_at": "2025-11-06T05:00:00Z"
    }
  ]
}
```

---

### 6. **GET /api/trades/open/?usageType=true**
**Status**: ✅ Complete  
**Purpose**: Get open trades  
**Query Parameters**: Same as `/api/trades/`

**Response**: Same structure as `/api/trades/` but only open positions

---

### 7. **GET /api/profiles/get-widget-info/?usageType=true**
**Status**: ✅ Complete  
**Purpose**: Get dashboard widget statistics  
**Response**:
```json
{
  "cumulativeProfit": 0,
  "wins": 0,
  "losses": 0,
  "winrate": 0,
  "drawdown": 0,
  "roi": 0,
  "avgTiT": 0,
  "maxTiT": 0,
  "minTiT": 0,
  "pf": 0,
  "maxP": 0,
  "avgP": 0,
  "maxL": 0,
  "avgL": 0,
  "maxPos": 0
}
```

---

### 8. **GET /api/profiles/get-favorites**
**Status**: ✅ Complete  
**Purpose**: Get user's favorite strategies/tickers  
**Response**:
```json
{
  "favorites": [
    "VIX1",
    "JADIND30S",
    "JADEVOINDICATOR"
  ]
}
```

---

### 9. **GET /api/profiles/get-stat-config**
**Status**: ✅ Complete  
**Purpose**: Get dashboard statistics configuration  
**Response**: Array with 8 items (stat configuration objects)

---

## 📈 Strategies

### 10. **GET /api/strategies/?style=at&manual=true&val=DirStrat**
**Status**: ✅ Complete  
**Purpose**: Get all strategies with optional filters  
**Query Parameters**:
- `style`: "at" for My Trader strategies
- `manual`: "true" for manual trading strategies
- `val`: Filter value (e.g., "DirStrat" for directional strategy)

**Response**:
```json
{
  "strategies": [
    {
      "id": 14330,
      "name": "JADDCAVIXES",
      "Strat_Type": "Stock",
      // ... full strategy object
    }
  ]
}
```

---

### 11. **GET /api/strategies/get-strat/**
**Status**: ✅ Complete  
**Purpose**: Get single strategy details  
**Query Parameters**: (ID likely in query or path)

**Response**:
```json
{
  "id": 14330,
  "Strat_Name": "JADDCAVIX",
  "Owner": "J.T.M.J",
  "Strat_Type": "Stock",
  "Days2Expo": null,
  "Strike_Offset": null,
  "Stoploss": "0",
  "Position_Size": "2",
  "Position_Add": "2",
  "TakeProfit": ["22"],
  "Trim": ["0"],
  "TradeTrim": "0",
  "TPSL_Units": "Ticks",
  "DirStrat": "",
  "Description": "",
  "Discord_Server": "TRADE_MANAGER",
  "AlgoDriven": false,
  "Private": false,
  "Enabled": true,
  "SubTicker": "ALL",
  "PremiumFilter": 0,
  "SubTimeFrame": "ALL",
  "Accounts": {
    "1": {
      "TM": ["", "", ""]
    }
  },
  "TimeFilter": {
    "stop1": "13:45",
    "stop2": null,
    "start1": "08:45",
    "start2": null
  },
  "IP_Address": "",
  "SLTP_Data": {
    "sl": "0",
    "avgdn": 0,
    "SL_Type": "Fixed",
    "SL_Units": "Price",
    "avgdnAmnt": 1,
    "avgdnType": "Ticks",
    "Trim_Units": "Contracts"
  },
  "Recorder": true,
  "Manual": false,
  "Discord_Channel": "",
  "Lock": null,
  "Profit": "612.50",
  "Delay_Add": "1",
  "Maxcons": "0",
  "UseLimits": false,
  "Alternate_Name": "",
  "Linked_Strat": "",
  "Inverse": false,
  "IgnoreAlgoSpecs": false,
  "Leverage": "1"
}
```

---

### 12. **POST /api/strategies/create/**
**Status**: ✅ Complete  
**Purpose**: Create new strategy  
**Request Body**: See [STRATEGY_CREATE_API_ANALYSIS.md](./STRATEGY_CREATE_API_ANALYSIS.md)

**Response**:
```json
{
  "message": "Strategy created successfully.",
  "id": 15038,
  "webhook_key": "IIRBECUJVCNWOCIUZZGASSMFU"
}
```

---

### 13. **POST /api/strategies/update/**
**Status**: ✅ Complete  
**Purpose**: Update strategy (enable/disable, partial updates)  
**Request Body**:
```json
{
  "id": 14995,
  "Enabled": false,
  "Owner": "J.T.M.J"
}
```

**Response**:
```json
{
  "message": "Strategy updated successfully.",
  "id": 14995,
  "webhook_key": "webhook_key_here"
}
```

---

### 14. **GET /api/trades/tickers/?strat=**
**Status**: ✅ Complete  
**Purpose**: Get available tickers for a strategy  
**Query Parameters**:
- `strat`: Strategy name (optional, empty string if none)

**Response**:
```json
{
  "tickers": []
}
```

---

### 15. **GET /api/trades/timeframes/?strat=**
**Status**: ✅ Complete  
**Purpose**: Get available timeframes for a strategy  
**Query Parameters**:
- `strat`: Strategy name (optional, empty string if none)

**Response**:
```json
{
  "timeframes": []
}
```

---

## 💼 Accounts

### 16. **GET /api/accounts/**
**Status**: ✅ Complete  
**Purpose**: Get all accounts for user  
**Response**:
```json
[
  {
    "name": "1302271",
    "accntID": "L465530",
    "main": 1491,
    "maxcons": 0,
    "customTicker": "",
    "mult": 1,
    "enabled": false
  }
]
```

---

## 🔌 WebSocket Connections

### 17. **WebSocket: wss://trademanagergroup.com:5000/ws**
**Status**: ✅ Discovered  
**Purpose**: Real-time updates for Control Center, Account Management  

**Authentication Message**:
```json
{
  "type": "AUTH",
  "user": "J.T.M.J",
  "token": "2btylfl2bo4w9lqptbroqvtb103q561y"
}
```

**Account Setup Message**:
```json
{
  "type": "ACCSETUP",
  "id": 1491,
  "user": "J.T.M.J"
}
```

**Response**:
```json
{
  "type": "ACCSETUP_COMPLETE",
  "status": "Success"
}
```

---

## 👤 Profiles

### 18. **POST /api/profiles/update-stat-config/**
**Status**: ✅ Complete  
**Purpose**: Update dashboard statistics configuration  
**Response**:
```json
{
  "message": "Configuration updated successfully"
}
```

---

## ⚠️ Expected Endpoints (Not Yet Captured)

### Settings:
- `PUT /api/profiles/update-username/` - Update username
- `POST /api/profiles/change-password/` - Change password
- `POST /api/profiles/toggle-push-notification/` - Toggle push notifications
- `POST /api/profiles/toggle-discord-dm/` - Toggle Discord DM

### Strategies:
- `PUT /api/strategies/:id/` - Full strategy update (expected)
- `DELETE /api/strategies/:id/` - Delete strategy (expected)

### Accounts:
- `POST /api/accounts/` - Create account (expected)
- `PUT /api/accounts/:id/` - Update account (expected)
- `DELETE /api/accounts/:id/` - Delete account (expected)

### Auth:
- `POST /api/auth/logout/` - Logout (expected)

---

## 📋 Implementation Priority

### Phase 1: Core Authentication ✅
1. ✅ CSRF token endpoint
2. ✅ Login endpoint
3. ✅ Auth check endpoint
4. ⚠️ Logout endpoint (expected)

### Phase 2: Dashboard ✅
1. ✅ Dashboard summary
2. ✅ Trades (all & open)
3. ✅ Widget info
4. ✅ Favorites
5. ✅ Stat config

### Phase 3: Strategies 🚧
1. ✅ Get strategies (list)
2. ✅ Get single strategy
3. ✅ Create strategy
4. ✅ Update strategy (partial)
5. ⚠️ Update strategy (full)
6. ⚠️ Delete strategy

### Phase 4: Accounts 🚧
1. ✅ Get accounts
2. ⚠️ Create account
3. ⚠️ Update account
4. ⚠️ Delete account
5. ✅ WebSocket connection

### Phase 5: Settings ⏳
1. ⚠️ Update username
2. ⚠️ Change password
3. ⚠️ Toggle notifications

---

## 🔑 Key Implementation Notes

### Authentication:
- All POST/PUT/DELETE requests require CSRF token in `X-CSRFToken` header
- Session managed via cookies
- `sessionId` returned in auth check response

### Field Naming:
- API uses mixed naming: `Strat_Name`, `Position_Size`, `TPSL_Units`
- Frontend should map to these exact names
- Some fields are strings, some are numbers (check examples)

### Nested Objects:
- `Accounts`: `{"account_id": {"TM": ["", "", ""]}}`
- `TimeFilter`: `{"start1": "HH:MM", "stop1": "HH:MM", ...}`
- `SLTP_Data`: Complex stop loss/take profit configuration

### Arrays:
- `TakeProfit`: Array of numbers `[22, 50, 100]`
- `Trim`: Array of numbers `[0, 10, 20]`

### WebSocket:
- Authentication required before sending messages
- Token from `sessionId` in auth check response
- Used for real-time updates in Control Center

---

## 📚 Documentation Files

- [LOGIN_API_ANALYSIS.md](./LOGIN_API_ANALYSIS.md) - Login API details
- [STRATEGY_CREATE_API_ANALYSIS.md](./STRATEGY_CREATE_API_ANALYSIS.md) - Strategy creation
- [NEW_ENDPOINTS_DISCOVERED.md](./NEW_ENDPOINTS_DISCOVERED.md) - New endpoints summary
- [CONTROL_CENTER_API_ANALYSIS.md](./CONTROL_CENTER_API_ANALYSIS.md) - Control Center APIs

---

## 🎯 Next Steps

1. ✅ **API Discovery**: Complete
2. 🚧 **Backend Implementation**: Start implementing endpoints
3. 🚧 **Frontend Integration**: Connect frontend to APIs
4. ⏳ **Testing**: Test each endpoint
5. ⏳ **Form Submissions**: Capture remaining form submissions (low priority)

---

**Ready for Implementation!** 🚀

