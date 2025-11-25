#!/usr/bin/env python3
"""
Test WebSocket Fixes - Verify Market Data WebSocket Authentication

This script tests:
1. Token validity
2. Market data WebSocket connection with message-based auth
3. Quote subscription
4. Message reception
"""

import sqlite3
import asyncio
import aiohttp
import json
import logging
import websockets
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_market_data_websocket():
    """Test market data WebSocket with message-based auth"""
    
    print("\n" + "="*60)
    print("TESTING MARKET DATA WEBSOCKET FIXES")
    print("="*60)
    
    # Get tokens from database
    db_path = "/Users/mylesjadwin/Trading Projects/just_trades.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, tradovate_token, md_access_token, 
                   datetime(token_expires_at) as expires
            FROM accounts 
            WHERE broker = 'Tradovate' 
            AND tradovate_token IS NOT NULL
            LIMIT 1
        """)
        account = cursor.fetchone()
        conn.close()
        
        if not account:
            print("❌ No account found")
            return False
        
        acc_id, name, access_token, md_token, expires = account
        print(f"\n✅ Found account: {name} (ID: {acc_id})")
        print(f"   Access Token: {access_token[:50] if access_token else 'None'}...")
        print(f"   MD Access Token: {md_token[:50] if md_token else 'None'}...")
        print(f"   Expires: {expires}")
        
        # Check if expired
        if expires:
            try:
                exp_dt = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                now = datetime.now()
                if now > exp_dt:
                    print(f"\n⚠️  Token is EXPIRED ({now - exp_dt} ago)")
                    print("   Please re-authenticate through main server web interface")
                    return False
                else:
                    print(f"✅ Token is valid (expires in {exp_dt - now})")
            except:
                print("⚠️  Could not parse expiration")
        
        # Use mdAccessToken if available, otherwise access_token
        token_to_use = md_token or access_token
        if not token_to_use:
            print("❌ No token available")
            return False
        
        if md_token:
            print("✅ Using mdAccessToken")
        else:
            print("⚠️  Using access_token (mdAccessToken not available)")
        
    except Exception as e:
        print(f"❌ Error getting tokens: {e}")
        return False
    
    # Test WebSocket connection
    print("\n" + "="*60)
    print("STEP 1: Connecting to Market Data WebSocket")
    print("="*60)
    
    ws_url = "wss://md.tradovateapi.com/v1/websocket"
    
    try:
        # Connect WITHOUT headers (FIXED)
        print(f"\nConnecting to: {ws_url}")
        print("Using message-based authentication (FIXED)")
        
        async with websockets.connect(ws_url) as ws:
            print("✅ Connected to WebSocket")
            
            # Wait for connection
            await asyncio.sleep(0.5)
            
            # Send authorization message (FIXED)
            print("\n" + "-"*60)
            print("STEP 2: Sending Authorization Message")
            print("-"*60)
            auth_message = f"authorize\n0\n\n{token_to_use}"
            print(f"Sending: authorize\\n0\\n\\n{token_to_use[:50]}...")
            await ws.send(auth_message)
            print("✅ Authorization message sent")
            
            # Wait for response
            print("\nWaiting for authorization response (3 seconds)...")
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                print(f"✅ Received response: {response[:200]}")
                
                # Try to parse
                try:
                    if response.startswith('a['):
                        data = json.loads(response[2:])
                        print(f"   Parsed (Socket.IO): {json.dumps(data, indent=2)}")
                    else:
                        data = json.loads(response)
                        print(f"   Parsed (JSON): {json.dumps(data, indent=2)}")
                except:
                    print(f"   Raw response: {response}")
            except asyncio.TimeoutError:
                print("⚠️  No immediate response (may still be processing)")
            
            # Test subscription
            print("\n" + "-"*60)
            print("STEP 3: Testing Quote Subscription")
            print("-"*60)
            
            # Get a contract ID from positions (if available)
            contract_id = None
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://demo.tradovateapi.com/v1/account/list",
                        headers={"Authorization": f"Bearer {access_token}"}
                    ) as resp:
                        if resp.status == 200:
                            accounts = await resp.json()
                            if accounts:
                                acc_id = accounts[0].get('id')
                                async with session.get(
                                    f"https://demo.tradovateapi.com/v1/account/{acc_id}/positions",
                                    headers={"Authorization": f"Bearer {access_token}"}
                                ) as pos_resp:
                                    if pos_resp.status == 200:
                                        positions = await pos_resp.json()
                                        open_positions = [p for p in positions if abs(p.get('netPos', 0)) > 0]
                                        if open_positions:
                                            contract_id = open_positions[0].get('contractId')
                                            print(f"✅ Found open position with contract ID: {contract_id}")
            except Exception as e:
                print(f"⚠️  Could not get contract ID from positions: {e}")
            
            if not contract_id:
                # Use a test contract ID (MNQ December 2025)
                contract_id = 12345  # This will fail, but we'll see the error
                print(f"⚠️  No open positions found, using test contract ID: {contract_id}")
            
            # Try subscription with FIXED format
            subscribe_data = {"contractId": int(contract_id)}
            subscribe_msg = f"md/subscribeQuote\n1\n\n{json.dumps(subscribe_data)}"
            
            print(f"\nSending subscription:")
            print(f"Format: md/subscribeQuote\\n1\\n\\n{json.dumps(subscribe_data)}")
            await ws.send(subscribe_msg)
            print("✅ Subscription message sent")
            
            # Listen for messages
            print("\n" + "-"*60)
            print("STEP 4: Listening for Messages (10 seconds)")
            print("-"*60)
            print("Watch for quote updates or error messages...\n")
            
            messages_received = 0
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < 10:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    messages_received += 1
                    print(f"\n📨 Message #{messages_received}:")
                    print(f"   Raw: {message[:300]}")
                    
                    # Try to parse
                    try:
                        if message.startswith('a['):
                            data = json.loads(message[2:])
                            print(f"   Parsed (Socket.IO): {json.dumps(data, indent=2)}")
                        else:
                            data = json.loads(message)
                            print(f"   Parsed (JSON): {json.dumps(data, indent=2)}")
                    except:
                        print(f"   Could not parse as JSON")
                except asyncio.TimeoutError:
                    continue
            
            print(f"\n{'='*60}")
            print("TEST RESULTS")
            print("="*60)
            print(f"✅ WebSocket connected: YES")
            print(f"✅ Authorization sent: YES")
            print(f"✅ Subscription sent: YES")
            print(f"📨 Messages received: {messages_received}")
            
            if messages_received > 0:
                print("\n✅ SUCCESS! WebSocket is working and receiving messages!")
                print("   The fixes appear to be working correctly.")
            else:
                print("\n⚠️  No messages received yet")
                print("   This could mean:")
                print("   - Subscription format needs adjustment")
                print("   - No quotes available for test contract")
                print("   - Need to check with actual open position")
            
            return messages_received > 0
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ WebSocket connection failed: {e}")
        print("   Status code indicates authentication or connection issue")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_market_data_websocket())
    if result:
        print("\n✅ Test completed successfully!")
    else:
        print("\n⚠️  Test completed with issues - check output above")

