# Recorders Tab - Handoff Document

**Date:** December 3, 2025  
**Status:** ✅ COMPLETE - Full trade recording with real-time TP/SL monitoring

---

## 🎯 How Trade Recording Works (REAL DATA)

### The System Flow

1. **Entry Signal**: TradingView sends `buy` or `sell` → Trade opens with calculated TP/SL levels
2. **Real-Time Monitoring**: TradingView WebSocket streams live prices
3. **Auto-Close**: When price crosses TP or SL → Trade automatically closes with correct PnL
4. **No manual TP/SL alerts needed!**

### TradingView WebSocket Integration (NEW!)

The system connects to TradingView's WebSocket using your session cookies for **real-time price data**:

```
📊 TradingView CME_MINI:MNQ1!: bid=25653.0, ask=25653.75
💰 TradingView price: MNQ = 25653.375
```

**Setup your session (one-time):**
```bash
curl -X POST http://localhost:8082/api/tradingview/session \
  -H "Content-Type: application/json" \
  -d '{
    "sessionid": "YOUR_SESSION_ID",
    "sessionid_sign": "YOUR_SESSION_SIGN",
    "device_t": "YOUR_DEVICE_TOKEN"
  }'
```

**Get cookies from:** Chrome DevTools → Application → Cookies → tradingview.com

### TradingView Alert Setup (Simplified!)

You only need **1 alert** per strategy now:

#### Entry Signal
```json
{
  "recorder": "{{strategy.order.comment}}",
  "action": "{{strategy.order.action}}",
  "ticker": "{{ticker}}",
  "price": "{{close}}"
}
```

**TP/SL are monitored automatically** via real-time price feed!

### Supported Webhook Actions

| Action | Description |
|--------|-------------|
| `buy` / `long` | Opens LONG position |
| `sell` / `short` | Opens SHORT position |
| `close` / `flat` / `exit` | Closes any open position |
| `tp_hit` / `take_profit` | Manual TP close (optional) |
| `sl_hit` / `stop_loss` | Manual SL close (optional) |

### Example Trade Flow

```
1. Webhook: BUY @ 25655.50 → LONG opened, TP=25660.50, SL=25650.50
2. TradingView WebSocket: Price streaming... 25654, 25655, 25656...
3. Price hits 25660.50 → 🎯 TP HIT! Trade auto-closed, PnL: +$10.00
```

---

## ✅ What's Been Completed

### 1. Recorders CRUD System
- **Database Table:** `recorders` in `just_trades.db` with 38 columns
- **API Endpoints** (in `ultra_simple_server.py`):
  - `GET /api/recorders` - List all recorders with search & pagination
  - `GET /api/recorders/<id>` - Get single recorder
  - `POST /api/recorders` - Create new recorder
  - `PUT /api/recorders/<id>` - Update recorder
  - `DELETE /api/recorders/<id>` - Delete recorder
  - `POST /api/recorders/<id>/clone` - Clone recorder
  - `POST /api/recorders/<id>/start` - Start recording
  - `POST /api/recorders/<id>/stop` - Stop recording
  - `GET /api/recorders/<id>/webhook` - Get webhook URL & alert templates

### 2. Webhook System (WORKING ✅)
- **Endpoint:** `POST /webhook/<webhook_token>`
- **Location:** `ultra_simple_server.py` around line 2000
- TradingView sends alerts → Our system receives, logs, AND processes them
- **Signals Table:** `recorded_signals` stores all incoming signals

### 3. Trade Recording System (NEW ✅)
- **Database Table:** `recorded_trades` with full trade lifecycle tracking
- **Trade Processing Logic:**
  - BUY signal → Opens LONG position (or closes SHORT first)
  - SELL signal → Opens SHORT position (or closes LONG first)
  - CLOSE signal → Closes any open position
- **PnL Calculation:** Automatic per-trade PnL based on tick size & tick value
- **Supported Symbols:** MNQ, MES, MYM, M2K, NQ, ES, YM, RTY, CL, GC, and more

### 4. PnL API Endpoints (NEW ✅)
- `GET /api/recorders/<id>/pnl` - Full PnL summary with:
  - Total PnL, wins, losses, win rate
  - Daily PnL history for charting
  - Cumulative PnL and drawdown
  - Open position info
  - Profit factor calculation
