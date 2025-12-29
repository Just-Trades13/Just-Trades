# Trade Manager - COMPLETE SYSTEMATIC AUDIT
**Date:** December 29, 2025
**Method:** Page-by-page, element-by-element analysis

---

## 🔍 AUDIT PLAN

### Pages to Audit:
1. ✅ Dashboard (`/user/dashboard`)
2. ⏳ My Recorders (`/user/recorders`)
3. ⏳ My Traders (`/user/traders`)
4. ⏳ Account Management (`/user/account-management`)
5. ⏳ Control Center (`/user/at/controls`)
6. ⏳ Settings (`/user/settings`)
7. ⏳ Strategy Creation/Edit (modal/page)
8. ⏳ Trader Creation/Edit (modal/page)
9. ⏳ Account Setup (Tradovate/Webull/Robinhood)

### Elements to Check on Each Page:
- [ ] All buttons and their actions
- [ ] All form fields and dropdowns
- [ ] All toggles and switches
- [ ] All modals and dialogs
- [ ] All navigation links
- [ ] All data displays
- [ ] All filters and search
- [ ] All API endpoints called
- [ ] All JavaScript functions
- [ ] All UI components

---

## 📋 PAGE-BY-PAGE AUDIT

### 1. DASHBOARD (`/user/dashboard`)

**Status:** ⏳ IN PROGRESS

#### Navigation Elements:
- [ ] Dashboard link
- [ ] My Recorder link
- [ ] Trader dropdown (Account Management, My Trader, Control Center)
- [ ] Settings link
- [ ] User profile menu

#### Main Content:
- [ ] Viewing filter (Recorded Strats?)
- [ ] Date range filter
- [ ] Strategy filter
- [ ] User filter
- [ ] Metrics display (P&L, Win Rate, etc.)
- [ ] Charts/graphs
- [ ] Tables/lists
- [ ] Action buttons

#### API Calls:
- [ ] `/api/trades/?usageType=true`
- [ ] `/api/trades/open/?usageType=true`
- [ ] `/api/profiles/get-stat-config/`
- [ ] `/api/profiles/get-favorites/`
- [ ] `/api/profiles/get-widget-info/?usageType=true`

---

### 2. MY RECORDERS (`/user/recorders`)

**Status:** ⏳ PENDING

#### Elements to Check:
- [ ] Create Strategy button
- [ ] Strategy list table
- [ ] Edit button for each strategy
- [ ] Delete/Remove button
- [ ] Refresh button
- [ ] Strategy details modal
- [ ] Form fields:
  - [ ] Strategy name
  - [ ] Position size
  - [ ] Position add
  - [ ] Take profit
  - [ ] Stop loss
  - [ ] TPSL units (Ticks/Percent)
  - [ ] Symbol
  - [ ] Direction
  - [ ] Time filters
  - [ ] Signal cooldown
  - [ ] Max signals
  - [ ] Max daily loss
  - [ ] Max contracts
  - [ ] Signal delay
  - [ ] Recording enabled toggle
  - [ ] Demo account selection
  - [ ] Webhook token
  - [ ] Private/Public toggle
- [ ] Logs section
- [ ] Performance metrics

---

### 3. MY TRADERS (`/user/traders`)

**Status:** ⏳ PENDING

#### Elements to Check:
- [ ] Create Trader button
- [ ] Trader list
- [ ] Edit/Delete buttons
- [ ] Enable/Disable toggle
- [ ] Form fields:
  - [ ] Recorder selection
  - [ ] Account selection
  - [ ] Subaccount selection
  - [ ] Risk overrides
  - [ ] Position size override
  - [ ] TP/SL overrides
  - [ ] Time filter overrides
  - [ ] Enabled accounts (multi-select)

---

### 4. ACCOUNT MANAGEMENT (`/user/account-management`)

**Status:** ⏳ PENDING

#### Elements to Check:
- [ ] Add Account button
- [ ] Account list
- [ ] Platform selection (Tradovate/Webull/Robinhood)
- [ ] Account setup forms:
  - [ ] Tradovate: Username, Password, Client ID, Secret
  - [ ] Webull: API credentials
  - [ ] Robinhood: Token extraction
- [ ] Test Connection button
- [ ] Edit Account
- [ ] Delete Account
- [ ] Enable/Disable toggle
- [ ] Subaccount management
- [ ] Refresh token button

---

### 5. CONTROL CENTER (`/user/at/controls`)

**Status:** ⏳ PENDING

#### Elements to Check:
- [ ] Manual Trader Panel
- [ ] Live Trading Panel
- [ ] Close All button
- [ ] Clear All button
- [ ] Disable All Strats button
- [ ] Strategy table:
  - [ ] Strategy name
  - [ ] Enable toggle
  - [ ] P/L display
  - [ ] Show/Hide button
  - [ ] Close button
  - [ ] Clear button
