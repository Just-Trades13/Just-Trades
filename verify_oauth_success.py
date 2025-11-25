#!/usr/bin/env python3
"""
Verify if OAuth flow worked and token was stored
"""

import sqlite3
import asyncio
import aiohttp
import sys

DB_PATH = 'just_trades.db'

async def test_token(account_id=4):
    """Test if stored token works"""
    
    # Get account from database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, username, tradovate_token, tradovate_refresh_token,
               token_expires_at
        FROM accounts
        WHERE id = ?
    """, (account_id,))
    
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print(f"❌ Account {account_id} not found")
        return False
    
    print("=" * 60)
    print("OAuth Token Verification")
    print("=" * 60)
    print()
    print(f"Account: {account['name']} (ID: {account['id']})")
    print(f"Username: {account['username']}")
    print()
    
    token = account['tradovate_token']
    refresh_token = account['tradovate_refresh_token']
    expires_at = account['token_expires_at']
    
    if not token:
        print("❌ No token stored")
        print()
        print("OAuth flow may not have completed successfully.")
        print("Try connecting again:")
        print("  http://localhost:8082/api/accounts/4/connect")
        return False
    
    print("✅ Token found in database!")
    print(f"   Token: {token[:50]}...")
    if refresh_token:
        print(f"   Refresh Token: {refresh_token[:50]}...")
    if expires_at:
        print(f"   Expires: {expires_at}")
    print()
    
    # Test if token works
    print("🔄 Testing token with Tradovate API...")
    
    base_url = "https://demo.tradovateapi.com/v1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            # Get account list
            async with session.get(
                f"{base_url}/account/list",
                headers=headers
            ) as response:
                if response.status == 200:
                    accounts = await response.json()
                    print(f"✅ Token is VALID and working!")
                    print(f"   Found {len(accounts)} account(s)")
                    print()
                    
                    # Get account details
                    if accounts:
                        acc = accounts[0]
                        acc_id = acc.get('id')
                        
                        async with session.get(
                            f"{base_url}/account/item",
                            headers=headers,
                            params={"id": acc_id}
                        ) as info_response:
                            if info_response.status == 200:
                                info = await info_response.json()
                                balance = (
                                    info.get('dayTradingBuyingPower') or
                                    info.get('netLiquidation') or
                                    info.get('availableFunds') or
                                    info.get('cashBalance')
                                )
                                print("Account Details:")
                                print(f"   Name: {acc.get('name', 'N/A')}")
                                print(f"   ID: {acc_id}")
                                if balance:
                                    print(f"   Balance: ${balance:,.2f}")
                    
                    print()
                    print("=" * 60)
                    print("✅ SUCCESS! OAuth flow worked!")
                    print("=" * 60)
                    print()
                    print("The token is stored and working.")
                    print("You can now:")
                    print("  1. Use recorder backend with this token")
                    print("  2. Fetch positions and account data")
                    print("  3. Place orders (if permissions allow)")
                    return True
                else:
                    text = await response.text()
                    print(f"❌ Token test failed: Status {response.status}")
                    print(f"   Response: {text[:200]}")
                    return False
        except Exception as e:
            print(f"❌ Error testing token: {e}")
            return False


if __name__ == '__main__':
    account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    asyncio.run(test_token(account_id))

