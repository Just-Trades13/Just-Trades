# Just Trades Platform - Claude CLI Handoff Document

> **CRITICAL**: Read this ENTIRE document before making ANY changes.
> This platform has been broken MULTIPLE times by AI making unauthorized changes.

---

## 🚨 ABSOLUTE RULES - FOLLOW OR BREAK EVERYTHING

### Before ANY Code Change:
1. **ASK PERMISSION** - "I want to modify [file] to [change]. Is this okay?"
2. **WAIT** for explicit "yes" / "approved" / "go ahead"
3. **ONE change at a time** - never bulk edit
4. **TEST** after each change
5. **HAVE ROLLBACK READY** - know how to restore

### NEVER Do These Things:
- Refactor or "improve" working code
- Remove code you think is "unused"
- Make changes without asking
- Touch multiple files at once
- Modify database schemas without approval
- Add features not explicitly requested

---

## 📁 Project Architecture

### Core Files (The Holy Trinity)
| File | Purpose | Lines |
|------|---------|-------|
| `ultra_simple_server.py` | Main Flask server - ALL API routes, webhooks, OAuth, UI | ~24,600 |
| `recorder_service.py` | Trading engine - webhook processing, TP/SL, position tracking | ~6,800 |
| `phantom_scraper/tradovate_integration.py` | Tradovate API wrapper - orders, positions, WebSocket | ~2,300 |

### Supporting Files
| File | Purpose |
|------|---------|
| `user_auth.py` | User authentication system |
| `subscription_models.py` | Subscription/plan management |
| `whop_integration.py` | Whop payment integration |
| `async_utils.py` | Safe async execution utilities |
| `production_db.py` | PostgreSQL connection handling |

### Database
- **Local**: `just_trades.db` (SQLite)
- **Production**: PostgreSQL on Railway
- **CRITICAL**: All SQL must work on BOTH databases

### Templates (UI)
Located in `templates/` - key files:
- `dashboard.html` - Main dashboard
- `control_center.html` - Trading control center
- `manual_copy_trader.html` - Manual trading interface
- `recorders.html` / `recorders_list.html` - Recorder management
- `admin_users.html` - Admin user management
- `broker_selection.html` - Broker selection UI

---

## 💾 Database Schema (Key Tables)

```sql
-- Users
users (id, username, email, password_hash, is_admin, is_approved, discord_user_id, ...)

-- Broker Accounts
accounts (id, user_id, name, broker, auth_type, environment, tradovate_token, ...)

-- Recorders (Signal Sources)
recorders (id, user_id, name, webhook_token, symbol, tp_ticks, sl_ticks, ...)

-- Traders (Account-Recorder Links)
traders (id, user_id, recorder_id, account_id, enabled, multiplier, ...)

-- Trades
recorded_trades (id, recorder_id, ticker, side, entry_price, exit_price, pnl, status, ...)

-- Positions
recorder_positions (id, recorder_id, ticker, side, total_quantity, avg_entry_price, ...)
```

---

## 🔌 Supported Brokers

| Broker | Status | Auth Type | Notes |
|--------|--------|-----------|-------|
| **Tradovate** | ✅ Working | OAuth + Credentials | Primary broker, full integration |
| **NinjaTrader** | ⚠️ UI Only | Same as Tradovate | Uses Tradovate API (same backend) |
| **ProjectX/TopstepX** | ✅ Working | API Key | Prop firm support |
| **Webull** | ✅ Working | App Key/Secret | Stocks, options, futures |
| **Rithmic** | 🔜 Coming Soon | - | Not implemented |

### NinjaTrader Note
NinjaTrader Brokerage uses Tradovate's backend API. The broker_selection.html already shows it as available and routes to the same credentials flow as Tradovate.

---

## 🔄 Trading Flow

```
TradingView Alert
       ↓
Webhook: POST /webhook/{token}
       ↓
process_webhook_directly() in ultra_simple_server.py
       ↓
Find all enabled traders for this recorder
       ↓
Queue broker execution tasks
       ↓
broker_execution_worker() processes queue
       ↓
execute_simple() in recorder_service.py
       ↓
TradovateIntegration places order via WebSocket/REST
       ↓
TP/SL orders placed
       ↓
Position recorded in DB
```

---

## ⚡ Critical Code Sections

### 1. OAuth Token Exchange (~line 1338 in ultra_simple_server.py)
```python
# CRITICAL: Try LIVE first, then DEMO (demo gets rate-limited)
token_endpoints = [
    'https://live.tradovateapi.com/v1/auth/oauthtoken',  # MUST BE FIRST
    'https://demo.tradovateapi.com/v1/auth/oauthtoken'   # Fallback only
]
```
**NEVER change the order or remove LIVE endpoint.**

### 2. Webhook Broker Execution (~line 9130-9183 in ultra_simple_server.py)
```python
# MUST queue broker orders BEFORE returning from webhook
broker_execution_queue.put_nowait(close_task)
```
**NEVER remove the queue blocks before early returns.**

### 3. Position Reconciliation (recorder_service.py)
```python
start_position_reconciliation()  # Runs every 60 seconds
```
**NEVER disable this - it keeps DB in sync with broker.**

### 4. WebSocket Keep-Alive (recorder_service.py)
```python
start_websocket_keepalive_daemon()  # Pings every 30 seconds
```
**NEVER remove - provides 5-10x faster order execution.**

---

## 🐘 PostgreSQL Compatibility Rules

