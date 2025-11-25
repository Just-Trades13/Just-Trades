#!/usr/bin/env python3
"""
Test trade using API credentials (CID: 8581) instead of OAuth
"""
import asyncio
import aiohttp
import json
import base64
import sqlite3

# API credentials
CLIENT_ID = "8581"
CLIENT_SECRET = "43469c08-7b5d-4401-8a98-0bd67ad1eb13"

async def get_accounts():
    """Get accounts from the API"""
    url = "http://localhost:8082/api/accounts"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            data = await response.json()
            # Return in expected format
            if data.get('success'):
                return {'success': True, 'accounts': data.get('accounts', [])}
            return data

async def decode_token(token):
    """Decode JWT token to check permissions"""
    try:
        parts = token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            decoded = base64.urlsafe_b64decode(payload)
            token_data = json.loads(decoded)
            return token_data
    except Exception as e:
        print(f"Error decoding token: {e}")
    return None

async def send_test_trade(account_id, subaccount_id, symbol, side, quantity):
    """Send a test trade"""
    url = "http://localhost:8082/api/manual-trade"
    headers = {"Content-Type": "application/json"}
    payload = {
        "account_subaccount": f"{account_id}:{subaccount_id}",
        "symbol": symbol,
        "side": side,
        "quantity": quantity
    }

    print(f"\n🚀 Placing test trade with API credentials:")
    print(f"   Account: {payload['account_subaccount']}")
    print(f"   Symbol: {payload['symbol']}")
    print(f"   Side: {payload['side']}")
    print(f"   Quantity: {payload['quantity']}")

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            response_status = response.status
            response_json = await response.json()
            print(f"\n📡 Response Status: {response_status}")
            print(f"📦 Response: {json.dumps(response_json, indent=2)}")
            return response_json

async def main():
    print("=" * 60)
    print("TEST TRADE WITH API CREDENTIALS (CID: 8581)")
    print("=" * 60)
    
    # 1. Get available accounts
    print("\n1️⃣ Getting accounts...")
    accounts_data = await get_accounts()
    
    if not accounts_data or not accounts_data.get('success'):
        print("❌ Failed to retrieve accounts")
        return
    
    target_account_id = None
    target_subaccount_id = None
    
    # Get account from database directly
    conn = sqlite3.connect('just_trades.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, tradovate_token, client_id, client_secret, tradovate_accounts FROM accounts LIMIT 1")
    db_account = cursor.fetchone()
    conn.close()
    
    if not db_account:
        print("❌ No account found in database")
        return
    
    print(f"\n📋 Account: {db_account['name']} (ID: {db_account['id']})")
    
    if db_account['tradovate_token']:
        token = db_account['tradovate_token']
        print(f"   ✅ Has token")
        print(f"   🔑 Token (first 50 chars): {token[:50]}...")
        
        # Decode token
        token_data = await decode_token(token)
        if token_data:
            print(f"\n   📋 Decoded Token Payload:")
            print(f"      {json.dumps(token_data, indent=6)}")
            
            if 'phs' in token_data:
                phs = token_data['phs']
                if isinstance(phs, list):
                    print(f"\n   ✅✅✅ phs is ARRAY: {phs}")
                    print(f"   ✅ Token HAS trading permissions!")
                else:
                    print(f"\n   ⚠️ phs is NUMBER: {phs}")
                    print(f"   ⚠️ Token may NOT have trading permissions")
        
        print(f"\n   🔑 Client ID: {db_account['client_id'] or 'Not set (using 8581 for test)'}")
        print(f"   🔑 Client Secret: {(db_account['client_secret'] or 'Not set')[:20]}...")
        
        # Parse tradovate_accounts to find demo account
        if db_account['tradovate_accounts']:
            try:
                trad_accounts = json.loads(db_account['tradovate_accounts'])
                demo_accounts = [acc for acc in trad_accounts if acc.get('is_demo', False)]
                if demo_accounts:
                    target_subaccount_id = str(demo_accounts[0].get('id') or demo_accounts[0].get('accountId', ''))
                    target_account_id = db_account['id']
                    print(f"\n   📊 Found demo account: {target_subaccount_id}")
                else:
                    print(f"\n   ⚠️ No demo accounts found in tradovate_accounts")
            except:
                print(f"\n   ⚠️ Could not parse tradovate_accounts")
        
        # Fallback: use account ID as subaccount
        if not target_subaccount_id:
            target_subaccount_id = str(db_account['id'])
            target_account_id = db_account['id']
            print(f"\n   ⚠️ Using account ID as subaccount: {target_subaccount_id}")
    else:
        print("   ❌ No token - account not connected")
        return
    
    if not target_account_id or not target_subaccount_id:
        print("\n❌ No suitable demo account found for testing")
        return
    
    # 2. Send test trade
    print(f"\n2️⃣ Sending test trade...")
    trade_result = await send_test_trade(target_account_id, target_subaccount_id, "MNQ", "Sell", 1)
    
    if trade_result and trade_result.get('success'):
        print("\n✅✅✅ TRADE SUCCESSFUL!")
        print("   The API credentials (8581) work for trading!")
    else:
        error = trade_result.get('error', 'Unknown error') if trade_result else 'No response'
        print(f"\n❌ TRADE FAILED: {error}")
        print("\n   This tells us:")
        if "Access is denied" in error or "Access denied" in error:
            print("   - Token does NOT have trading permissions")
            print("   - Need to check OAuth app settings or user account API trading permissions")
        elif "not connected" in error.lower():
            print("   - Account is not connected (no token)")
            print("   - Need to connect account first")
        else:
            print(f"   - Error: {error}")

if __name__ == "__main__":
    asyncio.run(main())

