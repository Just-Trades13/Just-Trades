#!/usr/bin/env python3
"""
Populate database with test users and strategies
Based on Trade Manager screenshots
"""

import sys
import os
from datetime import datetime, timedelta
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import User, Account, Strategy, RecordedPosition, Trade

def create_test_data():
    """Create test users, accounts, strategies, and sample trades"""
    db = SessionLocal()
    
    try:
        print("=" * 60)
        print("POPULATING TEST DATA")
        print("=" * 60)
        print()
        
        # Create test users
        users_data = [
            {'username': 'testuser1', 'email': 'testuser1@just.trades'},
            {'username': 'testuser2', 'email': 'testuser2@just.trades'},
            {'username': 'testuser3', 'email': 'testuser3@just.trades'},
        ]
        
        users = []
        for user_data in users_data:
            # Check if user exists
            existing = db.query(User).filter(User.username == user_data['username']).first()
            if existing:
                print(f"⚠️  User {user_data['username']} already exists, skipping...")
                users.append(existing)
                continue
            
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                password_hash=f"hashed_{user_data['username']}_123"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            users.append(user)
            print(f"✅ Created user: {user.username} (ID: {user.id})")
        
        print()
        
        # Create accounts for each user
        accounts = []
        for user in users:
            # Demo account
            demo_account = Account(
                user_id=user.id,
                name=f"{user.username} Demo Account",
                broker="Tradovate",
                auth_type="credentials",
                username=f"{user.username}_demo",
                account_id=f"DEMO{random.randint(100000, 999999)}",
                environment="demo",
                client_id=f"client_{user.username}",
                client_secret=f"secret_{user.username}",
                enabled=True,
                max_contracts=5,
                multiplier=1.0
            )
            db.add(demo_account)
            db.commit()
            db.refresh(demo_account)
            accounts.append(demo_account)
            print(f"✅ Created demo account for {user.username}: {demo_account.name} (ID: {demo_account.id})")
        
        print()
        
        # Strategies from screenshots
        strategies_data = [
            # testuser1 strategies
            {'name': 'JADDCAVIX', 'symbol': 'MNQ', 'user_index': 0},
            {'name': 'JADDCAVIXES', 'symbol': 'ES', 'user_index': 0},
            {'name': 'JADES', 'symbol': 'ES', 'user_index': 0},
            {'name': 'JADIND50', 'symbol': 'MNQ', 'user_index': 0},
            {'name': 'JADNQ', 'symbol': 'NQ', 'user_index': 0},
            
            # testuser2 strategies
            {'name': 'STRATEGY_A', 'symbol': 'ES', 'user_index': 1},
            {'name': 'STRATEGY_B', 'symbol': 'NQ', 'user_index': 1},
            
            # testuser3 strategies
            {'name': 'STRATEGY_X', 'symbol': 'ES', 'user_index': 2},
            {'name': 'STRATEGY_Y', 'symbol': 'MNQ', 'user_index': 2},
        ]
        
        strategies = []
        for strat_data in strategies_data:
            user = users[strat_data['user_index']]
            account = accounts[strat_data['user_index']]
            
            strategy = Strategy(
                user_id=user.id,
                account_id=account.id,
                demo_account_id=account.id,
                name=strat_data['name'],
                symbol=strat_data['symbol'],
                position_size=random.randint(1, 4),
                position_add=1,
                take_profit=random.choice([20, 22, 25, 30]),
                stop_loss=random.choice([40, 50, 60]),
                tpsl_units="Ticks",
                recording_enabled=True,
                delay_seconds=random.randint(0, 5),
                max_contracts=random.randint(2, 5),
                premium_filter=random.choice([True, False]),
                direction_filter="both",
                time_filter_enabled=True,
                time_filter_start="09:30",
                time_filter_end="16:00",
                entry_delay=random.randint(0, 3),
                signal_cooldown=random.randint(30, 120),
                max_signals_per_session=random.randint(10, 20),
                max_daily_loss=random.choice([500, 1000, 1500]),
                auto_flat=False,
                active=True
            )
            db.add(strategy)
            db.commit()
            db.refresh(strategy)
            strategies.append(strategy)
            print(f"✅ Created strategy: {strategy.name} for {user.username} (ID: {strategy.id})")
        
        print()
        
        # Create sample recorded positions (trades) for the strategies
        print("Creating sample trades...")
        
        # Base prices for different symbols
        base_prices = {
            'ES': 6870.0,
            'NQ': 25500.0,
            'MNQ': 25500.0
        }
        
        # Generate trades for the last 30 days
        trade_count = 0
        for strategy in strategies:
            symbol = strategy.symbol
            base_price = base_prices.get(symbol, 1000.0)
            
            # Generate 5-15 trades per strategy
            num_trades = random.randint(5, 15)
            
            for i in range(num_trades):
                # Random date in last 30 days
                days_ago = random.randint(0, 30)
                entry_time = datetime.now() - timedelta(days=days_ago, hours=random.randint(9, 15), minutes=random.randint(0, 59))
                
                # Random entry price around base
                entry_price = base_price + random.uniform(-50, 50)
                
                # Random side
                side = random.choice(['Buy', 'Sell'])
                
                # Random quantity
                quantity = random.choice([1, 2, 4])
                
                # Calculate exit (win or loss)
                is_win = random.random() > 0.3  # 70% win rate
                if is_win:
                    # Win: exit price moves in favor
                    if side == 'Buy':
                        exit_price = entry_price + random.uniform(5, 30)
                    else:
                        exit_price = entry_price - random.uniform(5, 30)
                else:
                    # Loss: exit price moves against
                    if side == 'Buy':
                        exit_price = entry_price - random.uniform(5, 30)
                    else:
                        exit_price = entry_price + random.uniform(5, 30)
                
                # Calculate P&L (simplified)
                if side == 'Buy':
                    pnl = (exit_price - entry_price) * quantity * 50  # ES/NQ multiplier
                else:
                    pnl = (entry_price - exit_price) * quantity * 50
                
                # Round to 2 decimals
                pnl = round(pnl, 2)
                
                exit_time = entry_time + timedelta(minutes=random.randint(2, 30))
                
                position = RecordedPosition(
                    strategy_id=strategy.id,
                    account_id=strategy.account_id,
                    symbol=f"{symbol}1!",
                    side=side,
                    quantity=quantity,
                    entry_price=round(entry_price, 2),
                    entry_timestamp=entry_time,
                    exit_price=round(exit_price, 2),
                    exit_timestamp=exit_time,
                    exit_reason='Take Profit' if is_win else 'Stop Loss',
                    pnl=pnl,
                    pnl_percent=round((pnl / (entry_price * quantity * 50)) * 100, 2) if entry_price > 0 else 0,
                    status='closed',
                    stop_loss_price=round(entry_price - (30 if side == 'Buy' else -30), 2),
                    take_profit_price=round(entry_price + (25 if side == 'Buy' else -25), 2)
                )
                db.add(position)
                trade_count += 1
        
        db.commit()
        print(f"✅ Created {trade_count} recorded positions (trades)")
        print()
        
        # Summary
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Users: {len(users)}")
        print(f"Accounts: {len(accounts)}")
        print(f"Strategies: {len(strategies)}")
        print(f"Recorded Positions: {trade_count}")
        print()
        
        # Show strategies per user
        for user in users:
            user_strategies = [s for s in strategies if s.user_id == user.id]
            print(f"{user.username}: {len(user_strategies)} strategies")
            for strat in user_strategies:
                positions = db.query(RecordedPosition).filter(RecordedPosition.strategy_id == strat.id).count()
                print(f"  - {strat.name} ({strat.symbol}): {positions} trades")
        
        print()
        print("✅ Test data populated successfully!")
        print()
        print("You can now:")
        print("  1. Refresh http://localhost:8082/dashboard")
        print("  2. Select users/strategies from the filter dropdowns")
        print("  3. See data in the chart and trade history")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    create_test_data()

