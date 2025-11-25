# TradersPost OAuth Security Pattern

## Key Security Features

### 1. State Parameter (CSRF Protection)

**TradersPost uses:**
- UUID for state parameter (not account ID)
- Example: `b29d8b75aa7071f841f86e0fcaeed325f73fea50`
- Stored in session during OAuth initiation
- Verified on callback to prevent CSRF attacks

**Your Implementation:**
- ✅ Generates UUID for state
- ✅ Stores in session
- ✅ Verifies on callback

### 2. Redirect URI Path

**TradersPost uses:**
- Full path: `https://traderspost.io/app/trading/connect/tradovate/redirect`
- Specific callback endpoint

**Your Implementation:**
- Full path: `https://your-ngrok-url.ngrok-free.dev/auth/tradovate/callback`
- Or: `https://yourdomain.com/auth/tradovate/callback`

### 3. OAuth Flow

1. **Initiation:**
   - Generate UUID for state
   - Store state + account_id in session
   - Redirect to Tradovate OAuth

2. **Callback:**
   - Verify state matches session
   - Get account_id from session
   - Exchange code for token
   - Store token

## OAuth URL Pattern

```
https://trader.tradovate.com/oauth?
  response_type=code&
  client_id=YOUR_CLIENT_ID&
  redirect_uri=YOUR_REDIRECT_URI&
  state=UUID_FOR_CSRF_PROTECTION&
  scope=All
```

## Security Benefits

1. **CSRF Protection:**
   - State parameter prevents cross-site request forgery
   - Only your app can complete the OAuth flow

2. **Session Security:**
   - State stored in server-side session
   - Cannot be tampered with by client

3. **Account Verification:**
   - Account ID stored in session
   - Verified on callback

## Implementation Details

### State Generation
```python
import uuid
oauth_state = str(uuid.uuid4()).replace('-', '')
```

### State Storage
```python
session['tradovate_oauth_state'] = oauth_state
session['tradovate_account_id'] = account_id
```

### State Verification
```python
expected_state = session.get('tradovate_oauth_state')
if state != expected_state:
    return error("Invalid state - CSRF attack")
```

## OAuth App Response

TradersPost receives OAuth app configuration:
```json
{
    "name": "TradersPost Production Env",
    "logo": "data:image/jpeg;base64,...",
    "privacyPolicyLink": "https://traderspost.io/privacy/",
    "termsAndConditionsLink": "https://traderspost.io/terms/",
    "internal": false,
    "acl": "{\"entries\":{\"Orders\":\"FullAccess\",\"Positions\":\"Read\",...}}"
}
```

## Next Steps

1. **Register OAuth app** with:
   - Redirect URI: `https://your-ngrok-url.ngrok-free.dev/auth/tradovate/callback`
   - Privacy policy and terms links
   - Permissions (Orders: FullAccess, Positions: Read, etc.)

2. **Test OAuth flow:**
   - Visit: `http://localhost:8082/api/accounts/4/connect`
   - Should redirect with UUID state
   - Should verify state on callback
   - Should store token

## Security Checklist

- ✅ State parameter: UUID (not account ID)
- ✅ State stored in session
- ✅ State verified on callback
- ✅ Account ID stored in session
- ✅ Redirect URI includes callback path
- ✅ CSRF protection implemented

