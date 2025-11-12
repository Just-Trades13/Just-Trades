# Complete Trade Manager Site Specification - Just.Trades Replica

**Extraction Date:** 2025-11-05  
**Source:** trademanagergroup.com  
**Target:** Just.Trades (exact replica)

---

## 📊 Site Structure - Complete Map

### Pages Extracted ✅

1. **Dashboard** - `/user/dashboard`
2. **My Recorders** - `/user/strats` (demo account strategy recording)
3. **Create/Edit Strategy** - `/user/strat` (strategy creation form)
4. **Account Management** - `/user/at/accnts` (list all accounts)
5. **Add Account Setup** - `/user/at/accntsetup` (add account form)
6. **My Trader** - `/user/at/strats` (live trading strategies)
7. **Control Center** - `/user/at/controls` (manual trading interface)
8. **Settings** - `/user/settings` (user preferences)

---

## 🔌 Complete API Endpoint List (25+ Endpoints)

### System
- `GET /api/system/csrf-token/` ✅

### Authentication
- `GET /api/auth/check-auth/` ✅
- `POST /api/auth/login/` ✅ (need payload)
- Expected: `POST /api/auth/logout/`

### Accounts
- `GET /api/accounts/get-all-at-accounts/` ✅
- Expected: `POST /api/accounts/add-tradovate/` (need payload)
- Expected: `POST /api/accounts/test-tradovate-connection/` (need payload)
- Expected: `PUT /api/accounts/{id}/` (need payload)
- Expected: `DELETE /api/accounts/{id}/`
- Expected: `POST /api/accounts/{id}/refresh/` (need payload)

### Strategies
- `GET /api/strategies/` ✅
- `GET /api/strategies/?val=DirStrat` ✅
- `GET /api/strategies/?style=at` ✅ (My Trader page)
- `GET /api/strategies/?manual=true` ✅ (Control Center)
- `GET /api/strategies/get-strat/?strat={name}&at=false` ✅
- Expected: `POST /api/strategies/` (need payload)
- Expected: `PUT /api/strategies/{id}/` (need payload)
- Expected: `DELETE /api/strategies/{id}/`

### Trades
- `GET /api/trades/` ✅
- `GET /api/trades/?usageType=true` ✅
- `GET /api/trades/?user={username}&usageType=true` ✅
- `GET /api/trades/?strategy={name}&user={username}&usageType=true` ✅
- `GET /api/trades/open/` ✅
- `GET /api/trades/open/?usageType=true` ✅
- `GET /api/trades/open/?user={username}&usageType=true` ✅
- `GET /api/trades/open/?strategy={name}&user={username}&usageType=true` ✅
- `GET /api/trades/tickers/?strat=` ✅
- `GET /api/trades/timeframes/?strat=` ✅
- Expected: `POST /api/trades/execute/` (manual trading from Control Center)

### Profiles
- `GET /api/profiles/get-limits/` ✅
- `GET /api/profiles/get-stat-config/` ✅
- `POST /api/profiles/update-stat-config/` ✅ (need payload)
- `GET /api/profiles/get-favorites/` ✅
- `POST /api/profiles/set-favorites/` ✅ (need payload)
- `GET /api/profiles/get-widget-info/?usageType=true` ✅
- `GET /api/profiles/get-widget-info/?user={username}&usageType=true` ✅
- `GET /api/profiles/get-widget-info/?strategy={name}&user={username}&usageType=true` ✅
- `GET /api/profiles/details/` ✅ (Settings page)
- Expected: `POST /api/profiles/update-username/`
- Expected: `POST /api/profiles/change-password/`
- Expected: `POST /api/profiles/toggle-push-notification/`
- Expected: `POST /api/profiles/toggle-discord-dm/`

### WebSocket
- `wss://trademanagergroup.com:5000/ws` ✅ (Control Center - real-time updates)

---

## 📋 Page-by-Page Specifications

### 1. Dashboard (`/user/dashboard`)

**Purpose:** View recorded strategy performance and analytics

**Components:**
- "VIEWING RECORDED STRATS" filter button
- User selector dropdown
- Strategy selector dropdown
- Symbol selector dropdown
- TimeFrame selector dropdown
- Trade History table with pagination
- Performance charts (canvas element)
- Date picker calendar

