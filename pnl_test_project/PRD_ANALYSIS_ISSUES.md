# PRD Analysis - Why We're Having Issues

## Key Findings from PRD (https://gist.github.com/Mahdi451/7c94e2b37ecfc9ad037b31035e5e7a1a)

The PRD confirms our architecture but reveals critical gaps in our implementation.

---

## 🔴 CRITICAL ISSUE #1: Market Data WebSocket Authentication

### What the PRD Says:
> "Use a library like `ws` to connect to the Tradovate WebSocket endpoint (`wss://md.tradovateapi.com/v1/websocket`)"

**What it DOESN'T say**: How to authenticate!

### What Our Code Does (WRONG):
```python
# Line 875-879 in tradovate_integration.py
headers = {
    "Authorization": f"Bearer {token_to_use}"
}
self.ws_connection = await websockets.connect(ws_url, extra_headers=headers)
```

**Problem**: We're using HTTP headers for authentication, but:
- User data WebSocket uses **message-based auth**: `authorize\n0\n\n{TOKEN}`
- Market data WebSocket might need the **same message-based auth**
- The PRD doesn't specify, so we're guessing

### Evidence:
- User data WebSocket (line 924): Uses message-based auth ✅
- Market data WebSocket (line 879): Uses header-based auth ❓

**Likely Issue**: Market data WebSocket might reject header-based auth and require message-based auth like user data WebSocket.

---

## 🔴 CRITICAL ISSUE #2: Subscription Format Unknown

### What the PRD Says:
> "All incoming messages should be parsed (JSON parse if needed)"

**What it DOESN'T say**: How to subscribe to quotes!

### What Our Code Does (GUESSING):
```python
# Lines 1167-1185 in tradovate_integration.py
# Try 1: Newline-delimited
subscribe_msg_newline = f"subscribeQuote\n1\n\n{json.dumps(subscribe_data)}"

# Try 2: JSON-RPC
subscribe_msg_rpc = {"id": 1, "method": "subscribeQuote", "params": {...}}

# Try 3: Array format
subscribe_msg_array = ["subscribeQuote", {...}]
```

**Problem**: We're trying **3 different formats** because we don't know which one works!

### Why This Is A Problem:
1. Sending 3 subscriptions might confuse Tradovate
2. We don't know which format (if any) is correct
3. We're not receiving responses, so we can't tell which worked

**Likely Issue**: None of these formats might be correct, or we need to authenticate first.

---

## 🔴 CRITICAL ISSUE #3: No Message-Based Auth for Market Data

### Comparison:

**User Data WebSocket** (WORKING pattern):
```python
# Connect WITHOUT headers
self.ws_user_connection = await websockets.connect(ws_url)

# Authorize via MESSAGE
auth_message = f"authorize\n0\n\n{self.access_token}"
await self.ws_user_connection.send(auth_message)

# Subscribe via MESSAGE
subscribe_message = "user/syncRequest\n1\n\n"
await self.ws_user_connection.send(subscribe_message)
```

**Market Data WebSocket** (UNCERTAIN pattern):
```python
# Connect WITH headers (might be wrong!)
headers = {"Authorization": f"Bearer {token_to_use}"}
self.ws_connection = await websockets.connect(ws_url, extra_headers=headers)

# No explicit authorization message!
# Just tries to subscribe immediately
```

**Problem**: Market data WebSocket might need:
1. Connect WITHOUT headers
2. Send authorization MESSAGE first
3. Then subscribe

---

## 🔴 CRITICAL ISSUE #4: Message Parsing Assumptions

### What the PRD Says:
> "All incoming messages should be parsed (JSON parse if needed)"

### What Our Code Does:
```python
# Lines 991-1034 in tradovate_integration.py
data = json.loads(message)  # Assumes JSON

# Tries to handle:
# - Array format: [message_type, payload]
# - JSON-RPC format: {"method": "...", "params": {...}}
# - Dict format: {"e": "...", "d": {...}}
```

