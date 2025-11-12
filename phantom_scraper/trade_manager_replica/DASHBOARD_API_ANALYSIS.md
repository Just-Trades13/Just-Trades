# Dashboard API Analysis

## ✅ Success! API Calls Captured

This extraction captured **actual API calls** with real request/response data!

**File**: `trade_manager_functionality__user_dashboard_1762407753203.json`  
**Total API Calls**: 9 unique calls  
**Timestamp**: 2025-11-06T05:41:58.354Z

---

## 📡 API Endpoints Identified

### 1. **GET /api/trades/**
**Purpose**: Fetch all trades  
**Query Parameters**:
- `user` (optional): Filter by username (e.g., `SMARTYIELD`, `J.T.M.J`)
- `usageType`: Always `true`

**Sample Calls**:
- `/api/trades/?user=SMARTYIELD&usageType=true`
- `/api/trades/?usageType=true` (no user filter)
- `/api/trades/?user=J.T.M.J&usageType=true`

**Response**: Array of trade objects (empty array in sample: `[]`)

**Status**: 200 OK

---

### 2. **GET /api/trades/open/**
**Purpose**: Fetch open trades  
**Query Parameters**:
- `user` (optional): Filter by username
- `usageType`: Always `true`

**Sample Calls**:
- `/api/trades/open/?user=SMARTYIELD&usageType=true`
- `/api/trades/open/?usageType=true`
- `/api/trades/open/?user=J.T.M.J&usageType=true`

**Response**: Array of open trade objects (empty array in sample: `[]`)

**Status**: 200 OK

---

### 3. **GET /api/profiles/get-widget-info/**
**Purpose**: Get dashboard widget information (stats, filters, etc.)  
**Query Parameters**:
- `user` (optional): Filter by username
- `usageType`: Always `true`

**Sample Calls**:
- `/api/profiles/get-widget-info/?user=SMARTYIELD&usageType=true`
- `/api/profiles/get-widget-info/?usageType=true`
- `/api/profiles/get-widget-info/?user=J.T.M.J&usageType=true`

**Response Structure**:
```json
{
  "cumulativeProfit": 0,
  "wins": 0,
  "losses": 0,
  "winrate": 0,
  "drawdown": 0,
  "roi": 0,
  "avgTiT": 0,  // Average Time in Trade
  "maxTiT": 0,  // Max Time in Trade
  "minTiT": 0,  // Min Time in Trade
  "pf": 0,      // Profit Factor
  "maxP": 0,    // Max Profit
  "avgP": 0,    // Average Profit
  "maxL": 0,    // Max Loss
  "avgL": 0,    // Average Loss
  "maxPos": 0,  // Max Position
  "avgPos": 0,  // Average Position
  "maxDD": 0,   // Max Drawdown
  "avgDD": 0,   // Average Drawdown
  "days": 0,
  "strategies": [
    { "name": "BEARSPY" },
    { "name": "GBANG6" },
    // ... many more strategies
  ],
  "users": [],
  "symbols": [],
  "timeFrames": [],
  "accounts": []
}
```

**Status**: 200 OK

**Key Insights**:
- Returns comprehensive statistics for dashboard widgets
- Includes filter dropdown options (strategies, users, symbols, timeFrames, accounts)
- When user filter is applied, returns minimal data (all zeros, empty arrays)
- Without user filter, returns full data with strategy names

---

## 🔍 Key Observations

### 1. **User Filtering**
- All endpoints support optional `user` query parameter
- When `user` is specified, responses are filtered/scoped to that user
- Without `user`, returns aggregate/all data

### 2. **Usage Type**
- All calls include `usageType=true`
- This appears to be a flag indicating "recorded strategies" usage mode

### 3. **Response Headers**
All responses include:
- `content-type: application/json`
- Security headers (HSTS, X-Frame-Options, X-Content-Type-Options)
- `vary: origin, Cookie` (indicates cookie-based auth)

### 4. **Empty Responses**
- Most trade arrays are empty (`[]`)
- This suggests either:
  - No trades for the filtered user
  - Test/demo account
  - Data was cleared

### 5. **Widget Info Response**
- When no user filter: Returns full data with 100+ strategies
- When user filter applied: Returns minimal data (all zeros)
- This suggests the endpoint aggregates data differently based on parameters

---

## 📊 Dashboard Data Flow

### Initial Load Sequence:
1. **GET /api/trades/?user=[USER]&usageType=true** - Load trades
2. **GET /api/profiles/get-widget-info/?user=[USER]&usageType=true** - Load widget stats
3. **GET /api/trades/open/?user=[USER]&usageType=true** - Load open trades

### Filter Changes:
When user changes filters (user, strategy, symbol, timeframe):
1. **GET /api/trades/?usageType=true** (with new filters)
2. **GET /api/trades/open/?usageType=true** (with new filters)
3. **GET /api/profiles/get-widget-info/?usageType=true** (with new filters)

### Note:
- Calls happen both with and without user filter
- This suggests the dashboard supports both:
  - User-specific view (filtered)
  - Global/all data view (unfiltered)

---

## 🔧 Implementation Notes

### Current Dashboard Component:
- Already has filters for user, strategy, symbol, timeframe
- Calls `dashboardAPI.getSummary()`, `tradesAPI.getAll()`, `tradesAPI.getOpen()`
- Missing: `get-widget-info` endpoint

### Required Updates:

1. **Add Widget Info Endpoint**:
   ```javascript
   // In api.js
   getWidgetInfo: (params = {}) => {
     const queryString = new URLSearchParams({
       usageType: true,
       ...params
     }).toString();
     return axios.get(`/api/profiles/get-widget-info/?${queryString}`);
   }
   ```

2. **Update Dashboard Component**:
   - Call `profilesAPI.getWidgetInfo()` to get:
     - Statistics (wins, losses, winrate, etc.)
     - Filter dropdown options (strategies, users, symbols, timeFrames, accounts)
   - Populate filter dropdowns with data from widget info
   - Display statistics in summary cards

3. **Handle Filter Changes**:
   - When filters change, update query parameters
   - Include `usageType=true` in all calls
   - Support optional `user` parameter

4. **Response Handling**:
   - Handle empty trade arrays gracefully
   - Handle minimal widget info (when user filter applied)
   - Display proper loading states

---

## 📝 Next Steps

1. **Update API Service** (`frontend/src/services/api.js`):
   - Add `getWidgetInfo()` method to `profilesAPI`

2. **Update Dashboard Component** (`frontend/src/pages/Dashboard.jsx`):
   - Call `getWidgetInfo()` on mount
   - Use widget info to populate filter dropdowns
   - Display widget statistics
   - Update filter change handlers to include `usageType=true`

3. **Update Backend** (`api/dashboard.py` or create `api/profiles.py`):
   - Implement `/api/profiles/get-widget-info/` endpoint
   - Return statistics and filter options
   - Support user filtering

4. **Test**:
   - Test with user filter
   - Test without user filter
   - Test filter changes
   - Verify empty state handling

---

## 🎯 Summary

This extraction is **much more valuable** than the previous one because it contains:
- ✅ Real API endpoints
- ✅ Actual request URLs with query parameters
- ✅ Response data structures
- ✅ Request/response headers
- ✅ Multiple calls showing different filter combinations

This gives us the exact API contract we need to implement!

