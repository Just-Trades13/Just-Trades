# Strategy Create API Analysis

## ✅ Success! Strategy Creation API Captured

**File**: `trade_manager_functionality__user_strat_1762408663571.json`  
**Page**: `/user/strats` (Create/Edit Strategy page)  
**Timestamp**: 2025-11-06T05:57:18.920Z

**Total API Calls**: 9  
**Form Submissions**: 0  
**WebSockets**: 0

---

## 📡 Strategy Creation API Endpoint

### **POST /api/strategies/create/**

**Purpose**: Create a new trading strategy

**Request Body**:
```json
{
  "Strat_Name": "FDSA",
  "Strat_Type": "Stock",
  "Days2Expo": 0,
  "Strike_Offset": 0,
  "Stoploss": 0,
  "Position_Size": 1,
  "Position_Add": 1,
  "TakeProfit": [0],
  "Trim": [0],
  "TradeTrim": 0,
  "TPSL_Units": "Ticks",
  "DirStrat": "",
  "Description": "",
  "Discord_Channel": "",
  "AlgoDriven": false,
  "Private": true,
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
    "start1": null,
    "stop1": null,
    "start2": null,
    "stop2": null
  },
  "SLTP_Data": {
    "avgdn": 0,
    "avgdnAmnt": 1,
    "avgdnType": "Ticks",
    "SL_Type": "Fixed",
    "SL_Units": "Ticks",
    "Trim_Units": "Contracts"
  },
  "Recorder": true,
  "Manual": false,
  "Delay_Add": 1,
  "Maxcons": 0,
  "Linked_Strat": "",
  "Alternate_Name": "",
  "Inverse": false,
  "IgnoreAlgoSpecs": false,
  "Leverage": 1
}
```

**Success Response (200)**:
```json
{
  "message": "Strategy created successfully.",
  "id": 15038,
  "webhook_key": "IIRBECUJVCNWOCIUZZGASSMFU"
}
```

**Key Fields Explanation**:

#### Basic Strategy Info:
- `Strat_Name`: Strategy name (required, uppercase)
- `Strat_Type`: Type of strategy - "Stock", "Futures", "Options", etc.
- `Description`: Optional description
- `Alternate_Name`: Alternative name for the strategy
- `Discord_Channel`: Discord channel for notifications

#### Position Management:
- `Position_Size`: Initial position size (number of contracts/shares)
- `Position_Add`: Additional position size (for scaling in)
- `Delay_Add`: Delay before adding position (seconds/minutes)
- `Maxcons`: Maximum contracts/positions allowed (0 = unlimited)

#### Stop Loss & Take Profit:
- `Stoploss`: Stop loss value
- `TakeProfit`: Array of take profit levels (e.g., `[22, 50, 100]`)
- `Trim`: Array of trim levels (reduce position at these profit levels)
- `TradeTrim`: Trade trim value
- `TPSL_Units`: Units for TP/SL - "Ticks", "Price", "Percent", etc.

#### SLTP Advanced Data:
- `SLTP_Data.avgdn`: Average down value
- `SLTP_Data.avgdnAmnt`: Average down amount
- `SLTP_Data.avgdnType`: Average down type - "Ticks", "Price", etc.
- `SLTP_Data.SL_Type`: Stop loss type - "Fixed", "Trailing", "ATR", etc.
- `SLTP_Data.SL_Units`: Stop loss units
- `SLTP_Data.Trim_Units`: Trim units - "Contracts", "Percent", etc.

#### Options-Specific (if applicable):
- `Days2Expo`: Days to expiration (for options)
- `Strike_Offset`: Strike price offset (for options)

#### Filtering:
- `SubTicker`: Sub-ticker filter - "ALL" or specific ticker
- `SubTimeFrame`: Sub-timeframe filter - "ALL" or specific timeframe
- `PremiumFilter`: Premium filter value (for options)

