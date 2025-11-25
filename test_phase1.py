#!/usr/bin/env python3
"""
Phase 1 Testing Script
Tests all database models, relationships, and operations
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.database import SessionLocal, init_db, engine
    from app.models import (
        User, Account, Strategy, Trader, Trade, 
        RecordedPosition, StrategyLog, WebhookLog
    )
    from sqlalchemy import inspect
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_database_connection():
    """Test 1: Database connection"""
    print("\n" + "="*60)
    print("TEST 1: Database Connection")
    print("="*60)
    try:
        # Test engine connection
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_tables_exist():
    """Test 2: Verify all tables exist"""
    print("\n" + "="*60)
    print("TEST 2: Tables Existence")
    print("="*60)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected_tables = [
            'users', 'accounts', 'strategies', 'traders', 
            'trades', 'recorded_positions', 'strategy_logs', 'webhook_logs'
        ]
        
        missing = [t for t in expected_tables if t not in tables]
        if missing:
            print(f"❌ Missing tables: {missing}")
            return False
        
        print(f"✅ All {len(expected_tables)} tables exist")
        for table in expected_tables:
            print(f"   ✓ {table}")
        return True
    except Exception as e:
        print(f"❌ Table check failed: {e}")
        return False

def test_create_user():
    """Test 3: Create a user"""
    print("\n" + "="*60)
    print("TEST 3: Create User")
    print("="*60)
    db = SessionLocal()
    try:
        # Check if test user exists
        existing = db.query(User).filter(User.username == "testuser").first()
        if existing:
            db.delete(existing)
            db.commit()
        
        # Create new user
        user = User(
            username="testuser",
            email="test@just.trades",
            password_hash="hashed_password_here",
            discord_dms_enabled=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print(f"✅ User created: ID={user.id}, Username={user.username}")
        return user
    except Exception as e:
        print(f"❌ User creation failed: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def test_create_account(user):
    """Test 4: Create an account"""
    print("\n" + "="*60)
    print("TEST 4: Create Account")
    print("="*60)
    db = SessionLocal()
    try:
        account = Account(
            user_id=user.id if user else None,
            name="Test Demo Account",
            broker="Tradovate",
            auth_type="credentials",
            username="demo_user",
            password="encrypted_password",
            account_id="DEMO123456",
            environment="demo",
            client_id="test_client_id",
            client_secret="test_client_secret",
            enabled=True,
            max_contracts=5,
            multiplier=1.0
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        
        print(f"✅ Account created: ID={account.id}, Name={account.name}")
        print(f"   - Broker: {account.broker}")
        print(f"   - Environment: {account.environment}")
        print(f"   - OAuth Client ID: {account.client_id}")
        return account
    except Exception as e:
        print(f"❌ Account creation failed: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def test_create_strategy(user, account):
    """Test 5: Create a strategy"""
    print("\n" + "="*60)
    print("TEST 5: Create Strategy")
    print("="*60)
    db = SessionLocal()
    try:
        strategy = Strategy(
            user_id=user.id if user else None,
            account_id=account.id if account else None,
            demo_account_id=account.id if account else None,
            name="TEST_STRATEGY",
            symbol="ES",
            position_size=1,
            position_add=1,
            take_profit=22.0,
            stop_loss=50.0,
            tpsl_units="Ticks",
            recording_enabled=True,
            delay_seconds=5,
            max_contracts=3,
            premium_filter=True,
            direction_filter="both",
            time_filter_enabled=True,
            time_filter_start="09:30",
            time_filter_end="16:00",
            entry_delay=2,
            signal_cooldown=60,
            max_signals_per_session=10,
            max_daily_loss=500.0,
            auto_flat=False,
            active=True,
            positional_settings={
                "tp_levels": [22, 44, 66],
                "trailing_stop": False
            }
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        
        print(f"✅ Strategy created: ID={strategy.id}, Name={strategy.name}")
        print(f"   - Symbol: {strategy.symbol}")
        print(f"   - Recording Enabled: {strategy.recording_enabled}")
        print(f"   - Position Size: {strategy.position_size}")
        print(f"   - TP: {strategy.take_profit}, SL: {strategy.stop_loss}")
        return strategy
    except Exception as e:
        print(f"❌ Strategy creation failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return None
    finally:
        db.close()

def test_create_trader(user, strategy, account):
    """Test 6: Create a trader"""
    print("\n" + "="*60)
    print("TEST 6: Create Trader")
    print("="*60)
    db = SessionLocal()
    try:
        trader = Trader(
            user_id=user.id if user else None,
            strategy_id=strategy.id if strategy else None,
            account_id=account.id if account else None,
            name="Test Trader",
            enabled=True,
            max_contracts=2,
            custom_ticker="ES",
            multiplier=1.5,
            stop_loss=45.0,
            take_profit=20.0
        )
        db.add(trader)
        db.commit()
        db.refresh(trader)
        
        print(f"✅ Trader created: ID={trader.id}, Name={trader.name}")
        print(f"   - Strategy ID: {trader.strategy_id}")
        print(f"   - Account ID: {trader.account_id}")
        print(f"   - Enabled: {trader.enabled}")
        return trader
    except Exception as e:
        print(f"❌ Trader creation failed: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def test_create_trade(account, strategy, trader):
    """Test 7: Create a trade"""
    print("\n" + "="*60)
    print("TEST 7: Create Trade")
    print("="*60)
    db = SessionLocal()
    try:
        trade = Trade(
            account_id=account.id if account else None,
            strategy_id=strategy.id if strategy else None,
            trader_id=trader.id if trader else None,
            symbol="ES",
            side="buy",
            quantity=1,
            price=4200.50,
            order_type="market",
            status="filled",
            entry_price=4200.50,
            webhook_payload={
                "strategy": "TEST_STRATEGY",
                "action": "buy",
                "contracts": 1
            }
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)
        
        print(f"✅ Trade created: ID={trade.id}")
        print(f"   - Symbol: {trade.symbol}, Side: {trade.side}")
        print(f"   - Quantity: {trade.quantity}, Price: {trade.price}")
        print(f"   - Status: {trade.status}")
        return trade
    except Exception as e:
        print(f"❌ Trade creation failed: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def test_create_recorded_position(strategy, account):
    """Test 8: Create a recorded position"""
    print("\n" + "="*60)
    print("TEST 8: Create Recorded Position")
    print("="*60)
    db = SessionLocal()
    try:
        position = RecordedPosition(
            strategy_id=strategy.id if strategy else None,
            account_id=account.id if account else None,
            symbol="ES",
            side="Buy",
            quantity=1,
            entry_price=4200.00,
            entry_timestamp=datetime.now(),
            stop_loss_price=4150.00,
            take_profit_price=4222.00,
            status="open",
            tradovate_order_id="ORD123456"
        )
        db.add(position)
        db.commit()
        db.refresh(position)
        
        print(f"✅ Recorded Position created: ID={position.id}")
        print(f"   - Symbol: {position.symbol}, Side: {position.side}")
        print(f"   - Entry Price: {position.entry_price}")
        print(f"   - Status: {position.status}")
        return position
    except Exception as e:
        print(f"❌ Recorded Position creation failed: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def test_create_strategy_log(strategy):
    """Test 9: Create a strategy log"""
    print("\n" + "="*60)
    print("TEST 9: Create Strategy Log")
    print("="*60)
    db = SessionLocal()
    try:
        log = StrategyLog(
            strategy_id=strategy.id if strategy else None,
            log_type="entry",
            message="Position opened: Long 1 ES @ 4200.00",
            data={
                "symbol": "ES",
                "side": "buy",
                "quantity": 1,
                "price": 4200.00
            }
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        
        print(f"✅ Strategy Log created: ID={log.id}")
        print(f"   - Type: {log.log_type}")
        print(f"   - Message: {log.message[:50]}...")
        return log
    except Exception as e:
        print(f"❌ Strategy Log creation failed: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def test_create_webhook_log(strategy):
    """Test 10: Create a webhook log"""
    print("\n" + "="*60)
    print("TEST 10: Create Webhook Log")
    print("="*60)
    db = SessionLocal()
    try:
        webhook_data = {
            "strategy": "TEST_STRATEGY",
            "action": "buy",
            "contracts": 1,
            "symbol": "ES",
            "price": 4200.50
        }
        webhook = WebhookLog(
            strategy_id=strategy.id if strategy else None,
            webhook_data=json.dumps(webhook_data),
            processed=True
        )
        db.add(webhook)
        db.commit()
        db.refresh(webhook)
        
        print(f"✅ Webhook Log created: ID={webhook.id}")
        print(f"   - Processed: {webhook.processed}")
        print(f"   - Strategy ID: {webhook.strategy_id}")
        return webhook
    except Exception as e:
        print(f"❌ Webhook Log creation failed: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def test_relationships():
    """Test 11: Test relationships between models"""
    print("\n" + "="*60)
    print("TEST 11: Test Relationships")
    print("="*60)
    db = SessionLocal()
    try:
        # Test User -> Strategies relationship
        user = db.query(User).filter(User.username == "testuser").first()
        if user:
            print(f"✅ User found: {user.username}")
            print(f"   - Has {len(user.strategies)} strategy(ies)")
            print(f"   - Has {len(user.traders)} trader(s)")
        
        # Test Account -> Strategies relationship
        account = db.query(Account).filter(Account.name == "Test Demo Account").first()
        if account:
            print(f"✅ Account found: {account.name}")
            print(f"   - Has {len(account.strategies)} strategy(ies)")
            print(f"   - Has {len(account.traders)} trader(s)")
            print(f"   - Has {len(account.trades)} trade(s)")
        
        # Test Strategy -> Logs relationship
        strategy = db.query(Strategy).filter(Strategy.name == "TEST_STRATEGY").first()
        if strategy:
            print(f"✅ Strategy found: {strategy.name}")
            print(f"   - Has {len(strategy.strategy_logs)} log(s)")
            print(f"   - Has {len(strategy.recorded_positions)} recorded position(s)")
            print(f"   - Has {len(strategy.traders)} trader(s)")
        
        return True
    except Exception as e:
        print(f"❌ Relationship test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def test_queries():
    """Test 12: Test various queries"""
    print("\n" + "="*60)
    print("TEST 12: Test Queries")
    print("="*60)
    db = SessionLocal()
    try:
        # Count all records
        user_count = db.query(User).count()
        account_count = db.query(Account).count()
        strategy_count = db.query(Strategy).count()
        trader_count = db.query(Trader).count()
        trade_count = db.query(Trade).count()
        position_count = db.query(RecordedPosition).count()
        log_count = db.query(StrategyLog).count()
        webhook_count = db.query(WebhookLog).count()
        
        print("✅ Query counts:")
        print(f"   - Users: {user_count}")
        print(f"   - Accounts: {account_count}")
        print(f"   - Strategies: {strategy_count}")
        print(f"   - Traders: {trader_count}")
        print(f"   - Trades: {trade_count}")
        print(f"   - Recorded Positions: {position_count}")
        print(f"   - Strategy Logs: {log_count}")
        print(f"   - Webhook Logs: {webhook_count}")
        
        # Test filter queries
        active_strategies = db.query(Strategy).filter(Strategy.active == True).count()
        enabled_accounts = db.query(Account).filter(Account.enabled == True).count()
        open_positions = db.query(RecordedPosition).filter(RecordedPosition.status == 'open').count()
        
        print("\n✅ Filter queries:")
        print(f"   - Active Strategies: {active_strategies}")
        print(f"   - Enabled Accounts: {enabled_accounts}")
        print(f"   - Open Positions: {open_positions}")
        
        return True
    except Exception as e:
        print(f"❌ Query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

def cleanup_test_data():
    """Cleanup: Remove test data"""
    print("\n" + "="*60)
    print("CLEANUP: Removing Test Data")
    print("="*60)
    db = SessionLocal()
    try:
        # Delete in reverse order of dependencies
        db.query(WebhookLog).filter(WebhookLog.strategy_id != None).delete()
        db.query(StrategyLog).delete()
        db.query(RecordedPosition).delete()
        db.query(Trade).delete()
        db.query(Trader).delete()
        db.query(Strategy).delete()
        db.query(Account).delete()
        db.query(User).filter(User.username == "testuser").delete()
        db.commit()
        print("✅ Test data cleaned up")
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    """Run all tests"""
    print("="*60)
    print("PHASE 1 TESTING SUITE")
    print("="*60)
    
    results = []
    
    # Basic tests
    results.append(("Database Connection", test_database_connection()))
    results.append(("Tables Existence", test_tables_exist()))
    
    # Create tests
    user = test_create_user()
    results.append(("Create User", user is not None))
    
    account = test_create_account(user)
    results.append(("Create Account", account is not None))
    
    strategy = test_create_strategy(user, account)
    results.append(("Create Strategy", strategy is not None))
    
    trader = test_create_trader(user, strategy, account)
    results.append(("Create Trader", trader is not None))
    
    trade = test_create_trade(account, strategy, trader)
    results.append(("Create Trade", trade is not None))
    
    position = test_create_recorded_position(strategy, account)
    results.append(("Create Recorded Position", position is not None))
    
    log = test_create_strategy_log(strategy)
    results.append(("Create Strategy Log", log is not None))
    
    webhook = test_create_webhook_log(strategy)
    results.append(("Create Webhook Log", webhook is not None))
    
    # Relationship and query tests
    results.append(("Test Relationships", test_relationships()))
    results.append(("Test Queries", test_queries()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Phase 1 is working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review errors above.")
    
    # Ask about cleanup
    print("\n" + "="*60)
    # Auto-cleanup for non-interactive testing
    print("Auto-cleaning test data...")
    cleanup_test_data()

if __name__ == '__main__':
    import json
    main()

