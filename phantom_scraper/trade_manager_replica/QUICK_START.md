# Quick Start Guide - Trade Manager Replica

**Get the test site up and running in 5 minutes!**

---

## 🚀 **Setup Steps**

### 1. **Create Test User**
```bash
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
python3 SETUP_TEST_USER.py
```

**Full path:** `/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/SETUP_TEST_USER.py`

This creates a test user:
- **Username**: `testuser`
- **Password**: `testpass123`

---

### 2. **Start Backend Server**
```bash
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
python3 app.py
```

**Full path:** `/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/app.py`

The server will start on **http://localhost:5001**

You should see:
```
🚀 Just.Trades Backend Server Starting...
📡 Backend API: http://localhost:5001
🔌 WebSocket: ws://localhost:5001
```

---

### 3. **Start Frontend (Development Mode)**

**Option A: Vite Dev Server (Recommended for Development)**
```bash
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend"
npm install  # If not already installed
npm run dev
```

**Full path:** `/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend`

Frontend will run on **http://localhost:5173**

**Option B: Build for Production**
```bash
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend"
npm run build
```

Then access the app through the backend at **http://localhost:5001**

---

## 🔐 **Login**

1. Navigate to **http://localhost:5173** (dev) or **http://localhost:5001** (prod)
2. Use test credentials:
   - Username: `testuser`
   - Password: `testpass123`
   - reCAPTCHA: Any value (backend accepts placeholder for testing)

---

## 📋 **What's Implemented**

### ✅ **Backend APIs**
- Authentication (login, logout, check-auth)
- CSRF token generation
- Dashboard (summary, trades)
- Strategies (list, get, create, update, delete)
- Accounts (list, add, update, delete)
- Trades (list, open, tickers, timeframes)
- Profiles (favorites, stat config, widget info)

### ✅ **Frontend Components**
- Login page
- Dashboard
- My Recorders
- My Trader
- Account Management
- Control Center
- Settings
- Create/Edit Strategy

### ⚠️ **Known Limitations**

1. **reCAPTCHA**: Currently accepts placeholder token
   - TODO: Integrate actual reCAPTCHA v2 widget

2. **Database**: Some fields may need migration
   - Run `python3 SETUP_TEST_USER.py` to initialize database

3. **WebSocket**: Basic implementation exists
   - Control Center WebSocket may need additional work

4. **Form Submissions**: Settings form submissions not fully captured
   - Core functionality works, some edge cases may need testing

---

## 🧪 **Testing Endpoints**

### Test Login:
```bash
curl -X POST http://localhost:5001/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123","captchaToken":"test"}' \
  -c cookies.txt
```

### Test Dashboard:
```bash
curl -X GET http://localhost:5001/api/dashboard/summary/ \
  -b cookies.txt
```

### Test Strategies List:
```bash
curl -X GET http://localhost:5001/api/strategies/?val=DirStrat \
  -b cookies.txt
```

---

## 🐛 **Troubleshooting**

### Database Issues:
- Delete `trade_manager.db` and run `SETUP_TEST_USER.py` again
- Check database schema matches expected structure

### CORS Issues:
- Make sure frontend is running on allowed port (5173, 3000, 5000)
- Check `app.py` CORS configuration

### Authentication Issues:
- Check browser console for errors
- Verify session is set correctly
- Check CSRF token is being sent

### Frontend Not Loading:
- Check if `frontend/dist` exists (for production build)
- Or use `npm run dev` for development mode
- Check backend logs for errors

---

## 📝 **Next Steps**

1. **Test Login Flow**
   - Login with test user
   - Verify dashboard loads
   - Check API calls in browser DevTools

2. **Test Strategy Creation**
   - Navigate to Create Strategy page
   - Fill out form
   - Submit and verify strategy is created

3. **Test Dashboard**
   - Verify summary cards load
   - Check trades table
   - Test filters

4. **Add reCAPTCHA**
   - Install `react-google-recaptcha`
   - Add reCAPTCHA site key
   - Update Login component

---

## 🎯 **Success Criteria**

✅ Backend server starts without errors  
✅ Frontend loads (dev or production)  
✅ Can login with test user  
✅ Dashboard displays summary cards  
✅ Can create a strategy  
✅ API endpoints return correct data structures  

---

**Ready to test!** 🚀

If you encounter any issues, check:
- Backend logs (terminal running `app.py`)
- Browser console (F12)
- Network tab (DevTools → Network)
