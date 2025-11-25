# Trade Manager Authentication Flow - Solution

## How Trade Manager Works

Based on the fact that Trade Manager CAN sync sim accounts, here's how they likely do it:

### Step 1: Initial Authentication (Web Interface)
1. User logs into Trade Manager's website
2. User clicks "Connect Tradovate Account"
3. User enters Tradovate credentials
4. User solves CAPTCHA (if required)
5. Trade Manager gets access token + refresh token
6. **Tokens are stored in Trade Manager's database**

### Step 2: Backend Uses Stored Tokens
1. Backend services use the **stored tokens** (not credentials)
2. No CAPTCHA needed because token is already authenticated
3. Tokens are valid for 24 hours
4. Refresh tokens when they expire

## Solution for Your Recorder Backend

### Option 1: Web-Based Authentication Flow (Recommended)

**Frontend (Your Website):**
1. User goes to "Connect Account" page
2. User enters Tradovate credentials
3. JavaScript makes API call to your backend
4. Backend authenticates (user solves CAPTCHA if needed)
5. Backend stores access token + refresh token in database
6. User's account is now connected

**Backend (Recorder Service):**
1. Uses **stored tokens** from database (not credentials)
2. No CAPTCHA needed - token is already authenticated
3. Refreshes token when it expires
4. Polls positions using stored token

### Option 2: Manual Token Generation

For testing, you can:
1. Manually authenticate through a browser/Postman
2. Get the access token
3. Store it in the database
4. Recorder backend uses stored token

## Implementation

The recorder backend should:
1. Check if account has a valid token
2. If yes, use token (no CAPTCHA)
3. If no/expired, require user to re-authenticate through web interface
4. Store tokens in `accounts` table (`tradovate_token`, `tradovate_refresh_token`)

