# Test Signal-Based Tracking (Trade Manager Style)
**Date:** December 29, 2025
**Goal:** Test if signal-based tracking works without broker sync

---

## 🎯 TEST PLAN

### What We're Testing:
1. ✅ Positions track from signals (not broker API)
2. ✅ Multiple signals create correct positions (DCA works)
3. ✅ CLOSE signals reset positions
4. ✅ P&L calculates from market data (TradingView API)
5. ✅ No broker API calls needed for position tracking

---

## 📋 STEP-BY-STEP TEST

### Step 1: Disable Broker Sync (Temporary for Testing)

**File:** `recorder_service.py`  
**Line:** ~5373-5382

**Comment out the broker sync:**
```python
# TEMPORARY: Disabled for signal-based tracking test
# if ticker:
#     try:
#         sync_result = sync_position_with_broker(recorder_id, ticker)
#         ...
```

**Or add a flag:**
```python
# Signal-based tracking test mode
SIGNAL_BASED_TESTING = True

if ticker and not SIGNAL_BASED_TESTING:
    try:
        sync_result = sync_position_with_broker(recorder_id, ticker)
        ...
```

---

### Step 2: Send Test Webhooks

**Test 1: Single BUY Signal**
```bash
curl -X POST http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN \
  -H "Content-Type: application/json" \
  -d '{
    "recorder": "TEST_RECORDER",
    "action": "buy",
    "ticker": "MNQ1!",
    "price": "25600"
  }'
```

**Expected Result:**
- Position created: +1 MNQ @ 25600
- No broker API call for position
- Position tracked in database

**Check Database:**
```sql
SELECT * FROM recorder_positions WHERE recorder_id = ? AND status = 'open';
-- Should show: +1 MNQ @ 25600
```

---

**Test 2: DCA (Multiple BUY Signals)**
```bash
# Signal 1
curl -X POST http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "TEST_RECORDER", "action": "buy", "ticker": "MNQ1!", "price": "25600"}'

# Signal 2 (DCA)
curl -X POST http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "TEST_RECORDER", "action": "buy", "ticker": "MNQ1!", "price": "25610"}'
```

**Expected Result:**
- Position updated: +2 MNQ @ 25605 avg (weighted average)
- No broker API call
- Both signals recorded

**Check Database:**
```sql
SELECT total_quantity, avg_entry_price FROM recorder_positions 
WHERE recorder_id = ? AND ticker = 'MNQ1!' AND status = 'open';
-- Should show: total_quantity = 2, avg_entry_price = 25605
```

---

**Test 3: CLOSE Signal**
```bash
curl -X POST http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN \
  -H "Content-Type: application/json" \
  -d '{
    "recorder": "TEST_RECORDER",
    "action": "close",
    "ticker": "MNQ1!",
    "price": "25620"
  }'
```

**Expected Result:**
- Position closed: 0 MNQ
- Exit price: 25620
- P&L calculated: (25620 - 25605) × 2 × $2 = $60

**Check Database:**
```sql
SELECT status, exit_price, realized_pnl FROM recorder_positions 
WHERE recorder_id = ? AND ticker = 'MNQ1!';
-- Should show: status = 'closed', exit_price = 25620, realized_pnl = 60
```

---

**Test 4: SELL Signal (Partial Exit)**
```bash
# First, create position
curl -X POST http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "TEST_RECORDER", "action": "buy", "ticker": "MNQ1!", "price": "25600"}'

curl -X POST http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "TEST_RECORDER", "action": "buy", "ticker": "MNQ1!", "price": "25610"}'
# Now have: +2 MNQ @ 25605

# Partial exit
curl -X POST http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "TEST_RECORDER", "action": "sell", "ticker": "MNQ1!", "price": "25620"}'
```

**Expected Result:**
- Position reduced: +1 MNQ @ 25605 (from +2)
- Partial exit recorded
- No broker API call

---

### Step 3: Verify No Broker API Calls

**Check Server Logs:**
```bash
# Look for broker API calls
grep -i "get_positions\|sync_position\|broker.*position" server.log

# Should see NO calls to broker position API during signal processing
```

**Expected:**
- ✅ Webhook received
- ✅ Signal recorded
- ✅ Position updated from signal
- ❌ NO "Syncing with broker" messages
- ❌ NO "get_positions" API calls

---

### Step 4: Test P&L Calculation

**After creating a position, check if P&L updates:**

**Check Database:**
```sql
SELECT 
  ticker,
  total_quantity,
  avg_entry_price,
  current_price,
  unrealized_pnl,
  worst_unrealized_pnl
FROM recorder_positions 
WHERE recorder_id = ? AND status = 'open';
```

