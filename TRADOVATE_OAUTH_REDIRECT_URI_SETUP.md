# Tradovate OAuth Redirect URI Setup Guide

## ✅ What Was Fixed

1. **OAuth Authorization URL**: Changed from `demo.tradovate.com/oauth/authorize` to `trader.tradovate.com/oauth`
2. **OAuth Scope**: Updated to include `read write trade marketdata order` (required for trading)
3. **Redirect URI**: Now **REQUIRES HTTPS** (Tradovate requirement)
4. **Token Exchange**: Added fallback to try both demo and live endpoints

## 🔑 OAuth App Credentials

- **Client ID (cid)**: `8698`
- **Client Secret**: `09242e35-2640-4aee-825e-deeaf6029fe4`

## 🔗 Redirect URI Configuration

### What Redirect URI Should You Use?

The redirect URI must be a **single endpoint** (no wildcards or account IDs in the path):
```
https://[your-domain]/api/oauth/callback
```

**Important Notes:**
- ✅ **MUST use HTTPS** (not HTTP)
- ✅ Must match exactly what's registered in your Tradovate OAuth app
- ✅ **Single endpoint** - account_id is passed via OAuth state parameter (no wildcards needed)
- ✅ Tradovate does **NOT support wildcards** in redirect URIs

### Option 1: Using ngrok (Recommended for Local Development)

1. **Start ngrok** with HTTPS:
   ```bash
   ngrok http 8082
   ```

2. **Copy the HTTPS URL** (e.g., `https://abc123.ngrok.io`)

3. **Create `ngrok_url.txt`** in your project root:
   ```
   https://abc123.ngrok.io
   ```

4. **Register in Tradovate OAuth App:**
   - Go to Tradovate → Application Settings → API Access → OAuth Registration
   - Add redirect URI: `https://abc123.ngrok.io/api/oauth/callback`
   - **Note:** No wildcards needed - this single endpoint handles all accounts

### Option 2: Using Production Domain

1. **Set environment variable:**
   ```bash
   export PRODUCTION_URL=https://yourdomain.com
   ```

2. **Or create `.env` file:**
   ```
   PRODUCTION_URL=https://yourdomain.com
   ```

3. **Register in Tradovate OAuth App:**
   - Redirect URI: `https://yourdomain.com/api/oauth/callback`

### How It Works

The account_id is passed through the OAuth `state` parameter, so you only need to register **one redirect URI** for all accounts. The system automatically extracts the account_id from the state parameter when Tradovate redirects back.

## 📝 Steps to Configure in Tradovate

1. **Log into Tradovate**: https://tradovate.com
2. **Go to Application Settings** → **API Access** → **OAuth Registration**
3. **Find your OAuth app** (Client ID: 8698)
4. **Update Redirect URI** to match your HTTPS domain:
   - Example: `https://abc123.ngrok.io/api/oauth/callback`
   - Or: `https://yourdomain.com/api/oauth/callback`
   - **Important:** Use the single endpoint (no account ID in path, no wildcards)
5. **Save changes**

## 🧪 Testing the OAuth Flow

1. **Start your server** (make sure HTTPS is configured)
2. **Go to Accounts page**: `/accounts`
3. **Create a new account** or select existing
4. **Click "Connect"** on a Tradovate account
5. **You should be redirected** to Tradovate OAuth page
6. **Authorize the app**
7. **You'll be redirected back** with tokens stored

## ⚠️ Common Issues

### Issue: "Redirect URI mismatch"
**Solution**: Make sure the redirect URI in Tradovate OAuth app **exactly matches** what the code generates.

### Issue: "HTTPS required"
**Solution**: 
- Use ngrok for local development
- Or deploy to a server with HTTPS
- Set `PRODUCTION_URL` environment variable

### Issue: "Broken page after selecting Tradovate"
**Solution**: 
- Check server logs for errors
- Verify the redirect URI is HTTPS
- Ensure OAuth app is properly configured in Tradovate

## 🔍 How to Check Your Current Redirect URI

The code will log the redirect URI being used. Check your server logs for:
```
Using ngrok redirect_uri: https://...
```
or
```
Using request-based redirect_uri: https://...
```

Make sure this **exactly matches** what's registered in your Tradovate OAuth app.

## 📞 Need Help?

If you're still having issues:
1. Check server logs for the exact redirect URI being used
2. Verify it matches what's in Tradovate OAuth app settings
3. Ensure the redirect URI uses HTTPS (not HTTP)
4. Make sure the OAuth app has "Orders: Full Access" enabled

