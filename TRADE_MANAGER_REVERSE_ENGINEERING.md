# Trade Manager Reverse Engineering - Complete Analysis

**Date:** 2025-01-XX  
**Source:** HAR file analysis, browser inspection, architecture documentation  
**Purpose:** Complete reverse engineering of trademanagergroup.com for replica

---

## 🏗️ System Architecture

### Technology Stack

**Frontend:**
- React (Single Page Application)
- Build tool: Webpack (bundle: `main.d6a4e8f7.js`)
- CSS: Custom CSS with CSS variables
- UI Framework: Custom components with Material Icons
- Toast notifications: react-toastify
- Fonts: Roboto, Poppins, Inter

**Backend:**
- Django/Flask (Python) - Based on URL patterns (`/api/`)
- Session-based authentication (Django sessions)
- CSRF protection
- Nginx server (Ubuntu)

**Database:**
- Likely PostgreSQL or SQLite (based on Django patterns)

**Authentication:**
- Session cookies (`sessionid`)
- CSRF tokens (`csrftoken`)
- Cookie-based authentication

---

## 📡 API Endpoints (Verified from HAR)

### 1. CSRF Token Endpoint

**Endpoint:** `GET /api/system/csrf-token/`

**Request:**
```http
GET /api/system/csrf-token/ HTTP/1.1
Host: trademanagergroup.com
Cookie: sessionid=...; csrftoken=...
```

**Response:**
```json
{
  "csrfToken": "uKWhuEHas1abxpJLrZ6fvAMobHOeKqUZIHIbtNsdxbDBbMtx9KpDSBajdR2yA2NB"
}
```

**Purpose:** Get CSRF token for form submissions

---

### 2. Authentication Check

**Endpoint:** `GET /api/auth/check-auth/`

**Request:**
```http
GET /api/auth/check-auth/ HTTP/1.1
Host: trademanagergroup.com
Content-Type: application/json
Cookie: sessionid=...; csrftoken=...
```

**Response:**
```json
{
  "user": {
    "username": "J.T.M.J",
    "email": "just.trades.chicago@gmail.com",
    "admin": false,
    "DiscordID": "963881348039340122",
    "access": "full",
    "signed": true,
    "is_email_verified": true,
    "sessionId": "o2vjugv8vlxmxgi8pgbmpn8xkkdexgaj"
  }
}
```

**Purpose:** Check if user is authenticated and get user info

---

### 3. Get All Accounts

**Endpoint:** `GET /api/accounts/get-all-at-accounts/`

**Request:**
```http
GET /api/accounts/get-all-at-accounts/ HTTP/1.1
Host: trademanagergroup.com
Cookie: sessionid=...; csrftoken=...
```

**Response:**
```json
[
  {
    "id": 1491,
    "Name": "Bryan-Nolan",
    "Platform": "Tradovate",
    "Status": null,
    "disabled": false,
    "subAccounts": [
      {
        "id": 6123,
        "Name": "1302271",
        "Active": true
      }
    ]
  },
  {
    "id": 1496,
    "Name": "Tony",
    "Platform": "Tradovate",
    "Status": null,
    "disabled": false,
    "subAccounts": [
      {
        "id": 6131,
        "Name": "1393592",
        "Active": true
      }
    ]
  },
  {
    "id": 1745,
    "Name": "Koram",
    "Platform": "Tradovate",
    "Status": null,
    "disabled": false,
    "subAccounts": [
      {
        "id": 7021,
        "Name": "1536745",
        "Active": true
      },
      {
        "id": 7022,
        "Name": "DEMO",
        "Active": true
      }
    ]
  }
]
```

**Purpose:** Get all user's trading accounts with subaccounts

---

### 4. Get Profile Limits

**Endpoint:** `GET /api/profiles/get-limits/`

**Request:**
```http
GET /api/profiles/get-limits/ HTTP/1.1
Host: trademanagergroup.com
Cookie: sessionid=...; csrftoken=...
```

**Response:**
```json
{
  "micros": false,
  "maxAccounts": 999,
  "totalTraderStrats": 999,
  "totalRecorderStrats": 999
}
```

**Purpose:** Get user's plan limits (accounts, strategies)

---

## 🔐 Authentication Flow

### Session Management

1. **Initial Page Load:**
   - User visits any page
   - Frontend requests CSRF token: `GET /api/system/csrf-token/`
   - CSRF token stored in cookie and state

2. **Auth Check:**
   - Frontend calls: `GET /api/auth/check-auth/`
   - If authenticated: Returns user object
   - If not authenticated: Redirects to login

3. **API Requests:**
   - All API requests include:
     - Cookie: `sessionid=<session_id>; csrftoken=<csrf_token>`
     - Header: `X-CSRFToken: <csrf_token>` (for POST/PUT/DELETE)

### Cookies

- `sessionid`: Django session ID (httpOnly, secure, SameSite=Lax)
- `csrftoken`: CSRF token (secure, SameSite=Lax)
- `_ga`, `_gid`: Google Analytics
- `_gat_gtag_UA_XXXXX_Y`: Google Analytics throttling

---

## 🎨 UI Structure & Pages

