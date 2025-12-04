# 🎯 IMPLEMENTATION PLAN: Recorder Drawdown Tracking (Trade Manager Style)

**Created:** December 4, 2025  
**Priority:** HIGH  
**Status:** READY FOR IMPLEMENTATION  
**Estimated Effort:** Medium (4-6 hours)

---

## 📋 Problem Statement

### Current Behavior (BROKEN)
- Each TradingView webhook signal creates a **separate trade record**
- Drawdown shows **$0.00 for ALL trades** 
- No connection to actual Tradovate position data
- MFE/MAE tracking runs every 5 seconds - misses fast trades (2-4 sec)

### Desired Behavior (Trade Manager Style)
- DCA entries combine into **ONE position record** with weighted average entry
- Drawdown shows **actual worst unrealized P&L** during the trade
- Real-time tracking via Tradovate position polling
- Position SIZE shows total contracts (e.g., 4 instead of 4 separate trades of 1)

### Evidence (Screenshots Dec 4, 2025)

**Trade Manager:**
| Status | Size | Entry | Drawdown |
|--------|------|-------|----------|
| OPEN | **4** | 25620.13 (avg) | **-21.00** |
| WIN | 1 | 25616.50 | **-1.50** |

**Just.Trades (Current - WRONG):**
| Status | Size | Entry | Drawdown |
|--------|------|-------|----------|
| WIN | 1 | 25620.50 | **$0.00** |
| WIN | 1 | 25616.50 | **$0.00** |
| WIN | 1 | 25617.75 | **$0.00** |

---

## 🏗️ Architecture Change Required

### Current Architecture
```
TradingView Signal → Webhook → Create NEW trade record → Poll price (5 sec) → Check TP/SL
                                    ↓
                         Each signal = separate trade
                         No real position tracking
```

### New Architecture (Trade Manager Style)
```
TradingView Signal → Webhook → Update POSITION record → Track in background
                                    ↓
Tradovate API Poll (1-2 sec) → Get actual position → Update drawdown → Store worst P&L
                                    ↓
                         One position = all DCA entries combined
                         Real-time unrealized P&L tracking
```

---

## 📊 Database Schema Changes

### Option A: Modify `recorded_trades` table (RECOMMENDED)
Add columns to track position-style data:

```sql
-- Add to recorded_trades table:
ALTER TABLE recorded_trades ADD COLUMN is_position BOOLEAN DEFAULT 0;
ALTER TABLE recorded_trades ADD COLUMN avg_entry_price REAL;
ALTER TABLE recorded_trades ADD COLUMN total_quantity INTEGER DEFAULT 1;
ALTER TABLE recorded_trades ADD COLUMN worst_unrealized_pnl REAL DEFAULT 0;
ALTER TABLE recorded_trades ADD COLUMN best_unrealized_pnl REAL DEFAULT 0;
ALTER TABLE recorded_trades ADD COLUMN last_price REAL;
ALTER TABLE recorded_trades ADD COLUMN tradovate_position_id TEXT;
```

### Option B: Create new `recorder_positions` table
```sql
CREATE TABLE recorder_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'LONG' or 'SHORT'
    
    -- Position tracking
    total_quantity INTEGER DEFAULT 0,
    avg_entry_price REAL,
    
    -- Entries (stored as JSON array)
    entries TEXT,  -- [{"price": 25620.50, "qty": 1, "time": "..."}, ...]
    
    -- Real-time tracking
    current_price REAL,
    unrealized_pnl REAL DEFAULT 0,
    worst_unrealized_pnl REAL DEFAULT 0,  -- MAX ADVERSE (drawdown)
    best_unrealized_pnl REAL DEFAULT 0,   -- MAX FAVORABLE
    
    -- Exit
    exit_price REAL,
    exit_time DATETIME,
    realized_pnl REAL,
    
    -- Status
    status TEXT DEFAULT 'open',  -- 'open', 'closed'
    
    -- Timestamps
    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (recorder_id) REFERENCES recorders(id)
);
```

**RECOMMENDATION:** Use Option B (new table) to avoid breaking existing functionality.

