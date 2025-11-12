# New Endpoints Discovered

## ✅ Additional API Endpoints from Latest Extraction

**File**: `trade_manager_functionality__user_dashboard_1762408561408.json`  
**Date**: 2025-11-06

---

## 🔐 Authentication & System

### **POST /api/auth/login/** ⭐ CAPTURED!
**Purpose**: User login with reCAPTCHA  
**Request**:
```json
{
  "username": "J.T.M.J",
  "password": "Greens13",
  "captchaToken": "reCAPTCHA_v2_token"
}
```
**Response**:
```json
{
  "user": {
    "username": "J.T.M.J",
    "email": "just.trades.chicago@gmail.com",
    "admin": false,
    "DiscordID": "963881348039340122",
    "access": "full",
    "signed": true,
    "is_email_verified": true
  }
}
```
**Status**: 200 OK

**Key Points**:
- Requires reCAPTCHA v2 token
- Returns user object (no `success` flag)
- No `sessionId` in response (likely set via cookie)

---

### **GET /api/system/csrf-token** ⭐ NEW
**Purpose**: Get CSRF token for API requests  
**Response**:
```json
{
  "csrfToken": "token_value_here"
}
```
**Status**: 200 OK

**Usage**:
- Called on app initialization
- Token used in `X-CSRFToken` header for all POST/PUT/DELETE requests
- Prevents CSRF attacks

---

## 👤 Profile Management

### **GET /api/profiles/get-favorites** ⭐ NEW
**Purpose**: Get user's favorite strategies/tickers  
**Response**:
```json
{
  "favorites": [
    "VIX1",
    "JADIND30S",
    "JADEVOINDICATOR",
    // ... more favorites
  ]
}
```
**Status**: 200 OK

**Usage**:
- Loaded on dashboard initialization
- Used for quick access to favorite items
- May be used to pre-populate filters

---

### **GET /api/profiles/get-stat-config** ⭐ NEW
**Purpose**: Get dashboard statistics configuration  
**Response**: Array with 8 items (stat configuration objects)

**Status**: 200 OK

**Usage**:
- Loads user's dashboard widget preferences
- Configures which statistics to display
- Customizes dashboard layout

**Note**: Exact structure not captured, but returns array of config objects

---

### **POST /api/profiles/update-stat-config/** ⭐ NEW
**Purpose**: Update dashboard statistics configuration  
**Response**:
```json
{
  "message": "Configuration updated successfully"
}
```
**Status**: 200 OK

**Usage**:
- Saves user's dashboard customization
- Called when user changes widget preferences
- Updates which stats are displayed

---

## 📊 Complete Endpoint List

### Authentication:
- ✅ `GET /api/auth/check-auth/` - Check auth status
- ✅ `POST /api/auth/login/` - **Login (NEW - CAPTURED!)**
- ✅ `POST /api/auth/logout/` - Logout (expected, not captured)

### Dashboard:
- ✅ `GET /api/trades/` - Get all trades
- ✅ `GET /api/trades/open/` - Get open trades
- ✅ `GET /api/profiles/get-widget-info/` - Get widget stats
- ✅ `GET /api/profiles/get-favorites` - **Get favorites (NEW)**
- ✅ `GET /api/profiles/get-stat-config` - **Get stat config (NEW)**
- ✅ `POST /api/profiles/update-stat-config/` - **Update stat config (NEW)**

### Strategies:
- ✅ `GET /api/strategies/` - Get all strategies
- ✅ `GET /api/strategies/get-strat/` - Get single strategy
- ✅ `POST /api/strategies/update/` - Update strategy (enable/disable)
- ⚠️ `POST /api/strategies/` - Create strategy (expected, not captured)
- ⚠️ `PUT /api/strategies/:id/` - Full strategy update (expected, not captured)
- ⚠️ `DELETE /api/strategies/:id/` - Delete strategy (expected, not captured)

### Accounts:
- ✅ `GET /api/accounts/` - Get all accounts

### Trades:
- ✅ `GET /api/trades/tickers/` - Get available tickers
- ✅ `GET /api/trades/timeframes/` - Get available timeframes

### System:
- ✅ `GET /api/system/csrf-token` - **Get CSRF token (NEW)**

### Settings:
- ⚠️ `PUT /api/profiles/update-username/` - Update username (expected)
- ⚠️ `POST /api/profiles/change-password/` - Change password (expected)
- ⚠️ `POST /api/profiles/toggle-push-notification/` - Toggle push (expected)
- ⚠️ `POST /api/profiles/toggle-discord-dm/` - Toggle Discord DM (expected)

---

## 🎯 Summary

**Total New Endpoints**: 4  
**Login API**: ✅ Complete with request/response  
**CSRF Token**: ✅ Discovered  
**Profile Favorites**: ✅ Discovered  
**Stat Config**: ✅ Discovered (get & update)

**Remaining to Capture**:
- Strategy create/update/delete (form submissions)
- Settings form submissions (username, password, notifications)
- Account CRUD operations (REST API, not just WebSocket)

