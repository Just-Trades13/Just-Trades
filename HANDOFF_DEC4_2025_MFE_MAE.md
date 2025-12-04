# 🔄 HANDOFF: MFE/MAE & Reset History Fixes - Dec 4, 2025

---

## 📋 Session Summary

**Date:** December 4, 2025  

### Fix 1: MFE/MAE (Drawdown) Tracking
**Issue:** All trades showed 0 drawdown (`max_adverse = 0`) despite being a DCA strategy where drawdown is inevitable  
**Root Cause:** The `check_recorder_trades_tp_sl()` function monitored prices but never updated `max_favorable` or `max_adverse` columns  
**Solution:** Added MFE/MAE tracking code inside `check_recorder_trades_tp_sl()` that updates on every price tick  
**Status:** ✅ FIXED AND WORKING

### Fix 2: Reset Trade History Button
**Issue:** "Reset Trade History" button in My Recorders was not working  
**Root Cause:** Frontend button called `/api/recorders/<id>/reset-history` but the backend endpoint didn't exist  
**Solution:** Added the missing API endpoint to `ultra_simple_server.py`  
**Status:** ✅ FIXED AND WORKING

---

## ✅ What Was Fixed

### The Problem
- `recorded_trades` table had columns for `max_favorable` and `max_adverse`
- Documentation claimed `update_trade_mfe_mae()` function existed - **IT DIDN'T**
- All 592+ closed trades showed `0.0` for both values
- Impossible for a DCA strategy to have zero drawdown on every trade

### The Solution
Added MFE/MAE tracking code inside `check_recorder_trades_tp_sl()` function at lines ~5657-5697 in `ultra_simple_server.py`.

### Code Added (lines ~5657-5697)
```python
# =====================================================
# MFE/MAE TRACKING - Update on every price tick
# =====================================================
side = trade['side']
entry_price = trade['entry_price']
tick_size = get_tick_size(ticker)
tick_value = get_tick_value(ticker)

# Get current MFE/MAE values
current_max_favorable = trade.get('max_favorable') or 0
current_max_adverse = trade.get('max_adverse') or 0

# Calculate current excursion based on trade direction
if side == 'LONG':
    # For LONG: favorable = price went UP, adverse = price went DOWN
    favorable_excursion = max(0, current_price - entry_price)
    adverse_excursion = max(0, entry_price - current_price)
else:  # SHORT
    # For SHORT: favorable = price went DOWN, adverse = price went UP
    favorable_excursion = max(0, entry_price - current_price)
    adverse_excursion = max(0, current_price - entry_price)

# Update MFE/MAE if we have new highs/lows
new_max_favorable = max(current_max_favorable, favorable_excursion)
new_max_adverse = max(current_max_adverse, adverse_excursion)

# Only update database if values changed (to reduce DB writes)
if new_max_favorable != current_max_favorable or new_max_adverse != current_max_adverse:
    cursor.execute('''
        UPDATE recorded_trades 
        SET max_favorable = ?, max_adverse = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (new_max_favorable, new_max_adverse, trade['id']))
    conn.commit()
```

### Evidence It's Working
```
Before: Trade 2226 | max_favorable=0.0 | max_adverse=0.0
After:  Trade 2226 | max_favorable=0.0 | max_adverse=0.75  ← TRACKING!
```

---

## 📁 Backup Locations

### Files Backed Up
```
backups/WORKING_STATE_DEC4_2025_MFE_MAE/
└── ultra_simple_server.py  ← Contains the MFE/MAE fix

backups/WORKING_STATE_DEC4_2025_RESET_HISTORY/
├── ultra_simple_server.py  ← Contains both fixes
└── recorders_list.html
```

### Git Tags
```bash
git tag WORKING_DEC4_2025_MFE_MAE
git tag WORKING_DEC4_2025_RESET_HISTORY

# To restore if needed:
git checkout WORKING_DEC4_2025_RESET_HISTORY -- ultra_simple_server.py
```

### Git Commits
```
commit: "Add MFE/MAE (drawdown) tracking to check_recorder_trades_tp_sl() - Dec 4, 2025"
commit: "Add /api/recorders/<id>/reset-history endpoint - Dec 4, 2025"
```

---

## 🔑 Key Technical Details

### Function Modified
- **File:** `ultra_simple_server.py`
- **Function:** `check_recorder_trades_tp_sl()` (lines ~5616-5789)
- **Purpose:** Monitors open trades for TP/SL hits on every price tick

### Database Columns Used
```sql
-- In recorded_trades table:
max_favorable REAL DEFAULT 0  -- Max price movement IN FAVOR
max_adverse REAL DEFAULT 0    -- Max price movement AGAINST (drawdown)
```

