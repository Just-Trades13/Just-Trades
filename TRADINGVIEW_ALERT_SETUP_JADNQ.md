# TradingView Alert Setup for JADNQ Strategy

## 🔴 PROBLEM IDENTIFIED

Your TradingView strategy alerts are not firing correctly because the **alert message format** is not configured properly. The strategy file (Pine Script) is fine, but TradingView needs the correct webhook message format to send the right data to your server.

---

## ✅ CORRECT ALERT MESSAGE FORMAT

When creating an alert from your strategy in TradingView, you **MUST** use this exact message format in the alert configuration:

### **Copy-Paste This JSON into TradingView Alert Message:**

```json
{
  "ticker": "{{ticker}}",
  "price": {{close}},
  "action": "{{strategy.order.action}}",
  "market_position": "{{strategy.market_position}}",
  "position_size": {{strategy.position_size}},
  "prev_position_size": {{strategy.prev_market_position_size}},
  "quantity": {{strategy.order.contracts}},
  "strategy_name": "JADNQ"
}
```

---

## 📋 STEP-BY-STEP SETUP INSTRUCTIONS

### Step 1: Open Your Strategy on TradingView
1. Open your chart with the "NQ 1m HA + LSMA Trend Follow" strategy
2. Make sure the strategy is running and showing signals

### Step 2: Create Alert
1. Click the **"Alerts"** button (bell icon) in the top toolbar
2. Click **"Create Alert"**

### Step 3: Configure Alert Condition
1. **Condition:** Select your strategy name: `"NQ 1m HA + LSMA Trend Follow (LSMA Trail) — Bot Clear"`
2. **Alert Trigger:** Select **"Any order fills"** or **"Order filled"** (this fires on entry/exit)
   - OR select specific conditions like "Long" or "Short" if you want separate alerts

### Step 4: Configure Webhook Message (CRITICAL)
1. **Enable:** Check **"Webhook URL"**
2. **Webhook URL:** Enter your ngrok URL:
   ```
   https://clay-ungilled-heedlessly.ngrok-free.dev/webhook/YOUR_RECORDER_WEBHOOK_TOKEN
   ```
   *(Replace `YOUR_RECORDER_WEBHOOK_TOKEN` with your actual recorder token)*

3. **Message:** Copy and paste this EXACT JSON:
   ```json
   {
     "ticker": "{{ticker}}",
     "price": {{close}},
     "action": "{{strategy.order.action}}",
     "market_position": "{{strategy.market_position}}",
     "position_size": {{strategy.position_size}},
     "prev_position_size": {{strategy.prev_market_position_size}},
     "quantity": {{strategy.order.contracts}},
     "strategy_name": "JADNQ"
   }
   ```
   
   **⚠️ IMPORTANT NOTES:**
   - Do NOT put quotes around numbers (like `{{close}}` not `"{{close}}"`)
   - Do NOT modify the placeholders (keep `{{}}` exactly as shown)
   - The `{{ticker}}` will automatically be "CME_MINI:MNQ1!" or similar
   - The server expects `market_position` to be "long", "short", or "flat"

### Step 5: Save and Test
1. Click **"Create"** to save the alert
2. Wait for a signal to fire (or manually trigger by changing conditions temporarily)
3. Check your server logs at `/tmp/just_trades_server.log` to see if the webhook was received

---

## 🔍 WHAT EACH FIELD DOES

| Field | TradingView Placeholder | What It Does |
|-------|------------------------|--------------|
| `ticker` | `{{ticker}}` | Symbol (e.g., "CME_MINI:MNQ1!") |
| `price` | `{{close}}` | Current close price |
| `action` | `{{strategy.order.action}}` | "buy" or "sell" from strategy |
| `market_position` | `{{strategy.market_position}}` | **"long"**, **"short"**, or **"flat"** |
| `position_size` | `{{strategy.position_size}}` | Current position size (e.g., 1, 2, -1) |
| `prev_position_size` | `{{strategy.prev_market_position_size}}` | Previous position size (for detecting closes) |
| `quantity` | `{{strategy.order.contracts}}` | Number of contracts in the order |

