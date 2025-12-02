# Handoff Document - Trading Platform Development

## Current Date: December 2025

## System Status: ✅ MOSTLY WORKING - TRAILING STOP IN PROGRESS

### What's Working:
- ✅ Account Management - Fully working, baseline saved (DO NOT TOUCH)
- ✅ Manual Trader Buy/Sell orders place successfully
- ✅ Symbol conversion (MNQ1! → MNQZ5) working
- ✅ Dynamic contract detection for rollovers
- ✅ OAuth token refresh working
- ✅ Account connection working (demo and live accounts stored)
- ✅ Close button cancels all orders + flattens position
- ✅ Take Profit (TP) orders working
- ✅ Stop Loss (SL) orders working
- ✅ Manual trader moved to dedicated `/manual-trader` tab

### Current Issues:
- ⚠️ **Trailing Stop** - API payload being debugged (Tradovate rejecting order)
- ⚠️ **Breakeven** - Requires market data subscription (not yet implemented)

---

## Recent Changes Made

### 1. Manual Trader Moved to Dedicated Tab
- **File**: `templates/manual_copy_trader.html` (NEW)
- **Status**: ✅ Working
- **Features**:
  - Removed from control center
  - New route: `/manual-trader`
  - Added to navigation in `layout.html`
  - Isolated from other control center features

### 2. Account Management Restored
- **File**: `templates/account_management.html`
- **Status**: ✅ Fully Working - DO NOT TOUCH
- **Features**:
  - Shows real accounts (not mock data)
  - Displays live account number (green) and demo account number (orange)
  - Refresh button updates subaccounts
  - Removed Clear Trades and Delete buttons from header
  - Removed settings gear icon from cards
- **Snapshot**: `ACCOUNT_MGMT_SNAPSHOT.md` + `backups/2025-11-25/`

### 3. Risk Controls Added (ATM-style)
- **File**: `templates/manual_copy_trader.html`
- **Status**: ✅ TP/SL Working, ⚠️ Trailing/Breakeven In Progress
- **Features**:
  - Take Profit (ticks) - ✅ Working
  - Stop Loss (ticks) - ✅ Working
  - Trailing Stop (activation/offset ticks) - ⚠️ Debugging
  - Breakeven (trigger ticks) - ⚠️ Requires market data
- **Backend**: `apply_risk_orders()` places bracket orders after entry

### 4. Close Button Enhanced
- **File**: `ultra_simple_server.py` - `/api/manual-trade` endpoint
- **Status**: ✅ Working
- **Features**:
  - Cancels all working orders BEFORE flattening
  - Flattens position
  - Sweeps for remaining orders AFTER flattening
  - Mirrors Tradovate's "Close and Cancel All" functionality

### 5. OAuth Credentials Updated
- **Client ID**: `8698`
- **Client Secret**: `09242e35-2640-4aee-825e-deeaf6029fe4`
- **Redirect URI**: `https://clay-ungilled-heedlessly.ngrok-free.dev/api/oauth/callback`

---

## Current Problems

### 1. Trailing Stop Order Rejection
- **Issue**: Tradovate API rejecting trailing stop orders
- **Error**: `Error: 0, message='Attempt to decode JSON with unexpected mimetype: ', url=URL('https://demo.tradovateapi.com/v1/order/placeorder')`
- **Files to Check**:
  - `phantom_scraper/tradovate_integration.py` - `create_trailing_stop_order()`
  - `ultra_simple_server.py` - `apply_risk_orders()`
  - `openapi.json` - TrailingStop order structure
- **Next Steps**: Review Tradovate API docs for correct `TrailingStop` payload structure

### 2. Breakeven Requires Market Data
- **Issue**: Breakeven logic needs real-time quotes to trigger
- **Status**: Not yet implemented (requires WebSocket market data subscription)
- **Files**: Market data subscription not yet integrated

---

## Key Files & Functions

### Backend (`ultra_simple_server.py`):
- **Line 100**: `convert_tradingview_to_tradovate_symbol()` - Symbol conversion
- **Line 114**: `apply_risk_orders()` - Places TP/SL/Trailing orders after entry
- **Line 762**: `/api/manual-trade` - Manual trade endpoint
- **Line 757**: `/manual-trader` - Manual trader page route
- **Function**: `fetch_and_store_tradovate_accounts()` - Fetches from both demo and live

### Frontend (`templates/manual_copy_trader.html`):
- **Function**: `loadAccountsForManualTrader()` - Load accounts dropdown from `/api/accounts`
- **Function**: `placeManualTrade()` - Place trade with risk settings
- **Risk Settings**: TP, SL, Trailing Stop, Breakeven inputs

### Integration (`phantom_scraper/tradovate_integration.py`):
- **Method**: `place_order()` - Handles 401 retry with token refresh
- **Method**: `get_positions()` - Uses `/position/list` endpoint
- **Method**: `get_orders()` - Uses `/order/list` endpoint
- **Method**: `cancel_order()` - Uses `/order/cancelorder` endpoint
- **Method**: `create_trailing_stop_order()` - Creates TrailingStop order payload

---

## Database Schema

