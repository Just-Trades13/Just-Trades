# Trade Manager Architecture Analysis & Emulation Guide

**Purpose**: Understand Trade Manager's multi-server architecture and emulate it for our system.

---

## 📊 Part 1: How to Inspect Trade Manager's Architecture

### Method 1: Browser Developer Tools (Real-Time Inspection)

**Steps:**
1. **Open Trade Manager** in your browser (https://trademanagergroup.com)
2. **Open Developer Tools** (F12 or Cmd+Option+I)
3. **Go to Network Tab**
4. **Filter by XHR/Fetch** to see API calls
5. **Filter by WS** to see WebSocket connections
6. **Record network activity** while using the app

**What to Look For:**
- **API Endpoints**: Note all `/api/*` endpoints
- **WebSocket URLs**: Look for `ws://` or `wss://` connections
- **Request Headers**: Check for authentication tokens, CSRF tokens
- **Response Formats**: Understand data structures
- **Server Headers**: Check `Server` header to identify backend technology
- **Multiple Domains**: Check if different services use different subdomains

**Key Findings from Analysis:**
- Main API: `https://trademanagergroup.com/api/*`
- WebSocket: Likely `wss://trademanagergroup.com/ws/` or similar
- Server: `nginx/1.18.0 (Ubuntu)` - suggests Django/Flask backend
- CSRF tokens required for POST/PUT/DELETE
- Session-based authentication

---

### Method 2: HAR File Analysis (Already Done)

**Location**: `/phantom_scraper/trademanagergroup.com.har`

**How to Analyze:**
1. **Open HAR file** in browser (Chrome DevTools → Network → Import HAR)
2. **Or use Python script** to parse:
```python
import json

with open('trademanagergroup.com.har', 'r') as f:
    har_data = json.load(f)

# Extract all API endpoints
endpoints = set()
for entry in har_data['log']['entries']:
    url = entry['request']['url']
    if '/api/' in url:
        endpoints.add(url)

print("Discovered API Endpoints:")
for endpoint in sorted(endpoints):
    print(f"  - {endpoint}")
```

**What We Found:**
- ✅ 25+ API endpoints discovered
- ✅ Authentication flow documented
- ✅ Dashboard, Trades, Strategies, Accounts endpoints
- ✅ WebSocket connections (likely for real-time updates)

**See**: `/phantom_scraper/trade_manager_replica/MASTER_API_SUMMARY.md` for complete list

---

### Method 3: Network Traffic Monitoring

**Tools:**
- **Wireshark**: Deep packet inspection
- **mitmproxy**: HTTP/HTTPS proxy
- **Charles Proxy**: Commercial HTTP proxy
- **Browser Extensions**: Request Interceptor

**Steps:**
1. **Set up proxy** (mitmproxy recommended)
2. **Configure browser** to use proxy
3. **Use Trade Manager** normally
4. **Capture all traffic**
5. **Analyze patterns**:
   - Which requests go to which servers?
   - Are there separate services for different functions?
   - What's the communication pattern?

**What to Identify:**
- **Separate Services**: Different ports/domains for different functions
- **WebSocket Servers**: Real-time data services
- **API Servers**: REST endpoints
- **Database Connections**: Direct DB access (unlikely, but check)
- **Third-Party Services**: External APIs used

---

### Method 4: JavaScript Code Analysis

**Steps:**
1. **Open Trade Manager** in browser
2. **View Page Source** or inspect bundled JavaScript
3. **Look for**:
   - WebSocket connection code
   - API base URLs
   - Service endpoints
   - Connection patterns

**Key Code Patterns to Find:**
```javascript
// WebSocket connections
const ws = new WebSocket('wss://...');

// API base URLs
const API_BASE = 'https://trademanagergroup.com/api';

// Service endpoints
const TRADES_SERVICE = 'https://trades.trademanagergroup.com';
const WEBSOCKET_SERVICE = 'wss://ws.trademanagergroup.com';
```

---

## 🏗️ Part 2: What Trade Manager Has (Based on Analysis)

### Discovered Architecture Components

#### 1. **Main Web Server** (Django/Flask + Nginx)
- **Purpose**: Serves frontend, handles authentication, routes API requests
- **Technology**: Python (Django/Flask), Nginx reverse proxy
- **Endpoints**: All `/api/*` routes
- **Port**: 443 (HTTPS)

#### 2. **API Service** (REST API)
- **Purpose**: Handles all business logic, database operations
- **Endpoints**: 
  - `/api/auth/*` - Authentication
  - `/api/dashboard/*` - Dashboard data
  - `/api/trades/*` - Trade operations
  - `/api/strategies/*` - Strategy management
  - `/api/accounts/*` - Account management
  - `/api/profiles/*` - User profiles
- **Technology**: Likely Django REST Framework or Flask-RESTful

#### 3. **WebSocket Service** (Real-Time Updates)
- **Purpose**: Real-time position updates, P&L updates, order status
- **Technology**: Likely Django Channels, Socket.IO, or native WebSocket
- **Connection**: `wss://trademanagergroup.com/ws/` or similar
- **Events**: 
  - Position updates
  - P&L updates
  - Order fills
  - Account balance changes

#### 4. **Trade Execution Service** (Likely Separate)
- **Purpose**: Handles actual trade execution with Tradovate
- **Technology**: Python service connecting to Tradovate API
- **Communication**: Likely communicates with main API via message queue or direct DB

#### 5. **Data Logging Service** (Likely Separate)
- **Purpose**: Records all trades, positions, P&L for historical analysis
- **Technology**: Background service, possibly Celery or similar
- **Storage**: Database (PostgreSQL/MySQL) + possibly time-series DB

#### 6. **Database** (PostgreSQL/MySQL)
- **Purpose**: Stores all application data
- **Tables**: Users, Accounts, Strategies, Trades, Positions, etc.

---

## 🚀 Part 3: How to Emulate Trade Manager's Architecture

### Proposed Multi-Server Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React/Vue)                      │
│              https://yourdomain.com                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Reverse Proxy (Nginx)                            │
│         Routes requests to appropriate services               │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┘
       │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│   Main   │ │   API    │ │ WebSocket│ │  Trade   │ │  Logger  │
│  Server  │ │ Service  │ │ Service  │ │ Service  │ │ Service  │
│          │ │          │ │          │ │          │ │          │
│ Port     │ │ Port     │ │ Port     │ │ Port     │ │ Port     │
│ 5000     │ │ 5001     │ │ 5002     │ │ 5003     │ │ 5004     │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │           │            │            │            │
     └───────────┴────────────┴────────────┴────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │    Database (SQLite/   │
              │    PostgreSQL)         │
              └───────────────────────┘
```

---

### Service Breakdown

#### **Service 1: Main Web Server** (`ultra_simple_server.py`)
**Port**: 5000  
**Purpose**: 
- Serves frontend HTML/CSS/JS
- Handles authentication
- Routes API requests to API service
- Serves static files

**Current Status**: ✅ Already exists  
**Enhancements Needed**:
- Add reverse proxy configuration
- Add service discovery/routing
- Add health check endpoints

---

#### **Service 2: API Service** (`api_service.py` or new `api_server.py`)
**Port**: 5001  
**Purpose**:
- All REST API endpoints
- Business logic
- Database operations
- Account management
- Strategy management
- Trade queries

**Endpoints to Implement**:
```
GET  /api/dashboard/summary/
GET  /api/trades/
GET  /api/trades/open/
GET  /api/strategies/
POST /api/strategies/
GET  /api/accounts/
POST /api/accounts/
GET  /api/profiles/get-stat-config
```

**Technology**: Flask/FastAPI  
**Status**: ⚠️ Partially exists in `ultra_simple_server.py`  
**Action**: Extract API routes to separate service

---

#### **Service 3: WebSocket Service** (`websocket_service.py`)
**Port**: 5002  
**Purpose**:
- Real-time position updates
- Real-time P&L updates
- Order status updates
- Account balance updates
- Live market data (if needed)

**Technology**: 
- Python: `websockets` library or `Socket.IO` (python-socketio)
- Or: Node.js with `ws` library

**Events to Emit**:
```javascript
// Client subscribes to:
- 'position_update'  // Position changes
- 'pnl_update'       // P&L changes
- 'order_fill'       // Order filled
- 'account_update'   // Account balance changes
```

**Status**: ❌ Not yet implemented  
**Action**: Create new WebSocket service

**Reference**: See `/phantom_scraper/websocket docs.txt` for detailed implementation

---

#### **Service 4: Trade Execution Service** (`trade_execution_service.py`)
**Port**: 5003  
**Purpose**:
- Executes trades via Tradovate API
- Manages order placement
- Handles stop-loss/take-profit
- Position management
- Risk management

**Technology**: Python with `tradovate_integration.py`  
**Communication**: 
- Receives trade requests from API service (via message queue or HTTP)
- Updates database directly
- Emits events to WebSocket service

**Status**: ⚠️ Partially exists in `ultra_simple_server.py`  
**Action**: Extract trade execution logic to separate service

---

#### **Service 5: Data Logging Service** (`logging_service.py`)
**Port**: 5004  
**Purpose**:
- Logs all trades to database
- Records position history
- Calculates P&L
- Generates reports
- Historical data analysis

**Technology**: Python background service  
**Communication**:
- Listens to database changes (triggers or polling)
- Or: Receives events from other services
- Writes to time-series database (optional)

**Status**: ❌ Not yet implemented  
**Action**: Create new logging service

---

### Implementation Plan

#### **Phase 1: Separate API Service** (Week 1)
1. **Extract API routes** from `ultra_simple_server.py`
2. **Create** `api_server.py` on port 5001
3. **Move** all `/api/*` endpoints to new service
4. **Update** frontend to call new API service
5. **Test** all endpoints work

#### **Phase 2: WebSocket Service** (Week 2)
1. **Create** `websocket_service.py` on port 5002
2. **Implement** WebSocket server (Socket.IO or native)
3. **Add** event handlers for position/P&L updates
4. **Update** frontend to connect to WebSocket
5. **Test** real-time updates work

#### **Phase 3: Trade Execution Service** (Week 3)
1. **Extract** trade execution logic from main server
2. **Create** `trade_execution_service.py` on port 5003
3. **Implement** message queue (Redis/RabbitMQ) or HTTP communication
4. **Update** API service to send trade requests to execution service
5. **Test** trade execution flow

#### **Phase 4: Logging Service** (Week 4)
1. **Create** `logging_service.py` on port 5004
2. **Implement** database change listeners or event subscribers
3. **Add** P&L calculation logic
4. **Add** historical data storage
5. **Test** logging and reporting

#### **Phase 5: Reverse Proxy** (Week 5)
1. **Set up** Nginx reverse proxy
2. **Configure** routing to all services
3. **Add** SSL/TLS certificates
4. **Add** load balancing (if needed)
5. **Test** all services through proxy

---

### Communication Patterns

#### **Option 1: HTTP Communication** (Simplest)
```
Frontend → API Service → Trade Execution Service (HTTP)
API Service → WebSocket Service (HTTP)
Trade Execution Service → Database
WebSocket Service → Frontend (WebSocket)
```

**Pros**: Simple, easy to debug  
**Cons**: Synchronous, potential bottlenecks

#### **Option 2: Message Queue** (Recommended)
```
Frontend → API Service → Message Queue (Redis/RabbitMQ) → Trade Execution Service
Trade Execution Service → Message Queue → WebSocket Service
WebSocket Service → Frontend (WebSocket)
```

**Pros**: Asynchronous, scalable, decoupled  
**Cons**: More complex, requires message queue setup

#### **Option 3: Database Events** (For Logging)
```
Trade Execution Service → Database
Database Triggers → Logging Service
Logging Service → Database (historical data)
```

**Pros**: Automatic, reliable  
**Cons**: Database-specific, can be slow

---

### Technology Stack Recommendations

#### **Option A: Python-Only Stack** (Current)
- **Main Server**: Flask (`ultra_simple_server.py`)
- **API Service**: Flask or FastAPI
- **WebSocket Service**: `python-socketio` or `websockets`
- **Trade Service**: Python with existing `tradovate_integration.py`
- **Logging Service**: Python background service
- **Message Queue**: Redis (with `celery` or `rq`)

**Pros**: 
- ✅ Already using Python
- ✅ Can reuse existing code
- ✅ Single language ecosystem

**Cons**:
- ⚠️ WebSocket performance may be limited
- ⚠️ More complex async handling

#### **Option B: Hybrid Stack** (Recommended)
- **Main Server**: Flask (Python)
- **API Service**: FastAPI (Python) - Better async support
- **WebSocket Service**: Node.js with `ws` or `Socket.IO`
- **Trade Service**: Python (existing code)
- **Logging Service**: Python background service
- **Message Queue**: Redis

**Pros**:
- ✅ Best performance for WebSocket
- ✅ FastAPI excellent for APIs
- ✅ Can still use existing Python code

**Cons**:
- ⚠️ Two languages to maintain
- ⚠️ More deployment complexity

---

### Quick Start: Single Service First

**Before building multiple services, start with one:**

1. **Keep everything in `ultra_simple_server.py`** for now
2. **Add WebSocket support** to existing server
3. **Add logging** to existing server
4. **Once working, extract** to separate services

**This approach:**
- ✅ Faster to implement
- ✅ Easier to debug
- ✅ Can refactor later
- ✅ Less infrastructure needed

---

## 📋 Next Steps

### Immediate Actions:
1. **✅ Review** this guide
2. **🔍 Inspect** Trade Manager using browser dev tools
3. **📊 Analyze** HAR file more deeply (if needed)
4. **💡 Decide** on architecture approach:
   - Start with single service + WebSocket?
   - Or build multiple services from start?

### Short-Term (1-2 weeks):
1. **Add WebSocket support** to existing server
2. **Test** real-time updates
3. **Extract** API routes to separate file (even if same process)

### Medium-Term (1-2 months):
1. **Separate** services into different processes
2. **Add** message queue for async communication
3. **Add** reverse proxy for routing
4. **Add** logging service

### Long-Term (3+ months):
1. **Scale** services independently
2. **Add** monitoring and health checks
3. **Add** load balancing
4. **Optimize** performance

---

## 🔗 Related Files

- **HAR Analysis**: `/phantom_scraper/trade_manager_replica/HAR_ANALYSIS.md`
- **API Documentation**: `/phantom_scraper/trade_manager_replica/MASTER_API_SUMMARY.md`
- **WebSocket Docs**: `/phantom_scraper/websocket docs.txt`
- **Live P&L Docs**: `/phantom_scraper/Live pnl docs.txt`
- **Trade Manager Backend**: `/phantom_scraper/trade_manager_backend.py`
- **Trade Manager Auth**: `/phantom_scraper/trade_manager_auth.py`

---

## 💡 Key Takeaways

1. **Trade Manager uses multiple services** - Main server, API, WebSocket, Trade execution, Logging
2. **You can inspect it** - Use browser dev tools, HAR files, network monitoring
3. **Start simple** - Add WebSocket to existing server first
4. **Extract later** - Once working, separate into microservices
5. **Use message queues** - For async communication between services
6. **Reverse proxy** - Route requests to appropriate services

---

**Last Updated**: December 2025  
**Status**: Analysis Complete - Ready for Implementation