**API Calls:**
- `GET /api/trades/?usageType=true`
- `GET /api/trades/open/?usageType=true`
- `GET /api/profiles/get-stat-config/`
- `GET /api/profiles/get-favorites/`
- `GET /api/profiles/get-widget-info/`
- `GET /api/strategies/get-strat/?strat={name}&at=false` (when selecting strategy)

**Filters:**
- User filter
- Strategy filter
- Symbol filter
- TimeFrame filter
- Date range (calendar)

---

### 2. My Recorders (`/user/strats`)

**Purpose:** Manage demo account strategies (for recording/backtesting)

**Components:**
- "Create Strategy" button
- Search strategies field
- Strategy table with:
  - Action buttons (Edit, Delete, Refresh)
  - Strategy name (clickable)
  - Strategy details (expandable rows)
- Pagination

**API Calls:**
- `GET /api/strategies/`

**Strategy Details Shown:**
- Strat Type: Stock
- Days to Expiry
- Strike Offset
- Position Size
- Position Add
- Take Profit
- Stop Loss
- Trim
- TPSL Unit: Tick
- Directional Strategy: No
- Logs section

**Actions:**
- Create Strategy → `/user/strat`
- Edit Strategy (button)
- Delete Strategy (button)
- Refresh Strategy (button)

---

### 3. Create/Edit Strategy (`/user/strat`)

**Purpose:** Create or edit a strategy configuration

**Form Fields:**

**Basic:**
- Strategy Name (textbox)
- Strategy Type (combobox - "Stock", etc.)
- Directional Strategy (combobox)

**Position Settings (Optional):**
- Initial Position Size (spinbutton)
- Add Position Size (spinbutton)

**Stop Loss / Take Profit Settings (Optional):**
- Take Profit Target:
  - TP Unit (combobox - "Ticks", "Percent", "Dollars")
  - Trim Unit (combobox)
  - TP Value (spinbutton)
  - Trim % (spinbutton)
  - "Add TP" button (multiple TP levels)
- Stop Loss:
  - Stop Loss Disabled (toggle)
  - Stop Loss Amount (spinbutton)
  - SL Unit (combobox)
  - SL Type (combobox)
- Averaging Down:
  - Average Down Amount (spinbutton)
  - Average Down Point (spinbutton)

**API Calls:**
- `GET /api/strategies/?val=DirStrat` (when selecting directional strategy)
- `GET /api/trades/tickers/?strat=` (get available symbols)
- `GET /api/trades/timeframes/?strat=` (get available timeframes)
- Expected: `POST /api/strategies/` (on submit)

---

### 4. Account Management (`/user/at/accnts`)

**Purpose:** Manage trading accounts

**Components:**
- Account count: "Account X Used / Unlimited"
- "+ Add Account" button
- Search accounts field
- Delete button (bulk)
- Clear Trade button (bulk)
- Account cards (one per account):
  - Account name
  - "Edit Account Credentials" button
  - "Refresh SubAccount" button (re-authenticates)
  - Subaccounts list with tags (e.g., "TAKEPROFIT647802407")

**API Calls:**
- `GET /api/accounts/get-all-at-accounts/`
- `GET /api/profiles/get-limits/`

**Actions:**
- Add Account → `/user/at/accntsetup`
- Edit Account Credentials (button)
- Refresh SubAccount (button)
- Delete (bulk action)
- Clear Trade (bulk action)

---

### 5. Add Account Setup (`/user/at/accntsetup`)

**Purpose:** Add new trading account

**Components:**
- "Enter Detail" heading
- "← Change Platform" button
- Platform selection (icons):
  - Tradovate
  - Webull
  - Tradier
  - Blofin
  - ProjectX
  - Rithmic

**Expected Form Fields (for Tradovate):**
- Username
- Password
- Client ID
- Client Secret
- Account Name (optional)

**API Calls:**
- Expected: `POST /api/accounts/add-tradovate/` (on submit)
- Expected: `POST /api/accounts/test-tradovate-connection/` (test button)

---

### 6. My Trader (`/user/at/strats`)

**Purpose:** Manage live trading strategies (different from My Recorders)

