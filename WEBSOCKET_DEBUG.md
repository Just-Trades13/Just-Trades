# WebSocket Debugging Guide

**Issue**: WebSocket connection not showing in console  
**HAR Analysis**: Shows polling still happening (multiple `/api/positions/1` calls)

---

## 🔍 Diagnostic Steps

### 1. Check Server is Running with WebSocket
```bash
python ultra_simple_server.py
```

**Expected output:**
```
Starting Just.Trades. server on 0.0.0.0:8082
WebSocket support enabled (like Trade Manager)
```

### 2. Check Browser Console
Open `http://localhost:8082/manual-trader` and check console for:
- ✅ "Initializing WebSocket connection..."
- ✅ "✅ Connected to WebSocket - Manual Trader"
- ❌ Any errors?

### 3. Check Network Tab
1. Open DevTools → Network tab
2. Filter by "WS" (WebSocket)
3. Should see a WebSocket connection to `ws://localhost:8082/socket.io/`

### 4. Check Server Logs
Look for:
- WebSocket connection messages
- Any errors when clients connect

---

## 🐛 Common Issues

### Issue 1: Socket.IO Not Loading
**Symptom**: Console shows "Socket.IO not loaded!"  
**Fix**: Check if CDN is accessible, try different CDN

### Issue 2: Server Not Running
**Symptom**: Connection errors in console  
**Fix**: Make sure server is running with `socketio.run()`

### Issue 3: CORS Issues
**Symptom**: Connection blocked  
**Fix**: Check `cors_allowed_origins` in SocketIO initialization

### Issue 4: Port Mismatch
**Symptom**: Can't connect  
**Fix**: Make sure client connects to same port as server

---

## ✅ Quick Test

Run this in browser console on Manual Trader page:
```javascript
// Check if Socket.IO loaded
console.log('Socket.IO loaded:', typeof io !== 'undefined');

// Try connecting manually
if (typeof io !== 'undefined') {
    const testSocket = io();
    testSocket.on('connect', () => console.log('✅ Test connection successful!'));
    testSocket.on('connect_error', (err) => console.error('❌ Connection error:', err));
}
```

---

## 📊 Expected Behavior

**When working correctly:**
1. Page loads
2. Console shows "Initializing WebSocket connection..."
3. Console shows "✅ Connected to WebSocket - Manual Trader"
4. Network tab shows WebSocket connection (filter by "WS")
5. Status badge shows "Connected"
6. Position updates appear automatically (no polling)

**When NOT working:**
1. No console messages
2. Network tab shows only HTTP requests (no WebSocket)
3. Status badge shows "Disconnected" or "Connecting..."
4. Multiple `/api/positions/1` calls (polling fallback)

---

## 🔧 Next Steps

1. **Check server logs** - Are WebSocket connections being accepted?
2. **Check browser console** - Any JavaScript errors?
3. **Check Network tab** - Is WebSocket connection established?
4. **Test manual connection** - Use console test code above

