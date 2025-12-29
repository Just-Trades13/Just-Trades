# 🚀 Start Server and Monitor Signals

## Current Status

- ✅ Recorder created: `LIVE_TEST_RECORDER`
- ✅ TP Ticks: 10
- ✅ Webhook token ready
- ⚠️  Server not running (tables not initialized)
- ⚠️  No signals received yet

---

## Step 1: Start the Server

**Start the main server in test mode:**

```bash
cd "/Users/mylesjadwin/Trading Projects"
SIGNAL_BASED_TEST=true python3 ultra_simple_server.py
```

**Or run in background:**
```bash
SIGNAL_BASED_TEST=true nohup python3 ultra_simple_server.py > server.log 2>&1 &
```

This will:
- Initialize database tables
- Start webhook endpoint on port 8082
- Enable signal-based tracking (no broker sync)

---

## Step 2: Check if Server is Running

```bash
# Check if server is running
lsof -i :8082

# Or check process
ps aux | grep ultra_simple_server
```

---

## Step 3: Monitor Signals

**In another terminal, run:**

```bash
python3 check_webhook_signals.py
```

**Or monitor in real-time:**
```bash
python3 check_webhook_signals.py --monitor
```

This will show:
- Recent signals received
- Open positions
- Closed positions
- P&L updates

---

## Step 4: Test Webhook

**Once server is running, test the webhook:**

```bash
curl -X POST http://localhost:8082/webhook/LmTtsTM872MX-H84aAbxFLeuKLgiXpqGCOllyWhe8Vk \
  -H "Content-Type: application/json" \
  -d '{
    "recorder": "LIVE_TEST_RECORDER",
    "action": "buy",
    "ticker": "MNQ1!",
    "price": "25600"
  }'
```

**Expected response:**
```json
{
  "success": true,
  "message": "Signal processed"
}
```

---

## Step 5: Check What We're Getting

**After server is running and signals are sent:**

```bash
python3 check_webhook_signals.py
```

**Or check database directly:**
```bash
sqlite3 just_trades.db "SELECT * FROM recorded_signals ORDER BY created_at DESC LIMIT 10;"
sqlite3 just_trades.db "SELECT * FROM recorder_positions WHERE status = 'open';"
```

---

## Troubleshooting

### Server Won't Start
- Check if port 8082 is already in use
- Check for errors in server.log
- Make sure database file exists

### No Signals Received
- Check webhook URL is correct in TradingView
- Check server logs for webhook attempts
- Verify TradingView alert is triggering
- Check if using ngrok/Railway, make sure URL is accessible

### Tables Don't Exist
- Server needs to run once to create tables
- Or run: `python3 init_db.py` (if it exists)

---

## Quick Status Check

Run this to see current status:

```bash
python3 check_webhook_signals.py
```

---

**Once server is running, signals will be tracked and we can monitor accuracy!**
