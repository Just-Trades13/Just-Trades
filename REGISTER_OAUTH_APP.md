# Register OAuth App for TradersPost-Style Flow

## Based on TradersPost's OAuth App Configuration

### OAuth App Details

**App Name:** TradersPost Production Env

**Permissions (ACL):**
- Orders: FullAccess
- Positions: Read
- Prices: Read
- Chat: Read
- Users: Read
- Fees: Read
- Accounting: Read
- ContractLibrary: Read
- Alerts: Read
- Risks: Read
- Reports: Denied (default)
- Default: Denied

**Additional Information:**
- Privacy Policy: https://traderspost.io/privacy/
- Terms and Conditions: https://traderspost.io/terms/
- Logo: base64 encoded image (optional)
- Internal: false

## Step-by-Step Registration

### Step 1: Prepare Your Information

1. **App Name:** Just.Trade (or your app name)
2. **Privacy Policy URL:** 
   - Development: `https://your-ngrok-url.ngrok-free.dev/privacy`
   - Production: `https://yourdomain.com/privacy`
3. **Terms and Conditions URL:**
   - Development: `https://your-ngrok-url.ngrok-free.dev/terms`
   - Production: `https://yourdomain.com/terms`
4. **Logo:** (Optional) Upload your app logo
5. **Redirect URI:**
   - Development: `https://clay-ungilled-heedlessly.ngrok-free.dev`
   - Production: `https://yourdomain.com/auth/tradovate/callback`

### Step 2: Register OAuth App in Tradovate

1. **Log into Tradovate**
   - Go to: https://tradovate.com
   - Log in with your account

2. **Navigate to Application Settings**
   - Click on "Application Settings" in account menu
   - Go to "API Access" tab
   - Click on "OAuth Registration"

3. **Fill Out OAuth Registration Form**

   **Required Fields:**
   - **App Title:** Just.Trade (or your app name)
   - **Redirect URI:** `https://clay-ungilled-heedlessly.ngrok-free.dev` (your ngrok URL)

   **Optional Fields:**
   - **Privacy Policy Link:** `https://your-ngrok-url.ngrok-free.dev/privacy`
   - **Terms and Conditions Link:** `https://your-ngrok-url.ngrok-free.dev/terms`
   - **Logo:** Upload your app logo (optional)

   **Permissions:**
   - Select permissions you need:
     - **Orders:** Full Access (for trading)
     - **Positions:** Read (for viewing positions)
     - **Prices:** Read (for market data)
     - **Chat:** Read (optional)
     - **Users:** Read (optional)
     - **Fees:** Read (optional)
     - **Accounting:** Read (optional)
     - **ContractLibrary:** Read (optional)
     - **Alerts:** Read (optional)
     - **Risks:** Read (optional)

4. **Click "Generate" or "Create"**
   - You'll get a Client ID and Client Secret
   - **Save these immediately!** (shown only once)

### Step 3: Update Account in Database

After getting the new Client ID and Secret:

1. **Update account in database:**
   ```python
   # Update account with new OAuth app credentials
   # Client ID: (new one from OAuth app)
   # Client Secret: (new one from OAuth app)
   ```

2. **Or update via web interface:**
   - Go to: `http://localhost:8082/accounts`
   - Click "Edit" on your account
   - Enter new Client ID and Secret
   - Save

### Step 4: Test OAuth Flow

1. **Visit:** `http://localhost:8082/api/accounts/4/connect`
2. **Should redirect to:** `https://trader.tradovate.com/oauth?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&scope=All`
3. **Should show OAuth authorization page:**
   - "Sign In with Tradovate"
   - "to continue to Just.Trade" (your app name)
   - Permissions list
   - Privacy policy and terms links
4. **Log in and authorize**
5. **Redirects back:** With authorization code
6. **Token stored:** Automatically

## Important Notes

### Redirect URI

- **Must match exactly** what's registered in OAuth app
- **No trailing slash**
- **Must be public URL** (not localhost)
- **Use ngrok for development** or production domain

### Scope

- **OAuth URL uses:** `scope=All`
- **Actual permissions:** Defined in OAuth app registration
- **Scope "All"** grants all permissions you selected

### Permissions

- **Orders: FullAccess** - Required for trading
- **Positions: Read** - Required for viewing positions
- **Prices: Read** - Required for market data
- **Other permissions:** Optional, based on your needs

### Privacy Policy and Terms

- **Required for OAuth app** (best practice)
- **Should be publicly accessible**
- **Must match URLs** registered in OAuth app

## OAuth Flow

1. **User clicks "Connect Account"**
2. **Redirects to:** `https://trader.tradovate.com/oauth?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&scope=All`
3. **User logs in and authorizes**
4. **Tradovate redirects back:** `YOUR_REDIRECT_URI?code=AUTHORIZATION_CODE&state=ACCOUNT_ID`
5. **Exchange code for token:**
   - POST to: `https://live.tradovateapi.com/v1/auth/accesstokenrequest`
   - Or: `https://demo.tradovateapi.com/v1/auth/accesstokenrequest`
6. **Store token** in database
7. **Use token** for API calls

## Next Steps

1. **Create privacy policy page** (if you don't have one)
2. **Create terms page** (if you don't have one)
3. **Register OAuth app** in Tradovate with all required fields
4. **Get Client ID and Secret**
5. **Update account** in database
6. **Test OAuth flow**

## Testing

After registering OAuth app:

```bash
# Test redirect
curl -I http://localhost:8082/api/accounts/4/connect

# Should redirect to:
# https://trader.tradovate.com/oauth?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&scope=All
```

## Troubleshooting

### OAuth app not showing authorization page

- **Check redirect URI** - must match exactly
- **Check Client ID** - must be correct
- **Check OAuth app status** - must be active/approved

### Redirect URI mismatch

- **Error:** "redirect_uri_mismatch"
- **Solution:** Update redirect URI in OAuth app to match exactly

### Invalid client

- **Error:** "invalid_client"
- **Solution:** Check Client ID and Secret are correct

### Invalid scope

- **Error:** "invalid_scope"
- **Solution:** Use `scope=All` or check permissions in OAuth app

