# SMC AutoTrader Setup Guide

## 🎯 What This Does

The SMC AutoTrader strategy generates **JSON webhook alerts** that can be sent to:
- **TradersPost** (recommended for Tradovate)
- **3Commas**
- **Custom webhook receivers**

When conditions align, it automatically sends entry signals with:
- Entry price
- Stop loss level
- Take profit levels (TP1, TP2, TP3)
- Position direction
- Confluence score

---

## 📋 Alert Message Formats

### TradersPost Format (Recommended)
```json
{
  "ticker": "NQ",
  "action": "buy",
  "sentiment": "bullish", 
  "price": 21500.00,
  "stopLoss": 21480.00,
  "takeProfit": 21560.00
}
```

### Custom Format (Most Flexible)
```json
{
  "signal": "LONG",
  "symbol": "NQ",
  "entry": 21500.00,
  "sl": 21480.00,
  "tp1": 21530.00,
  "tp2": 21590.00,
  "tp3": 21650.00,
  "confluence": 5,
  "timestamp": "2025-12-05 09:30"
}
```

### 3Commas Format
```json
{
  "message_type": "bot",
  "bot_id": "YOUR_BOT_ID",
  "email_token": "YOUR_TOKEN",
  "delay_seconds": 0,
  "action": "start_long"
}
```

---

## 🔧 Setup Instructions

### Step 1: Add Strategy to TradingView
1. Open TradingView → Pine Editor
2. Create new strategy (not indicator)
3. Paste the code from `SMC_AutoTrader_System.pine`
4. Save and add to chart

### Step 2: Configure Settings
1. Click the gear icon on the strategy
2. Set your parameters:
   - **Ticker Symbol**: NQ, ES, MNQ, MES (must match your broker)
   - **Webhook Format**: TradersPost, 3Commas, or Custom
   - **Risk %**: How much to risk per trade
   - **Min Confluence**: How many factors must align (3-5 recommended)

### Step 3: Create TradingView Alert
1. Right-click chart → **Add Alert**
2. Condition: Select **"SMC AutoTrader NQ/ES"**
3. Select: **"Any alert() function call"**
4. ✅ Check **"Webhook URL"**
5. Paste your webhook URL (from TradersPost, etc.)
6. Alert name: "SMC AutoTrader - NQ"
7. Message: Leave **EMPTY** (the strategy sends the JSON automatically)

### Step 4: Connect to TradersPost (Example)
1. Go to [traderspost.io](https://traderspost.io)
2. Create a new strategy
3. Connect your Tradovate account
4. Get your webhook URL
5. Paste it into TradingView alert

---

## 📊 Confluence Scoring System

The strategy scores each setup out of 7 points:

| Factor | Points | Description |
|--------|--------|-------------|
| Trend | +1 | Structure is bullish/bearish (MSS/BOS) |
| Zone | +1 | Price in discount (longs) / premium (shorts) |
| SMT | +1 | NQ/ES divergence detected |
| FVG | +1 | Price at or near Fair Value Gap |
| Order Block | +1 | Price at Order Block |
| Killzone | +1 | In London, NY AM, or NY PM session |
| Silver Bullet | +1 | In 10-11 AM or 2-3 PM EST window |

**Minimum required**: Configurable (default 3)

---

## 🎯 Alert Types

### Entry Alerts
- **🟢 LONG Entry**: Bullish confluence met, opens long
- **🔴 SHORT Entry**: Bearish confluence met, opens short

### Exit Alerts
- **TP1 Hit**: Partial close (default 50%)
- **TP2 Hit**: Another partial close (default 30%)
- **TP3 Hit**: Full close (remaining 20%)
- **Stop Loss**: Emergency exit

---

## ⚙️ Recommended Settings

### For NQ (Nasdaq Futures)
```
Ticker: NQ
Compare Symbol: ES1!
ATR Stop Multiplier: 1.5
ATR TP1 Multiplier: 1.5
ATR TP2 Multiplier: 3.0
ATR TP3 Multiplier: 5.0
Min Confluence: 3
```

### For ES (S&P Futures)
```
Ticker: ES
Compare Symbol: NQ1!
ATR Stop Multiplier: 1.5
ATR TP1 Multiplier: 1.5
ATR TP2 Multiplier: 3.0
ATR TP3 Multiplier: 5.0
Min Confluence: 3
```

### For MNQ/MES (Micros)
Same settings, just change ticker to MNQ or MES

---

## 🕐 Best Times to Trade

The strategy automatically detects these sessions:

| Session | Time (EST) | Quality |
|---------|------------|---------|
| London | 2:00-5:00 AM | Good for direction |
| NY AM | 8:30-11:00 AM | **Best volatility** |
| Silver Bullet 1 | 10:00-11:00 AM | **ICT's power hour** |
| NY PM | 1:30-4:00 PM | Continuation moves |
| Silver Bullet 2 | 2:00-3:00 PM | **ICT's power hour** |

---

## 🛑 Risk Management

### Built-in Protection
- Stop loss calculated from ATR or structure
- Partial closes at TP1/TP2 lock in profit
- Trailing stop option (manual)

### Recommended Position Sizing
- Risk 1-2% per trade max
- For $50k account: ~$500-1000 risk per trade
- NQ: About 10-20 points SL
- ES: About 4-8 points SL

---

## 🔄 Webhook Flow

```
TradingView Alert Fires
        ↓
JSON Message Generated
        ↓
Sent to Webhook URL
        ↓
TradersPost Receives
        ↓
Order Sent to Tradovate
        ↓
Trade Executed
```

---

## ⚠️ Important Notes

1. **Paper trade first!** Test with sim account before going live
2. **Latency exists**: Webhook → Broker has ~1-3 second delay
3. **Check your broker**: Make sure ticker symbols match
4. **Monitor actively**: Automation isn't "set and forget"
5. **TradingView Premium**: Need Pro+ for webhook alerts on multiple charts

---

## 🐛 Troubleshooting

### Alert not firing?
- Check confluence score in info table
- Make sure you're in a killzone (if enabled)
- Verify trend direction matches

### Webhook not working?
- Test URL with a simple alert first
- Check TradersPost logs
- Verify JSON format is correct

### Wrong position size?
- TradersPost handles sizing, not TradingView
- Configure position size in TradersPost settings

---

## 📞 Support

For TradersPost setup: https://traderspost.io/docs
For TradingView alerts: https://www.tradingview.com/support/solutions/43000529348

---

*Built for NQ/ES futures trading with SMC concepts*
