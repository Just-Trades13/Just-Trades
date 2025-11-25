# Just.Trades. Backend Implementation Plan

## Overview

This document outlines the step-by-step plan to build the backend for Just.Trades., transforming the current UI-only application into a fully functional trading automation platform.

## Current State

### ✅ What We Have
- **UI**: Complete, polished frontend with all pages (Dashboard, Recorders, Strategies, Traders, Control Center, Settings)
- **Basic Flask Server**: `ultra_simple_server.py` with template rendering
- **Database Models**: SQLAlchemy models in `phantom_scraper/models.py` (Account, Strategy, Trade, WebhookLog)
- **Tradovate Integration**: `phantom_scraper/tradovate_integration.py` with authentication, account management, order placement, position polling
- **Database**: SQLite databases (`trading_data.db`, `trading_webhook.db`)

### ❌ What's Missing
- **User Authentication**: No user accounts, sessions, or login system
- **API Endpoints**: No REST API for frontend to consume
- **Database Schema**: Missing tables (users, recorded_positions, strategy_logs) and fields
- **Recorder Service**: Background service to poll positions and match to strategies
- **Discord Integration**: Bot setup and notification system
- **Webhook Handler**: TradingView alert processing
- **Real-time Updates**: WebSocket/SSE for live dashboard updates
- **Data Layer**: Service layer connecting UI → API → Database → Tradovate

---

## Implementation Phases

### Phase 1: Database & Models (Foundation)
**Goal**: Complete database schema and models

#### Tasks:
1. **Add Missing Tables**
   - `users` table (authentication, Discord integration)
   - `recorded_positions` table (demo position tracking)
   - `strategy_logs` table (strategy event logging)
   - `traders` table (strategy-account assignments)

2. **Extend Existing Tables**
   - `accounts`: Add `client_id`, `client_secret` fields for OAuth
   - `strategies`: Add `symbol`, `demo_account_id`, `recording_enabled`, `user_id`
   - `trades`: Add fields for webhook tracking, strategy matching

3. **Create Database Migration Script**
   - SQLAlchemy Alembic setup
   - Migration to add new tables/fields
   - Data migration for existing data (if any)

**Files to Create/Modify:**
- `app/models.py` - Complete model definitions
- `app/database.py` - Database initialization and session management
- `migrations/` - Alembic migration files

**Estimated Time**: 2-3 hours

---

### Phase 2: User Authentication & Sessions
**Goal**: Secure user authentication system

#### Tasks:
1. **User Registration/Login**
   - Registration endpoint (username, email, password)
   - Login endpoint (username/email + password)
   - Password hashing (bcrypt)
   - Session management (Flask sessions)

2. **Session Management**
   - CSRF token generation
   - Session cookie handling
   - Auth middleware for protected routes
   - Logout functionality

3. **User Settings**
   - Profile management
   - Password change
   - Account deletion

**Files to Create/Modify:**
- `app/auth.py` - Authentication logic
- `app/routes/auth.py` - Auth endpoints
- `templates/login.html` - Login page
- `templates/register.html` - Registration page
- Update `ultra_simple_server.py` - Add auth routes

**Estimated Time**: 3-4 hours

---

### Phase 3: API Endpoints (Core CRUD)
**Goal**: REST API for all UI operations

#### Tasks:
1. **Accounts API** (`/api/accounts/`)
   - `GET /api/accounts/` - List all accounts
   - `POST /api/accounts/` - Add new account (Tradovate)
   - `GET /api/accounts/<id>/` - Get account details
   - `PUT /api/accounts/<id>/` - Update account
   - `DELETE /api/accounts/<id>/` - Delete account
   - `POST /api/accounts/test-connection/` - Test Tradovate connection

2. **Recorders/Strategies API** (`/api/recorders/`)
   - `GET /api/recorders/` - List all recorders
   - `POST /api/recorders/` - Create new recorder
   - `GET /api/recorders/<id>/` - Get recorder details
   - `PUT /api/recorders/<id>/` - Update recorder
   - `DELETE /api/recorders/<id>/` - Delete recorder
   - `POST /api/recorders/<id>/start/` - Start recording
   - `POST /api/recorders/<id>/stop/` - Stop recording

