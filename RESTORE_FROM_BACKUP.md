# 🔄 RESTORE FROM BACKUP - Quick Reference

**If another context window breaks things, use this guide to restore.**

---

## ✅ Current Status (Restored)

- ✅ Account dropdown fixed - now parses JSON strings correctly
- ✅ Manual trader should be working
- ✅ All code matches `WORKING_STATE_BACKUP.md`

---

## 🚨 If Manual Trader Breaks Again

### Step 1: Check These Files Match Backup

1. **`templates/control_center.html`** - `loadAccountsForManualTrader()` function
   - Must parse both array and JSON string formats
   - Must handle `tradovate_accounts` and `subaccounts`
   - Must be `async function` (not regular function)

2. **`ultra_simple_server.py`** - `/api/manual-trade` endpoint
   - Must use `token_container` for async scoping
   - Must convert symbol AFTER getting access_token
   - Must only refresh token if expired (5-minute buffer)

3. **`phantom_scraper/tradovate_integration.py`** - `place_order()` function
   - Must use single endpoint: `/order/placeorder`
   - Must NOT try multiple endpoints
   - Must NOT add retries

### Step 2: Restore from Backup

1. Read `WORKING_STATE_BACKUP.md` - See what was working
2. Read `WHAT_NOT_TO_DO.md` - See what broke things
3. Compare current code to backup
4. Restore any differences

### Step 3: Test

1. Restart server: `pkill -f ultra_simple_server && python3 ultra_simple_server.py > server.log 2>&1 &`
2. Open browser: `http://localhost:8082/control-center`
3. Check account dropdown has accounts
4. Place test trade: Select account, ticker (MNQ1!), quantity (1), click Buy
5. Check toast notification appears (not alert)
6. Check server logs for errors

---

## 📋 Quick Fixes

### Account Dropdown Empty?
- Check `loadAccountsForManualTrader()` is `async function`
- Check it parses JSON strings: `JSON.parse(account.tradovate_accounts)`
- Check browser console for errors

### Manual Trade Fails?
- Check token is valid (not expired)
- Check symbol conversion is working (MNQ1! → MNQZ5)
- Check server logs for Tradovate API errors

### Buttons Grey Out?
- Check `placeManualTrade()` uses `.then().catch()` (not `await`)
- Check buttons are NOT disabled in code

### Alerts Instead of Toasts?
- Check `showToast()` function exists
- Check `placeManualTrade()` uses `showToast()` (not `alert()`)

---

## 🔗 Related Files

- `WORKING_STATE_BACKUP.md` - Full backup of working state
- `WHAT_NOT_TO_DO.md` - What broke things before
- `PRE_CHANGE_CHECKLIST.md` - Checklist before making changes
- `HANDOFF_DOCUMENT.md` - Full handoff documentation

---

**Last Updated**: November 18, 2025
**Status**: ✅ RESTORED - Account dropdown fixed

