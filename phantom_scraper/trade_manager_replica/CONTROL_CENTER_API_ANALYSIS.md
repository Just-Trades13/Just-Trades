# Control Center API Analysis

## ✅ Success! API Calls & WebSocket Messages Captured

**File**: `trade_manager_functionality__user_at_controls_1762408049757.json`  
**Page**: `/user/at/controls` (Control Center)  
**Timestamp**: 2025-11-06T05:47:15.964Z

**Total API Calls**: 6  
**Total WebSocket Connections**: 2

---

## 📡 API Endpoints Identified

### 1. **GET /api/strategies/?style=at**
**Purpose**: Get all active trading (AT) strategies  
**Query Parameters**:
- `style`: Always `at` (for active trading strategies)

**Sample Calls**:
- `/api/strategies/?style=at`

**Response Structure**:
```json
[
  {
    "id": 14954,
    "Strat_Name": "JADDCAVIXES",
    "Strat_Type": "Stock",
    "Days2Expo": null,
    "Strike_Offset": null,
    "Stoploss": "500",
    "Position_Size": "1",
    "Position_Add": "1",
    "TakeProfit": ["10"],
    "Trim": ["0"],
    "TPSL_Units": "Ticks",
    "DirStrat": "",
    "SubTicker": "ALL",
    "SubTimeFrame": "ALL",
    "Enabled": false,
    "Owner": "J.T.M.J",
    "Accounts": {
      "1491": {
        "L465530": [0, "", 2]
      },
      "1493": {
        "L667523": [0, "", 1]
      }
      // ... more account mappings
    },
    "Alternate_Name": "REAL_ACCOUNTS_JADDCAVIXES"
  },
  // ... more strategies
]
```

**Status**: 200 OK

**Key Insights**:
- Returns array of strategy objects (not wrapped in `{strategies: [...]}`)
- Each strategy includes full configuration
- `Accounts` object maps account IDs to account-specific settings
- Used to populate the "Live Strategies" panel
- Called on page load and after strategy updates

---

### 2. **GET /api/trades/open/**
**Purpose**: Get all open trades  
**Query Parameters**: None

**Sample Calls**:
- `/api/trades/open/`

**Response Structure**:
```json
[]
```

**Status**: 200 OK

**Key Insights**:
- Returns empty array when no open trades
- Used to display open positions in Control Center
- Called on page load and after actions

---

### 3. **POST /api/strategies/update/** ⭐ NEW ENDPOINT
**Purpose**: Update strategy settings  
**Content-Type**: `application/json`

**Request Body Structure**:
```json
{
  "id": 14995,
  "Enabled": false,
  "Owner": "J.T.M.J"
}
```

**Sample Calls**:
- `POST /api/strategies/update/` with body: `{"id":14995,"Enabled":false,"Owner":"J.T.M.J"}`
- `POST /api/strategies/update/` with body: `{"id":14994,"Enabled":false,"Owner":"J.T.M.J"}`

**Response Structure**:
```json
{
  "message": "Strategy updated successfully.",
  "id": 14995,
  "webhook_key": "IIRBECUJVCNWOCIUZZGASSMFU"
}
```

**Status**: 200 OK

**Key Insights**:
- Used to enable/disable strategies
- Minimal payload: only sends `id`, `Enabled`, and `Owner`
- Returns success message, strategy ID, and webhook key
- Called when user toggles strategy enable/disable switch
- After update, page refreshes strategy list (GET /api/strategies/?style=at)

---

## 🔌 WebSocket Messages

**URL**: `wss://trademanagergroup.com:5000/ws`  
**Protocol**: None specified

### WebSocket Connection 1:
**Purpose**: Appears to be for real-time updates (connection opened but closed quickly)

**Message Flow**:
1. **Client → Server (AUTH)**:
```json
{
  "type": "AUTH",
  "user": "J.T.M.J",
  "token": "2btylfl2bo4w9lqptbroqvtb103q561y"
}
```

2. **Connection Closed**: Code 1005 (no status code received)

**Note**: This connection didn't receive a response - likely closed before authentication completed.

---

### WebSocket Connection 2:
**Purpose**: Real-time connection for live updates

