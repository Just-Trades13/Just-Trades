# Analysis: Position Tracker PRD

## Source
TypeScript/Node.js PRD for Position Tracker microservice

---

## Key Insights from PRD

### 1. WebSocket Connection Pattern
**From PRD:**
```typescript
const wsManager = new WebSocketManager('wss://md.tradovateapi.com/v1/websocket');
```

**What This Tells Us:**
- ✅ Confirms market data WebSocket URL: `wss://md.tradovateapi.com/v1/websocket`
- ⚠️ This PRD only uses market data WebSocket
- ❓ Doesn't show user data WebSocket (for positions)

**Our Implementation:**
- We need BOTH WebSockets (market data + user data)
- Market data for quotes
- User data for position updates

---

### 2. Message Parsing
**From PRD:**
```typescript
this.socket.on('message', (data: string) => {
  try {
    const message = JSON.parse(data);
    // Dispatch to event handler
  } catch (err) {
    logger.error('Error parsing WebSocket message', err);
  }
});
```

**What This Tells Us:**
- ✅ Messages come as JSON strings (not newline-delimited)
- ✅ Need to parse JSON
- ✅ Handle parsing errors

**Our Implementation:**
- We handle both Socket.IO format (`a[{...}]`) and JSON
- This PRD suggests JSON is the primary format
- May need to adjust our parsing

---

### 3. Order State Transitions
**From PRD:**
- States: `Working`, `Filled`, `Canceled`, `Rejected`, `Expired`
- Market orders may skip from `PendingNew` to `Filled`
- Need duplicate prevention

**What This Tells Us:**
- Order updates come through WebSocket
- Need to track state transitions
- Position updates happen on `Filled` orders

**Our Implementation:**
- We're tracking positions, not individual orders
- But this shows how order updates work

---

### 4. Position Updates
**From PRD:**
```typescript
// Only update positions on Filled
if (orderDetails.ordStatus !== 'Filled') return;

const quantityChange = orderDetails.side === 'Buy'
  ? orderDetails.filledQuantity
  : -1 * (orderDetails.filledQuantity || 0);
```

**What This Tells Us:**
- Positions update on `Filled` orders
- Calculate net position from fills
- Track average price for P&L

**Our Implementation:**
- We get positions from REST API
- We get position updates from WebSocket
- This PRD calculates positions from order fills (different approach)

---

### 5. WebSocket Reconnection
**From PRD:**
```typescript
private reconnect() {
  if (this.reconnectAttempts < this.maxReconnectAttempts) {
    this.reconnectAttempts++;
    setTimeout(() => {
      logger.info(`Reconnecting... Attempt #${this.reconnectAttempts}`);
      this.connect();
    }, 1000 * this.reconnectAttempts); // Exponential backoff
  }
}
```

**What This Tells Us:**
- ✅ Need automatic reconnection
- ✅ Exponential backoff
- ✅ Max retry limit

**Our Implementation:**
- We have heartbeat, but may need better reconnection logic

---

## Differences from Our Use Case

### PRD Focus
- **Order tracking** - Track every order state transition
- **Position calculation** - Calculate positions from order fills
- **Database persistence** - Store all trades and positions

### Our Focus
- **Real-time P&L** - Show current P&L for open positions
- **Position updates** - Get positions from REST API and WebSocket
- **Quote updates** - Get real-time prices for P&L calculation

---

## What We Can Learn

### 1. WebSocket Message Format
**From PRD:**
- Messages are JSON strings
- Parse with `JSON.parse(data)`
- Handle parsing errors

**Our Implementation:**
- We handle Socket.IO format (`a[{...}]`) and JSON
- May need to simplify if JSON is primary format

---

### 2. Connection Management
**From PRD:**
- Automatic reconnection with exponential backoff
- Max retry limit
- Logging for connection lifecycle

**Our Implementation:**
- We have basic connection, but could improve reconnection logic

---

### 3. Error Handling
**From PRD:**
- Validate mandatory fields
- Skip invalid messages
- Log errors with context

**Our Implementation:**
- We have basic error handling
- Could add more validation

---

## What's Missing from PRD

### 1. User Data WebSocket
**PRD only shows:**
- Market data WebSocket (`wss://md.tradovateapi.com/v1/websocket`)

**We need:**
- User data WebSocket (`wss://demo.tradovateapi.com/v1/websocket`)
- For position updates (not just order fills)

---

### 2. Authentication Format
**PRD doesn't show:**
- How to authenticate WebSocket
- Token format
- Authorization message

**We need:**
- Authentication format (newline-delimited or JSON?)
- Using `accessToken` or `mdAccessToken`

---

### 3. Subscription Format
**PRD doesn't show:**
- How to subscribe to data
- Subscription message format
- What to subscribe to

**We need:**
- Subscription format for positions
- Subscription format for quotes

---

### 4. Position Updates Format
**PRD shows:**
- Calculating positions from order fills

**We need:**
- Position updates from WebSocket (entityType: "Position")
- Does it include `openPnl`?

---

## Key Takeaways

### ✅ Confirmed
1. WebSocket messages are JSON (primary format)
2. Need automatic reconnection
3. Need error handling and validation
4. Market data WebSocket URL is correct

### ⚠️ Still Unknown
1. User data WebSocket authentication format
2. Subscription format for positions
3. Position update message format
4. Does position entity include `openPnl`?

### 🔍 What to Test
1. Are messages JSON or Socket.IO format?
2. What's the exact authentication format?
3. What's the subscription format?
4. What fields are in position updates?

---

## Updated Understanding

### WebSocket Messages
**Likely Format:**
- JSON strings (not newline-delimited for messages)
- Parse with `JSON.parse()`
- Handle both formats (Socket.IO and JSON) for compatibility

### Connection Management
- Need robust reconnection logic
- Exponential backoff
- Max retry limit

### Position Updates
- May come as JSON messages
- Need to parse and extract position data
- May or may not include `openPnl`

---

## Action Items

1. **Update Test Project**
   - Simplify message parsing (focus on JSON)
   - Add better reconnection logic
   - Add more validation

2. **Test to Verify**
   - What format do messages actually come in?
   - What's the authentication format?
   - What's the subscription format?

3. **Compare Approaches**
   - PRD calculates positions from order fills
   - We get positions from REST API and WebSocket
   - Both approaches may be valid

---

## Summary

**What PRD Confirms:**
- ✅ WebSocket connection pattern
- ✅ JSON message parsing
- ✅ Reconnection logic
- ✅ Error handling approach

**What PRD Doesn't Show:**
- ❌ User data WebSocket
- ❌ Authentication format
- ❌ Subscription format
- ❌ Position update format

**What We Still Need:**
- Test to see actual message formats
- Verify authentication format
- Verify subscription format
- See if `openPnl` exists in position updates

