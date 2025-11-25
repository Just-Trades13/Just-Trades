# Tradovate P&L Tracking Test Project

This is a minimal standalone test project to verify real-time P&L tracking works correctly before integrating into the main project.

## Purpose

- Test Tradovate authentication and token capture
- Test WebSocket connections (user data + market data)
- Test real-time position updates
- Test real-time quote updates
- Calculate and display live P&L
- Identify any issues in isolation

## Setup

1. Install dependencies:
```bash
pip install aiohttp websockets
```

2. Make sure you have:
   - Tradovate account credentials
   - At least one OPEN position in Tradovate (netPos != 0)
   - Optional: Client ID and Client Secret (if using OAuth app)

## Usage

Run the test:
```bash
python test_pnl_tracking.py
```

The script will:
1. Ask for your Tradovate credentials
2. Authenticate and capture tokens (including mdAccessToken)
3. Fetch open positions from REST API
4. Connect to user data WebSocket for position updates
5. Connect to market data WebSocket for real-time quotes
6. Display P&L updates every second

## What to Look For

### Success Indicators:
- ✅ Authentication succeeds and captures `mdAccessToken`
- ✅ WebSocket connections establish successfully
- ✅ Position updates received via WebSocket
- ✅ Quote updates received via WebSocket
- ✅ P&L values update in real-time (not frozen)

### Common Issues:
- ❌ No `mdAccessToken` - market data WebSocket won't work
- ❌ WebSocket connection fails - check token format
- ❌ No position updates - check subscription format
- ❌ No quote updates - check subscription format
- ❌ P&L frozen - using stale REST API data instead of WebSocket

## Output

The script will display:
- Authentication status
- WebSocket connection status
- Raw WebSocket messages (for debugging)
- Position details (symbol, entry price, current price)
- Real-time P&L calculation
- WebSocket `openPnl` if available

## Next Steps

Once this test project works correctly:
1. Identify the working patterns
2. Document the correct message formats
3. Integrate into main project
4. Remove debugging code

