#!/usr/bin/env python3
"""
Test trade directly against Tradovate API to isolate the problem
This bypasses our backend and tests the token directly
"""
import asyncio
import aiohttp
import json
import sqlite3
import base64

async def get_token_from_db():
    """Get access token from database"""
    conn = sqlite3.connect('just_trades.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, tradovate_token 
        FROM accounts 
        WHERE tradovate_token IS NOT NULL 
        LIMIT 1
    """)
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        return None, None
    
    return account['tradovate_token'], account['name']

def decode_token(token):
    """Decode JWT to check phs"""
    try:
        parts = token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
    except:
        pass
    return None

async def get_account_list(access_token):
    """Get account list from Tradovate"""
    url = "https://demo.tradovateapi.com/v1/account/list"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                text = await response.text()
                print(f"❌ Failed to get account list: {response.status}")
                print(f"   Response: {text[:500]}")
                return None

async def place_order_direct(access_token, account_id, symbol="MNQ"):
    """Place order directly to Tradovate API"""
    url = "https://demo.tradovateapi.com/v1/order/placeorder"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Try different symbol formats
    symbols_to_try = [
        symbol,  # Just "MNQ"
        f"{symbol}Z5",  # With expiry
        f"{symbol}H6",  # Alternative expiry
    ]
    
    order = {
        "accountId": account_id,
        "action": "Sell",
        "symbol": None,  # Will be set in loop
        "orderType": "Market",
        "orderQty": 1,
        "isAutomated": True
    }
    
    async with aiohttp.ClientSession() as session:
        for symbol_to_try in symbols_to_try:
            order["symbol"] = symbol_to_try
            print(f"\n🚀 Trying symbol: {symbol_to_try}")
            print(f"   Order: {json.dumps(order, indent=2)}")
            
            try:
                async with session.post(url, headers=headers, json=order) as response:
                    status = response.status
                    response_text = await response.text()
                    
                    print(f"\n📡 Response Status: {status}")
                    
                    try:
                        response_json = json.loads(response_text)
                        print(f"📦 Response JSON:")
                        print(json.dumps(response_json, indent=2))
                        
                        if status == 200:
                            if "orderId" in response_json:
                                print(f"\n✅✅✅ SUCCESS! Order placed!")
                                print(f"   Order ID: {response_json.get('orderId')}")
                                print(f"   Symbol: {response_json.get('symbol')}")
                                print(f"   Status: {response_json.get('status')}")
                                print(f"\n🎉 The token HAS trading permissions!")
                                print(f"   The problem is NOT the token - it's something in our backend logic")
                                return True
                            else:
                                print(f"\n⚠️ Got 200 but no orderId in response")
                        elif status == 403:
                            print(f"\n❌❌❌ Access Denied (403)")
                            if "failureReason" in response_json:
                                print(f"   Reason: {response_json['failureReason']}")
                            print(f"\n🔍 Diagnosis:")
                            print(f"   The token does NOT have trading permissions")
                            print(f"   This confirms the OAuth token is the problem")
                            return False
                        elif "Access is denied" in response_text or "Access denied" in response_text:
                            print(f"\n❌❌❌ Access Denied")
                            print(f"\n🔍 Diagnosis:")
                            print(f"   The token does NOT have trading permissions")
                            print(f"   This confirms the OAuth token is the problem")
                            return False
                        else:
                            print(f"\n⚠️ Unexpected response")
                            if symbol_to_try != symbols_to_try[-1]:
                                print(f"   Trying next symbol...")
                                continue
                    except:
                        print(f"📦 Response Text: {response_text[:500]}")
                        if "Access is denied" in response_text or "Access denied" in response_text:
                            print(f"\n❌❌❌ Access Denied")
                            print(f"\n🔍 Diagnosis:")
                            print(f"   The token does NOT have trading permissions")
                            return False
                        
            except Exception as e:
                print(f"❌ Error: {e}")
                if symbol_to_try != symbols_to_try[-1]:
                    print(f"   Trying next symbol...")
                    continue
    
    return None

async def main():
    print("=" * 70)
    print("DIRECT TRADOVATE API TEST - ISOLATING THE PROBLEM")
    print("=" * 70)
    
    # Step 1: Get token
    print("\n1️⃣ Getting access token from database...")
    access_token, account_name = await get_token_from_db()
    
    if not access_token:
        print("❌ No token found in database")
        print("   Please connect your account first at http://localhost:8082/accounts")
        return
    
    print(f"✅ Found token for account: {account_name}")
    print(f"   Token (first 50 chars): {access_token[:50]}...")
    
    # Decode token to check phs
    token_data = decode_token(access_token)
    if token_data:
        print(f"\n📋 Token Payload:")
        if 'phs' in token_data:
            phs = token_data['phs']
            if isinstance(phs, list):
                print(f"   ✅ phs is ARRAY: {phs}")
            else:
                print(f"   ⚠️ phs is NUMBER: {phs}")
        print(f"   {json.dumps(token_data, indent=2)}")
    
    # Step 2: Get account list
    print(f"\n2️⃣ Getting account list from Tradovate...")
    accounts = await get_account_list(access_token)
    
    if not accounts:
        print("❌ Could not get account list - token may be invalid")
        return
    
    print(f"✅ Found {len(accounts)} accounts")
    
    # Find demo account
    demo_account = None
    for acc in accounts:
        print(f"   Account ID: {acc.get('id')}, Name: {acc.get('name')}, Active: {acc.get('isActive')}")
        # Look for demo account (usually has 'demo' in name or isActive=True)
        if acc.get('isActive') and (not demo_account or 'demo' in str(acc.get('name', '')).lower()):
            demo_account = acc
            print(f"      ⭐ Using this as demo account")
    
    if not demo_account:
        # Use first active account
        for acc in accounts:
            if acc.get('isActive'):
                demo_account = acc
                break
    
    if not demo_account:
        demo_account = accounts[0] if accounts else None
    
    if not demo_account:
        print("❌ No accounts found")
        return
    
    account_id = demo_account.get('id')
    print(f"\n✅ Using account ID: {account_id}")
    print(f"   Account name: {demo_account.get('name')}")
    
    # Step 3: Place test order
    print(f"\n3️⃣ Placing test order directly to Tradovate API...")
    print(f"   This bypasses our backend completely")
    print(f"   URL: https://demo.tradovateapi.com/v1/order/placeorder")
    
    result = await place_order_direct(access_token, account_id, "MNQ")
    
    # Summary
    print(f"\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if result is True:
        print("✅✅✅ TOKEN WORKS FOR TRADING!")
        print("   The OAuth token HAS trading permissions")
        print("   The problem is in our backend logic, not the token")
        print("   Check:")
        print("   - Account/subaccount mapping")
        print("   - Order format in our backend")
        print("   - API endpoint URLs")
    elif result is False:
        print("❌❌❌ TOKEN DOES NOT HAVE TRADING PERMISSIONS")
        print("   The OAuth token is the problem")
        print("   Even though OAuth app has 'Orders: Full Access'")
        print("   Solutions:")
        print("   1. Click 'Update' in Tradovate OAuth app settings")
        print("   2. Check user account has 'API Trading' enabled")
        print("   3. Try creating a new OAuth app")
        print("   4. Contact Tradovate support")
    else:
        print("⚠️ Could not determine result - check output above")

if __name__ == "__main__":
    asyncio.run(main())

