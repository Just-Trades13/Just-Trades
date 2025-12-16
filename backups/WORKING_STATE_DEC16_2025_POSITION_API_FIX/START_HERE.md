# 🚨 MANDATORY: READ BEFORE ANY CODE CHANGES 🚨

---

## 🔴 CRITICAL UPDATE - DEC 11, 2025 🔴

**V2 TRADING ENGINE - TRADEMANAGER REPLICA IMPLEMENTATION COMPLETE**

### 🚀 Major Components Added:

| Component | Purpose | Location |
|-----------|---------|----------|
| `BrokerEventLoop` | Tradovate WS-driven triggers | `recorder_service_v2.py:874` |
| `AdvancedExitManager` | Exit state machine (MARKET orders) | `recorder_service_v2.py:1151` |
| `ExitConfirmationLoop` | Wait for flat confirmation | `recorder_service_v2.py:1575` |
| `ForceFlattenKillSwitch` | Emergency flatten (750ms) | `recorder_service_v2.py:1649` |
| `PositionDriftReconciler` | Virtual vs broker sync | `recorder_service_v2.py:1733` |
| `DCAEngine` | Auto-DCA with state persistence | `recorder_service_v2.py:496` |
| `PnLEngine` | Virtual PnL using TV prices | `recorder_service_v2.py:627` |

### 🔥 TradingView Routing Mode Detection

The system now checks for `tradingViewTradingEnabled` flag via Tradovate API:
- **Location:** `tradovate_integration.py:334` - `check_tradingview_routing_enabled()`
- **API Endpoint:** `/api/accounts/<id>/check-tradingview-routing`
- **Credentials Page:** `/accounts/<id>/credentials` - Stores username/password and auto-checks TV routing

When TV routing is enabled:
- ✅ High-frequency tick stream
- ✅ Low-latency execution
- ✅ Instant partial fills
- ✅ Chart-synchronized PnL

### ⚠️ CRITICAL: EXIT ORDERS USE MARKET ONLY

**Exits ALWAYS use MARKET orders - NO limit orders!**

This prevents stranded orders when price moves away from limit price.

```python
# In AdvancedExitManager.initiate_exit():
order = ExitOrder(
    order_type="Market",  # ALWAYS market - no limit orders
    ...
)
```

### 📍 Latest Working Files:
```
recorder_service_v2.py  ← V2 Engine (4,407 lines)
tradovate_integration.py ← Tradovate API + TV routing detection (1,869 lines)
ultra_simple_server.py   ← Main server + TV routing endpoint (9,755 lines)
```

### 📝 Full Architecture:
See **`JUST_TRADES_TRADEMANAGER_REPLICA.md`** for complete documentation.

---

## 🔴 CRITICAL UPDATE - DEC 8, 2025 (Evening Session) 🔴

**THREE MAJOR BUGS FIXED IN TRADING ENGINE:**

### 1. ✅ FIXED: SHORT Close Was Sending SELL Instead of BUY
**File:** `recorder_service.py` line ~1304
**Problem:** When SHORT position hit TP, system sent SELL (adding to short) instead of BUY (closing short)
**Impact:** Position went from -3 to -4 instead of closing, caused $3+ losses
**Fix:** Changed `action='CLOSE'` to `action=close_action` where `close_action = 'BUY' for SHORT`

### 2. ✅ FIXED: Trades Recording When Broker Rejected
**File:** `recorder_service.py` lines ~3048, ~3213
**Problem:** Even when broker returned error `{}`, system recorded trade in DB anyway
**Impact:** DB showed 3 contracts, broker had 0 = complete mismatch
**Fix:** Only record trade if `broker_result.get('success') and broker_result.get('fill_price')`

### 3. ✅ FIXED: Redundant Close Orders Flipping Position
**File:** `recorder_service.py` line ~1298
**Problem:** TP limit filled on broker, but system detected TP via polling and sent ANOTHER close
**Impact:** Position flipped to opposite side
**Fix:** Added `check_broker_position_exists()` - query broker BEFORE sending close order

---

## 🏗️ ARCHITECTURE UPDATE - DEC 5, 2025 🏗️

