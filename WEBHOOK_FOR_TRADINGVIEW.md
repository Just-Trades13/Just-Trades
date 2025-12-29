# 🔗 Webhook URL for TradingView

## Your Webhook URL

```
http://localhost:8083/webhook/LmTtsTM872MX-H84aAbxFLeuKLgiXpqGCOllyWhe8Vk
```

**⚠️ IMPORTANT:** If you're running on Railway or have a public URL, replace `localhost:8083` with your actual domain.

---

## 📋 Recorder Configuration

- **Name:** `LIVE_TEST_RECORDER`
- **TP Ticks:** `10` ✅
- **TP Enabled:** `Yes` ✅
- **Position Size:** `1` contract

---

## 📨 TradingView Alert Message

**Use this JSON in your TradingView alert webhook:**

```json
{
  "recorder": "LIVE_TEST_RECORDER",
  "action": "{{strategy.order.action}}",
  "ticker": "{{ticker}}",
  "price": "{{close}}"
}
```

**Or use the simple format:**

```json
{
  "recorder": "LIVE_TEST_RECORDER",
  "action": "buy",
  "ticker": "MNQ1!",
  "price": "{{close}}"
}
```

---

## 🚀 Before Sending Signals

**Start the server in test mode:**

```bash
SIGNAL_BASED_TEST=true python3 recorder_service.py
```

This enables signal-based tracking (no broker sync) so we can test accuracy.

---

## 📊 What Will Happen

1. **Signal Received:** TradingView sends webhook
2. **Position Created:** +1 contract @ entry price (signal-based)
3. **TP Order:** 10 tick take profit will be set
4. **Tracking:** Position tracked from signals (not broker API)
5. **P&L Updates:** Calculated from TradingView market data

---

## 🔍 Monitoring

Watch the server logs to see:
- Signal received
- Position created/updated
- TP order placed
- P&L updates

Check database:
```sql
SELECT * FROM recorder_positions WHERE recorder_id = 1;
SELECT * FROM recorded_signals WHERE recorder_id = 1;
```

---

## ✅ Ready to Test!

1. Start server: `SIGNAL_BASED_TEST=true python3 recorder_service.py`
2. Add webhook to TradingView alert
3. Send test signal
4. Watch it track accurately!

---

**The system will track positions from signals and automatically set 10 tick TP!**
