# Installation Instructions - WebSocket Support

**Status**: ✅ Implementation Complete!

---

## Step 1: Install Flask-SocketIO

```bash
pip install flask-socketio
```

---

## Step 2: Test the Server

```bash
python ultra_simple_server.py
```

You should see:
```
Starting Just.Trades. server on 0.0.0.0:8082
WebSocket support enabled (like Trade Manager)
```

---

## Step 3: Test WebSocket Connection

1. **Open your browser** to `http://localhost:8082/control-center`
2. **Open DevTools** (F12) → Console tab
3. **You should see**: "Connected to WebSocket"
4. **Check Network tab** → Filter by "WS" → Should see WebSocket connection

---

## What's Been Implemented

### ✅ Backend (ultra_simple_server.py)
- Flask-SocketIO initialized
- WebSocket handlers (connect, disconnect, subscribe)
- Background thread emitting updates every second
- Strategy P&L recording database table
- Background service recording P&L every second
- P&L Calendar API endpoint (`/api/dashboard/pnl-calendar`)
- P&L vs Drawdown Chart API endpoint (`/api/dashboard/pnl-drawdown-chart`)
- WebSocket events emitted after trade execution
- Changed `app.run` to `socketio.run`

### ✅ Frontend (templates/control_center.html)
- Socket.IO client library added
- WebSocket connection on page load
- Real-time log entries
- Real-time P&L updates
- Real-time position updates
- Connection status indicator

---

## WebSocket Events

### Events Emitted by Server:
- `status` - Connection status
- `pnl_update` - P&L updates (every second)
- `position_update` - Position updates (every second)
- `strategy_pnl_update` - Strategy-specific P&L (every second)
- `log_entry` - Log entries (on events)
- `trade_executed` - Trade execution events

### Events Received by Server:
- `connect` - Client connects
- `disconnect` - Client disconnects
- `subscribe` - Client subscribes to channels

---

## Next Steps

1. **Install flask-socketio**: `pip install flask-socketio`
2. **Start server**: `python ultra_simple_server.py`
3. **Test WebSocket**: Open Control Center and check console
4. **Test trade execution**: Place a manual trade and watch logs update
5. **Implement P&L calculation**: Update `calculate_strategy_pnl()` function
6. **Add dashboard charts**: Use the new API endpoints

---

## TODO: Complete P&L Calculation

The following functions need actual implementation:
- `calculate_strategy_pnl(strategy_id)` - Calculate P&L from trades
- `calculate_strategy_drawdown(strategy_id)` - Calculate drawdown
- `emit_realtime_updates()` - Get actual positions and P&L from database

These are currently placeholders returning 0.0. You'll need to:
1. Query your trades database
2. Calculate P&L based on entry/exit prices
3. Calculate drawdown from peak to current

---

## Testing Checklist

- [ ] Install flask-socketio
- [ ] Start server successfully
- [ ] WebSocket connects on Control Center page
- [ ] Status dot shows "Connected"
- [ ] Log entries appear in real-time
- [ ] P&L updates (once calculation is implemented)
- [ ] Trade execution emits WebSocket events
- [ ] Dashboard APIs return data

---

**Ready to test!** Install flask-socketio and start the server!

