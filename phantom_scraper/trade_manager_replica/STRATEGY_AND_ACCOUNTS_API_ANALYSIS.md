# Strategy & Accounts API Analysis

## ✅ Success! API Calls & WebSocket Messages Captured

**Files Analyzed:**
1. `trade_manager_functionality__user_strat_1762407816800.json` - My Recorders (Create/Edit Strategy)
2. `trade_manager_functionality__user_at_strat_1762407941512.json` - My Trader (Create/Edit Strategy)
3. `trade_manager_functionality__user_at_accnts_1762407884646.json` - Account Management (WebSocket messages!)

---

## 📡 API Endpoints Identified

### 1. **GET /api/auth/check-auth/**
**Purpose**: Verify user authentication status  
**Used On**: Both strategy pages  
**Response Structure**:
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
    "sessionId": "2btylfl2bo4w9lqptbroqvtb103q561y"
  }
}
```
**Status**: 200 OK

---

### 2. **GET /api/strategies/**
**Purpose**: Get list of all strategies  
**Query Parameters**:
- `val` (optional): Filter type (e.g., `DirStrat`)

**Sample Calls**:
- `/api/strategies/?val=DirStrat`

**Response Structure**:
```json
{
  "strategies": [
    { "name": "10TICKS-1" },
    { "name": "10TICKS-2" },
    { "name": "18YEAROLDBADDIE" },
    // ... 100+ strategies
  ]
}
```
**Status**: 200 OK

**Key Insights**:
- Returns array of strategy objects with `name` property
- Used to populate strategy dropdowns
- Can be filtered by strategy type (`val` parameter)

---

### 3. **GET /api/strategies/get-strat/** ⭐ NEW ENDPOINT
**Purpose**: Get detailed strategy information  
**Query Parameters**:
- `id`: Strategy ID (e.g., `14330`)

**Sample Calls**:
- `/api/strategies/get-strat/?id=14330`

**Response Structure**:
```json
{
  "id": 14330,
  "Strat_Name": "JADDCAVIXES",
  "Owner": "J.T.M.J",
  "Strat_Type": "DirStrat",
  "Days2Expo": 0,
  "Strike_Offset": 0,
  "Stoploss": 0,
  "Position_Size": 1,
  "Position_Add": 0,
  "TakeProfit": 0
  // ... additional fields
}
```

**Status**: 200 OK

**Key Insights**:
- Used when editing an existing strategy
- Returns full strategy configuration
- Includes all form fields for pre-population

---

### 4. **GET /api/accounts/** ⭐ NEW ENDPOINT
**Purpose**: Get list of all accounts  
**Used On**: My Trader (Create/Edit Strategy)  
**Response Structure**:
```json
[
  {
    "name": "Account Name",
    "accntID": 123,
    "main": true,
    "maxcons": 5,
    "customTicker": "MES1!",
    "mult": 1.0,
    "enabled": true
  },
  // ... more accounts
]
```

**Status**: 200 OK

**Key Insights**:
- Returns array of account objects
- Used for account routing table in strategy creation
- Each account has:
  - `name`: Display name
  - `accntID`: Unique identifier
  - `main`: Boolean (is main account?)
  - `maxcons`: Maximum concurrent positions
  - `customTicker`: Default ticker symbol
  - `mult`: Multiplier
  - `enabled`: Boolean (is account enabled?)

---

### 5. **GET /api/trades/tickers/**
**Purpose**: Get available tickers for a strategy  
**Query Parameters**:
- `strat` (optional): Strategy name (e.g., `JADDCAVIX`)

**Sample Calls**:
- `/api/trades/tickers/?strat=JADDCAVIX`
- `/api/trades/tickers/?strat=` (empty, get all)

**Response Structure**:
```json
{
  "tickers": [
    "MES1!",
    "MNQ1!",
    "NQ1!",
    // ... more tickers
  ]
}
```

**Status**: 200 OK

**Key Insights**:
- Returns available ticker symbols
- Can be filtered by strategy name
- Used to populate ticker dropdowns

---

### 6. **GET /api/trades/timeframes/**
**Purpose**: Get available timeframes  
**Query Parameters**:
- `strat` (optional): Strategy name

**Sample Calls**:
- `/api/trades/timeframes/?strat=`
- `/api/trades/timeframes/?strat=JADDCAVIX`

**Response Structure**:
```json
{
  "timeframes": [
    "1m",
    "5m",
    "15m",
    "1h",
    "4h",
    "1d"
    // ... more timeframes
  ]
}
```

**Status**: 200 OK

**Key Insights**:
- Returns available timeframe options
- Can be filtered by strategy name
- Used to populate timeframe dropdowns

---

## 🔌 WebSocket Messages (Account Management)

**URL**: `wss://trademanagergroup.com:5000/ws`  
**Protocol**: None specified

### Message Flow:

1. **Connection Open**: Client connects to WebSocket

2. **Authentication Message** (Client → Server):
```json
{
  "type": "AUTH",
  "user": "J.T.M.J",
  "token": "2btylfl2bo4w9lqptbroqvtb103q561y"
}
```