### URL Patterns

Based on HAR file analysis:

- `/user/at/accntsetup/` - Account setup page
- `/user/at/accnts` - Account management page
- `/user/dashboard` - Dashboard (inferred)
- `/user/strats` - My Recorders (strategies) page
- `/user/traders` - My Traders page (inferred)
- `/user/settings` - Settings page (inferred)
- `/user/control` - Control Center (inferred)

### Page Components

#### 1. Dashboard
- **Viewing:** "VIEWING RECORDED STRATS" filter
- **Filters:** User, Strategy, Date Range
- **Metrics:** P&L, Win Rate, Total Trades, etc.

#### 2. My Recorders (Strategies)
- **Create Strategy** button
- **Strategy List:** Name, Position Size, Take Profit, Stop Loss
- **Actions:** Edit, Refresh, Remove
- **Strategy Details:**
  - Strategy Name
  - Position Size
  - Position Add
  - Take Profit
  - Stop Loss
  - TPSL Units (Ticks/Percent)
  - Logs section

#### 3. Account Management
- **Add Account** button
- **Account List:** Name, Platform, Status, Enable/Disable
- **Account Details:**
  - Account Name
  - Platform (Tradovate, etc.)
  - Subaccounts list
  - Active/Disabled status

#### 4. Settings
- **Discord Integration:**
  - Link Discord button
  - Enable/Disable Discord DMs toggle
- **Profile Settings:**
  - Email verification
  - Account limits

---

## 🎨 Design System

### CSS Variables (Extracted from DOM)

```css
:root {
  /* Colors */
  --background-color: #000000;
  --background-dark: #0f172a;
  --background-light: #fff;
  --primary-color: #2cc511;
  --primary-dark: #007a06;
  --secondary-color: #1d2235;
  --sidebar-color: #334155;
  --text-light: #f2f2f2;
  --text-muted: #ccc;
  
  /* Status Colors */
  --success-color: #00f2c3;
  --error-color: #ff4e4e;
  --danger-color: #fd5d93;
  --info-color: #1d8cf8;
  --warning: #ff8d72;
  
  /* Accent */
  --accent-color: #60a5fa;
  
  /* Table Layout */
  --col-account: 20%;
  --col-enable: 12%;
  --col-max: 18%;
  --col-mult: 20%;
  --col-ticker: 30%;
  
  /* Other */
  --company-name: Trade Manager;
  --discord_-server: TRADE_MANAGER;
}
```

### Typography

- **Primary Font:** Poppins, sans-serif
- **Secondary Font:** Inter, sans-serif
- **Monospace:** SFMono-Regular, Menlo, Monaco, Consolas
- **Base Size:** 0.875rem (14px)
- **Line Height:** 1.5

### Icons

- **Material Icons:** Google Material Icons
- **Font Awesome:** Font Awesome 5.0.10

---

## 📋 Inferred API Endpoints (Not in HAR but likely exist)

Based on architecture document and UI patterns:

### Account Management

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

**Update Account:**
```
PUT /api/accounts/{id}/
Body: { updated fields }
```

**Delete Account:**
```
DELETE /api/accounts/{id}/
```

### Strategy Management

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
  "tpsl_units": "Ticks",
  "account_id": 123,
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

### Recorder System

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

### Dashboard

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

### Discord Integration

**Link Discord:**
```
GET /oauth/discord/callback/?code=...
```

**Toggle Discord DMs:**
```
POST /api/user/toggle-discord-dms/
Body: { "enabled": true }
```

### Webhooks

**TradingView Webhook:**
```
POST /webhook/{strategy_id}
Body: {
  "symbol": "...",
  "action": "buy|sell|close",
  "price": "...",
  ...
}
```

---

## 🗄️ Database Schema (Inferred)

### Users Table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    discord_user_id TEXT,
    discord_dms_enabled BOOLEAN DEFAULT 1,
    admin BOOLEAN DEFAULT 0,
    access TEXT DEFAULT 'full',  -- 'full', 'limited', etc.
    is_email_verified BOOLEAN DEFAULT 0,
    session_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Accounts Table

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name TEXT NOT NULL,
    platform TEXT NOT NULL,  -- 'Tradovate', etc.
    status TEXT,
    disabled BOOLEAN DEFAULT 0,
    username TEXT,
    password TEXT,  -- Encrypted
    client_id TEXT,
    client_secret TEXT,  -- Encrypted
    tradovate_token TEXT,
    tradovate_refresh_token TEXT,
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Subaccounts Table

```sql
CREATE TABLE subaccounts (
    id INTEGER PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    name TEXT NOT NULL,
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Strategies Table

```sql
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    account_id INTEGER REFERENCES accounts(id),
    name TEXT NOT NULL,
    position_size INTEGER DEFAULT 1,
    position_add INTEGER DEFAULT 1,
    take_profit REAL,
    stop_loss REAL,
    tpsl_units TEXT,  -- 'Ticks', 'Percent', 'Dollars'
    symbol TEXT,
    recording_enabled BOOLEAN DEFAULT 1,
    demo_account_id INTEGER REFERENCES accounts(id),
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Recorded Positions Table

