# Trade Manager Architecture Database
## Complete System Documentation for Replication

**Date Created:** December 2024  
**Purpose:** Comprehensive reference for replicating Trade Manager system  
**Last Updated:** 2025-01-XX (Updating with verified Tradovate API documentation)

---

## 📊 Implementation Progress Tracker

**Last Updated:** 2025-01-XX

### ✅ Completed & Verified
- [x] Tradovate API documentation obtained (official docs)
- [x] Authentication flow documented (username/password with OAuth credentials)
- [x] Base URL structure confirmed (live.tradovateapi.com, demo.tradovateapi.com)
- [x] Account management endpoints identified
- [x] Position polling endpoints identified
- [x] Order execution endpoints identified

### 🔄 In Progress
- [ ] Refresh token endpoint verification (docs show `GET /renewAccessToken`, code uses `POST /auth/refresh-token`)
- [ ] Endpoint path verification (docs vs actual implementation)
- [ ] Request/response format validation
- [ ] Full authentication flow testing

### ❌ Not Started
- [ ] Position Recorder service implementation
- [ ] Discord bot integration
- [ ] Real-time dashboard updates
- [ ] Strategy matching algorithm
- [ ] Complete end-to-end testing

### 📝 Notes & Discoveries
- **2025-01-XX**: Official Tradovate API docs obtained - contains exact endpoint specifications
- **2025-01-XX**: Need to verify if endpoint paths include `/auth/` prefix or not
- **2025-01-XX**: Refresh token endpoint likely needs correction (GET vs POST)
- **2025-01-XX**: API docs show relaxed REST API - supports GET/POST, JSON responses

---

## Table of Contents

