# Full Thread Analysis: "Api websocket and marketdata websocket"

## Source
- **Thread**: community.tradovate.com/t/api-websocket-and-marketdata-websocket/4037
- **Original Problem**: "Access denied" when placing orders via WebSocket
- **Solution Found**: Need to use correct account information

---

## Key Information from Full Thread

### 1. Original Problem (beebee, Feb 2022)
**Issue**: Getting "Access denied" when trying to place orders via WebSocket

**Error:**
```json
{
  "failureReason": "UnknownReason",
  "failureText": "Access is denied"
}
```

---

### 2. Solution (beebee, Feb 2022)
**The Fix:**
> "You need to call the account list endpoint, get the demo account userspec and userid, use that with when routing the orders and everything should work as expected."

**What This Means:**
- ✅ Must call `/account/list` endpoint
- ✅ Get `accountSpec` and `userId` from account list
- ✅ Use these when routing orders

---

### 3. Clarification on accountSpec (beebee, Apr 2022)
**Question**: Which attribute from account list endpoint passes to `accountSpec` in placeorder endpoint?

**Answer (beebee):**
> "when u get the access token response:
> - accountSpec is `name` from access token response
> - accountId is `userId` from access token response"

**⚠️ This was later corrected!**

---

### 4. Official Clarification (Alexander - Tradovate Employee, Apr 2022)
**CRITICAL CORRECTION:**

> "accountSpec is the `name` field from the accessTokenRequest response, correct. 
> 
> But the accountId you need to get from the `/account/list` operation. Then you can choose one of your accounts. 
> 
> Typical users have a single account but it isn't unheard of to have multiples. 
> 
> The `userId` field is used for things like starting a subscription to real-time data for your user."

**This is the KEY information!**

---

## What This Means

### Account Information Breakdown

**From `accessTokenRequest` Response:**
```json
{
  "accessToken": "...",
  "mdAccessToken": "...",
  "name": "account_spec_value",  // ← This is accountSpec
  "userId": 123456,              // ← This is for subscriptions, NOT accountId
  ...
}
```

**From `/account/list` Response:**
```json
[
  {
    "id": 789012,                // ← This is accountId (for orders)
    "name": "account_spec_value",
    "userId": 123456,
    ...
  }
]
```

**Summary:**
- `accountSpec` = `name` from `accessTokenRequest` response ✅
- `accountId` = `id` from `/account/list` response ✅ (NOT `userId` from auth!)
- `userId` = `userId` from `accessTokenRequest` response (for subscriptions) ✅

---

## Implications for Our Implementation

### 1. For Order Placement
**We Need:**
- `accountSpec` = `name` from auth response
- `accountId` = `id` from `/account/list` response

**Current Status**: ⚠️ We might be using wrong `accountId`!

---

### 2. For WebSocket Subscriptions
**We Need:**
- `userId` = `userId` from auth response (for user data subscriptions)

**Current Status**: ✅ We should be using this correctly

---

### 3. For Position Tracking
**We Need:**
- Get account list to find correct `accountId`
- Use `accountId` to filter positions
- Use `userId` for subscriptions

**Current Status**: ⚠️ Need to verify we're using correct IDs

---

## Critical Discovery

### The "Access Denied" Problem
**Root Cause**: Using wrong `accountId` or missing account information

**Solution**: 
1. Call `/account/list` after authentication
2. Get the `id` field (this is `accountId`)
3. Use this `accountId` for orders and position queries

---

## What We Need to Update

### 1. Authentication Flow
**After getting access token:**
```python
# Get account list
accounts = await session.get(f"{base_url}/account/list", headers=headers)
account_data = await accounts.json()

# Get the account ID (not userId from auth!)
if account_data and len(account_data) > 0:
    account_id = account_data[0].get("id")  # ← This is accountId
    account_spec = data.get("name")  # ← This is accountSpec from auth
    user_id = data.get("userId")  # ← This is userId for subscriptions
```

### 2. WebSocket Subscriptions
**For user data subscriptions:**
- Use `userId` from auth response (for subscriptions)
- Use `accountId` from account list (for filtering positions)

### 3. Position Queries
**When getting positions:**
- Filter by `accountId` from account list
- Not by `userId` from auth

---

## Updated Implementation Steps

### Step 1: Authenticate
```python
response = await session.post(f"{base_url}/auth/accesstokenrequest", json=login_data)
auth_data = await response.json()

access_token = auth_data.get("accessToken")
md_access_token = auth_data.get("mdAccessToken")
account_spec = auth_data.get("name")  # ← accountSpec
user_id = auth_data.get("userId")     # ← userId (for subscriptions)
```

### Step 2: Get Account List
```python
headers = {"Authorization": f"Bearer {access_token}"}
response = await session.get(f"{base_url}/account/list", headers=headers)
accounts = await response.json()

if accounts and len(accounts) > 0:
    account_id = accounts[0].get("id")  # ← accountId (for orders/positions)
```

### Step 3: Use Correct IDs
```python
# For orders:
order_data = {
    "accountSpec": account_spec,  # From auth response
    "accountId": account_id,       # From account list
    ...
}

# For subscriptions:
# Use user_id from auth response

# For position queries:
# Filter by account_id from account list
```

---

## Questions Answered

### Q: Why "Access denied"?
**A**: Using wrong `accountId` or missing account information

### Q: What is accountSpec?
**A**: `name` field from `accessTokenRequest` response

### Q: What is accountId?
**A**: `id` field from `/account/list` response (NOT `userId` from auth!)

### Q: What is userId?
**A**: `userId` field from `accessTokenRequest` response (used for subscriptions)

---

## Action Items

1. ✅ Update authentication to capture `name` (accountSpec) and `userId`
2. ✅ Add call to `/account/list` after authentication
3. ✅ Store `accountId` from account list (not `userId` from auth)
4. ✅ Use correct IDs for:
   - Orders: `accountSpec` + `accountId`
   - Subscriptions: `userId`
   - Position queries: `accountId`

---

## Status

**Before**: ⚠️ May have been using wrong account information

**After**: ✅ Now know the correct way to get and use account information

**Next**: Update test project to use correct account information

