# Tradovate Market Data WebSocket Implementation

## ✅ What We Implemented

### 1. WebSocket Market Data Connection
- **Connection**: `wss://demo.tradovateapi.com/v1/websocket` (demo) or `wss://live.tradovateapi.com/v1/websocket` (live)
- **Authorization**: Uses `md_access_token` from database
- **Format**: SockJS protocol (inherited from Tradovate)
  - Authorization: `"authorize\n0\n\n{md_access_token}"`
  - Subscribe: `"quote/subscribe\n{id}\n\n{json}"`

### 2. Market Data Subscription
- Automatically subscribes to symbols we have positions in
- Gets symbols from:
  - `_position_cache` (synthetic positions)
  - `open_positions` database table
- Converts TradingView symbols (MES1!) to Tradovate format

### 3. Real-Time Price Updates
- Updates `_market_data_cache` with:
  - `last` - Last traded price
  - `bid` - Bid price
  - `ask` - Ask price
- Automatically triggers `update_position_pnl()` when prices update

### 4. PnL Calculation
- Uses contract multipliers (MES=$5, MNQ=$2, ES=$50, NQ=$20)
- Formula: `PnL = (Current Price - Avg Price) × Quantity × Multiplier`
- Updates database `open_positions` table with:
  - `last_price`
  - `unrealized_pnl`
  - `updated_at`

## 🔧 How It Works

1. **Server Startup**: Market data WebSocket thread starts automatically
2. **Connection**: Connects to Tradovate WebSocket using `md_access_token`
3. **Subscription**: Subscribes to quotes for all symbols with open positions
4. **Updates**: Receives real-time price updates and updates cache
5. **PnL**: Automatically recalculates PnL when prices change

## 📋 Requirements

### Prerequisites
- `md_access_token` must be stored in `accounts` table
- `websockets` Python library installed (`pip install websockets`)
- Market data subscription on Tradovate account (may be required)

### Database Schema
```sql
CREATE TABLE accounts (
    ...
    md_access_token TEXT,
    ...
);
```

## 🚀 Testing

1. **Check if md_access_token exists**:
   ```sql
   SELECT id, name, md_access_token FROM accounts WHERE md_access_token IS NOT NULL;
   ```

2. **Place a trade** - should see:
   - Fill price retrieved from `/fill/list`
   - Position stored in `open_positions`
   - Market data subscription for that symbol

3. **Check logs** for:
   - "✅ Market data WebSocket thread started"
   - "Connecting to Tradovate market data WebSocket"
   - "Subscribed to market data for {symbol}"
   - "Updated PnL for {symbol}"

4. **Verify PnL updates**:
   - Check `open_positions` table - `last_price` and `unrealized_pnl` should update
   - Check frontend - PnL should move as price changes

## 🔍 Troubleshooting

### WebSocket Not Connecting
- Check if `md_access_token` exists in database
- Verify market data subscription is active on Tradovate account
- Check logs for authorization errors

### No Price Updates
- Verify symbol format is correct (Tradovate format, not TradingView)
- Check if subscription message was sent successfully
- Verify WebSocket is receiving messages (check logs)

### PnL Not Calculating
- Verify `avg_price` is set (from fill price)
- Verify `last_price` is updating in `_market_data_cache`
- Check contract multiplier is correct for symbol

## 📝 Code Locations

- **WebSocket connection**: `ultra_simple_server.py` line ~2950-3050
- **Market data processing**: `ultra_simple_server.py` line ~3050-3100
- **PnL calculation**: `ultra_simple_server.py` line ~2890-2940
- **Background thread start**: `ultra_simple_server.py` line ~3498-3503

## 🎯 Next Steps

1. **Test with real trade** - Place a trade and verify:
   - Fill price is retrieved
   - Market data subscription works
   - PnL updates in real-time

2. **Handle symbol conversion** - Improve `convert_symbol_for_tradovate_md()` to properly convert TradingView symbols to Tradovate contract IDs

3. **Error handling** - Add better error handling for:
   - WebSocket disconnections
   - Invalid symbols
   - Missing market data subscriptions

4. **Performance** - Optimize:
   - Symbol subscription (only subscribe to active positions)
   - Cache updates (batch updates)
   - Database writes (batch updates)