**Components:**
- "Create Strategy" button
- Search strategies field
- Strategy table (similar to My Recorders)
- Pagination

**API Calls:**
- `GET /api/strategies/?style=at`

**Note:** This appears to be for live trading strategies, while My Recorders is for demo/recording strategies.

---

### 7. Control Center (`/user/at/controls`)

**Purpose:** Manual trading interface

**Components:**
- Trading Form:
  - Strategy selector (combobox)
  - Ticker selector (combobox)
  - "Close" button (close form)
  - "Sell" button
  - Position Size (Qty) (spinbutton)
  - "Buy" button
- Bulk Actions:
  - "Close All" button
  - "Clear All" button
  - "Disable All Strat" button
- Strategy Toggles:
  - Multiple switches (on/off) for each strategy

**API Calls:**
- `GET /api/strategies/?manual=true`
- `GET /api/strategies/?style=at`
- `GET /api/trades/open/`
- `wss://trademanagergroup.com:5000/ws` (WebSocket for real-time updates)
- Expected: `POST /api/trades/execute/` (when clicking Buy/Sell)

**Real-time Features:**
- WebSocket connection for live updates
- Real-time position monitoring

---

### 8. Settings (`/user/settings`)

**Purpose:** User preferences and account settings

**Components:**

**Notifications:**
- Push Notification section:
  - Heading: "Push Notification"
  - "Disable Push Notification" button (toggle)

**Discord:**
- Discord DM section:
  - Heading: "Discord DM"
  - "Disable Discord DM" button (toggle)
  - "Discord Linked" link (with Discord icon)

**Account:**
- Sign Out link

**Profile:**
- Change Username:
  - Label: "Change Your Username"
  - Textbox
  - "Update" button

**Password:**
- Change Password:
  - "New Password" textbox (with strength indicator/progressbar)
  - "Confirm Password" textbox
  - "Change Password" button

**API Calls:**
- `GET /api/profiles/details/`
- Expected: `POST /api/profiles/update-username/`
- Expected: `POST /api/profiles/change-password/`
- Expected: `POST /api/profiles/toggle-push-notification/`
- Expected: `POST /api/profiles/toggle-discord-dm/`
- Expected: `GET /oauth/discord/callback/` (Discord OAuth)

---

## 🔄 User Workflows

### Workflow 1: Add Tradovate Account
1. Navigate to Account Management
2. Click "+ Add Account"
3. Select Tradovate platform
4. Fill form (username, password, client_id, client_secret)
5. Click "Test Connection" (optional)
6. Submit form
7. Account appears in list

### Workflow 2: Create Strategy for Recording
1. Navigate to My Recorders
2. Click "Create Strategy"
3. Fill form:
   - Strategy name
   - Strategy type
   - Position settings
   - TP/SL settings
4. Submit form
5. Strategy appears in list

### Workflow 3: Manual Trade from Control Center
1. Navigate to Control Center
2. Select strategy from dropdown
3. Select ticker from dropdown
4. Enter position size
5. Click "Buy" or "Sell"
6. Trade executes via API

### Workflow 4: View Strategy Performance
1. Navigate to Dashboard
2. Select filters (user, strategy, symbol, timeframe)
3. View trade history table
4. View performance charts
5. Analyze metrics

---

## 🗄️ Database Schema (Complete)

### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    discord_user_id TEXT,
    discord_access_token TEXT,
    discord_dms_enabled BOOLEAN DEFAULT 1,
    push_notifications_enabled BOOLEAN DEFAULT 1,
    admin BOOLEAN DEFAULT 0,
    access TEXT DEFAULT 'full',
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
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'Tradovate',
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
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### Subaccounts Table
```sql
CREATE TABLE subaccounts (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    active BOOLEAN DEFAULT 1,
    tags TEXT,  -- JSON array of tags
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### Strategies Table
```sql
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    account_id INTEGER,
    name TEXT NOT NULL,
    strat_type TEXT,  -- "Stock", "Futures", etc.
    days_to_expiry INTEGER,
    strike_offset REAL,
    position_size INTEGER DEFAULT 1,
    position_add INTEGER DEFAULT 1,
    take_profit REAL,
    stop_loss REAL,
    trim TEXT,  -- "All", "Partial"
    tpsl_units TEXT,  -- "Ticks", "Percent", "Dollars"
    directional_strategy TEXT,
    symbol TEXT,
    recording_enabled BOOLEAN DEFAULT 1,
    demo_account_id INTEGER,
    manual_trading_enabled BOOLEAN DEFAULT 0,  -- For Control Center
    active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (demo_account_id) REFERENCES accounts(id)
);
```

### Trades Table
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL,
    strategy_id INTEGER,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'buy' or 'sell'
    quantity INTEGER NOT NULL,
    price REAL,
    order_type TEXT,  -- 'market', 'limit', 'stop'
    status TEXT DEFAULT 'pending',  -- 'pending', 'filled', 'cancelled', 'rejected'
    tradovate_order_id TEXT,
    entry_price REAL,
    exit_price REAL,
    pnl REAL DEFAULT 0.0,
    usage_type TEXT,  -- 'recorder' or 'manual'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filled_at TIMESTAMP,
    closed_at TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
```

