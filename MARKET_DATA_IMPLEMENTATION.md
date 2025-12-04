# Market Data Implementation Plan

## Current Status
- ✅ Positions show quantity
- ❌ Avg price is N/A (need fill price from order)
- ❌ Last price is N/A (need market data)
- ❌ PnL is not moving (need real-time prices)

## Trade Manager's Approach
Trade Manager shows:
- `Open_Price`: Fill price from order
- `Drawdown`: Calculated PnL (likely from TradingView or Tradovate market data)
- Real-time PnL updates

## Implementation Options

### Option 1: TradingView Market Data (Recommended)
**Pros:**
- Free (if you have TradingView account)
- Real-time prices
- Easy to integrate (REST API or WebSocket)

**Cons:**
- Requires TradingView account
- Rate limits

**Implementation:**
```python
# Use TradingView's symbol format (MES1!, MNQ1!, etc.)
# Fetch prices via HTTP or WebSocket
# Update positions every second
```

### Option 2: Tradovate Market Data WebSocket
**Pros:**
- Direct from broker
- Real-time
- Already have mdAccessToken

**Cons:**
- More complex WebSocket setup
- Need to understand Tradovate's market data protocol

**Implementation:**
```python
# Connect to wss://md.tradovate.com/v1/websocket
# Authenticate with mdAccessToken
# Subscribe to symbol quotes
# Receive real-time price updates
```

### Option 3: Simple HTTP Polling (Temporary)
**Pros:**
- Simple to implement
- Works immediately

**Cons:**
- Not real-time (5-10 second delay)
- Rate limits

**Implementation:**
```python
# Poll Tradovate's market data endpoint every 5 seconds
# Or use a free market data API
```

## Recommended Approach

1. **Short-term:** Get fill price from order status (avgFillPrice)
2. **Medium-term:** Set up TradingView market data (simplest)
3. **Long-term:** Upgrade to Tradovate WebSocket for real-time

## Next Steps

1. ✅ Get fill price from order (implemented)
2. ⏳ Set up market data source (TradingView or Tradovate)
3. ⏳ Calculate PnL: (current_price - fill_price) * quantity * multiplier
4. ⏳ Update positions every second with new prices

## PnL Calculation

For MES/MNQ:
- Contract multiplier: 5
- PnL = (current_price - fill_price) * quantity * 5

For ES/NQ:
- Contract multiplier: 20
- PnL = (current_price - fill_price) * quantity * 20

Example:
- Fill price: 25329.59
- Current price: 25331.00
- Quantity: 1 (long)
- PnL = (25331.00 - 25329.59) * 1 * 5 = $7.05

