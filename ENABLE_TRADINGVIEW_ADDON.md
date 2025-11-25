# Enable TradingView Add-On - Required Step

## The Missing Piece

Trade Manager requires users to enable the **TradingView add-on** in their Tradovate account before connecting. This is why authentication was failing with CAPTCHA.

## How to Enable TradingView Add-On

### Step 1: Log into Tradovate Account
1. Go to **https://demo.tradovate.com** (for demo account)
2. Log in with credentials:
   - Username: `WhitneyHughes86`
   - Password: `L5998E7418C1681tv=`

### Step 2: Find Add-On Settings
1. Click on your account/profile menu (top right)
2. Go to **"Account Settings"** or **"Subscriptions"**
3. Look for **"Add-ons"** or **"Plugins"** section
4. Find **"TradingView"** add-on/plugin

### Step 3: Enable TradingView Add-On
1. Click on **"TradingView"** add-on
2. Click **"Enable"** or **"Subscribe"**
3. Follow any prompts (may require subscription fee)
4. Save settings

### Step 4: Verify
1. Check that TradingView add-on shows as **"Active"** or **"Enabled"**
2. You may see a message about API access being enabled

## After Enabling

Once the TradingView add-on is enabled:

1. **Authentication should work** - No more CAPTCHA (or different flow)
2. **API access enabled** - Account can be accessed via API
3. **Trade Manager can sync** - Your account will sync in Trade Manager
4. **Your recorder can connect** - Backend can authenticate and get tokens

## Testing After Enabling

1. Run the check script:
   ```bash
   python3 check_tradingview_addon.py 4
   ```

2. Should see:
   - ✅ Authentication successful (no CAPTCHA)
   - ✅ API access enabled
   - ✅ TradingView plugin active

3. Test authentication:
   ```bash
   python3 web_auth_endpoint.py
   ```

4. Should get access token and store it automatically

## Why This Matters

The TradingView add-on:
- ✅ Enables API access for third-party integrations
- ✅ Allows Trade Manager (and your app) to authenticate
- ✅ May bypass CAPTCHA requirements
- ✅ Provides necessary permissions for API calls

## Next Steps

1. **Enable TradingView add-on** in the demo account
2. **Test authentication** - should work now
3. **Store token** - automatic after successful auth
4. **Test recorder backend** - should now be able to get positions

## Alternative: Check Your Personal Account

If your personal account already has TradingView add-on enabled:
1. Test authentication with your account
2. If it works, we know the setup is correct
3. Then enable it on the demo account

