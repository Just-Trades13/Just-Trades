# 🔒 RESTORE POINT: December 3, 2025

## This is a known-good stable state

### Quick Restore Commands

```bash
# Restore to this exact state
git checkout stable-dec3-2025

# Or restore just the code while keeping current database
git checkout stable-dec3-2025 -- ultra_simple_server.py templates/ phantom_scraper/

# Restore database backup
cp backups/just_trades_dec3_2025.db just_trades.db
```

### Git Information
- **Tag:** `stable-dec3-2025`
- **Commit:** c803a6f
- **Branch:** main

### What's Working

| Feature | Status |
|---------|--------|
| Dashboard | ✅ Working |
| Market Heatmap | ✅ Fixed (Yahoo/Finnhub) |
| Account Management | ✅ Working |
| Manual Trader | ✅ Working |
| Live Positions/PnL | ✅ WebSocket working |
| OCO Tracking | ✅ Fixed + Orphan cleanup |
| Trailing Stops | ✅ Working |
| Break-Even Monitor | ✅ Working |
| TradingView Webhooks | ✅ Working |
| Risk Management (TP/SL) | ✅ Working |

### Key Files (Don't Modify Without Backup)

1. **ultra_simple_server.py** - Main Flask server
2. **phantom_scraper/tradovate_integration.py** - Tradovate API
3. **templates/dashboard.html** - Dashboard UI
4. **templates/manual_copy_trader.html** - Manual Trader UI
5. **templates/account_management.html** - Account Management UI
6. **just_trades.db** - Main database

### Database Backup Location
```
backups/just_trades_dec3_2025.db
```

### Recent Fixes Included

1. **Market Heatmap** - Fixed to use `chartPreviousClose` from Yahoo Finance
2. **PnL Cache** - Capped rate limit backoff at 30 seconds max
3. **OCO Tracking** - Added orphaned order cleanup on server restart

### How to Start Server

```bash
cd "/Users/mylesjadwin/Trading Projects"
python3 ultra_simple_server.py
```

Server runs on: http://localhost:8082

### If Something Breaks

1. Stop the server: `pkill -f "python3 ultra_simple_server.py"`
2. Restore code: `git checkout stable-dec3-2025`
3. Restore database: `cp backups/just_trades_dec3_2025.db just_trades.db`
4. Restart server: `python3 ultra_simple_server.py`

---
*Created: December 3, 2025*
*Last tested: December 3, 2025 - All features verified working*
