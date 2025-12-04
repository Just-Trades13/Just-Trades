# Quick WebSocket Test

## Test 1: Check if Socket.IO Loads

Open browser console on Manual Trader page and type:
```javascript
typeof io
```

**Expected**: `"function"`  
**If undefined**: Socket.IO CDN is blocked or not loading

---

## Test 2: Manual Connection Test

In browser console, type:
```javascript
const testSocket = io();
testSocket.on('connect', () => console.log('✅ MANUAL TEST CONNECTED!'));
testSocket.on('connect_error', (err) => console.error('❌ ERROR:', err));
```

**Expected**: "✅ MANUAL TEST CONNECTED!"  
**If error**: Server issue or connection problem

---

## Test 3: Check Server Logs

When you load the page, server should show:
```
Client connected to WebSocket
```

**If not showing**: Server isn't accepting WebSocket connections

---

## Test 4: Check Network Tab

1. Open DevTools → Network
2. Filter by "WS" (WebSocket)
3. Refresh page
4. Should see: `ws://localhost:8082/socket.io/?EIO=4&transport=websocket`

**If not there**: Client isn't attempting connection

---

## Most Likely Issues

1. **Socket.IO CDN blocked** → Try different CDN or local file
2. **JavaScript error** → Check console for red errors
3. **Server not running** → Make sure `python ultra_simple_server.py` is running
4. **Port mismatch** → Make sure connecting to port 8082

---

## Quick Fix: Use Local Socket.IO

If CDN is blocked, download Socket.IO and serve locally:
```bash
cd static/js
wget https://cdn.socket.io/4.5.4/socket.io.min.js
```

Then change in HTML:
```html
<script src="/static/js/socket.io.min.js"></script>
```

