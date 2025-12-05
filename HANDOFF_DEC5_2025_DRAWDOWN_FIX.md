# 🔧 HANDOFF: Drawdown Tracking Fix - Dec 5, 2025

---

## 📋 Session Summary

**Date:** December 5, 2025  
**Duration:** Diagnostic and fix session  
**Status:** ✅ **COMPLETE AND WORKING**

### Problem Reported
- Drawdown showing $0.00 for 90% of trades
- Values completely different from Trade Manager
- Sometimes showing inverted/negative values for wins

### Root Causes Identified
1. **TradingView WebSocket not connected** - No session cookies configured
2. **Scanner API bug** - Requesting invalid columns (`bid`, `ask`) caused API to return no data

### Fixes Applied
1. ✅ Fixed TradingView Scanner API columns
2. ✅ Stored TradingView session cookies
3. ✅ Restarted Trading Engine
4. ✅ Verified real-time drawdown tracking working

---

## 🔍 Diagnostic Process

### Step 1: Check Trading Engine Status
```bash
curl -s http://localhost:8083/status
```
**Before Fix:**
```json
{
  "cached_prices": {},
  "websocket_connected": false,
  "subscribed_symbols": []
}
```

### Step 2: Check TradingView Session
```bash
curl -s http://localhost:8082/api/tradingview/session
```
**Result:** `"configured": false` - No cookies stored!

### Step 3: Test Scanner API
```bash
curl -X POST "https://scanner.tradingview.com/futures/scan" \
  -H "Content-Type: application/json" \
  -d '{"symbols": {"tickers": ["CME_MINI:MNQ1!"]}, "columns": ["close", "bid", "ask"]}'
```
**Result:** `{"totalCount":0,"error":"Unknown field \"bid\""}` - API error!

---

## 🛠️ Fixes Applied

### Fix 1: TradingView Scanner API (recorder_service.py ~line 694)

**Before:**
```python
payload = {
    "symbols": {"tickers": [tv_symbol]},
    "columns": ["close", "bid", "ask"]
}
```

**After:**
```python
payload = {
    "symbols": {"tickers": [tv_symbol]},
    "columns": ["close"]  # Only request 'close' - bid/ask not available in this API
}
```

### Fix 2: Store TradingView Session Cookies
```bash
curl -X POST http://localhost:8082/api/tradingview/session \
  -H "Content-Type: application/json" \
  -d '{
    "sessionid": "lp992963ppcyy790wxquhf2fquhopvv",
    "sessionid_sign": "v3:QcspTiCJOFhvLcADCSuWDYt1uG2P+HB4THZpcYr7PBU="
  }'
```

### Fix 3: Restart Trading Engine
```bash
pkill -f "python.*recorder_service"
cd "/Users/mylesjadwin/Trading Projects" && python3 recorder_service.py &
```

---

## ✅ Verification

### After Fix - Trading Engine Status:
```json
{
  "cached_prices": {"MES": 6879.75, "MN": 25711.75},
  "websocket_connected": true,
  "subscribed_symbols": ["CME:MN1!", "CME_MINI:MNQ1!", "CME:ES1!", "CME:NQ1!", "CME_MINI:MES1!"]
}
```

### Real-Time Drawdown Updates Confirmed:
```
=== Snapshot 1 (23:06:23) ===
351|MNQ1!|SHORT|25712.125|-16.5|-17.5

=== Snapshot 2 (23:06:25) ===
351|MNQ1!|SHORT|25712.375|-17.5|-17.5

=== Snapshot 3 (23:06:27) ===
351|MNQ1!|SHORT|25712.75|-19.0|-19.0  ← worst_unrealized_pnl updated!
```

---

## 📊 How Drawdown Tracking Works

### Architecture Flow:
```
TradingView WebSocket (wss://data.tradingview.com)
         │
         ▼
on_price_update(symbol, price) in recorder_service.py
         │
         ├──► Update _market_data_cache
         │
         ├──► For each position with this symbol:
         │        update_position_drawdown(pos_id, price)
         │        → Calculate unrealized PnL
         │        → worst_unrealized_pnl = min(current, unrealized)
         │        → best_unrealized_pnl = max(current, unrealized)
         │
         └──► Write to recorder_positions table
```

### Key Functions in recorder_service.py:
| Function | Line ~Range | Purpose |
|----------|-------------|---------|
| `get_price_from_tradingview_api()` | ~675-710 | Fallback price fetch (when WS down) |
| `update_position_drawdown()` | ~427-487 | Update position's worst/best unrealized PnL |
| `on_price_update()` | ~541-565 | Called on every WebSocket price tick |
| `poll_position_drawdown()` | ~784-885 | Polling fallback (1 second) when WS not connected |

### Database Table: `recorder_positions`
```sql
SELECT id, ticker, side, total_quantity, avg_entry_price,
       current_price, unrealized_pnl, worst_unrealized_pnl, best_unrealized_pnl
FROM recorder_positions WHERE status='open';
```

---

## ⚠️ Important Notes

### 1. Historical Trades Show $0 Drawdown
Trades closed **before** this fix will still show `$0.00` drawdown - this is expected because we weren't tracking it then.

### 2. TradingView Cookies Expire
If drawdown stops working in the future:
1. Go to TradingView.com → DevTools (F12) → Application → Cookies
2. Copy `sessionid` and `sessionid_sign`
3. Store via API:
```bash
curl -X POST http://localhost:8082/api/tradingview/session \
  -H "Content-Type: application/json" \
  -d '{"sessionid": "NEW_VALUE", "sessionid_sign": "NEW_VALUE"}'
```
4. Restart Trading Engine

### 3. Market Hours
Real-time prices only stream when markets are open:
- **Futures:** Sunday 6pm ET - Friday 5pm ET (with daily breaks)

---

## 🔗 Trade Manager Comparison

From HAR file analysis, Trade Manager:
- Uses their own WebSocket at `wss://trademanagergroup.com:5000/ws`
- Calculates drawdown **server-side** and returns in `/api/trades/open/` response
- Shows drawdown like: `"Drawdown": "-11.00"` (dollars, negative = loss)

Our implementation now matches this behavior:
- ✅ Real-time price streaming via TradingView WebSocket
- ✅ Server-side drawdown calculation
- ✅ `worst_unrealized_pnl` tracks the most negative unrealized PnL seen
- ✅ Updates on every price tick

---

## 📁 Files Changed

| File | Change |
|------|--------|
| `recorder_service.py` | Fixed Scanner API columns (line ~694) |
| `START_HERE.md` | Added drawdown fix documentation |
| `HANDOFF_DEC5_2025_DRAWDOWN_FIX.md` | This document |

---

## 🚀 Quick Commands

```bash
# Check if drawdown is working
curl -s http://localhost:8083/status | python3 -c "import sys,json; d=json.load(sys.stdin); print('WebSocket:', d['websocket_connected']); print('Prices:', d['cached_prices'])"

# Check position drawdown values
sqlite3 just_trades.db "SELECT id, ticker, worst_unrealized_pnl FROM recorder_positions WHERE status='open';"

# Restart Trading Engine
pkill -f "python.*recorder_service" && cd "/Users/mylesjadwin/Trading Projects" && python3 recorder_service.py &

# Check TradingView session
curl -s http://localhost:8082/api/tradingview/session
```

---

*Created: December 5, 2025*  
*Session: Drawdown Tracking Fix*  
*Related: HANDOFF_DEC5_2025_MICROSERVICES_ARCHITECTURE.md, HANDOFF_DEC4_2025_POSITION_TRACKING.md*