#### Strategy Linking:
- `DirStrat`: Directional strategy name (for linking to another strategy)
- `Linked_Strat`: Linked strategy name
- `Inverse`: Boolean - inverse the linked strategy signals

#### Account Configuration:
- `Accounts`: Object mapping account IDs to configuration
  - Format: `{"account_id": {"TM": ["", "", ""]}}`
  - TM array appears to be account-specific settings

#### Time Filter:
- `TimeFilter.start1`: Start time for first trading window
- `TimeFilter.stop1`: Stop time for first trading window
- `TimeFilter.start2`: Start time for second trading window (optional)
- `TimeFilter.stop2`: Stop time for second trading window (optional)
- Format: "HH:MM" (24-hour format)

#### Strategy Flags:
- `Recorder`: Boolean - enable recording/tracking
- `Manual`: Boolean - manual trading mode
- `AlgoDriven`: Boolean - algorithm-driven strategy
- `Private`: Boolean - private strategy (not shared)
- `Enabled`: Boolean - strategy enabled/active
- `IgnoreAlgoSpecs`: Boolean - ignore algorithm specifications
- `Leverage`: Number - leverage multiplier (default: 1)

**Status**: 200 OK

**Key Insights**:
- ✅ **Returns strategy ID**: `id` field in response
- ✅ **Returns webhook key**: `webhook_key` for strategy webhooks
- ✅ **Complex nested structure**: Accounts, TimeFilter, SLTP_Data are nested objects
- ✅ **Arrays for TP/Trim**: TakeProfit and Trim are arrays (can have multiple levels)
- ✅ **All fields optional except Strat_Name**: Most fields have defaults

---

## 📋 Supporting APIs

### 1. **GET /api/strategies/?val=DirStrat**
**Purpose**: Get list of strategies (for dropdowns, linking)  
**Query Parameters**:
- `val`: Filter by directional strategy value (optional)

**Response**:
```json
{
  "strategies": [
    {"name": "10TICKS-1"},
    {"name": "10TICKS-2"},
    {"name": "18YEAROLDBADDIE"},
    // ... hundreds more strategies
  ]
}
```

**Usage**:
- Populate dropdown for `DirStrat` (directional strategy selection)
- Filter strategies by name
- Returns array of strategy objects with `name` field

**Key Insights**:
- Returns simplified strategy list (just names)
- Used for dropdown selection
- Can filter by `val` parameter (directional strategy value)

---

### 2. **GET /api/trades/tickers/?strat=**
**Purpose**: Get available tickers for a strategy  
**Query Parameters**:
- `strat`: Strategy name (optional, empty string if none selected)

**Response**:
```json
{
  "tickers": []
}
```

**Usage**:
- Populate ticker dropdown when strategy is selected
- Filter tickers based on selected strategy
- Returns empty array if no strategy selected or no tickers available

**Key Insights**:
- Query parameter is `strat` (not `strategy`)
- Returns array of ticker strings
- Dynamic based on strategy selection

---

### 3. **GET /api/trades/timeframes/?strat=**
**Purpose**: Get available timeframes for a strategy  
**Query Parameters**:
- `strat`: Strategy name (optional, empty string if none selected)

**Response**:
```json
{
  "timeframes": []
}
```

**Usage**:
- Populate timeframe dropdown when strategy is selected
- Filter timeframes based on selected strategy
- Returns empty array if no strategy selected or no timeframes available

**Key Insights**:
- Query parameter is `strat` (not `strategy`)
- Returns array of timeframe strings
- Dynamic based on strategy selection

---

## 🔄 Create Strategy Flow

1. **Page Load**:
   - `GET /api/auth/check-auth/` - Verify authentication
   - `GET /api/strategies/?val=DirStrat` - Load strategies for dropdown
   - `GET /api/trades/tickers/?strat=` - Load tickers (empty initially)
   - `GET /api/trades/timeframes/?strat=` - Load timeframes (empty initially)

