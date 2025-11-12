# Complete Site Extraction Log - Trade Manager → Just.Trades

**Started:** 2025-11-05  
**Goal:** Extract every aspect of trademanagergroup.com for exact replica

---

## 📊 Progress Summary

### Pages Extracted ✅
1. **Dashboard** (`/user/dashboard`) - ✅ Complete
2. **My Recorders** (`/user/strats`) - ✅ Complete  
3. **Create Strategy** (`/user/strat`) - ✅ Complete
4. **Account Management** (`/user/at/accnts`) - ✅ Complete
5. **Add Account Setup** (`/user/at/accntsetup`) - 🔄 In Progress

### Pages Remaining ⏳
1. **My Trader** (`/user/at/strats`) - Need to extract
2. **Control Center** (`/user/at/controls`) - Need to extract
3. **Settings** (`/user/settings`) - Need to extract

---

## 🔍 API Endpoints Discovered (20+)

### System & Auth
- `GET /api/system/csrf-token/`
- `GET /api/auth/check-auth/`
- `POST /api/auth/login/`

### Accounts
- `GET /api/accounts/get-all-at-accounts/`
- Expected: `POST /api/accounts/add-tradovate/` (need to capture)
- Expected: `PUT /api/accounts/{id}/` (need to capture)
- Expected: `DELETE /api/accounts/{id}/` (need to capture)
- Expected: `POST /api/accounts/{id}/refresh/` (need to capture)

### Strategies
- `GET /api/strategies/`
- `GET /api/strategies/?val=DirStrat`
- `GET /api/strategies/get-strat/?strat={name}&at=false`
- Expected: `POST /api/strategies/` (need to capture)
- Expected: `PUT /api/strategies/{id}/` (need to capture)
- Expected: `DELETE /api/strategies/{id}/` (need to capture)

### Trades
- `GET /api/trades/`
- `GET /api/trades/?usageType=true`
- `GET /api/trades/?user={username}&usageType=true`
- `GET /api/trades/?strategy={name}&user={username}&usageType=true`
- `GET /api/trades/open/`
- `GET /api/trades/open/?usageType=true`
- `GET /api/trades/open/?user={username}&usageType=true`
- `GET /api/trades/open/?strategy={name}&user={username}&usageType=true`
- `GET /api/trades/tickers/?strat=`
- `GET /api/trades/timeframes/?strat=`

### Profiles
- `GET /api/profiles/get-limits/`
- `GET /api/profiles/get-stat-config/`
- `POST /api/profiles/update-stat-config/`
- `GET /api/profiles/get-favorites/`
- `POST /api/profiles/set-favorites/`
- `GET /api/profiles/get-widget-info/?usageType=true`
- `GET /api/profiles/get-widget-info/?user={username}&usageType=true`
- `GET /api/profiles/get-widget-info/?strategy={name}&user={username}&usageType=true`

---

## 📝 Form Structures Discovered

### Create Strategy Form (`/user/strat`)
**Fields:**
- Strategy Name (textbox)
- Strategy Type (combobox - "Stock", etc.)
- Directional Strategy (combobox)
- Initial Position Size (spinbutton)
- Add Position Size (spinbutton)
- Take Profit Settings:
  - TP Unit (combobox)
  - Trim Unit (combobox)
  - TP Value (spinbutton)
  - Trim % (spinbutton)
  - Add TP button
- Stop Loss Settings:
  - Stop Loss Disabled (toggle)
  - Stop Loss Amount (spinbutton)
  - SL Unit (combobox)
  - SL Type (combobox)
- Averaging Down (disabled section)

### Add Account Form (`/user/at/accntsetup`)
**Status:** 🔄 Currently extracting form fields
**Components:**
- "Enter Detail" heading
- "← Change Platform" button
- Platform selection (icons visible: Tradovate, Webull, Tradier, Blofin, ProjectX, Rithmic)

---

## 🎯 Next Actions

### Immediate
1. ✅ Extract Add Account form fields completely
2. ⏳ Fill out and submit Add Account form → Capture POST request
3. ⏳ Navigate to My Trader page
4. ⏳ Navigate to Control Center
5. ⏳ Navigate to Settings

### Form Interactions Needed
1. **Add Account:**
   - Fill form
   - Click "Test Connection" (if exists)
   - Submit form
   - Capture POST payload

2. **Create Strategy:**
   - Fill form completely
   - Submit form
   - Capture POST payload

3. **Edit Account:**
   - Click "Edit Account Credentials"
   - Modify fields
   - Submit
   - Capture PUT payload

4. **Delete Account:**
   - Click delete
   - Confirm
   - Capture DELETE request

---

## 📦 Files Created

1. `TRADE_MANAGER_REVERSE_ENGINEERING.md` - Initial analysis
2. `DISCOVERED_API_ENDPOINTS.md` - API endpoints list
3. `CREATE_STRATEGY_FORM.md` - Strategy form fields
4. `ACCOUNT_MANAGEMENT_EXTRACTION.md` - Account page structure
5. `COMPLETE_SITE_EXTRACTION_PLAN.md` - Extraction checklist
6. `EXTRACTION_PROGRESS.json` - Progress tracking

---

## 🔄 Continuous Extraction

This document will be updated as we extract more information from the site.

