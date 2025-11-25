# Phase 1 Backend Testing Guide

## Quick Test Results

✅ **All 12 automated tests passed!**

The test script (`test_phase1.py`) verified:
- Database connection
- All 8 tables exist
- Can create all model types (User, Account, Strategy, Trader, Trade, RecordedPosition, StrategyLog, WebhookLog)
- All relationships work correctly
- Queries and filters work

---

## Testing Methods

### Method 1: Automated Test Suite (Recommended)

Run the comprehensive test script:

```bash
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3 test_phase1.py
```

**What it tests:**
- ✅ Database connection
- ✅ All 8 tables exist
- ✅ Create User
- ✅ Create Account (with OAuth fields)
- ✅ Create Strategy (with all new fields)
- ✅ Create Trader
- ✅ Create Trade
- ✅ Create Recorded Position
- ✅ Create Strategy Log
- ✅ Create Webhook Log
- ✅ Test Relationships (User→Strategies, Account→Strategies, etc.)
- ✅ Test Queries (counts, filters)

**Expected Output:** All 12 tests should pass ✅

---

### Method 2: Manual Database Inspection

Check the database directly:

```bash
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3 -c "
from app.database import engine
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()

print('📊 Database Tables:')
for table in sorted(tables):
    if table != 'alembic_version':
        print(f'  ✅ {table}')
        
        # Show columns
        columns = inspector.get_columns(table)
        print(f'     Columns: {len(columns)}')
        for col in columns[:3]:  # Show first 3
            print(f'       - {col[\"name\"]}: {col[\"type\"]}')
        if len(columns) > 3:
            print(f'       ... and {len(columns) - 3} more')
        print()
"
```

---

### Method 3: Create Sample Data Manually

Create a simple test script to add real data:

```bash
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3
```

Then in Python:

```python
from app.database import SessionLocal
from app.models import User, Account, Strategy, RecordedPosition
from datetime import datetime

db = SessionLocal()

# Create a user
user = User(
    username="demo_user",
    email="demo@just.trades",
    password_hash="hashed_password_123"
)
db.add(user)
db.commit()
print(f"✅ Created user: {user.username} (ID: {user.id})")

# Create an account
account = Account(
    user_id=user.id,
    name="Demo Trading Account",
    broker="Tradovate",
    auth_type="credentials",
    username="demo_trader",
    account_id="DEMO123",
    environment="demo",
    client_id="demo_client_id",
    client_secret="demo_secret",
    enabled=True
)
db.add(account)
db.commit()
print(f"✅ Created account: {account.name} (ID: {account.id})")

# Create a strategy
strategy = Strategy(
    user_id=user.id,
    account_id=account.id,
    demo_account_id=account.id,
    name="DEMO_STRATEGY",
    symbol="ES",
    position_size=1,
    take_profit=22.0,
    stop_loss=50.0,
    recording_enabled=True,
    active=True
)
db.add(strategy)
db.commit()
print(f"✅ Created strategy: {strategy.name} (ID: {strategy.id})")

# Create a recorded position
position = RecordedPosition(
    strategy_id=strategy.id,
    account_id=account.id,
    symbol="ES",
    side="Buy",
    quantity=1,
    entry_price=4200.00,
    entry_timestamp=datetime.now(),
    status="open"
)
db.add(position)
db.commit()
print(f"✅ Created recorded position: {position.symbol} @ {position.entry_price}")

# Query to verify
print("\n📊 Verification:")
print(f"  Users: {db.query(User).count()}")
print(f"  Accounts: {db.query(Account).count()}")
print(f"  Strategies: {db.query(Strategy).count()}")
print(f"  Recorded Positions: {db.query(RecordedPosition).count()}")

db.close()
```

---

### Method 4: Test API Endpoints

Test the dashboard API endpoints we created:

#### Test Users Endpoint
```bash
curl http://localhost:8082/api/dashboard/users
```

Expected: JSON with list of users

#### Test Strategies Endpoint
```bash
curl http://localhost:8082/api/dashboard/strategies
```

Expected: JSON with list of strategies

#### Test Chart Data Endpoint
```bash
curl "http://localhost:8082/api/dashboard/chart-data"
```

Expected: JSON with `labels`, `profit`, `drawdown` arrays

#### Test Trade History Endpoint
```bash
curl "http://localhost:8082/api/dashboard/trade-history"
```

Expected: JSON with `trades` array

#### Test Metrics Endpoint
```bash
curl "http://localhost:8082/api/dashboard/metrics"
```

Expected: JSON with `metrics` object containing all calculated stats

---

### Method 5: Test with Filters

Test that filters work correctly:

```bash
# Test with user filter (if you have user ID 1)
curl "http://localhost:8082/api/dashboard/chart-data?user_id=1"

# Test with strategy filter
curl "http://localhost:8082/api/dashboard/chart-data?strategy_id=1"

# Test with symbol filter
curl "http://localhost:8082/api/dashboard/chart-data?symbol=ES"

# Test with timeframe filter
curl "http://localhost:8082/api/dashboard/chart-data?timeframe=month"
```

---

## Database File Location

The database is stored at:
```
/Users/mylesjadwin/Trading Projects/just_trades.db
```

You can inspect it directly with:
```bash
sqlite3 just_trades.db
```

Then run SQL commands:
```sql
.tables                    -- List all tables
.schema users              -- Show users table structure
SELECT * FROM users;       -- Show all users
SELECT * FROM strategies;  -- Show all strategies
.exit                      -- Exit
```

---

## What Phase 1 Includes

### ✅ Database Tables (8 total)
1. **users** - User accounts and Discord integration
2. **accounts** - Trading accounts (Tradovate) with OAuth
3. **strategies** - Trading strategies/recorders
4. **traders** - Strategy-account assignments
5. **trades** - Executed trades
6. **recorded_positions** - Demo position tracking
7. **strategy_logs** - Strategy event logs
8. **webhook_logs** - TradingView webhook logs

### ✅ Key Features
- All relationships working (User→Strategies, Account→Strategies, etc.)
- OAuth fields in accounts table
- Recording fields in strategies table
- JSON fields for complex data
- Timestamps auto-updating

---

## Quick Verification Checklist

- [ ] Run `test_phase1.py` - all tests pass
- [ ] Check database file exists: `just_trades.db`
- [ ] Verify tables exist (8 tables)
- [ ] Test creating a user manually
- [ ] Test creating a strategy manually
- [ ] Test API endpoints return data
- [ ] Test filters work on API endpoints

---

## Next Steps

Once Phase 1 is confirmed working:
- **Phase 2**: User Authentication & Sessions
- **Phase 3**: API Endpoints (Core CRUD)
- **Phase 4**: Webhook Handler (TradingView integration)

---

## Troubleshooting

**If tests fail:**
1. Make sure virtual environment is activated: `source venv/bin/activate`
2. Check database exists: `ls -la just_trades.db`
3. Reinitialize database: `python3 init_database.py`
4. Check for import errors in console output

**If API endpoints return errors:**
1. Make sure Flask server is running: `python3 ultra_simple_server.py --port 8082`
2. Check server logs: `tail -f flask_output.log`
3. Verify database connection in server logs