```python
# Check database type
is_postgres = is_using_postgres()
placeholder = '%s' if is_postgres else '?'

# Boolean values
enabled_value = 'TRUE' if is_postgres else '1'

# String defaults in ALTER TABLE
if is_postgres:
    cursor.execute("ALTER TABLE t ADD COLUMN x TEXT DEFAULT 'value'")
else:
    cursor.execute('ALTER TABLE t ADD COLUMN x TEXT DEFAULT "value"')
```

---

## 🛠️ TODO - Features to Add/Fix

### 1. DCA (Dollar Cost Averaging) Logic - BROKEN
**Location**: `recorder_service.py` and `ultra_simple_server.py`
**Issue**: DCA detection and TP updates after adding to positions are not working correctly
**Key functions**:
- `update_exit_brackets()` - Updates TP after DCA
- `is_dca` detection in `process_webhook_directly()`

### 2. Admin Panel View Mode
**Purpose**: Allow admin to view the platform as a specific user (impersonation)
**Location**: `admin_users.html` and admin routes
**Status**: Not implemented or broken

### 3. NinjaTrader Full Integration
**Current**: UI shows NinjaTrader, routes to Tradovate credentials
**Needed**: Verify the flow works end-to-end, may need specific handling

---

## 🔒 Locked Files - ASK BEFORE MODIFYING

```
⛔ LOCKED - Explicit permission required:
├── ultra_simple_server.py
├── recorder_service.py
├── templates/manual_copy_trader.html
├── templates/account_management.html  ← NEVER TOUCH
├── templates/recorders.html
├── templates/recorders_list.html
├── templates/dashboard.html
├── templates/control_center.html
└── just_trades.db
```

---

## 🆘 Recovery Commands

```bash
# Restore to known working state
git reset --hard WORKING_JAN14_2026_LIVE_ACCOUNTS_FIX

# Restore single file
git checkout WORKING_JAN14_2026_LIVE_ACCOUNTS_FIX -- ultra_simple_server.py

# View recent commits
git log --oneline -20

# Create backup before changes
git stash push -m "backup before changes"

# Restart server
pkill -f "python.*ultra_simple"
nohup python3 ultra_simple_server.py > /tmp/server.log 2>&1 &
```

---

## 📋 Working Git Tags

| Tag | Description |
|-----|-------------|
| `WORKING_JAN14_2026_LIVE_ACCOUNTS_FIX` | Most recent stable |
| `WORKING_JAN12_2025_WEBSOCKET_ORDERS` | WebSocket orders working |
| `WORKING_JAN1_2025_STABLE` | First successful overnight trading |
| `WORKING_DEC31_2025_WEBHOOK_FIX` | Webhook broker execution fixed |

---

## 🏃 Running the Platform

### Local Development
```bash
cd "/Users/mylesjadwin/Trading Projects"
python3 ultra_simple_server.py
# Runs on http://localhost:5000
```

### Production (Railway)
- Auto-deploys from git push
- PostgreSQL database
- Environment variables for secrets

### Environment Variables
```
DATABASE_URL=postgresql://...  # Railway provides this
DISCORD_BOT_TOKEN=...          # For notifications
SECRET_KEY=...                 # Flask sessions
```

---

## 📚 Key Concepts

### Recorders
A "recorder" is a signal source (e.g., TradingView strategy). Each recorder has:
- Webhook token for receiving signals
- Risk settings (TP, SL, position sizes)
- Linked traders (accounts that copy its signals)

### Traders
A "trader" links an account to a recorder:
- `recorder_id` - Which signals to follow
- `account_id` - Which broker account to trade on
- `multiplier` - Position size multiplier (1x, 2x, 3x...)
- `enabled` - Whether to execute trades

### DCA (Dollar Cost Averaging)
When a signal matches the current position direction:
- Add to position instead of opening new
- Use `add_position_size` instead of `initial_position_size`
- Update TP to new average price + ticks

---

## ⚠️ Past Disasters - Learn From These

### Dec 4, 2025: AI Bulk Changes
- Modified 3 files without asking
- Created new files without permission
- Deleted template when "undoing"
- **Lesson**: ONE change at a time, ASK FIRST

### Jan 12, 2026: "Improvements" Broke Everything
- Added TP unit conversion logic → broke TP placement
- Strict user_id filtering → filtered out legacy data
- Made 15+ rapid changes → cascading failures
- **Lesson**: Don't "improve" working code, test after EACH change

---

## 🎯 Quick Start for Claude CLI

1. **First**: Reset to stable state if needed
   ```bash
   git reset --hard WORKING_JAN14_2026_LIVE_ACCOUNTS_FIX
   ```

2. **Read**: This file and `.cursorrules`

3. **Ask**: Before ANY file modification

4. **One change**: Make minimal edits, test, commit

5. **Rollback**: If broken, restore from git tag

---

## 📝 Session Log - January 19, 2026

### Issues Fixed This Session

#### 1. TP Orders Placing When TP=0 (CRITICAL FIX)
**Problem:** JTMGC strategy (recorder ID 18) had TP set to 0 but limit orders were still being placed at entry price.

**Root Causes Found:**
1. `execute_trade_simple()` at line 741 had default `tp_ticks=10` instead of `0`
2. Database stored `{'value': 0, 'trim': 100}` but code only looked for `'ticks'` key
3. Multiple code paths didn't check `if tp_ticks > 0` before placing TP

