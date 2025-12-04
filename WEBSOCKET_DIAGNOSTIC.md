# WebSocket Diagnostic Steps

## Current Issue
- HAR file shows NO WebSocket connections
- Page took 484 seconds to load (8 minutes!) - something is hanging
- Only 1 API call: `/api/accounts`

## Diagnostic Steps

### 1. Check Browser Console
Open `http://localhost:8082/manual-trader` and check console for:
- JavaScript errors (red text)
- "🔌 WebSocket initialization script loaded"
- "Socket.IO available: true/false"
- Any connection errors

### 2. Check Network Tab
1. Open DevTools → Network tab
2. Refresh page
3. Filter by "WS" (WebSocket)
4. Should see: `ws://localhost:8082/socket.io/?EIO=4&transport=websocket`

### 3. Check Server Logs
When you load the page, server should show:
```
Client connected to WebSocket
```

### 4. Test Socket.IO Script Loading
In browser console, type:
```javascript
typeof io
```
Should return: `"function"` (not `"undefined"`)

### 5. Manual Connection Test
In browser console, type:
```javascript
const testSocket = io();
testSocket.on('connect', () => console.log('✅ Manual test connected!'));
testSocket.on('connect_error', (err) => console.error('❌ Error:', err));
```

## Common Issues

### Issue 1: Socket.IO Not Loading
**Symptom**: `typeof io === "undefined"`  
**Fix**: Check if CDN is blocked, try different CDN

### Issue 2: JavaScript Error
**Symptom**: Console shows red errors  
**Fix**: Fix the JavaScript error first

### Issue 3: Server Not Running
**Symptom**: Connection errors  
**Fix**: Make sure server is running with `python ultra_simple_server.py`

### Issue 4: CORS/Port Mismatch
**Symptom**: Connection refused  
**Fix**: Make sure connecting to correct port (8082)

## Quick Fix Test

Try opening `test_websocket.html` in browser:
- If this works → Issue is in manual_copy_trader.html
- If this doesn't work → Issue is with server or Socket.IO setup

