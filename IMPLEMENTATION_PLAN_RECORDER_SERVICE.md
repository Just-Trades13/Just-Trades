# 🏗️ Recorder Service Implementation Plan

**Date:** December 4, 2025  
**Goal:** Create scalable, event-driven recording system  
**Approach:** Separate `recorder_service.py` that works alongside `ultra_simple_server.py`

---

## 📋 Overview

### What We're Building:

```
┌─────────────────────────┐         ┌─────────────────────────┐
│  ultra_simple_server.py │         │   recorder_service.py   │
│      (Port 8082)        │         │      (Port 8083)        │
│                         │         │                         │
│  • Dashboard UI         │         │  • Webhook processing   │
│  • Account Management   │◄───────►│  • Price streaming      │
│  • Manual Trading       │ SQLite  │  • Position tracking    │
│  • Settings             │         │  • Drawdown (real-time) │
│  • API for UI           │         │  • TP/SL monitoring     │
│                         │         │  • Event-driven design  │
└─────────────────────────┘         └─────────────────────────┘
```

### Why This Architecture:

| Benefit | Description |
|---------|-------------|
| **Scalability** | Handles 100+ users, no polling overhead |
| **Reliability** | Recorder crash doesn't kill main server |
| **Accuracy** | Event-driven = captures every tick |
| **Maintainability** | Smaller, focused files |
| **Testability** | Test recorder logic independently |

---

## 🔧 recorder_service.py Structure

### File Layout (~1,200 lines total):

```python
#!/usr/bin/env python3
"""
Recorder Service - Event-Driven Trade Recording Engine

Responsibilities:
1. Receive webhooks from TradingView
2. Stream prices via TradingView WebSocket
3. Track positions with real-time drawdown
4. Monitor TP/SL on every price tick
5. Update database for dashboard consumption

Runs independently on port 8083
Shares just_trades.db with main server
"""

# ============================================================
# SECTION 1: Imports & Configuration (~50 lines)
# ============================================================
# - Flask for webhook endpoint
# - SQLite for database
# - WebSockets for TradingView
# - Threading for background tasks

# ============================================================
# SECTION 2: Database Helpers (~100 lines)
# ============================================================
# - get_db_connection()
# - Recorder queries
# - Position queries
# - Trade queries

# ============================================================
# SECTION 3: Price Utilities (~80 lines)
# ============================================================
# - get_tick_size(ticker)
# - get_tick_value(ticker)
# - extract_symbol_root(ticker)
# - CONTRACT_MULTIPLIERS

# ============================================================
# SECTION 4: Position Index (In-Memory) (~60 lines)
# ============================================================
# - _open_positions_by_symbol = {"MNQ": [pos_id_1, pos_id_2], ...}
# - add_position_to_index(symbol, position_id)
# - remove_position_from_index(symbol, position_id)
# - get_positions_for_symbol(symbol)
# - rebuild_position_index()

# ============================================================
# SECTION 5: Position Management (~200 lines)
# ============================================================
# - open_position(recorder_id, ticker, side, price, quantity)
# - add_to_position(position_id, price, quantity)  # DCA
# - close_position(position_id, exit_price, reason)
# - update_position_drawdown(position_id, current_price)

# ============================================================
# SECTION 6: Trade Management (~150 lines)
# ============================================================
# - open_trade(recorder_id, signal_id, ticker, side, price, quantity, tp, sl)
# - close_trade(trade_id, exit_price, reason)
# - update_trade_mfe_mae(trade_id, current_price)

# ============================================================
# SECTION 7: Webhook Handler (~250 lines)
# ============================================================
# - /webhook/<token> endpoint
# - Signal parsing (BUY, SELL, CLOSE, TP_HIT, SL_HIT)
# - Trade/Position creation
# - TP/SL price calculation

# ============================================================
# SECTION 8: Price Event Handler (~150 lines)
# ============================================================
# - on_price_update(symbol, price)
#   1. Get positions for symbol from index
#   2. For each position:
#      - Calculate unrealized P&L
#      - Update worst_unrealized_pnl (drawdown)
#      - Check TP/SL
#      - Close if hit
#   3. Update MFE/MAE for open trades

# ============================================================
# SECTION 9: TradingView WebSocket (~200 lines)
# ============================================================
# - connect_tradingview_websocket()
# - subscribe_to_symbols()
# - process_price_message()
#   → Calls on_price_update() for each price

# ============================================================
# SECTION 10: Health & Status (~50 lines)
# ============================================================
# - /health endpoint
# - /status endpoint (stats, open positions count, etc.)

# ============================================================
# SECTION 11: Startup & Main (~60 lines)
# ============================================================
# - Initialize database tables
# - Rebuild position index from DB
# - Start TradingView WebSocket
# - Start Flask server on port 8083
```

---

## 📊 Key Design: Event-Driven Drawdown

### The Core Logic:

```python
def on_price_update(symbol: str, price: float):
    """
    Called on EVERY price tick from TradingView.
    This is where the magic happens - no polling needed.
    """
    # O(1) lookup - get positions for this symbol
    position_ids = _open_positions_by_symbol.get(symbol, [])
    
    for pos_id in position_ids:
        # Get position from DB (could cache for more speed)
        position = get_position(pos_id)
        if not position or position['status'] != 'open':
            continue
        
        # Calculate current unrealized P&L
        side = position['side']
        avg_entry = position['avg_entry_price']
        total_qty = position['total_quantity']
        tick_size = get_tick_size(position['ticker'])
        tick_value = get_tick_value(position['ticker'])
        
        if side == 'LONG':
            pnl_ticks = (price - avg_entry) / tick_size
        else:  # SHORT
            pnl_ticks = (avg_entry - price) / tick_size
        
        unrealized_pnl = pnl_ticks * tick_value * total_qty
        
        # UPDATE DRAWDOWN (this is the key fix!)
        current_worst = position['worst_unrealized_pnl'] or 0
        new_worst = min(current_worst, unrealized_pnl)  # Most negative
        
        if new_worst < current_worst:
            update_position_worst_pnl(pos_id, new_worst)
        
        # Check TP/SL
        check_and_close_if_hit(position, price)
```

