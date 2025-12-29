# Quick Test: Signal-Based Tracking
**Time:** 5 minutes
**Goal:** Verify signal-based tracking works without broker sync

---

## 🚀 QUICK START (3 Steps)

### Step 1: Temporarily Disable Broker Sync

**File:** `recorder_service.py`  
**Line:** ~5373

**Add this flag at the top of the file:**
```python
# TEST MODE: Signal-based tracking (disable broker sync)
SIGNAL_BASED_TEST_MODE = True  # Set to False to re-enable broker sync
```

**Then modify the sync code:**
```python
# Line ~5373
if ticker and not SIGNAL_BASED_TEST_MODE:  # ADD THIS CHECK
    try:
        sync_result = sync_position_with_broker(recorder_id, ticker)
        ...
```

---

### Step 2: Run Test Script

**Edit the test script:**
```bash
# Edit test_signal_tracking.py
# Change these lines:
WEBHOOK_URL = "http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN"  # Your actual token
RECORDER_NAME = "YOUR_RECORDER_NAME"  # Your actual recorder name
```

**Run the test:**
```bash
python3 test_signal_tracking.py
```

---

### Step 3: Verify Results

**Check database:**
```bash
sqlite3 just_trades.db
```

```sql
-- Check positions
SELECT id, recorder_id, ticker, side, total_quantity, avg_entry_price, status 
FROM recorder_positions 
WHERE recorder_id = (SELECT id FROM recorders WHERE name = 'YOUR_RECORDER_NAME')
ORDER BY created_at DESC;

-- Check signals
SELECT id, action, ticker, price, created_at 
FROM recorded_signals 
WHERE recorder_id = (SELECT id FROM recorders WHERE name = 'YOUR_RECORDER_NAME')
ORDER BY created_at DESC;
```

---

## ✅ WHAT TO LOOK FOR

### Success Indicators:

1. **Positions created from signals:**
   - ✅ `recorder_positions` table has entries
   - ✅ `total_quantity` matches signals sent
   - ✅ `avg_entry_price` is correct (weighted average for DCA)

2. **Signals recorded:**
   - ✅ `recorded_signals` table has all signals
   - ✅ Each signal has correct action, ticker, price

3. **No broker API calls:**
   - ✅ Server logs show NO "Syncing with broker" messages
   - ✅ Server logs show NO "get_positions" API calls

4. **P&L updating (if background thread running):**
   - ✅ `current_price` updates in database
   - ✅ `unrealized_pnl` calculates correctly
   - ✅ `worst_unrealized_pnl` tracks worst P&L

---

## 🧪 MANUAL TEST (If Script Doesn't Work)

**Test 1: Single BUY**
```bash
curl -X POST http://localhost:5000/webhook/YOUR_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "YOUR_RECORDER", "action": "buy", "ticker": "MNQ1!", "price": "25600"}'
```

**Expected:** Position created in database

**Test 2: DCA**
```bash
curl -X POST http://localhost:5000/webhook/YOUR_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "YOUR_RECORDER", "action": "buy", "ticker": "MNQ1!", "price": "25610"}'
```

**Expected:** Position updated: +2 @ 25605 avg

**Test 3: CLOSE**
```bash
curl -X POST http://localhost:5000/webhook/YOUR_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"recorder": "YOUR_RECORDER", "action": "close", "ticker": "MNQ1!", "price": "25620"}'
```

**Expected:** Position closed: status = 'closed', exit_price = 25620

---

## 🔍 CHECK SERVER LOGS

**Look for these messages:**
```
✅ Good (Signal-based):
📨 Webhook received for recorder 'YOUR_RECORDER'
📊 New position: LONG MNQ1! x1 @ 25600
📈 Position DCA: LONG MNQ1! +1 @ 25610 | Total: 2 @ avg 25605.00

❌ Bad (Still using broker):
🔄 Webhook: Syncing database with broker position
⚠️ Syncing with broker...
```

---

## 🎯 EXPECTED BEHAVIOR

### Signal-Based Tracking (What We Want):
```
Signal → Record in DB → Update position from signal → Done
✅ Fast (no API calls)
✅ Reliable (no network issues)
✅ Never misses signals
```

### Broker-Based Tracking (What We're Replacing):
```
Signal → Sync with broker → Place order → Poll broker → Update position
❌ Slow (API calls)
❌ Can fail (network issues)
❌ Can miss signals (if broker API fails)
```

---

## 🚨 TROUBLESHOOTING

### Issue: "Recorder not found"
- Check recorder name is correct
- Check recorder is enabled (`recording_enabled = 1`)
- Check webhook token matches

### Issue: Position not created
- Check server logs for errors
- Check database connection
- Verify signal was recorded in `recorded_signals` table

### Issue: Broker sync still happening
- Check `SIGNAL_BASED_TEST_MODE = True` is set
- Check the `if` statement includes the check
- Restart server after changes

---

## ✅ IF TESTS PASS

**You've proven signal-based tracking works!**

Next steps:
1. Keep `SIGNAL_BASED_TEST_MODE = True` (or remove broker sync entirely)
2. Disable reconciliation thread
3. Test with real TradingView webhooks
4. Monitor for any issues

---

## ❌ IF TESTS FAIL

**Debug steps:**
1. Check server logs for errors
2. Verify webhook endpoint is working
3. Check database schema matches expected structure
4. Verify recorder exists and is enabled
5. Check signal recording works (even if position doesn't update)

---

**This quick test will prove signal-based tracking works exactly like Trade Manager!**
