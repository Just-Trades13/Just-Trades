# Pre-Test Checklist: What We're Missing

## 🔍 Review Status

### ✅ What We Have

1. **Test Project Structure**
   - ✅ Main test script (`test_pnl_tracking.py`)
   - ✅ Requirements file (`requirements.txt`)
   - ✅ README with instructions
   - ✅ Research documentation

2. **Authentication**
   - ✅ REST API authentication
   - ✅ Token capture (accessToken, mdAccessToken)
   - ✅ Account list retrieval (with correct accountId)

3. **WebSocket Connections**
   - ✅ User data WebSocket connection
   - ✅ Market data WebSocket connection
   - ✅ Basic error handling

4. **Message Parsing**
   - ✅ Handles Socket.IO format (`a[{...}]`)
   - ✅ Handles JSON format
   - ✅ Handles Trade Manager format (`{"type": "DATA", "data": {...}}`)
   - ✅ Extracts prices (ask/bid/last)

5. **P&L Calculation**
   - ✅ Tries to get `openPnl` from WebSocket
   - ✅ Falls back to calculating from prices
   - ✅ Handles contract multipliers

6. **Logging**
   - ✅ Extensive logging throughout
   - ✅ Logs all WebSocket messages
   - ✅ Logs P&L calculations

---

## ❌ What We're Missing

### 1. Market Data Subscription Format ⚠️ CRITICAL

**Current Status:**
- We connect to market data WebSocket
- We authenticate
- **BUT**: We don't subscribe to specific contracts!

**What's Missing:**
```python
# We need to subscribe to quotes for contracts we have positions in
# But we don't know the exact format!
```

**Options We Have:**
- Newline-delimited: `subscribeQuote\n1\n\n{JSON}`
- JSON-RPC: `{"id": 1, "method": "subscribeQuote", "params": {...}}`
- Array: `["subscribeQuote", {...}]`

**What We Need:**
- [ ] Verify which subscription format works
- [ ] Subscribe to contracts we have positions in
- [ ] Handle subscription responses

**Current Code:**
```python
# In main(), we try to subscribe but format is uncertain:
subscribe_msg = f"md/subscribeQuote\n1\n\n{contract_id}"
# OR
subscribe_msg = json.dumps({"id": 1, "method": "subscribeQuote", "params": {"contractId": contract_id}})
```

---

### 2. User Data Subscription Verification ⚠️

**Current Status:**
- We use: `user/syncRequest\n1\n\n`
- This is from your existing code
- **BUT**: Not verified from external examples

**What's Missing:**
- [ ] Verify this subscription format works
- [ ] Check if we need additional subscriptions
- [ ] Verify we're getting position updates

**Current Code:**
```python
subscribe_message = "user/syncRequest\n1\n\n"
await self.ws_user.send(subscribe_message)
```

---

### 3. Reconnection Logic ⚠️

**Current Status:**
- Basic connection
- Heartbeat messages
- **BUT**: No automatic reconnection on disconnect

**What's Missing:**
- [ ] Automatic reconnection with exponential backoff
- [ ] Max retry limit
- [ ] Re-subscribe after reconnection
- [ ] Handle connection failures gracefully

**From PRD:**
```python
private reconnect() {
  if (this.reconnectAttempts < this.maxReconnectAttempts) {
    this.reconnectAttempts++;
    setTimeout(() => {
      this.connect();
    }, 1000 * this.reconnectAttempts); // Exponential backoff
  }
}
```

---

### 4. Contract ID to Symbol Mapping ⚠️

**Current Status:**
- We get contract info from REST API
- Store in `self.contracts` dict
- **BUT**: May not have all contracts we need

**What's Missing:**
- [ ] Ensure we get contract info for all positions
- [ ] Map contract IDs to symbols correctly
- [ ] Handle missing contract info gracefully

---

### 5. Error Handling for Edge Cases ⚠️

**Current Status:**
- Basic try/catch blocks
- Logs errors
- **BUT**: May not handle all edge cases

**What's Missing:**
- [ ] Handle partial messages
- [ ] Handle malformed JSON
- [ ] Handle missing required fields
- [ ] Handle WebSocket connection drops
- [ ] Handle authentication failures

---

### 6. Subscription Response Handling ⚠️

**Current Status:**
- We send subscriptions
- **BUT**: We don't check for subscription confirmations

**What's Missing:**
- [ ] Listen for subscription confirmations
- [ ] Handle subscription errors
- [ ] Verify subscriptions are active
- [ ] Re-subscribe if needed

