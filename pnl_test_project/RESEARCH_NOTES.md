# Tradovate P&L Tracking Research Notes

## Research Status: IN PROGRESS

This document tracks research findings from actual working examples and community discussions.

## Key Findings So Far

### 1. WebSocket Authentication Format
**Found in search results:**
- Format: `authorize\n1\n\n{TOKEN}` (newline-delimited)
- Alternative: JSON format `{"authorize": TOKEN}`
- **Need to verify**: Which format actually works?

### 2. Market Data Subscription
**Found examples:**
```json
{
  "id": 1,
  "method": "subscribeQuote",
  "params": {
    "symbol": "MNQZ1"
  }
}
```

**Also found:**
- Newline-delimited: `md/subscribeQuote\n1\n\n{JSON}`
- **Need to verify**: Which format works?

### 3. User Data Subscription
**From existing code:**
- Format: `user/syncRequest\n1\n\n` (newline-delimited)
- **Status**: Used in existing code, but not verified from external examples

### 4. Position Updates Format
**From existing code:**
- Socket.IO format: `a[{"e": "props", "d": {...}}]`
- JSON format: `{"e": "props", "d": {"entityType": "Position", "entity": {...}}}`
- **Need to verify**: What format does Tradovate actually send?

## Repositories to Examine

1. **github.com/dearvn/tradovate** - Python examples
   - Status: Found repository, need to examine actual code files
   
2. **github.com/cullen-b/Tradovate-Python-Client** - Python client library
   - Status: Need to examine WebSocket implementation
   
3. **github.com/tradovate/example-api-csharp-trading** - Official C# example
   - Status: Need to examine WebSocket code
   
4. **github.com/tradovate/example-api-js** - Official JavaScript example
   - Status: Need to examine WebSocket code

## Community Forum Posts to Review

1. **community.tradovate.com/t/api-websocket-and-marketdata-websocket/4037**
   - Status: Need to read actual discussion
   
2. **community.tradovate.com/t/how-to-get-real-time-pnl-for-tradovate-account/12383**
   - Status: Need to read actual discussion

## Critical Questions to Answer

1. **What is the EXACT format for WebSocket authorization?**
   - Newline-delimited: `authorize\n0\n\n{TOKEN}` or `authorize\n1\n\n{TOKEN}`?
   - JSON: `{"authorize": TOKEN}`?
   - Which ID number (0, 1, or other)?

2. **What is the EXACT format for market data subscription?**
   - JSON-RPC: `{"id": 1, "method": "subscribeQuote", "params": {...}}`?
   - Newline-delimited: `md/subscribeQuote\n1\n\n{JSON}`?
   - Array format: `["subscribeQuote", {...}]`?

3. **What is the EXACT format for user data subscription?**
   - Newline-delimited: `user/syncRequest\n1\n\n`?
   - JSON format?
   - What ID number?

4. **What format do position updates actually come in?**
   - Socket.IO: `a[{...}]`?
   - JSON: `{"e": "props", "d": {...}}`?
   - Newline-delimited?

5. **Does position entity include `openPnl` field?**
   - If yes, what's the exact field name?
   - If no, how do others calculate it?

6. **What format do market data quotes come in?**
   - What fields are in the quote message?
   - How to identify which contract the quote is for?

## Next Steps

1. ✅ Search for GitHub repositories
2. ⏳ Examine actual code files from repositories
3. ⏳ Read community forum discussions in detail
4. ⏳ Document exact message formats from working examples
5. ⏳ Update test project with verified formats
6. ⏳ Test with real credentials

## Notes

- Existing code tries multiple formats (suggests uncertainty)
- Need to find ONE working example to confirm format
- Community forum posts may have actual code snippets
- GitHub repos should have working implementations