- [ ] AutoTrader Logs panel
- [ ] WebSocket connection status
- [ ] Log entry format
- [ ] Color coding

---

### 6. SETTINGS (`/user/settings`)

**Status:** ⏳ PENDING

#### Elements to Check:
- [ ] Profile settings
- [ ] Discord integration:
  - [ ] Link Discord button
  - [ ] Enable/Disable DMs toggle
- [ ] Email verification
- [ ] Password change
- [ ] Account limits display
- [ ] Notification preferences
- [ ] API keys management

---

### 7. STRATEGY CREATION/EDIT

**Status:** ⏳ PENDING

#### Elements to Check:
- [ ] Modal or separate page
- [ ] Strategy name input
- [ ] Signal source selection:
  - [ ] TradingView
  - [ ] Telegram
  - [ ] Discord
  - [ ] Manual
- [ ] Strategy builder (if manual):
  - [ ] Ticker extraction rules
  - [ ] Price extraction rules
  - [ ] Direction rules (Buy/Sell)
  - [ ] Filter rules (Take the Trade)
  - [ ] Rule combinators (AND/OR)
- [ ] Position settings
- [ ] Risk settings
- [ ] Time filters
- [ ] Save/Cancel buttons

---

### 8. TRADER CREATION/EDIT

**Status:** ⏳ PENDING

#### Elements to Check:
- [ ] Recorder selection dropdown
- [ ] Account selection
- [ ] Risk override options
- [ ] Enable/Disable toggle
- [ ] Multi-account selection

---

## 🔍 FEATURE DISCOVERY CHECKLIST

### Risk Management Features:
- [ ] Direction filter (Long/Short/Both)
- [ ] Time filter #1 (start/stop)
- [ ] Time filter #2 (start/stop)
- [ ] Signal cooldown (seconds)
- [ ] Max signals per session
- [ ] Max daily loss
- [ ] Max contracts per trade
- [ ] Signal delay (Nth signal)
- [ ] Rule combinators (AND/OR)
- [ ] "Take the Trade" filters

### Order Management Features:
- [ ] Market orders
- [ ] Limit orders
- [ ] Stop orders
- [ ] Bracket orders
- [ ] DCA (Average Down)
- [ ] Partial exits (Trim)
- [ ] Multiple TP targets
- [ ] TP/SL units (Ticks/Points/Percent)
- [ ] GTC orders
- [ ] Position reconciliation

### Signal Source Features:
- [ ] TradingView webhooks
- [ ] Telegram scraper
- [ ] Discord scraper
- [ ] Manual strategy builder
- [ ] Regex parsing
- [ ] Signal extraction rules

### Broker Features:
- [ ] Tradovate integration
- [ ] Webull integration
- [ ] Robinhood integration
- [ ] OAuth authentication
- [ ] API key authentication
- [ ] Subaccount support
- [ ] Token refresh

### UI/UX Features:
- [ ] Push notifications
- [ ] Bulk actions
- [ ] Color-coded logs
- [ ] Loading states
- [ ] Error handling
- [ ] Toast notifications
- [ ] Real-time updates
- [ ] Trade history
- [ ] Performance analytics

---

## 📊 API ENDPOINT DISCOVERY

### Authentication:
- [ ] `/api/auth/check-auth/`
- [ ] `/api/auth/login/`
- [ ] `/api/auth/logout/`
- [ ] `/api/system/csrf-token/`

### Strategies:
- [ ] `/api/strategies/`
- [ ] `/api/strategies/?style=at`
- [ ] `/api/strategies/?manual=true`
- [ ] `/api/strategies/update/`
- [ ] `/api/strategies/{id}/`

### Trades:
- [ ] `/api/trades/open/`
- [ ] `/api/trades/?usageType=true`
- [ ] `/api/trades/history/`
- [ ] `/api/trades/close/`

### Accounts:
- [ ] `/api/accounts/get-all-at-accounts/`
- [ ] `/api/accounts/`
- [ ] `/api/accounts/add-tradovate/`
- [ ] `/api/accounts/test-tradovate-connection/`

### Scrapers:
- [ ] `/api/scraper/create/`
- [ ] `/api/scraper/get_scraper`
- [ ] `/api/scraper/telegram/start-login/`
- [ ] `/api/scraper/telegram/verify-code/`
- [ ] `/api/scraper/telegram/messages`
- [ ] `/api/scraper/discord/`

### Profiles:
- [ ] `/api/profiles/get-limits/`
- [ ] `/api/profiles/get-stat-config/`
- [ ] `/api/profiles/get-favorites/`
- [ ] `/api/profiles/get-widget-info/`
- [ ] `/api/profiles/set-telegram-api/`
- [ ] `/api/profiles/update-stat-config/`

### System:
- [ ] `/api/system/save-fcm-token/`

---

## 🎯 SYSTEMATIC EXPLORATION IN PROGRESS...

*This document will be updated as I go through each page systematically*
