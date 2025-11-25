# ⚠️ WORKING STATE BACKUP - DO NOT MODIFY

**This document preserves the last known working state of the manual trader.**

**If another context window breaks things, restore from this backup.**

---

## ✅ Last Known Working State (November 18, 2025)

### Status:
- ✅ Manual trader Buy/Sell orders working
- ✅ Symbol conversion (MNQ1! → MNQZ5) working
- ✅ Dynamic contract detection working
- ✅ Position recording in database working
- ✅ Toast notifications (non-blocking) working
- ✅ Token refresh working (only when expired)
- ✅ Account dropdown loading working

---

## 🔑 Key Working Code Sections

### 1. Manual Trade Endpoint (`ultra_simple_server.py` line ~2415)

**CRITICAL: This endpoint must:**
- Parse `account_subaccount` format: `"account_id:subaccount_id"`
- Get account from database
- Parse `tradovate_accounts` JSON to find subaccount
- Determine `is_demo` from subaccount
- Convert symbol using `convert_tradingview_to_tradovate_symbol()` AFTER getting access_token
- Only refresh token if actually expired (5-minute buffer)
- Use `token_container` dict for async function scoping
- Place order via `TradovateIntegration.place_order()`
- Record position in `recorded_positions` table after success

**DO NOT:**
- Add unnecessary token validation
- Add multiple endpoint attempts
- Add retry logic with delays
- Add order verification after placement
- Change token refresh logic to be more aggressive

### 2. Symbol Conversion (`ultra_simple_server.py` line ~107)

**Function: `convert_tradingview_to_tradovate_symbol()`**

**Must:**
- Check if already Tradovate format (return as-is)
- Strip TradingView suffix (1!, 2!, etc.)
- Try dynamic detection from Tradovate API (if access_token provided)
- Cache results for 1 hour
- Fall back to hardcoded map if API unavailable

**DO NOT:**
- Strip characters from already-correct symbols
- Apply conversion to symbols already in Tradovate format

### 3. Place Order (`phantom_scraper/tradovate_integration.py` line ~390)

**Function: `place_order()`**

**Must:**
- Use single endpoint: `/order/placeorder`
- Return success if `orderId` present
- Return failure if `failureReason` or `failureText` present
- Log errors clearly

**DO NOT:**
- Try multiple endpoints
- Add retry logic
- Add exponential backoff
- Add fallback endpoints (unless 404)

### 4. Token Refresh (`phantom_scraper/tradovate_integration.py` line ~239)

**Function: `refresh_access_token()`**

**Must:**
- Use OAuth 2.0 endpoint: `/oauth/token`
- Use form-encoded format: `grant_type=refresh_token&refresh_token=...`
- Include `client_id` and `client_secret` if provided
- Return new tokens with expiration

**DO NOT:**
- Try multiple refresh endpoints
- Try JSON format
- Add complex error handling

### 5. Frontend Manual Trade (`templates/control_center.html` line ~597)

**Function: `placeManualTrade()`**

**Must:**
- Use `fetch().then().catch()` (non-blocking)
- Show toast notifications (not alerts)
- Never disable buttons
- Never add delays

**DO NOT:**
- Use `await fetch` (blocking)
- Use `alert()` (blocking)
- Disable buttons during request
- Add `setTimeout` delays

### 6. Account Loading (`templates/control_center.html` line ~448)

**Function: `loadAccountsForManualTrader()`**

**Must:**
- Parse `tradovate_accounts` from API response
- Handle both array and JSON string formats
- Display accounts with demo/live labels
- Use format: `account_id:subaccount_id` for option values

**DO NOT:**
- Assume `tradovate_accounts` is always an array
- Skip parsing if it's a string

---

## 🚨 Critical Rules

### Token Refresh:
- **ONLY refresh if token is expired** (within 5 minutes of expiration)
- **DO NOT refresh on every request**
- **DO NOT validate token permissions before using it**

### API Calls:
- **Use single endpoint first** (don't try multiple)
- **DO NOT add retries** unless explicitly requested
- **DO NOT add delays** between calls

### Error Handling:
- **Keep it simple** - log and return error
- **DO NOT add complex retry logic**
- **DO NOT add multiple fallback endpoints**

### Frontend:
- **Never block the UI** - use non-blocking requests
- **Never disable buttons** - allow instant clicks
- **Use toast notifications** - not alerts

---

## 📋 Restore Checklist

If things break, check:

1. ✅ Is `manual_trade()` endpoint using `token_container` for async scoping?
2. ✅ Is symbol conversion called AFTER `access_token` is available?
3. ✅ Is token refresh only happening when expired (5-minute buffer)?
4. ✅ Is `place_order()` using single endpoint `/order/placeorder`?
5. ✅ Is `refresh_access_token()` using `/oauth/token` with form-encoded?
6. ✅ Is frontend using `.then().catch()` (not `await`)?
7. ✅ Are buttons NOT being disabled?
8. ✅ Are toast notifications used (not alerts)?
9. ✅ Is `loadAccountsForManualTrader()` parsing JSON strings?

---

## 🔄 How to Restore

1. **Read this file** - Understand what was working
2. **Check `WHAT_NOT_TO_DO.md`** - See what broke things before
3. **Check `PRE_CHANGE_CHECKLIST.md`** - Follow the checklist
4. **Restore code** - Use this document as reference
5. **Test manually** - Place a test trade
6. **Verify** - Check server logs for errors

---

## 📝 Files to Check

### Backend:
- `ultra_simple_server.py` - Manual trade endpoint (~line 2415)
- `phantom_scraper/tradovate_integration.py` - Place order (~line 390), Token refresh (~line 239)

### Frontend:
- `templates/control_center.html` - Manual trade function (~line 597), Account loading (~line 448)

---

## ⚠️ WARNING

**DO NOT modify working code unless:**
1. User explicitly requests the change
2. You've verified the problem exists
3. You've read `WHAT_NOT_TO_DO.md`
4. You've followed `PRE_CHANGE_CHECKLIST.md`

**The user cannot afford to break working code.**

---

**Last Updated**: November 18, 2025
**Status**: ✅ WORKING - Manual trader functional

