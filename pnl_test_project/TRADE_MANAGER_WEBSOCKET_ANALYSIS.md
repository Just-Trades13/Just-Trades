# Trade Manager WebSocket Analysis

## Source
Screenshot from Trade Manager's WebSocket connection showing real-time market data

---

## Key Observations

### 1. WebSocket Connection
**Status**: ✅ Active and healthy (green circle indicator)
**Origin**: `https://trademanagergroup.com`
**Server**: `TornadoServer/6.4` (Trade Manager's server, not Tradovate directly)

**What This Means:**
- Trade Manager has its own WebSocket server
- It's receiving data (likely from Tradovate) and reformatting it
- Not directly from Tradovate's WebSocket

---

### 2. Message Format
**Structure:**
```json
{
  "type": "DATA",
  "data": {
    "ticker": "ES1!",  // TradingView format
    "prices": {
      "ask": 6723.25,
      "bid": 6723.00
    },
    "tickinfo": {
      "step": 0.25,    // Tick size
      "amnt": 12.5     // Tick value (dollar amount per tick)
    }
  }
}
```

**Key Fields:**
- `type`: "DATA" (indicates this is market data)
- `ticker`: TradingView format (ES1!, MES1!, MNQ1!, NQ1!)
- `prices.ask`: Ask price
- `prices.bid`: Bid price
- `tickinfo.step`: Tick size (0.25 for ES, etc.)
- `tickinfo.amnt`: Dollar value per tick (12.5 for ES, etc.)

---

### 3. Ticker Format
**Trade Manager Uses:**
- `ES1!` - E-mini S&P 500 (TradingView format)
- `MES1!` - Micro E-mini S&P 500
- `MNQ1!` - Micro E-mini Nasdaq-100
- `NQ1!` - E-mini Nasdaq-100

**Tradovate Uses:**
- `ESZ5` - E-mini S&P 500 (Tradovate format)
- `MESZ5` - Micro E-mini S&P 500
- `MNQZ5` - Micro E-mini Nasdaq-100
- `NQZ5` - E-mini Nasdaq-100

**What This Means:**
- Trade Manager converts Tradovate symbols to TradingView format
- We need to do the same conversion in our code

---

### 4. Price Structure
**Available Fields:**
- `ask`: Ask price (what you pay to buy)
- `bid`: Bid price (what you get to sell)
- No `last` price shown (but might be in other messages)

**For P&L Calculation:**
- Can use `bid` for long positions (sell price)
- Can use `ask` for short positions (buy price)
- Or use mid-price: `(ask + bid) / 2`

---

### 5. Tick Information
**Fields:**
- `step`: Tick size (0.25 for ES, 0.25 for NQ, etc.)
- `amnt`: Dollar value per tick
  - ES: 12.5 (0.25 * $50 per point)
  - MES: 1.25 (0.25 * $5 per point)
  - NQ: 5.0 (0.25 * $20 per point)
  - MNQ: 0.5 (0.25 * $2 per point)

**For P&L Calculation:**
- Can use `amnt` directly for tick-based P&L
- Or calculate: `(price_diff / step) * amnt`

---

## What This Tells Us About Tradovate

### Likely Tradovate WebSocket Format
**Trade Manager probably receives from Tradovate:**
- Contract ID or symbol
- Ask/bid prices
- Tick information

**Trade Manager then:**
- Converts symbols to TradingView format
- Wraps in `{"type": "DATA", "data": {...}}` structure
- Sends to clients

**Tradovate's actual format might be:**
- Different structure (not wrapped in "type"/"data")
- Different field names
- Contract ID instead of symbol
- But likely has ask/bid prices and tick info

---

## Implications for Our Implementation

### 1. Message Structure
**Trade Manager Format:**
```json
{
  "type": "DATA",
  "data": {
    "ticker": "...",
    "prices": {"ask": ..., "bid": ...},
    "tickinfo": {"step": ..., "amnt": ...}
  }
}
```

**Tradovate Format (likely):**
- May not have "type" wrapper
- May use contract ID instead of ticker
- But should have ask/bid prices
- May have tick information

**Our Implementation:**
- Handle both formats
- Extract ask/bid prices
- Use for P&L calculation

---

### 2. Price Fields
**Available:**
- `ask`: Ask price
- `bid`: Bid price

**For P&L:**
- Long position: Use `bid` (sell price) or mid-price
- Short position: Use `ask` (buy price) or mid-price
- Or use `last` price if available

**Our Implementation:**
- Check for `last` price first
- Fallback to `bid` for long, `ask` for short
- Or use mid-price: `(ask + bid) / 2`

---

### 3. Symbol Conversion
**Trade Manager:**
- Converts Tradovate symbols to TradingView format
- ESZ5 → ES1!
- MNQZ5 → MNQ1!

**Our Implementation:**
- We already have symbol conversion logic
- Need to ensure it works correctly
- May need to convert both ways (TradingView → Tradovate for API, Tradovate → TradingView for display)

---

### 4. Tick Information
**Trade Manager Provides:**
- `step`: Tick size
- `amnt`: Dollar value per tick

**Our Implementation:**
- Can use `amnt` directly if Tradovate provides it
- Or calculate from contract multiplier
- Use for accurate P&L calculation

---

## What We Can Learn

### ✅ Confirmed
1. Market data comes as JSON messages
2. Prices include ask/bid (at minimum)
3. Tick information is available (step and dollar amount)
4. Real-time updates are frequent (multiple per second)

### ⚠️ Still Unknown
1. Tradovate's exact message format (Trade Manager reformats it)
2. Whether Tradovate uses "type"/"data" wrapper
3. Whether Tradovate provides `last` price
4. Whether Tradovate uses contract ID or symbol

### 🔍 What to Test
1. What format does Tradovate actually send?
2. What fields are in Tradovate's messages?
3. Does Tradovate provide tick information?
4. Does Tradovate provide `last` price?

---

## Updated Test Project Considerations

### 1. Message Parsing
**Handle Multiple Formats:**
```python
# Trade Manager format
if isinstance(data, dict) and "type" in data and "data" in data:
    if data["type"] == "DATA":
        market_data = data["data"]
        ticker = market_data.get("ticker")
        ask = market_data.get("prices", {}).get("ask")
        bid = market_data.get("prices", {}).get("bid")

# Tradovate format (likely)
elif isinstance(data, dict):
    # May have different structure
    contract_id = data.get("contractId")
    ask = data.get("ask") or data.get("askPrice")
    bid = data.get("bid") or data.get("bidPrice")
    last = data.get("last") or data.get("lastPrice")
```

---

### 2. Price Selection
**For P&L Calculation:**
```python
# Priority order:
# 1. Last price (if available)
# 2. Mid price (ask + bid) / 2
# 3. Bid for long, Ask for short

if last_price:
    current_price = last_price
elif ask and bid:
    current_price = (ask + bid) / 2  # Mid price
elif position_side == "long" and bid:
    current_price = bid
elif position_side == "short" and ask:
    current_price = ask
```

---

### 3. Tick Information
**If Tradovate Provides:**
```python
# Use tick amount directly
tick_amnt = data.get("tickinfo", {}).get("amnt")
if tick_amnt:
    pnl = (price_diff / tick_step) * tick_amnt
```

---

## Summary

**What Trade Manager Shows:**
- ✅ JSON message format
- ✅ Ask/bid prices available
- ✅ Tick information available
- ✅ Real-time updates

**What We Still Need:**
- ❓ Tradovate's exact message format
- ❓ Whether Tradovate provides `last` price
- ❓ Whether Tradovate uses contract ID or symbol
- ❓ Whether Tradovate provides tick information

**Next Steps:**
- Test our WebSocket connection to Tradovate
- See what format Tradovate actually sends
- Compare with Trade Manager's format
- Adjust our parsing accordingly

