# Port Change Notice

## ⚠️ Important: Backend Port Changed

**Port 5000 is occupied by macOS AirPlay Receiver!**

The backend has been changed to use **port 5001** instead.

### Updated Configuration:

- **Backend:** http://localhost:5001
- **WebSocket:** ws://localhost:5001
- **Frontend:** http://localhost:5173 (unchanged)

### To Use:

1. **Restart the backend** - it will now use port 5001
2. **Frontend is already updated** - it will connect to port 5001

### If you want to use a different port:

Set environment variable:
```bash
export PORT=8000
python3 app.py
```

Or update `frontend/src/services/api.js` and `frontend/vite.config.js` to match.

