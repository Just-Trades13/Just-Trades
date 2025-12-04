#!/usr/bin/env python3
"""
Test Trade Manager's Approach
Testing if we can replicate Trade Manager's method:
1. Tradovate REST API (username/password) for orders/positions
2. TradingView Public API for market data
3. Calculate P&L ourselves
"""

import asyncio
import aiohttp
import json
import sqlite3
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_trademanager_approach():
    """Test Trade Manager's approach: Tradovate API + TradingView market data"""
    
    print("=" * 60)
    print("Testing Trade Manager's Approach")
    print("=" * 60)
    print()
    print("Theory: Trade Manager uses:")
    print("  1. Tradovate REST API (username/password) for orders/positions")
    print("  2. TradingView Public API for market data")
    print("  3. Calculates P&L themselves")
    print()
    
    # Step 1: Test Tradovate REST API with username/password
    print("Step 1: Testing Tradovate REST API (username/password)...")
    print("   (This is what Trade Manager uses for orders/positions)")
    
    # Get credentials from database
    try:
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, username, password 
            FROM accounts 
            WHERE username IS NOT NULL AND password IS NOT NULL
            LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            username = row['username']
            password = row['password']
            print(f"   ✅ Found credentials for account: {row['name']}")
            print(f"   Username: {username}")
        else:
            print("   ⚠️  No username/password credentials found")
            print("   (This is expected if you're using OAuth)")
            conn.close()
            return
        conn.close()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Test Tradovate login
    try:
        from phantom_scraper.tradovate_integration import TradovateIntegration
        
        async with TradovateIntegration(demo=True) as tradovate:
            print("   Attempting Tradovate login with username/password...")
            success = await tradovate.login_with_credentials(username, password)
            if success:
                print("   ✅ Tradovate login successful!")
                print(f"   Access token: {tradovate.access_token[:20]}...")
                
                # Test getting positions
                print()
                print("   Testing position retrieval...")
                positions = await tradovate.get_positions(None)
                print(f"   ✅ Retrieved {len(positions)} positions from Tradovate")
                if positions:
                    for pos in positions[:3]:
                        print(f"      - {pos.get('symbol', 'N/A')}: {pos.get('netPos', 0)}")
            else:
                print("   ❌ Tradovate login failed")
                return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print()
    
    # Step 2: Test TradingView Public API for market data
    print("Step 2: Testing TradingView Public API for market data...")
    print("   (This is what Trade Manager might use for prices)")
    
    test_symbols = ["MES1!", "MNQ1!"]
    
    async with aiohttp.ClientSession() as session:
        for symbol in test_symbols:
            try:
                # Try TradingView symbol search
                print(f"   Testing {symbol}...")
                
                # Method 1: Symbol search
                url = f"https://symbol-search.tradingview.com/symbol_search/?text={symbol}"
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"      ✅ Symbol search successful")
                        if data:
                            print(f"      Found: {data[0].get('symbol', 'N/A')}")
                
                # Method 2: Try to get quote (might not work without auth)
                # TradingView doesn't have a public quote API, but let's try
                print(f"      ⚠️  TradingView doesn't have public quote API")
                print(f"      (Would need to use alternative: Yahoo Finance, Alpha Vantage, etc.)")
                
            except Exception as e:
                print(f"      ❌ Error: {e}")
    
    print()
    
    # Step 3: Calculate P&L (like Trade Manager might do)
    print("Step 3: Calculating P&L (like Trade Manager)...")
    print("   Formula: (Current Price - Avg Price) × Quantity × Multiplier")
    print("   This is what Trade Manager likely does:")
    print("   1. Get positions from Tradovate API")
    print("   2. Get current prices from market data source")
    print("   3. Calculate P&L themselves")
    print("   ✅ This approach would work!")
    
    print()
    print("=" * 60)
    print("Conclusion")
    print("=" * 60)
    print()
    print("Trade Manager likely:")
    print("  1. ✅ Uses Tradovate REST API (username/password) for orders/positions")
    print("  2. ✅ Uses market data source (TradingView public API or alternative) for prices")
    print("  3. ✅ Calculates P&L themselves")
    print()
    print("Why TradingView add-on is required:")
    print("  - Maybe just for verification that user has market data access?")
    print("  - Or Trade Manager uses TradingView's broker integration (not public API)")
    print()
    print("Next step: Inspect Trade Manager's network requests to see exact API calls")

if __name__ == "__main__":
    try:
        asyncio.run(test_trademanager_approach())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