---

## 🔧 Code Changes Required

### File: `ultra_simple_server.py`

#### 1. Create Position Table (Run Once)
Location: In `init_db()` function around line ~850

```python
# Add after recorded_trades table creation
cursor.execute('''
    CREATE TABLE IF NOT EXISTS recorder_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recorder_id INTEGER NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        total_quantity INTEGER DEFAULT 0,
        avg_entry_price REAL,
        entries TEXT,
        current_price REAL,
        unrealized_pnl REAL DEFAULT 0,
        worst_unrealized_pnl REAL DEFAULT 0,
        best_unrealized_pnl REAL DEFAULT 0,
        exit_price REAL,
        realized_pnl REAL,
        status TEXT DEFAULT 'open',
        opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        closed_at DATETIME,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (recorder_id) REFERENCES recorders(id)
    )
''')
```

#### 2. Modify Webhook Handler
Location: `/webhook/<token>` route around line ~4200

**Current behavior:** Creates new `recorded_trades` entry for each signal

**New behavior:**
```python
# When BUY/SELL signal received:
# 1. Check if position already open for this recorder+symbol+side
# 2. If YES: Add to position (update avg entry, increase qty)
# 3. If NO: Create new position record
# 4. If OPPOSITE side signal: Close position, open new one

def handle_webhook_signal(recorder_id, action, symbol, price, quantity=1):
    conn = sqlite3.connect('just_trades.db')
    cursor = conn.cursor()
    
    side = 'LONG' if action.lower() == 'buy' else 'SHORT'
    
    # Check for existing open position
    cursor.execute('''
        SELECT id, total_quantity, avg_entry_price, entries, side
        FROM recorder_positions
        WHERE recorder_id = ? AND symbol = ? AND status = 'open'
    ''', (recorder_id, symbol))
    
    existing = cursor.fetchone()
    
    if existing:
        pos_id, total_qty, avg_entry, entries_json, pos_side = existing
        entries = json.loads(entries_json) if entries_json else []
        
        if pos_side == side:
            # SAME SIDE: Add to position (DCA)
            new_qty = total_qty + quantity
            new_avg = ((avg_entry * total_qty) + (price * quantity)) / new_qty
            entries.append({'price': price, 'qty': quantity, 'time': datetime.now().isoformat()})
            
            cursor.execute('''
                UPDATE recorder_positions
                SET total_quantity = ?, avg_entry_price = ?, entries = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_qty, new_avg, json.dumps(entries), pos_id))
        else:
            # OPPOSITE SIDE: Close position
            close_position(cursor, pos_id, price)
            # Optionally open new position in opposite direction
    else:
        # NO POSITION: Create new
        entries = [{'price': price, 'qty': quantity, 'time': datetime.now().isoformat()}]
        cursor.execute('''
            INSERT INTO recorder_positions (recorder_id, symbol, side, total_quantity, avg_entry_price, entries)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (recorder_id, symbol, side, quantity, price, json.dumps(entries)))
    
    conn.commit()
    conn.close()
```

#### 3. Add Position Polling Thread
Location: After `check_recorder_trades_tp_sl()` function around line ~5800