### How MFE/MAE is Calculated
| Trade Side | max_favorable | max_adverse |
|------------|---------------|-------------|
| LONG | max(current_price - entry_price) | max(entry_price - current_price) |
| SHORT | max(entry_price - current_price) | max(current_price - entry_price) |

### Values Stored
- **In price points** (not ticks or dollars)
- Example: `max_adverse = 0.75` on MES means price went 0.75 points against you
- To convert to ticks: `0.75 / 0.25 = 3 ticks`
- To convert to dollars: `3 ticks × $1.25/tick = $3.75`

---

## ⚠️ Important Notes

### Historical Trades
- All 592+ trades that closed BEFORE this fix will still show `0.0` drawdown
- This is expected - the tracking only works while trades are OPEN
- New trades going forward will track correctly

### TradingView Session
- MFE/MAE tracking requires price data from either:
  1. TradingView WebSocket (requires session cookies)
  2. Polling fallback (uses TradingView public API every 5 seconds)
- Currently: `"configured": false` for TradingView session
- Polling fallback is active and working

### Server Status
- Server running on port 8082
- PID can be found with: `pgrep -f "python.*ultra_simple"`
- Logs at: `/tmp/server.log`

---

## 🔧 How to Verify Fix is Working

### Check Open Trade MFE/MAE
```bash
sqlite3 just_trades.db "SELECT id, side, entry_price, max_favorable, max_adverse FROM recorded_trades WHERE status='open';"
```

### Check Server is Running
```bash
pgrep -f "python.*ultra_simple" && echo "Server running"
```

### Check Recent Logs
```bash
tail -50 /tmp/server.log
```

---

## 📝 Next Steps / Future Work

1. **Dashboard Display** - Consider adding MFE/MAE columns to the trade history table
2. **Dollar Conversion** - The dashboard API already has code to convert points to dollars:
   ```python
   drawdown_dollars = (max_adverse_points / tick_size * tick_value * quantity)
   ```
3. **Historical Backfill** - Could potentially recalculate MFE/MAE for closed trades if entry/exit prices allow inference

---

## 🚫 DO NOT MODIFY

These are critical and must not be changed without explicit permission:
- `ultra_simple_server.py` - Core server with MFE/MAE fix
- `templates/account_management.html` - NEVER TOUCH
- OAuth token exchange code (LIVE+DEMO fallback)

---

## 📞 Quick Commands

```bash
# Restart server
pkill -f "python.*ultra_simple"
nohup python3 ultra_simple_server.py > /tmp/server.log 2>&1 &

# Restore from backup
cp backups/WORKING_STATE_DEC4_2025_MFE_MAE/ultra_simple_server.py ./

# Or use git
git checkout WORKING_DEC4_2025_MFE_MAE -- ultra_simple_server.py

# Check MFE/MAE on trades
sqlite3 just_trades.db "SELECT id, side, entry_price, max_favorable, max_adverse FROM recorded_trades ORDER BY id DESC LIMIT 10;"
```

---

## 📅 Timeline

| Time | Action |
|------|--------|
| Session Start | User reported all trades showing 0 drawdown |
| Investigation | Found `max_favorable`/`max_adverse` columns exist but never updated |
| Root Cause | `update_trade_mfe_mae()` function referenced in docs but didn't exist |
| Fix Applied | Added MFE/MAE tracking to `check_recorder_trades_tp_sl()` |
| Verified | Trade 2226 now shows `max_adverse=0.75` (was 0.0) |
| Backed Up | Created backup + git tag `WORKING_DEC4_2025_MFE_MAE` |

---

## ✅ Reset Trade History Endpoint

### API Endpoint
```
POST /api/recorders/<recorder_id>/reset-history
```

### What It Does
- Deletes all `recorded_trades` for the specified recorder
- Deletes all `recorded_signals` for the specified recorder
- Keeps the recorder settings unchanged
- Returns count of deleted records

### Response Example
```json
{
    "success": true,
    "message": "Trade history reset for \"JADVIX\". Deleted 302 trades and 150 signals.",
    "trades_deleted": 302,
    "signals_deleted": 150
}
```

### How to Use
1. Go to **My Recorders** page
2. Click the **refresh icon** (🔄) next to the strategy
3. Confirm in the modal dialog
4. Trade history is cleared, strategy settings remain

---

*Last updated: Dec 4, 2025*
*Git tags: WORKING_DEC4_2025_MFE_MAE, WORKING_DEC4_2025_RESET_HISTORY*
*Backups: backups/WORKING_STATE_DEC4_2025_MFE_MAE/, backups/WORKING_STATE_DEC4_2025_RESET_HISTORY/*
