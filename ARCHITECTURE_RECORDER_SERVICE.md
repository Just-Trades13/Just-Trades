# 📐 Architectural Analysis & Recorder Service Implementation Plan

**Created:** December 4, 2025  
**Status:** PLANNING PHASE - No code changes made yet  
**Backup:** `backups/WORKING_STATE_DEC4_2025_PRE_RECORDER_SERVICE/`

---

## 🎯 Goal

Create a **robust, scalable recording system** that:
1. Tracks drawdown accurately (like Trade Manager)
2. Handles 100+ users with many strategies
3. Is maintainable and testable
4. Can fail independently without crashing the main server

---

## 📊 Current Architecture Analysis

### File: `ultra_simple_server.py` (7,658 lines)

```
┌─────────────────────────────────────────────────────────────────┐
│                    ultra_simple_server.py                        │
│                         (7,658 lines)                            │
├─────────────────────────────────────────────────────────────────┤
│ RESPONSIBILITIES:                                                │
│                                                                  │
│ 1. WEB SERVER (Flask + SocketIO)                                │
│    - HTML template serving                                       │
│    - API endpoints for all features                              │
│    - WebSocket for real-time updates                            │
│                                                                  │
│ 2. AUTHENTICATION                                                │
│    - Tradovate OAuth flow (~lines 1300-1500)                    │
│    - Token management                                            │
│                                                                  │
│ 3. ACCOUNT MANAGEMENT                                            │
│    - Account CRUD operations                                     │
│    - Subaccount handling                                         │
│                                                                  │
│ 4. TRADING (Manual & Copy)                                       │
│    - Manual trade execution                                      │
│    - Copy trading logic                                          │
│    - Position management                                         │
│                                                                  │
│ 5. RECORDERS (Signal Recording)                                  │
│    - Webhook handler (~lines 2800-3400)                         │
│    - Trade creation/closing                                      │
│    - Position tracking (~lines 3058-3146)                       │
│                                                                  │
│ 6. PRICE STREAMING                                               │
│    - TradingView WebSocket (~lines 6321-6544)                   │
│    - Tradovate WebSocket (~lines 5750-5893)                     │
│    - Market data cache                                           │
│                                                                  │
│ 7. TP/SL MONITORING                                              │
│    - check_recorder_trades_tp_sl() (~lines 5895-6100)           │
│    - poll_recorder_tp_sl_thread() (~lines 6102-6190)            │
│                                                                  │
│ 8. DRAWDOWN TRACKING                                             │
│    - poll_recorder_positions_drawdown() (~lines 6199-6284)      │
│    - 1-second polling loop                                       │
│                                                                  │
│ 9. DASHBOARD API                                                 │
│    - Trade history (~lines 4744-4900)                           │
│    - Chart data                                                  │
│    - Metrics                                                     │
│                                                                  │
│ 10. BACKGROUND THREADS (Started at lines 7612-7643)             │
│     - emit_realtime_updates (PnL updates)                       │
│     - record_strategy_pnl_continuously                          │
│     - start_market_data_websocket (Tradovate)                   │
│     - start_recorder_tp_sl_polling (Fallback)                   │
│     - start_position_drawdown_polling (Trade Manager style)     │
│     - start_tradingview_websocket (Real-time prices)            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema (Complete)

### Tables Used by Recording System:

```sql
-- RECORDERS: Strategy configurations
CREATE TABLE recorders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    strategy_type TEXT DEFAULT 'Futures',
    symbol TEXT,
    initial_position_size INTEGER DEFAULT 2,
    tp_targets TEXT DEFAULT '[]',           -- JSON array
    sl_enabled INTEGER DEFAULT 0,
    sl_amount REAL DEFAULT 0,
    sl_units TEXT DEFAULT 'Ticks',
    webhook_token TEXT,
    recording_enabled INTEGER DEFAULT 1,
    signal_count INTEGER DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME
);

-- RECORDED_SIGNALS: Every webhook received
CREATE TABLE recorded_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    action TEXT NOT NULL,                   -- BUY, SELL, CLOSE, TP_HIT, SL_HIT
    ticker TEXT,
    price REAL,
    position_size TEXT,
    market_position TEXT,
    signal_type TEXT,                       -- 'strategy' or 'alert'
    raw_data TEXT,                          -- Original JSON
    created_at DATETIME,
    FOREIGN KEY (recorder_id) REFERENCES recorders(id)
);

