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

*Last updated: Jan 19, 2026*
*Author: Claude Code Session*
