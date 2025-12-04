#!/usr/bin/env python3
"""
Test script to verify Tradovate market data access via WebSocket
This is a standalone test to see if we can get real-time prices before integrating into main system
"""

import asyncio
import json
import sqlite3
import sys
import os
from datetime import datetime

try:
    import websockets
except ImportError:
    print("❌ websockets library not installed. Install with: pip install websockets")
    sys.exit(1)

# Add parent directory to path to import tradovate_integration
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_market_data_websocket():
    """Test connecting to Tradovate market data WebSocket and getting quotes"""
    
    print("=" * 60)
    print("Tradovate Market Data WebSocket Test")
    print("=" * 60)
    print()
    
    # Step 1: Get md_access_token from database
    print("Step 1: Fetching md_access_token from database...")
    md_token = None
    demo = True
    
    try:
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, md_access_token 
            FROM accounts 
            WHERE md_access_token IS NOT NULL AND md_access_token != ''
            LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            md_token = row['md_access_token']
            # Default to demo - you can change this if needed
            demo = True  # Set to False for live trading
            print(f"✅ Found md_access_token for account: {row['name']} (ID: {row['id']})")
            print(f"   Demo mode: {demo} (change in script if needed)")
            print(f"   Token length: {len(md_token)} characters")
        else:
            print("❌ No md_access_token found in database")
            print("   Make sure you've connected a Tradovate account and it has md_access_token")
            conn.close()
            return
        conn.close()
    except Exception as e:
        print(f"❌ Error fetching md_access_token: {e}")
        return
    
    if not md_token:
        print("❌ md_access_token is empty")
        return
    
    print()
    
    # Step 2: Connect to WebSocket
    print("Step 2: Connecting to Tradovate market data WebSocket...")
    ws_url = "wss://demo.tradovateapi.com/v1/websocket" if demo else "wss://live.tradovateapi.com/v1/websocket"
    print(f"   URL: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as ws:
            print("✅ WebSocket connected")
            print()
            
            # Step 3: Authorize
            print("Step 3: Authorizing with md_access_token...")
            auth_message = f"authorize\n0\n\n{md_token}"
            await ws.send(auth_message)
            print(f"   Sent: authorize\\n0\\n\\n{md_token[:20]}...")
            
            # Wait for response
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                print(f"   Response: {response[:200]}")
                
                # Check if authorization was successful
                if "ok" in response.lower() or "authorized" in response.lower():
                    print("✅ Authorization successful")
                else:
                    print(f"⚠️  Authorization response: {response}")
            except asyncio.TimeoutError:
                print("⚠️  No authorization response received (timeout)")
            except Exception as e:
                print(f"⚠️  Error reading authorization response: {e}")
            
            print()
            
            # Step 4: Subscribe to a test symbol
            print("Step 4: Subscribing to market data for test symbols...")
            print("   Trying different subscription formats...")
            
            # Format 1: Try with contract ID lookup first
            # We need to get contract IDs for symbols
            print("   Note: May need contract IDs instead of symbols")
            
            # Try different endpoint formats
            subscription_formats = [
                # Format 1: Direct quote request
                ("quote/request", {"symbol": "MESM1"}),
                ("quote/request", {"symbols": ["MESM1", "MNQM1"]}),
                # Format 2: Subscribe (might need different format)
                ("quote/subscribe", {"symbol": "MESM1"}),
                ("quote/subscribe", {"symbols": ["MESM1"]}),
                # Format 3: Market data subscription
                ("marketData/subscribe", {"symbol": "MESM1"}),
                # Format 4: Try with contract ID (would need to lookup first)
            ]
            
            message_id = 1
            for endpoint, payload in subscription_formats:
                try:
                    # SockJS format: "{endpoint}\n{id}\n\n{json}"
                    subscribe_msg = f"{endpoint}\n{message_id}\n\n{json.dumps(payload)}"
                    print(f"   Trying: {endpoint} with {payload}")
                    await ws.send(subscribe_msg)
                    message_id += 1
                    await asyncio.sleep(0.5)  # Wait a bit between attempts
                except Exception as e:
                    print(f"   ❌ Error with {endpoint}: {e}")
            
            print()
            print("Step 5: Listening for market data updates (10 seconds)...")
            print("   (Press Ctrl+C to stop early)")
            print()
            print("-" * 60)
            
            # Step 5: Listen for market data
            message_count = 0
            start_time = asyncio.get_event_loop().time()
            timeout = 10.0  # Listen for 10 seconds
            
            try:
                while True:
                    try:
                        # Wait for message with timeout
                        message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        message_count += 1
                        elapsed = asyncio.get_event_loop().time() - start_time
                        
                        print(f"[{elapsed:.1f}s] Message #{message_count}:")
                        
                        # Try to parse message
                        try:
                            # Check if it's SockJS format
                            if message.startswith("frame"):
                                parts = message.split("\n", 3)
                                if len(parts) >= 4:
                                    json_data = json.loads(parts[3])
                                    print(f"   Format: SockJS frame")
                                    print(f"   Data: {json.dumps(json_data, indent=2)}")
                                else:
                                    print(f"   Raw: {message[:200]}")
                            elif message.startswith("["):
                                # Direct JSON array
                                data = json.loads(message)
                                print(f"   Format: JSON array")
                                print(f"   Data: {json.dumps(data, indent=2)}")
                            elif message.startswith("{"):
                                # Direct JSON object
                                data = json.loads(message)
                                print(f"   Format: JSON object")
                                print(f"   Data: {json.dumps(data, indent=2)}")
                            else:
                                print(f"   Format: Unknown")
                                print(f"   Raw: {message[:200]}")
                        except json.JSONDecodeError:
                            print(f"   Format: Non-JSON")
                            print(f"   Raw: {message[:200]}")
                        
                        print()
                        
                        # Check timeout
                        if elapsed >= timeout:
                            print(f"⏱️  Timeout reached ({timeout}s)")
                            break
                            
                    except asyncio.TimeoutError:
                        # No message received in 1 second, check if we should continue
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed >= timeout:
                            print(f"⏱️  Timeout reached ({timeout}s) - no messages received")
                            break
                        # Continue waiting
                        continue
                        
            except KeyboardInterrupt:
                print("\n⚠️  Interrupted by user")
            
            print("-" * 60)
            print()
            print(f"Summary:")
            print(f"   Messages received: {message_count}")
            print(f"   Duration: {elapsed:.1f} seconds")
            
            if message_count == 0:
                print()
                print("⚠️  No market data messages received.")
                print("   Possible reasons:")
                print("   - Market data subscription not active on Tradovate account")
                print("   - Symbol format incorrect")
                print("   - Market closed")
                print("   - WebSocket subscription format incorrect")
            else:
                print("✅ Successfully received market data!")
                
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ WebSocket connection failed: {e}")
        print("   Check if the URL is correct and server is accessible")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def test_alternative_methods():
    """Test alternative methods to get market data"""
    print()
    print("=" * 60)
    print("Testing Alternative Market Data Methods")
    print("=" * 60)
    print()
    
    # Method 1: Try HTTP endpoint (if available)
    print("Method 1: Checking for HTTP market data endpoints...")
    print("   (Tradovate may not have HTTP endpoints for market data)")
    print("   This would require checking Tradovate API documentation")
    print()
    
    # Method 2: Check if we can get contract info first
    print("Method 2: Getting contract information...")
    try:
        from phantom_scraper.tradovate_integration import TradovateIntegration
        
        async with TradovateIntegration(demo=True) as tradovate:
            # Try to get contract list
            print("   Attempting to get contract list...")
            # This would require authentication first
            print("   (Would need to authenticate first)")
    except Exception as e:
        print(f"   Error: {e}")
    
    print()

if __name__ == "__main__":
    print()
    print("🧪 Testing Tradovate Market Data Access")
    print()
    
    # Run the test
    try:
        asyncio.run(test_market_data_websocket())
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test alternative methods
    try:
        asyncio.run(test_alternative_methods())
    except Exception as e:
        print(f"Alternative methods test failed: {e}")
    
    print()
    print("=" * 60)
    print("Test Complete")
    print("=" * 60)

