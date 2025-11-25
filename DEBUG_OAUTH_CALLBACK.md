# Debug OAuth Callback Issue

## The Problem

✅ OAuth authorization page works (`http://localhost:8082/api/accounts/4/connect`)
✅ You can log in and authorize
❌ But after authorization, callback might not be working

## Expected Behavior

### Direct Access to Callback URL
If you visit `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback` directly:
- ✅ **Expected:** Error message (no code parameter)
- ✅ **This is normal** - callback should only be called by Tradovate after authorization

### After Authorization
After you log in and authorize on Tradovate:
1. Tradovate should redirect to: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback?code=AUTHORIZATION_CODE&state=UUID`
2. Your app receives the code
3. Token is exchanged
4. Token is stored
5. You're redirected to accounts page

## Debugging Steps

### Step 1: Verify Redirect URI in OAuth App

1. **Log into Tradovate**
   - Go to: https://tradovate.com
   - Application Settings → API Access → OAuth Registration
   - Edit your OAuth app

2. **Check redirect URI:**
   - Should be: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
   - Must match exactly (no trailing slash)
   - Must be https (not http)

3. **Update if needed:**
   - Change to: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
   - Save

### Step 2: Test OAuth Flow

1. **Start OAuth flow:**
   ```
   http://localhost:8082/api/accounts/4/connect
   ```

2. **Log in and authorize:**
   - Enter credentials
   - Click "Login"
   - Click "Authorize"

3. **Watch what happens:**
   - Check the URL in browser after authorization
   - Should redirect to: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback?code=...&state=...`
   - If it redirects somewhere else, that's the issue

### Step 3: Check Server Logs

After authorization, check server logs:

```bash
tail -f server.log | grep -E "OAuth|callback|token|state"
```

**Look for:**
- `OAuth callback received` - Callback was hit
- `code: present` - Code was received
- `Token stored` - Token was stored successfully

### Step 4: Check ngrok Logs

Check if ngrok is receiving the request:

```bash
# Check ngrok web interface
open http://127.0.0.1:4040
```

**Look for:**
- Requests to `/auth/tradovate/callback`
- Response codes (200, 400, 500)
- Query parameters (code, state)

## Common Issues

### Issue 1: Redirect URI Mismatch

**Symptoms:**
- After authorization, Tradovate shows error
- Or redirects to wrong URL

**Fix:**
- Update redirect URI in OAuth app to match exactly
- Must be: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`

### Issue 2: ngrok Not Running

**Symptoms:**
- Callback URL doesn't work
- ngrok returns error

**Fix:**
```bash
# Check if ngrok is running
ps aux | grep ngrok

# If not running, start it
ngrok http 8082
```

### Issue 3: State Mismatch

**Symptoms:**
- Callback receives code
- But state doesn't match
- Error: "Invalid state parameter"

**Fix:**
- This is CSRF protection
- Make sure session is maintained
- Check if cookies are enabled

### Issue 4: Token Exchange Fails

**Symptoms:**
- Callback receives code
- But token exchange fails
- Error in server logs

**Fix:**
- Check Client ID and Secret are correct
- Check redirect URI matches exactly
- Check token endpoint is correct

## Testing

### Test 1: Direct Access (Expected Error)

```bash
curl https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback
```

**Expected:** Error message (no code)

### Test 2: OAuth Flow

1. Visit: `http://localhost:8082/api/accounts/4/connect`
2. Log in and authorize
3. Watch browser URL after authorization
4. Check server logs
5. Verify token was stored

## Next Steps

1. ✅ Verify redirect URI in OAuth app
2. ✅ Test OAuth flow
3. ✅ Check server logs
4. ✅ Check ngrok logs
5. ✅ Verify token storage

## What to Look For

After authorization, you should see:

1. **Browser redirects to:**
   ```
   https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback?code=...&state=...
   ```

2. **Server logs show:**
   ```
   OAuth callback received - code: present, state: ...
   Token exchange using redirect URI: ...
   ✅ OAuth token stored for account 4
   ```

3. **Database shows:**
   ```sql
   SELECT tradovate_token, token_expires_at FROM accounts WHERE id = 4;
   ```

4. **You're redirected to:**
   ```
   http://localhost:8082/accounts?connected=4&success=true
   ```

## Success Indicators

✅ OAuth authorization page shows
✅ You can log in and authorize
✅ Browser redirects to callback URL with code
✅ Server logs show token stored
✅ Database has token
✅ You're redirected to accounts page