3. **Traders API** (`/api/traders/`)
   - `GET /api/traders/` - List all traders
   - `POST /api/traders/` - Create new trader (assign strategy to account)
   - `GET /api/traders/<id>/` - Get trader details
   - `PUT /api/traders/<id>/` - Update trader
   - `DELETE /api/traders/<id>/` - Delete trader
   - `POST /api/traders/<id>/toggle/` - Enable/disable trader

4. **Dashboard API** (`/api/dashboard/`)
   - `GET /api/dashboard/summary/` - Dashboard overview (metrics, stats)
   - `GET /api/dashboard/positions/` - Current open positions
   - `GET /api/dashboard/trade-history/` - Recent trades
   - `GET /api/dashboard/performance/` - Performance metrics

5. **Settings API** (`/api/settings/`)
   - `GET /api/settings/` - Get user settings
   - `PUT /api/settings/` - Update settings
   - `POST /api/settings/discord-link/` - Link Discord account
   - `POST /api/settings/discord-toggle/` - Toggle Discord DMs

**Files to Create/Modify:**
- `app/api/accounts.py` - Account endpoints
- `app/api/recorders.py` - Recorder endpoints
- `app/api/traders.py` - Trader endpoints
- `app/api/dashboard.py` - Dashboard endpoints
- `app/api/settings.py` - Settings endpoints
- `app/api/__init__.py` - API blueprint registration
- Update `ultra_simple_server.py` - Register API blueprints

**Estimated Time**: 6-8 hours

---

### Phase 4: Webhook Handler (TradingView Integration)
**Goal**: Process TradingView alerts and execute trades

#### Tasks:
1. **Webhook Endpoint**
   - `POST /webhook/<strategy_name>/` - Receive TradingView alerts
   - Parse JSON payload (strategy, action, contracts, metadata)
   - Validate payload structure
   - Find matching strategy/recorder
   - Route to appropriate account(s)

2. **Trade Execution Logic**
   - Map TradingView action to Tradovate order
   - Apply strategy settings (TP, SL, filters, delays)
   - Execute order via Tradovate API
   - Handle errors and retries
   - Log webhook and trade to database

3. **Signal Processing**
   - Strategy matching (by name or ID)
   - Account routing (which account to use)
   - Position sizing (contracts, multiplier)
   - Risk management (max contracts, daily loss limits)

**Files to Create/Modify:**
- `app/webhooks.py` - Webhook handler
- `app/services/trade_executor.py` - Trade execution service
- `app/services/signal_processor.py` - Signal processing logic
- Update `ultra_simple_server.py` - Add webhook route

**Estimated Time**: 4-5 hours

---

### Phase 5: Recorder Service (Position Tracking)
**Goal**: Background service to track demo account positions

#### Tasks:
1. **Background Scheduler**
   - Set up APScheduler or Celery
   - Scheduled task to poll positions every 1-5 minutes
   - Per-strategy polling (only active recorders)

2. **Position Polling**
   - Get open positions from Tradovate API
   - Get filled orders from Tradovate API
   - Match positions to strategies (symbol, account, time window)
   - Track position changes (new, updated, closed)

3. **Position Recording**
   - Record new positions to `recorded_positions` table
   - Update existing positions (quantity changes, P&L)
   - Mark closed positions (exit price, P&L, reason)
   - Calculate performance metrics

4. **Strategy Logging**
   - Log position events to `strategy_logs`
   - Entry, exit, stop loss, take profit events
   - Error logging

**Files to Create/Modify:**
- `app/services/recorder_service.py` - Main recorder service
- `app/services/position_matcher.py` - Position matching logic
- `app/workers/recorder_worker.py` - Background worker
- `app/scheduler.py` - Scheduler setup
- Update `ultra_simple_server.py` - Start scheduler on app init

**Estimated Time**: 6-8 hours

---

### Phase 6: Discord Integration
**Goal**: Discord notifications for strategy events

#### Tasks:
1. **Discord Bot Setup**
   - Create Discord bot in Developer Portal
   - Get bot token
   - Set up discord.py client
   - Bot permissions (Send Messages, Read Message History)

2. **Discord OAuth**
   - OAuth callback endpoint (`/oauth/discord/callback/`)
   - Exchange code for access token
   - Store Discord user ID in database
   - Link/unlink Discord account

