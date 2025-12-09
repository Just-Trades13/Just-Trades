# Trading Engine Handoff - December 8, 2025

## Summary of Session Work

This session focused on fixing critical bugs in the webhook-based trading system that executes trades on Tradovate broker via TradingView signals.

---

## CRITICAL BUGS FIXED

### 1. ✅ FIXED: SHORT Position Close Sending Wrong Action
**File:** `recorder_service.py` (line ~1304)

**Problem:** When a SHORT position hit Take Profit, the system was supposed to BUY to close, but was sending SELL instead, which ADDED to the short position.

**Root Cause:** 
```python
# OLD (BROKEN):
execute_live_trade_with_bracket(
    action='CLOSE',  # <-- This became 'Sell' because 'CLOSE' != 'BUY'
    ...
)

# The execution function had:
order_action = 'Buy' if action == 'BUY' else 'Sell'
# So 'CLOSE' evaluated to 'Sell' - WRONG!
```

**Fix Applied:**
```python
# NEW (FIXED):
close_action = 'SELL' if side == 'LONG' else 'BUY'
execute_live_trade_with_bracket(
    action=close_action,  # Pass actual action, not 'CLOSE'
    ...
)
```

**Impact:** This bug caused -3 short position to become -4 (added instead of closed), resulting in a $3 loss when the next BUY signal had to buy through all the contracts.

---

### 2. ✅ FIXED: Trades Recording When Broker Rejects
**File:** `recorder_service.py` (lines ~3048-3090, ~3213-3255)

**Problem:** When the broker rejected an order (returned error `{}`), the system still recorded the trade in the database, causing DB/broker position mismatch.

**Symptoms:**
- DB showed: SHORT 3 contracts
- Broker showed: 0 contracts
- Logs showed: `Failed to place order: {}` but trade was still recorded

**Root Cause:** The code had fallback logic that recorded trades using "webhook price" even when broker rejected:
```python
# OLD (BROKEN):
if broker_result.get('success') and broker_result.get('fill_price'):
    # Record with broker data
else:
    fill_price = current_price  # <-- Still recorded even on rejection!
    # ... inserted trade anyway
```

**Fix Applied:**
```python
# NEW (FIXED):
if broker_result.get('error'):
    logger.error(f"❌ REJECTED by broker: {broker_result['error']} - NOT recording trade")
    trade_result = {'action': 'rejected', 'error': broker_result['error']}
elif broker_result.get('success') and broker_result.get('fill_price'):
    # Only record if broker confirmed
    ...
else:
    # No broker linked - signal only
    logger.info(f"📝 No broker linked - recording signal only (no position)")
```

**Applied to:**
- New LONG trades (lines ~3048-3090)
- New SHORT trades (lines ~3213-3255)
- DCA LONG additions (lines ~3002-3010)
- DCA SHORT additions (lines ~3167-3175)

---

### 3. ✅ FIXED: Redundant Close Orders Flipping Position
**File:** `recorder_service.py` (line ~1298-1316)

**Problem:** When TP limit order filled on broker, the system detected TP hit via price polling and sent ANOTHER close order, which flipped the position to the opposite side.

**Fix Applied:** Added `check_broker_position_exists()` function that queries broker BEFORE sending close order:
```python
def check_broker_position_exists(recorder_id: int, ticker: str) -> bool:
    """Check if broker still has an open position for this symbol."""
    # Queries Tradovate API for actual position
    # Returns False if position is already flat
```

Then in TP/SL handler:
```python
broker_has_position = check_broker_position_exists(trade['recorder_id'], ticker)

if broker_has_position:
    # Send close order
else:
    logger.info(f"✅ Broker position already closed (TP limit filled) - skipping redundant close")
```

---

### 4. ✅ SIMPLIFIED: Trade Execution Logic
**File:** `recorder_service.py` - `execute_live_trade_with_bracket()` function

**Old Approach:** Complex bracket order logic with Tradovate's OCO strategies (which were failing with "Order strategy is disabled" errors)

**New Approach:** Simple and reliable:
1. **Entry:** Market order (fast fill)
2. **TP:** Place limit order immediately after entry fill
3. **DCA:** Cancel old TP, place new TP at updated level
4. **Polling:** Check every 1 second if TP hit

```python
def execute_live_trade_with_bracket(...):
    # STEP 1: Place market order
    order_result = await tradovate.place_order(order_data)
    
    # STEP 2: Get position to confirm fill price
    positions = await tradovate.get_positions(account_id=...)
    
    # STEP 3: Place TP limit order (if not closing)
    if tp_ticks and action != 'CLOSE' and fill_price:
        tp_order_data = {
            "orderType": "Limit",
            "price": tp_price,
            ...
        }
        await tradovate.place_order(tp_order_data)
```

---

