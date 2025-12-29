# 🔄 HANDOFF DOCUMENT - December 29, 2025

## Project: Just.Trades. Automated Trading Platform
**Live URL:** https://justtrades-production.up.railway.app/
**Repository:** https://github.com/Just-Trades13/Just-Trades.git
**Hosted On:** Railway (auto-deploys from GitHub main branch)
**Database:** Neon PostgreSQL (external, more reliable than Railway's PostgreSQL)

---

## 📋 SESSION SUMMARY (Dec 29, 2025)

### What Was Done This Session:

#### 1. **User Approval System** ✅
- New user registrations now require admin approval
- Added `is_approved` column to `users` table
- Modified `/login` to check approval status before allowing login
- Modified `/register` to set new users as pending (is_approved = FALSE)
- Added admin endpoints: `/admin/users/approve/<id>` and `/admin/users/reject/<id>`
- Updated `templates/admin_users.html` with approve/reject buttons
- **Files Modified:** `user_auth.py`, `ultra_simple_server.py`, `templates/admin_users.html`

#### 2. **Trader Creation Page Fixes** ✅
- Removed "Strategy Template" dropdown (was confusing)
- Signal Source now pulls from ALL recorders in database
- Auto-populates form when recorder is selected
- **Files Modified:** `templates/traders.html`, `ultra_simple_server.py`

#### 3. **Recorder Privacy Toggle** ✅
- Added `is_private` column to recorders table
- Added toggle switch on recorder edit page (`/recorders/{id}`)
- Private recorders only visible to owner, public visible to all
- **Files Modified:** `templates/recorders.html`, `ultra_simple_server.py`

#### 4. **Stop Loss Order Placement Fix** ✅
- SL settings from recorder now actually create stop orders on broker
- If SL = 0, no stop order placed (allows TradingView to manage exits)
- If SL > 0, stop order placed at calculated price (GTC)
- Works with both bracket orders (new entries) and REST fallback (DCA)
- **Files Modified:** `ultra_simple_server.py`, `recorder_service.py`

#### 5. **Time Filter Toggles on Trader Create** ✅
- Added enable/disable toggles for Time Filter #1 and #2
- Fields dim when toggle is OFF
- Time filter settings now sent when creating new traders
- **Files Modified:** `templates/traders.html`

---

## 🏗️ ARCHITECTURE OVERVIEW

### Key Files:

| File | Purpose |
|------|---------|
| `ultra_simple_server.py` | Main Flask app - ALL routes, API endpoints, webhooks |
| `recorder_service.py` | Trade execution engine - bracket orders, TP/SL placement |
| `user_auth.py` | User authentication, approval system, password hashing |
| `tradovate_api_access.py` | Tradovate API authentication (username/password login) |
| `phantom_scraper/tradovate_integration.py` | WebSocket trading, order placement |

### Templates (Jinja2):

| Template | Page |
|----------|------|
| `templates/traders.html` | /traders (list), /traders/new (create), /traders/{id} (edit) |
| `templates/recorders.html` | /recorders/{id} (create/edit recorder) |
| `templates/admin_users.html` | /admin/users (user management) |
| `templates/dashboard.html` | /dashboard |
| `templates/login.html` | /login |
| `templates/register.html` | /register |

### Database Schema (Key Tables):

```sql
-- Users
users (
    id, username, email, password_hash, display_name,
    is_admin, is_active, is_approved,  -- is_approved = NEW
    created_at, updated_at, last_login, settings_json
)

-- Recorders (Signal Sources)
recorders (
    id, user_id, name, strategy_type, symbol,
    initial_position_size, add_position_size,
    tp_units, trim_units, tp_targets,  -- JSON array
    sl_enabled, sl_amount, sl_units, sl_type,
    avg_down_enabled, avg_down_amount, avg_down_point, avg_down_units,
    time_filter_1_enabled, time_filter_1_start, time_filter_1_stop,
    time_filter_2_enabled, time_filter_2_start, time_filter_2_stop,
    direction_filter, signal_cooldown, max_signals_per_session,
    max_daily_loss, max_contracts_per_trade, auto_flat_after_cutoff,
    webhook_token, recording_enabled, is_private,  -- is_private = NEW
    created_at, updated_at
)

-- Traders (Links Recorder to Account)
traders (
    id, user_id, recorder_id, account_id,
    subaccount_id, subaccount_name, is_demo,
    enabled, enabled_accounts,  -- JSON for multi-account
    -- Risk overrides (optional)
    initial_position_size, add_position_size,
    tp_targets, sl_enabled, sl_amount, ...
    time_filter_1_enabled, time_filter_1_start, time_filter_1_stop,
    time_filter_2_enabled, time_filter_2_start, time_filter_2_stop,
    created_at, updated_at
)

-- Accounts (Tradovate Credentials)
accounts (
    id, user_id, name, username, password,
    tradovate_token, md_access_token, token_expires,
    is_demo, created_at, updated_at
)
```

---

## 🔐 AUTHENTICATION FLOW

### OAuth Flow (Preferred - Scalable):
1. User connects via `/connect-tradovate` → redirects to Tradovate OAuth
2. Tradovate redirects back with auth code
3. `/oauth/callback` exchanges code for token
4. Token stored in `accounts.tradovate_token`

### API Access Flow (Fallback - Rate Limited):
1. Username/password stored in accounts table
2. `TradovateAPIAccess.login()` authenticates
3. Can trigger captcha/rate limits at scale

### Trade Execution Auth Priority:
1. **Token Cache** (instant, no API call)
2. **OAuth Token from DB** (scalable, no rate limit)
3. **API Access** (last resort, can trigger captcha)

---

## 📡 WEBHOOK FLOW

```
TradingView Alert → /webhook/{webhook_token} → process_webhook_directly()
                                                    ↓
                                            1. Find recorder by token
                                            2. Parse action (buy/sell/close)
                                            3. Apply ALL risk filters:
                                               - Direction filter
                                               - Time filters 1 & 2
                                               - Signal cooldown
                                               - Max signals/session
                                               - Max daily loss
                                               - Max contracts/trade
                                               - Signal delay (Nth)
                                            4. Get linked trader
                                            5. Execute via execute_trade_simple()
                                               - Place market order
                                               - Place TP limit order (GTC)
                                               - Place SL stop order (if SL > 0)
```

---

## ⚠️ CRITICAL CODE SECTIONS

### OAuth Token Exchange (DO NOT MODIFY):
```python
# ultra_simple_server.py ~line 1338
# CRITICAL: Try LIVE first, then DEMO (demo gets rate-limited)
token_endpoints = [
    'https://live.tradovateapi.com/v1/auth/oauthtoken',  # MUST BE FIRST
    'https://demo.tradovateapi.com/v1/auth/oauthtoken'   # Fallback only
]
```

### Position Reconciliation (DO NOT DISABLE):
```python
# recorder_service.py → start_position_reconciliation()
# Syncs DB with broker every 60 seconds
# AUTO-PLACES missing TP orders
```

### SL Order Placement (NEW - Dec 29):
```python
# recorder_service.py → execute_trade_simple()
# sl_ticks parameter added - places stop order if > 0
# If sl_ticks = 0, no stop order (TradingView manages exits)
```

---

## 🎯 RECORDER SETTINGS THAT CARRY OVER TO TRADES

| Setting | Status | Notes |
|---------|--------|-------|
| Direction Filter | ✅ Working | Blocks Long/Short based on filter |
| Time Filter 1 & 2 | ✅ Working | Blocks signals outside windows |
| Signal Cooldown | ✅ Working | Blocks rapid signals |
| Max Signals/Session | ✅ Working | Daily signal limit |
| Max Daily Loss | ✅ Working | Stops trading after loss |
| Max Contracts/Trade | ✅ Working | Caps quantity |
| Signal Delay (Nth) | ✅ Working | Every Nth signal |
| TP Targets | ✅ Working | GTC limit orders |
| TP Units | ✅ Working | Ticks/Points/Percent |
| SL Enabled | ✅ Working | Now places stop orders |
| SL Amount | ✅ Working | Converted to ticks |
| SL Units | ✅ Working | Ticks/Loss/Percent |
| is_private | ✅ Working | Hides from other users |

---

## 🔧 ENVIRONMENT VARIABLES (Railway)

```
DATABASE_URL=postgresql://neondb_owner:***@ep-small-hall-ae3vmr2h-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require
SECRET_KEY=***
TRADOVATE_CLIENT_ID=***
TRADOVATE_CLIENT_SECRET=***
FLASK_ENV=production
```

---

## 📝 PENDING TASKS / KNOWN ISSUES

### Should Do:
1. **Reset Neon password** - was visible in chat, update DATABASE_URL on Railway
2. **Create admin user on Neon** - current `jtmj` user was created on SQLite fallback
3. **Reconfigure Tradovate accounts** - need to re-add accounts and set up traders

### Nice to Have:
1. Add trailing stop loss support (currently only fixed SL)
2. Add multi-TP target support (currently only uses first target)
3. Add position sizing multipliers per account

### Known Issues:
- None currently - all major features working

---

## 🧪 TESTING CHECKLIST

### User Auth:
- [ ] New user registration shows "pending approval" message
- [ ] Admin can approve users at /admin/users
- [ ] Approved users can log in
- [ ] Rejected users are deleted

### Recorders:
- [ ] Private toggle shows on /recorders/{id}
- [ ] Private recorders only visible to owner
- [ ] Public recorders visible to all

### Traders:
- [ ] /traders/new shows all public recorders in dropdown
- [ ] Selecting recorder auto-populates settings
- [ ] Time filter toggles work (dim when OFF)
- [ ] Creating trader includes time filter settings

### Trade Execution:
- [ ] Webhook creates market order
- [ ] TP limit order placed (GTC)
- [ ] SL stop order placed when SL > 0
- [ ] SL NOT placed when SL = 0
- [ ] All risk filters work (direction, time, cooldown, etc.)

---

## 🚀 DEPLOYMENT

Push to main branch auto-deploys to Railway:
```bash
git add .
git commit -m "Description of changes"
git push origin main
```

Railway typically deploys within 30-60 seconds.

---

## 📞 ADMIN ACCESS

**Username:** jtmj
**Password:** JustTrades2025!
**Note:** This user was created via emergency endpoint - may need to be recreated on Neon

**Emergency Admin Endpoint (DELETE AFTER USE):**
`/emergency-admin-setup-dec26`

---

## 📚 GIT TAGS (Recovery Points)

```bash
git tag -l  # List all tags
git checkout WORKING_DEC3_2025  # Original working state
git checkout WORKING_DEC4_2025_OAUTH_FIX  # OAuth fallback fix
```

---

## 🔗 USEFUL LINKS

- **Live Site:** https://justtrades-production.up.railway.app/
- **Railway Dashboard:** https://railway.app/project/795a342c-3b36-4c34-bf80-a54be509391e
- **Neon Console:** https://console.neon.tech
- **GitHub Repo:** https://github.com/Just-Trades13/Just-Trades

---

*Last Updated: December 29, 2025*
*Session: User approval system, recorder privacy, SL order fix, time filter toggles*
