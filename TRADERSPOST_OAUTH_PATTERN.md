# TradersPost OAuth Pattern Analysis

## Network Flow Analysis

From TradersPost's network requests when connecting Tradovate account:

### OAuth Request
```
GET /oauth?response_type=code&client_id=2601&redirect_uri=https://traderspost.io/app/trading/...&scope=All
```

### Key Parameters

1. **Client ID:** `2601` (TradersPost's OAuth app)
2. **Scope:** `All` (not `read write`)
3. **Endpoint:** `/oauth` (not `/welcome`)
4. **Redirect URI:** `https://traderspost.io/app/trading/...` (production domain)
5. **Response Type:** `code` (standard OAuth)

### Full OAuth URL Pattern

```
https://trader.tradovate.com/oauth?response_type=code&client_id=2601&redirect_uri=https://traderspost.io/app/trading/...&scope=All
```

Or possibly:
```
https://live.tradovateapi.com/oauth?response_type=code&client_id=2601&redirect_uri=https://traderspost.io/app/trading/...&scope=All
```

## What We Updated

1. **Scope:** Changed from `read write` to `All` (matches TradersPost)
2. **Endpoint:** Changed from `/welcome` to `/oauth` (matches TradersPost)
3. **Redirect URI:** Uses ngrok URL or production domain

## Your Implementation

After registering a new OAuth app for redirect flow:

### OAuth URL
```
https://trader.tradovate.com/oauth?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&scope=All&state=ACCOUNT_ID
```

### Redirect URI Options

**Development:**
- `https://clay-ungilled-heedlessly.ngrok-free.dev` (your ngrok URL)
- Or: `https://YOUR_NGROK_URL.ngrok-free.dev`

**Production:**
- `https://yourdomain.com/auth/tradovate/callback`
- Or: `https://yourdomain.com/app/trading/callback`

## Next Steps

1. **Register new OAuth app** in Tradovate:
   - **App Title:** Just.Trade
   - **Redirect URI:** Your ngrok URL or production domain
   - **Privacy Policy URL:** Required (e.g., https://yourdomain.com/privacy)
   - **Terms URL:** Required (e.g., https://yourdomain.com/terms)
   - **Logo:** Optional (upload your app logo)
   - **Permissions:**
     - Orders: FullAccess (required for trading)
     - Positions: Read (required for viewing positions)
     - Prices: Read (required for market data)
     - Other: Read (optional)

2. **Get Client ID and Secret** from new OAuth app

3. **Update account** in database with new credentials

4. **Test OAuth flow:**
   - Visit: `http://localhost:8082/api/accounts/4/connect`
   - Should redirect to: `https://trader.tradovate.com/oauth?...&scope=All`
   - Should show OAuth authorization page with:
     - App name: "Just.Trade"
     - Permissions list
     - Privacy policy and terms links
   - Log in and authorize
   - Redirects back with code
   - Token stored automatically

## Differences from Credential-Based

| Feature | Credential-Based (Current) | OAuth Redirect (TradersPost) |
|---------|---------------------------|------------------------------|
| Client ID | 8552 | New OAuth app ID |
| Scope | N/A | All |
| Endpoint | `/v1/auth/accesstokenrequest` | `/oauth` |
| Flow | Direct API call | Redirect → Authorize → Callback |
| User Experience | Backend handles | User authorizes on Tradovate |

## Code Changes

✅ Updated scope to `All`
✅ Updated endpoint to `/oauth`
✅ OAuth redirect flow implemented
✅ Callback handler ready
✅ Token exchange ready

## Testing

After registering new OAuth app:

1. **Test redirect:**
   ```bash
   curl -I http://localhost:8082/api/accounts/4/connect
   ```
   Should redirect to Tradovate OAuth page

2. **Check OAuth URL:**
   - Should include `scope=All`
   - Should use `/oauth` endpoint
   - Should have correct redirect_uri

3. **Complete flow:**
   - Log in on Tradovate
   - Authorize app
   - Should redirect back with code
   - Token should be stored

