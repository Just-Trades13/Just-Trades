# 🚀 Scalable Multi-Account Trading Architecture

## Overview

This architecture is designed to handle **50-1000+ accounts** without rate limiting issues, following the same patterns used by TradersPost and TradeManager.

---

## Key Design Principles

### 1. OAuth-First Authentication (Like TradersPost)

```
PRIORITY ORDER:
1. Token Cache     → Instant, no API call
2. OAuth Token     → From DB, no rate limit, no captcha
3. API Access      → LAST RESORT only (triggers captcha)
```

**Why OAuth First:**
- OAuth tokens obtained via browser flow never trigger captcha
- No authentication rate limiting on trade execution
- Works with ALL accounts including prop accounts
- This is exactly how TradersPost/TradeManager work

### 2. Batch Processing

```
Accounts: 100
Batch Size: 25
Batches: 4

Batch 1: Accounts 1-25   → Execute in parallel
[0.5s delay]
Batch 2: Accounts 26-50  → Execute in parallel
[0.5s delay]
Batch 3: Accounts 51-75  → Execute in parallel
[0.5s delay]
Batch 4: Accounts 76-100 → Execute in parallel
```

**Configuration:**
```python
BATCH_SIZE = 25                    # Accounts per batch
BATCH_DELAY_SECONDS = 0.5          # Delay between batches
MAX_CONCURRENT_CONNECTIONS = 50    # Max WebSocket connections
API_CALLS_PER_MINUTE_LIMIT = 70    # Under 80/min limit
```

### 3. Rate Limit Tracking

Tradovate limits: **80 requests/minute**, **5,000 requests/hour**

Our system tracks API calls and waits if approaching limits:
- Records timestamp of each API call
- Checks against 70 calls/minute threshold (10 buffer)
- Pauses execution if limit approached

### 4. WebSocket Connection Pooling

Persistent WebSocket connections reduce overhead:
- Connections are reused across trades
- Pool maintains active connections per account
- Automatic cleanup of dead connections

### 5. Proactive Token Refresh

Background daemon refreshes tokens before expiry:
- Checks tokens every 5 minutes
- Refreshes if expiring within 30 minutes
- Uses refresh token (OAuth) first
- Falls back to API Access only if needed

---

## Trade Execution Flow

```
WEBHOOK RECEIVED
      ↓
┌─────────────────────────────────┐
│  Get all linked accounts (N)    │
└─────────────────────────────────┘
      ↓
┌─────────────────────────────────┐
│  Split into batches of 25       │
│  (e.g., 100 accounts = 4 batches)│
└─────────────────────────────────┘
      ↓
FOR EACH BATCH:
┌─────────────────────────────────┐
│  For each account in parallel:  │
│  1. Get cached/OAuth token      │
│  2. Get pooled WS connection    │
│  3. Place bracket order (WS)    │
│  4. Record API call             │
└─────────────────────────────────┘
      ↓
┌─────────────────────────────────┐
│  Wait 0.5s between batches      │
│  (allows rate limit recovery)   │
└─────────────────────────────────┘
      ↓
COMPLETE - All accounts traded
```

---

## Capacity Estimates

| Accounts | Batches | Execution Time | API Calls/Trade |
|----------|---------|----------------|-----------------|
| 25       | 1       | ~2 seconds     | ~50             |
| 50       | 2       | ~4 seconds     | ~100            |
| 100      | 4       | ~8 seconds     | ~200            |
| 250      | 10      | ~20 seconds    | ~500            |
| 500      | 20      | ~40 seconds    | ~1000           |
| 1000     | 40      | ~80 seconds    | ~2000           |

**Rate limit safety:** Even at 1000 accounts, we're well under the 5,000/hour limit.

---

## Requirements for Each Account

For optimal performance, each account should have:

1. **OAuth Token** (REQUIRED for scale)
   - User authorizes via browser once
   - System stores access + refresh tokens
   - Auto-refreshes before expiry

2. **Username/Password** (BACKUP only)
   - Used if OAuth refresh fails
   - May trigger captcha on first use
   - Not needed if OAuth tokens are fresh

---

## How to Add Accounts at Scale

### For Users (Self-Service OAuth):
1. Go to Account Management
2. Click "Connect Tradovate" for each account
3. Complete OAuth flow in browser
4. Done - account is ready for trading

### For Operators (Bulk):
1. Have users complete OAuth once
2. Tokens are stored automatically
3. System handles all refreshes

---

## Comparison to TradersPost/TradeManager

| Feature | TradersPost | TradeManager | Our System |
|---------|-------------|--------------|------------|
| Auth Method | OAuth | OAuth | OAuth-first |
| Rate Limit Handling | Unknown | Unknown | Batch + Track |
| Connection Reuse | Yes | Yes | WebSocket Pool |
| Token Refresh | Auto | Auto | Background Daemon |
| Prop Account Support | Yes | Yes | Yes (via OAuth) |

---

---

## Critical Bug Fixes Included

### Cross-Account TP Order Bug (Fixed Dec 18, 2025)

**Problem:** When `/account/{id}/orders` returned empty, the fallback `/order/list` returned orders from ALL accounts. The TP detection found orders from the WRONG account!

**Symptom:**
```
APEX4144400000005 → MODIFYING TP 351658970532  (wrong!)
APEX4144400000004 → MODIFYING TP 351658970532  (wrong!)
APEX4144400000003 → MODIFYING TP 351658970532  (correct - its own)
```

**Fix:** Filter orders by accountId in two places:
1. `tradovate_integration.py` - Filter fallback results
2. `recorder_service.py` - Defensive check when searching

---

## Troubleshooting

### "Account needs re-authorization"
- OAuth token expired and refresh failed
- Solution: User re-completes OAuth flow

### "Rate limit exceeded"
- Too many API calls too fast
- Solution: System auto-waits; no action needed

### "Captcha required"
- API Access triggered device verification
- Solution: Use OAuth instead (automatic with this architecture)

### "No token available"
- Account never completed OAuth
- Solution: Have user authorize via Account Management

---

## Configuration Reference

Location: `recorder_service.py` (top of file)

```python
# Scalability config
BATCH_SIZE = 25                    # Adjust based on testing
BATCH_DELAY_SECONDS = 0.5          # Increase if seeing rate limits
MAX_CONCURRENT_CONNECTIONS = 50    # Max simultaneous WS connections
API_CALLS_PER_MINUTE_LIMIT = 70    # Stay under 80/min

# Token refresh config
TOKEN_REFRESH_INTERVAL = 300       # Check every 5 minutes
TOKEN_REFRESH_THRESHOLD = 30       # Refresh if expires within 30 min
```

---

## Summary

This architecture handles 50-1000+ accounts by:
1. ✅ Using OAuth tokens (no captcha, no auth rate limits)
2. ✅ Processing in batches (prevents overwhelming API)
3. ✅ Tracking rate limits (stays under 80/min)
4. ✅ Pooling WebSocket connections (reduces overhead)
5. ✅ Auto-refreshing tokens (never expires during trading)

**Bottom line:** Just like TradersPost and TradeManager, we use OAuth for authentication and smart batching for execution.
