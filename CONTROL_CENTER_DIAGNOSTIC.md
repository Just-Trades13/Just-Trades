# Control Center P&L Discrepancy Analysis

## Issues Found

### 1. **User Filtering Mismatch** ⚠️
- `/api/traders` filters by `user_id` (only shows current user's traders)
- `/api/control-center/stats` does NOT filter by user_id (shows ALL recorders)
- **Result**: Table might show P&L for recorders the user doesn't have traders for

### 2. **Selector Bug** 🐛
- Line 701: `updateStrategyPnL()` looks for `tr[data-recorder-id="${strategyId}"]`
- Line 676: Table rows use `data-strategy-id="${strategy.id}"`
- **Result**: WebSocket P&L updates won't update the table

### 3. **Data Structure Difference** 📊
- **Live Trading Panel**: Shows P&L **per recorder** (summed across all tickers)
- **Live Positions**: Shows P&L **per position** (per recorder+ticker)
- **Expected**: If recorder has 2 positions, sum of position cards should = table row

### 4. **Potential Price Cache Timing** ⏱️
- Stats endpoint calculates prices on-demand
- WebSocket updates use cached prices from background thread
- **Result**: Slight timing differences might cause small discrepancies

## How to Verify

1. **Check browser console**:
   - Open DevTools → Console
   - Look for errors when loading Control Center
   - Check WebSocket messages: `live_position_update` and `live_positions_all`

2. **Compare numbers**:
   - For each strategy in the table, sum all position cards with that strategy name
   - They should match the table P&L

3. **Check user filtering**:
   - If you see strategies in the table that you don't have traders for, that's the user filtering bug

## Fixes Needed

1. ✅ Add user filtering to `/api/control-center/stats`
2. ✅ Fix selector bug in `updateStrategyPnL()`
3. ✅ Add debug logging to compare calculations
4. ✅ Ensure both use same price source at same time