3. **Notification Service**
   - Send DM on position opened
   - Send DM on position closed
   - Send DM on stop loss/take profit
   - Daily/weekly summary (optional)
   - Respect user preferences (enable/disable DMs)

4. **Notification Triggers**
   - Hook into recorder service events
   - Hook into webhook handler events
   - Error notifications

**Files to Create/Modify:**
- `app/services/discord_bot.py` - Discord bot client
- `app/services/notification_service.py` - Notification logic
- `app/routes/oauth.py` - OAuth callback handler
- Update `app/services/recorder_service.py` - Add notification calls
- Update `app/webhooks.py` - Add notification calls

**Estimated Time**: 4-5 hours

---

### Phase 7: Real-time Updates (WebSocket)
**Goal**: Live dashboard updates without page refresh

#### Tasks:
1. **WebSocket Server**
   - Set up Flask-SocketIO
   - Connection handling
   - Room management (per-user rooms)

2. **Event Broadcasting**
   - Position updates (new, updated, closed)
   - Trade execution updates
   - Strategy status changes
   - Account status changes

3. **Frontend Integration**
   - WebSocket client in JavaScript
   - Update dashboard metrics in real-time
   - Update trade history table
   - Update position list

**Files to Create/Modify:**
- `app/socketio.py` - SocketIO setup
- `app/services/realtime_broadcaster.py` - Event broadcasting
- `static/js/realtime.js` - Frontend WebSocket client
- Update `templates/dashboard.html` - Add WebSocket integration
- Update `ultra_simple_server.py` - Initialize SocketIO

**Estimated Time**: 3-4 hours

---

### Phase 8: Control Center (Manual Trading)
**Goal**: Manual trade execution interface

#### Tasks:
1. **Manual Trade API**
   - `POST /api/control-center/manual-trade/` - Execute manual trade
   - Strategy/ticker selection
   - Quantity input
   - BUY/SELL/CLOSE actions
   - Validation and execution

2. **Live Trading Panel API**
   - `GET /api/control-center/live-traders/` - Get active traders
   - `POST /api/control-center/trader/<id>/toggle/` - Enable/disable
   - `POST /api/control-center/trader/<id>/close/` - Close position
   - Real-time P&L updates

3. **AutoTrader Logs API**
   - `GET /api/control-center/logs/` - Get recent logs
   - WebSocket stream for live logs
   - Filter by strategy, account, date

**Files to Create/Modify:**
- `app/api/control_center.py` - Control center endpoints
- `app/services/manual_trader.py` - Manual trade execution
- Update `templates/control_center.html` - Connect to API

**Estimated Time**: 3-4 hours

---

### Phase 9: Analytics & Performance Calculations
**Goal**: Calculate and display performance metrics

#### Tasks:
1. **Performance Metrics**
   - Win rate calculation
   - Average win/loss
   - Profit factor
   - Sharpe ratio
   - Max drawdown
   - Cumulative return

2. **Analytics API**
   - `GET /api/analytics/strategy/<id>/` - Strategy performance
   - `GET /api/analytics/dashboard/` - Overall performance
   - `GET /api/analytics/chart-data/` - Chart data (profit vs drawdown)

3. **Data Aggregation**
   - Daily/weekly/monthly summaries
   - Trade frequency analysis
   - Best/worst days
   - Strategy comparison

**Files to Create/Modify:**
- `app/services/analytics.py` - Analytics calculations
- `app/api/analytics.py` - Analytics endpoints
- Update `templates/dashboard.html` - Use real analytics data

**Estimated Time**: 4-5 hours

---

### Phase 10: Testing & Polish
**Goal**: End-to-end testing and bug fixes

#### Tasks:
1. **Integration Testing**
   - Test full flow: Create account → Create strategy → Receive webhook → Execute trade → Record position
   - Test recorder service: Poll positions → Match to strategy → Update database
   - Test Discord notifications
   - Test real-time updates

2. **Error Handling**
   - API error responses
   - Tradovate API error handling
   - Webhook validation errors
   - Database error handling

3. **Performance Optimization**
   - Database query optimization
   - Caching (Redis optional)
   - Background task optimization

4. **Security**
   - Input validation
   - SQL injection prevention
   - XSS prevention
   - Rate limiting

