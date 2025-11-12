# Trade Manager API Endpoints - Discovered from Browser

**Date:** 2025-11-05  
**Source:** Live browser network inspection

## 🔍 New Endpoints Discovered

### Authentication
- ✅ `POST /api/auth/login/` - **NEW!** (was missing from HAR)

### Trades
- ✅ `GET /api/trades/` - **NEW!** Get all trades
- ✅ `GET /api/trades/open/` - **NEW!** Get open trades
- ✅ `GET /api/trades/?user={username}` - **NEW!** Filter by user
- ✅ `GET /api/trades/?strategy={name}` - **NEW!** Filter by strategy
- ✅ `GET /api/trades/?usageType=true` - **NEW!** With usage type

### Strategies
- ✅ `GET /api/strategies/` - **NEW!** Get all strategies
- ✅ `GET /api/strategies/get-strat/?strat={name}&at=false` - **NEW!** Get specific strategy

### Profiles
- ✅ `GET /api/profiles/get-stat-config/` - **NEW!** Get stats configuration
- ✅ `POST /api/profiles/update-stat-config/` - **NEW!** Update stats config
- ✅ `GET /api/profiles/get-favorites/` - **NEW!** Get favorites
- ✅ `POST /api/profiles/set-favorites/` - **NEW!** Set favorites
- ✅ `GET /api/profiles/get-widget-info/?usageType=true` - **NEW!** Get widget info
- ✅ `GET /api/profiles/get-widget-info/?user={username}` - **NEW!** Get widget info by user
- ✅ `GET /api/profiles/get-widget-info/?strategy={name}` - **NEW!** Get widget info by strategy

## 📋 Complete Endpoint List

### System
- `GET /api/system/csrf-token/` ✅ (from HAR)

### Authentication
- `GET /api/auth/check-auth/` ✅ (from HAR)
- `POST /api/auth/login/` ✅ **NEW!**

### Accounts
- `GET /api/accounts/get-all-at-accounts/` ✅ (from HAR)

### Trades
- `GET /api/trades/` ✅ **NEW!**
- `GET /api/trades/?usageType=true` ✅ **NEW!**
- `GET /api/trades/?user={username}&usageType=true` ✅ **NEW!**
- `GET /api/trades/?strategy={name}&user={username}&usageType=true` ✅ **NEW!**
- `GET /api/trades/open/` ✅ **NEW!**
- `GET /api/trades/open/?usageType=true` ✅ **NEW!**
- `GET /api/trades/open/?user={username}&usageType=true` ✅ **NEW!**
- `GET /api/trades/open/?strategy={name}&user={username}&usageType=true` ✅ **NEW!**

### Strategies
- `GET /api/strategies/` ✅ **NEW!**
- `GET /api/strategies/get-strat/?strat={name}&at=false` ✅ **NEW!**

### Profiles
- `GET /api/profiles/get-limits/` ✅ (from HAR)
- `GET /api/profiles/get-stat-config/` ✅ **NEW!**
- `POST /api/profiles/update-stat-config/` ✅ **NEW!**
- `GET /api/profiles/get-favorites/` ✅ **NEW!**
- `POST /api/profiles/set-favorites/` ✅ **NEW!**
- `GET /api/profiles/get-widget-info/?usageType=true` ✅ **NEW!**
- `GET /api/profiles/get-widget-info/?user={username}&usageType=true` ✅ **NEW!**
- `GET /api/profiles/get-widget-info/?strategy={name}&user={username}&usageType=true` ✅ **NEW!**

## 🔄 Next Steps

1. **Capture POST Request Payloads:**
   - Need to inspect `/api/auth/login/` POST body
   - Need to inspect `/api/profiles/update-stat-config/` POST body
   - Need to inspect `/api/profiles/set-favorites/` POST body

2. **Capture Response Formats:**
   - Need to see response from `/api/trades/`
   - Need to see response from `/api/strategies/`
   - Need to see response from `/api/profiles/get-stat-config/`

3. **Test Other Pages:**
   - Navigate to "My Recorders" to find strategy endpoints
   - Navigate to "Account Management" to find account endpoints
   - Navigate to "Settings" to find settings endpoints

