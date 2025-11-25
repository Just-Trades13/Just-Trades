# Quick Test Guide

## 🚀 Fast Start

### 1. Install Dependencies (if needed)
```bash
cd "/Users/mylesjadwin/Trading Projects/pnl_test_project"
pip install -r requirements.txt
```

### 2. Run the Test
```bash
python test_pnl_tracking.py
```

### 3. Enter Your Credentials
The script will ask for:
- Username
- Password
- Use Client ID/Secret? (usually `n`)
- Use demo account? (recommended: `y`)

### 4. Watch the Output
- ✅ Green checkmarks = Success
- ❌ Red X or errors = Problem
- 📊 Logs show what Tradovate sends

---

## 📋 Before You Start

**Make sure you have:**
- ✅ Tradovate account credentials
- ✅ At least one **OPEN POSITION** in Tradovate
- ✅ Internet connection

---

## 🎯 What Success Looks Like

```
✅ Got accessToken: abc123...
✅ Got mdAccessToken: xyz789...
✅ Found 1 open position(s)
✅ Connected to Tradovate User Data WebSocket
✅ Market data WebSocket connected
📊 Quote Update: contract=4086418, last=24967.75
💰 P&L: $0.50
```

---

## ❌ What Problems Look Like

```
❌ Authentication failed!
❌ No mdAccessToken in response
❌ No open positions found!
❌ WebSocket connection failed
⚠️  P&L: Cannot calculate (no price data)
```

---

## 🔍 What to Watch For

1. **Authentication** - Should get both tokens
2. **WebSocket Connections** - Both should connect
3. **Messages** - Should see position and quote updates
4. **P&L Updates** - Should update every second

---

## 🛑 To Stop the Test

Press `Ctrl+C` to stop

---

## 📝 After the Test

Review the logs to see:
- What message formats Tradovate uses
- Which subscription format worked
- Whether `openPnl` exists
- What needs to be fixed

