# P&L Tracking Issue - Systematic Debugging

## Problem
P&L shows static/frozen number (e.g., -$1197) and doesn't update in real-time.

## Root Cause Analysis

### Current Situation:
1. **prevPrice is STALE**: `prevPrice: 24334.0` from REST API doesn't update
2. **WebSocket not receiving updates**: No position updates with `openPnl` 
3. **Market data WebSocket not connecting**: No `mdAccessToken` available
4. **Calculation**: Using stale `prevPrice` (24334.0) vs entry (24926.5) = -$1197

### What We Need:
1. Real-time current price (not stale prevPrice)
2. OR position updates with `openPnl` from WebSocket
3. OR a field that actually updates when we poll REST API

## Debug Steps

### Step 1: Check what data Tradovate actually returns
Visit: `http://localhost:5000/api/positions/debug`

This will show:
- All position fields from REST API
- WebSocket cache status
- Whether prevPrice updates between polls

### Step 2: Check if any price field updates
The debug endpoint will track if `prevPrice` changes between API calls.

### Step 3: Test WebSocket messages
Check server logs for:
- "📈 Position update from WebSocket" - means we're getting real-time updates
- "📨 WebSocket event" - shows what messages we're receiving

## Solutions

### Solution A: Use WebSocket quotes (Best)
- Need `mdAccessToken` from re-authentication
- Subscribe to market data WebSocket
- Get real-time quotes for contracts

### Solution B: Use WebSocket position updates (Good)
- User data WebSocket is connecting
- Need to receive position updates with `openPnl`
- Currently not receiving updates

### Solution C: Poll REST API more frequently (Temporary)
- Poll every 1 second (already implemented)
- Check if `prevPrice` or other fields update
- Use whatever field updates most frequently

### Solution D: Calculate from other fields
- Check if `boughtValue`/`soldValue` update
- Or use a different price field that updates

## Next Steps

1. Visit `/api/positions/debug` to see what data we're getting
2. Check if `prevPrice` updates when polling
3. If not, we need WebSocket to work OR find another updating field

