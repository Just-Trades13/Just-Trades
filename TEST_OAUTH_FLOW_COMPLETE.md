# Test Complete OAuth Flow

## Current Status

✅ OAuth authorization page works (`http://localhost:8082/api/accounts/4/connect`)
✅ You can log in and authorize
❓ After authorization, need to verify callback works

## Expected OAuth Flow

### Step 1: Start OAuth Flow
```
Visit: http://localhost:8082/api/accounts/4/connect
```
**Expected:** Redirects to Tradovate OAuth page ✅

### Step 2: Log In and Authorize
1. Enter Tradovate credentials
2. Click "Login"
3. Review permissions
4. Click "Authorize" or "Allow"

**Expected:** OAuth page shows and works ✅

### Step 3: Tradovate Redirects Back
After authorization, Tradovate should redirect to:
```
https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback?code=AUTHORIZATION_CODE&state=UUID
```

**What to check:**
- Does the browser redirect to this URL?
- Does the URL contain `code=` parameter?
- Does the URL contain `state=` parameter?

### Step 4: Callback Processes Request
Your app should:
1. ✅ Verify state matches (CSRF protection)
2. ✅ Exchange code for access token
3. ✅ Store token in database
4. ✅ Redirect to accounts page

**What to check:**
- Check server logs: `tail -f server.log`
- Look for: "OAuth callback received - code: present"
- Look for: "✅ OAuth token stored for account 4"

## Testing Steps

### Test 1: Verify Redirect URI in OAuth App

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

### Test 2: Complete OAuth Flow

1. **Start OAuth flow:**
   ```
   http://localhost:8082/api/accounts/4/connect
   ```

2. **Log in and authorize:**
   - Enter credentials
   - Click "Login"
   - Click "Authorize"

3. **Watch browser:**
   - After authorization, watch the URL bar
   - Should redirect to: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback?code=...&state=...`
   - If it doesn't redirect, that's the issue

4. **Check server logs:**
   ```bash
   tail -f server.log | grep -E "OAuth|callback|token"
   ```
   - Look for: "OAuth callback received - code: present"
   - Look for: "Token exchange using redirect URI"
   - Look for: "✅ OAuth token stored"

5. **Verify token:**
   ```bash
   python3 verify_oauth_success.py
   ```

## Troubleshooting

### Issue 1: Redirect URI Mismatch

**Symptoms:**
- After authorization, Tradovate shows error
- Or redirects to wrong URL
- Or doesn't redirect at all

**Fix:**
- Update redirect URI in OAuth app to match exactly
- Must be: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
- No trailing slash
- Must be https

### Issue 2: Browser Doesn't Redirect

**Symptoms:**
- After authorization, browser stays on Tradovate page
- Or shows error message
- Or redirects to different URL

**Possible causes:**
- Redirect URI doesn't match
- OAuth app not configured correctly
- Tradovate blocking redirect

**Fix:**
- Check redirect URI matches exactly
- Check OAuth app is active
- Check OAuth app permissions

### Issue 3: Callback Receives No Code

**Symptoms:**
- Browser redirects to callback URL
- But URL doesn't have `code=` parameter
- Server logs show "code: missing"

**Possible causes:**
- Redirect URI mismatch
- Authorization didn't complete
- Tradovate error

**Fix:**
- Check redirect URI matches exactly
- Try authorization again
- Check Tradovate error messages

### Issue 4: State Mismatch

**Symptoms:**
- Callback receives code
- But state doesn't match
- Error: "Invalid state parameter"

**Possible causes:**
- Session lost
- Cookies disabled
- Multiple tabs/windows

**Fix:**
- Make sure cookies are enabled
- Use single browser window
- Check session is maintained

## What to Look For

### Success Indicators

✅ OAuth authorization page shows
✅ You can log in and authorize
✅ Browser redirects to callback URL with code and state
✅ Server logs show "OAuth callback received - code: present"
✅ Server logs show "Token exchange using redirect URI"
✅ Server logs show "✅ OAuth token stored for account 4"
✅ Database has token
✅ You're redirected to accounts page

### Error Indicators

❌ After authorization, browser doesn't redirect
❌ Browser redirects but URL has no `code=` parameter
❌ Server logs show "code: missing"
❌ Server logs show "State mismatch"
❌ Server logs show "Token exchange failed"

## Next Steps

1. ✅ Verify redirect URI in OAuth app
2. ✅ Test complete OAuth flow
3. ✅ Watch browser after authorization
4. ✅ Check server logs
5. ✅ Verify token storage

## Questions to Answer

After you authorize, please check:

1. **Does the browser redirect?**
   - Yes → Check URL has `code=` and `state=`
   - No → Redirect URI mismatch issue

2. **Does the URL have `code=` parameter?**
   - Yes → Callback should work
   - No → Authorization didn't complete

3. **What do server logs show?**
   - "code: present" → Good!
   - "code: missing" → Issue with redirect

4. **Is token stored?**
   - Yes → Success! ✅
   - No → Check token exchange