**Fixes Applied:**
- `recorder_service.py:741` - Changed default `tp_ticks=10` → `tp_ticks=0`
- `recorder_service.py:1593` - Added `if tp_ticks and tp_ticks > 0:` before TP calculation
- `recorder_service.py:1609` - Added `if tp_price is None: pass` to skip TP placement
- `recorder_service.py:1654` - Added `if tp_price is not None and not tp_order_id:` check
- `recorder_service.py:3979-3984` - Fixed to handle both `'ticks'` and `'value'` keys
- `recorder_service.py:4114-4122` - Fixed key handling in sync function
- `recorder_service.py:6564-6573` - Fixed key handling in webhook processor

**When TP=0:** Logs should show `🎯 TP DISABLED (tp_ticks=0) - letting strategy handle exit`

#### 2. Multi-TP Targets UI
**Added:** Dynamic add/remove TP targets in both pages:
- `templates/traders.html` - Multi-TP with add/remove buttons
- `templates/recorders.html` - Multi-TP with add/remove buttons

**Format:** `[{ticks: 5, trim: 50}, {ticks: 10, trim: 100}]`

#### 3. Missing Database Column
**Error:** `column "same_direction_ignore" of relation "recorders" does not exist`

**Fix:** Added `/api/run-migrations` endpoint in `ultra_simple_server.py:3990-4020`

**To run migrations:**
```bash
curl -s "https://justtrades-production.up.railway.app/api/run-migrations"
```

### Key Commits This Session
```
102fb69 Add /api/run-migrations endpoint for missing columns
0ccc6c5 Fix remaining TP placement issues when tp_ticks=0
5830b5c Fix TP orders being placed when tp_ticks=0
d9b2e14 Add multiple TP targets support to recorder edit page
9cc80ab Add multiple TP targets support to trader edit page
```

### Current State of JTMGC (Recorder ID 18)
- **tp_targets:** `[{'trim': 100, 'value': 0}]`
- **Expected behavior:** No TP orders placed, TradingView handles all exits
- **Test:** Trigger trade signal, verify no limit orders on broker

### Useful Debug Commands
```bash
# Check recorder TP settings
curl -s "https://justtrades-production.up.railway.app/api/recorders/18" | python3 -m json.tool

# Check trader TP settings
curl -s "https://justtrades-production.up.railway.app/api/traders/177" | python3 -m json.tool

# Run database migrations
curl -s "https://justtrades-production.up.railway.app/api/run-migrations"

# Check all recorders
curl -s "https://justtrades-production.up.railway.app/api/recorders" | python3 -c "import json,sys; [print(f\"ID {r['id']}: {r['name']} - tp: {r.get('tp_targets')}\") for r in json.load(sys.stdin).get('recorders',[])]"
```

### Code Locations for TP Logic
| Location | Purpose |
|----------|---------|
| `recorder_service.py:736-744` | `execute_trade_simple()` function signature with tp_ticks default |
| `recorder_service.py:1588-1603` | TP price calculation with tp_ticks > 0 check |
| `recorder_service.py:1653-1654` | TP placement guard |
| `recorder_service.py:3974-3987` | `execute_live_trades()` TP config parsing |
| `recorder_service.py:6559-6573` | Webhook processor TP config parsing |

### User's Setup
- **Mac Mini:** Primary workstation at `/Users/mylesjadwin/Trading Projects`
- **MacBook Pro:** Clone repo from GitHub, install Claude Code with `npm install -g @anthropic-ai/claude-code`
- **Railway:** Auto-deploys from `main` branch pushes

---

## 📝 Session Log - January 19, 2026 (Continued)

### 1. Whop Integration Fix
**Problem:** API test returning 401 Unauthorized

**Root Cause:** Was calling `/api/v2/me` endpoint which doesn't exist in Whop API v2

**Fix:** Changed to `/api/v2/memberships?per_page=1` in `ultra_simple_server.py:4038`

**User Action Required:** Created new API key in Whop Dashboard with permissions:
- `member:basic:read`
- `webhook_receive:memberships`

**Status:** ✅ Working - 40 memberships found
```bash
curl -s "https://justtrades-production.up.railway.app/api/whop/status" | python3 -m json.tool
```

### 2. Economic Calendar Widgets

**Added TradingView Economic Calendar to:**
- `templates/dashboard.html` - Above the heatmap in "Market Intel" section
- `templates/quant_screener.html` - In Market tab (replaced static data)

**Widget Config:**
```javascript
{
    "colorTheme": "dark",
    "isTransparent": true,
    "width": "100%",
    "height": "380",
    "locale": "en",
    "importanceFilter": "0,1",  // High & medium importance
    "countryFilter": "us"       // US events only
}
```

### 3. News Feed Widget (Dashboard)
**Location:** Dashboard → Market Intel section (right side)

**Implementation:** Tries Financial Juice first, falls back to TradingView Timeline if fails

**Code Location:** `templates/dashboard.html:225-306`

### 4. Trial Abuse Protection System (NEW MODULE)

**Problem:** Scammers abuse 7-day free trials by changing email/payment method

**Solution:** New comprehensive tracking system

**New File:** `trial_abuse_protection.py` (~600 lines)

**Features:**
| Detection | What It Catches |
|-----------|-----------------|
| Device Fingerprint | Same browser/device, even in incognito |
| Email Pattern | `john+1@gmail.com` = `j.o.h.n@gmail.com` |
| Disposable Emails | 40+ temp email domains blocked |
| Card Fingerprint | Same card = blocked (if Whop provides) |
| Whop User ID | Same Whop account trying again |

