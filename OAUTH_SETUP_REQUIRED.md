# OAuth Setup Required

## What We Learned from TradersPost

TradersPost uses **OAuth redirect flow**, not direct credential authentication!

### The Real Flow:

1. **User clicks "Connect Tradovate"** in your app
2. **Your app redirects to:** `https://trader.tradovate.com/welcome?client_id=...&redirect_uri=...&response_type=code`
3. **User logs in** on Tradovate's website (not your app!)
4. **User sees permissions** and authorizes
5. **Tradovate redirects back** to your callback URL with `?code=...`
6. **Your app exchanges code** for access token
7. **Token stored** - done!

## Setup Required

### Step 1: Register Redirect URI in OAuth App

Your OAuth app needs to have the redirect URI registered:

1. **Log into Tradovate** (the account that has the OAuth app)
2. **Go to Application Settings** → **API Access** → **OAuth Registration**
3. **Edit your OAuth app** (Client ID: 8552)
4. **Add Redirect URI:**
   ```
   http://localhost:8082/auth/tradovate/callback
   ```
5. **For production, also add:**
   ```
   https://yourdomain.com/auth/tradovate/callback
   ```

### Step 2: Test the OAuth Flow

1. **Start your server:**
   ```bash
   python3 ultra_simple_server.py
   ```

2. **Visit in browser:**
   ```
   http://localhost:8082/api/accounts/4/connect
   ```

3. **You should be redirected to:**
   ```
   https://trader.tradovate.com/welcome?client_id=8552&redirect_uri=...
   ```

4. **Log in with Tradovate credentials**

5. **Authorize the app**

6. **You'll be redirected back** to your callback

7. **Token will be stored automatically**

## Permissions Requested

Based on TradersPost's flow, we request:
- **Read Only:** Profile, Positions, Accounting, Prices, etc.
- **Full Access:** Orders (to place trades)

## Why This Works

- ✅ **No TradingView add-on needed** - OAuth bypasses that requirement
- ✅ **No API Access subscription needed**
- ✅ **User authorizes in Tradovate's website** - more secure
- ✅ **Standard OAuth flow** - same as TradersPost

## Testing

After setting up redirect URI:

```bash
# Test OAuth flow
curl -L http://localhost:8082/api/accounts/4/connect

# Or visit in browser:
# http://localhost:8082/api/accounts/4/connect
```

You should be redirected to Tradovate's login page!