**Message Flow**:
1. **Client → Server (AUTH)**:
```json
{
  "type": "AUTH",
  "user": "J.T.M.J",
  "token": "2btylfl2bo4w9lqptbroqvtb103q561y"
}
```

2. **Server → Client (AUTH Response)**:
```json
{
  "data": "✅ Server Connection Established Successfully!"
}
```

3. **Connection Remains Open**: For receiving real-time updates

**Key Insights**:
- WebSocket stays open for live updates
- Used for real-time trade notifications, strategy status changes, etc.
- Authentication required before receiving updates

---

## 🔍 Key Observations

### 1. **Strategy Update Flow**
1. User toggles strategy enable/disable switch
2. `POST /api/strategies/update/` called with minimal payload
3. Server responds with success and webhook key
4. Page refreshes strategy list: `GET /api/strategies/?style=at`
5. Strategy list updates to show new enabled/disabled state

### 2. **Strategy Filtering**
- `?style=at` parameter filters for active trading strategies only
- Different from My Recorders which uses `?val=DirStrat`

### 3. **Account Mapping Structure**
- Strategies include `Accounts` object with nested structure:
  - Key: Account ID (e.g., "1491")
  - Value: Object with account-specific IDs (e.g., "L465530")
  - Account-specific value: Array `[0, "", 2]` (likely: [position, ticker, multiplier])

### 4. **WebSocket Usage**
- WebSocket connection established for real-time updates
- Connection persists after authentication
- Used for live trade notifications, strategy status changes, etc.

---

## 🔧 Implementation Notes

### Current ControlCenter Component:
- Missing: Strategy update endpoint
- Missing: WebSocket connection for real-time updates
- Has: Strategy list display (but needs proper data structure)

### Required Updates:

1. **Add Strategy Update API** (`frontend/src/services/api.js`):
   ```javascript
   strategiesAPI: {
     // ... existing methods
     update: (strategyId, updates) => {
       return axios.post('/api/strategies/update/', {
         id: strategyId,
         ...updates,
         Owner: getCurrentUser().username // or from auth context
       });
     }
   }
   ```

2. **Update ControlCenter Component** (`frontend/src/pages/ControlCenter.jsx`):
   - Load strategies on mount: `GET /api/strategies/?style=at`
   - Handle enable/disable toggle: Call `POST /api/strategies/update/`
   - Refresh strategy list after update
   - Display strategy details (enabled state, accounts, etc.)

3. **Implement WebSocket Service** (`frontend/src/services/websocket.js`):
   - Connect to `wss://trademanagergroup.com:5000/ws`
   - Send AUTH message with user and token
   - Wait for authentication confirmation
   - Keep connection open for real-time updates
   - Handle incoming messages (trade updates, strategy status changes, etc.)
   - Reconnect on disconnect

4. **Update Backend**:
   - Implement `POST /api/strategies/update/` endpoint
   - Accept `id`, `Enabled`, `Owner` in request body
   - Update strategy in database
   - Return success message, ID, and webhook key
   - Implement WebSocket server for real-time updates
   - Broadcast strategy status changes to connected clients

---

## 📝 Next Steps

1. **Update API Service**:
   - Add `update()` method to strategies API
   - Add `getByStyle()` method for filtering by style

2. **Update ControlCenter Component**:
   - Load strategies with `?style=at` filter
   - Implement enable/disable toggle functionality
   - Refresh strategy list after updates
   - Display strategy details properly

3. **Implement WebSocket**:
   - Create WebSocket service
   - Connect on Control Center page load
   - Handle authentication
   - Listen for real-time updates
   - Update UI when messages received

4. **Test**:
   - Test strategy enable/disable
   - Test WebSocket connection
   - Test real-time updates
   - Test strategy list refresh

---

## 🎯 Summary

This extraction provides:
- ✅ Strategy update endpoint with exact request/response structure
- ✅ Strategy list endpoint with `style=at` filter
- ✅ WebSocket connection flow for real-time updates
- ✅ Complete strategy data structure including account mappings
- ✅ Update flow sequence (POST → refresh GET)

This gives us the exact API contract needed to implement full Control Center functionality!

