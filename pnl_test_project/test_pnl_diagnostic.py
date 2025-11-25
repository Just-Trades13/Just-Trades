#!/usr/bin/env python3
"""
Comprehensive P&L Diagnostic Script

This script systematically tests:
1. Token validity and refresh
2. WebSocket connections (market data + user data)
3. Quote subscriptions
4. Position data retrieval
5. Real-time P&L calculation

Run this to identify exactly where the P&L tracking is failing.
"""

import sqlite3
import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PNLDiagnostic:
    def __init__(self):
        self.db_path = "/Users/mylesjadwin/Trading Projects/just_trades.db"
        self.base_url = "https://demo.tradovateapi.com/v1"
        self.access_token = None
        self.md_access_token = None
        self.refresh_token = None
        self.account_id = None
        self.user_id = None
        self.account_spec = None
        
    async def step1_check_tokens(self):
        """Step 1: Check if tokens exist and are valid"""
        print("\n" + "="*60)
        print("STEP 1: Checking stored tokens")
        print("="*60)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, name, tradovate_token, tradovate_refresh_token, 
                       token_expires_at, md_access_token, client_id, client_secret
                FROM accounts 
                WHERE broker = 'Tradovate' 
                AND tradovate_token IS NOT NULL
                LIMIT 1
            """)
            
            account = cursor.fetchone()
            conn.close()
            
            if not account:
                print("❌ No stored tokens found")
                return False
            
            acc_id, name, access_token, refresh_token, expires_at, md_token, client_id, client_secret = account
            
            print(f"✅ Found account: {name} (ID: {acc_id})")
            print(f"   Access Token: {access_token[:50] if access_token else 'None'}...")
            print(f"   MD Access Token: {md_token[:50] if md_token else 'None'}...")
            print(f"   Refresh Token: {refresh_token[:50] if refresh_token else 'None'}...")
            print(f"   Expires At: {expires_at}")
            
            # Check if expired
            if expires_at:
                try:
                    # Handle different datetime formats
                    if isinstance(expires_at, str):
                        # Try parsing as ISO format
                        try:
                            expires_str = expires_at.replace('Z', '+00:00') if 'Z' in expires_at else expires_at
                            expires_dt = datetime.fromisoformat(expires_str)
                        except:
                            # Try parsing as SQLite datetime
                            expires_dt = datetime.fromisoformat(expires_at)
                    elif isinstance(expires_at, datetime):
                        expires_dt = expires_at
                    else:
                        # Unknown type - skip expiration check
                        print(f"   ⚠️  Unknown expiration type: {type(expires_at)}")
                        expires_dt = None
                    
                    if expires_dt:
                        # Get current time in same timezone
                        if expires_dt.tzinfo:
                            now = datetime.now(expires_dt.tzinfo)
                        else:
                            now = datetime.now()
                        
                        if now >= expires_dt:
                            print("⚠️  Token is EXPIRED - will try to refresh")
                            # Try to refresh
                            if refresh_token:
                                refreshed = await self._refresh_token(refresh_token, client_id, client_secret)
                                if refreshed:
                                    # Re-fetch from DB
                                    conn = sqlite3.connect(self.db_path)
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        SELECT tradovate_token, md_access_token, tradovate_refresh_token
                                        FROM accounts WHERE id = ?
                                    """, (acc_id,))
                                    account = cursor.fetchone()
                                    conn.close()
                                    if account:
                                        access_token, md_token, refresh_token = account
                                        print("✅ Token refreshed successfully")
                                    else:
                                        return False
                                else:
                                    print("❌ Token refresh failed - need to re-authenticate")
                                    return False
                            else:
                                print("❌ No refresh token available - need to re-authenticate")
                                return False
                        else:
                            print(f"✅ Token is valid (expires in {expires_dt - now})")
                except Exception as e:
                    print(f"⚠️  Could not parse expiration: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Test token validity
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/account/list",
                    headers={"Authorization": f"Bearer {access_token}"}
                ) as response:
                    if response.status == 200:
                        accounts = await response.json()
                        print(f"✅ Token is VALID - found {len(accounts)} accounts")
                        if accounts:
                            self.account_id = accounts[0].get('id')
                            print(f"   Using account ID: {self.account_id}")
                    else:
                        text = await response.text()
                        print(f"❌ Token is INVALID: {response.status} - {text[:200]}")
                        return False
            
            self.access_token = access_token
            self.md_access_token = md_token
            self.refresh_token = refresh_token
            
            return True
            
        except Exception as e:
            print(f"❌ Error checking tokens: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def _refresh_token(self, refresh_token: str, client_id: str = None, client_secret: str = None):
        """Refresh access token"""
        print("\n   Refreshing token...")
        
        client_id = client_id or "8580"
        client_secret = client_secret or "59dc97d6-0c11-4d2e-9044-480f8a6c1260"
        
        oauth_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        if client_id:
            oauth_data['client_id'] = client_id
        if client_secret:
            oauth_data['client_secret'] = client_secret
        
        oauth_form_data = urlencode(oauth_data)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/oauth/token",
                    data=oauth_form_data,
                    headers={'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
                ) as response:
                    # Check content type
                    content_type = response.headers.get('Content-Type', '')
                    print(f"   Response status: {response.status}, Content-Type: {content_type}")
                    
                    if 'application/json' in content_type:
                        data = await response.json()
                    else:
                        # Try to get text first to see what we got
                        text = await response.text()
                        print(f"   Non-JSON response: {text[:200]}")
                        try:
                            data = json.loads(text)
                        except:
                            return False
                    
                    if "accessToken" in data:
                        access_token = data.get("accessToken")
                        md_access_token = data.get("mdAccessToken")
                        new_refresh_token = data.get("refreshToken", refresh_token)
                        expires_in = data.get("expiresIn", 86400)
                        expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
                        
                        # Update database
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE accounts 
                            SET tradovate_token = ?,
                                tradovate_refresh_token = ?,
                                token_expires_at = ?,
                                md_access_token = ?
                            WHERE broker = 'Tradovate' AND tradovate_token IS NOT NULL
                        """, (access_token, new_refresh_token, expires_at, md_access_token))
                        conn.commit()
                        conn.close()
                        
                        print("   ✅ Token refreshed and stored")
                        return True
                    else:
                        print(f"   ❌ Refresh failed: {data}")
                        return False
        except Exception as e:
            print(f"   ❌ Refresh error: {e}")
            return False
    
    async def step2_get_positions(self):
        """Step 2: Get positions from REST API"""
        print("\n" + "="*60)
        print("STEP 2: Getting positions from REST API")
        print("="*60)
        
        if not self.access_token or not self.account_id:
            print("❌ Missing access token or account ID")
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/account/{self.account_id}/positions",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                ) as response:
                    if response.status == 200:
                        positions = await response.json()
                        open_positions = [p for p in positions if abs(p.get('netPos', 0)) > 0]
                        print(f"✅ Found {len(positions)} total positions, {len(open_positions)} open")
                        
                        for pos in open_positions:
                            contract_id = pos.get('contractId')
                            net_pos = pos.get('netPos', 0)
                            net_price = pos.get('netPrice')
                            prev_price = pos.get('prevPrice')
                            open_pnl = pos.get('openPnl') or pos.get('unrealizedPnl')
                            
                            print(f"\n   Position:")
                            print(f"      Contract ID: {contract_id}")
                            print(f"      Net Pos: {net_pos}")
                            print(f"      Net Price (avg entry): {net_price}")
                            print(f"      Prev Price (last): {prev_price}")
                            print(f"      Open P&L (from API): {open_pnl}")
                            print(f"      All fields: {list(pos.keys())}")
                            
                            # Check for P&L fields
                            pnl_fields = {k: v for k, v in pos.items() if 'pnl' in k.lower() or 'profit' in k.lower()}
                            if pnl_fields:
                                print(f"      P&L fields found: {pnl_fields}")
                        
                        return open_positions
                    else:
                        text = await response.text()
                        print(f"❌ Failed to get positions: {response.status} - {text[:200]}")
                        return []
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def step3_test_websocket_connection(self):
        """Step 3: Test WebSocket connections"""
        print("\n" + "="*60)
        print("STEP 3: Testing WebSocket connections")
        print("="*60)
        
        if not self.md_access_token:
            print("⚠️  No mdAccessToken - market data WebSocket may not work")
            print("   Will try with access_token as fallback")
        
        # Test market data WebSocket
        print("\n   Testing Market Data WebSocket...")
        try:
            import websockets
            ws_url = "wss://md.tradovateapi.com/v1/websocket"
            token_to_use = self.md_access_token or self.access_token
            
            print(f"   Connecting to: {ws_url}")
            print(f"   Using token: {token_to_use[:50] if token_to_use else 'None'}...")
            
            async with websockets.connect(ws_url) as ws:
                print("   ✅ Connected to market data WebSocket")
                
                # Try to authorize
                auth_msg = f"authorize\n0\n\n{token_to_use}"
                await ws.send(auth_msg)
                print(f"   ✅ Sent authorization message")
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    print(f"   ✅ Received response: {response[:200]}")
                except asyncio.TimeoutError:
                    print("   ⚠️  No response to authorization (may still work)")
                
                return True
                
        except Exception as e:
            print(f"   ❌ Market data WebSocket failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def step4_test_quote_subscription(self, contract_id: str):
        """Step 4: Test quote subscription for a contract"""
        print("\n" + "="*60)
        print(f"STEP 4: Testing quote subscription for contract {contract_id}")
        print("="*60)
        
        if not self.md_access_token:
            print("⚠️  No mdAccessToken - using access_token")
        
        token_to_use = self.md_access_token or self.access_token
        
        try:
            import websockets
            ws_url = "wss://md.tradovateapi.com/v1/websocket"
            
            async with websockets.connect(ws_url) as ws:
                # Authorize
                auth_msg = f"authorize\n0\n\n{token_to_use}"
                await ws.send(auth_msg)
                print("   ✅ Authorized")
                
                # Wait a bit for auth to process
                await asyncio.sleep(1)
                
                # Try multiple subscription formats
                formats = [
                    ("Newline-delimited", f"md/subscribeQuote\n1\n\n{json.dumps({'contractId': int(contract_id)})}"),
                    ("JSON-RPC", json.dumps({
                        "id": 1,
                        "method": "subscribeQuote",
                        "params": {"contractId": int(contract_id)}
                    })),
                    ("Array", json.dumps(["subscribeQuote", {"contractId": int(contract_id)}]))
                ]
                
                for format_name, subscribe_msg in formats:
                    print(f"\n   Trying {format_name} format...")
                    try:
                        await ws.send(subscribe_msg)
                        print(f"   ✅ Sent subscription ({format_name})")
                        
                        # Wait for response
                        try:
                            response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                            print(f"   ✅ Received: {response[:200]}")
                            
                            # Try to parse
                            try:
                                if response.startswith('a['):
                                    # Socket.IO format
                                    data = json.loads(response[2:])
                                    print(f"   📊 Parsed (Socket.IO): {data}")
                                else:
                                    # Try JSON
                                    data = json.loads(response)
                                    print(f"   📊 Parsed (JSON): {data}")
                            except:
                                print(f"   📊 Raw response: {response}")
                        except asyncio.TimeoutError:
                            print(f"   ⚠️  No immediate response ({format_name})")
                        
                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"   ❌ {format_name} failed: {e}")
                
                # Listen for a few seconds to see if we get quote updates
                print("\n   Listening for quote updates (5 seconds)...")
                quote_received = False
                start_time = asyncio.get_event_loop().time()
                while (asyncio.get_event_loop().time() - start_time) < 5:
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        print(f"   📊 Quote update: {response[:300]}")
                        quote_received = True
                    except asyncio.TimeoutError:
                        continue
                
                if quote_received:
                    print("   ✅ Received quote updates!")
                else:
                    print("   ⚠️  No quote updates received (subscription may not be working)")
                
                return quote_received
                
        except Exception as e:
            print(f"   ❌ Quote subscription test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def run_full_diagnostic(self):
        """Run all diagnostic steps"""
        print("\n" + "="*60)
        print("TRADOVATE P&L DIAGNOSTIC")
        print("="*60)
        print("\nThis will systematically test:")
        print("1. Token validity and refresh")
        print("2. Position retrieval")
        print("3. WebSocket connections")
        print("4. Quote subscriptions")
        print("\nMake sure you have an OPEN POSITION in Tradovate!")
        print("="*60)
        
        # Step 1: Check tokens
        if not await self.step1_check_tokens():
            print("\n❌ Step 1 failed - cannot continue")
            return
        
        # Step 2: Get positions
        positions = await self.step2_get_positions()
        if not positions:
            print("\n⚠️  No open positions found - cannot test P&L tracking")
            return
        
        # Step 3: Test WebSocket
        ws_ok = await self.step3_test_websocket_connection()
        if not ws_ok:
            print("\n⚠️  WebSocket connection failed - real-time P&L may not work")
        
        # Step 4: Test quote subscription for first position
        if positions:
            contract_id = str(positions[0].get('contractId'))
            if contract_id:
                await self.step4_test_quote_subscription(contract_id)
        
        # Summary
        print("\n" + "="*60)
        print("DIAGNOSTIC SUMMARY")
        print("="*60)
        print(f"✅ Tokens: {'Valid' if self.access_token else 'Invalid'}")
        print(f"✅ Positions: {len(positions)} open")
        print(f"✅ WebSocket: {'Connected' if ws_ok else 'Failed'}")
        print(f"✅ MD Token: {'Available' if self.md_access_token else 'Missing'}")
        print("\nNext steps:")
        if not self.md_access_token:
            print("  - Re-authenticate to get mdAccessToken")
        if not ws_ok:
            print("  - Check WebSocket connection logic")
        if positions and not any(p.get('openPnl') for p in positions):
            print("  - REST API doesn't provide openPnl - need WebSocket quotes")
        print("="*60)

if __name__ == "__main__":
    diagnostic = PNLDiagnostic()
    asyncio.run(diagnostic.run_full_diagnostic())

