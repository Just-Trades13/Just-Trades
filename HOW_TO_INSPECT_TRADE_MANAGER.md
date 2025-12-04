# How to Inspect Trade Manager - Step by Step Guide

## Goal

Find out **exactly** how Trade Manager accesses TradingView data when TradingView add-on is enabled.

## Step 1: Inspect Trade Manager's Network Requests

### When Adding an Account:
1. Open Trade Manager in browser
2. Open DevTools (F12 or Right-click → Inspect)
3. Go to **Network** tab
4. **Clear** the network log (trash icon)
5. Go to "Add Account" page
6. Select "Tradovate" → "REST API"
7. Enter username/password
8. **Watch the Network tab** for API calls
9. Look for:
   - Calls to `trademanagergroup.com/api/*`
   - Calls to `tradingview.com` or `tv.*`
   - Calls to `tradovateapi.com`
   - Any calls that might be TradingView-related

### When Viewing Positions/P&L:
1. With account connected, view positions or P&L
2. **Watch Network tab** for API calls
3. Look for:
   - Calls that return position data
   - Calls that return P&L data
   - Calls to TradingView domains
   - Calls that might be getting market data

## Step 2: Inspect TradingView's Network Requests

### When Broker is Connected:
1. Log into TradingView
2. Connect your Tradovate account (if not already)
3. Open DevTools (F12)
4. Go to **Network** tab
5. **Clear** the network log
6. View your positions or P&L in TradingView
7. **Watch for API calls** that:
   - Return position data
   - Return P&L data
   - Return account data
   - Might be broker-related

### What to Look For:
- **API endpoints** (URLs)
- **Request method** (GET, POST, etc.)
- **Request headers** (authentication, tokens)
- **Response data** (JSON, what fields?)
- **Authentication method** (API key? token? cookies?)

## Step 3: Compare the Two

Compare what you see:
- **Does Trade Manager make calls to TradingView?**
- **Do the endpoints match?**
- **Is Trade Manager using the same API calls as TradingView?**

## What to Share With Me

When you inspect, please share:
1. **API endpoint URLs** (e.g., `https://api.tradingview.com/broker/positions`)
2. **Request method** (GET, POST, etc.)
3. **Request headers** (especially authentication)
4. **Response data** (what fields are returned?)
5. **Any TradingView-related calls** you see

## Example of What We're Looking For

**Good findings:**
```
Request: GET https://api.tradingview.com/broker/positions
Headers: Authorization: Bearer xyz123
Response: {positions: [...], pnl: 123.45}
```

**This would tell us:**
- TradingView has a broker API
- It requires authentication
- It returns positions and P&L
- We can replicate this!

## If You Don't See TradingView Calls

If Trade Manager doesn't make direct TradingView API calls:
- They might be using a different method
- They might have special access
- We'll need to use alternative approach

## Next Steps After Inspection

Once you share findings, I'll:
1. Implement the same API calls
2. Replicate Trade Manager's authentication
3. Get positions, P&L, and market data the same way