- `GET /api/recorders/<id>/trades` - Trade history with pagination
- `GET /api/recorders/all/pnl` - Aggregated PnL for all recorders

### 5. Dashboard Integration (NEW ✅)
- `GET /api/dashboard/strategies` - Lists recorders as strategies
- `GET /api/dashboard/chart-data` - PnL chart data from recorded trades
- `GET /api/dashboard/trade-history` - Trade table with pagination
- `GET /api/dashboard/calendar-data` - Daily PnL for calendar view
- `GET /api/dashboard/metrics` - Metric cards with real data

### 6. Control Center Updates (NEW ✅)
- `GET /api/control-center/stats` - Live recorder stats
- Real-time WebSocket updates for signals and trades
- PnL display per recorder
- Open/closed trade counts
- Toggle recorder on/off functionality

### 7. Templates
- `templates/recorders_list.html` - List page with search, pagination, actions
- `templates/recorders.html` - Create/Edit form with webhook modal
- `templates/control_center.html` - Live trading panel with real-time updates
- `templates/dashboard.html` - Uses recorded trades for charts & tables

---

## Database Schema

### `recorded_trades` Table
```sql
CREATE TABLE recorded_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    signal_id INTEGER,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    side TEXT NOT NULL,              -- LONG or SHORT
    entry_price REAL,
    entry_time DATETIME,
    exit_price REAL,
    exit_time DATETIME,
    quantity INTEGER DEFAULT 1,
    pnl REAL DEFAULT 0,
    pnl_ticks REAL DEFAULT 0,
    fees REAL DEFAULT 0,
    status TEXT DEFAULT 'open',      -- open or closed
    exit_reason TEXT,                -- signal, reversal, etc.
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recorder_id) REFERENCES recorders(id),
    FOREIGN KEY (signal_id) REFERENCES recorded_signals(id)
);
```

### `recorded_signals` Table
```sql
CREATE TABLE recorded_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    ticker TEXT,
    price REAL,
    position_size TEXT,
    market_position TEXT,
    signal_type TEXT,
    raw_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recorder_id) REFERENCES recorders(id)
);
```

---

## How It Works

### Signal → Trade Flow
1. TradingView sends webhook to `/webhook/<token>`
2. Signal is recorded to `recorded_signals`
3. Trade processing logic kicks in:
   - Checks for open trades for this recorder
   - If BUY and has open SHORT → closes SHORT with PnL, opens new LONG
   - If SELL and has open LONG → closes LONG with PnL, opens new SHORT
   - If CLOSE → closes any open position
4. Trade is recorded to `recorded_trades`
5. WebSocket events emitted for real-time UI updates

### PnL Calculation
```python
tick_size = get_tick_size(ticker)  # e.g., 0.25 for MNQ
tick_value = get_tick_value(ticker)  # e.g., $0.50 for MNQ

if side == 'LONG':
    pnl_ticks = (exit_price - entry_price) / tick_size
else:  # SHORT
    pnl_ticks = (entry_price - exit_price) / tick_size

pnl = pnl_ticks * tick_value * quantity
```

---

## Testing

### Test Webhook (Example)
```bash
# Get webhook token
sqlite3 just_trades.db "SELECT webhook_token FROM recorders WHERE id = 3"

# Send BUY signal
curl -X POST http://localhost:8082/webhook/<TOKEN> \
  -H "Content-Type: application/json" \
  -d '{"recorder": "My Strategy", "action": "buy", "ticker": "MNQ1!", "price": "21500.25"}'

# Send SELL signal (closes LONG, opens SHORT)
curl -X POST http://localhost:8082/webhook/<TOKEN> \
  -H "Content-Type: application/json" \
  -d '{"recorder": "My Strategy", "action": "sell", "ticker": "MNQ1!", "price": "21510.50"}'
```

### API Endpoints Testing
```bash
# Control center stats
curl http://localhost:8082/api/control-center/stats

# Recorder PnL
curl http://localhost:8082/api/recorders/3/pnl

# Trade history
curl "http://localhost:8082/api/dashboard/trade-history?timeframe=all"

# Chart data
curl "http://localhost:8082/api/dashboard/chart-data?timeframe=month"
```

---

## Key Files Modified

| File | Changes |
|------|---------|
| `ultra_simple_server.py` | Added trade recording logic, PnL endpoints, control center API |
| `templates/control_center.html` | Real-time updates, live PnL display |
| `templates/dashboard.html` | Already connected to trade data |
| `just_trades.db` | New `recorded_trades` table |

