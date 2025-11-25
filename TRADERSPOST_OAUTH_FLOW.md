# TradersPost OAuth Redirect Flow

## What TradersPost Does

When you click "Connect Account" on TradersPost:
1. **Redirects to:** `https://trader.tradovate.com/welcome?client_id=...&redirect_uri=...&response_type=code&scope=...`
2. **Shows OAuth authorization page:**
   - "Sign In with Tradovate"
   - "to continue to TradersPost Production Env"
   - Permissions list (Read Only: Positions, etc. | Full: Orders)
   - Login form
3. **User logs in and authorizes**
4. **Redirects back to:** TradersPost callback URL with `code=...`
5. **TradersPost exchanges code for token**

## Why Your OAuth App Doesn't Work

Your current OAuth app (Client ID: 8552, App Name: "test") is configured for:
- **Credential-based authentication** (appId, cid, sec)
- **NOT OAuth redirect flow**

This is why `/welcome` shows regular login page instead of OAuth authorization page.

## Solution: Register New OAuth App for Redirect Flow

You need to register a **NEW OAuth app** specifically for OAuth redirect flow:

### Step 1: Register New OAuth App in Tradovate

1. **Log into Tradovate**
2. **Go to:** Application Settings → API Access → OAuth Registration
3. **Click "Create New OAuth App"** (or similar)
4. **Fill out form:**
   - **App Title:** Just.Trade (or your app name)
   - **Redirect URI:** 
     - For development: `https://clay-ungilled-heedlessly.ngrok-free.dev` (your ngrok URL)
     - For production: Your production domain
   - **Permissions:** Select what you need (read positions, write orders, etc.)
5. **Click "Generate"** or "Create"
6. **Save the Client ID and Client Secret** (you'll need these)

### Step 2: Update Code to Use New OAuth App

The code already supports OAuth redirect flow, but you need:
- **New Client ID** (from the new OAuth app)
- **New Client Secret** (from the new OAuth app)
- **Correct Redirect URI** (must match exactly what's registered)

### Step 3: Test OAuth Redirect Flow

1. **Visit:** `http://localhost:8082/api/accounts/4/connect`
2. **Should redirect to:** Tradovate OAuth authorization page
3. **Should show:** App name and permissions (like TradersPost)
4. **Log in and authorize**
5. **Redirects back:** With authorization code
6. **Token stored:** Automatically

## Key Differences

### Credential-Based (Your Current App)
- Uses: `appId`, `cid`, `sec`
- Endpoint: `/v1/auth/accesstokenrequest`
- Direct authentication (no redirect)
- Shows regular login page

### OAuth Redirect (TradersPost Style)
- Uses: `client_id`, `redirect_uri`, `response_type=code`
- Endpoint: `/welcome` (authorization page)
- Redirect flow (user authorizes on Tradovate)
- Shows OAuth authorization page with app name

## Next Steps

1. **Register new OAuth app** for redirect flow in Tradovate
2. **Get new Client ID and Secret**
3. **Update account in database** with new credentials
4. **Test OAuth redirect flow**

## Important Notes

- **Two different OAuth apps:** One for credential-based, one for redirect
- **Different Client IDs:** Each app has its own Client ID
- **Redirect URI must match:** Exactly what's registered in OAuth app
- **ngrok URL changes:** If you restart ngrok, update redirect URI in OAuth app