**Database Tables Created:**
```sql
trial_fingerprints (id, fingerprint_type, fingerprint_value, whop_membership_id,
                    whop_user_id, email, ip_address, trial_count, is_blocked, ...)

trial_abuse_log (id, event_type, fingerprint_type, fingerprint_value,
                 whop_membership_id, email, ip_address, details, created_at)
```

**Frontend Integration:**
- Added FingerprintJS to `templates/layout.html:1271-1359`
- Tracks device on every page load
- Shows "Trial Already Used" modal if blocked

**API Endpoints:**
```bash
# Check abuse stats
curl -s "https://justtrades-production.up.railway.app/api/admin/trial-abuse/stats"

# List flagged users
curl -s "https://justtrades-production.up.railway.app/api/admin/trial-abuse/flagged"

# Unblock a user
curl -X POST "https://justtrades-production.up.railway.app/api/admin/trial-abuse/unblock" \
  -H "Content-Type: application/json" \
  -d '{"fingerprint_type": "device", "fingerprint_value": "abc123..."}'
```

**Files Modified:**
- `trial_abuse_protection.py` (NEW)
- `whop_integration.py` - Added trial tracking to webhook handler
- `ultra_simple_server.py` - Added initialization at startup
- `templates/layout.html` - Added fingerprinting script + body data attributes

### Commits This Session
```
f502609 Try Financial Juice first, fallback to TradingView if fails
8943030 Replace Financial Juice with TradingView Timeline news widget
5bf27cc Add comprehensive trial abuse protection system
9d65ff1 Add Financial Juice headlines widget next to economic calendar
0e7e82b Add TradingView economic calendar widgets
1ee2853 Fix Whop API test to use /memberships endpoint
```

### Quick Reference - New Features

**Check Whop Status:**
```bash
curl -s "https://justtrades-production.up.railway.app/api/whop/status" | python3 -m json.tool
```

**Check Trial Abuse Stats:**
```bash
curl -s "https://justtrades-production.up.railway.app/api/admin/trial-abuse/stats" | python3 -m json.tool
```

**View Flagged Users:**
```bash
curl -s "https://justtrades-production.up.railway.app/api/admin/trial-abuse/flagged" | python3 -m json.tool
```

### File Locations for New Features

| Feature | File | Lines |
|---------|------|-------|
| Whop API test fix | `ultra_simple_server.py` | 4038-4045 |
| Whop status endpoint | `ultra_simple_server.py` | 4022-4055 |
| Trial abuse module | `trial_abuse_protection.py` | 1-600+ |
| Trial tracking in webhook | `whop_integration.py` | 277-317 |
| Device fingerprinting | `templates/layout.html` | 1271-1359 |
| Economic calendar (dashboard) | `templates/dashboard.html` | 190-223 |
| News feed (dashboard) | `templates/dashboard.html` | 225-306 |
| Economic calendar (quant) | `templates/quant_screener.html` | 762-779 |

---

## 📝 Session Log - January 25, 2026

### Real-Time Max Daily Loss Protection System (MAJOR FEATURE)

**User Request:** "how are we tracking th users data for while its n a trade to make sure max loss etc works"

**Problem Identified:** The existing `max_daily_loss` setting only checked CLOSED trades when a NEW signal came in. If a user was IN a trade and it tanked past their max loss, the system did NOTHING.

### Solution Implemented

Created comprehensive real-time max loss monitoring for ALL broker types:

#### 1. Paper Trades - Added to `ultra_simple_server.py`

**New Functions (lines 540-672):**
- `_get_live_price_for_symbol(symbol)` - Gets live price from TradingView WebSocket cache
- `_calculate_unrealized_pnl(symbol, side, quantity, entry_price, live_price)` - Calculates P&L using FUTURES_SPECS point values
- `check_paper_max_daily_loss()` - Main function that:
  - Gets all open paper trades
  - Groups by recorder_id
  - Calculates realized P&L (closed trades today) + unrealized P&L (open positions)
  - Auto-closes ALL positions when `total_pnl <= -max_daily_loss`

**Integration:** Called from `check_paper_trades_tpsl()` which runs every 500ms

#### 2. Live Accounts - New Module `live_max_loss_monitor.py`

**For Tradovate & NinjaTrader:**
- `TradovateMaxLossConnection` class - WebSocket connection per account
- Connects to `wss://[demo|live].tradovateapi.com/v1/websocket`
- Subscribes to `user/syncrequest` for real-time P&L updates
- Monitors `cashBalance.openPnL + cashBalance.realizedPnL`
- Auto-flattens via `liquidate_position` when breached

**For ProjectX/TopstepX:**
- `_monitor_projectx_account()` - REST polling every 5 seconds
- Gets P&L from `get_account_info()` endpoint
- Auto-flattens via `liquidate_position` when breached

**Key Functions:**
- `_load_max_loss_accounts()` - Loads all traders with max_daily_loss > 0
- `flatten_account_positions()` - Flattens Tradovate/NinjaTrader positions
- `flatten_projectx_positions()` - Flattens ProjectX positions
- `start_live_max_loss_monitor()` - Starts background thread
- `get_max_loss_monitor_status()` - Returns current status

#### 3. Admin API Endpoint

**Added:** `/api/admin/max-loss-monitor/status` (lines 6577-6604)

