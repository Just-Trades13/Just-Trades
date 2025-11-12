# Just.Trades 🚀

**Complete Trade Manager Replica - 100% Functional**

A full-stack trading management platform with real-time updates, Tradovate integration, and automated strategy execution.

---

## 🎯 Quick Start

### 1. Install Dependencies

```bash
cd phantom_scraper/trade_manager_replica
./install_deps.sh
```

**Or manually:**
```bash
# Backend
pip3 install --break-system-packages -r requirements.txt

# Frontend
cd frontend
npm install
```

### 2. Create Test User

```bash
python3 setup_test_user.py
```

**Test Credentials:**
- Username: `testuser`
- Password: `testpass123`

### 3. Start Backend

```bash
python3 app.py
```

Backend runs on: **http://localhost:5000**

### 4. Start Frontend (new terminal)

```bash
cd frontend
npm run dev
```

Frontend runs on: **http://localhost:5173**

---

## 📋 Features

✅ **Complete Authentication System**
- User login/logout
- Session management
- CSRF protection

✅ **Strategy Management**
- Create/edit/delete strategies
- Demo account recording
- Position tracking

✅ **Account Management**
- Add Tradovate accounts
- Test connections
- Subaccount management

✅ **Manual Trading**
- Control Center interface
- Real-time WebSocket updates
- Buy/Sell/Close orders

✅ **Dashboard & Analytics**
- Trade history
- Performance metrics
- Win rate calculation
- P&L tracking

✅ **Integrations**
- Tradovate API
- Discord OAuth & DMs
- TradingView webhooks

---

## 🏗️ Architecture

### Backend
- **Framework:** Flask 3.0
- **Database:** SQLite (PostgreSQL ready)
- **WebSocket:** Flask-SocketIO
- **API:** RESTful with 25+ endpoints

### Frontend
- **Framework:** React 19
- **Build Tool:** Vite
- **Routing:** React Router
- **State:** Context API
- **WebSocket:** Socket.IO Client

---

## 📁 Project Structure

```
trade_manager_replica/
├── api/              # API blueprints (11 endpoints)
├── services/         # Business logic (Tradovate, Discord, Recorder)
├── frontend/         # React application
│   ├── src/
│   │   ├── pages/   # 8 page components
│   │   ├── components/
│   │   ├── services/
│   │   └── contexts/
├── database.py       # Database schema
├── websocket_handlers.py
└── app.py           # Main Flask app
```

---

## 🔌 API Endpoints

### Authentication
- `GET /api/auth/check-auth/` - Check auth status
- `POST /api/auth/login/` - Login
- `POST /api/auth/logout/` - Logout

### Strategies
- `GET /api/strategies/` - List strategies
- `POST /api/strategies/` - Create strategy
- `PUT /api/strategies/{id}/` - Update strategy
- `DELETE /api/strategies/{id}/` - Delete strategy

### Accounts
- `GET /api/accounts/get-all-at-accounts/` - List accounts
- `POST /api/accounts/add-tradovate/` - Add Tradovate account
- `POST /api/accounts/test-tradovate-connection/` - Test connection

### Trades
- `GET /api/trades/` - Get trades
- `GET /api/trades/open/` - Get open trades
- `POST /api/trades/execute/` - Execute trade

### Dashboard
- `GET /api/dashboard/summary/` - Dashboard summary
- `GET /api/dashboard/analytics/{id}/` - Strategy analytics

**See COMPLETE_IMPLEMENTATION.md for full API documentation**

---

## 🧪 Testing

See **TESTING_GUIDE.md** for comprehensive testing instructions.

**Quick Test:**
1. Login with test credentials
2. Create a strategy
3. Add a Tradovate account (optional)
4. Test Control Center manual trading

---

## 📝 Environment Variables

Create a `.env` file (optional):

```env
SECRET_KEY=your-secret-key
DISCORD_CLIENT_ID=your-discord-client-id
DISCORD_CLIENT_SECRET=your-discord-client-secret
DISCORD_BOT_TOKEN=your-discord-bot-token
```

See `.env.example` for template.

---

## 🐛 Troubleshooting

**Backend Issues:**
- Port 5000 in use? `lsof -i :5000` and kill process
- Missing dependencies? Run `./install_deps.sh`
- Import errors? Check Python version: `python3 --version` (need 3.8+)

**Frontend Issues:**
- Port 5173 in use? Vite will use next available port
- Missing dependencies? Run `npm install` in frontend directory
- Build errors? Check Node version: `node --version` (need 16+)

**Database Issues:**
- Database file created automatically on first run
- Reset database: Delete `trade_manager.db` and restart backend

---

## 📚 Documentation

- **COMPLETE_IMPLEMENTATION.md** - Full implementation details
- **TESTING_GUIDE.md** - Comprehensive testing guide
- **QUICK_START.md** - Quick start instructions
- **FINAL_STATUS.md** - Implementation status

---

## 🎉 Status: 100% Complete

✅ All backend endpoints implemented  
✅ All frontend pages built  
✅ All integrations complete  
✅ Ready for testing and deployment

---

## 📄 License

This is a replica/reverse-engineered version for educational purposes.

---

**Built with ❤️ for Just.Trades**
