# Testing Guide - Browser Testing with Log Monitoring

## Setup

1. **Server is running** ✅ (PID: 41844)
2. **I'll monitor logs** - Watching for WebSocket, quotes, P&L
3. **You test in browser** - Tell me what you see

---

## What I'm Monitoring

### 🔵 WebSocket Connections
- Market Data WebSocket connection
- User Data WebSocket connection
- Authorization messages
- Connection status

### 🟢 Quote Subscriptions
- Subscription messages sent
- Quote updates received
- Contract IDs and symbols

### 🟡 P&L Calculations
- Which price source is used (WebSocket quote vs prevPrice)
- P&L calculation method
- Real-time updates

### 🔴 Errors
- Connection failures
- Authentication errors
- Subscription failures
- Missing data

---

## What to Look For in Browser

### 1. Positions Page
- **URL**: `http://localhost:8082` → Navigate to Positions
- **What to check**:
  - Are positions showing?
  - Are symbols correct (not "Contract-XXXXXXX")?
  - Is P&L showing?
  - Does P&L update when market moves?

### 2. P&L Behavior
- **Frozen?** - P&L stays the same
- **Updating?** - P&L changes with market
- **Wrong values?** - P&L seems incorrect

### 3. Refresh Behavior
- **Manual refresh** - Does P&L update?
- **Auto refresh** - Is there auto-refresh? How often?

---

## Testing Steps

### Step 1: Open Positions Page
1. Go to `http://localhost:8082`
2. Navigate to Positions/Open Positions
3. **Tell me**: 
   - Do you see any positions?
   - What symbols are shown?
   - What P&L values are shown?

### Step 2: Watch for Updates
1. Keep positions page open
2. Watch P&L values for 30-60 seconds
3. **Tell me**:
   - Do P&L values change?
   - How often do they update?
   - Are they frozen?

### Step 3: Check Browser Console
1. Open browser DevTools (F12)
2. Go to Console tab
3. **Tell me**:
   - Any errors?
   - Any WebSocket connection messages?
   - Any API call errors?

---

## What I'll Tell You

While you test, I'll report:

1. **WebSocket Status**
   - ✅ Connected / ❌ Failed
   - Authorization success/failure

2. **Quote Subscriptions**
   - ✅ Subscribed / ❌ Failed
   - Quotes received / Not received

3. **P&L Calculation**
   - Using WebSocket quotes (✅ Real-time)
   - Using prevPrice (❌ Stale)
   - Using openPnl from WebSocket (✅ Best)

4. **Errors**
   - Any connection issues
   - Any subscription failures
   - Any missing data

---

## Quick Test Commands

While you test, I can also run:

```bash
# Check positions endpoint
curl http://localhost:8082/api/positions | python3 -m json.tool

# Check token status
sqlite3 just_trades.db "SELECT id, name, datetime(token_expires_at) as expires FROM accounts WHERE broker='Tradovate';"
```

---

## Expected vs Actual

### Expected (If Working):
- ✅ WebSocket connects
- ✅ Quotes subscribed
- ✅ Quotes received
- ✅ P&L updates in real-time
- ✅ Uses WebSocket quotes (not prevPrice)

### If Not Working:
- ❌ WebSocket fails to connect
- ❌ Subscription fails
- ❌ No quotes received
- ❌ P&L uses prevPrice (stale)
- ❌ P&L is frozen

---

## Ready to Test?

1. **You**: Open browser, go to positions page
2. **Me**: Monitor logs and report what I see
3. **You**: Tell me what you see in browser
4. **Together**: Compare and fix any issues

Let me know when you're ready to start!

