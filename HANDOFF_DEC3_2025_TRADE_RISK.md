# 🔄 Handoff Document - December 3, 2025
## Next Task: Trade & Risk Handling Improvements

---

## 📍 Current Working State

### ✅ What's Working Now

| Feature | Status | Notes |
|---------|--------|-------|
| Dashboard | ✅ Working | Market heatmap fixed (Yahoo/Finnhub) |
| Account Management | ✅ Working | Tradovate OAuth integration |
| Manual Trader | ✅ Working | Live positions, PnL display |
| WebSocket Updates | ✅ Working | Real-time positions/PnL |
| Trade Recording | ✅ Working | Recorders with TP/SL monitoring |
| OCO Tracking | ✅ Fixed | Orphaned order cleanup on startup |
| Timezone Display | ✅ Fixed | Chicago timezone (America/Chicago) |

### 🔧 Recent Fixes Applied (This Session)

1. **OCO Tracking + Orphaned Orders**
   - Added `cleanup_orphaned_orders()` function in `ultra_simple_server.py`
   - Runs 10 seconds after server startup
   - Cancels working orders that have no matching position
   - Prevents leftover TP/SL orders when server restarts

2. **Timezone Fix for Trade Times**
   - Modified `formatDateTime()` in `templates/dashboard.html`
   - Modified `addLogEntry()` in `templates/control_center.html`
   - Converts UTC timestamps to Chicago timezone
   - Times now display correctly (e.g., "Dec 03, 2025 08:32 PM")

3. **Protection System Fix**
   - Added `TAB_ISOLATION_MAP.md` to `.cursorignore`
   - Added to `.cursorrules` protected files list

---

## 🎯 Next Task: Trade & Risk Handling

### What You Want to Work On

The user wants to improve how trades and risk are handled to match their vision. Key areas likely include:

1. **Trade Execution Flow**
   - How trades are placed (market vs limit)
   - Entry order handling
   - Position sizing

2. **Risk Management**
   - Take Profit (TP) handling
   - Stop Loss (SL) handling
   - OCO (One-Cancels-Other) behavior
   - Break-even functionality
   - Trailing stops

3. **Order Management**
   - How orders are tracked
   - Order status updates
   - Order cancellation logic

### Current Implementation Overview

#### Key Files for Trade/Risk:

```
ultra_simple_server.py
├── apply_risk_management_orders() - Line ~285
│   └── Places TP/SL as OCO orders after entry fills
│
├── place_exit_oco() - In tradovate_integration.py
│   └── Creates OCO bracket orders via Tradovate API
│
├── monitor_oco_orders() - Line ~5877
│   └── Background thread checking for filled orders
│   └── Cancels partner order when one fills
│
├── cleanup_orphaned_orders() - Line ~6075
│   └── Startup cleanup for orphaned working orders
│
├── register_break_even_monitor() - Line ~6083
│   └── Moves SL to entry when position goes profitable
│
└── Manual Trade Handler - Around line 3600
    └── /api/manual-trade endpoint
    └── Handles BUY/SELL/CLOSE with risk parameters
```

#### Risk Config Structure (from manual trader):

```javascript
{
    action: 'BUY' | 'SELL' | 'CLOSE',
    symbol: 'MNQZ5',
    quantity: 1,
    account_id: 26029294,
    order_type: 'MARKET' | 'LIMIT',
    limit_price: null,
    
    // Risk Management
    take_profit_enabled: true,
    take_profit_ticks: 20,
    stop_loss_enabled: true,
    stop_loss_ticks: 10,
    trailing_stop_enabled: false,
    trailing_stop_ticks: 8,
    break_even_enabled: false,
    break_even_ticks: 10
}
```

---

## 📁 Key Files Reference

### Core Files (Modify Carefully)

| File | Purpose |
|------|---------|
| `ultra_simple_server.py` | Main Flask server - ALL endpoints |
| `phantom_scraper/tradovate_integration.py` | Tradovate API client |
| `templates/manual_copy_trader.html` | Manual Trader UI |
| `templates/dashboard.html` | Dashboard UI |