1. [System Overview](#system-overview)
2. [User Authentication & Sessions](#user-authentication--sessions)
3. [Tradovate Integration](#tradovate-integration)
4. [Discord Integration](#discord-integration)
5. [Recorder System](#recorder-system)
6. [Dashboard & Analytics](#dashboard--analytics)
7. [Database Schema](#database-schema)
8. [API Endpoints & Flows](#api-endpoints--flows)
9. [TradingView Integration](#tradingview-integration)
10. [Missing Components & Implementation Guide](#missing-components--implementation-guide)

---

## System Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     TRADE MANAGER ARCHITECTURE                  │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Frontend   │───▶│   Backend    │───▶│  Database    │
│  (React)     │    │  (Flask)     │    │  (SQLite/    │
│              │    │              │    │   Postgres)  │
└──────────────┘    └──────────────┘    └──────────────┘
       │                   │                     │
       │                   │                     │
       ▼                   ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Discord Bot │    │  Recorder    │    │   Analytics  │
│              │    │   Service    │    │   Engine     │
└──────────────┘    └──────────────┘    └──────────────┘
       │                   │                     │
       │                   ▼                     │
       │            ┌──────────────┐            │
       │            │  Tradovate   │            │
       │            │     API      │            │
       │            └──────────────┘            │
       │                                         │
       └─────────────────────────────────────────┘
                   ┌──────────────┐
                   │ TradingView  │
                   │   Webhooks   │
                   └──────────────┘
```

### Key Features

1. **Strategy Recording**: Tracks demo account positions for strategy performance
2. **Discord Notifications**: Private DM updates on strategy status
3. **Dashboard Analytics**: Real-time performance metrics and position tracking
4. **Multi-Account Support**: Live and demo Tradovate accounts
5. **Strategy Management**: Create, edit, monitor trading strategies

---

## User Authentication & Sessions

### Session Management

**Trade Manager Web Sessions:**
- **Framework**: Flask sessions with CSRF protection
- **CSRF Token Endpoint**: `/api/system/csrf-token/`
- **Auth Check Endpoint**: `/api/auth/check-auth/`
- **Session Cookies**: `csrftoken`, `sessionid`

**Session Flow:**
```
1. User visits site → Get CSRF token
2. User logs in → Session created
3. All API calls include:
   - Header: X-CSRFToken: <token>
   - Cookie: csrftoken=<token>; sessionid=<session_id>
```

### User Account Structure

**Database Fields:**
- User ID
- Discord User ID (linked via OAuth)
- Discord DMs enabled (boolean)
- Session ID
- Created/Updated timestamps

**Authentication Headers:**
```python
headers = {
    "Content-Type": "application/json",
    "X-CSRFToken": self.csrf_token,
    "Cookie": f"csrftoken={self.csrf_token}; sessionid={self.session_id}"
}
```

---

## Tradovate Integration

### ⚠️ Status: Updating with Official API Documentation

**Last Verified:** 2025-01-XX  
**Source:** Official Tradovate API Documentation

### OAuth App Registration

**Process:**
1. User registers OAuth app in Tradovate account
   - Navigate to: Application Settings → API Access → OAuth Registration
   - App Title: User's app name (e.g., "Just.Trade")
   - Redirect URI: `http://localhost:8082` (or production URL)
   - Permissions: Account access, trading

2. Generate Credentials
   - Client ID (CID): Generated once, shown only once
   - Client Secret (SEC): Same as CID or separate
   - **CRITICAL**: Save immediately, cannot be retrieved later

3. Store in Database
   - User enters Client ID and Secret in account settings
   - Stored encrypted in `accounts` table

### API Server URLs (Verified from Official Docs)

**Live Environment:**
- Base URL: `https://live.tradovateapi.com/v1` ✅ VERIFIED
- Market Data WebSocket: `wss://md.tradovate.com/v1/websocket`

**Demo Environment:**
- Base URL: `https://demo.tradovateapi.com/v1` ✅ VERIFIED
- Market Data WebSocket: `wss://md.tradovate.com/v1/websocket`

**Note:** Official docs also mention `api.tradovate.com` - need to verify which is correct

### Authentication Endpoints (From Official API Docs)

**Access Token Request:**
- **Endpoint:** `POST /accessTokenRequest` (Note: may need `/auth/` prefix - needs verification)
- **Purpose:** Get access token using username/password
- **Status:** 🔄 NEEDS VERIFICATION - Current code uses `/auth/accesstokenrequest`

**OAuth Token:**
- **Endpoint:** `POST /oAuthToken` (for OAuth flow)
- **Purpose:** OAuth-based authentication
- **Status:** ❌ NOT IMPLEMENTED

**Renew Access Token:**
- **Endpoint:** `GET /renewAccessToken` ✅ FROM OFFICIAL DOCS
- **Purpose:** Refresh expired access token using refresh token
- **Status:** ⚠️ CURRENT CODE USES `POST /auth/refresh-token` - NEEDS FIXING
- **Note:** Official docs show **GET** method, our code uses **POST**

**Get User Info:**
- **Endpoint:** `GET /me`
- **Purpose:** Get authenticated user information
- **Status:** ❌ NOT IMPLEMENTED

### Login Request Format

**With Client Credentials (OAuth):**
```json
{
    "name": "username",
    "password": "password",
    "appId": "Just.Trade",
    "appVersion": "1.0.0",
    "cid": "client_id",
    "sec": "client_secret"
}
```

**Without Client Credentials (Username/Password only):**
```json
{
    "name": "username",
    "password": "password",
    "appId": "Tradovate",
    "appVersion": "1.0.0",
    "deviceId": "uuid-string"
}
```

**Response Format:**
```json
{
    "accessToken": "string",
    "refreshToken": "string",
    "expiresIn": 86400,
    "userId": 12345
}
```

### Token Management

**Access Token:**
- Expires: ~24 hours (86400 seconds)
- Stored in: `accounts.tradovate_token`
- Used for: API requests (Authorization: Bearer <token>)
- Header format: `Authorization: Bearer {accessToken}`

**Refresh Token:**
- Stored in: `accounts.tradovate_refresh_token` (encrypted)
- Used for: Getting new access tokens
- Expiration: Longer-lived than access token
- **CRITICAL FIX NEEDED:** Refresh endpoint should be `GET /renewAccessToken`, not `POST /auth/refresh-token`

**Token Refresh Flow (CORRECTED):**
```python
1. Check token_expires_at
2. If expired → GET /renewAccessToken (with refreshToken in query/body)
3. Update access_token and refresh_token
4. Save to database
```

**Current Implementation Issue:**
- ❌ Code uses: `POST /auth/refresh-token`
- ✅ Should use: `GET /renewAccessToken` (per official docs)
- 🔄 **ACTION REQUIRED:** Fix refresh token endpoint in `tradovate_integration.py` line 214

### Complete Tradovate API Endpoints (From Official Docs)

**Authentication Endpoints:**
- `POST /accessTokenRequest` - Get access token (username/password)
- `POST /oAuthToken` - OAuth token flow
- `GET /renewAccessToken` - Refresh access token ✅ VERIFIED
- `GET /me` - Get authenticated user info

**Account Endpoints:**
- `GET /account/list` - List all accounts ✅ VERIFIED (in code)
- `GET /account/{id}` - Get account details ✅ VERIFIED (in code)
- `GET /account/{id}/subaccounts` - Get subaccounts ✅ VERIFIED (in code)
- `GET /account/listitem` - Account list items (for Recorder)

**Position Endpoints (For Recorder System):**
- `GET /position/list` - List all open positions ✅ NEEDED FOR RECORDER
- `GET /position/find` - Find specific positions ✅ NEEDED FOR RECORDER
- **Status:** ⚠️ Partially implemented in `tradovate_integration.py` - needs verification

**Order Endpoints:**
- `POST /order/placeOrder` - Place new order ✅ VERIFIED (in code as `/order/place-order`)
- `GET /order/list` - List orders ✅ NEEDED FOR RECORDER
- `GET /order/find` - Find specific orders ✅ NEEDED FOR RECORDER
- `GET /order/fill` - Get filled orders ✅ NEEDED FOR RECORDER
- **Status:** ⚠️ Order placement implemented, but endpoint path may need verification

**Market Data (WebSocket):**
- `wss://md.tradovate.com/v1/websocket` - Market data WebSocket
- **Status:** ⚠️ WebSocket code exists but needs verification

**Implementation Status:**
- ✅ Account listing: Implemented
- ✅ Position polling: Partially implemented (`get_positions()` exists)
- ✅ Order placement: Implemented (`place_order()` exists)
- ❌ Order querying: Not implemented (needed for Recorder)
- ❌ Filled orders: Not implemented (needed for Recorder)
- 🔄 Endpoint paths: Need verification against official docs

### Trade Manager's Secret

**Key Insight:**
- Trade Manager has ONE pre-registered OAuth app
- Uses their Client ID/Secret for ALL users
- Users provide Tradovate credentials
- Trade Manager authenticates on their behalf
- **This is why they can connect instantly**

**Our Implementation:**
- Each user registers their own OAuth app
- User provides credentials AND OAuth credentials
- More secure but requires setup

---

## Discord Integration

### OAuth Connection

**Discord OAuth App:**
- Client ID: `1128079426891042827`
- Redirect URI: `https://trademanagergroup.com/oauth/discord/callback/`
- Scope: `identify` (minimum), possibly `dm` for sending messages
- Authorization URL: `https://discord.com/oauth2/authorize?client_id=1128079426891042827&response_type=code&redirect_uri=https%3A%2F%2Ftrademanagergroup.com%2Foauth%2Fdiscord%2Fcallback%2F&scope=identify`

**OAuth Flow:**
```
1. User clicks "Link Discord" in Settings
2. Redirect to Discord OAuth
3. User authorizes
4. Callback receives code
5. Exchange code for access token
6. Store Discord User ID in database
7. Optionally store access token for DM sending
```

### Discord Bot Setup

**Bot Token:**
- Required for sending DMs
- Create bot in Discord Developer Portal
- Bot permissions: Send Messages, Read Message History

**DM Sending:**
```python
# Discord.py example
import discord

bot = discord.Client()

@bot.event
async def on_ready():
    user = await bot.fetch_user(discord_user_id)
    await user.send("Strategy JADNQ: Position opened - Long 1 ES @ 4200.00")
```

### Notification Types

**Strategy Status Updates:**
1. **Position Opened**
   - Message: `"Strategy {name}: Position opened - {side} {qty} {symbol} @ {price}"`

2. **Position Closed**
   - Message: `"Strategy {name}: Position closed - P&L: ${pnl}"`

3. **Stop Loss Hit**
   - Message: `"Strategy {name}: Stop loss triggered @ {price} - Loss: ${loss}"`

4. **Take Profit Hit**
   - Message: `"Strategy {name}: Take profit hit @ {price} - Profit: ${profit}"`

5. **Strategy Performance**
   - Daily/weekly summary of all strategies

**User Settings:**
- Enable/Disable Discord DMs (stored in user settings)
- Settings endpoint: `/api/user/settings` (inferred)

### Discord Integration Code Structure

**Needed Components:**
```python
# discord_bot.py
class DiscordNotificationService:
    def __init__(self, bot_token):
        self.bot = discord.Client()
        self.bot_token = bot_token
    
    async def send_strategy_update(self, discord_user_id, message):
        """Send DM to user about strategy update"""
        pass
    
    async def send_position_opened(self, discord_user_id, strategy, position):
        """Notify user of new position"""
        pass
    
    async def send_position_closed(self, discord_user_id, strategy, position, pnl):
        """Notify user of closed position with P&L"""
        pass
```

---

## Recorder System

### Purpose

The Recorder tracks demo account positions and matches them to strategies for performance analytics.

### Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    RECORDER WORKFLOW                        │
└─────────────────────────────────────────────────────────────┘

1. User creates strategy in "My Recorders"
   - Strategy Name (e.g., "JADNQ")
   - Position Size, Take Profit, Stop Loss
   - Linked to demo account

2. Strategy runs on demo account
   - TradingView alerts → Webhook → Tradovate API
   - Positions opened in demo account

3. Recorder Service (Background Worker)
   - Polls Tradovate API every X minutes (e.g., 1-5 min)
   - Gets all open positions from demo account
   - Gets all filled orders
   - Matches to strategies by:
     * Symbol
     * Strategy name (from TradingView alert)
     * Time window

4. Record Position Data
   - Entry price, quantity, side
   - Stop loss, take profit levels
   - Entry timestamp
   - Strategy ID

5. Monitor Position Changes
   - Position closed → Record exit price, P&L
   - Stop loss hit → Record as stopped out
   - Take profit hit → Record as target hit
   - Partial exit → Record remaining quantity

6. Update Dashboard
   - Real-time position updates
   - P&L calculations
   - Performance metrics

7. Send Discord Notifications
   - On position opened
   - On position closed
   - On stop loss/take profit hit
```

### Position Matching Logic

**Matching Strategy:**
```python
def match_position_to_strategy(position, strategies):
    """
    Match Tradovate position to user strategy
    
    Criteria:
    1. Symbol matches (e.g., "ES" or "NQ")
    2. Strategy name in order comment/notes (if available)
    3. Time window (position opened within last hour of strategy signal)
    4. Account matches strategy's demo account
    """
    for strategy in strategies:
        if position.symbol == strategy.symbol:
            if position.account_id == strategy.account_id:
                if is_within_time_window(position.timestamp, strategy.last_signal):
                    return strategy
    return None
```

### Recorder Service Implementation

**Background Worker (Celery/APScheduler):**
```python
# recorder_service.py
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tradovate_integration import TradovateIntegration

class PositionRecorder:
    def __init__(self, db_path):
        self.db_path = db_path
        self.scheduler = AsyncIOScheduler()
        self.active_recordings = {}  # strategy_id -> recording_state
    
    async def start_recording(self, strategy_id, account_id):
        """Start recording positions for a strategy"""
        pass
    
    async def poll_positions(self, account_id):
        """Poll Tradovate for current positions"""
        async with TradovateIntegration(demo=True) as tradovate:
            # Get account positions
            positions = await tradovate.get_positions(account_id)
            
            # Get filled orders
            orders = await tradovate.get_filled_orders(account_id)
            
            return positions, orders
    
    async def record_position(self, position, strategy_id):
        """Record position to database"""
        # Insert into recorded_positions table
        pass
    
    async def update_position_status(self, position_id, status, exit_price, pnl):
        """Update position when closed/stopped out"""
        pass
```

**Scheduled Task:**
```python
# Run every 1-5 minutes
@scheduler.scheduled_job('interval', minutes=1)
async def record_all_strategies():
    """Poll all active strategies and record positions"""
    strategies = get_active_strategies()
    for strategy in strategies:
        positions, orders = await poll_positions(strategy.account_id)
        match_and_record(positions, orders, strategy)
```

### Tradovate API Endpoints Needed (For Recorder System)

**Get Positions:**
- Endpoint: `GET /position/list` ✅ FROM OFFICIAL DOCS
- Returns: List of open positions
- Fields: symbol, quantity, side, entryPrice, unrealizedPnL
- **Status:** ✅ Partially implemented in `tradovate_integration.py` (`get_positions()` method exists)
- **Action:** Verify endpoint path and response format

**Get Orders:**
- Endpoint: `GET /order/list` or `GET /order/find` ✅ FROM OFFICIAL DOCS
- Filters: Filled orders, date range
- Fields: symbol, quantity, side, fillPrice, fillTime, orderId
- **Status:** ❌ NOT IMPLEMENTED - Need to add `get_orders()` and `get_filled_orders()` methods
- **Action:** Implement order querying methods

**Get Filled Orders (Specific for Recorder):**
- Endpoint: `GET /order/fill` ✅ FROM OFFICIAL DOCS
- Purpose: Get completed/filled orders for position matching
- **Status:** ❌ NOT IMPLEMENTED
- **Action:** Implement `get_filled_orders()` method

**Get Account Info:**
- Endpoint: `GET /account/listitem` or `GET /account/{id}`
- Returns: Account details including demo/live status
- **Status:** ✅ Implemented (`get_account_info()` exists)
- **Action:** Verify which endpoint returns the needed account status info

---

## Dashboard & Analytics

### Dashboard Structure

**Main Dashboard:**
- URL: `/user/dashboard`
- Filter: "VIEWING RECORDED STRATS"
- Filters: User, Strategy, Date Range

**My Recorders Tab:**
- URL: `/user/strats`
- Lists all strategies
- Create Strategy button
- Edit/Refresh/Remove actions
- Strategy details:
  - Strategy Name
  - Position Size
  - Position Add
  - Take Profit
  - Stop Loss
  - TPSL Units (Ticks/Percent)
  - Logs section

### Analytics Metrics

**Per Strategy:**
- Total Trades
- Win Rate (%)
- Average Win
- Average Loss
- Largest Win
- Largest Loss
- Total P&L
- Profit Factor
- Max Drawdown
- Sharpe Ratio

**Position Tracking:**
- Current Open Positions
- Entry Price
- Current Price
- Unrealized P&L
- Time in Trade
- Distance to Stop Loss
- Distance to Take Profit

**Time-based Analytics:**
- Daily P&L
- Weekly P&L
- Monthly P&L
- Trade frequency
- Best/worst days

### Dashboard Data Flow

```
Recorder Service → Database → Dashboard API → React Frontend
                                      ↓
                              Real-time Updates (WebSocket)
```

**API Endpoints (Inferred):**
- `GET /api/strategies` - List all strategies
- `GET /api/strategies/{id}/positions` - Get recorded positions
- `GET /api/strategies/{id}/analytics` - Get performance metrics
- `GET /api/dashboard/summary` - Dashboard overview
- `WS /ws/dashboard` - WebSocket for real-time updates

---

## Database Schema

### Current Implementation Status

**✅ Already Implemented:**
- `accounts` table (with Tradovate token fields)
- `strategies` table (basic structure)
- `trades` table (trade execution logging)
- `webhook_logs` table

**❌ Missing Tables (Required for Full System):**
- `users` table (user authentication, Discord integration)
- `recorded_positions` table (separate from trades - for demo position tracking)
- `strategy_logs` table (strategy-specific event logs)

**⚠️ Missing Fields in Existing Tables:**
- `strategies.symbol` (needed for position matching)
- `strategies.demo_account_id` (link to demo account for recording)
- `strategies.recording_enabled` (toggle recording on/off)
- `accounts.client_id` and `accounts.client_secret` (OAuth credentials)

### Accounts Table

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    broker TEXT NOT NULL,  -- "Tradovate"
    auth_type TEXT NOT NULL,  -- "credentials" or "api"
    
    -- Credentials authentication
    username TEXT,
    password TEXT,  -- Encrypted
    account_id TEXT,  -- Tradovate account ID
    
    -- API authentication
    api_key TEXT,
    api_secret TEXT,  -- Encrypted
    api_endpoint TEXT,
    environment TEXT,  -- "live" or "demo"
    
    -- OAuth credentials (MISSING - needs to be added)
    client_id TEXT,
    client_secret TEXT,  -- Encrypted
    
    -- Tradovate tokens
    tradovate_token TEXT,
    tradovate_refresh_token TEXT,  -- Encrypted
    token_expires_at DATETIME,
    
    -- Account settings
    max_contracts INTEGER DEFAULT 1,
    multiplier REAL DEFAULT 1.0,
    enabled BOOLEAN DEFAULT 1,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Strategies Table

```sql
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,  -- Link to users table (MISSING - needs users table)
    account_id INTEGER,  -- Link to accounts table
    name TEXT NOT NULL,  -- "JADNQ", "JADGC", etc.
    
    -- Strategy settings
    strat_type TEXT,  -- "Stock", "Futures", etc.
    symbol TEXT,  -- "ES", "NQ", etc. (MISSING - needs to be added)
    days_to_expiry INTEGER,
    strike_offset REAL,
    position_size INTEGER DEFAULT 1,
    position_add INTEGER DEFAULT 1,
    take_profit REAL,
    stop_loss REAL,
    trim TEXT,  -- "All", "Partial"
    tpsl_units TEXT,  -- "Ticks", "Percent", "Dollars"
    directional_strategy TEXT,
    
    -- Recording settings (MISSING - needs to be added)
    recording_enabled BOOLEAN DEFAULT 1,
    demo_account_id INTEGER,  -- Demo account for recording
    
    -- Status
    active BOOLEAN DEFAULT 1,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (demo_account_id) REFERENCES accounts(id)
);
```

### Recorded Positions Table

```sql
CREATE TABLE recorded_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    
    -- Position details
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- "Buy" or "Sell"
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    entry_timestamp DATETIME NOT NULL,
    
    -- Exit details
    exit_price REAL,
    exit_timestamp DATETIME,
    exit_reason TEXT,  -- "Take Profit", "Stop Loss", "Manual", "Signal"
    
    -- P&L
    pnl REAL,
    pnl_percent REAL,
    commission REAL,
    net_pnl REAL,
    
    -- Stop Loss / Take Profit
    stop_loss_price REAL,
    take_profit_price REAL,
    
    -- Tradovate IDs
    tradovate_order_id TEXT,
    tradovate_position_id TEXT,
    
    -- Status
    status TEXT DEFAULT 'open',  -- "open", "closed", "stopped_out", "target_hit"
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (strategy_id) REFERENCES strategies(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### Users Table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    
    -- Discord integration
    discord_user_id TEXT,
    discord_access_token TEXT,  -- Encrypted
    discord_dms_enabled BOOLEAN DEFAULT 1,
    
    -- Session
    session_id TEXT,
    last_login DATETIME,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Strategy Logs Table

```sql
CREATE TABLE strategy_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    log_type TEXT NOT NULL,  -- "entry", "exit", "signal", "error"
    message TEXT NOT NULL,
    data JSON,  -- Additional data as JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
```

---

## API Endpoints & Flows

### Authentication Endpoints

**Get CSRF Token:**
```
GET /api/system/csrf-token/
Response: { "csrfToken": "..." }
```

**Check Auth:**
```
GET /api/auth/check-auth/
Headers: X-CSRFToken, Cookie
Response: { "authenticated": true, "user": {...} }
```

### Account Management Endpoints

**Get All Accounts:**
```
GET /api/accounts/get-all-at-accounts/
Response: { "accounts": [...] }
```

**Add Tradovate Account:**
```
POST /api/accounts/add-tradovate/
Body: {
    "username": "...",
    "password": "...",
    "client_id": "...",
    "client_secret": "..."
}
```

**Test Connection:**
```
POST /api/accounts/test-tradovate-connection/
Body: { credentials }
Response: { "success": true, "accounts": [...] }
```

### Strategy Endpoints (Inferred)

**List Strategies:**
```
GET /api/strategies/
Response: { "strategies": [...] }
```

**Create Strategy:**
```
POST /api/strategies/
Body: {
    "name": "JADNQ",
    "position_size": 1,
    "take_profit": 22,
    "stop_loss": 50,
    ...
}
```

**Get Strategy Details:**
```
GET /api/strategies/{id}/
Response: { strategy details + logs }
```

**Update Strategy:**
```
PUT /api/strategies/{id}/
Body: { updated fields }
```

**Delete Strategy:**
```
DELETE /api/strategies/{id}/
```

### Recorder Endpoints (Inferred)

**Start Recording:**
```
POST /api/recorder/start/{strategy_id}/
```

**Stop Recording:**
```
POST /api/recorder/stop/{strategy_id}/
```

**Get Recorded Positions:**
```
GET /api/recorder/positions/{strategy_id}/
Response: { "positions": [...] }
```

### Dashboard Endpoints (Inferred)

**Get Dashboard Summary:**
```
GET /api/dashboard/summary/
Response: {
    "total_strategies": 10,
    "active_positions": 5,
    "total_pnl": 1250.50,
    "today_pnl": 150.25,
    ...
}
```

**Get Strategy Analytics:**
```
GET /api/dashboard/analytics/{strategy_id}/
Response: {
    "total_trades": 50,
    "win_rate": 65.5,
    "total_pnl": 2500.00,
    ...
}
```

### Discord Endpoints (Inferred)

**Link Discord:**
```
GET /oauth/discord/callback/?code=...
```

**Toggle Discord DMs:**
```
POST /api/user/toggle-discord-dms/
Body: { "enabled": true }
```

---

## TradingView Integration

### Webhook Configuration

**Webhook URL Format:**
- With Strategy ID: `https://trademanagergroup.com/webhook/{strategy_id}`
- Generic: `https://trademanagergroup.com/webhook`

**Alert Message Format:**
```json
{
    "symbol": "{{ticker}}",
    "action": "{{strategy.order.action}}",
    "quantity": 1,
    "price": "{{close}}",
    "strategy": "{{strategy.strategy_name}}"
}
```

### Webhook Processing Flow

```
1. TradingView sends alert → Webhook endpoint
2. Parse alert data
3. Find strategy by name or ID
4. Execute trade on Tradovate (live/demo)
5. Log trade to database
6. Emit real-time update to dashboard
7. Send Discord notification (if enabled)
```

### Strategy Name Mapping

**TradingView Strategy Name → Database:**
- TradingView alert includes: `strategy.strategy_name`
- Matched to `strategies.name` in database
- Example: "JADNQ" in TradingView → Strategy "JADNQ" in database

---

## Missing Components & Implementation Guide

### 1. Discord Bot Service

**Required:**
- Discord bot token
- Discord.py library
- User Discord ID mapping
- DM sending functionality

**Implementation:**
```python
# discord_notifier.py
import discord
from discord.ext import tasks

class DiscordNotifier:
    def __init__(self, bot_token):
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = discord.Client(intents=intents)
        self.bot_token = bot_token
    
    async def send_strategy_notification(self, user_discord_id, message):
        user = await self.bot.fetch_user(user_discord_id)
        await user.send(message)
```

### 2. Recorder Background Service

**Required:**
- Background task scheduler (Celery or APScheduler)
- Tradovate API polling
- Position matching logic
- Database logging

**Implementation:**
```python
# position_recorder.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

class PositionRecorder:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    def start(self):
        self.scheduler.add_job(
            self.record_all_strategies,
            'interval',
            minutes=1
        )
        self.scheduler.start()
    
    async def record_all_strategies(self):
        # Poll positions and record
        pass
```

### 3. Real-time Dashboard Updates

**Required:**
- WebSocket server (Flask-SocketIO)
- Real-time position updates
- Live P&L calculations

**Implementation:**
```python
# Already in trading_webhook_server.py
from flask_socketio import SocketIO, emit

socketio = SocketIO(app)

@socketio.on('connect')
def handle_connect():
    emit('status', {'connected': True})

# Emit updates on position changes
socketio.emit('position_update', position_data)
```

### 4. Notification System

**Required:**
- Event listeners for position changes
- Discord notification triggers
- User preference checking

**Implementation:**
```python
# notification_service.py
class NotificationService:
    def __init__(self, discord_notifier):
        self.discord = discord_notifier
    
    async def notify_position_opened(self, user_id, strategy, position):
        if user_wants_discord_dms(user_id):
            message = f"Strategy {strategy.name}: Position opened - {position.side} {position.quantity} {position.symbol} @ {position.entry_price}"
            await self.discord.send_strategy_notification(user_discord_id, message)
```

### 5. Position Matching Algorithm

**Required:**
- Symbol matching
- Time window validation
- Strategy assignment logic

**Implementation:**
```python
def match_position_to_strategy(position, strategies):
    """Match position to strategy"""
    for strategy in strategies:
        if (position.symbol == strategy.symbol and
            position.account_id == strategy.demo_account_id and
            is_recent(position.timestamp)):
            return strategy
    return None
```

---

## Implementation Priority

### Phase 1: Core Functionality
1. ✅ Tradovate OAuth integration (DONE)
2. ✅ Account management (DONE)
3. ✅ Strategy CRUD operations
4. ✅ Database schema setup

### Phase 2: Recording System
1. Position polling service
2. Position matching algorithm
3. Database logging
4. Status tracking

### Phase 3: Notifications
1. Discord bot setup
2. OAuth integration
3. DM sending
4. Notification preferences

### Phase 4: Analytics
1. Dashboard API endpoints
2. Performance calculations
3. Real-time updates
4. Charting/visualization

---

## Environment Variables

```bash
# Tradovate
TRADOVATE_API_URL=https://live.tradovateapi.com/v1
TRADOVATE_DEMO_URL=https://demo.tradovateapi.com/v1

# Discord
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_CLIENT_ID=1128079426891042827
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_REDIRECT_URI=https://trademanagergroup.com/oauth/discord/callback

# Database
DATABASE_URL=sqlite:///trading_data.db
# or PostgreSQL:
# DATABASE_URL=postgresql://user:pass@localhost/trading

# Flask
SECRET_KEY=your_secret_key
FLASK_ENV=production
FLASK_DEBUG=False

# WebSocket
SOCKETIO_CORS_ALLOWED_ORIGINS=*
```

---

## File Structure

```
trade_manager/
├── app/
│   ├── __init__.py
│   ├── models.py              # Database models
│   ├── routes.py              # Flask routes
│   ├── auth.py                # Authentication
│   └── api/
│       ├── accounts.py        # Account endpoints
│       ├── strategies.py      # Strategy endpoints
│       ├── recorder.py        # Recorder endpoints
│       └── dashboard.py       # Dashboard endpoints
├── services/
│   ├── tradovate_service.py   # Tradovate API wrapper
│   ├── discord_notifier.py    # Discord bot
│   ├── position_recorder.py   # Position recording service
│   └── notification_service.py # Notification logic
├── workers/
│   └── recorder_worker.py     # Background recorder task
├── static/
│   └── js/
│       └── main.js            # React frontend
├── templates/
│   ├── dashboard.html
│   ├── strategies.html        # My Recorders
│   └── settings.html
├── database/
│   └── schema.sql             # Database schema
├── config.py                  # Configuration
├── requirements.txt
└── run.py                     # Application entry point
```

---

## Key Learnings from Trade Manager

1. **Pre-registered OAuth App**: Trade Manager uses one app for all users - simpler but less secure
2. **Demo Account Recording**: Tracks performance without risking live capital
3. **Discord Integration**: Real-time notifications keep users engaged
4. **Strategy-Based Tracking**: Links TradingView strategies to recorded performance
5. **Real-time Dashboard**: WebSocket updates for live position tracking

---

## Implementation Checklist

### Phase 1: Database Setup ✅ (Partial)
- [x] Accounts table (exists, needs OAuth fields)
- [x] Strategies table (exists, needs symbol & recording fields)
- [x] Trades table (exists)
- [x] Webhook logs table (exists)
- [ ] Users table (MISSING - create new)
- [ ] Recorded positions table (MISSING - create new)
- [ ] Strategy logs table (MISSING - create new)

### Phase 2: Tradovate Integration ✅ (Mostly Complete)
- [x] OAuth authentication flow
- [x] Token management
- [x] Account listing
- [x] Position polling (`get_positions()` exists)
- [x] Order execution
- [ ] Position matching algorithm (needs implementation)

### Phase 3: Recorder Service ❌ (Not Started)
- [ ] Background scheduler (APScheduler/Celery)
- [ ] Position polling loop
- [ ] Position-to-strategy matching
- [ ] Database logging of positions
- [ ] Position status tracking (open/closed/stopped)

### Phase 4: Discord Integration ❌ (Not Started)
- [ ] Discord OAuth callback handler
- [ ] Discord bot setup
- [ ] DM sending functionality
- [ ] User preference storage (enable/disable DMs)
- [ ] Notification triggers on position events

### Phase 5: Dashboard & Analytics ⚠️ (Partial)
- [x] WebSocket server (SocketIO exists)
- [x] Real-time trade updates
- [ ] Strategy performance calculations
- [ ] Position analytics API endpoints
- [ ] Dashboard frontend (React - needs work)

## 🔧 Action Items Based on Official API Documentation Review

**Date:** 2025-01-XX  
**Source:** Official Tradovate API Documentation

### Critical Fixes Required

#### 1. Refresh Token Endpoint (URGENT)
- **File:** `phantom_scraper/tradovate_integration.py` (line 214)
- **Current:** `POST /auth/refresh-token`
- **Should Be:** `GET /renewAccessToken` (per official docs)
- **Action:** Update `refresh_access_token()` method to use GET with correct endpoint
- **Priority:** HIGH - Token refresh is critical for maintaining connections

#### 2. Verify Authentication Endpoint Path
- **File:** `phantom_scraper/tradovate_integration.py`
- **Current:** `/auth/accesstokenrequest`
- **Docs Show:** `/accessTokenRequest` (may need `/auth/` prefix - verify)
- **Action:** Test both paths, document which works
- **Priority:** HIGH - Authentication must work

#### 3. Verify Order Placement Endpoint
- **File:** `phantom_scraper/tradovate_integration.py` (line 319)
- **Current:** `/order/place-order`
- **Docs Show:** `/order/placeOrder` (camelCase)
- **Action:** Verify which endpoint format works
- **Priority:** HIGH - Order execution is critical

### New Implementations Needed

#### 4. Implement Order Querying Methods
- **File:** `phantom_scraper/tradovate_integration.py`
- **Missing Methods:**
  - `get_orders()` - Get all orders
  - `get_filled_orders()` - Get completed orders (for Recorder)
  - `find_order()` - Find specific order
- **Endpoints Needed:**
  - `GET /order/list`
  - `GET /order/find`
  - `GET /order/fill`
- **Priority:** HIGH - Required for Recorder system

#### 5. Implement User Info Endpoint
- **File:** `phantom_scraper/tradovate_integration.py`
- **Endpoint:** `GET /me`
- **Purpose:** Get authenticated user information
- **Priority:** MEDIUM - Useful for account validation

#### 6. Verify Position Endpoints
- **File:** `phantom_scraper/tradovate_integration.py`
- **Current:** `get_positions()` exists but endpoint path needs verification
- **Verify:** 
  - Endpoint path: `/position/list` vs `/account/{id}/positions`
  - Response format matches expectations
- **Priority:** HIGH - Required for Recorder system

### Testing & Verification Tasks

#### 7. Endpoint Path Verification
- Test all endpoint paths against official docs
- Document actual working paths (may differ from docs)
- Update code with verified paths
- **Priority:** HIGH

#### 8. Request/Response Format Validation
- Verify all request payloads match Tradovate's expected format
- Verify response parsing handles all fields correctly
- Add error handling for unexpected responses
- **Priority:** MEDIUM

#### 9. Full Authentication Flow Testing
- Test username/password login
- Test with OAuth credentials (cid/sec)
- Test token refresh flow
- Test token expiration handling
- **Priority:** HIGH

### Documentation Updates

#### 10. Update API Endpoint Documentation
- Document all verified endpoint paths
- Document request/response formats
- Document error responses
- Create API reference guide
- **Priority:** MEDIUM

## Next Steps for Replication

### Immediate (This Week)
1. **Fix Refresh Token Endpoint** - Change to `GET /renewAccessToken`
2. **Verify Authentication Endpoints** - Test and document working paths
3. **Implement Order Querying** - Add `get_orders()` and `get_filled_orders()` methods
4. **Test Full Auth Flow** - Verify login → refresh → API calls work end-to-end

### Short Term (This Month)
1. **Complete Database Schema**
   - Add missing tables (users, recorded_positions, strategy_logs)
   - Add missing fields to existing tables (client_id, symbol, etc.)

2. **Implement Position Recorder Service**
   - Set up background scheduler
   - Implement position polling (using verified endpoints)
   - Build matching algorithm
   - Add database logging

3. **Verify All API Endpoints**
   - Test all endpoints against official docs
   - Update code with verified paths
   - Document discrepancies

### Medium Term (Next Month)
1. **Build Discord Integration**
   - Set up Discord bot
   - Implement OAuth flow
   - Create notification service
   - Add user preferences

2. **Complete Dashboard**
   - Add analytics API endpoints
   - Implement performance calculations
   - Build frontend components

3. **End-to-End Testing**
   - Test strategy creation → recording → notifications
   - Verify position matching accuracy
   - Test Discord notifications
   - Validate dashboard updates

---

**Document Version:** 1.1  
**Last Updated:** 2025-01-XX  
**Status:** In Progress - Updating with Official API Documentation  
**Changes in v1.1:**
- Added Implementation Progress Tracker
- Updated Tradovate Integration section with verified API endpoints from official docs
- Added complete API endpoints reference
- Added detailed action items based on API documentation review
- Identified critical fixes needed (refresh token endpoint, endpoint path verification)
- Documented implementation status for all endpoints

---

## User-Provided Detailed Walkthrough

### Notes from User Walkthrough
*This section will be continuously updated as we walk through the Trade Manager system*

**Last Updated:** [Will be updated during walkthrough]

---

### Overview of Walkthrough Topics

*Topics to cover during walkthrough:*
- [ ] User registration and onboarding flow
- [ ] Account connection process (Tradovate)
- [ ] Strategy creation and configuration
- [ ] Recording setup and workflow
- [ ] Dashboard interface and features
- [ ] Discord integration details
- [ ] Settings and preferences
- [ ] Trading execution flow
- [ ] Position tracking and matching
- [ ] Analytics and reporting
- [ ] Edge cases and error handling
- [ ] Any other features or workflows

---

### Walkthrough Notes

*Detailed notes from user walkthrough will be added here...*
