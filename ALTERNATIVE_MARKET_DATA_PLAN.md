# Alternative Market Data Implementation Plan

## Problem
Tradovate requires CME sub-vendor registration ($290-500/month) for real-time market data via API.

## Solution: Use TradingView Free API

### Why TradingView?
- ✅ Free tier available
- ✅ Real-time prices
- ✅ No CME registration needed
- ✅ Works with TradingView symbols (MES1!, MNQ1!)
- ✅ Easy HTTP API (no WebSocket complexity)

## Implementation Steps

### Step 1: TradingView Symbol Search API
```python
# Get symbol info
GET https://symbol-search.tradingview.com/symbol_search/?text=MES1!
# Returns: symbol details, exchange, etc.
```

### Step 2: TradingView Quote API
```python
# Get current price
GET https://scanner.tradingview.com/symbols?exchange=CME&symbol=MES1!
# Or use TradingView's quote endpoint
```

### Step 3: Alternative: Alpha Vantage
```python
# Free tier: 5 calls/min, 500 calls/day
GET https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=MES&apikey=YOUR_KEY
```

### Step 4: Alternative: Yahoo Finance (Unofficial)
```python
# Free, no API key needed
GET https://query1.finance.yahoo.com/v8/finance/chart/MES=F
```

## Recommended Approach

**Use TradingView Symbol Search + Quote APIs:**
1. Symbol already in TradingView format (MES1!, MNQ1!)
2. No conversion needed
3. Free tier available
4. Real-time data

## Code Structure

```python
def get_market_price_tradingview(symbol: str) -> Optional[float]:
    """Get current price from TradingView API"""
    try:
        # Try TradingView quote endpoint
        response = requests.get(
            f"https://scanner.tradingview.com/symbols",
            params={"exchange": "CME", "symbol": symbol},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('last_price') or data.get('close')
    except Exception as e:
        logger.warning(f"TradingView API error: {e}")
    
    # Fallback to Yahoo Finance
    try:
        response = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}=F",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            quote = data.get('chart', {}).get('result', [{}])[0]
            price = quote.get('meta', {}).get('regularMarketPrice')
            return float(price) if price else None
    except Exception as e:
        logger.warning(f"Yahoo Finance API error: {e}")
    
    return None
```

## Integration Points

1. **Replace Tradovate WebSocket** with TradingView HTTP polling
2. **Update `_market_data_cache`** with TradingView prices
3. **Keep Tradovate** for order execution only
4. **Calculate PnL** using TradingView prices

## Update Frequency

- **Poll every 1-2 seconds** for active positions
- **Cache results** to avoid rate limits
- **Update only symbols with open positions**

## Testing

1. Test TradingView API with MES1!, MNQ1!
2. Verify price format matches our needs
3. Test rate limits and error handling
4. Integrate into `update_position_pnl()`

