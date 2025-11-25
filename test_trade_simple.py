#!/usr/bin/env python3
"""
Simple test: Just try to place a trade and see what happens
"""
import asyncio
import aiohttp
import json
import sqlite3

async def place_test_trade():
    """Place a test trade to demo account"""
    print("=" * 60)
    print("TEST TRADE - DEMO ACCOUNT")
    print("=" * 60)
    
    # Get account and token from database
    conn = sqlite3.connect('just_trades.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, tradovate_token, tradovate_accounts 
        FROM accounts 
        WHERE tradovate_token IS NOT NULL 
        LIMIT 1
    """)
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print("❌ No account with token found in database")
        print("   Please connect your account first")
        return
    
    print(f"\n✅ Found account: {account['name']} (ID: {account['id']})")
    
    # Find demo account ID
    account_id = account['id']
    subaccount_id = None
    
    if account['tradovate_accounts']:
        try:
            trad_accounts = json.loads(account['tradovate_accounts'])
            demo_accounts = [acc for acc in trad_accounts if acc.get('is_demo', False)]
            if demo_accounts:
                subaccount_id = str(demo_accounts[0].get('id') or demo_accounts[0].get('accountId', ''))
                print(f"✅ Found demo account: {subaccount_id}")
            else:
                print("⚠️ No demo accounts found, using account ID")
                subaccount_id = str(account_id)
        except:
            print("⚠️ Could not parse tradovate_accounts, using account ID")
            subaccount_id = str(account_id)
    else:
        subaccount_id = str(account_id)
        print(f"⚠️ No tradovate_accounts, using account ID: {subaccount_id}")
    
    # Send test trade via the API
    url = "http://localhost:8082/api/manual-trade"
    headers = {"Content-Type": "application/json"}
    payload = {
        "account_subaccount": f"{account_id}:{subaccount_id}",
        "symbol": "MNQ",
        "side": "Sell",
        "quantity": 1
    }
    
    print(f"\n🚀 Placing test trade:")
    print(f"   Account: {payload['account_subaccount']}")
    print(f"   Symbol: {payload['symbol']}")
    print(f"   Side: {payload['side']}")
    print(f"   Quantity: {payload['quantity']}")
    print()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                response_status = response.status
                response_json = await response.json()
                
                print(f"📡 Response Status: {response_status}")
                print(f"📦 Response:")
                print(json.dumps(response_json, indent=2))
                
                if response_json.get('success'):
                    print("\n✅✅✅ SUCCESS! Trade placed!")
                    print("   The token WORKS for trading, even with numeric phs!")
                else:
                    error = response_json.get('error', 'Unknown error')
                    print(f"\n❌ Trade failed: {error}")
                    
                    if "Access is denied" in error or "Access denied" in error:
                        print("\n   🔍 Diagnosis:")
                        print("   - Token does NOT have trading permissions")
                        print("   - phs is likely a number, not an array")
                        print("   - Need to fix OAuth app permissions or user account settings")
                    elif "not connected" in error.lower():
                        print("\n   🔍 Diagnosis:")
                        print("   - Account is not connected")
                        print("   - Need to connect account first")
                    else:
                        print(f"\n   🔍 Diagnosis:")
                        print(f"   - Error: {error}")
                        print("   - Check server logs for more details")
                
    except Exception as e:
        print(f"\n❌ Error sending trade request: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(place_test_trade())