```python
def poll_recorder_positions():
    """
    Background thread that polls open positions and updates drawdown.
    Runs every 1-2 seconds for accurate tracking.
    """
    global _market_data_cache
    
    logger.info("🔄 Starting position drawdown tracker (every 1 second)")
    
    while True:
        try:
            conn = sqlite3.connect('just_trades.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all open positions
            cursor.execute('''
                SELECT p.*, r.name as recorder_name
                FROM recorder_positions p
                JOIN recorders r ON p.recorder_id = r.id
                WHERE p.status = 'open'
            ''')
            
            positions = [dict(row) for row in cursor.fetchall()]
            
            for pos in positions:
                symbol = pos['symbol']
                side = pos['side']
                avg_entry = pos['avg_entry_price']
                total_qty = pos['total_quantity']
                
                # Get current price from market data cache
                root = extract_symbol_root(symbol)
                current_price = None
                if root in _market_data_cache:
                    current_price = _market_data_cache[root].get('last')
                
                if not current_price:
                    continue
                
                # Calculate unrealized P&L
                tick_size = get_tick_size(symbol)
                tick_value = get_tick_value(symbol)
                
                if side == 'LONG':
                    pnl_ticks = (current_price - avg_entry) / tick_size
                else:  # SHORT
                    pnl_ticks = (avg_entry - current_price) / tick_size
                
                unrealized_pnl = pnl_ticks * tick_value * total_qty
                
                # Update worst/best unrealized P&L
                current_worst = pos['worst_unrealized_pnl'] or 0
                current_best = pos['best_unrealized_pnl'] or 0
                
                new_worst = min(current_worst, unrealized_pnl)  # Worst is most negative
                new_best = max(current_best, unrealized_pnl)    # Best is most positive
                
                # Update position
                cursor.execute('''
                    UPDATE recorder_positions
                    SET current_price = ?, 
                        unrealized_pnl = ?,
                        worst_unrealized_pnl = ?,
                        best_unrealized_pnl = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (current_price, unrealized_pnl, new_worst, new_best, pos['id']))
                
                conn.commit()
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Position polling error: {e}")
        
        time.sleep(1)  # Poll every 1 second

# Start position polling thread
position_poll_thread = threading.Thread(target=poll_recorder_positions, daemon=True)
position_poll_thread.start()
```

#### 4. Update Dashboard API
Location: `/api/dashboard/trade-history` around line ~3400

**Current:** Returns `recorded_trades` with `max_adverse` (always 0)

**New:** Return `recorder_positions` with `worst_unrealized_pnl` as drawdown

```python
@app.route('/api/dashboard/trade-history', methods=['GET'])
def api_dashboard_trade_history():
    # ... existing code ...
    
    # Add position-based trades
    cursor.execute('''
        SELECT p.*, r.name as strategy_name
        FROM recorder_positions p
        JOIN recorders r ON p.recorder_id = r.id
        WHERE p.status = 'closed'
        ORDER BY p.closed_at DESC
        LIMIT ?
    ''', (limit,))
    
    for pos in cursor.fetchall():
        trades.append({
            'open_time': pos['opened_at'],
            'closed_time': pos['closed_at'],
            'strategy': pos['strategy_name'],
            'symbol': pos['symbol'],
            'side': pos['side'],
            'size': pos['total_quantity'],
            'entry_price': pos['avg_entry_price'],
            'exit_price': pos['exit_price'],
            'profit': pos['realized_pnl'],
            'drawdown': abs(pos['worst_unrealized_pnl'])  # This is the key!
        })
```

#### 5. Position Close Logic
When opposite signal received OR exit signal:

```python
def close_position(cursor, position_id, exit_price):
    """Close a position and calculate final P&L"""
    cursor.execute('SELECT * FROM recorder_positions WHERE id = ?', (position_id,))
    pos = cursor.fetchone()
    
    if not pos:
        return
    
    avg_entry = pos['avg_entry_price']
    total_qty = pos['total_quantity']
    side = pos['side']
    
    tick_size = get_tick_size(pos['symbol'])
    tick_value = get_tick_value(pos['symbol'])
    
    if side == 'LONG':
        pnl_ticks = (exit_price - avg_entry) / tick_size
    else:
        pnl_ticks = (avg_entry - exit_price) / tick_size
    
    realized_pnl = pnl_ticks * tick_value * total_qty
    
    cursor.execute('''
        UPDATE recorder_positions
        SET status = 'closed',
            exit_price = ?,
            realized_pnl = ?,
            closed_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (exit_price, realized_pnl, position_id))
```

---

## 🧪 Testing Plan

### Test Case 1: Single Entry Position
1. Send BUY signal for MNQ @ 25600
2. Verify position created with qty=1, entry=25600
3. Price drops to 25598 (2 ticks down = -$1.00 drawdown)
4. Verify `worst_unrealized_pnl` = -1.00
5. Send SELL signal @ 25602
6. Verify position closed, drawdown preserved

