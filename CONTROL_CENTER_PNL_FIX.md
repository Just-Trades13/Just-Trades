# Control Center P&L Discrepancy Fix

## Problem Identified

The Control Center page had **discrepancies between two sections**:

1. **Live Trading Panel** (table showing strategy P&L)
2. **Live Positions Section** (cards showing real-time position P&L)

These sections showed different P&L numbers for the same positions.

## Root Causes

### 1. Different Data Sources
- **Live Trading Panel** used `recorded_trades` table (multiple rows per recorder for DCA entries)
- **Live Positions Section** used `recorder_positions` table (aggregated, one row per recorder+ticker)

### 2. Different Price Sources
- **Live Trading Panel** used `get_cached_price()` → API calls with caching
- **Live Positions Section** used TradingView market data cache (`_market_data_cache`)

### 3. Different Calculation Methods
- **Live Trading Panel**: `(current_price - entry_price) * tick_value * quantity`
- **Live Positions Section**: `pnl_ticks * tick_value * total_qty` where `pnl_ticks = (current_price - avg_entry) / tick_size`

## Solution

**Fixed `/api/control-center/stats` endpoint** to use:
1. ✅ **Same data source**: `recorder_positions` table (aggregated positions)
2. ✅ **Same price source**: TradingView market data cache (`_market_data_cache`)
3. ✅ **Same calculation**: Tick-based calculation matching WebSocket updates

## Changes Made

### File: `ultra_simple_server.py`
**Function**: `api_control_center_stats()` (line ~13644)

**Before**:
- Queried `recorded_trades` table
- Used `get_cached_price()` for prices
- Direct multiplication: `(price_diff) * tick_value * quantity`

**After**:
- Queries `recorder_positions` table (same as WebSocket)
- Uses TradingView market data cache (`_market_data_cache`)
- Tick-based calculation: `(price_diff / tick_size) * tick_value * quantity`

## Result

Both sections now:
- ✅ Use the same aggregated position data
- ✅ Use the same real-time price source
- ✅ Calculate P&L using the same method
- ✅ Show **identical P&L numbers**

## Testing

To verify the fix:
1. Open Control Center page
2. Compare P&L in Live Trading Panel table vs Live Positions cards
3. Numbers should now match exactly
4. Both should update in real-time via WebSocket

## Notes

- The fix maintains backward compatibility (still returns `open_positions` array)
- Falls back to `get_cached_price()` if TradingView cache doesn't have the symbol
- Uses same rounding (2 decimal places) as WebSocket updates for consistency