**Problem**: We're parsing defensively, but:
- We're not receiving ANY messages (quotes aren't coming)
- So we don't know what format Tradovate actually uses
- We might be parsing correctly, but never getting data to parse

**Likely Issue**: We're not subscribed correctly, so no messages arrive.

---

## 🔴 ROOT CAUSE ANALYSIS

### Why P&L is Frozen:

1. **Market Data WebSocket Not Authenticated Correctly**
   - Using headers instead of message-based auth
   - Tradovate might be rejecting the connection silently

2. **Subscription Not Working**
   - Trying 3 formats, but none might be correct
   - Or subscription fails because auth failed first

3. **No Quotes Received**
   - `ws_quotes` cache is empty
   - Falls back to stale `prevPrice` from REST API

4. **No Position Updates with `openPnl`**
   - User data WebSocket might be working
   - But position updates might not include `openPnl`
   - Or we're not parsing them correctly

---

## ✅ WHAT THE PRD CONFIRMS

1. **Architecture is Correct**
   - Separate WebSocket for market data ✅
   - Separate WebSocket for user data ✅
   - Message parsing is important ✅

2. **Real-time Data is Critical**
   - PRD emphasizes real-time updates ✅
   - We're trying to do this correctly ✅

3. **Error Handling Needed**
   - PRD mentions reconnection logic ✅
   - We have basic reconnection ✅

---

## ❌ WHAT THE PRD DOESN'T TELL US

1. **Exact Authentication Method**
   - How to auth market data WebSocket?
   - Message-based or header-based?

2. **Exact Subscription Format**
   - How to subscribe to quotes?
   - What message format?

3. **Exact Message Format**
   - What do quote messages look like?
   - What do position updates look like?

4. **Does `openPnl` Exist?**
   - PRD doesn't mention it
   - We're checking for it, but don't know if it exists

---

## 🎯 FIXES NEEDED

### Fix #1: Try Message-Based Auth for Market Data WebSocket

**Current** (line 879):
```python
headers = {"Authorization": f"Bearer {token_to_use}"}
self.ws_connection = await websockets.connect(ws_url, extra_headers=headers)
```

**Should Try**:
```python
# Connect WITHOUT headers
self.ws_connection = await websockets.connect(ws_url)

# Authorize via MESSAGE (like user data WebSocket)
auth_message = f"authorize\n0\n\n{self.md_access_token or self.access_token}"
await self.ws_connection.send(auth_message)

# Wait for auth response
await asyncio.sleep(0.5)
```

### Fix #2: Use Only ONE Subscription Format

**Current**: Tries 3 formats (confusing)

**Should Do**:
1. Try message-based auth first
2. Then try ONE subscription format
3. Log the response
4. If it fails, try next format

### Fix #3: Log ALL Incoming Messages

**Current**: Only logs parsed messages

**Should Do**:
```python
logger.info(f"RAW WebSocket message: {message}")
# Then try to parse
```

This will show us what Tradovate actually sends.

---

## 📋 ACTION PLAN

1. **Fix Market Data WebSocket Auth**
   - Remove header-based auth
   - Add message-based auth (like user data)
   - Test connection

2. **Fix Subscription Format**
   - Try ONE format at a time
   - Log responses
   - Document what works

3. **Add Comprehensive Logging**
   - Log ALL raw messages
   - Log ALL subscription attempts
   - Log ALL responses

4. **Test with Fresh Tokens**
   - Re-authenticate to get `mdAccessToken`
   - Run diagnostic
   - See actual Tradovate messages

---

## 🎯 BOTTOM LINE

**The PRD confirms our architecture is correct, but:**
- ❌ We're using wrong auth method for market data WebSocket
- ❌ We're guessing at subscription format
- ❌ We're not receiving messages, so we can't see what Tradovate sends

**The fix**: 
1. Use message-based auth for market data WebSocket (like user data)
2. Try subscription formats one at a time
3. Log everything to see what Tradovate actually sends
4. Test with fresh tokens

**Time to fix**: ~30 minutes (code changes) + testing

