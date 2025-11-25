# Comprehensive Tradovate P&L Tracking Research

## Research Date: 2025-11-24
## Status: IN PROGRESS - Gathering working examples

---

## Research Sources

### 1. Official Tradovate Resources
- **API Documentation**: https://api.tradovate.com/docs (404 - not accessible)
- **Community Forum**: https://community.tradovate.com
- **GitHub Examples**:
  - https://github.com/tradovate/example-api-csharp-trading
  - https://github.com/tradovate/example-api-oauth
  - https://github.com/tradovate/example-api-js
  - https://github.com/tradovate/example-api-trading-strategy

### 2. Community Projects
- **Python Examples**: https://github.com/dearvn/tradovate
- **Python Client**: https://github.com/cullen-b/Tradovate-Python-Client
- **Trading Journal**: https://github.com/hugodemenez/deltalytix

### 3. Community Discussions
- https://community.tradovate.com/t/api-websocket-and-marketdata-websocket/4037
- https://community.tradovate.com/t/how-to-get-real-time-pnl-for-tradovate-account/12383
- https://community.tradovate.com/t/understanding-the-need-to-calculate-account-performance-values/2116

### 4. Code Examples
- https://gist.github.com/Mahdi451/7c94e2b37ecfc9ad037b31035e5e7a1a

---

## Key Findings

### Authentication

**REST API Endpoint:**
- Demo: `https://demo.tradovateapi.com/v1/auth/accesstokenrequest`
- Live: `https://live.tradovateapi.com/v1/auth/accesstokenrequest`

**Request Format:**
```json
{
  "name": "username",
  "password": "password",
  "appId": "Just.Trade",
  "appVersion": "1.0.0",
  "cid": "client_id",  // Optional
  "sec": "client_secret"  // Optional
}
```

**Response Fields:**
- `accessToken` - For REST API and user data WebSocket
- `mdAccessToken` - **CRITICAL** - For market data WebSocket
- `refreshToken` - For token refresh
- `expiresIn` - Token expiration in seconds

**⚠️ CRITICAL**: Must capture `mdAccessToken` during authentication!

---

### WebSocket Connections

#### User Data WebSocket (Positions, Orders, Account)

**URL:**
- Demo: `wss://demo.tradovateapi.com/v1/websocket`
- Live: `wss://live.tradovateapi.com/v1/websocket`

**Authentication Format (CONFLICTING INFORMATION):**

**Option 1 - Newline-delimited (from existing code):**
```
authorize\n0\n\n{ACCESS_TOKEN}
```

**Option 2 - JSON (from search results):**
```json
{
  "authorize": "{ACCESS_TOKEN}"
}
```

**Option 3 - JSON with name/body (from search results):**
```json
{
  "name": "authorize",
  "body": {
    "accessToken": "{ACCESS_TOKEN}"
  }
}
```

**⚠️ NEED TO VERIFY**: Which format actually works?

**Subscription Format (CONFLICTING INFORMATION):**

**Option 1 - Newline-delimited (from existing code):**
```
user/syncRequest\n1\n\n
```

**Option 2 - JSON (from search results):**
```json
{
  "id": 2,
  "method": "subscribe",
  "params": {
    "channel": "user/snapshot",
    "accountId": 123456
  }
}
```

**⚠️ NEED TO VERIFY**: Which format actually works?

**Message Format (from existing code):**
- Socket.IO format: `a[{"e": "props", "d": {...}}]`
- JSON format: `{"e": "props", "d": {"entityType": "Position", "entity": {...}}}`

**Position Update Structure:**
```json
{
  "e": "props",
  "d": {
    "eventType": "Updated",
    "entityType": "Position",
    "entity": {
      "id": 123456,
      "accountId": 789012,
      "contractId": 345678,
      "netPos": 1,
      "netPrice": 24967.75,
      "prevPrice": 24334.0,
      "openPnl": 123.45,  // ⚠️ May or may not be present
      "unrealizedPnl": 123.45  // Alternative field name
    }
  }
}
```

---

#### Market Data WebSocket (Quotes)

**URL:**
- `wss://md.tradovateapi.com/v1/websocket` (same for demo and live)

**Authentication:**
- Use `mdAccessToken` (or `accessToken` as fallback)

**Authentication Format (CONFLICTING INFORMATION):**

**Option 1 - Newline-delimited:**
```
authorize\n1\n\n{MD_ACCESS_TOKEN}
```

**Option 2 - JSON:**
```json
{
  "authorize": "{MD_ACCESS_TOKEN}"
}
```

