# Dashboard Functionality Analysis

## Extracted Data Summary

**File**: `trade_manager_functionality__user_dashboard_1762406722539.json`  
**Page**: `/user/dashboard`  
**Timestamp**: 2025-11-06T05:25:08.447Z

## ✅ What Was Captured

### 1. Authentication Structure

**LocalStorage:**
```json
{
  "lastTicker": "MES1!",
  "_grecaptcha": "...",
  "lastStrategy": "JADDCAVIXES",
  "auth": {
    "isAuthenticated": true,
    "user": {
      "username": "J.T.M.J",
      "email": "just.trades.chicago@gmail.com",
      "admin": false,
      "DiscordID": "963881348039340122",
      "access": "full",
      "signed": true,
      "is_email_verified": true,
      "sessionId": "2btylfl2bo4w9lqptbroqvtb103q561y"
    }
  }
}
```

**SessionStorage:**
```json
{
  "auth": {
    "isAuthenticated": true,
    "user": {
      "username": "J.T.M.J",
      "email": "just.trades.chicago@gmail.com",
      "admin": false,
      "DiscordID": "963881348039340122",
      "access": "full",
      "signed": true,
      "is_email_verified": true
      // Note: No sessionId in sessionStorage
    }
  }
}
```

**Cookies:**
```
csrftoken=0JjCf9MUZjtIdqSJYVpITJmGLyPEWg34
_ga=GA1.2.1413952153.1744203650
_gat_gtag_UA_XXXXX_Y=1
_gid=GA1.2.739036613.1762399831
```

### 2. Event Listeners

- **React synthetic events** (click handlers via `function Zn(){}`)
- **Calendar interactions** (rbc-button-link elements)
- **Navigation clicks** (sidebar, navbar buttons)
- **Form inputs** (react-select components)

### 3. Component IDs

- `#root` - Main React root
- `#tooltip209599` - Minimize sidebar button
- `#darkModeToggle` - Dark mode toggle
- `#react-select-2-input`, `#react-select-3-input`, etc. - React Select inputs

## ⚠️ What's Missing (Needs Interaction)

### API Calls Not Captured

The `apiCalls` array is **empty**. This means:
1. The script was loaded **after** the page already fetched data, OR
2. No API calls were triggered yet (page might need user interaction)

**Expected API Calls** (based on Dashboard.jsx code):

1. **GET /api/dashboard/summary/**
   - Purpose: Get dashboard summary stats
   - Expected Response: `{ total_strategies, active_positions, total_pnl, today_pnl }`

2. **GET /api/trades/**
   - Purpose: Get all trades with filters
   - Query Params: `{ usageType: true, user, strategy, symbol, timeframe }`
   - Expected Response: `{ trades: [...] }`

3. **GET /api/trades/open/**
   - Purpose: Get open trades
   - Query Params: `{ usageType: true, ...filters }`
   - Expected Response: `{ trades: [...] }`

4. **GET /api/profiles/get-stat-config/**
   - Purpose: Get statistics configuration
   - Expected Response: Configuration object

5. **GET /api/profiles/get-favorites/**
   - Purpose: Get user favorites
   - Expected Response: Favorites array

6. **GET /api/system/csrf-token/** (if needed)
   - Purpose: Get CSRF token
   - Expected Response: `{ csrf_token: "..." }`

## 🔄 How to Capture API Calls

### Option 1: Refresh After Loading Script

1. **Load the script first** (before page fully loads)
2. **Refresh the page** (F5 or Cmd+R)
3. The script will intercept all API calls made during page load

### Option 2: Interact with Page

1. **Change filters** (User, Strategy, Symbol, Timeframe dropdowns)
2. **Click "VIEWING RECORDED STRATS" button**
3. **Navigate away and back** to Dashboard
4. **Wait for auto-refresh** (if any)

### Option 3: Network Tab Alternative

If script doesn't capture API calls, use Browser DevTools:
1. Open **Network tab** (F12 → Network)
2. **Filter by XHR/Fetch**
3. **Interact with page**
4. **Export as HAR** file

## 📋 Next Steps

1. **Re-run extraction** with script loaded BEFORE page load
2. **Interact with Dashboard** (change filters, click buttons)
3. **Export again** after interactions
4. **Share the new JSON file** with captured API calls

## 🔍 Key Findings

### Authentication Flow
- **CSRF token** required in cookies and headers (`X-CSRFToken`)
- **Session ID** stored in localStorage (not sessionStorage)
- **Auth state** stored in both localStorage and sessionStorage
- **User preferences** stored in localStorage (`lastTicker`, `lastStrategy`)

### Security
- CSRF protection via token in cookies
- Session-based authentication
- Credentials sent via `withCredentials: true`

### User Preferences
- Last selected ticker: `MES1!`
- Last selected strategy: `JADDCAVIXES`
- These preferences are likely used to pre-fill forms

