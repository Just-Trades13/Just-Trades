# TradingView Add-On Requirement

## Critical Discovery

Trade Manager requires users to have the **TradingView add-on/plugin enabled** on their Tradovate account before they can connect.

## What This Means

1. **Account Requirement**: The Tradovate account must have TradingView add-on enabled
2. **API Access**: The TradingView add-on likely enables API access for third-party integrations
3. **Authentication**: Once enabled, API authentication should work (possibly bypassing CAPTCHA)

## How to Enable TradingView Add-On

### Step 1: Log into Tradovate Account
1. Go to https://demo.tradovate.com (or live)
2. Log in with the account credentials

### Step 2: Enable TradingView Add-On
1. Go to Account Settings
2. Look for "Add-ons" or "Plugins" or "Subscriptions"
3. Find "TradingView" add-on
4. Enable it (may require subscription/fee)
5. Save settings

### Step 3: Verify API Access
1. After enabling, check if API access is available
2. The account should now allow API authentication
3. Trade Manager can then sync the account

## Why This Matters

The TradingView add-on likely:
- ✅ Enables API access for the account
- ✅ Allows third-party apps to authenticate
- ✅ May bypass CAPTCHA requirements
- ✅ Provides the necessary permissions

## Our Solution

### For Your Recorder Backend:

1. **Document the requirement**: Users must enable TradingView add-on
2. **Check for add-on**: Verify account has TradingView enabled before allowing connection
3. **Authentication flow**: After add-on is enabled, authentication should work

### Updated User Flow:

1. User enables TradingView add-on in Tradovate account
2. User goes to your website → "Connect Account"
3. User enters Tradovate credentials
4. Your backend authenticates (should work now that add-on is enabled)
5. Token is stored
6. Recorder backend uses stored token

## Next Steps

1. **Enable TradingView add-on** on the sim trading account (WhitneyHughes86)
2. **Test authentication again** - should work now
3. **Update documentation** - mention TradingView add-on requirement
4. **Add validation** - check if account has TradingView enabled before allowing connection

## Testing

After enabling TradingView add-on:
1. Test authentication: `python3 test_user_credentials.py`
2. Should now get access token (no CAPTCHA or different flow)
3. Store token and test recorder backend