```sql
CREATE TABLE recorded_positions (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id),
    account_id INTEGER REFERENCES accounts(id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'Buy' or 'Sell'
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    entry_timestamp TIMESTAMP NOT NULL,
    exit_price REAL,
    exit_timestamp TIMESTAMP,
    exit_reason TEXT,  -- 'Take Profit', 'Stop Loss', 'Manual', 'Signal'
    pnl REAL,
    pnl_percent REAL,
    stop_loss_price REAL,
    take_profit_price REAL,
    tradovate_order_id TEXT,
    tradovate_position_id TEXT,
    status TEXT DEFAULT 'open',  -- 'open', 'closed', 'stopped_out', 'target_hit'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Strategy Logs Table

```sql
CREATE TABLE strategy_logs (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id),
    log_type TEXT NOT NULL,  -- 'entry', 'exit', 'signal', 'error'
    message TEXT NOT NULL,
    data JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔄 Frontend Architecture

### React Component Structure (Inferred)

```
src/
├── components/
│   ├── Layout/
│   │   ├── Sidebar.js
│   │   ├── Header.js
│   │   └── MainContent.js
│   ├── Dashboard/
│   │   ├── DashboardMetrics.js
│   │   ├── StrategyList.js
│   │   └── PositionList.js
│   ├── Accounts/
│   │   ├── AccountList.js
│   │   ├── AddAccountModal.js
│   │   └── AccountCard.js
│   ├── Strategies/
│   │   ├── StrategyList.js
│   │   ├── CreateStrategyModal.js
│   │   ├── StrategyCard.js
│   │   └── StrategyLogs.js
│   ├── Settings/
│   │   ├── DiscordSettings.js
│   │   └── ProfileSettings.js
│   └── Common/
│       ├── Modal.js
│       ├── Button.js
│       ├── Input.js
│       └── Toast.js
├── services/
│   ├── api.js          # API client
│   ├── auth.js         # Authentication
│   └── websocket.js    # WebSocket client
├── hooks/
│   ├── useAuth.js
│   ├── useApi.js
│   └── useWebSocket.js
├── utils/
│   ├── constants.js
│   └── helpers.js
└── App.js
```

### API Client Pattern

```javascript
// services/api.js
class APIClient {
  constructor() {
    this.baseURL = 'https://trademanagergroup.com/api';
    this.csrfToken = null;
    this.sessionId = null;
  }

  async getCSRFToken() {
    const response = await fetch(`${this.baseURL}/system/csrf-token/`, {
      credentials: 'include'
    });
    const data = await response.json();
    this.csrfToken = data.csrfToken;
    return this.csrfToken;
  }

  async checkAuth() {
    const response = await fetch(`${this.baseURL}/auth/check-auth/`, {
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    return await response.json();
  }

  async getAccounts() {
    const response = await fetch(`${this.baseURL}/accounts/get-all-at-accounts/`, {
      credentials: 'include'
    });
    return await response.json();
  }

  async post(url, data) {
    if (!this.csrfToken) {
      await this.getCSRFToken();
    }
    
    const response = await fetch(`${this.baseURL}${url}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.csrfToken
      },
      credentials: 'include',
      body: JSON.stringify(data)
    });
    return await response.json();
  }
}
```

---

## 🚀 Implementation Plan

### Phase 1: Backend Foundation
1. ✅ Flask/Django setup with session management
2. ✅ CSRF protection
3. ✅ Database models
4. ✅ Authentication endpoints
5. ✅ Account management endpoints

### Phase 2: Frontend Foundation
1. ✅ React app setup
2. ✅ Routing (React Router)
3. ✅ API client
4. ✅ Authentication flow
5. ✅ Layout components

### Phase 3: Core Features
1. ✅ Account management UI
2. ✅ Strategy management UI
3. ✅ Dashboard UI
4. ✅ Settings UI

### Phase 4: Advanced Features
1. ✅ Recorder service
2. ✅ Discord integration
3. ✅ WebSocket real-time updates
4. ✅ Analytics and reporting

---

## 📝 Notes

- **CSRF Token:** Must be retrieved before any POST/PUT/DELETE requests
- **Session Cookies:** All requests include `sessionid` and `csrftoken` cookies
- **API Format:** JSON request/response
- **Error Handling:** Likely returns `{"error": "message"}` format
- **Authentication:** Session-based, no JWT tokens
- **Frontend:** React SPA with client-side routing
- **Backend:** Django/Flask with REST API

---

## 🔍 Missing Information (Need to Discover)

1. **Login Endpoint:** `POST /api/auth/login/` (inferred)
2. **Logout Endpoint:** `POST /api/auth/logout/` (inferred)
3. **Strategy CRUD Endpoints:** Need to verify exact paths
4. **Recorder API Endpoints:** Need to verify exact paths
5. **WebSocket Endpoint:** For real-time updates
6. **File Upload:** If any (for exports, etc.)

---

**Next Steps:**
1. Capture more HAR files with POST requests (add account, create strategy)
2. Analyze React bundle for component structure
3. Test all endpoints to verify request/response formats
4. Document WebSocket message formats
5. Build replica application

