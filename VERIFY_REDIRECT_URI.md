# Verify Redirect URI Configuration

## Current Status

✅ OAuth authorization page works
✅ Callback endpoint is accessible
❓ Need to verify redirect URI matches after authorization

## Critical Check: Redirect URI in OAuth App

The redirect URI in your OAuth app **MUST** match exactly what's used in the OAuth request.

### Current OAuth Request Uses:
```
https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback
```

### OAuth App Must Have:
```
https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback
```

**Must match exactly:**
- ✅ Same protocol (https)
- ✅ Same domain (clay-ungilled-heedlessly.ngrok-free.dev)
- ✅ Same path (/auth/tradovate/callback)
- ✅ No trailing slash
- ✅ No query parameters

## How to Verify

### Step 1: Check OAuth App Settings

1. **Log into Tradovate**
   - Go to: https://tradovate.com
   - Application Settings → API Access → OAuth Registration
   - Edit your OAuth app

2. **Check Redirect URI:**
   - Should be: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
   - If it's different, update it
   - Save

### Step 2: Test OAuth Flow

1. **Start OAuth:**
   ```
   http://localhost:8082/api/accounts/4/connect
   ```

2. **Check OAuth URL in browser:**
   - After redirect, check the URL
   - Should include: `redirect_uri=https%3A%2F%2Fclay-ungilled-heedlessly.ngrok-free.dev%2Fauth%2Ftradovate%2Fcallback`
   - (URL encoded version of the redirect URI)

3. **Log in and authorize**

4. **After authorization:**
   - Browser should redirect to: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback?code=...&state=...`
   - If it doesn't redirect, or redirects to a different URL, the redirect URI doesn't match

## Common Redirect URI Issues

### Issue 1: Missing Path
- **OAuth App has:** `https://clay-ungilled-heedlessly.ngrok-free.dev`
- **Code uses:** `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
- **Result:** Redirect URI mismatch error

### Issue 2: Wrong Path
- **OAuth App has:** `https://clay-ungilled-heedlessly.ngrok-free.dev/callback`
- **Code uses:** `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
- **Result:** Redirect URI mismatch error

### Issue 3: Trailing Slash
- **OAuth App has:** `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback/`
- **Code uses:** `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
- **Result:** May cause issues (some OAuth providers are strict)

### Issue 4: HTTP vs HTTPS
- **OAuth App has:** `http://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
- **Code uses:** `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
- **Result:** Redirect URI mismatch error

## What to Check After Authorization

After you authorize on Tradovate:

1. **Browser URL:**
   - Should be: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback?code=...&state=...`
   - If different URL → Redirect URI mismatch
   - If no redirect → Check OAuth app settings

2. **Server Logs:**
   ```bash
   tail -f server.log | grep -E "OAuth|callback|token"
   ```
   - Look for: "OAuth callback received - code: present"
   - If "code: missing" → Redirect URI issue

3. **Error Messages:**
   - "redirect_uri_mismatch" → Redirect URI doesn't match
   - "invalid_client" → Client ID/Secret issue
   - "invalid_grant" → Code expired or invalid

## Fix Redirect URI

If redirect URI doesn't match:

1. **Update OAuth App:**
   - Go to: Application Settings → API Access → OAuth Registration
   - Edit your OAuth app
   - Change redirect URI to: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
   - Save

2. **Test Again:**
   - Start OAuth flow
   - Log in and authorize
   - Should now redirect correctly

## Verification Checklist

- [ ] OAuth app redirect URI is set to: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
- [ ] No trailing slash
- [ ] Uses https (not http)
- [ ] Matches exactly what code uses
- [ ] OAuth app is active/enabled
- [ ] Tested complete OAuth flow
- [ ] Browser redirects to callback URL after authorization
- [ ] Callback URL has `code=` parameter
- [ ] Server logs show "code: present"

