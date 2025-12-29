# How to Run the Signal-Based Tracking Accuracy Test

## Quick Start

### Option 1: Automated Script (Easiest)
```bash
./run_accuracy_test.sh
```

This will:
1. Check if server is running
2. Start server in test mode if needed
3. Setup test environment
4. Run the long-term accuracy test

---

### Option 2: Manual Steps

#### Step 1: Start Server in Test Mode
```bash
export SIGNAL_BASED_TEST=true
python3 recorder_service.py
```

**Or in background:**
```bash
export SIGNAL_BASED_TEST=true
nohup python3 recorder_service.py > /tmp/recorder_test.log 2>&1 &
```

#### Step 2: Setup Test Environment
```bash
python3 setup_test_environment.py
```

This creates a test recorder and updates the test script with the correct webhook token.

#### Step 3: Run the Test
```bash
python3 test_long_term_accuracy.py
```

The test will:
- Send initial test signals
- Monitor accuracy every 10 seconds
- Run for 60 minutes (or until you stop it)
- Show real-time accuracy results
- Generate final report

---

## What the Test Does

1. **Sends Test Signals:**
   - BUY 1 MNQ @ 25600
   - BUY 1 MNQ @ 25610 (DCA)
   - BUY 1 MNQ @ 25620 (DCA)
   - Creates position: +3 MNQ @ 25610 avg

2. **Monitors Accuracy:**
   - Checks position matches expected from signals
   - Verifies P&L calculation is correct
   - Tracks how long it stays accurate

3. **Reports Results:**
   - Total time accurate
   - Accuracy percentage
   - First failure time (if any)
   - Final position state

---

## Expected Output

```
🧪 LONG-TERM SIGNAL-BASED TRACKING ACCURACY TEST
============================================================

📨 Sending test signals...
  ✅ BUY 1 MNQ @ 25600
  ✅ BUY 1 MNQ @ 25610 (DCA)
  ✅ BUY 1 MNQ @ 25620 (DCA)

⏱️  Starting accuracy monitoring...
   Will run until 15:30:00
   Checking every 10 seconds

[14:30:10] Check #1 ✅
  Position: Position accurate
  P&L: P&L accurate: $120.00
  Current: LONG 3 @ 25610.00
  Price: 25620.00 | P&L: $60.00

[14:30:20] Check #2 ✅
  Position: Position accurate
  ...

📊 FINAL TEST RESULTS
============================================================

Test Duration: 3600 seconds (60.0 minutes)
Total Checks: 360
Accurate Checks: 360
Accuracy Rate: 100.0%
Max Consecutive Failures: 0

✅ NO FAILURES - Stayed accurate for entire test duration!
   Time Accurate: 3600 seconds (60.0 minutes)
```

---

## Stopping the Test

Press `Ctrl+C` to stop the test early. It will show a summary of results.

---

## Troubleshooting

### Server Not Starting
```bash
# Check logs
tail -f /tmp/recorder_test.log

# Check if port is in use
lsof -i :8083
```

### Test Recorder Not Found
```bash
# Run setup again
python3 setup_test_environment.py
```

### Webhook Errors
- Check webhook token is correct
- Check server is running on port 8083
- Check recorder is enabled

---

## Interpreting Results

### ✅ Excellent (99%+ accuracy)
- Signal-based tracking is highly accurate
- Safe to implement permanently

### ✅ Good (95-99% accuracy)
- Mostly accurate with minor issues
- Generally reliable

### ❌ Poor (<95% accuracy)
- Has accuracy issues
- Review failures before implementing

---

## Next Steps After Test

**If test passes:**
1. Keep `SIGNAL_BASED_TEST_MODE` enabled (or remove broker sync)
2. Disable reconciliation thread
3. Deploy to production

**If test fails:**
1. Review failure logs
2. Identify specific issues
3. Fix problems
4. Re-test

---

**The test will prove if signal-based tracking stays accurate over time!**
