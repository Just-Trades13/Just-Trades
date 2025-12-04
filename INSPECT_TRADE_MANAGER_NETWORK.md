# Inspect Trade Manager Network Requests

## Hypothesis

Trade Manager might be:
1. **Scraping TradingView's web interface** (unlikely but possible)
2. **Using TradingView's internal APIs** (not public, but might be accessible)
3. **Using a combination**: Tradovate API for orders + TradingView public API for market data
4. **Calculating P&L themselves** using market data + positions

## What We Need to Find

When you use Trade Manager, can you:

1. **Open Browser DevTools** (F12)
2. **Go to Network tab**
3. **Filter by "tradingview" or "tv"**
4. **Watch for API calls** when:
   - Adding an account
   - Viewing positions
   - Seeing P&L updates

## What to Look For

- **API endpoints** that might be TradingView-related
- **Request URLs** that contain "tradingview" or broker-related terms
- **Response data** that shows positions, P&L, or market data
- **Authentication** - how Trade Manager authenticates with TradingView

## Alternative Theory

Maybe Trade Manager is:
1. Using **Tradovate REST API** (username/password) for:
   - Order execution
   - Position data
   - Account info
2. Using **TradingView Public API** (free) for:
   - Market data (prices)
   - Calculating P&L themselves

This would explain:
- ✅ Why TradingView add-on is required (maybe just for verification?)
- ✅ How they get market data without CME fees
- ✅ How they calculate P&L

## Next Steps

1. **Inspect Trade Manager's network requests**
2. **Look for TradingView API calls**
3. **See what endpoints they're using**
4. **Implement the same approach**

