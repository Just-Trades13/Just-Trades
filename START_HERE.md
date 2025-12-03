# START HERE - Trade Recorder System Handoff

**Date:** December 3, 2025  
**Status:** ✅ FULLY FUNCTIONAL - Real-time trade recording with auto TP/SL

---

## 🎯 What This System Does

A **Trade Recorder** that:
1. Receives signals from TradingView webhooks
2. Opens simulated trades with TP/SL levels (from recorder settings)
3. Monitors real-time prices via TradingView WebSocket
4. Auto-closes trades when TP or SL is hit
5. Calculates and stores PnL

---

## ✅ Current Working State

### Server
- **File:** `ultra_simple_server.py`
- **Port:** 8082
- **Start:** `python3 ultra_simple_server.py`

### Database
- **File:** `just_trades.db` (SQLite)
- **Key Tables:**
  - `recorders` - Strategy configurations with TP/SL settings
  - `recorded_trades` - Trade history with entry/exit/PnL
  - `recorded_signals` - Raw webhook signals
  - `accounts` - Tradovate accounts + TradingView session

### Real-Time Price Feed
- **Primary:** TradingView WebSocket (connected via session cookies)
- **Fallback:** TradingView Scanner API (polling)
- **Symbols streaming:** MNQ, MES, NQ, ES

### TradingView Session (Stored)
```
sessionid: lp992963ppcyy790wxquqhf2fquhopvv
sessionid_sign: v3:QcspTiCJOFhvLcADCSuWDYt1uG2P+HB4THZpcYr7PBU=
```

---

## 🔑 Key Files

| File | Purpose |
|------|---------|
| `ultra_simple_server.py` | Main Flask server (~6500 lines) |
| `just_trades.db` | SQLite database |
| `templates/dashboard.html` | PnL dashboard (Trade Manager style) |
| `templates/control_center.html` | Live recorder monitoring |
| `templates/recorders_list.html` | Recorder management |
| `templates/recorders.html` | Create/edit recorder form |
| `RECORDERS_HANDOFF.md` | Detailed documentation |

---

## 🛠️ Key Endpoints

### Webhooks
```
POST /webhook/<token>  - Receive TradingView signals
```

### Recorder API
```
GET    /api/recorders              - List all recorders
GET    /api/recorders/<id>         - Get single recorder
POST   /api/recorders              - Create recorder
PUT    /api/recorders/<id>         - Update recorder
GET    /api/recorders/<id>/pnl     - Get PnL stats
GET    /api/recorders/<id>/trades  - Get trade history
```

### TradingView Session
```
POST /api/tradingview/session  - Store session cookies
GET  /api/tradingview/session  - Check session status
```

### Dashboard
```
GET /api/dashboard/strategies    - List strategies
GET /api/dashboard/chart-data    - PnL chart data
GET /api/dashboard/trade-history - Trade table
GET /api/dashboard/metrics       - Metric cards
GET /api/dashboard/calendar-data - Calendar PnL
```

---

## 📊 How Trade Recording Works

### Signal Flow
```
TradingView Alert → POST /webhook/<token> → 
  1. Record signal to recorded_signals
  2. Check for open trade (close if reversal)
  3. Calculate TP/SL prices from recorder settings
  4. Insert new trade to recorded_trades
  5. Emit WebSocket event for UI update
```

### TP/SL Monitoring Flow
```
TradingView WebSocket → Real-time price update →
  1. Update _market_data_cache
  2. Call check_recorder_trades_tp_sl()
  3. For each open trade with TP/SL:
     - If price >= TP (LONG) or <= TP (SHORT) → Close at TP
     - If price <= SL (LONG) or >= SL (SHORT) → Close at SL
  4. Calculate PnL, update database
  5. Emit trade_executed WebSocket event
```

### PnL Calculation
```python
tick_size = get_tick_size(symbol)   # e.g., 0.25 for MNQ
tick_value = get_tick_value(symbol) # e.g., $0.50 for MNQ

if side == 'LONG':
    pnl_ticks = (exit_price - entry_price) / tick_size
else:
    pnl_ticks = (entry_price - exit_price) / tick_size

pnl = pnl_ticks * tick_value * quantity
```

---

## 🔧 Key Functions in ultra_simple_server.py

| Function | Line ~# | Purpose |
|----------|---------|---------|
| `receive_webhook()` | 2200 | Process incoming TradingView signals |
| `check_recorder_trades_tp_sl()` | 5100 | Check TP/SL on price update |
| `connect_tradingview_websocket()` | 5400 | TradingView WebSocket connection |
| `process_tradingview_message()` | 5530 | Parse TradingView price data |
| `get_tick_size()` | 620 | Get tick size for symbol |
| `get_tick_value()` | 665 | Get dollar value per tick |

---

## 📋 Test Commands

### Check server is running
```bash
curl http://localhost:8082/api/tradingview/session
```

### Send test webhook
```bash
curl -X POST http://localhost:8082/webhook/BCfOq35nzwuqZfBcNxk5iQ \
  -H "Content-Type: application/json" \
  -d '{"recorder": "JT Test 2", "action": "buy", "ticker": "MNQ1!", "price": "25650.00"}'
```

### Check open trades
```bash
sqlite3 just_trades.db "SELECT * FROM recorded_trades WHERE status = 'open'"
```

### Check price streaming
```bash
grep "💰" /tmp/server.log | tail -10
```

### Update TradingView session
```bash
curl -X POST http://localhost:8082/api/tradingview/session \
  -H "Content-Type: application/json" \
  -d '{"sessionid": "NEW_ID", "sessionid_sign": "NEW_SIGN"}'
```

---

## ⚠️ Protected Files (DO NOT MODIFY)

- `templates/account_management.html` - LOCKED
- Account management functions in `ultra_simple_server.py` - LOCKED
- See `.cursorignore` and `TAB_ISOLATION_MAP.md`

---

## 🔄 If Things Break

### TradingView WebSocket disconnects
1. Get fresh cookies from Chrome DevTools → tradingview.com
2. POST to `/api/tradingview/session`

### Server won't start
```bash
python3 -m py_compile ultra_simple_server.py  # Check syntax
tail -50 /tmp/server.log  # Check errors
```

### No price updates
```bash
grep "TradingView" /tmp/server.log | tail -20
```

---

## 📈 Current Test Recorder

| Field | Value |
|-------|-------|
| ID | 3 |
| Name | JT Test 2 |
| Webhook Token | BCfOq35nzwuqZfBcNxk5iQ |
| Position Size | 1 contract |
| TP | 20 ticks |
| SL | 20 ticks (enabled) |

---

## 🎯 What's Next (Optional)

1. **Close All Positions** - Button in Control Center
2. **Historical Backfill** - Process old signals
3. **Export to CSV** - Trade history download
4. **Session Auto-Refresh** - Detect expired cookies

---

**Server Log:** `/tmp/server.log`  
**Detailed Docs:** `RECORDERS_HANDOFF.md`  
**Tab Rules:** `TAB_ISOLATION_MAP.md`

---

*Last Updated: December 3, 2025*