### Recorded Positions Table
```sql
CREATE TABLE recorded_positions (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    entry_timestamp TIMESTAMP NOT NULL,
    exit_price REAL,
    exit_timestamp TIMESTAMP,
    exit_reason TEXT,
    pnl REAL,
    pnl_percent REAL,
    stop_loss_price REAL,
    take_profit_price REAL,
    tradovate_order_id TEXT,
    tradovate_position_id TEXT,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

### Strategy Logs Table
```sql
CREATE TABLE strategy_logs (
    id INTEGER PRIMARY KEY,
    strategy_id INTEGER NOT NULL,
    log_type TEXT NOT NULL,
    message TEXT NOT NULL,
    data TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
```

---

## 🎨 UI Component Structure

### Navigation
- Sidebar with collapsible menu
- Top navigation bar
- User menu dropdown

### Common Components
- Modal dialogs
- Toast notifications
- Dropdown selectors
- Date picker
- Tables with pagination
- Toggle switches
- Buttons (primary, secondary, danger)

### Color Scheme
- Background: `#000000` (black)
- Background Dark: `#0f172a`
- Primary: `#2cc511` (green)
- Text Light: `#f2f2f2`
- Text Muted: `#ccc`
- Success: `#00f2c3`
- Error: `#ff4e4e`
- Warning: `#ff8d72`

---

## 🔐 Authentication & Security

### Session Management
- Flask/Django sessions
- Session cookie: `sessionid`
- CSRF token: `csrftoken`
- CSRF token in header: `X-CSRFToken`
- All POST/PUT/DELETE require CSRF token

### Request Format
```http
POST /api/endpoint/
Content-Type: application/json
X-CSRFToken: <csrf_token>
Cookie: sessionid=<session_id>; csrftoken=<csrf_token>

{
  "field1": "value1",
  "field2": "value2"
}
```

---

## 📡 WebSocket Integration

**Endpoint:** `wss://trademanagergroup.com:5000/ws`

**Purpose:** Real-time updates in Control Center
- Position updates
- Trade execution confirmations
- Strategy status changes

**Implementation:** Flask-SocketIO or Django Channels

---

## 🚀 Next Steps for Complete Extraction

### Immediate Actions Needed

1. **Capture POST Request Payloads:**
   - Fill out Add Account form → Submit → Capture POST body
   - Fill out Create Strategy form → Submit → Capture POST body
   - Click "Edit Account" → Modify → Capture PUT body
   - Click "Buy" in Control Center → Capture POST body

2. **Capture Response Formats:**
   - Intercept all GET responses
   - Document exact JSON structure
   - Note all field names and types

3. **Test All Interactions:**
   - Edit strategy
   - Delete strategy
   - Refresh subaccount
   - Toggle Discord DM
   - Change password
   - Update username

4. **Extract WebSocket Messages:**
   - Monitor WebSocket connection
   - Capture message formats
   - Document event types

---

## 📦 Deliverables Status

✅ **Completed:**
- Page navigation structure
- UI component mapping
- API endpoint discovery
- Database schema (inferred)
- Form field extraction
- Workflow documentation

⏳ **In Progress:**
- POST/PUT/DELETE request payloads
- Response format documentation
- WebSocket message formats

---

**This document will be continuously updated as we extract more information.**