### Why This Works at Scale:

```
100 users × 5 strategies × 2 open positions = 1,000 positions

With POLLING (current):
- Check ALL 1,000 positions every second
- 1,000 DB reads/sec minimum
- Misses fast trades

With EVENT-DRIVEN (new):
- Price arrives for MNQ
- Index lookup: O(1) → find 50 MNQ positions
- Update only those 50 positions
- 50 DB writes instead of 1,000 reads
- NEVER misses a tick
```

---

## 📁 Files Changed

### NEW Files:

| File | Purpose |
|------|---------|
| `recorder_service.py` | New recording engine (~1,200 lines) |
| `start_services.sh` | Script to start both services |
| `RECORDER_SERVICE_DOCS.md` | Documentation |

### MODIFIED Files:

| File | Changes |
|------|---------|
| `ultra_simple_server.py` | Remove ~1,500 lines of recorder code |
| `START_HERE.md` | Add recorder service documentation |
| `.cursorrules` | Add recorder service rules |

### UNCHANGED Files:

| File | Reason |
|------|--------|
| `templates/*.html` | No changes needed |
| `just_trades.db` | Schema stays same |

---

## 🔄 Migration Strategy

### Phase 1: Create Recorder Service (No Breaking Changes)

1. Create `recorder_service.py` with all recorder logic
2. Test webhook endpoint on port 8083
3. Test drawdown tracking
4. Both servers run simultaneously
5. **Main server still works as before**

### Phase 2: Cutover Webhooks

1. Update TradingView alerts to use port 8083 webhook
2. Or: Add proxy in main server to forward to recorder
3. Verify trades recording correctly
4. Verify drawdown tracking

### Phase 3: Remove Duplicate Code

1. Remove recorder code from `ultra_simple_server.py`
2. Main server becomes ~5,000 lines (cleaner!)
3. Update documentation

### Phase 4: Production Hardening

1. Add health checks
2. Add auto-restart on failure
3. Add logging/monitoring

---

## 🔗 Webhook URL Changes

### Current:
```
https://your-domain.ngrok-free.dev/webhook/<token>
(Port 8082 - main server)
```

### New (Two Options):

**Option A: Direct to Recorder Service**
```
https://your-domain.ngrok-free.dev:8083/webhook/<token>
(Requires ngrok config for second port)
```

**Option B: Proxy Through Main Server (Recommended)**
```
# Main server proxies to recorder service
@app.route('/webhook/<token>', methods=['POST'])
def webhook_proxy(token):
    # Forward to recorder service
    return requests.post(f'http://localhost:8083/webhook/{token}', 
                        json=request.get_json()).json()
```

**I recommend Option B** - no TradingView changes needed.

---

## 🗄️ Database Access

### Shared SQLite Strategy:

```python
# recorder_service.py
def get_db_connection():
    """Get database connection with WAL mode for concurrent access"""
    conn = sqlite3.connect('just_trades.db', timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')  # Better concurrency
    conn.execute('PRAGMA busy_timeout=30000')  # Wait up to 30s
    conn.row_factory = sqlite3.Row
    return conn
```

### Access Pattern:

| Service | Tables | Access |
|---------|--------|--------|
| Main Server | All tables | Read/Write |
| Recorder Service | recorders, recorded_*, recorder_positions | Read/Write |
| Dashboard | recorder_positions, recorded_trades | Read only |

---

## ✅ Implementation Checklist

### Phase 1: Create Service (I'll do this first)
- [ ] Create `recorder_service.py` skeleton
- [ ] Add database helpers
- [ ] Add price utilities (copy from main server)
- [ ] Add position index
- [ ] Add position management functions
- [ ] Add trade management functions
- [ ] Add webhook endpoint
- [ ] Add price event handler (KEY - this fixes drawdown)
- [ ] Add TradingView WebSocket
- [ ] Add health endpoint
- [ ] Test independently

### Phase 2: Integration
- [ ] Add webhook proxy to main server
- [ ] Test end-to-end webhook flow
- [ ] Test drawdown tracking
- [ ] Compare with Trade Manager values

### Phase 3: Cleanup
- [ ] Remove duplicate code from main server
- [ ] Update START_HERE.md
- [ ] Update .cursorrules
- [ ] Create handoff document

---

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Database locks | WAL mode, busy_timeout, retry logic |
| Service not running | Health checks, auto-restart script |
| Webhook downtime | Proxy approach = instant cutover |
| Breaking main server | Phase 1 adds only, no removals |

---

## 🚀 Ready to Proceed?

**I need your approval before writing any code.**

The plan:
1. ✅ Create `recorder_service.py` (NEW file - safe)
2. ✅ Test it works independently
3. ⚠️ Only THEN modify `ultra_simple_server.py` (with your permission)

**Do you approve this plan?**

If yes, I'll start with creating `recorder_service.py`.

---

## 📝 Approval

- [ ] User approves the architecture
- [ ] User approves creating `recorder_service.py`
- [ ] User understands webhook proxy approach
- [ ] User is ready to proceed

**Reply "yes" or "approved" to begin implementation.**
