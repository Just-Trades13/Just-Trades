# Tab Isolation Map

**CRITICAL**: When working on a specific tab, ONLY modify files listed for that tab. Do NOT touch files from other tabs.

---

## 🎯 Tab-to-Files Mapping

### 1. Account Management Tab (`/accounts`)
**Route**: `/accounts`  
**Template**: `templates/account_management.html`  
**Backend Endpoints** (in `ultra_simple_server.py`):
- `@app.route('/accounts')` - Page route
- `@app.route('/api/accounts', methods=['GET'])` - Get accounts
- `@app.route('/api/accounts', methods=['POST'])` - Create account
- `@app.route('/api/accounts/<int:account_id>/broker-selection')` - Broker selection
- `@app.route('/api/accounts/<int:account_id>/set-broker', methods=['POST'])` - Set broker
- `@app.route('/api/accounts/<int:account_id>/connect')` - Connect account
- `@app.route('/api/oauth/callback')` - OAuth callback
- `@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])` - Delete account
- `@app.route('/api/accounts/<int:account_id>/refresh-subaccounts', methods=['POST'])` - Refresh subaccounts
- `fetch_and_store_tradovate_accounts()` function

**Allowed Files**:
- ✅ `templates/account_management.html`
- ✅ `templates/broker_selection.html` (if exists)
- ✅ Account-related functions in `ultra_simple_server.py`
- ✅ OAuth-related functions in `ultra_simple_server.py`

**FORBIDDEN Files** (DO NOT MODIFY):
- ❌ `templates/manual_copy_trader.html`
- ❌ `templates/control_center.html`
- ❌ `templates/dashboard.html`
- ❌ Manual trader endpoints
- ❌ Control center endpoints
- ❌ Any other tab's files

---

### 2. Manual Trader / Copy Trader Tab (`/manual-trader`)
**Route**: `/manual-trader`  
**Template**: `templates/manual_copy_trader.html`  
**Backend Endpoints** (in `ultra_simple_server.py`):
- `@app.route('/manual-trader')` - Page route
- `@app.route('/api/manual-trade', methods=['POST'])` - Place manual trade
- `apply_risk_orders()` function
- `convert_tradingview_to_tradovate_symbol()` function
- `get_tick_size()` function
- `cancel_open_orders()` function

**Integration Files**:
- `phantom_scraper/tradovate_integration.py` - Order placement, position fetching, order cancellation methods

**Allowed Files**:
- ✅ `templates/manual_copy_trader.html`
- ✅ `/api/manual-trade` endpoint in `ultra_simple_server.py`
- ✅ Risk management functions in `ultra_simple_server.py`
- ✅ Order-related methods in `phantom_scraper/tradovate_integration.py`

**FORBIDDEN Files** (DO NOT MODIFY):
- ❌ `templates/account_management.html` - **LOCKED**
- ❌ `templates/control_center.html`
- ❌ Account management endpoints
- ❌ Control center endpoints
- ❌ Any other tab's files

---

### 3. Control Center Tab (`/control-center`)
**Route**: `/control-center`  
**Template**: `templates/control_center.html`  
**Backend Endpoints** (in `ultra_simple_server.py`):
- `@app.route('/control-center')` - Page route
- `@app.route('/api/live-strategies', methods=['GET'])` - Get live strategies
- AutoTrader-related endpoints

**Allowed Files**:
- ✅ `templates/control_center.html`
- ✅ Control center endpoints in `ultra_simple_server.py`
- ✅ Live strategies endpoints

**FORBIDDEN Files** (DO NOT MODIFY):
- ❌ `templates/account_management.html` - **LOCKED**
- ❌ `templates/manual_copy_trader.html`
- ❌ Manual trader endpoints
- ❌ Account management endpoints
- ❌ Any other tab's files

---

### 4. Dashboard Tab (`/dashboard`)
**Route**: `/dashboard`  
**Template**: `templates/dashboard.html`  
**Backend Endpoints** (in `ultra_simple_server.py`):
- `@app.route('/dashboard')` - Page route
- `@app.route('/api/dashboard/users', methods=['GET'])` - Get users
- `@app.route('/api/dashboard/strategies', methods=['GET'])` - Get strategies
- `@app.route('/api/dashboard/chart-data', methods=['GET'])` - Get chart data

**Allowed Files**:
- ✅ `templates/dashboard.html`
- ✅ Dashboard endpoints in `ultra_simple_server.py`

**FORBIDDEN Files** (DO NOT MODIFY):
- ❌ All other tab templates
- ❌ All other tab endpoints
- ❌ Account management (LOCKED)
- ❌ Manual trader
- ❌ Control center

---

### 5. Strategies Tab (`/strategies`)
**Route**: `/strategies`  
**Template**: `templates/strategies.html`  
**Backend Endpoints** (in `ultra_simple_server.py`):
- `@app.route('/strategies')` - Page route
- `@app.route('/api/strategies', methods=['GET'])` - Get strategies

