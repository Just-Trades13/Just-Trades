#!/usr/bin/env python3
"""
Quick Phase 1 Test - Simple verification script
Run this to quickly verify Phase 1 is working
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import User, Account, Strategy, RecordedPosition
from sqlalchemy import inspect
from datetime import datetime

print("=" * 60)
print("QUICK PHASE 1 VERIFICATION")
print("=" * 60)
print()

# Test 1: Check tables
print("1️⃣  Checking database tables...")
inspector = inspect(engine)
tables = inspector.get_table_names()
expected = ['users', 'accounts', 'strategies', 'traders', 'trades', 
            'recorded_positions', 'strategy_logs', 'webhook_logs']
missing = [t for t in expected if t not in tables]
if missing:
    print(f"   ❌ Missing tables: {missing}")
    sys.exit(1)
print(f"   ✅ All {len(expected)} tables exist")
print()

# Test 2: Check we can query
print("2️⃣  Testing database queries...")
db = SessionLocal()
try:
    user_count = db.query(User).count()
    account_count = db.query(Account).count()
    strategy_count = db.query(Strategy).count()
    position_count = db.query(RecordedPosition).count()
    
    print(f"   ✅ Users: {user_count}")
    print(f"   ✅ Accounts: {account_count}")
    print(f"   ✅ Strategies: {strategy_count}")
    print(f"   ✅ Recorded Positions: {position_count}")
except Exception as e:
    print(f"   ❌ Query failed: {e}")
    sys.exit(1)
finally:
    db.close()
print()

# Test 3: Create and delete test record
print("3️⃣  Testing create/delete operations...")
db = SessionLocal()
try:
    # Create test user
    test_user = User(
        username="quick_test_user",
        email="quicktest@just.trades",
        password_hash="test_hash"
    )
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    print(f"   ✅ Created test user: {test_user.username} (ID: {test_user.id})")
    
    # Delete test user
    db.delete(test_user)
    db.commit()
    print(f"   ✅ Deleted test user")
except Exception as e:
    print(f"   ❌ Create/delete failed: {e}")
    db.rollback()
    sys.exit(1)
finally:
    db.close()
print()

print("=" * 60)
print("✅ PHASE 1 VERIFICATION COMPLETE!")
print("=" * 60)
print()
print("All basic operations working correctly.")
print("Ready to proceed to Phase 2!")

