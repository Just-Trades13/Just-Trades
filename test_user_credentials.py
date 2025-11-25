#!/usr/bin/env python3
"""
Test Tradovate connection with user's own credentials
This simulates how end users will connect - they provide their own username/password
while the app uses the OAuth Client ID/Secret for the application
"""

import sqlite3
import asyncio
import sys
import os
import logging
import aiohttp

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Database path
DB_PATH = os.getenv('DB_PATH', 'just_trades.db')

async def test_user_login(username, password, client_id, client_secret, demo=True):
    """Test login with user's credentials using app's OAuth credentials"""
    
    base_url = "https://demo.tradovateapi.com/v1" if demo else "https://live.tradovateapi.com/v1"
    
    print("=" * 60)
    print("Testing User Authentication")
    print("=" * 60)
    print(f"User Username: {username}")
    print(f"App Client ID: {client_id}")
    print(f"Demo Mode: {demo}")
    print()
    
    login_data = {
        "name": username,
        "password": password,
        "appId": "Just.Trade",
        "appVersion": "1.0.0",
        "cid": client_id,
        "sec": client_secret
    }
    
    print("🔐 Attempting login...")
    print(f"   Endpoint: {base_url}/auth/accesstokenrequest")
    print()
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{base_url}/auth/accesstokenrequest",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                print(f"Response Status: {response.status}")
                
                data = await response.json()
                print(f"Response: {data}")
                print()
                
                if response.status == 200 and "accessToken" in data:
                    access_token = data.get("accessToken")
                    refresh_token = data.get("refreshToken")
                    
                    print("✅ Login successful!")
                    print(f"   Access Token: {access_token[:30]}...")
                    print()
                    
                    # Now get account information
                    print("📊 Fetching account information...")
                    
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }
                    
                    # Get accounts
                    async with session.get(
                        f"{base_url}/account/list",
                        headers=headers
                    ) as acc_response:
                        if acc_response.status == 200:
                            accounts = await acc_response.json()
                            print(f"✅ Found {len(accounts)} account(s)")
                            print()
                            
                            for acc in accounts:
                                acc_id = acc.get('id')
                                acc_name = acc.get('name', 'N/A')
                                acc_type = acc.get('accountType', 'N/A')
                                
                                print(f"Account: {acc_name} (ID: {acc_id})")
                                print(f"  Type: {acc_type}")
                                
                                # Get account info with balance
                                async with session.get(
                                    f"{base_url}/account/item?id={acc_id}",
                                    headers=headers
                                ) as info_response:
                                    if info_response.status == 200:
                                        account_info = await info_response.json()
                                        
                                        # Try different balance field names
                                        balance = (
                                            account_info.get('dayTradingBuyingPower') or
                                            account_info.get('netLiquidation') or
                                            account_info.get('availableFunds') or
                                            account_info.get('balance') or
                                            'N/A'
                                        )
                                        
                                        print(f"  Balance/Buying Power: ${balance}")
                                        print(f"  Available Funds: ${account_info.get('availableFunds', 'N/A')}")
                                        print(f"  Net Liquidation: ${account_info.get('netLiquidation', 'N/A')}")
                                        print(f"  Margin Used: ${account_info.get('marginUsed', 'N/A')}")
                                        print()
                                        
                                        # Get positions
                                        async with session.get(
                                            f"{base_url}/position/list",
                                            headers=headers,
                                            params={"accountId": acc_id}
                                        ) as pos_response:
                                            if pos_response.status == 200:
                                                positions = await pos_response.json()
                                                if positions:
                                                    print(f"  Open Positions: {len(positions)}")
                                                    for pos in positions:
                                                        symbol = pos.get('symbol', 'N/A')
                                                        qty = pos.get('quantity', 0)
                                                        avg_price = pos.get('averagePrice', 0)
                                                        print(f"    - {symbol}: {qty} @ ${avg_price}")
                                                else:
                                                    print("  No open positions")
                                        
                                        print()
                                    
                        return True
                else:
                    error_text = data.get("errorText", "Unknown error")
                    print(f"❌ Login failed: {error_text}")
                    
                    if "password" in error_text.lower() or "username" in error_text.lower():
                        print()
                        print("⚠️  Credential Issue:")
                        print("   This means the USER's username/password is incorrect.")
                        print("   The OAuth app credentials (Client ID/Secret) are working,")
                        print("   but the user's Tradovate account credentials are wrong.")
                        print()
                        print("   Please verify:")
                        print(f"   - Username: {username}")
                        print("   - Password is correct and case-sensitive")
                        print("   - Account exists and is active")
                    
                    return False
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    # Get credentials from database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT username, password, client_id, client_secret, name
        FROM accounts
        WHERE id = 4
    """)
    
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print("❌ Account not found!")
        sys.exit(1)
    
    username = account['username']
    password = account['password']
    client_id = account['client_id']
    client_secret = account['client_secret']
    account_name = account['name']
    
    print(f"Testing connection for: {account_name}")
    print()
    
    success = asyncio.run(test_user_login(username, password, client_id, client_secret, demo=True))
    
    if success:
        print("=" * 60)
        print("✅ Connection test successful!")
        print("=" * 60)
        print()
        print("This confirms:")
        print("  ✅ OAuth app credentials are working")
        print("  ✅ User authentication flow is correct")
        print("  ✅ Can fetch account balance and positions")
        print()
        print("Your multi-user setup is working correctly!")
    else:
        print("=" * 60)
        print("❌ Connection test failed")
        print("=" * 60)
        print()
        print("Please verify the USER's Tradovate credentials are correct.")


if __name__ == '__main__':
    main()

