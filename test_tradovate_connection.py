#!/usr/bin/env python3
"""
Test Tradovate connection and fetch account balance
"""

import sqlite3
import asyncio
import sys
import os
import logging

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import Tradovate integration
try:
    # Try different import paths
    try:
        from phantom_scraper.tradovate_integration import TradovateIntegration
    except ImportError:
        # Try direct import
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'phantom_scraper'))
        from tradovate_integration import TradovateIntegration
    TRADOVATE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Tradovate integration not found: {e}")
    print("Make sure phantom_scraper/tradovate_integration.py exists")
    sys.exit(1)

# Database path
DB_PATH = os.getenv('DB_PATH', 'just_trades.db')

async def test_connection(account_id):
    """Test Tradovate connection and get account info"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get account credentials
    cursor.execute("""
        SELECT username, password, client_id, client_secret,
               tradovate_token, tradovate_refresh_token, name
        FROM accounts
        WHERE id = ? AND enabled = 1
    """, (account_id,))
    
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print(f"❌ Account {account_id} not found or disabled")
        return False
    
    username = account['username']
    password = account['password']
    client_id = account['client_id']
    client_secret = account['client_secret']
    account_name = account['name']
    token = account['tradovate_token']
    refresh_token = account['tradovate_refresh_token']
    
    print("=" * 60)
    print(f"Testing Tradovate Connection for: {account_name}")
    print("=" * 60)
    print(f"Username: {username}")
    print(f"Client ID: {client_id}")
    print()
    
    try:
        # Try demo first since this is a demo account
        print("🔐 Attempting to login to DEMO...")
        print(f"   Username: {username}")
        print(f"   Client ID: {client_id}")
        print(f"   Client Secret: {client_secret[:10]}...")
        print()
        
        async with TradovateIntegration(demo=True) as tradovate:
            # Force demo endpoint
            tradovate.base_url = "https://demo.tradovateapi.com/v1"
            
            # Try login with demo endpoint directly
            import aiohttp
            login_data = {
                "name": username,
                "password": password,
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
                "cid": client_id,
                "sec": client_secret
            }
            
            print("Sending login request to demo endpoint...")
            async with tradovate.session.post(
                "https://demo.tradovateapi.com/v1/auth/accesstokenrequest",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                print(f"Response status: {response.status}")
                data = await response.json()
                print(f"Response data: {data}")
                
                if response.status == 200 and "accessToken" in data:
                    tradovate.access_token = data.get("accessToken")
                    tradovate.refresh_token = data.get("refreshToken")
                    print("✅ Login successful!")
                else:
                    error_text = data.get("errorText", "Unknown error")
                    print(f"❌ Login failed: {error_text}")
                    if "password" in error_text.lower():
                        print("\n⚠️  Password issue detected. Please verify:")
                        print("   - Password is correct and case-sensitive")
                        print("   - No extra spaces or characters")
                        print("   - Special characters are correct")
                    return False
            
            login_result = tradovate.access_token is not None
            
            if not login_result:
                print("❌ Login failed!")
                print("Please check:")
                print("  - Username and password are correct")
                print("  - Client ID and Secret are correct")
                print("  - OAuth app has proper permissions")
                print()
                print("Debug info:")
                print(f"  Access token received: {tradovate.access_token is not None}")
                if tradovate.access_token:
                    print(f"  Token (first 20 chars): {tradovate.access_token[:20]}...")
                return False
            
            print("✅ Login successful!")
            print()
            
            # Get accounts list
            print("📋 Fetching account list...")
            accounts = await tradovate.get_accounts()
            
            if not accounts:
                print("❌ No accounts found")
                return False
            
            print(f"✅ Found {len(accounts)} account(s)")
            print()
            
            # Display account information
            print("=" * 60)
            print("Account Information:")
            print("=" * 60)
            
            for acc in accounts:
                print(f"\nAccount Name: {acc.get('name', 'N/A')}")
                print(f"Account ID: {acc.get('id', 'N/A')}")
                print(f"Account Type: {acc.get('accountType', 'N/A')}")
                print(f"Active: {acc.get('active', 'N/A')}")
                
                # Get detailed account info
                account_id_str = str(acc.get('id', ''))
                if account_id_str:
                    print(f"\n📊 Fetching detailed account info for {account_id_str}...")
                    account_info = await tradovate.get_account_info(account_id_str)
                    
                    if account_info:
                        print("\nAccount Details:")
                        print(f"  Balance: ${account_info.get('dayTradingBuyingPower', account_info.get('netLiquidation', 'N/A'))}")
                        print(f"  Net Liquidation: ${account_info.get('netLiquidation', 'N/A')}")
                        print(f"  Day Trading Buying Power: ${account_info.get('dayTradingBuyingPower', 'N/A')}")
                        print(f"  Available Funds: ${account_info.get('availableFunds', 'N/A')}")
                        print(f"  Margin Used: ${account_info.get('marginUsed', 'N/A')}")
                        print(f"  Open P&L: ${account_info.get('openPnL', 'N/A')}")
                        
                        # Get positions
                        print(f"\n📈 Fetching positions...")
                        positions = await tradovate.get_positions(account_id_str)
                        
                        if positions:
                            print(f"  Open Positions: {len(positions)}")
                            for pos in positions:
                                symbol = pos.get('symbol', 'N/A')
                                quantity = pos.get('quantity', 0)
                                avg_price = pos.get('averagePrice', 0)
                                print(f"    - {symbol}: {quantity} @ ${avg_price}")
                        else:
                            print("  No open positions")
            
            print()
            print("=" * 60)
            print("✅ Connection test successful!")
            print("=" * 60)
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    # Get account ID from command line or use default
    if len(sys.argv) > 1:
        account_id = int(sys.argv[1])
    else:
        # Use the test account we just created
        account_id = 4
    
    print(f"Testing connection for Account ID: {account_id}")
    print()
    
    success = asyncio.run(test_connection(account_id))
    
    if success:
        print("\n✅ All tests passed! Connection is working.")
        sys.exit(0)
    else:
        print("\n❌ Connection test failed. Please check the errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()

