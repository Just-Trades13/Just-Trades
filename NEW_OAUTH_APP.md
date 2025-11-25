# New OAuth App Configuration

## OAuth App Credentials

**Client ID:** `8556`
**Client Secret:** `65a4a390-0acc-4102-b383-972348434f05`

## What Was Updated

1. ✅ **Database:** Account updated with new Client ID and Secret
2. ✅ **Code:** Fallback values updated to new credentials
3. ✅ **Server:** Restarted with new credentials

## OAuth App Requirements

Make sure your OAuth app in Tradovate is configured with:

1. **Redirect URI:**
   ```
   https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback
   ```
   - Must match exactly (no trailing slash)
   - Must be https (not http)

2. **Permissions:**
   - Orders: FullAccess
   - Positions: Read
   - Prices: Read
   - Other: Read (optional)

3. **App Details:**
   - App Name: Just.Trade (or your app name)
   - Logo: Your custom logo ✅
   - Privacy Policy: Required
   - Terms: Required

## Testing

### Step 1: Verify OAuth App Settings

1. **Log into Tradovate**
   - Go to: https://tradovate.com
   - Application Settings → API Access → OAuth Registration
   - Edit your OAuth app (Client ID: 8556)

2. **Check redirect URI:**
   - Should be: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
   - Update if needed
   - Save

### Step 2: Test OAuth Flow

1. **Start OAuth:**
   ```
   http://localhost:8082/api/accounts/4/connect
   ```

2. **You should see:**
   - OAuth authorization page
   - "JUST TRADES" logo (your custom logo) ✅
   - Permissions list
   - Login form

3. **Log in and authorize:**
   - Enter credentials
   - Click "Login"
   - Click "Authorize"

4. **After authorization:**
   - Should redirect to callback URL
   - Token should be stored
   - Should redirect to accounts page

### Step 3: Verify Token Storage

After authorization, verify token was stored:

```bash
python3 verify_oauth_success.py
```

Or check database:
```sql
SELECT id, name, client_id, tradovate_token, token_expires_at
FROM accounts
WHERE id = 4;
```

## Success Indicators

✅ OAuth authorization page shows
✅ Custom logo is displayed
✅ Permissions are shown
✅ You can log in and authorize
✅ Browser redirects to callback URL
✅ Token is stored in database
✅ You're redirected to accounts page

## Troubleshooting

### If OAuth page doesn't show:

1. **Check Client ID:**
   - Should be: `8556`
   - Verify in database: `SELECT client_id FROM accounts WHERE id = 4;`

2. **Check OAuth app:**
   - Is it active/enabled?
   - Is redirect URI correct?
   - Are permissions set?

### If callback doesn't work:

1. **Check redirect URI:**
   - Must match exactly: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
   - No trailing slash
   - Must be https

2. **Check server logs:**
   ```bash
   tail -f server.log | grep -E "OAuth|callback|token"
   ```

### If token exchange fails:

1. **Check Client Secret:**
   - Should be: `65a4a390-0acc-4102-b383-972348434f05`
   - Verify in database: `SELECT client_secret FROM accounts WHERE id = 4;`

2. **Check redirect URI:**
   - Must match exactly what was used in authorization request

## Next Steps

1. ✅ OAuth credentials updated
2. ✅ Server restarted
3. ⏳ Test OAuth flow
4. ⏳ Verify token storage
5. ⏳ Test API calls with token

## Notes

- **Client ID:** `8556` (new OAuth app)
- **Client Secret:** `65a4a390-0acc-4102-b383-972348434f05` (new OAuth app)
- **Redirect URI:** `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
- **State Storage:** Database (works across domains)
- **Logo:** Custom "JUST TRADES" logo ✅

