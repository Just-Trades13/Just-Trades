# TradingView to Tradovate Automated Trading Setup Guide

This guide will help you set up automated trading from TradingView alerts to Tradovate using webhooks and session-based authentication (no paid API required).

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /Users/mylesjadwin/Trading\ Projects/phantom_scraper
pip install -r requirements.txt
```

### 2. Configure Credentials

1. Copy the configuration template:
```bash
cp trading_config.env .env
```

2. Edit `.env` with your Tradovate credentials:
```bash
nano .env
```

Fill in your actual credentials:
```
TRADOVATE_USERNAME=your_actual_email@example.com
TRADOVATE_PASSWORD=your_actual_password
```

### 3. Start the Webhook Server

```bash
python trading_webhook_server.py
```

The server will start on `http://localhost:5000` and be ready to receive TradingView alerts.

## 📡 TradingView Alert Configuration

### Setting Up Webhook Alerts in TradingView

1. **Create a Strategy or Use an Indicator**
   - Go to TradingView and create your strategy/indicator
   - Add alert conditions for buy/sell signals

2. **Create Alert**
   - Right-click on your chart → "Add Alert"
   - Set your conditions (e.g., when strategy signals buy/sell)
   - Choose "Webhook URL" as the notification method

3. **Configure Webhook URL**
   - **Local Testing**: `http://localhost:5000/webhook`
   - **Production**: `https://your-domain.com/webhook` (use ngrok or similar for testing)

4. **Alert Message Format**
   Use this JSON format in the "Message" field:

```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "quantity": 1,
  "price": "{{close}}",
  "stop_loss": "{{strategy.order.stop}}",
  "take_profit": "{{strategy.order.limit}}",
  "strategy": "{{strategy.strategy_name}}"
}
```

### Alternative Simple Format

For basic alerts, you can use this simpler format:

```json
{
  "symbol": "ES1!",
  "action": "buy",
  "quantity": 1
}
```

## 🔧 Advanced Configuration

### Custom Alert Formats

The webhook server can handle various alert formats. Here are examples:

#### Pine Script Strategy Alert
```json
{
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "quantity": {{strategy.order.contracts}},
  "price": "{{close}}",
  "stop_loss": "{{strategy.order.stop}}",
  "take_profit": "{{strategy.order.limit}}"
}
```

#### Indicator Alert
```json
{
  "symbol": "NQ1!",
  "action": "sell",
  "quantity": 2,
  "strategy": "RSI_Overbought"
}
```

#### Close Position Alert
```json
{
  "symbol": "YM1!",
  "action": "close"
}
```

### Supported Actions

- `buy` / `long` / `enter_long` - Open long position
- `sell` / `short` / `enter_short` - Open short position  
- `close` / `exit` - Close existing position

### Supported Symbols

The system works with any Tradovate-supported futures symbols:
- `ES1!` - E-mini S&P 500
- `NQ1!` - E-mini NASDAQ-100
- `YM1!` - E-mini Dow Jones
- `RTY1!` - E-mini Russell 2000
- `GC1!` - Gold
- `CL1!` - Crude Oil
- And many more...

## 🛡️ Security Features

### Webhook Authentication (Optional)

Add a secret key to your `.env` file:
```
WEBHOOK_SECRET=your_secret_key_here
```

Then include it in your TradingView alerts:
```json
{
  "symbol": "ES1!",
  "action": "buy",
  "quantity": 1,
  "secret": "your_secret_key_here"
}
```

### Risk Management

Configure risk parameters in `.env`:
```
DEFAULT_QUANTITY=1
MAX_QUANTITY=10
RISK_PERCENTAGE=2.0
```

## 📊 Monitoring and Logs

### View Logs
```bash
tail -f trading_bot.log
```

### Health Check
```bash
curl http://localhost:5000/health
```

### Account Information
```bash
curl http://localhost:5000/account
```

## 🔄 Production Deployment

### Using ngrok for Testing

1. Install ngrok:
```bash
brew install ngrok
```

2. Start your webhook server:
```bash
python trading_webhook_server.py
```

3. In another terminal, expose your local server:
```bash
ngrok http 5000
```

4. Use the ngrok URL in your TradingView alerts:
```
https://abc123.ngrok.io/webhook
```

### VPS Deployment

1. Upload your code to a VPS
2. Install dependencies
3. Configure environment variables
4. Run with a process manager like PM2 or systemd
5. Set up SSL certificate for HTTPS

## 🚨 Important Notes

### Trading Risks
- **This is for educational purposes only**
- **Always test with paper trading first**
- **Start with small position sizes**
- **Monitor your trades closely**
- **Have proper risk management in place**

### Technical Considerations
- The system uses Selenium to automate browser interactions
- Keep your Tradovate credentials secure
- Monitor the webhook server for errors
- Have a backup plan if automation fails
- Test thoroughly before going live

### Browser Requirements
- Chrome browser must be installed
- The system uses undetected-chromedriver
- Headless mode is enabled by default
- Can be disabled for debugging

## 🐛 Troubleshooting

### Common Issues

1. **Login Failed**
   - Check your Tradovate credentials
   - Ensure 2FA is disabled or handle it manually
   - Check for captcha requirements

2. **Webhook Not Receiving Alerts**
   - Verify webhook URL is correct
   - Check if server is running
   - Test with curl: `curl -X POST http://localhost:5000/webhook -H "Content-Type: application/json" -d '{"symbol":"ES1!","action":"buy","quantity":1}'`

3. **Order Placement Failed**
   - Check if you have sufficient margin
   - Verify symbol is correct
   - Check if market is open
   - Review browser logs for errors

4. **Browser Issues**
   - Update Chrome browser
   - Check undetected-chromedriver compatibility
   - Try disabling headless mode for debugging

### Debug Mode

Enable debug mode in `.env`:
```
WEBHOOK_DEBUG=true
HEADLESS_MODE=false
```

This will show the browser window and provide more detailed logging.

## 📞 Support

If you encounter issues:

1. Check the logs: `tail -f trading_bot.log`
2. Test the webhook manually with curl
3. Verify your TradingView alert format
4. Check your Tradovate account status
5. Review the browser console for errors

## 🔄 Updates and Maintenance

- Keep your dependencies updated
- Monitor Tradovate for interface changes
- Test regularly with paper trading
- Keep backups of your configuration
- Stay updated with TradingView webhook changes

---

**Disclaimer**: This software is for educational purposes only. Trading futures involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results. Always consult with a financial advisor before making investment decisions.
