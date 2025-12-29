# Trade Manager vs Just.Trades - Architecture Comparison
**Date:** December 29, 2025

---

## 🏗️ SYSTEM ARCHITECTURE

### Trade Manager Group Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  React SPA (Single Page Application)                 │  │
│  │  - Material-UI Components                            │  │
│  │  - WebSocket Client (wss://:5000/ws)                │  │
│  │  - Firebase Messaging                                │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTPS (443) / WSS (5000)
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    REVERSE PROXY                             │
│                    (Nginx/Apache)                            │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
┌────────▼────────┐            ┌─────────▼─────────┐
│  Django API     │            │  WebSocket Server │
│  (Port 443)     │            │  (Port 5000)      │
│                 │            │                   │
│  - REST Endpoints│            │  - Real-time      │
│  - Auth         │            │  - Log streaming  │
│  - Strategies   │            │  - Trade updates  │
│  - Trades       │            │                   │
└────────┬────────┘            └───────────────────┘
         │
         │
┌────────▼─────────────────────────────────────────┐
│              DATABASE                             │
│         (PostgreSQL/MySQL)                        │
│  - Users, Strategies, Trades, Accounts           │
└───────────────────────────────────────────────────┘
```

### Just.Trades Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENT                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Jinja2 Templates (Server-rendered)                  │  │
│  │  - Bootstrap/jQuery UI                                │  │
│  │  - WebSocket Client (Flask-SocketIO)                 │  │
│  │  - AJAX for API calls                                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTPS
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    FLASK APPLICATION                          │
│              (ultra_simple_server.py)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  - All Routes & Endpoints                            │  │
│  │  - WebSocket Handler (Flask-SocketIO)               │  │
│  │  - Webhook Receiver                                  │  │
│  │  - Trade Executor (recorder_service.py)             │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              NEON POSTGRESQL DATABASE                         │
│  - Users, Recorders, Traders, Accounts, Trades              │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔄 DATA FLOW COMPARISON

### Trade Manager - Signal Flow
```
┌──────────┐     ┌──────────┐     ┌──────────┐
│Telegram  │     │ Discord   │     │TradingView│
│ Channel  │     │ Channel   │     │  Alert    │
└────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │
     │ Scraper        │ Scraper        │ Webhook
     ▼                ▼                ▼
┌─────────────────────────────────────────────┐
│         Django Backend                       │
│  ┌──────────────────────────────────────┐  │
│  │  Signal Parser                        │  │
│  │  - Regex matching                     │  │
│  │  - Rule evaluation                    │  │
│  └──────────────┬───────────────────────┘  │
│                 │                            │
│  ┌──────────────▼───────────────────────┐  │
│  │  Strategy Matcher                     │  │
│  │  - Ticker match                       │  │
│  │  - Direction filter                   │  │
│  │  - Take-the-trade filter              │  │
│  └──────────────┬───────────────────────┘  │
│                 │                            │
│  ┌──────────────▼───────────────────────┐  │
│  │  Trade Executor                       │  │
│  │  - Get broker credentials             │  │
│  │  - Format order                       │  │
│  │  - Execute API call                   │  │
│  └──────────────┬───────────────────────┘  │
└─────────────────┼────────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
    ┌────▼────┐      ┌─────▼─────┐
    │Robinhood│      │  Webull   │
    │   API   │      │    API    │
    └─────────┘      └───────────┘
```

### Just.Trades - Signal Flow
```
┌─────────────────────────────────────────┐
│         TradingView Alert                │
└──────────────┬──────────────────────────┘
               │
               │ Webhook POST
               ▼
┌──────────────────────────────────────────┐
│      Flask Webhook Handler                │
│  /webhook/{webhook_token}                 │
└──────────────┬───────────────────────────┘
               │
               │ Find Recorder
               ▼
┌──────────────────────────────────────────┐
│      Risk Filter Engine                   │
│  ┌────────────────────────────────────┐  │
│  │  ✓ Direction Filter                │  │
│  │  ✓ Time Filter #1                  │  │
│  │  ✓ Time Filter #2                  │  │
│  │  ✓ Signal Cooldown                 │  │
│  │  ✓ Max Signals/Session             │  │
│  │  ✓ Max Daily Loss                  │  │
│  │  ✓ Max Contracts/Trade             │  │
│  │  ✓ Signal Delay (Nth)              │  │
│  └────────────────────────────────────┘  │
└──────────────┬───────────────────────────┘
               │
               │ All Filters Pass
               ▼
┌──────────────────────────────────────────┐
│      Trade Executor                       │
│  (recorder_service.py)                    │
│  ┌────────────────────────────────────┐  │
│  │  1. Place Market Order              │  │
│  │  2. Place TP Limit Order (GTC)      │  │
│  │  3. Place SL Stop Order (if > 0)   │  │
│  │  4. Handle DCA if needed           │  │
│  └────────────────────────────────────┘  │
└──────────────┬───────────────────────────┘
               │
               │ REST API
               ▼
┌──────────────────────────────────────────┐
│         Tradovate API                    │
│  (live.tradovateapi.com)                  │
└──────────────────────────────────────────┘
```

---

## 📦 COMPONENT COMPARISON

### Backend Components

| Component | Trade Manager | Just.Trades |
|-----------|--------------|-------------|
| **Framework** | Django | Flask |
| **API Style** | REST (DRF) | REST (Flask routes) |
| **WebSocket** | Separate server | Flask-SocketIO |
| **ORM** | Django ORM | SQLAlchemy |
| **Auth** | Session-based | Session-based |
| **Task Queue** | Celery (likely) | Threading |

### Frontend Components

| Component | Trade Manager | Just.Trades |
|-----------|--------------|-------------|
| **Framework** | React | Jinja2 |
| **UI Library** | Material-UI | Bootstrap |
| **State Mgmt** | React State/Redux | Server state |
| **Real-time** | WebSocket client | WebSocket client |
| **Notifications** | Firebase | None |
| **Build Tool** | Webpack | None (server-rendered) |

### Database Schema

#### Trade Manager
```
users
  ├── id, username, email
  ├── discord_id, telegram_api_id
  └── robinhood_token, webull_credentials

strategies
  ├── id, user_id, name
  ├── configuration (JSON - rules)
  ├── enabled, type
  └── accounts (M2M)

accounts
  ├── id, user_id
  ├── broker_type (robinhood/webull/tdv)
  └── api_credentials (encrypted)

trades
  ├── id, strategy_id, account_id
  ├── symbol, side, quantity, price
  └── order_id, status, profit_loss
```

#### Just.Trades
```
users
  ├── id, username, email
  ├── is_admin, is_approved
  └── settings_json

recorders
  ├── id, user_id, name
  ├── strategy_type, symbol
  ├── position sizes, TP/SL config
  ├── risk filters (8+ fields)
  ├── is_private
  └── webhook_token

traders
  ├── id, user_id, recorder_id
  ├── account_id, subaccount_id
  ├── enabled, enabled_accounts
  └── risk overrides (optional)

accounts
  ├── id, user_id
  ├── username, password
  ├── tradovate_token (OAuth)
  └── is_demo

trades (inferred)
  ├── id, trader_id, account_id
  ├── symbol, side, quantity
  └── entry_price, exit_price
```

---

## 🔐 AUTHENTICATION FLOW

### Trade Manager
```
1. User Login → Django creates session
2. Session cookie stored
3. Every request includes cookie
4. Django validates session
5. Broker APIs use stored credentials
```

### Just.Trades
```
1. User Login → Flask creates session
2. Session cookie stored
3. Every request includes cookie
4. Flask validates session
5. Tradovate OAuth:
   - User connects → OAuth redirect
   - Callback → Exchange code for token
   - Token stored in DB
   - Used for API calls (no rate limit)
```

---

## 🚀 DEPLOYMENT

### Trade Manager
- **Hosting:** Self-hosted (likely VPS/Cloud)
- **Web Server:** Nginx/Apache
- **Process Manager:** Systemd/Supervisor
- **Database:** PostgreSQL/MySQL
- **WebSocket:** Separate service on port 5000

### Just.Trades
- **Hosting:** Railway (PaaS)
- **Web Server:** Gunicorn (likely)
- **Process Manager:** Railway
- **Database:** Neon PostgreSQL (external)
- **WebSocket:** Flask-SocketIO in same process

---

## 📊 SCALABILITY COMPARISON

### Trade Manager
- ✅ Separate WebSocket server (can scale independently)
- ✅ Django can run multiple workers
- ✅ Database connection pooling
- ⚠️ WebSocket on non-standard port (needs proxy config)

### Just.Trades
- ⚠️ WebSocket in same process (harder to scale)
- ✅ Railway auto-scaling
- ✅ Neon connection pooling
- ✅ OAuth tokens (no rate limit)
- ⚠️ Single broker (Tradovate only)

---

## 🎯 KEY ARCHITECTURAL DIFFERENCES

1. **Frontend Architecture**
   - Trade Manager: React SPA (client-side routing)
   - Just.Trades: Server-rendered (traditional)

2. **WebSocket Implementation**
   - Trade Manager: Separate service
   - Just.Trades: Integrated with Flask

3. **Signal Processing**
   - Trade Manager: Multiple sources, regex parsing
   - Just.Trades: Single source (TradingView), direct webhook

4. **Risk Management**
   - Trade Manager: Basic (in strategy rules)
   - Just.Trades: Dedicated filter engine (8+ filters)

5. **Order Management**
   - Trade Manager: Simple market/limit
   - Just.Trades: Advanced (bracket, DCA, multi-TP)

---

*Architecture comparison - See TRADE_MANAGER_COMPARISON.md for feature comparison*