**Files to Create/Modify:**
- `tests/` - Test files
- `app/utils/validators.py` - Input validation
- `app/utils/errors.py` - Error handling
- Update all API endpoints - Add error handling

**Estimated Time**: 6-8 hours

---

## File Structure (Final)

```
/Users/mylesjadwin/Trading Projects/
├── app/
│   ├── __init__.py                 # Flask app factory
│   ├── models.py                    # SQLAlchemy models
│   ├── database.py                  # DB initialization
│   ├── auth.py                     # Authentication logic
│   ├── socketio.py                 # SocketIO setup
│   ├── scheduler.py                 # Background scheduler
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py                 # Auth routes (login, register)
│   │   ├── main.py                 # Main routes (dashboard, pages)
│   │   └── oauth.py                # OAuth callbacks
│   ├── api/
│   │   ├── __init__.py             # API blueprint
│   │   ├── accounts.py             # Account endpoints
│   │   ├── recorders.py            # Recorder endpoints
│   │   ├── traders.py              # Trader endpoints
│   │   ├── dashboard.py            # Dashboard endpoints
│   │   ├── settings.py             # Settings endpoints
│   │   ├── control_center.py       # Control center endpoints
│   │   └── analytics.py           # Analytics endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── tradovate_service.py    # Tradovate API wrapper
│   │   ├── trade_executor.py       # Trade execution
│   │   ├── signal_processor.py    # Signal processing
│   │   ├── recorder_service.py     # Position recording
│   │   ├── position_matcher.py     # Position matching
│   │   ├── discord_bot.py          # Discord bot
│   │   ├── notification_service.py # Notifications
│   │   ├── manual_trader.py        # Manual trading
│   │   ├── analytics.py            # Analytics calculations
│   │   └── realtime_broadcaster.py # WebSocket events
│   ├── workers/
│   │   ├── __init__.py
│   │   └── recorder_worker.py     # Background recorder task
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── validators.py           # Input validation
│   │   └── errors.py               # Error handling
│   └── webhooks.py                 # TradingView webhook handler
├── migrations/                      # Alembic migrations
├── tests/                          # Test files
├── templates/                      # HTML templates (existing)
├── static/                         # Static files (existing)
├── config.py                       # Configuration
├── requirements.txt                # Dependencies
├── run.py                          # Application entry point
└── ultra_simple_server.py          # Current server (to be refactored)
```

---

## Dependencies to Add

```txt
# Authentication & Security
Flask-Login==0.6.3
Flask-Session==0.5.0
bcrypt==4.1.2
python-jose[cryptography]==3.3.0

# API & WebSocket
Flask-RESTful==0.3.10
Flask-SocketIO==5.3.6
python-socketio==5.10.0

# Background Tasks
APScheduler==3.10.4
celery==5.3.4  # Optional, if using Celery instead

# Discord
discord.py==2.3.2

# Database
SQLAlchemy==2.0.23
alembic==1.13.1

# HTTP Client (for Tradovate)
aiohttp==3.9.1
requests==2.31.0

# Utilities
python-dotenv==1.0.0
pydantic==2.5.3  # For data validation
```

---

## Implementation Order (Recommended)

1. **Phase 1** - Database & Models (Foundation)
2. **Phase 2** - User Authentication (Security first)
3. **Phase 3** - API Endpoints (Core functionality)
4. **Phase 4** - Webhook Handler (TradingView integration)
5. **Phase 5** - Recorder Service (Position tracking)
6. **Phase 6** - Discord Integration (Notifications)
7. **Phase 7** - Real-time Updates (UX enhancement)
8. **Phase 8** - Control Center (Manual trading)
9. **Phase 9** - Analytics (Performance metrics)
10. **Phase 10** - Testing & Polish (Quality assurance)

---

## Quick Start Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python -m app.database init

# Run migrations
alembic upgrade head

# Start development server
python run.py

# Start recorder worker (separate terminal)
python -m app.workers.recorder_worker
```

---

## Next Steps

1. **Review this plan** - Confirm approach and priorities
2. **Start Phase 1** - Database schema and models
3. **Iterate** - Build and test each phase incrementally
4. **Deploy** - Once stable, deploy to production

---

**Estimated Total Time**: 40-50 hours of development

**Priority Order**: Phases 1-5 are critical for core functionality. Phases 6-9 are enhancements that can be added incrementally.