### `recorded_positions` table:
```sql
- id (PRIMARY KEY)
- account_id (NOT NULL)
- symbol (VARCHAR(20)) - Converted symbol (MNQZ5)
- original_symbol (VARCHAR(20)) - TradingView symbol (MNQ1!)
- tradovate_symbol (VARCHAR(20)) - Converted symbol (MNQZ5)
- contract_id (VARCHAR(50))
- side (VARCHAR(10)) - Buy/Sell
- quantity (INTEGER)
- entry_price (FLOAT)
- entry_timestamp (DATETIME)
- exit_price (FLOAT)
- exit_timestamp (DATETIME)
- status (VARCHAR(20)) - 'open' or 'closed'
- tradovate_order_id (VARCHAR(50))
```

---

## Important Rules & Guidelines

### ⚠️ CRITICAL: Read Before Making Changes
1. **Read `WHAT_NOT_TO_DO.md`** - Lists mistakes to avoid
2. **Read `PRE_CHANGE_CHECKLIST.md`** - Mandatory checklist
3. **Never change working code** unless explicitly asked
4. **Verify problems exist** before fixing
5. **Make one small change at a time**

### Files to Read First:
- `WHAT_NOT_TO_DO.md` - What NOT to do
- `PRE_CHANGE_CHECKLIST.md` - Pre-change checklist
- `.cursorrules` - Project rules

---

## API Endpoints

### Working Endpoints:
- `GET /api/accounts` - Get all accounts (returns 1 account: Mark)
- `POST /api/manual-trade` - Place manual trade
- `GET /api/positions` - Get all positions
- `GET /api/live-strategies` - Get live strategies

### Manual Trade Request Format:
```json
{
  "account_subaccount": "1:26029294",
  "symbol": "MNQ1!",
  "side": "Buy",
  "quantity": 1
}
```

---

## Symbol Conversion Details

### TradingView → Tradovate:
- `MNQ1!` → `MNQZ5` (or current front month)
- `MES1!` → `MESZ5`
- `ES1!` → `ESZ5`
- `NQ1!` → `NQZ5`

### How It Works:
1. Checks if already Tradovate format (returns as-is)
2. Strips TradingView suffix (1!, 2!, etc.)
3. Tries dynamic detection from Tradovate API (if access_token provided)
4. Falls back to hardcoded map if API unavailable

### Contract Rollover:
- Automatically detects front month from Tradovate API
- Cached for 1 hour
- No manual updates needed when contracts expire

---

## Next Steps (When Ready)

### Immediate:
1. **Fix account dropdown** - Debug why accounts aren't showing
2. **Test position tracking** - Verify positions are recorded correctly
3. **Test symbol conversion** - Verify different tickers work

### Future:
1. Display recorded positions in UI
2. Update positions when closed
3. Show position history
4. TradingView webhook integration (symbol conversion ready)

---

## Testing Checklist

### Manual Trader:
- [ ] Accounts appear in dropdown
- [ ] Can select account
- [ ] Can select ticker
- [ ] Buy button places order
- [ ] Sell button places order
- [ ] Toast notification appears (no blocking alert)
- [ ] Toast auto-dismisses after 2.5 seconds
- [ ] Buttons stay clickable (no grey-out)

### Position Tracking:
- [ ] Positions recorded in database when trade placed
- [ ] Both original and converted symbols stored
- [ ] Entry price recorded (approximate from quote)

### Symbol Conversion:
- [ ] MNQ1! converts to MNQZ5 (or current front month)
- [ ] Works for different tickers (MES1!, ES1!, etc.)
- [ ] Already-converted symbols pass through unchanged

---

## Server Status

- **Port**: 8082
- **Status**: Running
- **Logs**: `server.log`
- **Template Auto-Reload**: Enabled
- **Browser Cache**: Disabled for development

### To Restart Server:
```bash
pkill -f "python.*ultra_simple_server"
sleep 2
nohup python3 ultra_simple_server.py > server.log 2>&1 &
```

---

## Known Issues

1. **Account dropdown empty** - Need to debug `loadAccountsForManualTrader()`
2. **Position display** - Positions are recorded but not displayed in UI yet
3. **Position closing** - Close button works but position status not updated in database

---

## Important Notes

- **Manual trader is working** - Don't break it!
- **Symbol conversion is critical** - Required for orders to work
- **Position recording is new** - May need refinement
- **Toast notifications replace alerts** - No blocking dialogs
- **Buttons never disable** - For instant trading

---

## Contact Points

- **Main Server File**: `ultra_simple_server.py`
- **Frontend**: `templates/control_center.html`
- **Integration**: `phantom_scraper/tradovate_integration.py`
- **Database**: `just_trades.db`

---

## Quick Reference

### To Place a Trade:
1. Select account from dropdown
2. Select ticker (e.g., MNQ1!)
3. Enter quantity
4. Click Buy or Sell
5. Toast notification appears (auto-dismisses)

### To Debug:
1. Check browser console (F12)
2. Check server logs: `tail -f server.log`
3. Check database: `sqlite3 just_trades.db`
4. Test API: `curl http://localhost:8082/api/accounts`

---

**Last Updated**: November 18, 2025
**Status**: Manual trader working, account dropdown needs fix

