# Quick Test Guide - Recorder Backend

## ✅ Setup Complete!

Your test data has been created:
- **User ID**: 4
- **Account ID**: 4 (WhitneyHughes86 demo account)
- **Strategy ID**: 10 (Test Recorder for NQ)
- **API Key**: test-key-12345

## 🚀 Testing Steps

### Step 1: Start the Recorder Backend

In one terminal:
```bash
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3 recorder_backend.py --port 8083
```

You should see:
```
============================================================
Recorder Backend Service - Production Ready
============================================================
Host: 127.0.0.1
Port: 8083
...
```

### Step 2: Test Health Check

In another terminal:
```bash
curl http://localhost:8083/health | python3 -m json.tool
```

Expected response:
```json
{
  "status": "healthy",
  "active_recordings": 0,
  "active_users": 0,
  ...
}
```

### Step 3: Start Recording

```bash
curl -X POST http://localhost:8083/api/recorders/start/10 \
  -H "X-API-Key: test-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 4, "poll_interval": 30}' | python3 -m json.tool
```

Expected response:
```json
{
  "success": true,
  "message": "Recording started for strategy 10",
  "strategy_id": 10,
  "user_id": 4,
  "poll_interval": 30
}
```

### Step 4: Check Status

```bash
curl -H "X-API-Key: test-key-12345" \
     -H "X-User-ID: 4" \
     http://localhost:8083/api/recorders/status | python3 -m json.tool
```

### Step 5: Check Recorded Positions

```bash
curl -H "X-API-Key: test-key-12345" \
     -H "X-User-ID: 4" \
     http://localhost:8083/api/recorders/positions/10 | python3 -m json.tool
```

### Step 6: Stop Recording

```bash
curl -X POST http://localhost:8083/api/recorders/stop/10 \
  -H "X-API-Key: test-key-12345" \
  -H "X-User-ID: 4" | python3 -m json.tool
```

## 📊 What to Expect

1. **Recording starts**: The backend will begin polling Tradovate every 30 seconds
2. **Positions detected**: If you have open positions in your demo account, they'll be recorded
3. **Logs**: Check `recorder_backend.log` for detailed logs
4. **Database**: Positions will be saved to `just_trades.db` in the `recorded_positions` table

## 🔍 Monitoring

### View Logs
```bash
tail -f recorder_backend.log
```

### Check Database
```bash
sqlite3 just_trades.db "SELECT * FROM recorded_positions ORDER BY entry_timestamp DESC LIMIT 5;"
```

### Check Strategy Logs
```bash
sqlite3 just_trades.db "SELECT * FROM strategy_logs WHERE strategy_id = 10 ORDER BY created_at DESC LIMIT 10;"
```

## ⚠️ Troubleshooting

### "Unauthorized" error
- Make sure API key is set: `export RECORDER_API_KEY=test-key-12345`
- Or check `.env` file has `RECORDER_API_KEY=test-key-12345`

### "Strategy not found" error
- Verify strategy ID: `sqlite3 just_trades.db "SELECT id, name FROM strategies WHERE id = 10;"`
- Check user_id matches: `sqlite3 just_trades.db "SELECT user_id FROM strategies WHERE id = 10;"`

### No positions recorded
- Check if you have open positions in your Tradovate demo account
- Verify account credentials are correct
- Check logs for Tradovate connection errors

### Tradovate connection errors
- Verify OAuth credentials (Client ID: 8552, Client Secret: d7d4fc4c-43f1-4f5d-a132-dd3e95213239)
- Check username/password are correct
- Ensure OAuth app has "Positions" and "Account Information" permissions

