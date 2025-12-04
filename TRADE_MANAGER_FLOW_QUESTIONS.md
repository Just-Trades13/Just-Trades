# Trade Manager Flow - Questions for Implementation

## Authentication Flow

1. **Username/Password Storage**:
   - Does Trade Manager store username/password in their database?
   - Or do they pass it through to TradingView/Tradovate each time?
   - How do they handle password security/encryption?

2. **TradingView Connection**:
   - When user adds account with username/password, how does Trade Manager connect to TradingView?
   - Is there a TradingView API endpoint to authenticate with broker credentials?
   - What's the exact API call/endpoint?

## TradingView Broker Integration API

3. **Market Data Access**:
   - What TradingView API endpoints does Trade Manager use to get market data?
   - Is it a REST API or WebSocket?
   - What's the base URL? (e.g., `https://api.tradingview.com/` or similar)

4. **Authentication with TradingView**:
   - How does Trade Manager authenticate with TradingView's broker integration API?
   - Do they use the broker username/password directly?
   - Or is there a TradingView API key/token involved?

5. **Symbol Format**:
   - When Trade Manager gets market data from TradingView, what symbol format does it use?
   - Is it TradingView format (MES1!, MNQ1!) or broker format (MESM1, MNQM1)?

## Account Setup Flow

6. **Adding Account**:
   - When user adds account in Trade Manager:
     - They enter username/password
     - They check "TradingView add-on enabled"?
     - What happens next? How does Trade Manager verify the TradingView connection?

7. **TradingView Add-on Verification**:
   - How does Trade Manager know if TradingView add-on is enabled?
   - Is there an API call to check this?
   - Or does it just try to connect and see if it works?

## Market Data Subscription

8. **Real-time Updates**:
   - How does Trade Manager subscribe to real-time market data from TradingView?
   - WebSocket? REST polling? Something else?
   - What's the subscription format?

9. **Data Format**:
   - What does the market data response look like from TradingView?
   - JSON? What fields? (last, bid, ask, volume, etc.)

## Trading Execution

10. **Order Placement**:
    - Does Trade Manager place orders through TradingView or directly to Tradovate?
    - If through TradingView, what's the API endpoint?
    - If directly to Tradovate, how do they authenticate? (username/password to get token?)

## What I Need From You

Please explain:
1. **The exact flow** from user adding account → getting market data
2. **TradingView API endpoints** Trade Manager uses
3. **Authentication method** with TradingView
4. **Any API documentation** or examples you've seen
5. **How you know** TradingView add-on is enabled/working

## Implementation Plan

Once I understand the flow, I'll implement:
1. ✅ Username/password authentication option (in addition to OAuth)
2. ✅ TradingView broker integration API connection
3. ✅ Market data subscription via TradingView
4. ✅ Real-time price updates
5. ✅ PnL calculation using TradingView prices

