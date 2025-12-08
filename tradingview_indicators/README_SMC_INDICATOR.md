# SMC Strategy Indicator for NQ/ES Trading

## 📥 How to Install

1. Open TradingView
2. Go to **Pine Editor** (bottom of chart)
3. Click **Open** → **New blank indicator**
4. Delete all default code
5. Copy/paste the entire contents of `SMC_NQ_ES_Strategy.pine`
6. Click **Save** and name it "SMC Strategy - NQ/ES"
7. Click **Add to Chart**

---

## 🎯 Features Included

### 1. SMT Divergence (Smart Money Technique)
Compares NQ and ES to detect divergences:
- **Bullish SMT**: Current symbol makes Lower Low, comparison makes Higher Low
- **Bearish SMT**: Current symbol makes Higher High, comparison makes Lower High

> **Setup**: If you're on ES chart, set compare symbol to `NQ1!`  
> If you're on NQ chart, set compare symbol to `ES1!`

### 2. Fair Value Gaps (FVG)
- **Bullish FVG**: Gap up (green boxes) - price inefficiency to fill from above
- **Bearish FVG**: Gap down (red boxes) - price inefficiency to fill from below
- Auto-removes mitigated FVGs

### 3. Order Blocks (OB)
- **Bullish OB**: Last bearish candle before significant bullish move (teal boxes)
- **Bearish OB**: Last bullish candle before significant bearish move (maroon boxes)
- Removes invalidated OBs when price closes through them

### 4. Market Structure (BOS/CHoCH)
- **BOS (Break of Structure)**: Continuation - trend continues
- **CHoCH (Change of Character)**: Reversal - trend changes direction

### 5. Liquidity Levels
- **Equal Highs (EQH)**: Resting buy stops above - expect sweep
- **Equal Lows (EQL)**: Resting sell stops below - expect sweep
- **Sweeps**: X marks when liquidity is taken

### 6. Killzones (EST Times)
- **London**: 2:00 AM - 5:00 AM EST (blue background)
- **NY AM**: 8:30 AM - 11:00 AM EST (green background)
- **NY PM**: 1:30 PM - 4:00 PM EST (orange background)

### 7. Premium/Discount Zones
- **Premium**: Above equilibrium (50% of range) - look to sell
- **Discount**: Below equilibrium - look to buy
- Gray dotted line shows equilibrium

---

## 🎯 IDEAL TRADE SETUPS

The indicator marks **high-probability setups** with 🎯 when multiple confluences align:

### Bullish 🎯
- SMT Bullish Divergence
- Price in Discount Zone
- Near Bullish FVG or Order Block
- In a Killzone (preferably)

### Bearish 🎯
- SMT Bearish Divergence  
- Price in Premium Zone
- Near Bearish FVG or Order Block
- In a Killzone (preferably)

---

## ⚙️ Recommended Settings

### For NQ (on NQ chart):
```
Compare Symbol: ES1!
Min FVG Size: 5-10 points
Min OB Move: 15-20 points
Swing Length: 5 (for faster signals) or 10 (for cleaner structure)
```

### For ES (on ES chart):
```
Compare Symbol: NQ1!
Min FVG Size: 2-4 points
Min OB Move: 8-12 points
Swing Length: 5 or 10
```

### Timeframes:
- **5m-15m**: Best for entries and FVG/OB
- **1H-4H**: Best for structure (BOS/CHoCH)
- **Daily**: Best for bias and key levels

---

## 🔔 Alerts Available

1. **Bullish/Bearish SMT Divergence**
2. **Bullish/Bearish FVG**
3. **CHoCH Bullish/Bearish**
4. **Liquidity Sweep High/Low**
5. **Killzone Opens** (London, NY AM, NY PM)
6. **🎯 High Probability Setups** (confluence alerts)

To set up alerts:
1. Right-click on chart → **Add Alert**
2. Condition: Select "SMC Strategy - NQ/ES"
3. Choose the alert type you want
4. Set notification method (popup, email, webhook)

---

## 📊 Info Table (Top Right)

Shows real-time info:
- Current Trend (Bullish/Bearish/Neutral)
- Zone (Premium/Discount)
- Equilibrium level
- Current Session
- Last Swing High/Low
- SMT Comparison Symbol

---

## 🧠 TRJ's Trading Approach

Based on the concepts in the indicator:

### Entry Checklist:
1. ✅ Identify HTF bias (Daily/4H structure)
2. ✅ Wait for price to reach Premium (shorts) or Discount (longs)
3. ✅ Look for SMT divergence between NQ and ES
4. ✅ Find FVG or Order Block for entry
5. ✅ Confirm with BOS/CHoCH on LTF
6. ✅ Enter during Killzone for momentum
7. ✅ Target opposite liquidity (EQH/EQL)

### Risk Management:
- Stop loss: Beyond the Order Block or FVG
- Target: Liquidity levels or equilibrium

---

## 🔧 Customization

All colors and parameters are adjustable in the indicator settings panel. Toggle each feature on/off as needed.

---

## ⚠️ Disclaimer

This is a tool to help identify SMC concepts on your chart. It does not guarantee profitable trades. Always:
- Backtest thoroughly
- Use proper risk management
- Trade with a plan
- Don't rely solely on any indicator

---

## Updates

If you want me to add:
- Multi-timeframe analysis
- Auto-drawn trendlines
- ICT concepts (Breakers, Mitigation Blocks)
- Session highs/lows
- Previous day high/low/close
- Weekly/Monthly levels

Just let me know!
