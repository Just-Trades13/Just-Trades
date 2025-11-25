# P&L Tracking Issue - Root Cause Analysis

## Problem
P&L values are "frozen" - they don't update in real-time on the website.

## Root Cause

The P&L calculation in `ultra_simple_server.py` `/api/positions` endpoint follows this priority:

1. **WebSocket Position Updates** (BEST) - Uses `openPnl` from WebSocket position updates
2. **REST API Position Data** - Checks for `openPnl` or `unrealizedPnl` in position data
3. **Manual Calculation** - Calculates from `netPrice` (avg entry) and current market price
   - Tries `get_quote()` REST API (often returns 404)
   - Falls back to WebSocket quote cache (`ws_quotes`)
   - **FINAL FALLBACK: `prevPrice` from REST API (STALE - THIS IS THE PROBLEM)**

## Why P&L is Frozen

The code is falling back to `prevPrice` because:
1. WebSocket quotes aren't being received (subscription not working)
2. `get_quote()` REST API returns 404
3. `prevPrice` from REST API position data is **stale** - it doesn't update in real-time

## Evidence from Code

From `ultra_simple_server.py` lines 3154-3172:
```python
# Fallback to prevPrice (stale but better than nothing)
# NOTE: prevPrice from REST API is often stale - it doesn't update in real-time
# This is why P&L appears frozen. We need WebSocket quotes or position updates.
prev_price = pos.get('prevPrice')
```

## Solution

We need to ensure WebSocket quotes are working. The code already tries to:
1. Connect to market data WebSocket (`connect_market_data_websocket()`)
2. Subscribe to quotes (`subscribe_to_quote()`)
3. Store quotes in `ws_quotes` cache

But the subscription may not be working correctly.

## Current Status

- ✅ Token refresh endpoint exists but returns 404 (may need different endpoint)
- ✅ WebSocket connection code exists
- ❌ Quote subscriptions may not be working
- ❌ `mdAccessToken` may be missing (needed for market data WebSocket)

## Next Steps

1. **Verify WebSocket Connection**: Check if market data WebSocket is actually connecting
2. **Verify Quote Subscriptions**: Check if subscription messages are being sent correctly
3. **Verify Message Parsing**: Check if quote updates are being received and parsed
4. **Check `mdAccessToken`**: Ensure it's being captured during authentication

## Diagnostic Script

Run `test_pnl_diagnostic.py` to systematically test:
- Token validity
- WebSocket connections
- Quote subscriptions
- Position data

## Quick Fix (Temporary)

If WebSocket isn't working, we could:
1. Poll `/api/positions` more frequently (but still uses stale `prevPrice`)
2. Use a different quote source (if available)
3. Fix WebSocket subscription (preferred solution)

