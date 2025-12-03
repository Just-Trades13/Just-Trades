# Testing Guide - WebSocket Implementation

**Status**: Ready for Testing  
**Date**: December 2025

---

## 🚀 Quick Start Test

### Step 1: Start the Server
```bash
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python ultra_simple_server.py
```

**Expected Output:**
```
Starting Just.Trades. server on 0.0.0.0:8082
WebSocket support enabled (like Trade Manager)
```

---

## ✅ Test Checklist

### Test 1: WebSocket Connection
1. **Open browser** to `http://localhost:8082/control-center`
2. **Open DevTools** (F12) → Console tab
3. **Expected**: See "✅ Connected to WebSocket - Dashboard" or "Connected to WebSocket"
4. **Check Network tab** → Filter by "WS" → Should see WebSocket connection

**✅ Pass**: WebSocket connects  
**❌ Fail**: Check server logs, verify flask-socketio installed

---

### Test 2: Real-Time Updates
1. **Stay on Control Center page**
2. **Watch console** - Should see update messages every second:
   - `P&L update: {...}`
   - `Position update: {...}`
3. **Check status dot** - Should show "Connected"

**✅ Pass**: Updates appear every second  
**❌ Fail**: Check background threads are running

---

### Test 3: Trade Execution
1. **Go to Manual Trader** page
2. **Place a trade** (buy/sell)
3. **Go back to Control Center**
4. **Expected**: Log entry appears in AutoTrader Logs immediately

**✅ Pass**: Log entry appears  
**❌ Fail**: Check WebSocket event emission in server logs

---

### Test 4: Dashboard Updates
1. **Open Dashboard** page
2. **Open DevTools** → Console
3. **Expected**: See "✅ Connected to WebSocket - Dashboard"
4. **Watch console** - Should see P&L updates every second
5. **Place a trade** - Should see trade_executed event

**✅ Pass**: Dashboard receives updates  
**❌ Fail**: Check Socket.IO script loaded

---

### Test 5: P&L Recording
1. **Enable a strategy** (if you have one)
2. **Wait a few seconds**
3. **Check database**:
   ```bash
   sqlite3 trading_webhook.db "SELECT * FROM strategy_pnl_history ORDER BY timestamp DESC LIMIT 5;"
   ```
4. **Expected**: See P&L records being created

**✅ Pass**: Records appear in database  
**❌ Fail**: Check strategies table exists, verify calculate_strategy_pnl() works

---

## 🔍 Debugging

### WebSocket Not Connecting?
1. **Check server logs** - Look for WebSocket errors
2. **Check browser console** - Look for connection errors
3. **Verify flask-socketio installed**: `pip list | grep flask-socketio`
4. **Check port** - Make sure port 8082 is not in use

### No Updates Appearing?
1. **Check background threads** - Should be running
2. **Check database** - Make sure you have trades/positions
3. **Check console** - Look for error messages
4. **Verify database connections** - Check if tables exist

### P&L Not Calculating?
1. **Check database** - Verify trades table has data
2. **Check calculate_strategy_pnl()** - May need to adjust queries
3. **Check SQLAlchemy models** - If using models, verify imports work

---

## 📊 Expected Behavior

### Every Second:
- P&L update event emitted
- Position update event emitted
- Strategy P&L recorded (if strategies exist)

### On Trade Execution:
- Log entry event emitted
- Position update event emitted
- Trade executed event emitted

### On Page Load:
- WebSocket connects immediately
- Status indicator shows "Connected"
- Updates start flowing

---

## 🎯 Success Criteria

**✅ All Tests Pass When:**
1. WebSocket connects on both pages
2. Updates appear every second in console
3. Trade execution triggers events
4. Log entries appear in real-time
5. P&L numbers update (if you have trades)

---

**Ready to test!** Start the server and follow the checklist above.
