# How to Get TradingView API Credentials (Mac Guide)

## Overview
To connect to TradingView's API, you need three pieces of information:
- **Session ID**
- **Session Signed ID**
- **Token**

## Method 1: Manual Extraction via Browser Developer Tools (Mac)

### Step 1: Log into TradingView
1. Open your web browser (Safari, Chrome, Firefox, or Edge)
2. Go to https://www.tradingview.com
3. Log in to your TradingView account

### Step 2: Open Developer Tools (Mac Keyboard Shortcuts)
- **Safari**: 
  - First enable Developer menu: Safari → Settings → Advanced → Check "Show Develop menu"
  - Then press `Cmd+Option+I` or go to Develop → Show Web Inspector
- **Chrome/Edge**: Press `Cmd+Option+I`
- **Firefox**: Press `Cmd+Option+I`

### Step 3: Access Application/Storage Tab
1. Click on the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox)
2. In the left sidebar, expand **Cookies**
3. Click on `https://www.tradingview.com`

### Step 4: Find the Required Values
Look for these cookies in the list:

- **`sessionid`** - This is your **Session ID**
- **`sessionid_sign`** - This is your **Session Signed ID**

### Step 5: Find the Token
The token is typically stored in localStorage:

1. In the same Developer Tools window, look for **Local Storage** in the left sidebar
2. Click on `https://www.tradingview.com`
3. Look for a key that contains "token" or "auth_token"
4. Copy the value - this is your **Token**

Alternatively, check **Session Storage** if it's not in Local Storage.

## Method 2: Using Network Tab (Alternative - Mac)

1. With Developer Tools open, go to the **Network** tab
2. Refresh the page (`Cmd+R`)
3. Look for API requests to `tradingview.com`
4. Click on any request
5. In the **Headers** section, look at:
   - **Request Headers** → `Cookie` header (contains sessionid and sessionid_sign)
   - **Response Headers** → May contain token information

## Method 3: Windows Tool (If Available)

If the form provides a download link for a Windows tool:
1. Click "Download Tool to extract details (Windows Required)"
2. Follow the tool's instructions
3. The tool will automatically extract and display the credentials

## Important Notes

⚠️ **Security Warning:**
- These credentials provide access to your TradingView account
- Keep them secure and don't share them publicly
- They may expire when you log out or after a period of inactivity
- You may need to refresh them if your session expires

⚠️ **Session Expiration:**
- TradingView sessions can expire after periods of inactivity
- If your connection stops working, you may need to extract new credentials
- Re-login to TradingView and repeat the extraction process

## Troubleshooting

**Can't find the cookies?**
- Make sure you're logged into TradingView
- Try refreshing the page after opening Developer Tools
- Clear your browser cache and log in again

**Token not in Local Storage?**
- Check Session Storage instead
- Look for keys with names like: `auth_token`, `access_token`, `token`, `api_token`
- Some implementations may use different storage methods

**Values seem incorrect?**
- Ensure you're copying the entire value (some are long strings)
- Double-check for any extra spaces or characters
- Try extracting fresh values after a fresh login

## Quick Reference (Mac)

1. Log into TradingView website
2. Open Developer Tools (`Cmd+Option+I`)
3. Go to Application/Storage tab
4. Cookies → Find `sessionid` and `sessionid_sign`
5. Local Storage → Find token value
6. Copy all three values to your form

## Mac-Specific Tips

**If using Safari:**
- Safari requires you to enable the Developer menu first:
  1. Go to **Safari** → **Settings** (or **Preferences**)
  2. Click the **Advanced** tab
  3. Check the box "Show Develop menu in menu bar"
  4. Now you can use `Cmd+Option+I` or Develop → Show Web Inspector

**If Developer Tools won't open:**
- Try right-clicking on the TradingView page and selecting "Inspect Element" (Chrome/Firefox)
- Or use View → Developer → Developer Tools from the menu bar