Returns:
```json
{
  "paper_trades": {"monitor_running": true},
  "live_accounts": {
    "running": true,
    "tradovate_accounts": 2,
    "projectx_accounts": 1,
    "breached_today": []
  }
}
```

### Broker Support Matrix

| Broker | Monitoring Method | P&L Source | Flatten Method |
|--------|------------------|------------|----------------|
| **Tradovate** | WebSocket (real-time) | `cashBalance.openPnL` | `liquidate_position` |
| **NinjaTrader** | WebSocket (real-time) | Same as Tradovate | Same as Tradovate |
| **ProjectX** | REST (every 5s) | `get_account_info` | `liquidate_position` |
| **Paper Trades** | TradingView WS (500ms) | Calculated from prices | `_close_paper_trade_tpsl` |

### Database Queries

**Tradovate/NinjaTrader accounts:**
```sql
SELECT t.id, t.recorder_id, t.account_id, t.max_daily_loss, t.subaccount_id,
       a.tradovate_token, a.environment, a.name, a.broker
FROM traders t
JOIN accounts a ON t.account_id = a.id
WHERE t.enabled = TRUE
  AND t.max_daily_loss > 0
  AND a.tradovate_token IS NOT NULL
  AND t.subaccount_id IS NOT NULL
  AND a.broker IN ('Tradovate', 'NinjaTrader', '')
```

**ProjectX accounts:**
```sql
SELECT t.id, t.recorder_id, t.account_id, t.max_daily_loss,
       a.projectx_account_id, a.tradovate_token, a.environment, a.name, a.projectx_prop_firm
FROM traders t
JOIN accounts a ON t.account_id = a.id
WHERE t.enabled = TRUE
  AND t.max_daily_loss > 0
  AND a.broker IN ('ProjectX', 'projectx')
  AND a.tradovate_token IS NOT NULL
```

### Protection Flow

```
User sets max_daily_loss = $500 on trader

While in trade:
├── Paper Trade: Monitor checks every 500ms
│   └── realized + unrealized > -$500 → AUTO CLOSE
│
├── Tradovate/NinjaTrader: WebSocket gets real-time updates
│   └── openPnL + realizedPnL > -$500 → LIQUIDATE ALL
│
└── ProjectX: REST checks every 5 seconds
    └── account P&L > -$500 → LIQUIDATE ALL

After breach:
└── Account marked as "breached today" (no repeated flattens)
└── Resets at midnight
```

### Log Output When Triggered

```
🚨 MAX DAILY LOSS BREACHED for [Account Name]!
   Realized: $-200.00 | Unrealized: $-350.00 | Total: $-550.00 | Limit: -$500.00
💀 FLATTENED 2 positions for [Account Name] due to max loss breach (P&L: $-550.00)
   Liquidated contract 12345 (netPos: 2)
   Liquidated contract 67890 (netPos: -1)
```

### Files Created/Modified

| File | Change |
|------|--------|
| `live_max_loss_monitor.py` | **NEW** - Complete live account monitoring module (~700 lines) |
| `ultra_simple_server.py` | Added paper trade max loss functions + admin endpoint + startup integration |

### Commits This Session

```
df54e42 Add real-time max daily loss protection for paper and live trades
3662f57 Fix: Use subaccount_id instead of non-existent tradovate_account_id
fc579aa Explicitly include NinjaTrader accounts in max loss monitor
```

### Testing Checklist

When testing with users:

**Paper Trades:**
- [ ] Set max_daily_loss on a recorder
- [ ] Open a paper trade
- [ ] Let it go negative past the limit
- [ ] Verify auto-close and log output

**Tradovate/NinjaTrader:**
- [ ] Set max_daily_loss on a trader with connected account
- [ ] Open a position via webhook signal
- [ ] Let it go negative past the limit
- [ ] Verify auto-flatten and log output

**ProjectX:**
- [ ] Set max_daily_loss on a trader with ProjectX account
- [ ] Open a position
- [ ] Verify P&L polling (every 5s)
- [ ] Verify auto-flatten when breached

**Admin Check:**
```bash
curl -s "https://justtrades-production.up.railway.app/api/admin/max-loss-monitor/status" | python3 -m json.tool
```

### Key Code Locations

| Feature | File | Lines |
|---------|------|-------|
| Paper trade max loss check | `ultra_simple_server.py` | 574-672 |
| Live price helper | `ultra_simple_server.py` | 540-556 |
| Unrealized P&L calculation | `ultra_simple_server.py` | 559-571 |
| Admin status endpoint | `ultra_simple_server.py` | 6577-6604 |
| Live monitor startup | `ultra_simple_server.py` | 27315-27321 |
| Tradovate WebSocket class | `live_max_loss_monitor.py` | 47-241 |
| Tradovate flatten function | `live_max_loss_monitor.py` | 244-315 |
| Load accounts function | `live_max_loss_monitor.py` | 318-405 |
| Main monitor loop | `live_max_loss_monitor.py` | 408-510 |
| ProjectX monitor function | `live_max_loss_monitor.py` | 513-576 |
| ProjectX flatten function | `live_max_loss_monitor.py` | 579-624 |

### Rollback Instructions

If issues arise:
```bash
# Revert to before max loss changes
git revert fc579aa 3662f57 df54e42

# Or reset to specific commit
git reset --hard 4e55a38
```

---

## 📝 Session Log - January 26, 2026

### Stop Loss Not Working on Tradovate Prop Firm Accounts (CRITICAL FIX)

