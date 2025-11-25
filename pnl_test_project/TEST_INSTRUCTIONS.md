# How to Test the P&L Tracking Project

## Step-by-Step Instructions

### Step 1: Install Dependencies

```bash
cd "/Users/mylesjadwin/Trading Projects/pnl_test_project"
pip install -r requirements.txt
```

**Expected Output:**
```
Collecting aiohttp>=3.8.0
Collecting websockets>=11.0
...
Successfully installed aiohttp-3.x.x websockets-11.x.x
```

---

### Step 2: Prepare Your Credentials

**You'll need:**
- ✅ Tradovate username
- ✅ Tradovate password
- ✅ Demo or Live account? (demo is recommended for testing)
- ✅ Optional: Client ID and Client Secret (if using OAuth app)

**Make sure you have:**
- ✅ At least one **OPEN POSITION** in Tradovate
  - Position must have `netPos != 0` (not closed)
  - Can be any contract (MNQ, MES, NQ, ES, etc.)

---

### Step 3: Run the Test

```bash
python test_pnl_tracking.py
```

**The script will ask you:**
1. Username: `your_tradovate_username`
2. Password: `your_tradovate_password`
3. Use Client ID/Secret? (y/n): `n` (unless you have OAuth app)
4. Use demo account? (y/n): `y` (recommended for testing)

---

### Step 4: Watch the Output

**What You'll See:**

#### 1. Authentication Phase
```
============================================================
STEP 1: Authenticating with Tradovate
============================================================
Auth response status: 200
✅ Got accessToken: abc123...
✅ Got mdAccessToken: xyz789...
✅ Got account from /account/list:
   accountId: 123456 (use for orders/positions)
   accountSpec: DEMO4419847-2 (from auth response)
   userId: 789012 (from auth response, use for subscriptions)
```

**✅ Success Indicators:**
- Status 200
- Got both `accessToken` and `mdAccessToken`
- Got account information