### Database Tables

```sql
-- Main database: just_trades.db

-- Accounts & Tokens
accounts (id, name, tradovate_token, tradovate_accounts, ...)

-- Open Positions (in-memory + DB)
open_positions (symbol, net_quantity, avg_price, account_id, ...)

-- Recorded Trades (for recorders)
recorded_trades (id, recorder_id, entry_price, exit_price, pnl, ...)
```

---

## 🚀 How to Start

### Server Startup
```bash
cd "/Users/mylesjadwin/Trading Projects"
python3 ultra_simple_server.py
# Server runs on http://localhost:8082
```

### Current Git State
- **Tag:** `stable-dec3-2025` - Known good state
- **Branch:** `main`
- **Database Backup:** `backups/just_trades_dec3_2025.db`

### Restore If Needed
```bash
git checkout stable-dec3-2025
cp backups/just_trades_dec3_2025.db just_trades.db
```

---

## 📋 Tab Isolation Rules

**CRITICAL:** Only modify files for the tab you're working on!

### Manual Trader Tab Files:
- `templates/manual_copy_trader.html`
- `/api/manual-trade` endpoint
- `/api/positions` endpoint
- Related WebSocket handlers

### Dashboard Tab Files:
- `templates/dashboard.html`
- `/api/dashboard/*` endpoints

### Recorders Tab Files:
- `templates/recorders.html`
- `templates/recorders_list.html`
- `/api/recorders/*` endpoints
- `/webhook/*` endpoints

**See `TAB_ISOLATION_MAP.md` for complete mappings.**

---

## ⚠️ Protection Rules

1. **DO NOT modify** `templates/account_management.html` - LOCKED
2. **Read** `WHAT_NOT_TO_DO.md` before making changes
3. **Check** `.cursorignore` for protected files
4. **Use sandbox** for experimental changes

---

## 🔗 API Endpoints Summary

### Trade Execution
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/manual-trade` | POST | Execute manual trades |
| `/api/positions` | GET | Get current positions |
| `/api/orders` | GET | Get working orders |

### Risk Management
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/cancel-order/<id>` | POST | Cancel specific order |
| `/api/close-position` | POST | Close position + cancel orders |

### WebSocket Events
| Event | Direction | Purpose |
|-------|-----------|---------|
| `position_update` | Server→Client | Real-time position data |
| `pnl_update` | Server→Client | Real-time PnL data |
| `oco_triggered` | Server→Client | OCO order filled notification |

---

## 📝 Notes for Next Session

1. **OCO Monitor runs every 1 second** - Check `monitor_oco_orders()` for polling logic
2. **Break-even monitor** is separate from OCO - See `_break_even_monitors` dict
3. **Trailing stops** are implemented but may need refinement
4. **Tick values** are in `TICK_INFO` dict at top of `ultra_simple_server.py`

### Questions to Clarify:
- How should TP/SL be placed? (Immediately after entry? Wait for fill confirmation?)
- OCO behavior - Native Tradovate OCO vs custom monitoring?
- Trailing stop calculation - Based on entry or current price?
- Break-even activation - How many ticks profitable before moving SL?

---

## ✅ Session Summary

### What Was Done:
1. ✅ Fixed OCO tracking - Added orphaned order cleanup
2. ✅ Fixed timezone display - Chicago time for trade history
3. ✅ Protected TAB_ISOLATION_MAP.md in .cursorignore
4. ✅ Verified dashboard trade times showing correctly
5. ✅ Created save state with git tag `stable-dec3-2025`

### Commits Made:
- `8191a96` - Protect TAB_ISOLATION_MAP.md in .cursorignore
- `db1b16d` - Fix trade times to display in Chicago timezone
- `b2ab9c9` - Add orphaned order cleanup on server startup
- `c803a6f` - SAVE STATE: Working Trading System - Dec 3, 2025

---

**Last Updated:** December 3, 2025  
**Status:** ✅ Ready for Trade & Risk Handling work
