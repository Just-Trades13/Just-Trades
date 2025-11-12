# Login API Analysis

## ✅ Success! Login API Call Captured

**File**: `trade_manager_functionality__user_dashboard_1762408561408.json`  
**Page**: `/auth/login` (but redirected to dashboard after login)  
**Timestamp**: 2025-11-06T05:55:40.273Z

**Total API Calls**: 13  
**Form Submissions**: 1

---

## 📡 Login API Endpoint

### **POST /api/auth/login/**

**Purpose**: Authenticate user and create session

**Request Body**:
```json
{
  "username": "J.T.M.J",
  "password": "Greens13",
  "captchaToken": "0cAFcWeA7Ygv5MIzr7-GLda8Wi1C_lJZjBMfbUAGFYqjhwAnxDfRWv_MncwPI-7fcRs2pPvgHI77JCBMuLZrLv58xB1NPrj95yv5nx8YoVfdocsjIsd7N5bLTD31QJPZpKT8-F1QXyCJcarA09WR0TzUpzSPB4hlvgeWx1klEIZR6t9D2Q5772RdDM4MT6GTFvGKmkIAomzalMDOBomqk3S4wBCirWjEsKeEFjXcJaOH2sJk0Z6ZMNTgnvwf1YiCrkxsikNV7qmCyKkHFfSB3BMNntXblZb-laRc15Rs4ndJNnTqW3UcXK2NRHlssUQ3464cdN1JJJQ8PIjF3kKUlhPIvQKStK46bLFzM8usLITuoqnR-KgMBqWT3bVrWSxUpFMHXh5UgTS6Oox3QLpDudQU-sXcI8hPuUHw-4mCFcmZkevNjJRAcgQ9ai4_Robj0tol3iNAWeVVpnTUznzOU1uxgkIT8JG8kBAO4wOV3OMjfxOODUfAwDQCSSrazFSslFcHaovb4BhwmyESPy2pMecufkYI16KckqfQma9ZpSDgJCw9pHHU5t0tnlRGUa2PxZoAKc0FAbyPUUyzSN2AWHGttlnydkfXFZa0qLYWKXqi6Sc4cYaDP-VWql_YZuoTcK4h-moy-AegQ6QiCjpkwYUqJO88xnFveRcPGOCb1xjx40CAzjYcVyH7ib4qemUtSDDmL-6trGpfSCz-3EE4tQsDlVW1XdZPLxeXkZPurV-Rc7nqqv7XgtYW1fZqyBIB5TqsWrXAW0ze3gEeNl9yEYA47fH2EuEXp1eCep2fGDgpZhJ80a6xuLKMIMc-liF6cLU9TG5lAxc9a21X1svtOMIsG_crYFBQZuNzLHUX4Go55wXTB5OF6kzPCVwP8UK2gocE7tezYrt176FTWN..."
}
```

**Key Fields**:
- `username`: User's username or email
- `password`: Plain text password (sent over HTTPS)
- `captchaToken`: reCAPTCHA v2 token (required for login)

**Success Response (200)**:
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

**Note**: Response does NOT include `sessionId` in this call (it may be set via cookie or subsequent auth check)

**Status**: 200 OK

**Key Insights**:
- ✅ **reCAPTCHA Required**: Login requires valid reCAPTCHA token
- ✅ **Session Management**: After successful login, user is redirected to dashboard
- ✅ **No `success` flag**: Response directly contains `user` object (not wrapped in `{success: true, user: {...}}`)
- ✅ **No `sessionId` in response**: Likely set via HTTP-only cookie or retrieved via subsequent auth check

---

## 🔍 Additional Endpoints Discovered

### 1. **GET /api/system/csrf-token**
**Purpose**: Get CSRF token for API requests  
**Response**:
```json
{
  "csrfToken": "token_value"
}
```
**Status**: 200 OK

**Key Insights**:
- Called before login to get CSRF token
- Token is used in subsequent API requests (via `X-CSRFToken` header)

---

