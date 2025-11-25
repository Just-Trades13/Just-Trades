# Tradovate OAuth & Trading Fix - Complete Solution

**Date:** November 18, 2025  
**Status:** ✅ WORKING - Trades are successfully placing on Tradovate

---

## 🎯 Problem Summary

1. **OAuth tokens had numeric `phs` value** instead of array, causing "Access is denied" errors
2. **Symbol format mismatch**: TradingView uses "MNQ1!" (continuous contract), Tradovate needs "MNQZ5" (front month contract)
3. **Accounts page not showing subaccounts** after OAuth connection

---

## ✅ Solutions Implemented

### 1. OAuth Scope & Endpoint Fixes

**OAuth Authorization URL:**
- **Scope:** `scope=read+write+trade+marketdata+order` (space-separated, urlencode converts to `+`)
- **Endpoint:** `https://trader.tradovate.com/oauth` (authorization)
- **Token Exchange:** `https://demo.tradovateapi.com/v1/oauth/token` (primary) or `/auth/oauthtoken` (fallback)

**Key Finding:** Tokens work for trading even when `phs` is a number (not an array). The validation that rejected numeric `phs` was too strict.

**Location:** `ultra_simple_server.py` lines 2389-2417, 2752-2757

### 2. Symbol Conversion Fix (CRITICAL)

**Problem:** TradingView symbols like "MNQ1!" don't work with Tradovate API. Tradovate requires actual contract symbols like "MNQZ5".

**Solution:** Added `convert_tradingview_to_tradovate_symbol()` function that:
- Detects if symbol is already in Tradovate format (e.g., "MNQZ5") and leaves it unchanged
- Converts TradingView continuous contracts (e.g., "MNQ1!") to Tradovate front month contracts (e.g., "MNQZ5")
- Maps common symbols:
  - `MNQ1!` → `MNQZ5` (Micro E-mini Nasdaq - December 2025)
  - `MES1!` → `MESZ5` (Micro E-mini S&P 500 - December 2025)
  - `ES1!` → `ESZ5` (E-mini S&P 500 - December 2025)
  - `NQ1!` → `NQZ5` (E-mini Nasdaq - December 2025)

**Location:** `ultra_simple_server.py` lines 100-151, 1826-1831

**Applied to:** Manual trade endpoint (`/api/manual-trade`)

### 3. Token Validation Update

**Changed:** Token validation now allows tokens with numeric `phs` values, since they actually work for trading.

**Key Insight:** The `phs` field format doesn't determine trading permissions - the OAuth app permissions and user account settings do.

**Location:** `ultra_simple_server.py` lines 1908-1914

---

## 🔑 Key Learnings

### Token Permissions
- ✅ Tokens with `phs` as a **number** (e.g., `-508239039`) **DO work** for trading
- ✅ Tokens with `phs` as an **array** (e.g., `["Order.Read", "Order.Write"]`) also work
- ❌ The `phs` format is NOT the indicator of trading permissions
- ✅ What matters: OAuth app has "Orders: Full Access" enabled AND user account has API trading enabled

### Symbol Format Requirements
- ❌ **TradingView format:** `MNQ1!` (continuous contract) - **DOES NOT WORK** with Tradovate API
- ✅ **Tradovate format:** `MNQZ5` (front month contract) - **REQUIRED** for API orders
- ✅ **Solution:** Auto-convert TradingView symbols to Tradovate format before placing orders

### OAuth Flow
1. User clicks "Connect" → Redirected to Tradovate OAuth
2. User authorizes → Tradovate redirects back with `code`
3. Backend exchanges `code` for `access_token` and `refresh_token`
4. Token stored in database with expiration time
5. Accounts/subaccounts fetched and stored

### Token Endpoints
- **Authorization:** `https://trader.tradovate.com/oauth` (user-facing)
- **Token Exchange (Primary):** `https://demo.tradovateapi.com/v1/oauth/token` (OAuth 2.0 standard)
- **Token Exchange (Fallback):** `https://demo.tradovateapi.com/v1/auth/oauthtoken` (legacy)
- **API Calls:** `https://demo.tradovateapi.com/v1/...` (all API endpoints)

---

## 📋 Order Placement Format

**Tradovate API Order Format:**
```json
{
  "accountId": 26029294,
  "action": "Sell",
  "symbol": "MNQZ5",
  "orderType": "Market",
  "orderQty": 1,
  "isAutomated": true
}
```

**Endpoint:** `POST https://demo.tradovateapi.com/v1/order/placeorder`  
**Headers:** `Authorization: Bearer <access_token>`

**Response (Success):**
```json
{
  "orderId": 320483156243
}
```

**Response (Failure):**
```json
{
  "failureReason": "UnknownReason",
  "failureText": "Access is denied"
}
```

---

## 🧪 Testing Results

### Direct API Test (Bypassing Backend)
- ✅ Token works for trading (even with numeric `phs`)
- ✅ Order placed successfully with "MNQZ5" → Order ID: 320483156243
- ❌ Order failed with "MNQ" → "Access is denied"

### Manual Trader Test
- ✅ Selected "MNQ1!" from dropdown
- ✅ Automatically converted to "MNQZ5"
- ✅ Order placed successfully on broker
- ✅ Works with multiple accounts (OAuth and non-OAuth)

---

## 🔧 Files Modified

1. **`ultra_simple_server.py`**
   - Added `convert_tradingview_to_tradovate_symbol()` function
   - Updated OAuth scope to include `marketdata` and `order`
   - Updated token exchange endpoints to prioritize `/oauth/token`
   - Added symbol conversion in manual trade endpoint
   - Relaxed token validation (allows numeric `phs`)

2. **`phantom_scraper/tradovate_integration.py`**
   - Fixed syntax errors (indentation issues)
   - Updated refresh endpoints to prioritize `/oauth/token`

3. **`templates/account_management.html`**
   - Added error message display for OAuth failures
   - Shows detailed instructions when token validation fails

---

## 📝 Important Notes

1. **Symbol Conversion is Critical:** Always convert TradingView symbols before placing orders
2. **Token Format Doesn't Matter:** Numeric `phs` values work fine - don't reject them
3. **OAuth App Settings:** Must have "Orders: Full Access" enabled in Tradovate
4. **User Account Settings:** User must have "API Trading" enabled in their Tradovate account
5. **Contract Expiry:** Front month contracts (Z5 = December 2025) may need updating as they expire

---

## 🚀 Current Status

✅ **OAuth Flow:** Working  
✅ **Token Storage:** Working  
✅ **Symbol Conversion:** Working  
✅ **Order Placement:** Working  
✅ **Multiple Accounts:** Working  

**Verified:** Manual trader successfully places trades on Tradovate broker accounts.

---

## 🔄 Future Maintenance

### Contract Expiry Updates
As futures contracts expire, update the symbol map in `convert_tradingview_to_tradovate_symbol()`:
- Current: December 2025 contracts (Z5)
- Next: March 2026 contracts (H6)
- Update the `symbol_map` dictionary when front month changes

### Symbol Detection
Consider querying Tradovate API for available contracts to auto-detect front month instead of hardcoding.

---

**Last Updated:** November 18, 2025  
**Tested By:** User confirmed working with live trades

