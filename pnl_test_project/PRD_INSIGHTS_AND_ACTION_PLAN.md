# PRD Insights + Action Plan for P&L Tracking

## Key Insights from the PRD (https://gist.github.com/Mahdi451/7c94e2b37ecfc9ad037b31035e5e7a1a)

The PRD confirms our architecture approach and emphasizes:

### 1. **Message Parsing is Critical** (Section 3.1)
> "All incoming messages should be parsed (JSON parse if needed)"

**Our Current Implementation:**
- ✅ We parse JSON messages
- ✅ We handle Socket.IO format (`a[...]`)
- ✅ We handle plain JSON format
- ⚠️ **But we're not sure which format Tradovate actually uses**

### 2. **Position Updates Should Come from WebSocket** (Section 3.3)
> "For each fill, update the net position in the relevant contract/account"

**Our Current Implementation:**
- ✅ We listen for position updates via `user/syncRequest`
- ✅ We parse `{"e": "props", "d": {"entityType": "Position", "entity": {...}}}`
- ❓ **We check for `openPnl` but don't know if Tradovate sends it**

### 3. **Error Handling and Reconnection** (Section 3.1)
> "On close event, trigger a reconnection with an exponential backoff"

**Our Current Implementation:**
- ⚠️ We have basic reconnection but may need exponential backoff
- ⚠️ We need better error handling for failed subscriptions

### 4. **Real-time Data is the Goal** (Section 1)
> "Connects to the Tradovate WebSocket API for **real-time** market data"

**Our Problem:**
- ❌ We're falling back to stale `prevPrice` from REST API
- ❌ WebSocket quotes aren't being received
- ❌ Position updates may not include `openPnl`

---

## What the PRD Doesn't Tell Us (Tradovate-Specific)

The PRD is a **general architecture guide** - it doesn't specify:
1. ❓ Exact Tradovate WebSocket message formats
2. ❓ Exact subscription message format
3. ❓ Whether `openPnl` exists in position updates
4. ❓ Market data quote message structure

---

## Our Current Implementation Status

### ✅ What We're Doing Right (Based on PRD + Our Code)

1. **WebSocket Connection Management**
   - ✅ Connecting to `wss://md.tradovateapi.com/v1/websocket` for market data
   - ✅ Connecting to `wss://demo.tradovateapi.com/v1/websocket` for user data
   - ✅ Using `mdAccessToken` for market data WebSocket
   - ✅ Using `accessToken` for user data WebSocket

2. **Message Parsing** (Following PRD guidance)
   - ✅ Parsing JSON messages
   - ✅ Handling Socket.IO format
   - ✅ Handling multiple message formats (defensive programming)

3. **Position Tracking**
   - ✅ Listening for position updates
   - ✅ Checking for `openPnl` in position updates
   - ✅ Fallback to manual calculation

### ❌ What's Not Working

1. **Quote Subscriptions**
   - ❌ We try 3 different subscription formats (uncertain which works)
   - ❌ Quotes aren't being received
   - ❌ `ws_quotes` cache is empty

2. **Position Updates**
   - ❓ We check for `openPnl` but don't know if it exists
   - ❌ Falling back to stale `prevPrice`

3. **Token Management**
   - ❌ Token is expired
   - ❌ `mdAccessToken` may be missing

---

## Action Plan (Based on PRD + Current Issues)

### Phase 1: Fix Authentication (IMMEDIATE)

**Goal**: Get fresh tokens with `mdAccessToken`

**Steps**:
1. Use main server's `/api/accounts/<id>/authenticate` endpoint
2. Verify `mdAccessToken` is captured and stored
3. Test token validity

**Why**: Without valid tokens, we can't test WebSocket connections

---

### Phase 2: Verify WebSocket Message Formats (CRITICAL)

**Goal**: Determine exact Tradovate message formats

**Steps**:
1. Run `test_pnl_diagnostic.py` with fresh tokens
2. Connect to WebSocket and log ALL incoming messages
3. Document exact message formats we receive
4. Update code to use ONLY verified formats

**Why**: The PRD says "parse messages" but doesn't tell us Tradovate's format. We need to see what Tradovate actually sends.

---

### Phase 3: Fix Quote Subscriptions (CRITICAL)

**Goal**: Get real-time quotes working

**Steps**:
1. Test each subscription format individually
2. Log subscription responses
3. Verify quotes are being received
4. Update `ws_quotes` cache correctly

**Why**: Without real-time quotes, we fall back to stale `prevPrice`

---

### Phase 4: Verify Position Updates (IMPORTANT)

**Goal**: Check if `openPnl` exists in position updates

**Steps**:
1. Log ALL fields in position update messages
2. Check if `openPnl` or `unrealizedPnl` exists
3. If not, ensure manual calculation uses real-time quotes (not `prevPrice`)

**Why**: If Tradovate provides `openPnl`, we should use it. If not, we need accurate quotes for calculation.

---

### Phase 5: Implement PRD Best Practices (IMPROVEMENT)

**Goal**: Add robust error handling and reconnection

**Steps**:
1. Implement exponential backoff for reconnection
2. Add better error logging
3. Handle partial messages
4. Add duplicate prevention for position updates

**Why**: PRD emphasizes robust error handling - this will make the system more reliable

---

## Immediate Next Steps

1. **Re-authenticate** to get fresh tokens
2. **Run diagnostic script** to see what Tradovate actually sends
3. **Document exact message formats** from real responses
4. **Update code** to use verified formats only
5. **Test** with real open position

---

## Key Takeaway from PRD

The PRD confirms our architecture is correct, but emphasizes:
- **Message parsing must be robust** - handle multiple formats
- **Real-time data is critical** - don't fall back to stale data
- **Error handling is essential** - implement reconnection and retry logic

**Our specific issue**: We're trying multiple formats (good), but we need to **verify which one Tradovate actually uses** by testing with real connections and logging actual messages.