-- RECORDED_TRADES: Individual trades
CREATE TABLE recorded_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    signal_id INTEGER,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    side TEXT NOT NULL,                     -- LONG or SHORT
    entry_price REAL,
    entry_time DATETIME,
    exit_price REAL,
    exit_time DATETIME,
    quantity INTEGER DEFAULT 1,
    pnl REAL DEFAULT 0,
    pnl_ticks REAL DEFAULT 0,
    status TEXT DEFAULT 'open',             -- 'open' or 'closed'
    exit_reason TEXT,                       -- 'tp', 'sl', 'signal', 'reversal'
    tp_price REAL,                          -- Calculated TP level
    sl_price REAL,                          -- Calculated SL level
    tp_ticks REAL,
    sl_ticks REAL,
    max_favorable REAL DEFAULT 0,           -- MFE tracking
    max_adverse REAL DEFAULT 0,             -- MAE tracking
    worst_price REAL,
    FOREIGN KEY (recorder_id) REFERENCES recorders(id)
);

-- RECORDER_POSITIONS: Combined positions (Trade Manager style)
CREATE TABLE recorder_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,                     -- LONG or SHORT
    total_quantity INTEGER DEFAULT 0,       -- Combined size
    avg_entry_price REAL,                   -- Weighted average
    entries TEXT,                           -- JSON array of entries
    current_price REAL,
    unrealized_pnl REAL DEFAULT 0,
    worst_unrealized_pnl REAL DEFAULT 0,    -- THIS IS DRAWDOWN
    best_unrealized_pnl REAL DEFAULT 0,
    exit_price REAL,
    realized_pnl REAL,
    status TEXT DEFAULT 'open',
    opened_at DATETIME,
    closed_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY (recorder_id) REFERENCES recorders(id)
);
```

---

## 🔴 Current Problem: Why Drawdown Shows $0.00

### The Issue:

Looking at your screenshots:
- **Trade Manager**: Shows drawdown values like -2.00, -7.00
- **Just.Trades**: Shows $0.00 for all trades

### Root Cause Analysis:

1. **Polling Thread May Not Be Starting**
   - Server logs don't show "Position drawdown tracking active" 
   - The `start_position_drawdown_polling()` function may fail silently

2. **Trades Close Too Fast**
   - Your trades open and close within 1 second
   - 1-second polling can miss the entire trade lifecycle
   - No drawdown captured = $0.00 on close

3. **Event-Driven Updates Only Track TP/SL**
   - `check_recorder_trades_tp_sl()` (line 6522) IS called on every price
   - But it only updates MFE/MAE on `recorded_trades`, not `recorder_positions`
   - Dashboard reads from `recorder_positions` which never gets updated

4. **Database Query Issue**
   - Dashboard at line 4826: `'drawdown': abs(pos.get('worst_unrealized_pnl') or 0)`
   - If `worst_unrealized_pnl` is never updated, it stays 0

### The Fix Needed:

Update `worst_unrealized_pnl` **on every price tick**, not via polling.

---

## ✅ Proposed Solution: Event-Driven Drawdown

### Option A: Quick Fix (Modify existing code)

Add drawdown tracking to `check_recorder_trades_tp_sl()` function.

**Pros:** Fast to implement, minimal changes  
**Cons:** More code in already-large function

### Option B: Recorder Service (New architecture)

Create `recorder_service.py` that handles all recording logic.

**Pros:** Clean separation, scalable, testable, isolated failures  
**Cons:** More initial work, needs coordination between services

---

## 🏗️ Recommended: Option B - Recorder Service Architecture

### New File Structure:

```
/Users/mylesjadwin/Trading Projects/
├── ultra_simple_server.py          # Main server (reduced to ~5,000 lines)
├── recorder_service.py             # NEW: Recording engine (~1,500 lines)
├── just_trades.db                  # Shared database
└── backups/
    └── WORKING_STATE_DEC4_2025_PRE_RECORDER_SERVICE/
```

### Recorder Service Responsibilities:

```python
# recorder_service.py - Dedicated Recording Engine
"""
RESPONSIBILITIES:
1. TradingView WebSocket connection (price streaming)
2. Webhook endpoint processing (signals)
3. Position management (open/close/DCA)
4. Real-time drawdown tracking (event-driven)
5. TP/SL monitoring
6. Health check endpoint
"""
```

### Communication Between Services:

```
┌─────────────────────────┐         ┌─────────────────────────┐
│  ultra_simple_server.py │         │   recorder_service.py   │
│      (Port 8082)        │         │      (Port 8083)        │
│                         │         │                         │
│  • UI/Dashboard         │         │  • Webhook endpoint     │
│  • Account Management   │◄───────►│  • Price streaming      │
│  • Manual Trading       │ SQLite  │  • Position tracking    │
│  • Settings             │         │  • Drawdown calc        │
│  • API for UI           │         │  • TP/SL monitoring     │
│                         │         │                         │
└─────────────────────────┘         └─────────────────────────┘
                │                              │
                └──────────┬───────────────────┘
                           │
                    just_trades.db
