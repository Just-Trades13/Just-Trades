# Update OAuth Redirect URI to ngrok URL

## ngrok Public URL

**Your ngrok URL:**
```
https://clay-ungilled-heedlessly.ngrok-free.dev
```

This URL forwards to your local server at `http://localhost:8082`.

## Step 1: Update Redirect URI in Tradovate OAuth App

1. **Log into Tradovate**
   - Go to: https://tradovate.com
   - Log in with your account

2. **Go to Application Settings**
   - Look for "Application Settings" in account menu
   - Click on it

3. **Go to API Access → OAuth Registration**
   - Click on "API Access" tab
   - Click on "OAuth Registration"
   - Find your OAuth app (Client ID: 8552, App Name: "test")

4. **Edit OAuth App**
   - Click "Edit" on your OAuth app
   - Update Redirect URI to:
     ```
     https://clay-ungilled-heedlessly.ngrok-free.dev
     ```
   - **Important:** Must match exactly (no trailing slash, no path)
   - Click "Save"

## Step 2: Test OAuth Flow

1. **Visit in browser:**
   ```
   http://localhost:8082/api/accounts/4/connect
   ```

2. **You should now see:**
   - OAuth authorization page (not regular login!)
   - "Sign In with Tradovate"
   - "to continue to test" (your app name)
   - Permissions list (Read Only: Positions, etc. | Full: Orders)
   - Login form

3. **Log in and authorize:**
   - Enter credentials
   - Click "Login"
   - Click "Authorize" or "Allow"
   - You'll be redirected back to ngrok URL
   - Token will be stored automatically

## Why This Works

- ✅ **Public URL** - Tradovate accepts it (unlike localhost)
- ✅ **OAuth authorization page** - Shows app name and permissions
- ✅ **Callback works** - ngrok forwards to your local server
- ✅ **Same as TradersPost** - They use production URLs

## Important Notes

1. **ngrok URL changes** - If you restart ngrok, you'll get a new URL
2. **Update redirect URI** - Need to update it in OAuth app each time
3. **For production** - Use your production domain instead of ngrok

## Next Steps

1. **Update redirect URI** in Tradovate OAuth app to ngrok URL
2. **Test OAuth flow** - should see authorization page now!
3. **Complete authorization** - token will be stored
4. **Verify token** - check if it works

## Current ngrok URL

```
https://clay-ungilled-heedlessly.ngrok-free.dev
```

This URL is saved in `ngrok_url.txt` and will be used automatically!

