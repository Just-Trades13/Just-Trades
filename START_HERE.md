# 🚨 MANDATORY: READ BEFORE ANY CODE CHANGES 🚨

---

## 🏗️ ARCHITECTURE UPDATE - DEC 5, 2025 🏗️

**⚠️ THE SYSTEM NOW USES A 2-SERVER MICROSERVICES ARCHITECTURE**

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Server (port 8082)                   │
│  • OAuth & Authentication                                    │
│  • Dashboard UI (all templates)                              │
│  • Copy Trading                                              │
│  • Account Management                                        │
│  • Webhooks → PROXY to Trading Engine                        │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP Proxy
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                Trading Engine (port 8083)                    │
│  • Webhook Processing (signals → trades → positions)         │
│  • TP/SL Monitoring (real-time + polling)                   │
│  • Drawdown Tracking (worst_unrealized_pnl)                 │
│  • MFE/MAE Tracking                                         │
│  • Position Aggregation (DCA, weighted avg entry)           │
│  • TradingView WebSocket for price streaming                │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ just_trades.db│
                    │ (Shared DB)   │
                    └───────────────┘
```

### HOW TO START THE SYSTEM
```bash
./start_services.sh   # Starts both servers in correct order
```

### KEY FILES
| File | Port | Purpose |
|------|------|---------|
| `ultra_simple_server.py` | 8082 | Main Server (OAuth, UI, proxies webhooks) |
| `recorder_service.py` | 8083 | Trading Engine (ALL trading logic) |
| `start_services.sh` | - | Startup script |

### CRITICAL RULES
1. **Trading logic → `recorder_service.py` ONLY**
2. **UI/Dashboard → `ultra_simple_server.py` + templates**
3. **NEVER re-enable disabled threads in main server**
4. **Start Trading Engine BEFORE Main Server**

### FULL DOCUMENTATION
See **`HANDOFF_DEC5_2025_MICROSERVICES_ARCHITECTURE.md`** for complete details.

---

## 🛑🛑🛑 CRITICAL INCIDENT - DEC 4, 2025 🛑🛑🛑

**AN AI COMPLETELY IGNORED THESE RULES AND:**
- Modified `ultra_simple_server.py` WITHOUT asking permission
- Modified `templates/my_traders_tab.html` WITHOUT asking permission
- Created new template files WITHOUT asking permission
- Made BULK changes across multiple files at once
- **DELETED a template file** when trying to "undo" instead of restoring properly
- Ignored this START_HERE.md file completely
- Wasted the user's time and caused significant frustration

**THIS MUST NEVER HAPPEN AGAIN.**

**THE RULES BELOW ARE NOT SUGGESTIONS. THEY ARE REQUIREMENTS.**

**IF YOU DO NOT FOLLOW THESE RULES, YOU WILL BREAK THE CODEBASE.**

---

## ⛔ ABSOLUTE RULES - VIOLATION = BROKEN CODE

### RULE 0: ASK PERMISSION FOR EVERY SINGLE FILE
- Before touching ANY file, say: "I want to modify [filename] to [change]. Is this okay?"
- WAIT for the user to say "yes" or "approved"
- If the user hasn't explicitly approved, DO NOT TOUCH THE FILE
- "do it" does NOT mean "do whatever you want" - it means do what you ASKED about
- NEVER delete files - if you need to undo, use `git checkout` or `cp` from backup

### RULE 1: NEVER MODIFY THESE FILES WITHOUT EXPLICIT USER PERMISSION
```
LOCKED FILES - DO NOT TOUCH:
├── ultra_simple_server.py          ← CORE SERVER - ASK FIRST
├── templates/manual_copy_trader.html   ← MANUAL TRADER - ASK FIRST
├── templates/account_management.html   ← ACCOUNT MGMT - NEVER TOUCH
├── templates/recorders.html            ← RECORDERS - ASK FIRST
├── templates/recorders_list.html       ← RECORDERS LIST - ASK FIRST
├── templates/dashboard.html            ← DASHBOARD - ASK FIRST
├── templates/control_center.html       ← CONTROL CENTER - ASK FIRST
└── just_trades.db                      ← DATABASE - NEVER MODIFY SCHEMA
```

### RULE 2: BEFORE ANY CHANGE, YOU MUST:
1. ✅ **ASK USER**: "I want to modify [filename]. Is this okay?"
2. ✅ **WAIT FOR APPROVAL** before touching any code
3. ✅ **EXPLAIN WHAT YOU WILL CHANGE** before changing it
4. ✅ **MAKE ONE SMALL CHANGE AT A TIME** - not bulk edits

### RULE 3: THINGS YOU MUST NEVER DO
- ❌ **NEVER** refactor code that's working
- ❌ **NEVER** "improve" or "clean up" existing code
- ❌ **NEVER** remove code you think is "unused"
- ❌ **NEVER** change indentation or formatting of working code
- ❌ **NEVER** modify files in other tabs while working on one tab
- ❌ **NEVER** add "helpful" features not explicitly requested
- ❌ **NEVER** change database schemas without explicit approval
- ❌ **NEVER** delete or overwrite backup files

### RULE 4: IF YOU BREAK SOMETHING
1. **STOP IMMEDIATELY**
2. **TELL THE USER WHAT YOU BROKE**
3. **RESTORE FROM BACKUP**: `backups/WORKING_STATE_DEC3_2025/`
4. **OR USE GIT**: `git checkout WORKING_DEC3_2025 -- <filename>`

---

## 🔒 WORKING STATE BACKUP (Dec 4, 2025 - LATEST)

**Everything below is CONFIRMED WORKING. Do not break it.**

### Latest Backup (Position Tracking)
```
backups/WORKING_STATE_DEC4_2025_POSITION_TRACKING/
└── ultra_simple_server.py   ← Contains Trade Manager style position tracking
```

### Previous Backups
```
backups/WORKING_STATE_DEC4_2025_MFE_MAE/
backups/WORKING_STATE_DEC4_2025_RESET_HISTORY/
backups/WORKING_STATE_DEC3_2025/
```

### Git Tags (Most Recent First)
```bash
git tag WORKING_DEC4_2025_POSITION_TRACKING  # Trade Manager style drawdown
git tag WORKING_DEC4_2025_RESET_HISTORY      # Reset history fix
git tag WORKING_DEC4_2025_MFE_MAE            # Individual trade MFE/MAE
git tag WORKING_DEC3_2025                     # Original working state