---

## Important Notes

1. **Tab Isolation:** Only modified files for Recorders/Dashboard/Control Center tabs
2. **Protected Files:** Did NOT touch `templates/account_management.html`
3. **Server Port:** 8082
4. **Ngrok:** Running on port 8082 for TradingView webhooks

---

## UI Updates (Trade Manager Style)

The dashboard has been updated to match Trade Manager's layout:

1. **Filter Bar** - Compact design with "VIEWING RECORDED STRATS" button
2. **Strategy Label** - Shows selected strategy name below filters (like Trade Manager)
3. **Metric Cards** - 8 cards visible by default:
   - Cumulative Return (Time Traded + Return)
   - W_L_WINRATE (Wins, Losses, % Winrate)
   - Drawdown (Max DD, Avg DD, Run DD)
   - Total ROI
   - Contracts Held (Max Size, Avg Size)
   - TM Score (placeholder)
   - Max/Avg PNL (Max/Avg Profit, Max/Avg Loss)
   - Profit Factor
4. **Hide All Cards Toggle** - Like Trade Manager
5. **Profit vs Drawdown Chart** - Line chart with date labels
6. **Trade History Table** - STATUS, OPEN TIME, CLOSED TIME, STRATEGY, SYMBOL, SIDE, SIZE, ENTRY, EXIT, PROFIT, DRAWDOWN
7. **Calendar** - Monthly view with daily PnL and trade counts

---

## TP/SL Implementation Details

### Database Schema Update
```sql
-- New columns in recorded_trades
tp_price REAL,        -- Take profit price level
sl_price REAL,        -- Stop loss price level
tp_ticks REAL,        -- TP in ticks (from recorder settings)
sl_ticks REAL,        -- SL in ticks (from recorder settings)
max_favorable REAL,   -- Max favorable excursion (MFE)
max_adverse REAL      -- Max adverse excursion (MAE)
```

### TP/SL Calculation
When a trade opens:
```python
# LONG position
tp_price = entry_price + (tp_ticks * tick_size)
sl_price = entry_price - (sl_ticks * tick_size)

# SHORT position
tp_price = entry_price - (tp_ticks * tick_size)
sl_price = entry_price + (sl_ticks * tick_size)
```

### PnL Calculation
```python
pnl = pnl_ticks * tick_value * quantity

# MNQ example: 20 ticks × $0.50 × 1 contract = $10.00
```

### Tick Values by Symbol
| Symbol | Tick Size | Tick Value |
|--------|-----------|------------|
| MNQ | 0.25 | $0.50 |
| MES | 0.25 | $1.25 |
| NQ | 0.25 | $5.00 |
| ES | 0.25 | $12.50 |
| CL | 0.01 | $10.00 |

---

## Real-Time Price Sources (Priority Order)

1. **TradingView WebSocket** - Primary (requires session cookies)
2. **Tradovate Market Data** - Secondary (requires mdAccessToken)
3. **TradingView Scanner API** - Fallback (public, 5s polling)

## Session Cookie Refresh

TradingView cookies expire periodically. To refresh:

1. Open Chrome → tradingview.com → DevTools (F12)
2. Application tab → Cookies → www.tradingview.com
3. Copy `sessionid` and `sessionid_sign`
4. POST to `/api/tradingview/session`

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tradingview/session` | POST | Store TradingView session |
| `/api/tradingview/session` | GET | Check session status |
| `/webhook/<token>` | POST | Receive TradingView signals |
| `/api/recorders/<id>/pnl` | GET | Get recorder PnL stats |
| `/api/recorders/<id>/trades` | GET | Get trade history |
| `/api/control-center/stats` | GET | Live recorder stats |

---

## Next Steps (Optional Enhancements)

1. **Close All Positions Button** - Implement in Control Center
2. **Historical Backfill** - Process old signals into trades
3. **Advanced Risk Metrics** - Sharpe ratio, Sortino ratio, etc.
4. **Trade Notes/Tags** - Add annotations to trades
5. **Export to CSV** - Trade history export feature
6. **Session Auto-Refresh** - Detect expired session and prompt user

---

**Last Updated:** December 3, 2025  
**Status:** ✅ COMPLETE - Full trade recording with real-time TradingView price monitoring