### Test Case 2: DCA Position (Multiple Entries)
1. Send BUY @ 25600 (qty 1)
2. Send BUY @ 25598 (qty 1) - DCA
3. Verify: total_qty=2, avg_entry=25599
4. Price drops to 25594 (5 ticks from avg = -$2.50 drawdown)
5. Verify `worst_unrealized_pnl` = -2.50
6. Send BUY @ 25594 (qty 1) - More DCA
7. Verify: total_qty=3, avg_entry≈25597.33
8. Close position, verify drawdown preserved

### Test Case 3: SHORT Position
1. Send SELL signal for MNQ @ 25600
2. Verify SHORT position created
3. Price rises to 25602 (adverse for short)
4. Verify `worst_unrealized_pnl` is negative

---

## 📁 Files to Modify

| File | Changes | Risk |
|------|---------|------|
| `ultra_simple_server.py` | Add table, modify webhook, add polling thread, update API | MEDIUM |
| `templates/dashboard.html` | Update to show position-based trades | LOW |
| `templates/recorders_list.html` | No changes needed | NONE |

---

## ⚠️ Migration Considerations

### Existing Data
- Current `recorded_trades` table has 600+ trades
- These will NOT have proper drawdown (already closed)
- New positions going forward WILL have proper tracking
- **DO NOT DELETE existing data** - keep for historical reference

### Backward Compatibility
- Keep `recorded_trades` table working for existing code
- New `recorder_positions` table is additive
- Dashboard can show both (old trades + new positions)

---

## 🚀 Implementation Steps (For Next Chat Session)

### Step 1: Create Database Table
```bash
# Run this SQL or add to init_db()
sqlite3 just_trades.db "CREATE TABLE IF NOT EXISTS recorder_positions (...)"
```

### Step 2: Add Position Tracking to Webhook
- Modify `/webhook/<token>` handler
- Check for existing position before creating new trade
- Implement DCA logic (add to position instead of new record)

### Step 3: Add Position Polling Thread
- Create `poll_recorder_positions()` function
- Track `worst_unrealized_pnl` on every price tick
- Start thread on server startup

### Step 4: Update Dashboard API
- Modify `/api/dashboard/trade-history`
- Return positions with drawdown from `worst_unrealized_pnl`

### Step 5: Test
- Clear existing test data: `sqlite3 just_trades.db "DELETE FROM recorder_positions;"`
- Send test signals via webhook
- Verify drawdown tracking works

### Step 6: Backup & Commit
```bash
cp ultra_simple_server.py backups/WORKING_STATE_DEC4_2025_POSITION_TRACKING/
git add ultra_simple_server.py
git commit -m "Add position-based drawdown tracking (Trade Manager style)"
git tag WORKING_DEC4_2025_POSITION_TRACKING
```

---

## 📞 Quick Reference Commands

```bash
# Check current positions
sqlite3 just_trades.db "SELECT * FROM recorder_positions WHERE status='open';"

# Check closed positions with drawdown
sqlite3 just_trades.db "SELECT id, symbol, side, total_quantity, avg_entry_price, exit_price, realized_pnl, worst_unrealized_pnl FROM recorder_positions WHERE status='closed';"

# Restart server
pkill -f "python.*ultra_simple" && nohup python3 ultra_simple_server.py > /tmp/server.log 2>&1 &

# Check server logs
tail -100 /tmp/server.log | grep -iE "position|drawdown"
```

---

## ✅ Success Criteria

1. **DCA entries combine** into one position record
2. **Drawdown shows actual value** (not $0.00)
3. **Position size shows total** (e.g., 4 contracts, not 4 separate trades)
4. **Dashboard displays correctly** with proper drawdown column
5. **No regression** in existing functionality

---

## 🔗 Related Files

- `START_HERE.md` - Main documentation
- `HANDOFF_DEC4_2025_MFE_MAE.md` - Previous fix attempt
- `TRADE_MANAGER_ARCHITECTURE_DATABASE.md` - TM research
- `phantom_scraper/trade_manager_replica/services/position_recorder.py` - Reference implementation

---

*Created: Dec 4, 2025*
*Author: AI Assistant*
*For: Next chat session implementation*