# To restore any file:
git checkout WORKING_DEC4_2025_POSITION_TRACKING -- ultra_simple_server.py
```

---

## ✅ WHAT'S WORKING (DO NOT BREAK)

| Feature | Status | Files Involved |
|---------|--------|----------------|
| **Manual Trader** | ✅ Working | `manual_copy_trader.html`, server routes |
| **Live Position Cards** | ✅ Working | WebSocket `position_update` event |
| **Account PnL Display** | ✅ Working | `fetch_tradovate_pnl_sync()` |
| **Recorders Tab** | ✅ Working | `recorders.html`, `recorders_list.html` |
| **Webhook Signals** | ✅ Working | `/webhook/<token>` endpoint |
| **Trade Recording** | ✅ Working | `recorded_signals`, `recorded_trades` tables |
| **Dashboard** | ✅ Working | `dashboard.html` |
| **Control Center** | ✅ Working | `control_center.html` |
| **Account Management** | ✅ Working | `account_management.html` - NEVER TOUCH |
| **Tradovate OAuth** | ✅ Working | OAuth flow in server |
| **WebSocket Updates** | ✅ Working | `emit_realtime_updates()` |
| **Copy Trading** | ✅ Working | Copy trader logic in manual trader |
| **MFE/MAE Tracking** | ✅ Working | `update_trade_mfe_mae()` in server |
| **Reset Trade History** | ✅ Working | `/api/recorders/<id>/reset-history` endpoint |
| **Position Tracking (TM Style)** | ✅ Working | `recorder_positions` table, 1-sec polling |
| **Real-Time Drawdown** | ✅ Working | `worst_unrealized_pnl` tracking |

---

## 📋 TAB ISOLATION RULES

**When user says "work on X tab", ONLY modify files for that tab:**

| Tab | Allowed Files |
|-----|---------------|
| Manual Trader | `manual_copy_trader.html`, `/api/manual-trade` route |
| Recorders | `recorders.html`, `recorders_list.html`, recorder routes |
| Dashboard | `dashboard.html`, dashboard API routes |
| Control Center | `control_center.html`, control center routes |
| Account Management | **NEVER TOUCH** - It's locked |
| Settings | `settings.html` only |

**🚨 NEVER modify files from OTHER tabs while working on one tab!**

---

## 🛠️ HOW TO MAKE SAFE CHANGES

### Step 1: Ask Permission
```
"I need to modify [filename] to [do X]. Is this okay?"
```

### Step 2: Wait for User Approval
Do not proceed until user says "yes" or "go ahead"

### Step 3: Make ONE Small Change
- Edit only the specific lines needed
- Do not touch surrounding code
- Do not "improve" other parts

### Step 4: Test Immediately
- Verify the feature works
- Check server logs for errors
- Confirm no regressions

### Step 5: If Something Breaks
```bash
# Restore from backup
cp backups/WORKING_STATE_DEC3_2025/[filename] templates/[filename]

# Or use git
git checkout WORKING_DEC3_2025 -- [filename]
```

---

## 📊 POSITION TRACKING (Trade Manager Style) - Dec 4, 2025

### How It Works
- **DCA entries combine** into single position with weighted average entry
- **Real-time drawdown** tracked via 1-second polling (`worst_unrealized_pnl`)
- **Position closes on TP/SL** - matches Trade Manager behavior exactly
- **Dashboard shows positions** instead of individual trades

### Database Table: `recorder_positions`
```sql
SELECT id, ticker, side, total_quantity, avg_entry_price, 
       worst_unrealized_pnl, status 
FROM recorder_positions ORDER BY id DESC;
```

### Key Functions
- `update_recorder_position()` - Creates/updates positions on BUY/SELL
- `close_recorder_position()` - Closes positions on exit
- `poll_recorder_positions_drawdown()` - 1-second drawdown tracking
- `/api/dashboard/trade-history` - Returns position-based data

### Handoff Document
See `HANDOFF_DEC4_2025_POSITION_TRACKING.md` for full implementation details.

---

## 🚫 PAST MISTAKES (LEARN FROM THESE)

### Mistake 1: Bulk Refactoring
**What happened**: AI "improved" working code, broke everything
**Rule**: NEVER refactor working code

### Mistake 2: Modifying Multiple Tabs
**What happened**: AI fixed one tab but broke three others
**Rule**: ONE TAB AT A TIME

### Mistake 3: Changing Database Schema
**What happened**: AI added columns, broke existing queries
**Rule**: NEVER change schema without approval

### Mistake 4: Removing "Unused" Code
**What happened**: AI removed code it thought was unused, broke features
**Rule**: NEVER remove code you didn't write

### Mistake 5: Overwriting Backups
**What happened**: AI overwrote backup with broken code
**Rule**: NEVER modify backup files

---

## 📞 QUICK REFERENCE

### Restore Working State
```bash
# Restore single file
cp backups/WORKING_STATE_DEC3_2025/ultra_simple_server.py ./

