# Fix OAuth Callback Redirect Issue

## The Problem

✅ OAuth authorization page works
✅ You can log in and see permissions
❌ But callback URL doesn't work after authorization

## The Solution

The redirect URI in your OAuth app must match **exactly** what's used in the OAuth request.

### Current Callback URL

```
https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback
```

### What You Need to Do

1. **Log into Tradovate**
   - Go to: https://tradovate.com
   - Log in with your account

2. **Go to Application Settings**
   - Click on "Application Settings" in account menu
   - Go to "API Access" tab
   - Click on "OAuth Registration"

3. **Edit Your OAuth App**
   - Find your OAuth app (the one showing "Test" as app name)
   - Click "Edit"

4. **Update Redirect URI**
   - **Current (probably):** `https://clay-ungilled-heedlessly.ngrok-free.dev`
   - **Change to:** `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
   - **Important:** Must include the `/auth/tradovate/callback` path!
   - Click "Save"

5. **Test Again**
   - Visit: `http://localhost:8082/api/accounts/4/connect`
   - Log in and authorize
   - Should now redirect to: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback?code=...&state=...`
   - Token will be stored automatically

## Why This Happens

Tradovate requires the redirect URI to match **exactly**:
- If OAuth app has: `https://clay-ungilled-heedlessly.ngrok-free.dev`
- But code uses: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback`
- Tradovate will reject it (redirect URI mismatch)

## Verification

After updating the redirect URI:

1. **Test OAuth flow:**
   ```bash
   # Visit in browser
   http://localhost:8082/api/accounts/4/connect
   ```

2. **After authorization, you should see:**
   - Redirect to: `https://clay-ungilled-heedlessly.ngrok-free.dev/auth/tradovate/callback?code=...&state=...`
   - Token stored message
   - Redirect to accounts page

3. **Verify token:**
   ```bash
   python3 verify_oauth_success.py
   ```

## Alternative: Use Root Path

If you prefer to use the root path (like TradersPost uses a specific path), you can:

1. **Update OAuth app redirect URI to:**
   ```
   https://clay-ungilled-heedlessly.ngrok-free.dev
   ```

2. **Update code to use root path:**
   - Change callback route from `/auth/tradovate/callback` to `/`
   - Or add root route handler

But the current setup with `/auth/tradovate/callback` is better for organization.

## Next Steps

1. ✅ Update redirect URI in OAuth app
2. ✅ Test OAuth flow again
3. ✅ Verify token was stored
4. ✅ Test API calls with stored token