**Expected:**
- `current_price` should update (from TradingView API)
- `unrealized_pnl` should calculate: (current_price - avg_entry_price) × quantity × multiplier
- `worst_unrealized_pnl` should track worst P&L

**Check if background thread is running:**
```bash
# Check server logs for P&L updates
grep -i "drawdown\|pnl\|current_price" server.log | tail -20
```

**Expected:**
- ✅ "Position drawdown update" messages every second
- ✅ Current price from TradingView API
- ✅ P&L calculated and updated

---

## 🧪 QUICK TEST SCRIPT

Create a test script to automate testing:

```python
# test_signal_tracking.py
import requests
import time
import json

WEBHOOK_URL = "http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN"
RECORDER_NAME = "TEST_RECORDER"

def send_webhook(action, ticker, price):
    """Send test webhook"""
    data = {
        "recorder": RECORDER_NAME,
        "action": action,
        "ticker": ticker,
        "price": str(price)
    }
    response = requests.post(WEBHOOK_URL, json=data)
    print(f"✅ {action} {ticker} @ {price}: {response.status_code}")
    return response.json()

def test_signal_tracking():
    """Test signal-based tracking"""
    print("🧪 Testing Signal-Based Tracking\n")
    
    # Test 1: Single BUY
    print("Test 1: Single BUY Signal")
    send_webhook("buy", "MNQ1!", 25600)
    time.sleep(1)
    
    # Test 2: DCA
    print("\nTest 2: DCA (Multiple BUY)")
    send_webhook("buy", "MNQ1!", 25610)
    time.sleep(1)
    
    # Test 3: Check position
    print("\nTest 3: Check Position")
    # Query database to verify position
    
    # Test 4: CLOSE
    print("\nTest 4: CLOSE Signal")
    send_webhook("close", "MNQ1!", 25620)
    time.sleep(1)
    
    print("\n✅ Test Complete!")

if __name__ == "__main__":
    test_signal_tracking()
```

---

## ✅ VERIFICATION CHECKLIST

After testing, verify:

- [ ] Positions created from signals (not broker API)
- [ ] DCA works (multiple BUY signals combine)
- [ ] CLOSE resets position to 0
- [ ] SELL reduces position (partial exit)
- [ ] No broker API calls for position tracking
- [ ] P&L calculates from TradingView API
- [ ] Background thread updates P&L every second
- [ ] Positions persist in database
- [ ] Signals recorded in `recorded_signals` table

---

## 🔍 WHAT TO LOOK FOR

### ✅ Success Indicators:

1. **Server Logs:**
   ```
   📨 Webhook received for recorder 'TEST_RECORDER'
   📊 Signal-Based New Position: LONG MNQ1! x1 @ 25600
   📈 Signal-Based Position DCA: LONG MNQ1! +1 @ 25610 | Total: 2 @ avg 25605.00
   ```

2. **Database:**
   ```sql
   -- Position exists
   SELECT * FROM recorder_positions WHERE recorder_id = ?;
   
   -- Signals recorded
   SELECT * FROM recorded_signals WHERE recorder_id = ?;
   ```

3. **No Broker API Calls:**
   ```
   ❌ NO "Syncing with broker" messages
   ❌ NO "get_positions" API calls
   ❌ NO broker position sync
   ```

---

## 🚨 TROUBLESHOOTING

### Issue: Position not created
**Check:**
- Webhook token is correct
- Recorder exists and is enabled
- Signal is being recorded in `recorded_signals` table

### Issue: P&L not updating
**Check:**
- TradingView API is working (`get_price_from_tradingview_api()`)
- Background thread is running (`poll_position_drawdown()`)
- Market data cache is being updated

### Issue: Broker sync still happening
**Check:**
- Broker sync code is commented out
- No other code paths calling `sync_position_with_broker()`

---

## 📊 EXPECTED RESULTS

### Before (Broker-Based):
```
Signal → Place order → Poll broker API → Update position
❌ Can fail if broker API is down
❌ Can miss signals if broker API is delayed
```

### After (Signal-Based):
```
Signal → Record signal → Update position from signal
✅ Never fails (doesn't need broker API)
✅ Never misses signals (tracks every webhook)
```

---

## 🎯 NEXT STEPS

1. **Run tests** using the script above
2. **Verify results** match expected behavior
3. **If successful:** Keep signal-based tracking
4. **If issues:** Debug and fix

---

**This test will prove signal-based tracking works exactly like Trade Manager!**
