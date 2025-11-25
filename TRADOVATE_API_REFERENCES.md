# Tradovate API Reference Guide

## Official Resources

### Documentation
- **API Docs**: https://api.tradovate.com/docs
- **Community Forum**: https://community.tradovate.com
- **API Partitioning**: https://community.tradovate.com/t/how-is-the-tradovate-api-partitioned/3183

### GitHub Examples
- **C# Trading Example**: https://github.com/tradovate/example-api-csharp-trading
- **JavaScript OAuth Example**: https://github.com/tradovate/example-api-oauth
- **Python Examples**: https://github.com/dearvn/tradovate

### Key Forum Posts
- **WebSocket and Market Data**: https://community.tradovate.com/t/api-websocket-and-marketdata-websocket/4037
- **WebSocket Authentication**: https://community.tradovate.com/t/ws-authentication/5858
- **User Sync Request**: https://community.tradovate.com/t/search-position-by-symbol/3127/4
- **Long-lived Connections**: https://community.tradovate.com/t/long-lived-websocket-connections/3064

## WebSocket Implementation

### User Data WebSocket (Positions, Orders)
- **URL**: `wss://demo.tradovateapi.com/v1/websocket` (demo) or `wss://live.tradovateapi.com/v1/websocket` (live)
- **Authentication**: Newline-delimited: `authorize\n0\n\n[ACCESS_TOKEN]`
- **Subscription**: `user/syncRequest\n1\n\n`
- **Message Format**: `{"e": "props", "d": {"eventType": "Updated", "entityType": "Position", "entity": {...}}}`
- **Heartbeat**: Send `\n\n` every 2.5 seconds

### Market Data WebSocket (Quotes)
- **URL**: `wss://md.tradovateapi.com/v1/websocket` (same for demo and live)
- **Authentication**: Use `mdAccessToken` (or `accessToken` as fallback)
- **Subscription**: Format varies - check examples
- **Heartbeat**: Send `\n\n` every 2.5 seconds

## Authentication

### Endpoint
- **Demo**: `https://demo.tradovateapi.com/v1/auth/accesstokenrequest`
- **Live**: `https://live.tradovateapi.com/v1/auth/accesstokenrequest`

### Response Fields
- `accessToken`: For REST API and user data WebSocket
- `mdAccessToken`: For market data WebSocket (CRITICAL for real-time quotes)
- `refreshToken`: For token refresh
- `expiresIn`: Token expiration in seconds

### IMPORTANT
- **ALWAYS capture and store `mdAccessToken`** - required for market data WebSocket
- Store in database `md_access_token` column
- Use for market data WebSocket authentication

## Position Data

### REST API Position Fields
- `netPos`: Current position (0 = closed, != 0 = open)
- `netPrice`: Average entry price
- `prevPrice`: **STALE** - snapshot price, doesn't update in real-time
- `openPnl`: **May not be in REST API** - check WebSocket position updates
- `bought`/`sold`: Trade quantities
- `boughtValue`/`soldValue`: Trade values

### WebSocket Position Updates
- Subscribe to `user/syncRequest` for real-time updates
- Events: `{"e": "props", "d": {"entityType": "Position", "entity": {...}}}`
- Entity may contain `openPnl` or `unrealizedPnl` for real-time P&L

## P&L Calculation

### Real-Time P&L Options (in order of preference):
1. **WebSocket position updates with `openPnl`** (best - direct from Tradovate)
2. **WebSocket market data quotes** (good - real-time prices)
3. **REST API `prevPrice`** (worst - STALE, doesn't update)

### Formula
- **Long**: `(current_price - entry_price) * quantity * multiplier`
- **Short**: `(entry_price - current_price) * abs(quantity) * multiplier`
- **Multipliers**: MNQ=$2, MES=$5, NQ=$20, ES=$50 per point

## Common Issues

### P&L Frozen/Static
- **Cause**: Using stale `prevPrice` from REST API
- **Solution**: Use WebSocket quotes or position updates with `openPnl`

### WebSocket Not Connecting
- **Cause**: Missing `mdAccessToken` for market data WebSocket
- **Solution**: Re-authenticate to capture `mdAccessToken`

### No Position Updates
- **Cause**: WebSocket message format incorrect or not subscribed
- **Solution**: Verify subscription format and message parsing

