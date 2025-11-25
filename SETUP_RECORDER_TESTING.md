# Setting Up Recorder Backend for Testing

This guide will help you set up the recorder backend to test with a Tradovate demo account.

## Step 1: Tradovate OAuth Registration

Based on the Tradovate OAuth registration form you're viewing:

### Required Permissions for Recorder Backend:
1. **Positions** - Set to "Allowed" ✅ (CRITICAL - needed to read positions)
2. **Account Information** - Set to "Allowed" ✅ (CRITICAL - needed to identify accounts)
3. **Contract Library** - Set to "Allowed" (helpful for symbol info)
4. **Orders** - Can be "Denied" (we're only reading, not placing orders)

### OAuth Registration Details:
- **App Title**: `Just.Trades Recorder Backend` (or your preferred name)
- **Redirect URI**: `http://localhost:8083/oauth/callback` (for local testing)
  - For production: `https://your-domain.com/oauth/callback`
- **Privacy Policy Link**: (optional for testing)
- **Terms & Conditions Link**: (optional for testing)
- **Upload Logo**: (optional)

### Important Checkbox:
- ✅ **"Allow sending orders with no Market Data subscriptions"** - Can be checked or unchecked (we're not sending orders)

After clicking "Generate", you'll receive:
- **Client ID** (cid)
- **Client Secret** (sec)

**SAVE THESE** - you'll need them for the database setup!

## Step 2: Database Setup

We'll create test data in your database.

## Step 3: Test Script

We'll create a script to test the recorder backend.

