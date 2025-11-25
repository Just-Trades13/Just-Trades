# P&L Tracking Issue - Root Cause & Solution

## Current Status
✅ **Open position exists**: `netPos: 1`  
❌ **P&L is frozen**: Using stale `prevPrice` (24334.0)  
❌ **WebSocket not receiving updates**: No position updates with `openPnl`  
❌ **Market data WebSocket not connecting**: No `mdAccessToken`

## Root Cause
The `prevPrice` field from Tradovate REST API is **STALE** and doesn't update in real-time. It's a snapshot price, not a live quote.

## Why P&L is Frozen
1. **Entry price**: `netPrice: 24963.5` (correct)
2. **Current price**: `prevPrice: 24334.0` (STALE - doesn't update)
3. **Calculation**: (24334.0 - 24963.5) * 1 * 2.0 = **-$1259.00** (frozen)

## Solutions (in order of preference)

### Solution 1: Get WebSocket Working (BEST)
**What we need:**
- `mdAccessToken` for market data WebSocket (requires re-authentication)
- OR position updates with `openPnl` from user data WebSocket

**Status:**
- User data WebSocket: ✅ Connecting
- Market data WebSocket: ❌ Not connecting (no mdAccessToken)
- Position updates: ❌ Not receiving (messages not in expected format)

### Solution 2: Use REST API Quote Endpoint (TEMPORARY)
**What we can try:**
- Poll `/md/getQuote` endpoint every 1-2 seconds
- But this endpoint returns 404 (not working)

### Solution 3: Accept Stale P&L (CURRENT)
**What we're doing now:**
- Using stale `prevPrice` 
- P&L shows but doesn't update
- User sees frozen number

## Immediate Action Items

1. **Re-authenticate account** to get `mdAccessToken`
   - Go to account connection page
   - Re-enter credentials
   - This should capture `mdAccessToken`

2. **Check WebSocket messages** - we're receiving messages but not parsing them correctly
   - Messages are coming as "o" (open frame) and empty events
   - Need to check actual message format from Tradovate

3. **Alternative**: If WebSocket can't work, we need to find another price field that updates
   - Check if any other field in position response updates
   - Or find a different REST endpoint for quotes

## Next Steps
1. Re-authenticate to get `mdAccessToken`
2. Check if WebSocket starts receiving position updates
3. If not, we need to debug WebSocket message format