**⚠️ THE SYSTEM NOW USES A 3-SERVER MICROSERVICES ARCHITECTURE**

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Server (port 8082)                   │
│  • OAuth & Authentication                                    │
│  • Dashboard UI (all templates)                              │
│  • Copy Trading                                              │
│  • Account Management                                        │
│  • Webhooks → PROXY to Trading Engine                        │
│  • Insider Signals UI → PROXY to Insider Service             │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP Proxy
              ┌─────────────┴─────────────┐
              ▼                           ▼
┌─────────────────────────────┐  ┌─────────────────────────────┐
│  Trading Engine (port 8083) │  │  Insider Service (port 8084)│
│  • Webhook Processing       │  │  • SEC EDGAR Form 4 polling │
│  • TP/SL Monitoring         │  │  • 13D/13G Activist filings │
│  • V2 Engine (TradeManager) │  │  • Signal Scoring (0-100)   │
│  • DCA Engine               │  │  • Watchlist management     │
│  • TradingView WebSocket    │  │  • Stock price lookup       │
└─────────────┬───────────────┘  └─────────────┬───────────────┘
              │                                │
              └─────────────┬─────────────────┘
                            ▼
                    ┌───────────────┐
                    │ just_trades.db│
                    │ recorder_v2.db│
                    └───────────────┘
```

### HOW TO START THE SYSTEM
```bash
./start_services.sh   # Starts all 3 servers in correct order
```

### KEY FILES
| File | Port | Purpose |
|------|------|---------|
| `ultra_simple_server.py` | 8082 | Main Server (OAuth, UI, proxies) |
| `recorder_service.py` | 8083 | Trading Engine (imports V2) |
| `recorder_service_v2.py` | - | V2 Engine (TradeManager replica) |
| `insider_service.py` | 8084 | Insider Signals (SEC EDGAR data) |
| `start_services.sh` | - | Startup script |

---

## ⛔ ABSOLUTE RULES - VIOLATION = BROKEN CODE

### RULE 0: ASK PERMISSION FOR EVERY SINGLE FILE
- Before touching ANY file, say: "I want to modify [filename] to [change]. Is this okay?"
- WAIT for the user to say "yes" or "approved"
- If the user hasn't explicitly approved, DO NOT TOUCH THE FILE

### RULE 1: NEVER MODIFY THESE FILES WITHOUT EXPLICIT USER PERMISSION
```
LOCKED FILES - DO NOT TOUCH:
├── ultra_simple_server.py          ← CORE SERVER - ASK FIRST
├── templates/manual_copy_trader.html   ← MANUAL TRADER - ASK FIRST
├── templates/account_management.html   ← ACCOUNT MGMT - NEVER TOUCH
├── templates/recorders.html            ← RECORDERS - ASK FIRST
├── templates/dashboard.html            ← DASHBOARD - ASK FIRST
├── templates/control_center.html       ← CONTROL CENTER - ASK FIRST
└── just_trades.db                      ← DATABASE - NEVER MODIFY SCHEMA
```

### RULE 2: THINGS YOU MUST NEVER DO
- ❌ **NEVER** refactor code that's working
- ❌ **NEVER** remove code you think is "unused"
- ❌ **NEVER** use LIMIT orders for exits (always MARKET)
- ❌ **NEVER** change database schemas without explicit approval
- ❌ **NEVER** modify multiple tabs at once

---

## ✅ WHAT'S WORKING (DO NOT BREAK)

| Feature | Status | Files Involved |
|---------|--------|----------------|
| **V2 Trading Engine** | ✅ Working | `recorder_service_v2.py` |
| **TradeManager-style Exits** | ✅ Working | `AdvancedExitManager` (MARKET orders) |
| **DCA Engine** | ✅ Working | State persistence across restarts |
| **TradingView Routing Detection** | ✅ Working | `/api/accounts/<id>/check-tradingview-routing` |
| **Manual Trader** | ✅ Working | `manual_copy_trader.html` |
| **Live Position Cards** | ✅ Working | WebSocket `position_update` event |
| **Recorders Tab** | ✅ Working | `recorders.html` |
| **Webhook Signals** | ✅ Working | `/webhook/<token>` endpoint |
| **Dashboard** | ✅ Working | `dashboard.html` |
| **Tradovate OAuth** | ✅ Working | OAuth flow with LIVE+DEMO fallback |

---

## 🔒 WORKING STATE BACKUP (Dec 11, 2025)

### Latest Backup
```
backups/WORKING_STATE_DEC11_2025_V2_ENGINE/
├── recorder_service_v2.py       ← V2 Engine with TradeManager replica
├── tradovate_integration.py     ← TV routing detection
├── ultra_simple_server.py       ← Main server
└── START_HERE.md                ← This file
```

### Git Tags
```bash
git tag WORKING_DEC11_2025_V2_ENGINE
git tag WORKING_DEC8_2025_TRADING_FIX
git tag WORKING_DEC5_2025_COMPLETE
```

---

## 📊 V2 ENGINE COMPONENTS (Dec 11, 2025)

### DCA Engine
- **Trigger Types:** TICKS, PERCENT, ATR
- **State Persistence:** `dca_triggered_indices_json` column prevents double-triggers after restart
- **Max Qty Limits:** Configurable per strategy

### Exit Manager
- **ALWAYS uses MARKET orders** (no limit orders)
- **State Machine:** IDLE → PREPARE_EXIT → WORKING_EXIT → CONFIRM_FLAT → IDLE
- **No stranded orders** - immediate fills

### TradingView Routing
- **Check via API:** `check_tradingview_routing_enabled()` in `tradovate_integration.py`
- **UI Endpoint:** `/api/accounts/<id>/check-tradingview-routing`
- **Credentials page:** Stores username/password and auto-checks TV routing flag

### Service Layer
- `handle_tv_signal()` - Process TradingView webhooks
- `on_broker_fill()` - Process broker fills
- `on_broker_position_update()` - Process position changes
- `get_service_status()` - Control Center status API

---

## 🚫 COMMON MISTAKES TO AVOID

1. **Using LIMIT orders for exits** - ALWAYS use MARKET orders
2. **Not checking TV routing flag** - Call `check_tradingview_addon()` before live trading
3. **Adding Tradovate API calls to frequently-called endpoints** - Causes rate limiting
4. **Looking for a `settings` table** - It doesn't exist! Use `accounts` table

---

## 📞 QUICK REFERENCE

### Check V2 Engine Status
```bash
# Check recorder service logs
tail -50 /tmp/recorder.log | grep -E "V2|EXIT|DCA|MARKET"

