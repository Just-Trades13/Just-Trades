# Fix OAuth Redirect URI

## The Problem

Tradovate won't accept the redirect URI `http://localhost:8082/auth/tradovate/callback` because it's not registered in your OAuth app settings.

## Solution Options

### Option 1: Register the Redirect URI (Recommended)

1. **Log into Tradovate** (the account that has the OAuth app - Client ID: 8552)
2. **Go to:** Application Settings → API Access → OAuth Registration
3. **Edit your OAuth app**
4. **Add Redirect URI:**
   ```
   http://localhost:8082/auth/tradovate/callback
   ```
5. **Save**

### Option 2: Use Already Registered URI

If you already have a redirect URI registered, we can use that instead.

**Common registered URIs:**
- `http://localhost:8082`
- `http://127.0.0.1:8082`
- `http://localhost:8082/`

**To use a different URI:**

1. **Check what's registered** in your OAuth app settings
2. **Update the code** to use that URI
3. **Or set environment variable:**
   ```bash
   export TRADOVATE_REDIRECT_URI="http://localhost:8082"
   ```

### Option 3: Use ngrok for Public URL

If Tradovate doesn't allow localhost:

1. **Start ngrok:**
   ```bash
   ngrok http 8082
   ```

2. **Get the public URL** (e.g., `https://abc123.ngrok.io`)

3. **Register redirect URI in OAuth app:**
   ```
   https://abc123.ngrok.io/auth/tradovate/callback
   ```

4. **Set environment variable:**
   ```bash
   export TRADOVATE_REDIRECT_URI="https://abc123.ngrok.io/auth/tradovate/callback"
   ```

## Quick Fix

**Tell me what redirect URI is registered in your OAuth app**, and I'll update the code to use it!

Or if you want to register a new one, use:
```
http://localhost:8082/auth/tradovate/callback
```

## Testing

After fixing the redirect URI:

1. **Restart server** (if you changed code)
2. **Test in browser:**
   ```
   http://localhost:8082/api/accounts/4/connect
   ```
3. **Should redirect to Tradovate** without errors