3. **Authentication Response** (Server → Client):
```json
{
  "data": "✅ Server Connection Established Successfully!"
}
```

4. **Account Setup Request** (Client → Server):
```json
{
  "type": "ACCSETUP",
  "id": 1491,
  "user": "J.T.M.J"
}
```

5. **Account Setup Response** (Server → Client):
```json
{
  "type": "ACCSETUP_COMPLETE",
  "status": "Success"
}
```

6. **Connection Close**: WebSocket closes after setup completes

### Key Observations:

- **One-shot connection**: WebSocket opens, performs operation, closes
- **Authentication required**: Must send AUTH message first
- **Account setup**: Uses account ID to trigger setup process
- **Multiple connections**: Multiple WebSocket connections observed (one per account setup?)
- **Close code**: 1005 (no status code received)

---

## 🔍 Key Insights

### 1. **Strategy Pages Use Different Endpoints**
- **My Recorders** (`/user/strats`):
  - Uses `/api/strategies/get-strat/` to load existing strategy
  - No accounts endpoint (recorders don't use account routing)
  
- **My Trader** (`/user/at/strats`):
  - Uses `/api/accounts/` to load accounts for routing
  - Same strategy endpoints otherwise

### 2. **Account Management Uses WebSockets**
- No REST API calls for account setup
- Uses WebSocket for real-time account configuration
- Each account setup triggers a new WebSocket connection

### 3. **Filter Parameters**
- Strategies can be filtered by type (`val=DirStrat`)
- Tickers can be filtered by strategy (`strat=JADDCAVIX`)
- Timeframes can be filtered by strategy (`strat=JADDCAVIX`)

### 4. **Authentication**
- All pages check auth status on load
- Uses session-based authentication (`sessionId` in response)

---

## 🔧 Implementation Notes

### Current Components:

1. **CreateStrategy.jsx**:
   - Missing: `/api/strategies/get-strat/` call for editing
   - Missing: `/api/accounts/` call for account routing (My Trader only)
   - Missing: `/api/trades/tickers/` and `/api/trades/timeframes/` calls

2. **AccountManagement.jsx**:
   - Missing: WebSocket implementation for account setup
   - Currently uses REST API (needs to be changed to WebSocket)

### Required Updates:

1. **Add Strategy API Endpoints** (`frontend/src/services/api.js`):
   ```javascript
   strategiesAPI: {
     getAll: (params = {}) => {
       const queryString = new URLSearchParams(params).toString();
       return axios.get(`/api/strategies/${queryString ? '?' + queryString : ''}`);
     },
     getById: (id) => {
       return axios.get(`/api/strategies/get-strat/?id=${id}`);
     },
     // ... create, update, delete
   }
   ```

2. **Add Accounts API** (`frontend/src/services/api.js`):
   ```javascript
   accountsAPI: {
     getAll: () => {
       return axios.get('/api/accounts/');
     }
   }
   ```

3. **Add Tickers/Timeframes API** (`frontend/src/services/api.js`):
   ```javascript
   tradesAPI: {
     // ... existing methods
     getTickers: (strat = '') => {
       return axios.get(`/api/trades/tickers/?strat=${strat}`);
     },
     getTimeframes: (strat = '') => {
       return axios.get(`/api/trades/timeframes/?strat=${strat}`);
     }
   }
   ```

4. **Update CreateStrategy Component**:
   - Load strategy data when editing (use `get-strat` endpoint)
   - Load accounts list for My Trader version
   - Load tickers and timeframes dynamically
   - Pre-populate form fields from strategy data

5. **Implement WebSocket for Account Setup**:
   - Create WebSocket service for account management
   - Connect to `wss://trademanagergroup.com:5000/ws`
   - Send AUTH message with user and token
   - Wait for authentication confirmation
   - Send ACCSETUP message with account ID
   - Wait for ACCSETUP_COMPLETE response
   - Close connection

---

## 📝 Next Steps

1. **Update API Service**:
   - Add `get-strat` endpoint
   - Add `accounts` endpoint
   - Add `tickers` and `timeframes` endpoints

2. **Update CreateStrategy Component**:
   - Load strategy when editing
   - Load accounts for routing table
   - Load tickers/timeframes dynamically

3. **Implement WebSocket Service**:
   - Create WebSocket connection handler
   - Implement authentication flow
   - Implement account setup flow
   - Handle connection errors

4. **Update Backend**:
   - Implement `/api/strategies/get-strat/` endpoint
   - Implement `/api/accounts/` endpoint
   - Implement WebSocket server for account setup

5. **Test**:
   - Test strategy loading
   - Test account loading
   - Test WebSocket account setup
   - Test ticker/timeframe loading

---

## 🎯 Summary

This extraction provides:
- ✅ New API endpoints for strategies and accounts
- ✅ Complete WebSocket message flow for account setup
- ✅ Response structures for all endpoints
- ✅ Query parameter patterns
- ✅ Authentication flow details

This gives us the exact API contract needed to implement full functionality!

