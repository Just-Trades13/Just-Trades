# TradingView to Tradovate Automated Trading System

A complete solution for automating trades from TradingView alerts to Tradovate using webhooks and session-based authentication (no paid API required).

## 🎯 What This System Does

- **Receives TradingView alerts** via webhook
- **Automatically logs into Tradovate** using your regular credentials
- **Executes trades** based on your strategy signals
- **Manages positions** with stop loss and take profit
- **Works without paid APIs** - uses the same login as TradingView integration

## 📁 Files Created

### Core System
- `trading_webhook_server.py` - Main webhook server and trading engine
- `start_trading_bot.py` - Easy startup script with checks
- `test_trading_webhook.py` - Test script to verify functionality

### Configuration
- `trading_config.env` - Configuration template
- `TRADING_SETUP_GUIDE.md` - Complete setup guide

### TradingView Examples
- `tradingview_alert_example.pine` - Basic RSI/MA strategy example
- `tradingview_advanced_example.pine` - Advanced strategy with ATR stops

## 🚀 Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure credentials:**
```bash
cp trading_config.env .env
# Edit .env with your Tradovate credentials
```

3. **Start the system:**
```bash
python start_trading_bot.py
```

4. **Configure TradingView alerts:**
   - Webhook URL: `http://localhost:5000/webhook`
   - Message format: See examples in the Pine Script files

## 🔧 How It Works

### 1. Webhook Server
- Runs on Flask (port 5000)
- Receives JSON alerts from TradingView
- Parses trading signals (buy/sell/close)
- Manages Tradovate browser sessions

### 2. Tradovate Integration
- Uses Selenium with undetected-chromedriver
- Logs in with your regular credentials
- Automates order placement through web interface
- Handles stop loss and take profit orders

### 3. Alert Processing
- Supports multiple alert formats
- Validates trading signals
- Manages position sizing
- Implements risk management

## 📊 Supported Features

### Trading Actions
- ✅ Market buy orders
- ✅ Market sell orders
- ✅ Position closing
- ✅ Stop loss orders
- ✅ Take profit orders

### Risk Management
- ✅ Position size limits
- ✅ Risk percentage controls
- ✅ Order validation
- ✅ Error handling

### Monitoring
- ✅ Real-time logging
- ✅ Health check endpoint
- ✅ Account information
- ✅ Trade confirmations

## 🛡️ Security & Safety

### Built-in Protections
- Environment variable configuration
- Input validation
- Error handling
- Session management
- Logging and monitoring

### Risk Warnings
- ⚠️ **Paper trade first** - Test thoroughly
- ⚠️ **Start small** - Use minimal position sizes
- ⚠️ **Monitor closely** - Don't leave unattended
- ⚠️ **Have backups** - Manual trading capability

## 📈 TradingView Alert Formats

### Basic Format
```json
{
  "symbol": "ES1!",
  "action": "buy",
  "quantity": 1
}
```

### Advanced Format with Stops
```json
{
  "symbol": "NQ1!",
  "action": "sell",
  "quantity": 2,
  "stop_loss": 15100.0,
  "take_profit": 14900.0,
  "strategy": "MyStrategy"
}
```

### Close Position
```json
{
  "symbol": "ES1!",
  "action": "close"
}
```

## 🔄 Production Deployment

### Local Testing
- Use ngrok to expose local server
- Test with TradingView alerts
- Verify all functionality

### VPS Deployment
- Upload code to VPS
- Install dependencies
- Configure environment
- Run with process manager
- Set up SSL for HTTPS

## 🐛 Troubleshooting

### Common Issues
1. **Login fails** - Check credentials, disable 2FA
2. **Webhook not receiving** - Verify URL, check server status
3. **Orders not placing** - Check margin, symbol validity
4. **Browser errors** - Update Chrome, check driver compatibility

### Debug Mode
Enable in `.env`:
```
WEBHOOK_DEBUG=true
HEADLESS_MODE=false
```

## 📞 Support & Maintenance

### Monitoring
- Check logs: `tail -f trading_bot.log`
- Health check: `curl http://localhost:5000/health`
- Account info: `curl http://localhost:5000/account`

### Updates
- Keep dependencies updated
- Monitor Tradovate interface changes
- Test regularly with paper trading
- Stay updated with TradingView changes

## ⚖️ Legal Disclaimer

This software is for educational purposes only. Trading futures involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results. Always consult with a financial advisor before making investment decisions.

## 🎉 Ready to Start?

1. Read the complete setup guide: `TRADING_SETUP_GUIDE.md`
2. Configure your credentials in `.env`
3. Start with paper trading
4. Test thoroughly
5. Deploy carefully
6. Monitor closely

**Happy Trading! 🚀**
