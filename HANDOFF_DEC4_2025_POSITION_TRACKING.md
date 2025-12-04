# 🔄 HANDOFF: Position-Based Drawdown Tracking (Trade Manager Style) - Dec 4, 2025

---

## 📋 Session Summary

**Date:** December 4, 2025  
**Duration:** Full implementation session  
**Status:** ✅ **COMPLETE AND WORKING**

### What Was Implemented
Replicated Trade Manager's position tracking and drawdown behavior in Just.Trades:
1. ✅ DCA entries combine into single position with weighted average entry
2. ✅ Real-time drawdown tracking (worst_unrealized_pnl) via 1-second polling
3. ✅ Position closes when TP/SL hits (matches Trade Manager behavior)
4. ✅ Dashboard shows position-based data instead of individual trades
5. ✅ Reset History button now clears positions too

---

## 🏗️ Database Changes

### New Table: `recorder_positions`
```sql
CREATE TABLE recorder_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    total_quantity INTEGER DEFAULT 0,
    avg_entry_price REAL,
    entries TEXT,                    -- JSON array of individual entries
    current_price REAL,
    unrealized_pnl REAL DEFAULT 0,
    worst_unrealized_pnl REAL DEFAULT 0,  -- THIS IS THE DRAWDOWN
    best_unrealized_pnl REAL DEFAULT 0,
    exit_price REAL,
    realized_pnl REAL,
    status TEXT DEFAULT 'open',
    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recorder_id) REFERENCES recorders(id)
);
```

---

## 🔧 Code Changes Made

### File: `ultra_simple_server.py`

#### 1. Table Creation (Line ~912)
Added `recorder_positions` table creation in `init_db()` function.

#### 2. Helper Functions (Lines ~3053-3140)
Added two helper functions inside `receive_webhook()`:
- `close_recorder_position()` - Closes a position and calculates final PnL
- `update_recorder_position()` - Creates or updates position (DCA logic)

#### 3. Webhook Handler - BUY/SELL (Lines ~3281, ~3325)
Added `update_recorder_position()` calls in BUY and SELL blocks to track positions.

#### 4. Webhook Handler - CLOSE/TP_HIT/SL_HIT (Lines ~3167-3280)
Added position closing when trades close via signals.

#### 5. TP/SL Monitoring Thread (Lines ~6013-6055)
Added position closing in `check_recorder_trades_tp_sl()` when background TP/SL monitoring closes trades.

#### 6. Position Drawdown Polling Thread (Lines ~6150-6250)
New function `poll_recorder_positions_drawdown()`:
- Runs every 1 second
- Updates `current_price`, `unrealized_pnl`, `worst_unrealized_pnl`, `best_unrealized_pnl`
- Started via `start_position_drawdown_polling()`

#### 7. Dashboard API (Lines ~4712-4870)
Modified `/api/dashboard/trade-history` to read from `recorder_positions` table:
- Shows combined position size (`total_quantity`)
- Shows weighted average entry (`avg_entry_price`)
- Shows real drawdown (`worst_unrealized_pnl`)
- Falls back to `recorded_trades` if no positions exist

#### 8. Reset History Endpoint (Lines ~2384-2402)
Added deletion of `recorder_positions` in reset-history endpoint.

---

## 📊 How It Works Now (Trade Manager Style)

### Position Lifecycle:
```
1. BUY signal → Create new position (qty=1, entry=price)
2. BUY signal → Add to position (qty++, avg_entry recalculated)
3. BUY signal → Add to position (qty++, avg_entry recalculated)
4. [Polling thread updates worst_unrealized_pnl every 1 second]
5. TP HIT → Close position, record final drawdown
6. New BUY signal → Create NEW position (fresh start)
```

### Drawdown Calculation:
```python
if side == 'LONG':
    unrealized_pnl = (current_price - avg_entry) / tick_size * tick_value * total_qty
else:  # SHORT
    unrealized_pnl = (avg_entry - current_price) / tick_size * tick_value * total_qty

worst_unrealized_pnl = min(current_worst, unrealized_pnl)  # Most negative value
```

---

## ✅ Verification

### Confirmed Working:
- **$144.50 drawdown** matched between Trade Manager and Just.Trades
- **Position combining** - Size: 2, 15, 24 shown correctly
- **Weighted average entry** calculated correctly
- **Reset History** clears all data including positions
- **Real-time tracking** - drawdown updates every 1 second

---

## 📁 Backup Locations

```
backups/WORKING_STATE_DEC4_2025_POSITION_TRACKING/
└── ultra_simple_server.py

Git tag: WORKING_DEC4_2025_POSITION_TRACKING
```

---

## 🚀 Quick Commands

```bash
# Restart server
pkill -f "python.*ultra_simple" && nohup python3 ultra_simple_server.py > /tmp/server.log 2>&1 &

# Start ngrok
nohup ngrok http 8082 --domain=clay-ungilled-heedlessly.ngrok-free.dev > /tmp/ngrok.log 2>&1 &

# Check open positions
sqlite3 just_trades.db "SELECT id, ticker, side, total_quantity, avg_entry_price, worst_unrealized_pnl, status FROM recorder_positions ORDER BY id DESC LIMIT 10;"

# Check closed positions with drawdown
sqlite3 just_trades.db "SELECT id, ticker, side, total_quantity, avg_entry_price, exit_price, realized_pnl, worst_unrealized_pnl FROM recorder_positions WHERE status='closed' ORDER BY id DESC LIMIT 10;"

# Clear all position data (for testing)
sqlite3 just_trades.db "DELETE FROM recorder_positions;"
```

---

## 🔑 Key Files

| File | Purpose |
|------|---------|
| `ultra_simple_server.py` | Main server with all position tracking code |
| `just_trades.db` | Database with `recorder_positions` table |
| `START_HERE.md` | Project documentation (should be updated) |
| `IMPLEMENTATION_PLAN_RECORDER_DRAWDOWN.md` | Original implementation plan |

---

## ⚠️ Important Notes

1. **Historical trades** before this implementation show $0.00 drawdown - this is expected
2. **New trades** going forward will have proper drawdown tracking
3. **Position closes on TP/SL** - matches Trade Manager behavior
4. **1-second polling** ensures accurate drawdown capture

---

## 🔗 Related Documentation

- `HANDOFF_DEC4_2025_MFE_MAE.md` - Previous MFE/MAE fix (individual trades)
- `IMPLEMENTATION_PLAN_RECORDER_DRAWDOWN.md` - Original plan document
- `START_HERE.md` - Main project documentation

---

## 📝 Next Steps / Future Work

1. Consider adding position data to My Recorders tab
2. Consider showing open positions on dashboard (like Trade Manager's "OPEN" status)
3. Historical backfill of drawdown data (if needed)

---

*Created: Dec 4, 2025*  
*Git Tag: WORKING_DEC4_2025_POSITION_TRACKING*  
*Backup: backups/WORKING_STATE_DEC4_2025_POSITION_TRACKING/*