---

## 🚨 COMMON MISTAKES

### ❌ WRONG - Plain Text Alert:
```
JADNQ: OPEN_LONG, Price = 25850
```
This won't work because it's just text, not JSON!

### ❌ WRONG - Missing Required Fields:
```json
{
  "action": "buy",
  "price": 25850
}
```
Missing `market_position` and `position_size` - server can't determine action!

### ✅ CORRECT - Full JSON with Placeholders:
```json
{
  "ticker": "{{ticker}}",
  "price": {{close}},
  "action": "{{strategy.order.action}}",
  "market_position": "{{strategy.market_position}}",
  "position_size": {{strategy.position_size}},
  "prev_position_size": {{strategy.prev_market_position_size}},
  "quantity": {{strategy.order.contracts}},
  "strategy_name": "JADNQ"
}
```

---

## 🧪 HOW TO TEST

1. **Check if webhook is receiving:**
   ```bash
   tail -f /tmp/just_trades_server.log | grep -i "webhook\|JADNQ\|JADNQ"
   ```

2. **Check ngrok requests:**
   ```bash
   curl http://localhost:4040/api/requests/http | python3 -m json.tool | head -100
   ```

3. **Check database for signals:**
   ```bash
   sqlite3 just_trades.db "SELECT * FROM recorded_signals ORDER BY created_at DESC LIMIT 5;"
   ```

---

## 🔧 TROUBLESHOOTING

### Problem: "No action determined from message"
- **Cause:** Missing `market_position` or `position_size` in alert message
- **Fix:** Use the full JSON format above

### Problem: Webhook received but trade not executing
- **Cause:** Check server logs for filter blocks (time filters, cooldowns, etc.)
- **Fix:** Check `/tmp/just_trades_server.log` for filter messages

### Problem: Wrong ticker being used
- **Cause:** `{{ticker}}` might be "CME_MINI:MNQ1!" but server expects "MNQ" or "NQ"
- **Fix:** Add ticker mapping in recorder settings or use `{{exchange}}:{{ticker}}` format

### Problem: "market_position" shows wrong value
- **Cause:** Strategy might not be in position when alert fires
- **Fix:** Use "Order filled" alert trigger instead of "Signal fired"

---

## 📝 RECOMMENDED: Separate Alerts for Entry/Exit

You can create **two separate alerts** for better control:

### Alert 1: Entry Signals (Long/Short)
- **Condition:** Strategy → "Long" OR "Short"
- **Message:** Use the JSON above
- This fires when strategy opens a position

### Alert 2: Exit Signals (Close/Flat)
- **Condition:** Strategy → "Exit Long" OR "Exit Short" OR when `market_position` changes to "flat"
- **Message:** Same JSON format
- This fires when strategy closes a position

---

## ✅ VERIFICATION CHECKLIST

Before relying on automated trading, verify:

- [ ] Alert is created with webhook URL enabled
- [ ] Alert message contains full JSON with all placeholders
- [ ] Webhook URL includes your recorder token: `/webhook/YOUR_TOKEN`
- [ ] Test alert fires and appears in server logs
- [ ] Server logs show "📨 Webhook received" with correct data
- [ ] `market_position` shows "long", "short", or "flat" correctly
- [ ] Database `recorded_signals` table gets populated
- [ ] Broker orders are being placed (check Tradovate platform)

---

## 🎯 FINAL NOTES

- The **strategy comments** in Pine Script (like `OPEN_LONG`, `EXIT_TRAIL_LONG`) are **NOT** sent in webhooks - they're just for display
- TradingView **replaces** the placeholders like `{{strategy.market_position}}` with actual values when alert fires
- The server code in `ultra_simple_server.py` at line ~9300 looks for `market_position` and `position_size` to determine the action
- If `market_position = "flat"`, the server will CLOSE positions
- If `market_position = "long"`, the server will BUY
- If `market_position = "short"`, the server will SELL

---

**Last Updated:** January 9, 2026
**Strategy:** JADNQ (NQ 1m HA + LSMA Trend Follow)
