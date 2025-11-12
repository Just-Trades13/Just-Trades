# Just.Trades - Testing Guide

## 🚀 Quick Start

### Option 1: Use Start Scripts (Recommended)

**Terminal 1 - Backend:**
```bash
cd phantom_scraper/trade_manager_replica
./start_backend.sh
```

**Terminal 2 - Frontend:**
```bash
cd phantom_scraper/trade_manager_replica
./start_frontend.sh
```

### Option 2: Manual Start

**Backend:**
```bash
cd phantom_scraper/trade_manager_replica
python3 setup_test_user.py  # Create test user
python3 app.py              # Start server on http://localhost:5000
```

**Frontend:**
```bash
cd phantom_scraper/trade_manager_replica/frontend
npm install  # First time only
npm run dev  # Start dev server (usually http://localhost:5173)
```

---

## 🔐 Test Credentials

**Username:** `testuser`  
**Password:** `testpass123`

These are created automatically when you run `setup_test_user.py` or `start_backend.sh`.

---

## ✅ Testing Checklist

### 1. Authentication ✅
- [ ] Open frontend (http://localhost:5173)
- [ ] Navigate to login page
- [ ] Login with test credentials
- [ ] Verify redirect to dashboard

### 2. Dashboard ✅
- [ ] View dashboard summary cards
- [ ] Check filters (user, strategy, symbol, timeframe)
- [ ] View trade history table
- [ ] Verify data loads correctly

### 3. My Recorders ✅
- [ ] View strategies list
- [ ] Click "Create Strategy"
- [ ] Fill out strategy form
- [ ] Save strategy
- [ ] Edit strategy
- [ ] Delete strategy
- [ ] Test search functionality

### 4. Account Management ✅
- [ ] View accounts list
- [ ] Click "+ Add Account"
- [ ] Fill out Tradovate account form
- [ ] Test connection (if you have Tradovate credentials)
- [ ] Edit account
- [ ] Delete account

### 5. Control Center ✅
- [ ] Open Control Center page
- [ ] Verify WebSocket connection (green dot)
- [ ] Select strategy
- [ ] Select ticker
- [ ] Test Buy button
- [ ] Test Sell button
- [ ] Test Close button
- [ ] Check logs panel for updates

### 6. Settings ✅
- [ ] View user profile
- [ ] Toggle push notifications
- [ ] Connect Discord (if configured)
- [ ] Toggle Discord DMs
- [ ] Update username
- [ ] Change password

### 7. API Endpoints ✅
Test directly with curl or Postman:

```bash
# Get CSRF token
curl http://localhost:5000/api/system/csrf-token/

# Login
curl -X POST http://localhost:5000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}' \
  -c cookies.txt

# Check auth (with session cookie)
curl http://localhost:5000/api/auth/check-auth/ -b cookies.txt

# Get strategies
curl http://localhost:5000/api/strategies/ -b cookies.txt

# Get accounts
curl http://localhost:5000/api/accounts/get-all-at-accounts/ -b cookies.txt
```

---

## 🐛 Troubleshooting

### Backend won't start
- Check Python version: `python3 --version` (need 3.8+)
- Install dependencies: `pip3 install -r requirements.txt`
- Check port 5000 is available: `lsof -i :5000`

### Frontend won't start
- Check Node.js version: `node --version` (need 16+)
- Install dependencies: `npm install`
- Check port conflicts: `lsof -i :5173`

### Can't login
- Verify test user exists: Run `python3 setup_test_user.py`
- Check database file exists: `ls -la trade_manager.db`
- Check backend is running: `curl http://localhost:5000/api/system/csrf-token/`

### WebSocket not connecting
- Verify Flask-SocketIO is installed: `pip3 list | grep flask-socketio`
- Check backend logs for WebSocket connection messages
- Verify frontend WebSocket URL in `src/services/websocket.js`

### API errors
- Check browser console for errors
- Check backend terminal for error messages
- Verify CSRF token is being sent (check Network tab)

---

## 📊 Expected Behavior

### Backend
- Starts on `http://localhost:5000`
- Shows: `Running on http://0.0.0.0:5000`
- WebSocket ready for connections

### Frontend
- Starts on `http://localhost:5173` (or next available port)
- Vite dev server shows compilation status
- Hot reload works on file changes

### Database
- SQLite file: `trade_manager.db` (created automatically)
- Test user created automatically
- Tables initialized on first run

---

## 🎯 Next Steps After Testing

1. **Add Real Tradovate Account**
   - Get Tradovate credentials
   - Add account via Account Management
   - Test connection

2. **Create Real Strategy**
   - Create strategy in My Recorders
   - Configure position size, TP/SL
   - Set demo account

3. **Test Webhook**
   - Get webhook URL: `http://your-domain/api/webhook/{strategy_id}`
   - Configure in TradingView alert
   - Send test alert

4. **Test Recording**
   - Start recording on a strategy
   - Place trades in demo account
   - Verify positions are recorded

---

## 📝 Notes

- **Database**: SQLite file is created automatically in the project directory
- **Sessions**: Stored in filesystem (Flask-Session)
- **CSRF**: Tokens auto-generated on each request
- **WebSocket**: Auto-reconnects on disconnect
- **CORS**: Configured for localhost:3000, localhost:5000, localhost:5173

---

**Happy Testing! 🎉**

