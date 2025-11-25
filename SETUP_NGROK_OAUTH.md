# Setup ngrok for OAuth (Tradovate doesn't accept localhost)

## The Problem

Tradovate might not accept `localhost` redirect URIs for OAuth.
This is why you're seeing a regular login page instead of OAuth authorization page.

## Solution: Use ngrok for Public URL

### Step 1: Start ngrok

```bash
ngrok http 8082
```

You'll get a public URL like:
```
https://abc123.ngrok.io
```

### Step 2: Update OAuth App in Tradovate

1. **Log into Tradovate**
2. **Go to:** Application Settings → API Access → OAuth Registration
3. **Edit OAuth app** (Client ID: 8552)
4. **Update Redirect URI** to:
   ```
   https://abc123.ngrok.io
   ```
   Or:
   ```
   https://abc123.ngrok.io/auth/tradovate/callback
   ```
5. **Save**

### Step 3: Update Code to Use ngrok URL

Set environment variable:
```bash
export TRADOVATE_REDIRECT_URI="https://abc123.ngrok.io"
```

Or update code to use ngrok URL:
```python
redirect_uri = os.getenv('NGROK_URL', 'http://localhost:8082')
```

### Step 4: Test OAuth Flow

1. **Visit:** `http://localhost:8082/api/accounts/4/connect`
2. **Should redirect to:** Tradovate OAuth page (with app name and permissions)
3. **Log in and authorize**
4. **Redirect back to:** `https://abc123.ngrok.io?code=...`
5. **Token stored automatically**

## Why This Works

- ✅ **Public URL** - Tradovate accepts it
- ✅ **OAuth authorization page** - Shows app name and permissions
- ✅ **Callback works** - ngrok forwards to your local server
- ✅ **Same as TradersPost** - They use production URLs

## Alternative: Use Production URL

If you have a production domain:
1. **Update redirect URI** in OAuth app to your production URL
2. **Deploy your app** to production
3. **Test OAuth flow** on production

## Quick Setup

```bash
# Terminal 1: Start ngrok
ngrok http 8082

# Terminal 2: Update redirect URI in Tradovate OAuth app
# Use the ngrok URL (e.g., https://abc123.ngrok.io)

# Terminal 3: Test OAuth flow
# Visit: http://localhost:8082/api/accounts/4/connect
```

## Next Steps

1. **Start ngrok**
2. **Get public URL**
3. **Update redirect URI in OAuth app**
4. **Test OAuth flow**
5. **Should see OAuth authorization page now!**