**Allowed Files**:
- ✅ `templates/strategies.html`
- ✅ Strategy endpoints in `ultra_simple_server.py`

**FORBIDDEN Files** (DO NOT MODIFY):
- ❌ All other tab templates
- ❌ All other tab endpoints

---

### 6. Recorders Tab (`/recorders`)
**Route**: `/recorders`, `/recorders/new`, `/recorders/<id>`  
**Templates**: `templates/recorders.html`, `templates/recorders_list.html`  
**Backend Endpoints** (in `ultra_simple_server.py`):
- `@app.route('/recorders', methods=['GET'])` - List recorders
- `@app.route('/recorders/new')` - New recorder
- `@app.route('/recorders/<int:recorder_id>')` - Recorder detail

**Allowed Files**:
- ✅ `templates/recorders.html`
- ✅ `templates/recorders_list.html`
- ✅ Recorder endpoints in `ultra_simple_server.py`

**FORBIDDEN Files** (DO NOT MODIFY):
- ❌ All other tab templates
- ❌ All other tab endpoints

---

### 7. Traders Tab (`/traders`)
**Route**: `/traders`, `/traders/new`, `/traders/<id>`  
**Templates**: `templates/traders.html` (or similar)  
**Backend Endpoints** (in `ultra_simple_server.py`):
- `@app.route('/traders')` - List traders
- `@app.route('/traders/new')` - New trader
- `@app.route('/traders/<int:trader_id>')` - Trader detail

**Allowed Files**:
- ✅ Trader templates
- ✅ Trader endpoints in `ultra_simple_server.py`

**FORBIDDEN Files** (DO NOT MODIFY):
- ❌ All other tab templates
- ❌ All other tab endpoints

---

### 8. Settings Tab (`/settings`)
**Route**: `/settings`  
**Template**: `templates/settings.html`  
**Backend Endpoints** (in `ultra_simple_server.py`):
- `@app.route('/settings')` - Page route
- Settings-related endpoints

**Allowed Files**:
- ✅ `templates/settings.html`
- ✅ Settings endpoints in `ultra_simple_server.py`

**FORBIDDEN Files** (DO NOT MODIFY):
- ❌ All other tab templates
- ❌ All other tab endpoints

---

## 🚨 SHARED FILES (Handle with Extreme Caution)

These files are used by multiple tabs. **ONLY modify if explicitly requested**:

### `templates/layout.html`
- **Used by**: ALL tabs
- **Rule**: Only modify if user explicitly requests layout changes
- **Risk**: Breaking all tabs

### `ultra_simple_server.py` - Shared Functions
- **Used by**: Multiple tabs
- **Rule**: Only modify shared functions if explicitly requested
- **Examples**: Database initialization, utility functions

### `phantom_scraper/tradovate_integration.py` - Core Methods
- **Used by**: Manual trader, account management
- **Rule**: Only modify if explicitly requested
- **Risk**: Breaking multiple tabs

### Static Files (`static/`)
- **Used by**: ALL tabs
- **Rule**: Only modify if explicitly requested
- **Risk**: Breaking styling across all tabs

---

## ✅ Isolation Rules

### When Working on a Tab:

1. **IDENTIFY the tab** you're working on
2. **CHECK this map** for allowed files
3. **ONLY modify** files listed for that tab
4. **DO NOT modify** files from other tabs
5. **WARN user** if you need to modify shared files
6. **ASK permission** before touching forbidden files

### Red Flags - STOP IMMEDIATELY:

- 🔴 User says "work on account management" but you're about to modify manual trader
- 🔴 User says "fix control center" but you're about to modify account management
- 🔴 You're about to modify a file not listed in the tab's allowed files
- 🔴 You're about to modify a shared file without explicit permission
- 🔴 You're about to "improve" code in another tab "while you're at it"

---

## 📝 Example Workflows

### Example 1: Working on Manual Trader
```
User: "Fix the trailing stop in manual trader"

✅ ALLOWED:
- templates/manual_copy_trader.html
- /api/manual-trade endpoint
- apply_risk_orders() function
- tradovate_integration.py order methods

❌ FORBIDDEN:
- templates/account_management.html (LOCKED)
- templates/control_center.html
- Account management endpoints
```

### Example 2: Working on Account Management
```
User: "Add a feature to account management"

✅ ALLOWED:
- templates/account_management.html (if user explicitly approves)
- Account management endpoints
- OAuth endpoints

❌ FORBIDDEN:
- templates/manual_copy_trader.html
- Manual trader endpoints
- Control center files
```

---

## 🛡️ Protection Checklist

Before modifying ANY file:
- [ ] Which tab am I working on?
- [ ] Is this file listed in that tab's allowed files?
- [ ] Is this file in another tab's forbidden list?
- [ ] Is this a shared file? (If yes, ask permission)
- [ ] Am I about to modify a file from another tab?
- [ ] Have I warned the user if touching shared files?

---

**Last Updated**: December 2025  
**Status**: Active - All AI assistants must follow this map

