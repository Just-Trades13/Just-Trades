# Test Signal-Based Tracking Accuracy (Before Making Changes)
**Date:** December 29, 2025
**Goal:** Verify signal-based tracking is accurate WITHOUT making permanent changes

---

## 🎯 TESTING STRATEGY

**We'll test signal-based tracking in a way that:**
1. ✅ Doesn't break existing functionality
2. ✅ Can be easily reverted
3. ✅ Compares signal-based vs broker-based positions
4. ✅ Verifies accuracy

---

## 🔧 METHOD 1: Environment Variable (Safest)

### Step 1: Add Environment Variable Check

**File:** `recorder_service.py`  
**Line:** ~5373

**Add this check (doesn't change existing code):**
```python
# TEST MODE: Check environment variable
import os
SIGNAL_BASED_TEST_MODE = os.getenv('SIGNAL_BASED_TEST', 'false').lower() == 'true'

# Existing code stays the same, just add check:
if ticker and not SIGNAL_BASED_TEST_MODE:
    try:
        sync_result = sync_position_with_broker(recorder_id, ticker)
        ...
```

**This way:**
- ✅ Default behavior unchanged (broker sync still works)
- ✅ Only enabled when you set environment variable
- ✅ Easy to disable (just remove env var)

---

### Step 2: Run Server with Test Mode

```bash
# Enable test mode
export SIGNAL_BASED_TEST=true

# Start server
python3 recorder_service.py

# Or in one line:
SIGNAL_BASED_TEST=true python3 recorder_service.py
```

**To disable:**
```bash
unset SIGNAL_BASED_TEST
# Or just restart without the env var
```

---

## 🔧 METHOD 2: Database Flag (More Permanent)

### Step 1: Add Test Flag to Database

**Add a test flag to recorders table:**
```sql
ALTER TABLE recorders ADD COLUMN test_signal_based INTEGER DEFAULT 0;
```

**Enable for specific recorder:**
```sql
UPDATE recorders SET test_signal_based = 1 WHERE name = 'TEST_RECORDER';
```

**Check in code:**
```python
# Line ~5360
recorder = dict(recorder)
test_mode = recorder.get('test_signal_based', 0) == 1

if ticker and not test_mode:
    try:
        sync_result = sync_position_with_broker(recorder_id, ticker)
```

---

## 🧪 TEST PLAN: Compare Signal vs Broker

### Test 1: Send Signals and Compare

**Step 1: Send test signals**
```bash
# Signal 1: BUY
curl -X POST http://localhost:5000/webhook/YOUR_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "TEST_RECORDER", "action": "buy", "ticker": "MNQ1!", "price": "25600"}'

# Signal 2: BUY (DCA)
curl -X POST http://localhost:5000/webhook/YOUR_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "TEST_RECORDER", "action": "buy", "ticker": "MNQ1!", "price": "25610"}'
```

**Step 2: Check signal-based position**
```sql
SELECT 
    ticker,
    side,
    total_quantity,
    avg_entry_price,
    status
FROM recorder_positions 
WHERE recorder_id = (SELECT id FROM recorders WHERE name = 'TEST_RECORDER')
AND status = 'open';
```

**Expected:** +2 MNQ @ 25605 avg

**Step 3: Check broker position (if available)**
```python
# Manual check via API or Tradovate website
# Compare: Does broker show same position?
```

**Step 4: Compare**
- ✅ Signal-based: +2 MNQ @ 25605
- ✅ Broker: +2 MNQ @ 25605 (should match if orders filled correctly)

---

### Test 2: Verify P&L Accuracy

**Step 1: Get current price from TradingView**
```python
# Check if TradingView API is working
from recorder_service import get_price_from_tradingview_api
price = get_price_from_tradingview_api("MNQ1!")
print(f"Current price: {price}")
```

**Step 2: Calculate expected P&L**
```python
entry_price = 25605
current_price = 25650  # Example
quantity = 2
multiplier = 2  # $2 per point for MNQ

expected_pnl = (current_price - entry_price) * quantity * multiplier
# = (25650 - 25605) * 2 * 2 = $180
```

**Step 3: Check database P&L**
```sql
SELECT 
    unrealized_pnl,
    current_price,
    avg_entry_price,
    total_quantity
FROM recorder_positions 
WHERE recorder_id = (SELECT id FROM recorders WHERE name = 'TEST_RECORDER')
AND status = 'open';
```

**Step 4: Compare**
- ✅ Database P&L should match calculated P&L
- ✅ Current price should update (from TradingView API)

---

### Test 3: Test CLOSE Signal Accuracy

**Step 1: Send CLOSE signal**
```bash
curl -X POST http://localhost:5000/webhook/YOUR_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "TEST_RECORDER", "action": "close", "ticker": "MNQ1!", "price": "25620"}'
```

**Step 2: Check closed position**
```sql
SELECT 
    status,
    exit_price,
    realized_pnl,
    total_quantity,
    avg_entry_price
FROM recorder_positions 
WHERE recorder_id = (SELECT id FROM recorders WHERE name = 'TEST_RECORDER')
AND ticker = 'MNQ1!'
ORDER BY closed_at DESC
LIMIT 1;
```

**Step 3: Verify P&L calculation**
```python
# Expected P&L:
entry = 25605
exit = 25620
quantity = 2
multiplier = 2

realized_pnl = (exit - entry) * quantity * multiplier
# = (25620 - 25605) * 2 * 2 = $60
```

**Expected:**
- ✅ Status = 'closed'
- ✅ Exit price = 25620
- ✅ Realized P&L = $60

---

## 📊 ACCURACY VERIFICATION CHECKLIST

### Position Tracking Accuracy:
- [ ] Signal-based position matches broker position (if orders filled)
- [ ] DCA calculates correct weighted average
- [ ] CLOSE resets position correctly
- [ ] Partial exits reduce position correctly

### P&L Calculation Accuracy:
- [ ] Current price updates from TradingView API
- [ ] Unrealized P&L matches manual calculation
- [ ] Realized P&L matches manual calculation
- [ ] Drawdown (worst_unrealized_pnl) tracks correctly

### Signal Recording Accuracy:
- [ ] All signals recorded in `recorded_signals` table
- [ ] Signal timestamps are correct
- [ ] Signal prices match webhook prices

---

## 🔍 COMPARISON TEST: Signal vs Broker

### Create Test Script

```python
# compare_signal_vs_broker.py
import sqlite3
from phantom_scraper.tradovate_integration import TradovateIntegration
import asyncio

async def compare_positions(recorder_name):
    """Compare signal-based position vs broker position"""
    
    # Get signal-based position
    conn = sqlite3.connect('just_trades.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT r.id, r.name, t.subaccount_id, t.is_demo, a.tradovate_token
        FROM recorders r
        JOIN traders t ON r.trader_id = t.id
        JOIN accounts a ON t.account_id = a.id
        WHERE r.name = ?
    ''', (recorder_name,))
    
    recorder = cursor.fetchone()
    if not recorder:
        print(f"❌ Recorder '{recorder_name}' not found")
        return
    
    recorder_id = recorder[0]
    subaccount_id = recorder[2]
    is_demo = recorder[3]
    token = recorder[4]
    
    # Get signal-based position
    cursor.execute('''
        SELECT ticker, side, total_quantity, avg_entry_price
        FROM recorder_positions
        WHERE recorder_id = ? AND status = 'open'
    ''', (recorder_id,))
    
    signal_positions = cursor.fetchall()
    print(f"\n📊 Signal-Based Positions (from signals):")
    for pos in signal_positions:
        print(f"  {pos[0]}: {pos[1]} {pos[2]} @ {pos[3]}")
    
    # Get broker position
    async with TradovateIntegration(demo=is_demo) as tradovate:
        tradovate.access_token = token
        broker_positions = await tradovate.get_positions(account_id=subaccount_id)
        
        print(f"\n🏦 Broker Positions (from Tradovate API):")
        if broker_positions:
            for pos in broker_positions:
                symbol = pos.get('symbol', '')
                net_pos = pos.get('netPos', 0)
                net_price = pos.get('netPrice', 0)
                side = 'LONG' if net_pos > 0 else 'SHORT'
                print(f"  {symbol}: {side} {abs(net_pos)} @ {net_price}")
        else:
            print("  No open positions")
    
    # Compare
    print(f"\n🔍 Comparison:")
    # Add comparison logic here
    
    conn.close()

# Run
asyncio.run(compare_positions('TEST_RECORDER'))
```

---

## ✅ SUCCESS CRITERIA

### Test is successful if:

1. **Position Tracking:**
   - ✅ Signal-based positions match broker positions (when orders fill)
   - ✅ DCA calculates correct weighted average
   - ✅ CLOSE resets position correctly

2. **P&L Calculation:**
   - ✅ Current price updates from TradingView API
   - ✅ P&L matches manual calculation
   - ✅ Drawdown tracks correctly

3. **Reliability:**
   - ✅ Works even if broker API is down
   - ✅ Never misses signals
   - ✅ No disconnects

---

## 🚨 IF TEST FAILS

**If signal-based tracking is inaccurate:**

1. **Check signal recording:**
   - Are signals being recorded correctly?
   - Do signal prices match webhook prices?

2. **Check position calculation:**
   - Is weighted average correct for DCA?
   - Is position quantity correct?

3. **Check P&L calculation:**
   - Is TradingView API returning correct prices?
   - Is multiplier correct for each symbol?

4. **Check broker comparison:**
   - Do broker positions match signal positions?
   - Are orders filling correctly?

---

## 📋 TEST RESULTS TEMPLATE

```
TEST RESULTS - Signal-Based Tracking

Date: ___________
Recorder: ___________

Position Tracking:
[ ] Signal-based position matches broker
[ ] DCA calculates correctly
[ ] CLOSE resets correctly
[ ] Partial exits work correctly

P&L Calculation:
[ ] Current price updates
[ ] Unrealized P&L accurate
[ ] Realized P&L accurate
[ ] Drawdown tracks correctly

Reliability:
[ ] Works without broker API
[ ] No missed signals
[ ] No disconnects

Overall: [ ] PASS [ ] FAIL

Notes:
_________________________________
_________________________________
```

---

## 🎯 NEXT STEPS

**If test passes:**
- ✅ Signal-based tracking is accurate
- ✅ Safe to implement permanently
- ✅ Proceed with full implementation

**If test fails:**
- ❌ Identify specific issues
- ❌ Fix accuracy problems
- ❌ Re-test before implementing

---

**This test will prove if signal-based tracking is accurate enough to use!**