**❌ Failure Indicators:**
- Status 401/403 (authentication failed)
- No `mdAccessToken` (market data won't work)
- No account information

---

#### 2. Position Fetching
```
============================================================
STEP 2: Fetching open positions from REST API
============================================================
Got 1 positions from REST API
Found 1 OPEN positions (netPos != 0)
  Position 123456: contract=4086418, netPos=1, netPrice=24967.75
  Contract 4086418: MNQZ5
```

**✅ Success Indicators:**
- Found open positions
- Got contract information
- Shows symbol (e.g., MNQZ5)

**❌ Failure Indicators:**
- "No open positions found!" (need to open a position first)
- "Could not get contract info" (may still work, just won't show symbol)

---

#### 3. WebSocket Connections
```
============================================================
STEP 3: Connecting to User Data WebSocket
============================================================
Connecting to: wss://demo.tradovateapi.com/v1/websocket
✅ Connected to Tradovate User Data WebSocket
✅ Sent authorization message
✅ Subscribed to user/syncRequest

============================================================
STEP 4: Connecting to Market Data WebSocket
============================================================
Connecting to: wss://md.tradovateapi.com/v1/websocket
✅ Market data WebSocket connected
✅ Market data WebSocket authorized
```

**✅ Success Indicators:**
- Both WebSockets connected
- Authorization sent successfully
- Subscriptions sent

**❌ Failure Indicators:**
- Connection refused
- Authentication failed
- No subscription confirmation

---

#### 4. Subscription Attempts
```
Attempting to subscribe to quotes for contract 4086418
✅ Sent subscription (format 1 - newline-delimited) for contract 4086418
✅ Sent subscription (format 2 - JSON-RPC) for contract 4086418
✅ Sent subscription (format 3 - array) for contract 4086418
📊 Watch for quote updates for contract 4086418 - will show which format works
```

**What to Look For:**
- All 3 formats sent (we're trying all of them)
- Watch for quote updates in the logs
- One format should work (we'll see which one)

---

#### 5. Real-Time Updates
```
📨 User WS (JSON): {"e": "props", "d": {"entityType": "Position", "entity": {...}}}
🔄 Position Update: id=123456, netPos=1, openPnl=123.45

📊 Market Data WS (JSON): {"contractId": 4086418, "ask": 24968.0, "bid": 24967.5, "last": 24967.75}
💰 Quote Update: contract=4086418, last=24967.75, ask=24968.0, bid=24967.5
```

**✅ Success Indicators:**
- Receiving position updates
- Receiving quote updates
- Prices updating in real-time

**❌ Failure Indicators:**
- No messages received
- Only error messages
- Prices not updating

---

#### 6. P&L Display
```
============================================================
P&L UPDATE - 19:30:45
============================================================

Position: MNQZ5 (ID: 123456)
  Contract ID: 4086418
  Net Position: 1
  Entry Price: 24967.75
  Current Price: 24968.0
  💰 P&L: $0.50
  📡 WebSocket openPnl: $0.50
============================================================
```

**✅ Success Indicators:**
- P&L values updating every second
- Current price changing
- P&L matches market movement

**❌ Failure Indicators:**
- P&L stuck at $0.00
- "Cannot calculate (no price data)"
- Prices not updating

---

## What to Look For

### ✅ Success Signs

1. **Authentication Works**
   - Got both tokens
   - Got account information

2. **WebSockets Connect**
   - Both connections established
   - Authorization successful

3. **Messages Received**
   - Position updates coming through
   - Quote updates coming through
   - Messages in JSON format

4. **P&L Updates**
   - Values changing every second
   - Matches market movement
   - Shows both calculated and WebSocket `openPnl` (if available)

---

### ❌ Problem Signs

1. **Authentication Fails**
   - Check credentials
   - Check if using correct account type (demo/live)
   - Check if Client ID/Secret needed

2. **WebSocket Connection Fails**
   - Check if `mdAccessToken` was captured
   - Check network connection
   - Check if Tradovate API is accessible

3. **No Messages Received**
   - Check subscription format (we're trying all 3)
   - Check if position is actually open
   - Check if contract ID is correct

4. **P&L Not Updating**
   - Check if quotes are being received
   - Check if position data is correct
   - Check if multiplier is correct

---

## Troubleshooting

### Problem: "No mdAccessToken"
**Solution:**
- Re-authenticate
- Check if account has API access
- May need to use OAuth app

### Problem: "No open positions found"
**Solution:**
- Open a position in Tradovate first
- Make sure position has `netPos != 0`
- Check if using correct account

### Problem: "WebSocket connection failed"
**Solution:**
- Check network connection
- Check if Tradovate API is accessible
- Try again (may be temporary)

### Problem: "No quote updates"
**Solution:**
- Check which subscription format worked (in logs)
- May need to adjust subscription format
- Check if contract ID is correct

### Problem: "P&L stuck at $0.00"
**Solution:**
- Check if quotes are being received
- Check if position data is correct
- Check if multiplier is correct for contract

---

## Expected Test Duration

- **Setup**: 1-2 minutes
- **Test Run**: Let it run for 1-2 minutes to see updates
- **Analysis**: Review logs to see what worked

---

## What to Do After Test

### If It Works:
1. ✅ Document the working subscription format
2. ✅ Note which message formats Tradovate uses
3. ✅ Verify if `openPnl` exists in position updates
4. ✅ Integrate into main project

### If It Doesn't Work:
1. ❌ Review error messages
2. ❌ Check which step failed
3. ❌ Look at raw WebSocket messages in logs
4. ❌ Adjust based on what Tradovate actually sends

---

## Next Steps

1. **Run the test** following steps above
2. **Watch the output** for success/failure indicators
3. **Review logs** to see what Tradovate actually sends
4. **Fix issues** based on real responses
5. **Iterate** until it works

---

## Quick Start Command

```bash
cd "/Users/mylesjadwin/Trading Projects/pnl_test_project" && \
pip install -r requirements.txt && \
python test_pnl_tracking.py
```

Then enter your credentials when prompted!

