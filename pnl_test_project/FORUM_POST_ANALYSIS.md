# Forum Post Analysis: "Api websocket and marketdata websocket"

## Source
- **Author**: beebee
- **Date**: Feb 2022
- **Forum**: Tradovate Community Forum
- **URL**: community.tradovate.com/t/api-websocket-and-marketdata-websocket/4037

---

## Key Information from Post

### 1. Two Separate WebSocket Connections Confirmed

**Market Data WebSocket:**
- URL: `wss://md-demo.tradovateapi.com/v1/websocket`
- Status: ✅ **WORKING** - Successfully subscribes to futures and receives market data
- Token Used: `mdAccessToken` (implied)

**Order/User Data WebSocket:**
- URL: `wss://demo.tradovateapi.com/v1/websocket`
- Status: ⚠️ **CONNECTS** but has authorization issues
- Token Used: `accessToken` (implied)

---

### 2. Authentication Confirms Two Tokens

**From the post:**
> "During authentication, two access tokens are returned: `accessToken` and `mdAccessToken`"

**This confirms:**
- ✅ Two tokens are returned (we already know this)
- ✅ `mdAccessToken` is for market data WebSocket
- ✅ `accessToken` is for user data/order WebSocket

---

### 3. Authorization Problem Identified

**The Issue:**
- Market data WebSocket: ✅ Works fine
- User data WebSocket: ❌ "Access denied" when trying to place orders

**Error Response:**
```json
{
  "s": 200,
  "i": 0,
  "d": {
    "failureReason": "UnknownReason",
    "failureText": "Access is denied"
  }
}
```

**This suggests:**
- ⚠️ The `accessToken` might not have the right permissions
- ⚠️ Or the authorization format might be wrong
- ⚠️ Or the sequence number might be an issue

---

### 4. Questions Raised

**Question 1:**
> "Why am I getting 'Access denied' for sending buy/sell orders but not for market data?"

**Possible Answers:**
- Different permission levels for `accessToken` vs `mdAccessToken`
- Authorization format might be different for user data WebSocket
- Need to use different token or additional authorization

**Question 2:**
> "Does the sequence number need to be unique across the entire session or unique for each individual WebSocket connection?"

**This is important:**
- Sequence numbers might need to be unique per connection
- Or they might need to be unique across all connections
- This could affect message ordering and authorization

---

## Implications for Our Implementation

### 1. WebSocket URLs
**Confirmed:**
- Market Data: `wss://md-demo.tradovateapi.com/v1/websocket` (or `wss://md.tradovateapi.com/v1/websocket`)
- User Data: `wss://demo.tradovateapi.com/v1/websocket` (or `wss://live.tradovateapi.com/v1/websocket`)

**Status**: ✅ Matches what we have in our code

---

### 2. Token Usage
**Confirmed:**
- `mdAccessToken` → Market Data WebSocket ✅
- `accessToken` → User Data WebSocket ✅

**Status**: ✅ Matches what we have in our code

---

### 3. Authorization Issues
**Potential Problem:**
- User data WebSocket might need different authorization format
- Or might need additional permissions
- Or sequence numbers might be wrong

**What We Need to Check:**
- [ ] Is our authorization format correct for user data WebSocket?
- [ ] Are we using the right sequence numbers?
- [ ] Do we have the right permissions on the `accessToken`?

---

### 4. Message Format Clue
**From the error response:**
```json
{
  "s": 200,  // Status code?
  "i": 0,    // Sequence number?
  "d": {     // Data payload
    "failureReason": "UnknownReason",
    "failureText": "Access is denied"
  }
}
```

**This suggests:**
- Messages might have format: `{"s": status, "i": sequence, "d": data}`
- Or Socket.IO format: `a[{"s": 200, "i": 0, "d": {...}}]`
- Sequence number `i` is important

---

## What This Tells Us

### ✅ Confirmed
1. Two separate WebSocket connections (we know this)
2. Two different tokens (we know this)
3. Market data WebSocket works (good sign)
4. User data WebSocket can connect but has authorization issues

### ⚠️ Potential Issues
1. Authorization format for user data WebSocket might be wrong
2. Sequence numbers might need to be handled differently
3. Permissions on `accessToken` might be insufficient

### ❓ Still Unknown
1. Exact authorization format that works
2. How sequence numbers should be managed
3. What permissions are needed for `accessToken`

---

## Next Steps Based on This Post

1. **Check Authorization Format**
   - Verify we're using the correct format for user data WebSocket
   - Compare with market data WebSocket (which works)

2. **Check Sequence Numbers**
   - Ensure sequence numbers are unique per connection
   - Or ensure they're unique across all connections

3. **Check Permissions**
   - Verify `accessToken` has order placement permissions
   - May need to request different permissions during authentication

4. **Look for Replies**
   - Check if there are replies to this post with solutions
   - See what worked for others

---

## Questions to Answer

1. What authorization format did the user use that caused "Access denied"?
2. What authorization format works for market data (since that works)?
3. Are there replies to this post with solutions?
4. What sequence number format should we use?

---

## Notes

- This post is from Feb 2022 - might be outdated
- But it confirms the two-WebSocket approach
- Shows there can be authorization issues
- Suggests sequence numbers are important