2. **User Fills Form**:
   - User enters strategy name, selects type, configures settings
   - If user selects a directional strategy (`DirStrat`), may trigger:
     - `GET /api/trades/tickers/?strat=<strategy_name>` - Update tickers
     - `GET /api/trades/timeframes/?strat=<strategy_name>` - Update timeframes

3. **User Submits Form**:
   - `POST /api/strategies/create/` - Create strategy with all form data
   - Response contains `id` and `webhook_key`

4. **After Creation**:
   - Redirect to strategy detail page or strategy list
   - Show success message with strategy ID

---

## 🔧 Implementation Notes

### Current Create Strategy Component:
- Component exists (`CreateStrategy.jsx`)
- Missing: Complete API integration
- Missing: Form validation
- Missing: Dynamic ticker/timeframe loading

### Required Updates:

1. **Update API Service** (`frontend/src/services/api.js`):
   ```javascript
   strategiesAPI: {
     create: async (strategyData) => {
       return axios.post('/api/strategies/create/', strategyData);
     },
     getStrategiesForDropdown: async (val = '') => {
       return axios.get(`/api/strategies/?val=${val}`);
     },
     getTickers: async (strat = '') => {
       return axios.get(`/api/trades/tickers/?strat=${strat}`);
     },
     getTimeframes: async (strat = '') => {
       return axios.get(`/api/trades/timeframes/?strat=${strat}`);
     }
   }
   ```

2. **Update Create Strategy Component** (`frontend/src/pages/CreateStrategy.jsx`):
   - Load strategies dropdown on mount
   - Handle `DirStrat` selection → load tickers/timeframes
   - Build complete request body matching exact structure
   - Handle response (show success, redirect, or show error)

3. **Backend Implementation** (`api/strategies.py`):
   ```python
   @strategies_bp.route('/create/', methods=['POST'])
   @require_auth
   def create_strategy():
       data = request.get_json()
       
       # Validate required fields
       if not data.get('Strat_Name'):
           return jsonify({'error': 'Strategy name is required'}), 400
       
       # Create strategy in database
       # ... database insert logic ...
       
       # Generate webhook key
       webhook_key = generate_webhook_key()
       
       return jsonify({
           'message': 'Strategy created successfully.',
           'id': strategy_id,
           'webhook_key': webhook_key
       })
   ```

4. **Form Structure**:
   - Match exact field names from API (e.g., `Strat_Name` not `name`)
   - Handle nested objects (`Accounts`, `TimeFilter`, `SLTP_Data`)
   - Handle arrays (`TakeProfit`, `Trim`)
   - Provide defaults for all optional fields

---

## 📝 Field Mapping: Frontend → API

### Basic Fields:
- `strategyName` → `Strat_Name`
- `strategyType` → `Strat_Type`
- `positionSize` → `Position_Size`
- `positionAdd` → `Position_Add`
- `stopLoss` → `Stoploss`
- `takeProfit` → `TakeProfit` (array)
- `trim` → `Trim` (array)
- `tpslUnits` → `TPSL_Units`

### Nested Objects:
- `accounts` → `Accounts` (object with account IDs as keys)
- `timeFilter` → `TimeFilter` (object with start1, stop1, start2, stop2)
- `sltpData` → `SLTP_Data` (object with avgdn, SL_Type, etc.)

### Options-Specific:
- `daysToExpiry` → `Days2Expo`
- `strikeOffset` → `Strike_Offset`

### Flags:
- `isRecorder` → `Recorder`
- `isManual` → `Manual`
- `isAlgoDriven` → `AlgoDriven`
- `isPrivate` → `Private`
- `isEnabled` → `Enabled`

---

## 🎯 Summary

**Strategy Create API**: ✅ Complete  
**Request Structure**: ✅ Captured (full nested object)  
**Response Structure**: ✅ Captured (id, webhook_key, message)  
**Supporting APIs**: ✅ 3 additional APIs discovered
- Strategy list for dropdowns
- Ticker filter
- Timeframe filter

This gives us everything needed to implement complete strategy creation functionality!