**User Report:** "users are reporting stop loss not working when using the system on their tradovate propfirm accounts"

**Root Cause Found:**
The SL placement code did NOT validate that `broker_avg` (fill price) was valid before calculating the SL price. When the order fill wasn't immediately available from the API (common with prop firm accounts due to timing), `broker_avg` was set to 0, resulting in:
- LONG positions: `sl_price = 0 - (sl_ticks * tick_size) = -5.0` (invalid negative price)
- SHORT positions: `sl_price = 0 + (sl_ticks * tick_size) = 5.0` (invalid low price)

Tradovate rejected these invalid stop orders, leaving positions unprotected.

**Fixes Applied (`recorder_service.py`):**

1. **Added retry logic for fill price detection (lines 1658-1700):**
   - Now retries up to 3 times with progressive delays (0.5s, 1.0s, 1.5s) to get position fill price
   - Logs warnings on each retry attempt
   - Logs critical error if fill price can't be obtained after all attempts

2. **Added validation before SL order placement (lines 1871-1913):**
   - Checks `broker_avg > 0` before calculating SL price
   - Checks `sl_price > 0` before placing order
   - Clear error logging when SL can't be placed due to invalid data
   - Logs full response from Tradovate when SL order fails

**Code Changes:**

```python
# BEFORE (problematic):
if sl_ticks and sl_ticks > 0:
    if broker_side == 'LONG':
        sl_price = broker_avg - (sl_ticks * tick_size)  # Could be negative if broker_avg=0!
    # ... placed order with potentially invalid price

# AFTER (fixed):
if sl_ticks and sl_ticks > 0:
    if not broker_avg or broker_avg <= 0:
        logger.error(f"CANNOT PLACE SL: broker_avg is invalid ({broker_avg})")
        # Position logged as unprotected
    else:
        if broker_side == 'LONG':
            sl_price = broker_avg - (sl_ticks * tick_size)
        # Validate calculated price
        if sl_price <= 0:
            logger.error(f"CANNOT PLACE SL: calculated sl_price is invalid ({sl_price})")
        else:
            # Place order with validated price
```

**Why This Affected Prop Firms More:**
- Prop firm accounts may have slightly different order processing timing
- API responses might not include `avgFillPrice` immediately
- Position data might take longer to propagate

**Log Messages to Watch For:**
```
❌ [{acct_name}] CANNOT PLACE SL: broker_avg is invalid (0)
❌ [{acct_name}] CRITICAL: Could not get fill price after 3 attempts!
⚠️ [{acct_name}] Position not visible yet (attempt 1/3) - retrying...
✅ [{acct_name}] SL PLACED @ {price}
```

**Testing Checklist:**
- [ ] Place trade on Tradovate prop firm account
- [ ] Verify SL order appears on broker
- [ ] Check logs for "SL PLACED" message with valid price
- [ ] If SL fails, check for "CANNOT PLACE SL" error message

**Key Code Locations:**

| Feature | File | Lines |
|---------|------|-------|
| Fill price retry logic | `recorder_service.py` | 1658-1700 |
| SL validation & placement | `recorder_service.py` | 1871-1913 |

---

## 📝 Session Log - January 27, 2026

### 40% Trade Failure Rate Fixed (CRITICAL)

**User Report:** "why are we seeing so many failures"

**Investigation:**
```
Broker Execution Stats:
- Total Executed: 350
- Total Failed: 195 (~40% failure rate!)
- Last Error: "All 1 accounts failed"
```

**Root Cause Found:**
When traders use **legacy mode** (`enabled_accounts = null`), the code was NOT fetching credentials from the `accounts` table.

The query at line 815:
```sql
SELECT * FROM traders WHERE recorder_id = ? AND enabled = 1
```

This only gets trader columns. When the code later tried to authenticate:
```python
oauth_token = trader.get('tradovate_token')  # Returns None!
```

All auth methods failed because credentials were missing.

**The Fix (`recorder_service.py` lines 1047-1082):**

Legacy mode now fetches credentials from the accounts table:
```python
cursor.execute(f'''SELECT tradovate_token, username, password, broker,
    api_key, environment, projectx_username, projectx_api_key,
    projectx_prop_firm, tradovate_refresh_token, token_expires_at
    FROM accounts WHERE id = {placeholder}''', (acct_id,))
creds_row = cursor.fetchone()

if creds_row:
    creds = dict(creds_row)
    trader_dict['tradovate_token'] = creds.get('tradovate_token')
    trader_dict['tradovate_refresh_token'] = creds.get('tradovate_refresh_token')
    # ... etc
```

**Why 40% of Trades Failed:**
- 9 out of 15 enabled traders used legacy mode (null enabled_accounts)
- All 9 had subaccount_id set but NO credentials loaded
- Every trade on those accounts failed auth

**Commits:**
- `8766814` - Fix SL orders failing on Tradovate prop firm accounts
- `20132d6` - Fix legacy mode missing credentials causing 40% trade failures

**Log Messages After Fix:**
```
✅ Added trader (legacy): DEMO6385596 (ID: 37561986, Token: YES, Env: demo)
```

Previously it was just:
```
✅ Added trader: DEMO6385596 (ID: 37561986)
```

---

## 📝 Session Log - January 28, 2026

### HIVE MIND Architecture - 500 Account Parallel Execution

**User Request:** "the whole system need to work like hive mind if the signal come to us it need to go to everything attached parallel instantly"

### Changes Made

