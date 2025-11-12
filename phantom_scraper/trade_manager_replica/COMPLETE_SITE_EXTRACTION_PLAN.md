# Complete Site Extraction Plan - Trade Manager → Just.Trades

**Goal:** Create an exact replica of trademanagergroup.com

## 📋 Extraction Checklist

### 1. Authentication & User Management
- [ ] Login flow (POST request format)
- [ ] Logout flow
- [ ] Registration flow (if exists)
- [ ] Password reset flow
- [ ] User profile management
- [ ] Session management

### 2. Dashboard Page (`/user/dashboard`)
- [ ] All API endpoints called
- [ ] Data structures returned
- [ ] UI components structure
- [ ] Filters and search functionality
- [ ] Real-time updates (WebSocket?)

### 3. My Recorders (`/user/strats`)
- [ ] Strategy list API
- [ ] Create strategy form (all fields)
- [ ] Edit strategy form
- [ ] Delete strategy flow
- [ ] Strategy details view
- [ ] Strategy logs

### 4. Account Management (`/user/at/accnts`)
- [ ] Account list API
- [ ] Add Tradovate account form
- [ ] Test connection flow
- [ ] Edit account
- [ ] Delete account
- [ ] Account settings

### 5. My Trader (`/user/at/strats`)
- [ ] Trading strategies page
- [ ] Different from Recorders?

### 6. Control Center (`/user/at/controls`)
- [ ] Control center functionality
- [ ] All API endpoints

### 7. Settings (`/user/settings`)
- [ ] User settings API
- [ ] Discord integration
- [ ] Notification preferences
- [ ] Profile settings

### 8. API Endpoints
- [ ] Request formats (all POST/PUT/DELETE)
- [ ] Response formats (all GET)
- [ ] Error handling
- [ ] Authentication headers
- [ ] CSRF token usage

### 9. UI/UX
- [ ] Component structure
- [ ] Routing
- [ ] State management
- [ ] Styling system
- [ ] Icons and assets

### 10. Data Models
- [ ] Complete database schema
- [ ] Relationships
- [ ] Field types
- [ ] Constraints

## 🎯 Current Status

**Pages Navigated:**
- ✅ Dashboard (`/user/dashboard`)
- ✅ My Recorders (`/user/strats`)
- ✅ Create Strategy (`/user/strat`)

**Pages Remaining:**
- ⏳ Account Management (`/user/at/accnts`)
- ⏳ My Trader (`/user/at/strats`)
- ⏳ Control Center (`/user/at/controls`)
- ⏳ Settings (`/user/settings`)
- ⏳ Any other pages

**API Endpoints Found:** 16
**Need to Capture:** POST/PUT/DELETE payloads, all response formats

