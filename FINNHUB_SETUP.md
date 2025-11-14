# Finnhub API Setup Guide

## Why Finnhub?
- ✅ **60 API calls/minute** (most generous free tier)
- ✅ **Real-time data** (no delays)
- ✅ **Market cap included**
- ✅ **No credit card required**
- ✅ **Reliable and fast**

## Quick Setup (2 minutes)

### Step 1: Get Free API Key
1. Go to: https://finnhub.io
2. Click **"Get Free API Key"**
3. Sign up (email + password)
4. Copy your API key (looks like: `c1234567890abcdefghij`)

### Step 2: Add API Key to Your Server

**Option A: Environment Variable (Recommended)**
```bash
export FINNHUB_API_KEY="your_api_key_here"
```

**Option B: Add to your server startup**
```bash
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
FINNHUB_API_KEY="your_api_key_here" python3 ultra_simple_server.py --port 8082
```

**Option C: Create a `.env` file** (if you want to keep it secret)
```bash
echo "FINNHUB_API_KEY=your_api_key_here" > .env
```

### Step 3: Restart Server
The server will automatically:
- ✅ Use Finnhub if API key is set
- ✅ Fall back to Yahoo Finance if Finnhub fails
- ✅ Use sample data as last resort

## Current Status

**Without API Key:**
- Uses Yahoo Finance (current setup)
- Works but may be slower/less reliable

**With Finnhub API Key:**
- Faster, more reliable
- Real market cap data
- Better rate limits

## TradingView Note

❌ **TradingView does NOT have a public API for pulling stock data**
- TradingView is for **webhooks** (sending alerts TO your server)
- Cannot pull live prices FROM TradingView
- Use Finnhub or other APIs for data

## Test It

After adding your API key, refresh your dashboard and check the server logs:
```bash
tail -f flask_output.log | grep -i finnhub
```

You should see: `"Finnhub: Successfully fetched NVDA: $XXX.XX (+X.XX%)"`

