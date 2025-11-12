# Account Management Page - Complete Extraction

**Page URL:** `/user/at/accnts`

## 📋 UI Components Found

### Header Section
- **Account Count:** "Account 10 Used / Unlimited"
- **Add Account Button:** "+ Add Account"

### Search & Actions
- **Search Field:** "Search accounts..."
- **Delete Button:** Bulk delete action
- **Clear Trade Button:** Clear trade data

### Account Cards
Each account has:
- **Edit Account Credentials** button
- **Refresh SubAccount** button (re-authenticates)
- Account name (e.g., "whitney")
- Subaccounts list with tags (e.g., "TAKEPROFIT647802407")

## 🔍 API Endpoints Called

From network requests:
- `GET /api/accounts/get-all-at-accounts/` - Get all accounts
- `GET /api/profiles/get-limits/` - Get account limits
- `GET /api/auth/check-auth/` - Check authentication
- `GET /api/system/csrf-token/` - Get CSRF token

## 🎯 Expected Endpoints (Need to Capture)

When clicking "+ Add Account":
- **POST** `/api/accounts/add-tradovate/` (or similar)
  - Need: Request body format
  - Need: Response format

When clicking "Edit Account Credentials":
- **GET** `/api/accounts/{id}/` (or similar)
- **PUT** `/api/accounts/{id}/` (or similar)
  - Need: Request body format

When clicking "Refresh SubAccount":
- **POST** `/api/accounts/{id}/refresh/` (or similar)
  - Need: Request body format

When clicking "Delete":
- **DELETE** `/api/accounts/{id}/` (or similar)
  - Need: Request format