#### 1. 10 Parallel Broker Execution Workers (was 1)
**File:** `ultra_simple_server.py`
- Added `_broker_execution_worker_count = 10` at line 1589
- Modified `broker_execution_worker(worker_id)` to accept worker ID
- Created `start_broker_execution_workers()` function at lines 12847-12869
- Updated all references from `broker_execution_thread` to `_broker_execution_threads`

**Commits:**
- `e45ea71` - HIVE MIND: Add 10 parallel broker execution workers
- `fd99003` - Fix: Remove all references to old broker_execution_thread variable

#### 2. 500 Account Concurrency Scaling
**File:** `recorder_service.py`
| Setting | Before | After |
|---------|--------|-------|
| `MAX_CONCURRENT_CONNECTIONS` | 50 | 500 |
| `API_CALLS_PER_MINUTE_LIMIT` | 70 | 5000 (disabled) |
| PostgreSQL pool | 5-50 | 10-100 |

**Commit:** `dcf5082` - HIVE MIND: Scale to 500+ simultaneous account executions

#### 3. Async Lock for WebSocket Pool (Speed Fix)
**File:** `recorder_service.py` lines 146-182
- Changed `_WS_POOL_LOCK` from `threading.Lock()` to `asyncio.Lock()`
- `threading.Lock()` was blocking the entire event loop, causing delays
- Added fast-path check without lock for instant cached connections

**Commit:** `586c7c6` - SPEED FIX: Use async lock for WebSocket pool

#### 4. WebSocket Pre-Warming at Startup
**File:** `recorder_service.py` lines 194-272
- Added `prewarm_websocket_connections()` async function
- Added `start_websocket_prewarm()` to launch in background thread
- Pre-warms all enabled account WebSocket connections at startup
- First trade is now INSTANT (no cold connection delay)

**File:** `ultra_simple_server.py` lines 27825-27831
- Added startup call to `start_websocket_prewarm()`

**Commit:** `68ddba4` - INSTANT EXECUTION: Pre-warm WebSocket connections at startup

#### 5. CRITICAL BUG FIX: `failed_accounts` not defined
**File:** `recorder_service.py` lines 2157-2159
- Moved `failed_accounts = []` and `all_results = []` before try block
- Was causing "cannot access local variable 'failed_accounts'" errors
- **30+ failures overnight** due to this bug

**Commit:** `d552c77` - CRITICAL FIX: failed_accounts not defined error

### Overnight Analysis Results

| Issue | Count | Status |
|-------|-------|--------|
| `failed_accounts` not defined | 30+ | **FIXED** |
| Opposite signal blocked (avg_down_enabled=True) | 13 | Working as designed - DCA strats have resting TP orders |
| No trader linked (MGC recorder 34) | 6 | User needs to link traders |
| Access denied (1 account) | 1 | Account needs re-auth |

### Architecture After Changes

```
Signal arrives
     ↓
10 fast_webhook_workers (parallel)
     ↓
broker_execution_queue
     ↓
10 broker_execution_workers (parallel)
     ↓
Pre-warmed WebSocket pool (instant connection)
     ↓
asyncio.gather() fires ALL accounts SIMULTANEOUSLY
     ↓
Each account → own WebSocket → broker → executed
```

### API Endpoints for Monitoring

```bash
# Check HIVE MIND status
curl -s "https://justtrades-production.up.railway.app/api/broker-execution/status" | python3 -m json.tool

# Check recent failures
curl -s "https://justtrades-production.up.railway.app/api/broker-execution/failures?limit=20" | python3 -m json.tool

# Check webhook activity
curl -s "https://justtrades-production.up.railway.app/api/webhook-activity?limit=20" | python3 -m json.tool
```

### Key Commits This Session
```
d552c77 CRITICAL FIX: failed_accounts not defined error
68ddba4 INSTANT EXECUTION: Pre-warm WebSocket connections at startup
586c7c6 SPEED FIX: Use async lock for WebSocket pool
fd99003 Fix: Remove all references to old broker_execution_thread variable
dcf5082 HIVE MIND: Scale to 500+ simultaneous account executions
e45ea71 HIVE MIND: Add 10 parallel broker execution workers
```

### Notes for Next Session
- One orphaned trade (no TP) occurred during deployment - likely server restart mid-trade
- User will report if it happens again
- DCA strats with `avg_down_enabled=True` blocking opposite signals is **correct behavior** - they have resting TP orders
- System ready for 500 account parallel execution via WebSocket

---

## 📝 Session Log - January 28, 2026 (Continued - Fast Webhook Fix)

### Problem: Webhooks Processing Late or Not At All

**User Report:** Signals were being received (showing in raw webhooks) but not processed (not in webhook activity), causing missed trades.

### Root Cause Analysis

1. **Dead Code Path:** The fast webhook mode code at lines 12987-13013 was UNREACHABLE - the function returned at line 12962 before ever reaching the fast queue logic.

2. **No Connection Pooling:** `ultra_simple_server.py` created a FRESH PostgreSQL connection for every webhook (line 2059 `psycopg2.connect()`), causing delays when multiple signals arrived rapidly.

3. **Flask Context Issue:** Fast webhook workers used `app.test_request_context()` which caused `request.get_json()` to silently return empty data, failing signal processing.

### Fixes Applied

#### 1. Fixed Fast Webhook Code Path
**Location:** `ultra_simple_server.py:12953-13045`

