# Stock API Options for Heatmap

## TradingView Limitations
❌ **TradingView does NOT have a public API for pulling stock data**
- TradingView is for **webhooks/alerts** (sending signals TO your server)
- Cannot pull live stock prices FROM TradingView
- Would need to scrape their website (not recommended, violates ToS)

## Best Free Stock APIs (2025)

### 1. **Finnhub** ⭐ RECOMMENDED
- **Free Tier:** 60 API calls/minute
- **Real-time data:** Yes
- **Market cap:** Yes
- **Setup:** Just need free API key
- **URL:** https://finnhub.io
- **Best for:** Real-time heatmaps

### 2. **Alpha Vantage**
- **Free Tier:** 5 API calls/minute, 500/day
- **Real-time data:** Yes (15-min delay on free tier)
- **Market cap:** Yes
- **URL:** https://www.alphavantage.co
- **Best for:** Historical data, slower updates

### 3. **IEX Cloud**
- **Free Tier:** 100,000 messages/month
- **Real-time data:** Yes
- **Market cap:** Yes
- **URL:** https://iexcloud.io
- **Best for:** High volume apps

### 4. **Twelve Data**
- **Free Tier:** 800 calls/day
- **Real-time data:** Yes
- **Market cap:** Yes
- **URL:** https://twelvedata.com
- **Best for:** Multiple markets

## Recommendation: **Finnhub**
- Most generous free tier (60/min = 3,600/hour)
- Real-time data
- Easy to use
- No credit card required

## Implementation
I'll set up Finnhub as the primary API with Yahoo Finance as fallback.

