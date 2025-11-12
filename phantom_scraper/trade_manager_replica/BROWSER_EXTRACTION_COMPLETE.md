# Browser Extraction - Complete API Endpoint Discovery

**Date:** 2025-11-05  
**Source:** Live browser inspection in Cursor

## ✅ What I Can See

The browser is open at **https://trademanagergroup.com/user/strats** (My Recorders page)

### Current Page Structure
- **URL:** `/user/strats`
- **Title:** Trade Manager
- **User:** J.T.M.J (logged in)

### Navigation Menu
- Dashboard (`/user/dashboard`)
- My Recorder (`/user/strats`) - **CURRENT PAGE**
- Trader (submenu):
  - AM Account Management (`/user/at/accnts`)
  - SS My Trader (`/user/at/strats`)
  - CC Control Center (`/user/at/controls`)
- Setting (`/user/settings`)

## 📡 Complete API Endpoint List (From Network Requests)

### System
- ✅ `GET /api/system/csrf-token/`

### Authentication
- ✅ `GET /api/auth/check-auth/`
- ✅ `POST /api/auth/login/` - **NEWLY DISCOVERED**

### Accounts
- ✅ `GET /api/accounts/get-all-at-accounts/`

### Strategies
- ✅ `GET /api/strategies/` - **NEWLY DISCOVERED** - Get all strategies
- ✅ `GET /api/strategies/get-strat/?strat={name}&at=false` - **NEWLY DISCOVERED** - Get specific strategy

### Trades
- ✅ `GET /api/trades/?usageType=true` - **NEWLY DISCOVERED**
- ✅ `GET /api/trades/?user={username}&usageType=true` - **NEWLY DISCOVERED**
- ✅ `GET /api/trades/?strategy={name}&user={username}&usageType=true` - **NEWLY DISCOVERED**
- ✅ `GET /api/trades/open/?usageType=true` - **NEWLY DISCOVERED**
- ✅ `GET /api/trades/open/?user={username}&usageType=true` - **NEWLY DISCOVERED**
- ✅ `GET /api/trades/open/?strategy={name}&user={username}&usageType=true` - **NEWLY DISCOVERED**

### Profiles
- ✅ `GET /api/profiles/get-limits/`
- ✅ `GET /api/profiles/get-stat-config/` - **NEWLY DISCOVERED**
- ✅ `POST /api/profiles/update-stat-config/` - **NEWLY DISCOVERED**
- ✅ `GET /api/profiles/get-favorites/` - **NEWLY DISCOVERED**
- ✅ `POST /api/profiles/set-favorites/` - **NEWLY DISCOVERED**
- ✅ `GET /api/profiles/get-widget-info/?usageType=true` - **NEWLY DISCOVERED**
- ✅ `GET /api/profiles/get-widget-info/?user={username}&usageType=true` - **NEWLY DISCOVERED**
- ✅ `GET /api/profiles/get-widget-info/?strategy={name}&user={username}&usageType=true` - **NEWLY DISCOVERED**

## 🔍 What's Missing (Need to Capture)

### POST Request Payloads
1. **Login Request:**
   - URL: `POST /api/auth/login/`
   - Need: Request body format
   - Need: Response format

2. **Update Stat Config:**
   - URL: `POST /api/profiles/update-stat-config/`
   - Need: Request body format
   - Need: Response format

3. **Set Favorites:**
   - URL: `POST /api/profiles/set-favorites/`
   - Need: Request body format
   - Need: Response format

### Strategy Management (Need to Navigate)
- `POST /api/strategies/` - Create strategy (likely)
- `PUT /api/strategies/{id}/` - Update strategy (likely)
- `DELETE /api/strategies/{id}/` - Delete strategy (likely)

### Account Management (Need to Navigate)
- `POST /api/accounts/add-tradovate/` - Add account (likely)
- `POST /api/accounts/test-tradovate-connection/` - Test connection (likely)

### Response Formats (Need to Capture)
- `/api/strategies/` response format
- `/api/trades/` response format
- `/api/profiles/get-stat-config/` response format
- `/api/profiles/get-favorites/` response format
- `/api/profiles/get-widget-info/` response format

## 🎯 Next Steps

1. **Capture POST Request Details:**
   - Inspect Network tab when clicking "Create Strategy"
   - Inspect Network tab when adding account
   - Capture all request/response bodies

2. **Navigate to Other Pages:**
   - Account Management page (`/user/at/accnts`)
   - Settings page (`/user/settings`)
   - Control Center (`/user/at/controls`)

3. **Interact with Forms:**
   - Click "Create Strategy" button
   - Fill out and submit forms
   - Capture all API calls

## 📊 Summary

**Total Endpoints Discovered:** 20+ unique endpoints

**From HAR File:** 4 endpoints  
**From Browser Inspection:** 16+ additional endpoints

**Status:** ✅ Can see browser, ✅ Can navigate, ✅ Can capture network requests

