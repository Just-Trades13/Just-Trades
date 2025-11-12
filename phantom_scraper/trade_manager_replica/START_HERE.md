# 🚀 START HERE - Complete Setup Commands

**Copy and paste these commands in order:**

---

## **Step 1: Create Test User**

```bash
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
python3 SETUP_TEST_USER.py
```

**Expected output:**
```
✅ Test user created successfully!
   Username: testuser
   Password: testpass123
   User ID: 1
```

---

## **Step 2: Start Backend Server**

**Open a new terminal window/tab and run:**

```bash
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
python3 app.py
```

**Expected output:**
```
🚀 Just.Trades Backend Server Starting...
📡 Backend API: http://localhost:5001
🔌 WebSocket: ws://localhost:5001
```

**Keep this terminal open!** The backend must stay running.

---

## **Step 3: Start Frontend (Development Mode)**

**Open another new terminal window/tab and run:**

```bash
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend"
npm install
npm run dev
```

**Expected output:**
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

**Keep this terminal open too!**

---

## **Step 4: Open in Browser**

Navigate to: **http://localhost:5173**

Login with:
- **Username:** `testuser`
- **Password:** `testpass123`

---

## **File Paths Reference**

### Backend Files:
- **Main app:** `/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/app.py`
- **Database:** `/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/trade_manager.db`
- **Setup script:** `/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/SETUP_TEST_USER.py`

### Frontend Files:
- **Frontend directory:** `/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend`
- **Package.json:** `/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend/package.json`
- **Build output:** `/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend/dist`

---

## **Quick Commands Cheat Sheet**

```bash
# Navigate to project root
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"

# Setup test user
python3 SETUP_TEST_USER.py

# Start backend (Terminal 1)
python3 app.py

# Start frontend (Terminal 2)
cd frontend && npm run dev

# Build frontend for production
cd frontend && npm run build
```

---

## **Troubleshooting**

### Backend won't start:
- Check if port 5001 is already in use
- Check Python version: `python3 --version` (should be 3.7+)
- Install dependencies: `pip3 install flask flask-cors flask-session flask-socketio`

### Frontend won't start:
- Check Node version: `node --version` (should be 16+)
- Install dependencies: `cd frontend && npm install`
- Check if port 5173 is already in use

### Database errors:
- Delete database and rerun setup: `rm trade_manager.db && python3 SETUP_TEST_USER.py`

---

**That's it! You're ready to test.** 🎉