## KEY FILES MODIFIED

| File | Changes |
|------|---------|
| `recorder_service.py` | Main trading engine - all fixes above |
| `ultra_simple_server.py` | Added proactive token refresh thread (user added) |

---

## CURRENT ARCHITECTURE

### Trade Flow:
```
TradingView Alert
    ↓
Webhook POST to /webhook/{token}
    ↓
recorder_service.py processes signal
    ↓
Check for existing position (DCA vs new trade)
    ↓
Execute on Tradovate via API
    ↓
ONLY record in DB if broker confirms fill
    ↓
Place TP limit order on broker
    ↓
TP/SL polling thread monitors every 1 second
    ↓
When TP hit: Check broker position first, then close
```

### Key Functions:
- `execute_live_trade_with_bracket()` - Main execution (market + TP limit)
- `update_exit_brackets()` - Cancel old TP, place new TP (for DCA)
- `check_broker_position_exists()` - Query broker before closing
- `check_tp_sl_for_symbol()` - TP/SL monitoring logic
- `convert_ticker_to_tradovate()` - Symbol conversion (MNQ1! → MNQZ5)

---

## KNOWN ISSUES / LIMITATIONS

### 1. Broker Rate Limiting (429 errors)
Tradovate sometimes returns 429 errors, especially on:
- `get_positions()` calls
- Rapid order placement

**Current handling:** Graceful failure, trade not recorded if broker rejects.

### 2. Empty Error Response `{}`
Broker sometimes returns empty error object. This is treated as rejection.

### 3. Token Expiration
Tokens expire and need refresh. User added proactive token refresh thread in `ultra_simple_server.py` that refreshes tokens expiring within 2 hours every 30 minutes.

---

## DATABASE SCHEMA (relevant tables)

### recorded_trades
```sql
- id, recorder_id, signal_id
- ticker, action, side (LONG/SHORT)
- entry_price, exit_price, quantity
- tp_price, sl_price
- status (open/closed)
- pnl, pnl_ticks, exit_reason
- broker_order_id, broker_strategy_id, broker_fill_price
- broker_managed_tp_sl (0 or 1)
```

### recorder_positions
```sql
- id, recorder_id, ticker, side
- total_quantity, avg_entry_price
- status (open/closed)
```

---

## TESTING CHECKLIST

Before deploying, verify:

- [ ] LONG entry → Market order fills → TP limit placed → TP hits → Position closes (SELL)
- [ ] SHORT entry → Market order fills → TP limit placed → TP hits → Position closes (BUY)
- [ ] DCA LONG → Adds to position → Old TP cancelled → New TP at updated avg price
- [ ] DCA SHORT → Adds to position → Old TP cancelled → New TP at updated avg price
- [ ] Broker rejects order → Trade NOT recorded in DB
- [ ] TP limit fills on broker → No redundant close order sent
- [ ] DB and broker positions match after each trade

---

## QUICK COMMANDS

```bash
# Restart trading engine
pkill -f "python.*recorder_service" && python3 recorder_service.py > /tmp/trading_engine.log 2>&1 &

# Check logs
tail -f /tmp/trading_engine.log

# Check for errors
grep -E "(ERROR|REJECTED|Failed)" /tmp/trading_engine.log | tail -20

# Check DB open trades
sqlite3 just_trades.db "SELECT * FROM recorded_trades WHERE status='open';"

# Check DB open positions
sqlite3 just_trades.db "SELECT * FROM recorder_positions WHERE status='open';"

# Clean up mismatched state
sqlite3 just_trades.db "UPDATE recorded_trades SET status='closed', exit_price=entry_price, pnl=0 WHERE status='open';"
sqlite3 just_trades.db "DELETE FROM recorder_positions WHERE status='open';"
```

---

## NEXT STEPS / FUTURE IMPROVEMENTS

1. **Tradovate WebSocket for Real-Time Updates**
   - Instead of polling every 1 second, subscribe to Tradovate's user data WebSocket
   - Get instant notifications when orders fill or positions change

2. **Better Error Handling for Rate Limits**
   - Implement exponential backoff on 429 errors
   - Queue and retry failed orders

3. **Position Sync on Startup**
   - On service start, query broker for actual positions
   - Reconcile with DB and fix any mismatches

4. **Audit Trail**
   - Log every broker API call and response
   - Store in separate audit table for debugging

---

## FILES TO BACKUP

Before making more changes, backup these working files:
```bash
cp recorder_service.py backups/WORKING_STATE_DEC8_2025/
cp ultra_simple_server.py backups/WORKING_STATE_DEC8_2025/
cp just_trades.db backups/WORKING_STATE_DEC8_2025/
```

---

*Last updated: December 8, 2025*
*Session focus: Bug fixes for SHORT close action, broker rejection handling, redundant close prevention*
