# WebSocket PRD Guide - Position Tracker Implementation

This document is the **official guide** for implementing real-time P&L tracking via Tradovate WebSocket API.

**Source**: Position Tracker PRD (TypeScript/Node.js implementation guide)

---

## Key WebSocket Requirements

### 1. WebSocket Connection
- **Endpoint**: `wss://md.tradovateapi.com/v1/websocket`
- **Purpose**: Real-time market data and order updates
- **Connection Management**: Automatic reconnection with exponential backoff

### 2. Message Parsing
- All incoming messages should be **JSON parsed**
- Route messages to appropriate handlers:
  - **Order updates** → OrderEventHandler
  - **Position updates** → PositionManager
  - **Market data** → Quote handler

### 3. Automatic Reconnection
- On **close** event: Trigger reconnection with exponential backoff
- Track reconnection attempts
- Implement maximum retry limit
- Log all connection lifecycle events

### 4. Error Handling
- **Connection refused**: Handle temporary unavailability
- **Authentication errors**: Validate credentials, handle token refresh
- **Partial messages**: Log and discard or retry parsing carefully
- **Unexpected format**: Log and handle gracefully

### 5. Position Updates
- Update positions on fills, cancellations, rejections, and expirations
- Track net position and average price for P&L calculations
- Handle stop-loss and take-profit order states

### 6. Duplicate Prevention
- Use unique key: `${ordStatus}-${price}-${filledQuantity}-${quantity}`
- Maintain in-memory or Redis-based map of processed states
- Prevent repeated DB writes

### 7. Logging Requirements
- **Connection lifecycle**: Start, end, errors, reconnect attempts
- **Order state changes**: orderId, old status, new status, timestamp
- **Database operations**: Insert/update queries, especially errors
- **Error conditions**: Include stack traces

---

## Implementation Checklist

- [ ] WebSocket connection to `wss://md.tradovateapi.com/v1/websocket`
- [ ] Authentication via `mdAccessToken` or `accessToken`
- [ ] Message parsing (JSON)
- [ ] Automatic reconnection with exponential backoff
- [ ] Position update handling
- [ ] Real-time quote subscription
- [ ] P&L calculation from real-time quotes
- [ ] Error handling and logging
- [ ] Duplicate prevention

---

## Key Insights for Our Implementation

1. **WebSocket URL**: Use `wss://md.tradovateapi.com/v1/websocket` (same for demo and live)
2. **Message Format**: JSON messages that need parsing
3. **Reconnection**: Critical for reliability - implement exponential backoff
4. **Position Updates**: Should come through WebSocket, not just REST API
5. **Real-time Quotes**: Essential for live P&L calculation

---

## Current Issues vs PRD Requirements

### Issue #1: WebSocket Not Connecting
- **PRD Requirement**: Automatic reconnection with exponential backoff
- **Our Status**: Connection fails, no reconnection logic
- **Fix Needed**: Implement proper connection management

### Issue #2: Frozen P&L
- **PRD Requirement**: Real-time position updates and market data
- **Our Status**: Using stale REST API data (`prevPrice`)
- **Fix Needed**: Get WebSocket quotes working for real-time prices

### Issue #3: Duplicate Positions
- **PRD Requirement**: Duplicate prevention with unique keys
- **Our Status**: Same position appears multiple times
- **Fix Needed**: Implement deduplication logic

---

## Reference Implementation Pattern

```typescript
// WebSocket Manager Pattern (from PRD)
export class WebSocketManager {
  private socket?: WebSocket;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  public connect() {
    this.socket = new WebSocket(this.url);
    
    this.socket.on('open', () => {
      logger.info('WebSocket connected.');
      this.reconnectAttempts = 0;
    });

    this.socket.on('message', (data: string) => {
      try {
        const message = JSON.parse(data);
        // Route to handlers
      } catch (err) {
        logger.error('Error parsing WebSocket message', err);
      }
    });

    this.socket.on('error', (err) => {
      logger.error('WebSocket error', err);
    });

    this.socket.on('close', () => {
      logger.warn('WebSocket closed. Attempting reconnect...');
      this.reconnect();
    });
  }

  private reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        logger.info(`Reconnecting... Attempt #${this.reconnectAttempts}`);
        this.connect();
      }, 1000 * this.reconnectAttempts);
    }
  }
}
```

---

## Next Steps

1. **Fix WebSocket Connection**: Implement proper connection management per PRD
2. **Implement Reconnection**: Add exponential backoff logic
3. **Parse Messages**: Handle JSON message parsing correctly
4. **Subscribe to Quotes**: Get real-time market data
5. **Update P&L**: Calculate from real-time quotes, not stale REST data
6. **Deduplicate Positions**: Prevent duplicate position entries

---

**Last Updated**: Based on Position Tracker PRD
**Status**: Reference guide for all WebSocket implementation work