---

### 7. Position Filtering ⚠️

**Current Status:**
- We get positions from REST API
- Filter by `netPos != 0`
- **BUT**: May need to filter by accountId

**What's Missing:**
- [ ] Filter positions by accountId (from account list)
- [ ] Ensure we only track positions for the correct account
- [ ] Handle multiple accounts if needed

---

### 8. Testing Prerequisites ⚠️

**What We Need Before Testing:**
- [ ] Verify dependencies are installed (`pip install -r requirements.txt`)
- [ ] Have Tradovate credentials ready
- [ ] Have at least one OPEN position in Tradovate
- [ ] Know which account to use (demo vs live)
- [ ] Have Client ID/Secret if using OAuth

---

## 🎯 Critical Missing Items (Must Fix Before Test)

### 1. Market Data Subscription ⚠️⚠️⚠️
**Priority: CRITICAL**
- Without subscription, we won't get quote updates
- Need to verify format and subscribe to contracts

### 2. Reconnection Logic ⚠️⚠️
**Priority: HIGH**
- WebSocket connections can drop
- Need automatic reconnection
- Need to re-subscribe after reconnection

### 3. Subscription Verification ⚠️
**Priority: MEDIUM**
- Need to verify subscriptions are active
- Handle subscription errors
- Re-subscribe if needed

---

## 📋 Pre-Test Checklist

### Before Running Test:
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Have Tradovate credentials
- [ ] Have open position in Tradovate
- [ ] Know account type (demo/live)
- [ ] Have Client ID/Secret (if using OAuth)

### During Test, We'll Discover:
- [ ] What subscription format actually works
- [ ] What message format Tradovate sends
- [ ] Whether `openPnl` exists in position updates
- [ ] What quote message format looks like
- [ ] Whether authentication format is correct

### After Test, We'll Fix:
- [ ] Update subscription format if wrong
- [ ] Add reconnection logic
- [ ] Improve error handling
- [ ] Fix any parsing issues
- [ ] Optimize P&L calculation

---

## 🔧 Quick Fixes We Can Add Now

### 1. Add Reconnection Logic
```python
async def reconnect_websocket(self, ws_type='user'):
    """Reconnect WebSocket with exponential backoff"""
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            wait_time = 2 ** attempt  # Exponential backoff
            await asyncio.sleep(wait_time)
            logger.info(f"Reconnecting {ws_type} WebSocket (attempt {attempt + 1})...")
            if ws_type == 'user':
                return await self.connect_user_websocket()
            else:
                return await self.connect_market_data_websocket()
        except Exception as e:
            logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
    return False
```

### 2. Add Subscription Verification
```python
async def verify_subscription(self, contract_id):
    """Verify subscription is active"""
    # Wait for confirmation message
    # Check if we're receiving quotes
    # Re-subscribe if needed
    pass
```

### 3. Add Better Error Handling
```python
async def safe_parse_message(self, message):
    """Safely parse WebSocket message with error handling"""
    try:
        if message.startswith('a['):
            json_str = message[2:-1]
            return json.loads(json_str)
        else:
            return json.loads(message)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse message: {e}")
        logger.debug(f"Raw message: {message[:200]}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error parsing message: {e}")
        return None
```

---

## 📝 Summary

### Must Have Before Test:
1. ✅ Test project code (DONE)
2. ✅ Dependencies file (DONE)
3. ⚠️ Market data subscription (UNCERTAIN FORMAT)
4. ⚠️ Reconnection logic (MISSING)
5. ✅ Extensive logging (DONE)

### Will Discover During Test:
- Exact subscription format
- Message formats
- Whether `openPnl` exists
- What needs to be fixed

### Can Add After First Test:
- Reconnection logic (if connections drop)
- Better error handling (if we see errors)
- Subscription verification (if subscriptions fail)
- Performance optimizations

---

## 🚀 Recommendation

**We can test now, but expect:**
1. May need to adjust subscription format
2. May need to add reconnection logic
3. Will discover what Tradovate actually sends
4. Will fix issues based on real responses

**The test will show us:**
- What works
- What doesn't work
- What needs to be fixed

**This is the purpose of the test project** - to discover what we don't know!

---

## Next Steps

1. **Option A: Test Now**
   - Run test and see what happens
   - Fix issues as we discover them
   - Iterate based on real responses

2. **Option B: Add Reconnection First**
   - Add basic reconnection logic
   - Then test
   - More robust but may not be needed

**Recommendation: Test Now** - The test will show us what actually needs to be fixed!