# Check syntax
python3 -m py_compile recorder_service_v2.py
```

### Restart Services
```bash
pkill -f "python.*recorder_service"
pkill -f "python.*ultra_simple"
./start_services.sh
```

### Check TradingView Routing
```bash
curl http://localhost:8082/api/accounts/1/check-tradingview-routing
```

---

## 📅 Update Log

| Date | Change |
|------|--------|
| **Dec 11, 2025** | **V2 ENGINE: TradeManager replica complete** |
| Dec 11, 2025 | Added `BrokerEventLoop`, `AdvancedExitManager`, `ExitConfirmationLoop` |
| Dec 11, 2025 | Added `ForceFlattenKillSwitch`, `PositionDriftReconciler` |
| Dec 11, 2025 | Added TradingView routing detection (`tradingViewTradingEnabled`) |
| Dec 11, 2025 | Fixed exits to ALWAYS use MARKET orders (no limit orders) |
| Dec 11, 2025 | Added `modify_order`, `get_contract_id` to TradovateIntegration |
| Dec 11, 2025 | Added DCA state persistence (`dca_triggered_indices_json`) |
| **Dec 8, 2025** | **LIVE TRADING WORKING** - Fixed SHORT close, broker rejection, redundant orders |
| Dec 5, 2025 | Microservices architecture (8082 + 8083 + 8084) |
| Dec 4, 2025 | OAuth LIVE+DEMO fallback for rate limiting |

---

*Last updated: Dec 11, 2025 - V2 TradeManager Replica Complete*
*Backup tags: WORKING_DEC11_2025_V2_ENGINE*
*Architecture docs: JUST_TRADES_TRADEMANAGER_REPLICA.md*
