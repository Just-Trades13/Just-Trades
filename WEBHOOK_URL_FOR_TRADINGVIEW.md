# 🔗 Webhook URL for TradingView

## Your Webhook URL

**Use the main server's webhook endpoint (port 80/443 compatible):**

```
https://YOUR-PUBLIC-URL/webhook/LmTtsTM872MX-H84aAbxFLeuKLgiXpqGCOllyWhe8Vk
```

**Replace `YOUR-PUBLIC-URL` with:**
- Your Railway domain (if deployed on Railway)
- Your ngrok URL (if using ngrok)
- Your custom domain (if you have one)

---

## 🚀 Quick Setup Options

### Option 1: Use ngrok (Fastest - 2 minutes)

1. **Start ngrok:**
   ```bash
   ngrok http 8082
   ```

2. **Copy the HTTPS URL** (looks like `https://abc123.ngrok-free.app`)

3. **Your webhook URL:**
   ```
   https://abc123.ngrok-free.app/webhook/LmTtsTM872MX-H84aAbxFLeuKLgiXpqGCOllyWhe8Vk
   ```

**Note:** Free ngrok URLs change each restart. For permanent URL, sign up for ngrok account.

---

### Option 2: Use Railway (Permanent)

If you're deployed on Railway:

1. **Get your Railway domain** from Railway dashboard
2. **Your webhook URL:**
   ```
   https://your-app.railway.app/webhook/LmTtsTM872MX-H84aAbxFLeuKLgiXpqGCOllyWhe8Vk
   ```

---

## 📋 Recorder Details

- **Name:** `LIVE_TEST_RECORDER`
- **TP Ticks:** `10` ✅
- **TP Enabled:** `Yes` ✅
- **Webhook Token:** `LmTtsTM872MX-H84aAbxFLeuKLgiXpqGCOllyWhe8Vk`

---

## 📨 TradingView Alert Message

**Use this JSON in your TradingView alert:**

```json
{
  "recorder": "LIVE_TEST_RECORDER",
  "action": "{{strategy.order.action}}",
  "ticker": "{{ticker}}",
  "price": "{{close}}"
}
```

**Or simple format:**

```json
{
  "recorder": "LIVE_TEST_RECORDER",
  "action": "buy",
  "ticker": "MNQ1!",
  "price": "{{close}}"
}
```

---

## ⚠️ IMPORTANT: Start Server in Test Mode

**Before sending signals, start the server with:**

```bash
SIGNAL_BASED_TEST=true python3 ultra_simple_server.py
```

**Or if using Railway, set environment variable:**
```
SIGNAL_BASED_TEST=true
```

This enables signal-based tracking (no broker sync) so we can test accuracy.

---

## ✅ Ready to Test!

1. **Get your public URL** (ngrok or Railway)
2. **Update webhook URL** with your public domain
3. **Start server** in test mode
4. **Add webhook to TradingView** alert
5. **Send test signal** and watch it track!

---

**The webhook will work on port 80/443 through your public URL!**
