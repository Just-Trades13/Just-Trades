# Testing Guide: TradersPost-Style Connection

## Quick Test Steps

### Step 1: Start the Server

Open a terminal and run:

```bash
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3 ultra_simple_server.py
```

You should see:
```
Starting Just.Trades. server on 0.0.0.0:8082
```

**Keep this terminal open** - the server needs to keep running.

### Step 2: Test the Connection

Open a **new terminal window** and run:

```bash
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3 test_traderspost_connection.py 4
```

Or use curl:

```bash
curl http://localhost:8082/api/accounts/4/connect
```

### Step 3: Check Results

**If successful:**
```json
{
  "success": true,
  "message": "Account connected successfully (TradersPost-style)",
  "account_id": 4,
  "account_name": "Test Demo Account",
  "expires_at": "2024-01-02T12:00:00"
}
```

**If CAPTCHA required:**
```json
{
  "success": false,
  "error": "CAPTCHA_REQUIRED",
  "message": "CAPTCHA verification required...",
  "requires_setup": true
}
```

## Alternative: Test from Browser

1. Start server (Step 1 above)
2. Open browser: `http://localhost:8082/api/accounts/4/connect`
3. You'll see JSON response

## Alternative: Test with curl

```bash
# Test connection
curl http://localhost:8082/api/accounts/4/connect

# Pretty print JSON
curl http://localhost:8082/api/accounts/4/connect | python3 -m json.tool
```

## What to Expect

### ✅ Success Response
- Token is stored in database
- Account is connected
- Recorder backend can use stored token
- No CAPTCHA needed for future calls

### ❌ Error Responses

**CAPTCHA_REQUIRED:**
- Solution: Log into Tradovate website first, then try again

**Account not found:**
- Solution: Check account ID in database

**Connection error:**
- Solution: Make sure server is running

## After Successful Connection

1. **Test token usage:**
   ```bash
   curl -X POST http://localhost:8082/api/accounts/4/test-connection
   ```

2. **Test recorder backend:**
   ```bash
   python3 test_recorder_backend.sh
   ```

3. **Verify account balance:**
   - Check if token works for API calls

## Troubleshooting

### Server not running?
```bash
# Check if port 8082 is in use
lsof -i :8082

# Start server
python3 ultra_simple_server.py
```

### Connection refused?
- Make sure server is running on port 8082
- Check firewall settings
- Try `http://127.0.0.1:8082` instead of `localhost`

### CAPTCHA error?
1. Log into Tradovate website: https://demo.tradovate.com
2. Complete any security checks
3. Try connecting again

### Account not found?
```bash
# Check database
sqlite3 just_trades.db "SELECT id, name, username FROM accounts WHERE id = 4;"
```

## Full Test Flow

```bash
# Terminal 1: Start server
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3 ultra_simple_server.py

# Terminal 2: Test connection
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3 test_traderspost_connection.py 4

# Terminal 2: Test token usage
curl -X POST http://localhost:8082/api/accounts/4/test-connection
```