**⚠️ NEED TO VERIFY**: Which format actually works?

**Subscription Format (CONFLICTING INFORMATION):**

**Option 1 - JSON-RPC:**
```json
{
  "id": 1,
  "method": "subscribeQuote",
  "params": {
    "symbol": "MNQZ1"
  }
}
```

**Option 2 - Newline-delimited:**
```
md/subscribeQuote\n1\n\n{"symbol": "MNQZ1"}
```

**Option 3 - Array format:**
```json
["subscribeQuote", {"symbol": "MNQZ1"}]
```

**⚠️ NEED TO VERIFY**: Which format actually works?

**Quote Message Format (UNKNOWN):**
- Need to verify what fields are in quote messages
- Need to verify how to identify which contract the quote is for

---

## Critical Questions

### 1. WebSocket Authentication
- [ ] What is the EXACT format for user data WebSocket auth?
- [ ] What is the EXACT format for market data WebSocket auth?
- [ ] What ID number should be used (0, 1, or other)?
- [ ] Does it need to be newline-delimited or JSON?

### 2. User Data Subscription
- [ ] What is the EXACT format for `user/syncRequest`?
- [ ] Is it newline-delimited or JSON?
- [ ] What ID number should be used?
- [ ] Are there other subscription methods needed?

### 3. Market Data Subscription
- [ ] What is the EXACT format for quote subscription?
- [ ] Can we subscribe by contract ID or only by symbol?
- [ ] What is the exact method name?
- [ ] What format do quote updates come in?

### 4. Position Updates
- [ ] Does position entity include `openPnl` field?
- [ ] What is the exact field name (`openPnl`, `unrealizedPnl`, `openPnL`)?
- [ ] If not included, how do others calculate it?
- [ ] What format do position updates actually come in?

### 5. P&L Calculation
- [ ] Should we use `openPnl` from WebSocket if available?
- [ ] If calculating manually, what's the exact formula?
- [ ] How to handle contract multipliers?
- [ ] How to handle long vs short positions?

---

## Next Steps

1. **Examine GitHub Repositories**
   - [ ] Read actual code files from dearvn/tradovate
   - [ ] Read actual code files from cullen-b/Tradovate-Python-Client
   - [ ] Read actual code files from tradovate/example-api-csharp-trading
   - [ ] Read actual code files from tradovate/example-api-js

2. **Read Community Forum Posts**
   - [ ] Read full discussion at community.tradovate.com/t/api-websocket-and-marketdata-websocket/4037
   - [ ] Read full discussion at community.tradovate.com/t/how-to-get-real-time-pnl-for-tradovate-account/12383
   - [ ] Extract code snippets from forum posts

3. **Examine Code Examples**
   - [ ] Read gist.github.com/Mahdi451/7c94e2b37ecfc9ad037b31035e5e7a1a
   - [ ] Extract working patterns

4. **Document Verified Patterns**
   - [ ] Create document with EXACT working formats
   - [ ] Include code examples from working implementations
   - [ ] Note any differences between demo and live

5. **Update Test Project**
   - [ ] Update test project with verified formats
   - [ ] Remove conflicting/uncertain code
   - [ ] Add extensive logging to verify what Tradovate actually sends

---

## Notes

- Existing code tries multiple formats (suggests uncertainty about correct format)
- Need to find ONE working example to confirm format
- Community forum posts may have actual code snippets from working implementations
- GitHub repos should have working implementations we can study
- May need to test with real credentials to see what Tradovate actually accepts

---

## Resources to Review Next

1. **GitHub Repository Files**:
   - dearvn/tradovate - Look for websocket.py or similar
   - cullen-b/Tradovate-Python-Client - Look for websocket implementation
   - tradovate/example-api-csharp-trading - Look for WebSocket.cs

2. **Community Forum Posts**:
   - Read full discussions, not just summaries
   - Look for code blocks in forum posts
   - Check for replies with working examples

3. **Gist Code**:
   - Read the full gist code
   - Extract working patterns
   - Note any differences from our implementation

---

## Current Test Project Status

The test project (`test_pnl_tracking.py`) is based on:
- Existing code patterns from `tradovate_integration.py`
- General web search results (may not be accurate)
- Assumptions about message formats

**⚠️ WARNING**: The test project may not work correctly until we verify the exact message formats from working examples.

---

## Research Progress

- [x] Initial web searches
- [x] Found repository links
- [x] Found community forum links
- [x] Found code example links
- [ ] Examined actual code files
- [ ] Read full forum discussions
- [ ] Extracted working patterns
- [ ] Verified message formats
- [ ] Updated test project