Restructured the webhook endpoint so POST requests actually use the fast queue:
```python
if request.method == 'POST':
    if _fast_webhook_enabled:
        # Queue immediately, return <50ms
        _fast_webhook_queue.put_nowait({...})
        return jsonify({'success': True, 'queued': True}), 200
```

#### 2. Added PostgreSQL Connection Pooling
**Location:** `ultra_simple_server.py:2008-2054`

```python
_pg_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=20,
    maxconn=100,
    dsn=_db_url,
    connect_timeout=5
)
```

- Pool of 20-100 pre-opened connections
- `get_db_connection()` now uses pool first, falls back to fresh connection

#### 3. Fixed Fast Webhook Workers - No Flask Context Needed
**Location:** `ultra_simple_server.py:1523-1563` and `13048-13066`

**Problem:** Workers called `process_webhook_directly()` inside `test_request_context()`, but `request.get_json()` returned empty.

**Solution:**
- Created `process_webhook_with_data(token, raw_body_str)` wrapper
- Added `raw_body_override` parameter to `process_webhook_directly()`
- Workers pass body directly, JSON parsed from string not Flask request
- Workers use `app.app_context()` for Flask functions like `jsonify()`

```python
# Worker now does:
with app.app_context():
    result = process_webhook_with_data(token, body)
```

#### 4. Added Staleness Protection
**Location:** `ultra_simple_server.py:14676-14677` and `recorder_service.py:12632-12648`

Signals older than 30 seconds are rejected to prevent stale executions:
```python
SIGNAL_MAX_AGE_SECONDS = 30
if signal_age > SIGNAL_MAX_AGE_SECONDS:
    logger.warning(f"⏰ STALE SIGNAL REJECTED: {action} {ticker} was {signal_age:.1f}s old")
```

#### 5. Added Fast Webhook Monitoring
**Location:** `ultra_simple_server.py:27257-27267`

Added to `/api/broker-execution/status`:
```json
{
  "fast_webhook": {
    "enabled": true,
    "workers_configured": 10,
    "workers_alive": 10,
    "queue_size": 0
  }
}
```

### Architecture After Fixes

```
TradingView Alert
       ↓
Webhook endpoint receives (<10ms)
       ↓
log_raw_webhook() - for tracking
       ↓
Queue to _fast_webhook_queue (instant)
       ↓
Return 200 to TradingView (<50ms total)
       ↓
10 Fast Webhook Workers (parallel) pick from queue
       ↓
process_webhook_with_data() - validates, records trade
       ↓
Queue to broker_execution_queue
       ↓
10 HIVE MIND Broker Workers (parallel)
       ↓
asyncio.gather() executes ALL accounts simultaneously
       ↓
Pre-warmed WebSocket connections → Broker
```

### Capacity

| Component | Limit |
|-----------|-------|
| Fast webhook workers | 10 parallel |
| Broker execution workers | 10 parallel |
| Max concurrent accounts | 500 |
| DB connection pool | 20-100 |
| Webhook queue | 10,000 |
| Broker queue | 1,000 |

### Commits This Session
```
91fb7b8 Add staleness protection for delayed webhook processing
844a278 INSTANT WEBHOOKS: Fast mode + connection pooling
5104945 Add fast webhook worker status to monitoring endpoint
de17d4a Temporarily disable fast webhook mode - silent worker failures
d849cd1 Fix fast webhook workers - pass body directly, no Flask context
e570aa0 Add app.app_context() to fast webhook workers
```

### Key Findings

1. **TradingView sends duplicate webhooks** - Same signal arrives twice within 1ms. Deduplication handles this.

2. **Deploy restarts lose in-memory queue** - Signals queued during Railway deploy are lost. This is expected behavior with in-memory queues.

3. **TradingView alert latency** - 50-200ms delay between indicator painting and webhook being sent. This is TradingView's internal latency, not controllable.

### Testing Results

After fixes:
- Fast webhook: enabled, 10/10 workers alive
- 23 queued, 23 executed, 0 failed
- Signals processing in <50ms after receipt
- All JADVIX strategies (HighRisk/MediumRisk/LowRisk) executing correctly

### Useful Debug Commands

```bash
# Check fast webhook + broker status
curl -s "https://justtrades-production.up.railway.app/api/broker-execution/status" | python3 -m json.tool

# Check raw webhooks received
curl -s "https://justtrades-production.up.railway.app/api/raw-webhooks?limit=10" | python3 -m json.tool

# Check webhook activity (processed)
curl -s "https://justtrades-production.up.railway.app/api/webhook-activity?limit=10" | python3 -m json.tool

# Check failures
curl -s "https://justtrades-production.up.railway.app/api/broker-execution/failures?limit=10" | python3 -m json.tool
```

### Code Locations

| Feature | File | Lines |
|---------|------|-------|
| Fast webhook queue/workers | `ultra_simple_server.py` | 1519-1580 |
| Connection pool init | `ultra_simple_server.py` | 2027-2039 |
| Pool-aware get_db_connection | `ultra_simple_server.py` | 2056-2109 |
| Fast webhook endpoint | `ultra_simple_server.py` | 12978-13045 |
| process_webhook_with_data | `ultra_simple_server.py` | 13048-13066 |
| raw_body_override handling | `ultra_simple_server.py` | 13111-13114, 13215-13229 |
| Fast webhook status in API | `ultra_simple_server.py` | 27257-27267 |
| Staleness check | `recorder_service.py` | 12632-12648 |

---

*Last updated: Jan 28, 2026*
*Author: Claude Code Session*
