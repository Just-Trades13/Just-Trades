# Test Tradovate Market Data - Standalone Test

This is a **standalone test script** to verify we can access Tradovate market data before integrating it into the main system.

## Purpose

Test if we can:
1. ✅ Connect to Tradovate market data WebSocket
2. ✅ Authenticate with `md_access_token`
3. ✅ Subscribe to market data for symbols
4. ✅ Receive real-time price updates

## How to Run

```bash
cd "/Users/mylesjadwin/Trading Projects"
python3 test_tradovate_market_data.py
```

## What It Does

1. **Fetches `md_access_token`** from `just_trades.db`
2. **Connects** to Tradovate WebSocket (`wss://demo.tradovateapi.com/v1/websocket`)
3. **Authorizes** using the token
4. **Subscribes** to test symbols (MES, MNQ)
5. **Listens** for 10 seconds and prints all received messages
6. **Shows** what format the data comes in

## Expected Output

### Success Case:
```
✅ WebSocket connected
✅ Authorization successful
✅ Subscription message sent for MESM1
[1.2s] Message #1:
   Format: JSON array
   Data: {
     "symbol": "MESM1",
     "last": 25325.50,
     "bid": 25325.25,
     "ask": 25325.75
   }
```

### Failure Cases:
- **No md_access_token**: "❌ No md_access_token found in database"
- **Connection failed**: "❌ WebSocket connection failed"
- **No messages**: "⚠️ No market data messages received"
  - Market data subscription not active
  - Symbol format incorrect
  - Market closed

## What to Look For

1. **Can we connect?** - Check for "✅ WebSocket connected"
2. **Can we authenticate?** - Check for "✅ Authorization successful"
3. **Do we get data?** - Check message count > 0
4. **What format?** - See the actual message format
5. **What fields?** - Look for `last`, `bid`, `ask`, `symbol`, etc.

## Next Steps Based on Results

### If It Works:
- ✅ We can get market data!
- Integrate the working code into `ultra_simple_server.py`
- Use the same message format/parsing

### If It Doesn't Work:
- Check if market data subscription is active on Tradovate account
- Verify `md_access_token` is valid
- Try different symbol formats
- Check Tradovate API documentation for correct subscription format

## Troubleshooting

### "No md_access_token found"
- Make sure you've connected a Tradovate account
- Check `just_trades.db` for accounts with `md_access_token`

### "WebSocket connection failed"
- Check internet connection
- Verify Tradovate servers are accessible
- Try demo vs live URL

### "No messages received"
- Market data subscription may not be active
- Try during market hours
- Check symbol format (MESM1 vs MES1!)
- Verify subscription message format is correct

## Notes

- This is a **test script** - it doesn't affect the main system
- It runs for 10 seconds then stops
- Press Ctrl+C to stop early
- All output goes to console (no database writes)