```

### Key Design Decisions:

1. **Shared SQLite Database**
   - Both services read/write same database
   - Simple, no message broker needed
   - SQLite handles concurrent access

2. **Event-Driven Drawdown**
   - On every TradingView price tick:
     1. Update `recorder_positions.worst_unrealized_pnl`
     2. Check TP/SL
     3. Close position if hit
   - No polling needed

3. **In-Memory Position Index**
   ```python
   # O(1) lookup: symbol → position IDs
   _open_positions_by_symbol = {
       "MNQ": [pos_id_1, pos_id_5],
       "MES": [pos_id_2],
   }
   ```

4. **Health Check**
   - Main server checks recorder health
   - Auto-restart if recorder dies

---

## 📋 Implementation Plan (Step by Step)

### Phase 1: Preparation (No code changes)
- [x] Create backup of current state
- [x] Document current architecture
- [ ] User approval of plan

### Phase 2: Quick Fix First (Optional)
If you want immediate results before full architecture:
- [ ] Add drawdown update to `check_recorder_trades_tp_sl()`
- [ ] Test with new trades
- [ ] Verify drawdown shows correctly

### Phase 3: Create Recorder Service
- [ ] Create `recorder_service.py` skeleton
- [ ] Move TradingView WebSocket code
- [ ] Move webhook handler
- [ ] Move position tracking
- [ ] Move TP/SL monitoring
- [ ] Add health check endpoint

### Phase 4: Update Main Server
- [ ] Remove moved code from `ultra_simple_server.py`
- [ ] Add health check for recorder service
- [ ] Update documentation

### Phase 5: Testing
- [ ] Test webhook processing
- [ ] Test drawdown tracking
- [ ] Test TP/SL monitoring
- [ ] Test position closing
- [ ] Test service restart

### Phase 6: Documentation
- [ ] Update START_HERE.md
- [ ] Create recorder service documentation
- [ ] Update backup procedures

---

## 🔒 Backup & Recovery

### Current Backup:
```bash
backups/WORKING_STATE_DEC4_2025_PRE_RECORDER_SERVICE/
├── ultra_simple_server.py
├── just_trades.db
└── *.html (all templates)
```

### Git Tag:
```bash
# Create tag before any changes
git tag WORKING_DEC4_2025_PRE_RECORDER_SERVICE
```

### Recovery Commands:
```bash
# Restore everything
cp backups/WORKING_STATE_DEC4_2025_PRE_RECORDER_SERVICE/ultra_simple_server.py ./
cp backups/WORKING_STATE_DEC4_2025_PRE_RECORDER_SERVICE/just_trades.db ./
cp backups/WORKING_STATE_DEC4_2025_PRE_RECORDER_SERVICE/*.html templates/

# Or use git
git checkout WORKING_DEC4_2025_PRE_RECORDER_SERVICE
```

---

## 📊 Code to Move to Recorder Service

### From `ultra_simple_server.py`:

| Section | Lines | Purpose |
|---------|-------|---------|
| TradingView WebSocket | 6321-6544 | Price streaming |
| Webhook Handler | 2800-3400 | Signal processing |
| Position Tracking | 3058-3146 | Position open/close/DCA |
| TP/SL Monitoring | 5895-6100 | Check TP/SL on price |
| MFE/MAE Tracking | 5937-5976 | Track excursions |
| Drawdown Polling | 6199-6295 | (Replace with event-driven) |

**Total: ~1,500 lines to extract**

### Keep in Main Server:

| Section | Lines | Purpose |
|---------|-------|---------|
| OAuth Flow | 1300-1500 | Account auth |
| Account Management | Various | CRUD operations |
| Manual Trading | Various | Execute trades |
| Dashboard API | 4744-4900 | Trade history |
| UI Routes | Various | Serve templates |

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Break existing features | Full backup, git tag, incremental changes |
| Database conflicts | SQLite WAL mode, single-writer design |
| Service coordination | Health checks, auto-restart |
| Webhook downtime | Quick cutover, test webhook first |

---

## 🚀 Next Steps

**I need your approval before proceeding.**

Choose one:

### A) Quick Fix Only
- Modify `check_recorder_trades_tp_sl()` to update `recorder_positions` drawdown
- ~20 lines of code change
- Immediate results
- Can still do full architecture later

### B) Full Architecture
- Create recorder service
- Proper separation
- More work upfront
- Better long-term

### C) Both (Recommended)
- Quick fix first for immediate results
- Then implement full architecture

**What would you like me to do?**

---

## 📝 Approval Checklist

Before I make ANY changes:

- [ ] You approve the approach (A, B, or C)
- [ ] You confirm backup is acceptable
- [ ] You understand the risks
- [ ] You're ready for me to proceed

---

*Document created: Dec 4, 2025*
*Author: AI Assistant (with user oversight)*
*No code changes made - this is a planning document*