### 2. **GET /api/profiles/get-favorites**
**Purpose**: Get user's favorite strategies/tickers  
**Response**:
```json
{
  "favorites": [
    "VIX1",
    "JADIND30S",
    "JADEVOINDICATOR"
    // ... more favorites
  ]
}
```
**Status**: 200 OK

**Key Insights**:
- Returns array of favorite strategy/ticker names
- Used for dashboard quick access or pre-population

---

### 3. **GET /api/profiles/get-stat-config**
**Purpose**: Get dashboard statistics configuration  
**Response**: Array with 8 items (stat configuration objects)

**Status**: 200 OK

**Key Insights**:
- Returns configuration for dashboard statistics/widgets
- Used to configure which stats to display and how

---

### 4. **POST /api/profiles/update-stat-config/**
**Purpose**: Update dashboard statistics configuration  
**Request Body**: (Not shown in extraction, but likely contains stat config updates)

**Response**:
```json
{
  "message": "Configuration updated successfully"
}
```
**Status**: 200 OK

**Key Insights**:
- Used to save user's dashboard widget preferences
- Called when user customizes dashboard statistics

---

## 🔄 Login Flow Sequence

1. **Page Load**:
   - `GET /api/system/csrf-token` - Get CSRF token

2. **User Submits Login Form**:
   - `POST /api/auth/login/` - Authenticate with username, password, and captcha token

3. **After Successful Login** (redirected to dashboard):
   - `GET /api/auth/check-auth/` - Verify authentication (2 calls)
   - `GET /api/profiles/get-favorites` - Load favorites (3 calls)
   - `GET /api/profiles/get-stat-config` - Load stat config
   - `GET /api/profiles/get-widget-info/?usageType=true` - Load widget info
   - `GET /api/trades/?usageType=true` - Load trades
   - `GET /api/trades/open/?usageType=true` - Load open trades
   - `POST /api/profiles/update-stat-config/` - Update stat config (if user made changes)

---

## 🔧 Implementation Notes

### Current Login Component:
- Component exists (`Login.jsx`)
- Missing: reCAPTCHA integration
- Missing: CSRF token handling
- Missing: Exact API request structure

### Required Updates:

1. **Add reCAPTCHA Integration**:
   - Install `react-google-recaptcha` or similar
   - Add reCAPTCHA site key to environment variables
   - Get reCAPTCHA token before submitting login
   - Include token in login request

2. **Update Login API Call** (`frontend/src/services/api.js`):
   ```javascript
   authAPI: {
     login: async (username, password, captchaToken) => {
       return axios.post('/api/auth/login/', {
         username,
         password,
         captchaToken
       });
     }
   }
   ```

3. **Update Login Component** (`frontend/src/pages/Login.jsx`):
   - Add reCAPTCHA component
   - Get CSRF token on mount
   - Include reCAPTCHA token in login request
   - Handle response (redirect on success, show error on failure)

4. **CSRF Token Handling**:
   - Call `GET /api/system/csrf-token` on app initialization
   - Store token in Axios default headers
   - Include in all POST/PUT/DELETE requests

---

## 📝 Next Steps

1. **Update Login Component**:
   - Add reCAPTCHA integration
   - Update API call to include captchaToken
   - Handle CSRF token

2. **Add New Profile Endpoints**:
   - `GET /api/profiles/get-favorites`
   - `GET /api/profiles/get-stat-config`
   - `POST /api/profiles/update-stat-config/`

3. **Add System Endpoints**:
   - `GET /api/system/csrf-token`

4. **Test Login Flow**:
   - Test successful login
   - Test failed login (invalid credentials)
   - Test reCAPTCHA validation
   - Test CSRF token handling

---

## 🎯 Summary

**Login API**: ✅ Complete  
**Request Structure**: ✅ Captured (username, password, captchaToken)  
**Response Structure**: ✅ Captured (user object)  
**New Endpoints**: ✅ 4 new endpoints discovered

This gives us everything needed to implement the complete login flow!