# Restore all templates
cp backups/WORKING_STATE_DEC3_2025/*.html templates/

# Full git restore
git checkout WORKING_DEC3_2025
```

### Check Server Status
```bash
pgrep -f "python.*ultra_simple"  # Is server running?
tail -50 /tmp/server.log         # Recent logs
```

### Restart Server
```bash
pkill -f "python.*ultra_simple"
nohup python3 ultra_simple_server.py > /tmp/server.log 2>&1 &
```

---

## 🔐 CHECKSUMS (Verify File Integrity)

Run this to verify files haven't been corrupted:
```bash
md5 ultra_simple_server.py templates/*.html
```

Expected (Dec 3, 2025 working state):
- Store checksums after confirming working state

---

## ⚠️ FINAL WARNING

**This codebase has been broken multiple times by AI making unauthorized changes.**

**EVERY CHANGE REQUIRES:**
1. User permission
2. Clear explanation of what will change
3. Single-file, minimal edits
4. Immediate testing
5. Rollback plan ready

**If in doubt, ASK THE USER FIRST.**

---

## 📊 RECORDERS SYSTEM - COMPLETE DOCUMENTATION

### 🎯 Overview: How Trade Recording Works

The Recorders system allows you to:
1. Create strategies with TP/SL settings
2. Receive webhook signals from TradingView
3. **Automatically monitor prices via TradingView WebSocket**
4. Auto-close trades when TP/SL is hit
5. Display all trades on the Dashboard

### 🔄 The Complete Flow

```
TradingView Alert → Webhook → Record Trade → WebSocket Monitors Price → Auto-Close at TP/SL → Dashboard Shows Trade
```

**Step-by-step:**
1. **Create a Recorder** in "My Recorders" tab with TP/SL settings (in ticks)
2. **Get the Webhook URL** and JSON payload for TradingView
3. **TradingView sends BUY/SELL signal** to your webhook
4. **System opens a trade** with calculated TP/SL price levels
5. **TradingView WebSocket streams live prices** (MNQ, MES, NQ, ES, etc.)
6. **Background thread monitors** all open trades against live prices
7. **When price hits TP or SL** → Trade auto-closes with correct PnL
8. **Dashboard shows the trade** in Trade History + PnL Chart

### 🔑 CRITICAL: TradingView Session Cookies

**The real-time price monitoring REQUIRES your TradingView session cookies!**

Without these cookies, TP/SL won't auto-trigger - trades will only close on manual signals.

#### ⚠️ IMPORTANT: Database Storage Location

**The TradingView session is stored in the `accounts` table, NOT a `settings` table!**

```sql
-- Column: accounts.tradingview_session (TEXT, stores JSON)
-- Format: {"sessionid": "xxx", "sessionid_sign": "xxx", "updated_at": "2025-12-03T..."}

-- To check if configured directly via SQLite:
sqlite3 just_trades.db "SELECT tradingview_session FROM accounts LIMIT 1;"

-- Expected output when configured:
-- {"sessionid": "lp992963...", "sessionid_sign": "v3:QcspTi...", "updated_at": "2025-12-03T23:37:52"}

-- If NULL or empty, cookies need to be stored via the API
```

#### Key Functions in `ultra_simple_server.py`:

| Function | Line ~Range | Purpose |
|----------|-------------|---------|
| `store_tradingview_session()` | ~1655-1696 | Stores cookies in `accounts.tradingview_session` |
| `get_tradingview_session()` | ~5606-5620 | Retrieves cookies from database |
| `connect_tradingview_websocket()` | ~5623-5705 | Uses cookies to connect to TradingView WebSocket |
| `check_recorder_trades_tp_sl()` | ~5380-5512 | Monitors trades against `_market_data_cache` |
| `poll_recorder_trades_tp_sl()` | ~5534-5577 | Fallback polling if WebSocket is down |

#### How to Get Your TradingView Cookies:

1. **Open Chrome** → Go to `https://www.tradingview.com`
2. **Log in** to your TradingView account
3. **Open DevTools** (F12 or Cmd+Shift+I)
4. **Go to Application tab** → Cookies → www.tradingview.com
5. **Find these two cookies:**
   - `sessionid` (e.g., `lp992963ppcyy790wxquqhf2fquhopvv`)
   - `sessionid_sign` (e.g., `v3:QcspTiCJOFhvLcADCSuWDY1tuG2P+HB4THZpcYr7PBU=`)

#### How to Store the Cookies:

```bash
curl -X POST http://localhost:8082/api/tradingview/session \
  -H "Content-Type: application/json" \
  -d '{
    "sessionid": "YOUR_SESSIONID_HERE",
    "sessionid_sign": "YOUR_SESSION_SIGN_HERE"
  }'
```

#### Check if Session is Configured:

```bash
curl http://localhost:8082/api/tradingview/session
```

Expected response when configured:
```json
{
    "configured": true,
    "has_sessionid": true,
    "success": true,
    "updated_at": "2025-12-03T23:37:52.910211"
}
```

#### ⚠️ Session Expiration

TradingView cookies expire periodically (usually 24 hours to a few weeks). 
If trades stop auto-closing at TP/SL, **refresh your cookies** using the steps above.

### 📨 Webhook JSON Payloads

When you create a recorder, you get these JSON templates:

**For Indicator Alerts (separate BUY and SELL alerts):**
```json
{
  "recorder": "YOUR_STRATEGY_NAME",
  "action": "buy",
  "ticker": "{{ticker}}",
  "price": "{{close}}"
}
```

**For Pine Script Strategies (one alert handles both):**
```json
{
  "recorder": "YOUR_STRATEGY_NAME",
  "action": "{{strategy.order.action}}",
  "ticker": "{{ticker}}",
  "price": "{{close}}",
  "contracts": "{{strategy.order.contracts}}",
  "position_size": "{{strategy.position_size}}",
  "market_position": "{{strategy.market_position}}"
}
```

### 🗄️ Database Tables

| Table | Purpose |
|-------|---------|
| `accounts` | Tradovate accounts + `tradingview_session` column for TV cookies |
| `recorders` | Strategy configurations (name, TP/SL settings, webhook token) |
| `recorded_signals` | Every webhook signal received |
| `recorded_trades` | Individual trades with entry/exit prices, PnL |

**⚠️ There is NO `settings` table! TradingView cookies are in `accounts.tradingview_session`**

**Important:** When a recorder is deleted, all associated trades and signals are CASCADE DELETED.

#### Quick Database Queries:
```bash
# Check TradingView session
sqlite3 just_trades.db "SELECT tradingview_session FROM accounts LIMIT 1;"

# Count open trades
sqlite3 just_trades.db "SELECT COUNT(*) FROM recorded_trades WHERE status='open';"

# List all recorders
sqlite3 just_trades.db "SELECT id, name, webhook_token FROM recorders;"

# Check for orphaned trades (should return 0)
sqlite3 just_trades.db "SELECT COUNT(*) FROM recorded_trades WHERE recorder_id NOT IN (SELECT id FROM recorders);"
```

### 📊 Dashboard Integration

The Dashboard pulls data from `recorded_trades`:

| Dashboard Section | Data Source |
|-------------------|-------------|
| Trade History table | `recorded_trades` WHERE status='closed' |
| Profit vs Drawdown chart | Daily aggregated PnL from `recorded_trades` |
| Metric cards (Win Rate, etc.) | Calculated from `recorded_trades` |
| Calendar view | Daily PnL totals from `recorded_trades` |

### 🔧 Troubleshooting

**Trades not auto-closing at TP/SL?**
1. Check if TradingView session is configured: `curl http://localhost:8082/api/tradingview/session`
2. **Or check database directly:**
   ```bash
   sqlite3 just_trades.db "SELECT tradingview_session FROM accounts LIMIT 1;"
   ```
3. If NULL or empty, add your cookies (see above)
4. Check server logs for price streaming: `tail -f /tmp/server.log | grep "TradingView price"`

**Dashboard showing "N/A" for strategy?**
- Those are orphaned trades from deleted recorders
- Clean them up: 
```sql
sqlite3 just_trades.db "DELETE FROM recorded_trades WHERE recorder_id NOT IN (SELECT id FROM recorders);"
sqlite3 just_trades.db "DELETE FROM recorded_signals WHERE recorder_id NOT IN (SELECT id FROM recorders);"
```

**Prices not streaming?**
- Check WebSocket connection in logs: `grep "TradingView WebSocket" /tmp/server.log`
- May need to refresh TradingView cookies
- **Market must be open** (futures: Sun 6pm - Fri 5pm ET)

**How to verify WebSocket is receiving data:**
```bash
# Check for price data in logs
tail -100 /tmp/server.log | grep -E "TradingView price|lp="

# Check market data cache is populated (in Python/server context)
# The _market_data_cache dict stores: {"MNQ": 25635.5, "MES": 6862.25, ...}
```

**⚠️ DO NOT look for a `settings` table - it doesn't exist!**
- TradingView cookies are in `accounts.tradingview_session`
- Recorders are in `recorders` table
- Trades are in `recorded_trades` table

### 📈 Server Log Examples

**Successful price streaming:**
```
📊 TradingView CME_MINI:MNQ1!: lp=25635.5
💰 TradingView price: MNQ = 25635.5
📊 TradingView CME_MINI:MES1!: lp=6862.25
💰 TradingView price: MES = 6862.25
```

**Trade opened by webhook:**
```
📨 Webhook received for recorder 'My Strategy': {"action": "buy", "ticker": "MNQ1!", "price": "25640"}
📈 LONG opened for 'My Strategy': MNQ1! @ 25640.0 x1 | TP: 25645.0 | SL: 25635.0
```

**Auto-close at TP/SL:**
```
🎯 TP HIT via market data for 'My Strategy': LONG MNQ1! | Entry: 25640.0 | Exit: 25645.0 | PnL: $10.00 (20.0 ticks)
```

### 🔗 Key API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/tradingview/session` | POST | Store TradingView cookies |
| `/api/tradingview/session` | GET | Check session status |
| `/webhook/<token>` | POST | Receive TradingView signals |
| `/api/recorders` | GET/POST | List/create recorders |
| `/api/recorders/<id>` | PUT/DELETE | Update/delete recorder |
| `/api/recorders/<id>/webhook` | GET | Get webhook URL and JSON templates |
| `/api/dashboard/trade-history` | GET | Get recorded trades for dashboard |
| `/api/dashboard/chart-data` | GET | Get PnL chart data |

---

## 📈 MFE/MAE (Drawdown) Tracking - WORKING

**Added Dec 4, 2025** - The system now tracks Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE) for each trade.

### What It Tracks:
- **max_favorable** - How far price moved IN YOUR FAVOR before the trade closed
- **max_adverse** - How far price moved AGAINST YOU before the trade closed

### Database Columns:
```sql
-- In recorded_trades table:
max_favorable REAL DEFAULT 0  -- Stores max favorable price movement
max_adverse REAL DEFAULT 0    -- Stores max adverse price movement
```

### How It Works:
1. When a trade is open, `check_recorder_trades_tp_sl()` monitors prices
2. On each price update, `update_trade_mfe_mae()` calculates excursions
3. Values are stored in the database and available for analysis

### Verification:
```bash
# Check MFE/MAE for recent trades
sqlite3 just_trades.db "SELECT id, side, entry_price, exit_price, max_favorable, max_adverse FROM recorded_trades ORDER BY id DESC LIMIT 5;"

# Example output showing MFE tracking:
# 1589|LONG|21650.0|21651.25|3998.0|0.0  ← MFE = 3998.0 means price went 3998 points in favor
```

### Key Functions:
| Function | Line ~Range | Purpose |
|----------|-------------|---------|
| `check_recorder_trades_tp_sl()` | ~5616-5789 | Monitors TP/SL AND updates MFE/MAE on each price tick |

**Note:** MFE/MAE tracking is now built INTO `check_recorder_trades_tp_sl()` (lines ~5657-5697). There is no separate `update_trade_mfe_mae()` function.

---

## 📅 Update Log

| Date | Change |
|------|--------|
| **Dec 5, 2025** | **FIX: Drawdown tracking now working** |
| Dec 5, 2025 | Fixed TradingView Scanner API bug (was requesting invalid columns) |
| Dec 5, 2025 | Stored TradingView session cookies for WebSocket connection |
| Dec 5, 2025 | Real-time drawdown (`worst_unrealized_pnl`) now updates every price tick |
| **Dec 5, 2025** | **MAJOR: Microservices Architecture Migration** |
| Dec 5, 2025 | Split into 2-server architecture: Main Server (8082) + Trading Engine (8083) |
| Dec 5, 2025 | Moved all webhook processing to Trading Engine |
| Dec 5, 2025 | Moved TP/SL monitoring to Trading Engine |
| Dec 5, 2025 | Moved drawdown tracking to Trading Engine |
| Dec 5, 2025 | Main Server webhooks now proxy to Trading Engine |
| Dec 5, 2025 | Added `HANDOFF_DEC5_2025_MICROSERVICES_ARCHITECTURE.md` |
| Dec 5, 2025 | Added `handoff_logs` table to database |
| Dec 5, 2025 | Updated `start_services.sh` for new architecture |
| Dec 4, 2025 | Added Reset Trade History endpoint - `/api/recorders/<id>/reset-history` |
| Dec 4, 2025 | Added MFE/MAE (drawdown) tracking - `update_trade_mfe_mae()` function |
| Dec 4, 2025 | Added detailed database storage info (accounts.tradingview_session) |
| Dec 4, 2025 | Added function references for TradingView WebSocket code |
| Dec 4, 2025 | Added Recorders system documentation |
| Dec 4, 2025 | Added cascade delete for recorder trades/signals |
| Dec 3, 2025 | Initial working state backup |

---

## 🚨 COMMON AI MISTAKES TO AVOID

1. **Looking for a `settings` table** - It doesn't exist! Use `accounts` table
2. **Not knowing where TV cookies are stored** - `accounts.tradingview_session` column
3. **Not checking if market is open** - Futures: Sun 6pm - Fri 5pm ET
4. **Looking for wrong log patterns** - Use `grep "TradingView price"` or `grep "lp="`
5. **Trying to modify database schema** - NEVER do this without approval
6. **Using invalid TradingView API columns** - Only `close` works, NOT `bid`/`ask`

---

## 🔧 CRITICAL: Drawdown Tracking Fix (Dec 5, 2025)

### ⚠️ THE PROBLEM
Drawdown was showing $0.00 for 90% of trades because:
1. TradingView session cookies were not configured (WebSocket couldn't connect)
2. The fallback API was requesting invalid columns (`bid`, `ask`) which caused errors

### ✅ THE FIX
1. **Fixed Scanner API** in `recorder_service.py` line ~694:
   - Changed `["close", "bid", "ask"]` to `["close"]`
2. **Stored TradingView session cookies** for WebSocket real-time streaming

### 📍 How Drawdown Tracking Works Now
```
TradingView WebSocket (real-time prices)
         │
         ▼
on_price_update() in recorder_service.py
         │
         ├──► update_position_drawdown() 
         │    → Calculates unrealized PnL
         │    → Updates worst_unrealized_pnl if new low
         │
         └──► Stored in recorder_positions table
```

### 🔑 To Verify Drawdown is Working
```bash
# Check Trading Engine status
curl -s http://localhost:8083/status | python3 -m json.tool

# Look for:
# - "websocket_connected": true
# - "cached_prices": {"MES": ..., "MNQ": ...}

# Check positions have drawdown values
sqlite3 just_trades.db "SELECT id, ticker, worst_unrealized_pnl FROM recorder_positions WHERE status='open';"
```

### ⚠️ If Drawdown Stops Working
TradingView cookies expire! You have two options:

#### Option A: Automatic Refresh (Recommended)
Set up once, works forever:
```bash
# Store your TradingView credentials (one-time)
cd "/Users/mylesjadwin/Trading Projects"
python3 tradingview_auth.py store --username 'YOUR_EMAIL' --password 'YOUR_PASSWORD'

# Test it works
python3 tradingview_auth.py status
python3 tradingview_auth.py refresh

# The Trading Engine will now auto-refresh cookies when they expire!
```

#### Option B: Manual Refresh
1. Go to TradingView.com → DevTools (F12) → Application → Cookies
2. Copy `sessionid` and `sessionid_sign` values
3. Store them:
```bash
curl -X POST http://localhost:8082/api/tradingview/session \
  -H "Content-Type: application/json" \
  -d '{"sessionid": "YOUR_VALUE", "sessionid_sign": "YOUR_VALUE"}'
```
4. Restart Trading Engine:
```bash
pkill -f "python.*recorder_service"
cd "/Users/mylesjadwin/Trading Projects" && python3 recorder_service.py &
```

### 🔐 TradingView Auto-Auth System (Dec 5, 2025)

The system now supports automatic cookie refresh:

| Component | Purpose |
|-----------|---------|
| `tradingview_auth.py` | Manages credentials and auto-login |
| `tradingview_credentials` table | Encrypted credential storage |
| Auto-refresh in Trading Engine | Detects expired cookies and refreshes |

**API Endpoints:**
- `GET /api/tradingview/auth-status` - Check auth status (port 8083)
- `POST /api/tradingview/refresh` - Trigger manual refresh (port 8083)

**CLI Commands:**
```bash
python3 tradingview_auth.py store --username EMAIL --password PASSWORD
python3 tradingview_auth.py status
python3 tradingview_auth.py refresh
python3 tradingview_auth.py keepalive  # Run as daemon
```

---

## 🔐 CRITICAL: Tradovate OAuth Token Exchange Fix (Dec 4, 2025)

### ⚠️ THE PROBLEM
Tradovate's **DEMO API** (`demo.tradovateapi.com`) aggressively rate-limits OAuth token exchange requests (returns 429 errors). This can persist for 20+ minutes and makes account connection impossible.

### ✅ THE SOLUTION
**Try LIVE endpoint first, then fallback to DEMO.** The LIVE API doesn't have the same rate limiting.

### 📍 Location in Code
`ultra_simple_server.py` - OAuth callback function, around line ~1338-1365

### 🔑 THE CRITICAL CODE (NEVER REMOVE THIS)
```python
# Exchange authorization code for access token
# Try LIVE endpoint first (demo often rate-limited), then fallback to DEMO
import requests
token_endpoints = [
    'https://live.tradovateapi.com/v1/auth/oauthtoken',
    'https://demo.tradovateapi.com/v1/auth/oauthtoken'
]
token_payload = {
    'grant_type': 'authorization_code',
    'code': code,
    'redirect_uri': redirect_uri,
    'client_id': client_id,
    'client_secret': client_secret  # Always include the secret
}

# Try each endpoint until one works
response = None
for token_url in token_endpoints:
    logger.info(f"Trying token exchange at: {token_url}")
    response = requests.post(token_url, json=token_payload, headers={'Content-Type': 'application/json'})
    if response.status_code == 200:
        logger.info(f"✅ Token exchange succeeded at: {token_url}")
        break
    elif response.status_code == 429:
        logger.warning(f"⚠️ Rate limited (429) at {token_url}, trying next endpoint...")
        continue
    else:
        logger.warning(f"Token exchange failed at {token_url}: {response.status_code} - {response.text[:200]}")
        # For non-429 errors, still try next endpoint
        continue
```

### 🚫 WHAT NOT TO DO
- ❌ **NEVER** use only `demo.tradovateapi.com` for token exchange
- ❌ **NEVER** remove the LIVE endpoint fallback
- ❌ **NEVER** remove the 429 rate limit handling
- ❌ **NEVER** change the order (LIVE must be tried FIRST)

### 📋 How to Verify It's Working
```bash
# Check server logs after clicking "Reconnect"
tail -50 /tmp/server.log | grep -iE "token exchange|429|succeeded"

# Expected output when working:
# Trying token exchange at: https://live.tradovateapi.com/v1/auth/oauthtoken
# ✅ Token exchange succeeded at: https://live.tradovateapi.com/v1/auth/oauthtoken
```

### 🔧 If OAuth Stops Working
1. Check if BOTH endpoints are in the code (LIVE first, then DEMO)
2. Verify the token_endpoints list hasn't been modified
3. Check server logs for 429 errors
4. If only using DEMO endpoint, that's the bug - add LIVE back

### 📅 History
- **Dec 4, 2025**: Fixed persistent 429 rate limiting by trying LIVE endpoint first
- **Problem duration**: 20+ minutes of failed OAuth attempts before fix
- **Root cause**: Tradovate demo API aggressive rate limiting on `/v1/auth/oauthtoken`

---

## 🔒 WORKING STATE BACKUP (Dec 4, 2025 - OAuth Fix)

### New Backup Location
```
backups/WORKING_STATE_DEC4_2025_OAUTH_FIX/
├── ultra_simple_server.py  ← Contains the critical OAuth fix
├── manual_copy_trader.html
├── recorders.html
├── recorders_list.html
├── dashboard.html
├── control_center.html
├── account_management.html
└── just_trades.db
```

### Git Tag
```bash
git tag WORKING_DEC4_2025_OAUTH_FIX
# To restore the OAuth fix:
git checkout WORKING_DEC4_2025_OAUTH_FIX -- ultra_simple_server.py
```

---

---

## 📦 Database Handoff Logs

The system now stores handoff session logs in the database:

```bash
# View all handoff logs
sqlite3 just_trades.db "SELECT session_date, session_title, summary FROM handoff_logs;"

# View full details of latest handoff
sqlite3 just_trades.db "SELECT * FROM handoff_logs ORDER BY id DESC LIMIT 1;"
```

---

---

## 🔴 CRITICAL: Dec 8, 2025 - Live Trade Execution + Rate Limiting Incident

### ✅ MAJOR ACCOMPLISHMENT: Live Trading Now Works!

**The system can now execute REAL trades on Tradovate from webhook signals!**

#### The Complete Flow (Working):
```
TradingView Alert → Webhook (Main Server 8082) → Trading Engine (8083) → Tradovate API → REAL ORDER PLACED
```

#### What Was Fixed:
1. **Symbol Conversion** - TradingView sends `MNQ1!`, Tradovate needs `MNQZ5` (front-month contract)
2. **accountSpec Fix** - Was sending parent account name (`Mark`), needed subaccount name (`DEMO4419847-2`)
3. **TradovateIntegration Adoption** - Now uses same code as Manual Trader for consistency
4. **MD Token** - Added `md_access_token` to the SQL query for market data access

#### Key Code Location:
`recorder_service.py` - `execute_live_trades()` function (~line 400-500)

#### How to Test Live Trading:
```bash
# Send a webhook signal with REAL market price
curl -X POST http://localhost:8082/webhook/YOUR_WEBHOOK_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"action": "BUY", "ticker": "MNQ1!", "price": 25800.00}'

# Check Trading Engine logs for success
tail -30 /tmp/trading_engine.log | grep -E "LIVE|order|Order|✅"
```

#### Success Log Example:
```
📨 Webhook received for recorder 'Test': {'action': 'BUY', 'ticker': 'MNQ1!', 'price': 25802.25}
🚀 LIVE EXECUTION: Found 1 enabled trader(s) for recorder 14
📤 Placing order via TradovateIntegration (demo=True)
📤 Order data: {'accountSpec': 'DEMO4419847-2', 'orderType': 'Market', 'action': 'Buy', 'symbol': 'MNQZ5', 'orderQty': 1, 'timeInForce': 'Day', 'isAutomated': True, 'accountId': 26029294}
✅ LIVE TRADE EXECUTED on 'Mark': Buy 1 MNQ1! | Order ID: 336150489952
```

### 🔴 CRITICAL INCIDENT: Tradovate Rate Limiting (429 Errors)

#### What Happened:
1. AI modified `/api/control-center/stats` to call `fetch_tradovate_pnl_sync()` 
2. This endpoint gets called frequently from the UI
3. Combined with existing WebSocket polling, API calls DOUBLED
4. Tradovate returned 429 (rate limited) on ALL requests
5. **EVERYTHING BROKE** - manual trades, P&L updates, positions

#### Symptoms of Rate Limiting:
- Manual trader returns `{"error":{},"success":false}` or `{"error":"Access is denied"}`
- WebSocket broadcasts empty: `"positions":[]`, `"pnl_data":{}`
- Server logs show no errors (silent failure)

#### How to Check for Rate Limiting:
```bash
# Stop the server first
pkill -f "python.*ultra_simple"

# Test API directly
TOKEN=$(sqlite3 just_trades.db "SELECT tradovate_token FROM accounts WHERE id = 2;")
curl -s "https://demo.tradovateapi.com/v1/account/list" \
  -H "Authorization: Bearer $TOKEN"

# If response is empty or status 429, you're rate limited
# Wait 5-10 minutes before restarting server
```

#### Recovery Steps:
```bash
# 1. Stop server to stop polling
pkill -f "python.*ultra_simple"
pkill -f "python.*recorder_service"

# 2. Wait for rate limit to clear (5-10 minutes)
# Test periodically:
curl -s "https://demo.tradovateapi.com/v1/account/list" -H "Authorization: Bearer $TOKEN"

# 3. Once you get 200 response, restore from backup
cp backups/WORKING_STATE_DEC5_2025_COMPLETE/ultra_simple_server.py .

# 4. Restart services
./start_services.sh
```

### 🔒 NEVER DO THIS:
- ❌ **NEVER** add API calls to frequently-called endpoints
- ❌ **NEVER** call `fetch_tradovate_pnl_sync()` outside of the WebSocket emit loop
- ❌ **NEVER** poll Tradovate API more than every 0.5 seconds
- ❌ **NEVER** modify Control Center stats endpoint to make additional API calls

### 📊 Tradovate API Rate Limits:
- **~120 requests/minute** across all endpoints
- **Rate limit cooldown**: 5-10 minutes when triggered
- **WebSocket emit loop** already polls at 0.5s (120 req/min with 2 accounts)
- **DO NOT add more API calls** - we're at the limit

### 📍 Working Backup (Use This):
```
backups/WORKING_STATE_DEC5_2025_COMPLETE/
├── ultra_simple_server.py   ← SAFE VERSION - no extra API calls
├── recorder_service.py      ← Contains live trade execution
├── START_HERE.md
└── tradingview_auth.py
```

### 🔧 WebSocket P&L Updates (How They Work):

The WebSocket broadcasts real-time P&L every 0.5 seconds:

```python
# In ultra_simple_server.py - emit_realtime_updates() function
# This is the ONLY place that should call fetch_tradovate_pnl_sync()

def emit_realtime_updates():
    while True:
        pnl_data, tradovate_positions = fetch_tradovate_pnl_sync()
        
        socketio.emit('pnl_update', {
            'total_pnl': total_pnl,
            'open_pnl': open_pnl,      # Unrealized P&L
            'today_pnl': today_pnl,    # Realized P&L
            'active_positions': len(positions)
        })
        
        socketio.emit('position_update', {
            'positions': positions_list,
            'pnl_data': pnl_data       # Full account data
        })
        
        time.sleep(0.5)  # Every 0.5 seconds
```

The Manual Trader listens to these events:
```javascript
// In manual_copy_trader.html
socket.on('pnl_update', function(data) {
    // Updates account cards with P&L
});
socket.on('position_update', function(data) {
    // Updates position cards
});
```

### 🔑 Key Files Modified (Dec 8, 2025):

| File | Change | Status |
|------|--------|--------|
| `recorder_service.py` | Added live trade execution via TradovateIntegration | ✅ Working |
| `recorder_service.py` | Fixed symbol conversion (MNQ1! → MNQZ5) | ✅ Working |
| `recorder_service.py` | Fixed accountSpec to use subaccount name | ✅ Working |
| `ultra_simple_server.py` | **REVERTED** - Don't touch Control Center stats | ✅ Restored |

### 📋 Traders Tab (My Traders):

The Traders system links Recorders to Accounts for live trading:

```
Recorder (strategy) ──► Trader (link) ──► Account (Tradovate)
     │                      │                    │
     │                      │                    └── Has subaccounts (DEMO4419847-2, 1381296)
     │                      └── enabled flag (on/off)
     └── webhook_token, TP/SL settings
```

#### Database Tables:
- `traders` - Links recorder_id to account_id
- `recorders` - Strategy settings
- `accounts` - Tradovate credentials + subaccounts JSON

#### Key Queries:
```sql
-- Check trader links
SELECT t.id, r.name as strategy, a.name as account, t.enabled
FROM traders t
JOIN recorders r ON t.recorder_id = r.id
JOIN accounts a ON t.account_id = a.id;

-- Enable a recorder for webhooks
UPDATE recorders SET recording_enabled = 1 WHERE id = 14;
```

---

## 📅 Update Log

| Date | Change |
|------|--------|
| **Dec 8, 2025** | **LIVE TRADING WORKING** - Webhooks now execute real Tradovate orders |
| Dec 8, 2025 | Fixed symbol conversion (TradingView → Tradovate format) |
| Dec 8, 2025 | Fixed accountSpec to use subaccount name |
| Dec 8, 2025 | Added TradovateIntegration to recorder_service.py |
| Dec 8, 2025 | **INCIDENT**: Rate limiting broke everything - REVERTED changes |
| Dec 8, 2025 | Documented rate limiting recovery process |
| **Dec 5, 2025** | **FIX: Drawdown tracking now working** |
| Dec 5, 2025 | Fixed TradingView Scanner API bug (was requesting invalid columns) |
| Dec 5, 2025 | Stored TradingView session cookies for WebSocket connection |
| Dec 5, 2025 | Real-time drawdown (`worst_unrealized_pnl`) now updates every price tick |
| **Dec 5, 2025** | **MAJOR: Microservices Architecture Migration** |
| Dec 5, 2025 | Split into 2-server architecture: Main Server (8082) + Trading Engine (8083) |
| Dec 5, 2025 | Moved all webhook processing to Trading Engine |
| Dec 5, 2025 | Moved TP/SL monitoring to Trading Engine |
| Dec 5, 2025 | Moved drawdown tracking to Trading Engine |
| Dec 5, 2025 | Main Server webhooks now proxy to Trading Engine |
| Dec 5, 2025 | Added `HANDOFF_DEC5_2025_MICROSERVICES_ARCHITECTURE.md` |
| Dec 5, 2025 | Added `handoff_logs` table to database |
| Dec 5, 2025 | Updated `start_services.sh` for new architecture |
| Dec 4, 2025 | Added Reset Trade History endpoint - `/api/recorders/<id>/reset-history` |
| Dec 4, 2025 | Added MFE/MAE (drawdown) tracking - `update_trade_mfe_mae()` function |
| Dec 4, 2025 | Added detailed database storage info (accounts.tradingview_session) |
| Dec 4, 2025 | Added function references for TradingView WebSocket code |
| Dec 4, 2025 | Added Recorders system documentation |
| Dec 4, 2025 | Added cascade delete for recorder trades/signals |
| Dec 3, 2025 | Initial working state backup |

---

*Last updated: Dec 8, 2025 - Live Trading + Rate Limiting Documentation*
*Backup tags: WORKING_DEC3_2025, WORKING_DEC4_2025_OAUTH_FIX, WORKING_DEC4_2025_MFE_MAE, WORKING_DEC4_2025_RESET_HISTORY, WORKING_DEC5_2025_DRAWDOWN_FIX, WORKING_DEC5_2025_COMPLETE*
*Handoff docs: HANDOFF_DEC5_2025_COMPLETE.md, HANDOFF_DEC5_2025_MICROSERVICES_ARCHITECTURE.md, HANDOFF_DEC5_2025_DRAWDOWN_FIX.md*
