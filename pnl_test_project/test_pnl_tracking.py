#!/usr/bin/env python3
"""
Minimal Tradovate P&L Tracking Test
This is a standalone test to verify real-time P&L tracking works correctly
before integrating into the main project.
"""

import asyncio
import aiohttp
import json
import logging
import sys
from datetime import datetime
from typing import Dict, Optional

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("ERROR: websockets library not installed. Install with: pip install websockets")
    sys.exit(1)

# Configure logging to see everything
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TradovatePNLTracker:
    """Minimal P&L tracker for testing"""
    
    def __init__(self, demo=True):
        self.demo = demo
        self.base_url = "https://demo.tradovateapi.com/v1" if demo else "https://live.tradovateapi.com/v1"
        self.ws_user_url = "wss://demo.tradovateapi.com/v1/websocket" if demo else "wss://live.tradovateapi.com/v1/websocket"
        self.ws_md_url = "wss://md.tradovateapi.com/v1/websocket"  # Same for demo and live
        
        # Tokens
        self.access_token: Optional[str] = None
        self.md_access_token: Optional[str] = None
        
        # WebSocket connections
        self.ws_user: Optional[WebSocketClientProtocol] = None
        self.ws_md: Optional[WebSocketClientProtocol] = None
        
        # Data caches
        self.positions: Dict[int, Dict] = {}  # {position_id: position_data}
        self.quotes: Dict[int, Dict] = {}  # {contract_id: quote_data}
        self.contracts: Dict[int, Dict] = {}  # {contract_id: contract_info}
        
        # Account info (CRITICAL - from forum thread analysis)
        self.account_id: Optional[int] = None  # From /account/list (for orders/positions)
        self.account_spec: Optional[str] = None  # From auth response 'name' field
        self.user_id: Optional[int] = None  # From auth response (for subscriptions)
        
    async def authenticate(self, username: str, password: str, client_id: str = None, client_secret: str = None) -> bool:
        """Authenticate with Tradovate and get tokens"""
        logger.info("=" * 60)
        logger.info("STEP 1: Authenticating with Tradovate")
        logger.info("=" * 60)
        
        login_data = {
            "name": username,
            "password": password,
            "appId": "Just.Trade",
            "appVersion": "1.0.0",
        }
        
        if client_id and client_secret:
            # Try different Client ID formats
            # Format 1: As-is (e.g., "8580")
            # Format 2: With "cid" prefix (e.g., "cid8580")
            login_data["cid"] = client_id
            login_data["sec"] = client_secret
            logger.info(f"Using Client ID: {client_id}, Secret: {client_secret[:20]}...")
            
            # Also try with "cid" prefix if client_id is numeric
            if client_id.isdigit():
                logger.info(f"Client ID is numeric, will try both '{client_id}' and 'cid{client_id}' formats")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/auth/accesstokenrequest",
                    json=login_data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    logger.info(f"Auth response status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Auth response keys: {list(data.keys())}")
                        
                        if "errorText" in data:
                            logger.error(f"Auth error: {data['errorText']}")
                            return False
                        
                        self.access_token = data.get("accessToken")
                        self.md_access_token = data.get("mdAccessToken")
                        
                        if not self.access_token:
                            logger.error("No accessToken in response!")
                            return False
                        
                        logger.info(f"✅ Got accessToken: {self.access_token[:30]}...")
                        if self.md_access_token:
                            logger.info(f"✅ Got mdAccessToken: {self.md_access_token[:30]}...")
                        else:
                            logger.warning("⚠️  No mdAccessToken in response - market data WebSocket may not work")
                        
                        # Get account information (CRITICAL - from forum thread)
                        # accountSpec = name from auth response
                        # userId = userId from auth response (for subscriptions)
                        # accountId = id from /account/list (for orders/positions)
                        self.account_spec = data.get("name")  # accountSpec
                        self.user_id = data.get("userId")     # userId (for subscriptions)
                        
                        # Get account ID from account list (NOT userId from auth!)
                        await self._get_account_id(session)
                        
                        return True
                    else:
                        text = await response.text()
                        logger.error(f"Auth failed: {response.status} - {text}")
                        return False
                        
        except Exception as e:
            logger.error(f"Auth exception: {e}", exc_info=True)
            return False
    
    async def _get_account_id(self, session: aiohttp.ClientSession):
        """
        Get account ID from account list endpoint
        CRITICAL: accountId comes from /account/list, NOT from userId in auth response!
        From forum thread: accountId = id from /account/list, userId = userId from auth (for subscriptions)
        """
        try:
            async with session.get(
                f"{self.base_url}/account/list",
                headers={"Authorization": f"Bearer {self.access_token}"}
            ) as response:
                if response.status == 200:
                    accounts = await response.json()
                    if accounts and len(accounts) > 0:
                        # accountId is the 'id' field from account list (NOT userId from auth!)
                        self.account_id = accounts[0].get("id")
                        account_name = accounts[0].get("name", "Unknown")
                        logger.info(f"✅ Got account from /account/list:")
                        logger.info(f"   accountId: {self.account_id} (use for orders/positions)")
                        logger.info(f"   accountName: {account_name}")
                        logger.info(f"   accountSpec: {self.account_spec} (from auth response)")
                        logger.info(f"   userId: {self.user_id} (from auth response, use for subscriptions)")
                    else:
                        logger.warning("No accounts found in account list")
                else:
                    text = await response.text()
                    logger.error(f"Failed to get account list: {response.status} - {text}")
        except Exception as e:
            logger.error(f"Could not get account ID: {e}", exc_info=True)
    
    async def get_open_positions(self) -> list:
        """Get open positions from REST API"""
        logger.info("=" * 60)
        logger.info("STEP 2: Fetching open positions from REST API")
        logger.info("=" * 60)
        
        if not self.access_token:
            logger.error("No access token - authenticate first!")
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/position/list",
                    headers={"Authorization": f"Bearer {self.access_token}"}
                ) as response:
                    if response.status == 200:
                        positions = await response.json()
                        logger.info(f"Got {len(positions)} positions from REST API")
                        
                        # Filter to open positions only (netPos != 0)
                        open_positions = [p for p in positions if p.get("netPos", 0) != 0]
                        logger.info(f"Found {len(open_positions)} OPEN positions (netPos != 0)")
                        
                        # Filter by accountId if we have it (from forum thread - important!)
                        if self.account_id:
                            before_count = len(open_positions)
                            open_positions = [p for p in open_positions 
                                            if p.get("accountId") == self.account_id]
                            if len(open_positions) != before_count:
                                logger.info(f"Filtered to {len(open_positions)} positions for account {self.account_id} (was {before_count})")
                        
                        for pos in open_positions:
                            pos_id = pos.get("id")
                            contract_id = pos.get("contractId")
                            net_pos = pos.get("netPos", 0)
                            net_price = pos.get("netPrice")
                            
                            logger.info(f"  Position {pos_id}: contract={contract_id}, netPos={net_pos}, netPrice={net_price}")
                            
                            # Store position
                            self.positions[pos_id] = pos
                            
                            # Get contract info for symbol
                            if contract_id and contract_id not in self.contracts:
                                await self._get_contract_info(session, contract_id)
                        
                        return open_positions
                    else:
                        text = await response.text()
                        logger.error(f"Failed to get positions: {response.status} - {text}")
                        return []
        except Exception as e:
            logger.error(f"Exception getting positions: {e}", exc_info=True)
            return []
    
    async def _get_contract_info(self, session: aiohttp.ClientSession, contract_id: int):
        """Get contract information"""
        try:
            async with session.get(
                f"{self.base_url}/contract/item?id={contract_id}",
                headers={"Authorization": f"Bearer {self.access_token}"}
            ) as response:
                if response.status == 200:
                    contract = await response.json()
                    self.contracts[contract_id] = contract
                    symbol = contract.get("name", "UNKNOWN")
                    logger.info(f"  Contract {contract_id}: {symbol}")
        except Exception as e:
            logger.warning(f"Could not get contract {contract_id}: {e}")
    
    async def connect_user_websocket(self) -> bool:
        """Connect to user data WebSocket for position updates"""
        logger.info("=" * 60)
        logger.info("STEP 3: Connecting to User Data WebSocket")
        logger.info("=" * 60)
        
        if not self.access_token:
            logger.error("No access token - authenticate first!")
            return False
        
        try:
            logger.info(f"Connecting to: {self.ws_user_url}")
            self.ws_user = await websockets.connect(self.ws_user_url)
            logger.info("✅ WebSocket connected")
            
            # Authorize with newline-delimited format
            auth_msg = f"authorize\n0\n\n{self.access_token}"
            logger.info(f"Sending auth: {auth_msg[:50]}...")
            await self.ws_user.send(auth_msg)
            
            # Subscribe to user sync
            subscribe_msg = "user/syncRequest\n1\n\n"
            logger.info(f"Sending subscription: {subscribe_msg}")
            await self.ws_user.send(subscribe_msg)
            
            logger.info("✅ Subscribed to user/syncRequest")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}", exc_info=True)
            return False
    
    async def connect_market_data_websocket(self) -> bool:
        """Connect to market data WebSocket for real-time quotes"""
        logger.info("=" * 60)
        logger.info("STEP 4: Connecting to Market Data WebSocket")
        logger.info("=" * 60)
        
        # Use mdAccessToken if available, fallback to accessToken
        token = self.md_access_token or self.access_token
        if not token:
            logger.error("No token available for market data WebSocket!")
            return False
        
        try:
            logger.info(f"Connecting to: {self.ws_md_url}")
            logger.info(f"Using token: {token[:30]}...")
            self.ws_md = await websockets.connect(self.ws_md_url)
            logger.info("✅ Market data WebSocket connected")
            
            # Authorize
            auth_msg = f"authorize\n0\n\n{token}"
            logger.info(f"Sending auth: {auth_msg[:50]}...")
            await self.ws_md.send(auth_msg)
            
            logger.info("✅ Market data WebSocket authorized")
            return True
            
        except Exception as e:
            logger.error(f"Market data WebSocket connection failed: {e}", exc_info=True)
            return False
    
    async def listen_user_messages(self):
        """Listen for user data WebSocket messages (position updates)"""
        logger.info("=" * 60)
        logger.info("STEP 5: Listening for User Data Updates")
        logger.info("=" * 60)
        
        if not self.ws_user:
            logger.error("User WebSocket not connected!")
            return
        
        try:
            async for message in self.ws_user:
                try:
                    # Handle different message formats
                    if message.startswith('a['):
                        # Socket.IO format: a[{...}]
                        json_str = message[2:-1]  # Remove 'a[' and ']'
                        data = json.loads(json_str)
                        logger.info(f"📨 User WS (Socket.IO): {json.dumps(data, indent=2)[:200]}...")
                    elif message.startswith('o'):
                        # Socket.IO open message
                        logger.info(f"📨 User WS (Socket.IO open): {message}")
                    else:
                        # Try JSON parsing
                        try:
                            data = json.loads(message)
                            logger.info(f"📨 User WS (JSON): {json.dumps(data, indent=2)[:200]}...")
                            
                            # Check for position updates
                            if isinstance(data, dict):
                                event_type = data.get("e")
                                event_data = data.get("d", {})
                                
                                if event_type == "props" and isinstance(event_data, dict):
                                    entity_type = event_data.get("entityType")
                                    entity = event_data.get("entity")
                                    
                                    if entity_type == "Position" and entity:
                                        pos_id = entity.get("id")
                                        net_pos = entity.get("netPos", 0)
                                        open_pnl = entity.get("openPnl")
                                        
                                        logger.info(f"🔄 Position Update: id={pos_id}, netPos={net_pos}, openPnl={open_pnl}")
                                        
                                        # Update position cache
                                        if pos_id:
                                            self.positions[pos_id] = entity
                                            
                        except json.JSONDecodeError:
                            logger.info(f"📨 User WS (raw): {message[:100]}")
                            
                except Exception as e:
                    logger.error(f"Error processing user message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("User WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error listening to user messages: {e}", exc_info=True)
    
    async def listen_market_data_messages(self):
        """Listen for market data WebSocket messages (quotes)"""
        logger.info("=" * 60)
        logger.info("STEP 6: Listening for Market Data Updates")
        logger.info("=" * 60)
        
        if not self.ws_md:
            logger.error("Market data WebSocket not connected!")
            return
        
        try:
            async for message in self.ws_md:
                try:
                    # Handle different message formats
                    if message.startswith('a['):
                        json_str = message[2:-1]
                        data = json.loads(json_str)
                        logger.info(f"📊 Market Data WS (Socket.IO): {json.dumps(data, indent=2)[:200]}...")
                    elif message.startswith('o'):
                        logger.info(f"📊 Market Data WS (Socket.IO open): {message}")
                    else:
                        try:
                            data = json.loads(message)
                            logger.info(f"📊 Market Data WS (JSON): {json.dumps(data, indent=2)[:200]}...")
                        except json.JSONDecodeError:
                            logger.info(f"📊 Market Data WS (raw): {message[:100]}")
                            continue
                    
                    # Extract quote data (data should be defined at this point)
                    # Handle Trade Manager format: {"type": "DATA", "data": {"ticker": "...", "prices": {"ask": ..., "bid": ...}}}
                    # Handle Tradovate format: {"contractId": ..., "ask": ..., "bid": ..., "last": ...}
                    if isinstance(data, dict):
                        # Trade Manager format (wrapped)
                        if "type" in data and "data" in data and data["type"] == "DATA":
                            market_data = data["data"]
                            ticker = market_data.get("ticker")
                            ask = market_data.get("prices", {}).get("ask")
                            bid = market_data.get("prices", {}).get("bid")
                            logger.info(f"📊 Trade Manager format: ticker={ticker}, ask={ask}, bid={bid}")
                            # Note: Would need to map ticker to contract_id
                        
                        # Tradovate format (direct)
                        contract_id = data.get("contractId") or data.get("id")
                        ask = data.get("ask") or data.get("askPrice")
                        bid = data.get("bid") or data.get("bidPrice")
                        last = data.get("last") or data.get("lastPrice") or data.get("price") or data.get("close")
                        
                        if contract_id:
                            # Store quote with all available prices
                            self.quotes[contract_id] = {
                                "contractId": contract_id,
                                "ask": ask,
                                "bid": bid,
                                "last": last,
                                "mid": (ask + bid) / 2 if (ask and bid) else None
                            }
                            
                            # Log what we got
                            price_info = []
                            if last:
                                price_info.append(f"last={last}")
                            if ask:
                                price_info.append(f"ask={ask}")
                            if bid:
                                price_info.append(f"bid={bid}")
                            
                            logger.info(f"💰 Quote Update: contract={contract_id}, {', '.join(price_info)}")
                            
                except Exception as e:
                    logger.error(f"Error processing market data message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Market data WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error listening to market data messages: {e}", exc_info=True)
    
    def calculate_pnl(self, position: Dict) -> Optional[float]:
        """Calculate P&L for a position"""
        pos_id = position.get("id")
        contract_id = position.get("contractId")
        net_pos = position.get("netPos", 0)
        net_price = position.get("netPrice")
        
        if not contract_id or not net_price or net_pos == 0:
            return None
        
        # Try to get openPnl from WebSocket position update first
        if pos_id in self.positions:
            ws_pos = self.positions[pos_id]
            open_pnl = ws_pos.get("openPnl")
            if open_pnl is not None:
                return open_pnl
        
        # Fallback: calculate from current price
        quote = self.quotes.get(contract_id)
        if not quote:
            return None
        
        # Priority: last > mid > bid (for long) / ask (for short)
        current_price = quote.get("last")
        if not current_price:
            # Use mid price if available
            current_price = quote.get("mid")
            if not current_price:
                # Use bid for long, ask for short
                if net_pos > 0:  # Long position
                    current_price = quote.get("bid")
                else:  # Short position
                    current_price = quote.get("ask")
        
        if not current_price:
            return None
        
        # Calculate P&L
        # For long: (current - entry) * size * multiplier
        # For short: (entry - current) * abs(size) * multiplier
        price_diff = current_price - net_price
        pnl = price_diff * net_pos
        
        # Apply multiplier (simplified - would need contract info for exact multiplier)
        # MNQ = $2, MES = $5, NQ = $20, ES = $50 per point
        contract = self.contracts.get(contract_id, {})
        symbol = contract.get("name", "").upper()
        
        if "MNQ" in symbol:
            multiplier = 2.0
        elif "MES" in symbol:
            multiplier = 5.0
        elif "NQ" in symbol:
            multiplier = 20.0
        elif "ES" in symbol:
            multiplier = 50.0
        else:
            multiplier = 1.0  # Default
        
        pnl *= multiplier
        return pnl
    
    async def display_pnl_loop(self):
        """Continuously display P&L for all open positions"""
        logger.info("=" * 60)
        logger.info("STEP 7: Starting P&L Display Loop")
        logger.info("=" * 60)
        
        while True:
            try:
                await asyncio.sleep(1)  # Update every second
                
                if not self.positions:
                    continue
                
                print("\n" + "=" * 60)
                print(f"P&L UPDATE - {datetime.now().strftime('%H:%M:%S')}")
                print("=" * 60)
                
                for pos_id, position in self.positions.items():
                    contract_id = position.get("contractId")
                    net_pos = position.get("netPos", 0)
                    net_price = position.get("netPrice")
                    
                    contract = self.contracts.get(contract_id, {})
                    symbol = contract.get("name", "UNKNOWN")
                    
                    # Get P&L
                    pnl = self.calculate_pnl(position)
                    
                    print(f"\nPosition: {symbol} (ID: {pos_id})")
                    print(f"  Contract ID: {contract_id}")
                    print(f"  Net Position: {net_pos}")
                    print(f"  Entry Price: {net_price}")
                    
                    # Show current price if available
                    quote = self.quotes.get(contract_id)
                    if quote:
                        current_price = quote.get("last") or quote.get("price") or quote.get("close")
                        print(f"  Current Price: {current_price}")
                    
                    # Show P&L
                    if pnl is not None:
                        print(f"  💰 P&L: ${pnl:.2f}")
                    else:
                        print(f"  ⚠️  P&L: Cannot calculate (no price data)")
                    
                    # Show if we have WebSocket position update with openPnl
                    if pos_id in self.positions:
                        ws_pos = self.positions[pos_id]
                        open_pnl = ws_pos.get("openPnl")
                        if open_pnl is not None:
                            print(f"  📡 WebSocket openPnl: ${open_pnl:.2f}")
                
                print("=" * 60)
                
            except Exception as e:
                logger.error(f"Error in P&L display loop: {e}")
    
    async def send_heartbeats(self):
        """Send heartbeat messages to keep WebSocket connections alive"""
        while True:
            try:
                await asyncio.sleep(2.5)  # Every 2.5 seconds
                
                if self.ws_user:
                    try:
                        await self.ws_user.send("\n\n")
                    except:
                        pass
                
                if self.ws_md:
                    try:
                        await self.ws_md.send("\n\n")
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"Error sending heartbeats: {e}")
                break


async def main():
    """Main test function"""
    import os
    
    print("\n" + "=" * 60)
    print("TRADOVATE P&L TRACKING TEST")
    print("=" * 60)
    print("\nThis is a minimal test to verify real-time P&L tracking.")
    print("Make sure you have an OPEN POSITION in Tradovate before running this.\n")
    
    # Get credentials from environment variables or prompt
    username = os.getenv("TRADOVATE_USERNAME")
    password = os.getenv("TRADOVATE_PASSWORD")
    client_id = os.getenv("TRADOVATE_CLIENT_ID")
    client_secret = os.getenv("TRADOVATE_CLIENT_SECRET")
    demo_str = os.getenv("TRADOVATE_DEMO", "y").lower()
    
    if not username:
        username = input("Username: ").strip()
    if not password:
        password = input("Password: ").strip()
    
    use_client_creds = False
    if client_id and client_secret:
        use_client_creds = True
        print(f"Using Client ID/Secret from environment variables")
    else:
        try:
            use_client_creds = input("Use Client ID/Secret? (y/n): ").strip().lower() == 'y'
            if use_client_creds:
                client_id = input("Client ID: ").strip()
                client_secret = input("Client Secret: ").strip()
        except EOFError:
            use_client_creds = False
    
    if demo_str in ('y', 'yes', 'true', '1'):
        demo = True
    elif demo_str in ('n', 'no', 'false', '0'):
        demo = False
    else:
        try:
            demo = input("Use demo account? (y/n): ").strip().lower() == 'y'
        except EOFError:
            demo = True  # Default to demo
            print("Using demo account (default)")
    
    # Create tracker
    tracker = TradovatePNLTracker(demo=demo)
    
    # Authenticate
    try:
        auth_result = await tracker.authenticate(username, password, client_id, client_secret)
        if not auth_result:
            print("❌ Authentication failed!")
            print("\nTroubleshooting:")
            print("1. Check your username and password")
            print("2. Verify you're using the correct account type (demo/live)")
            print("3. If using Client ID/Secret, verify they're correct")
            print("4. Check if your account has API access enabled")
            return
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Get initial positions
    positions = await tracker.get_open_positions()
    if not positions:
        print("\n⚠️  No open positions found!")
        print("Please open a position in Tradovate and run this script again.")
        return
    
    print(f"\n✅ Found {len(positions)} open position(s)")
    
    # Connect WebSockets
    user_ws_ok = await tracker.connect_user_websocket()
    md_ws_ok = await tracker.connect_market_data_websocket()
    
    if not user_ws_ok and not md_ws_ok:
        print("❌ Failed to connect to WebSockets - P&L will not update in real-time")
        return
    
    # Subscribe to quotes for contracts we have positions in
    # Try multiple subscription formats - test will show which one works
    if md_ws_ok:
        for position in positions:
            contract_id = position.get("contractId")
            if contract_id:
                logger.info(f"Attempting to subscribe to quotes for contract {contract_id}")
                
                # Try Format 1: Newline-delimited (like user data WebSocket)
                try:
                    subscribe_msg = f"md/subscribeQuote\n1\n\n{json.dumps({'contractId': contract_id})}"
                    await tracker.ws_md.send(subscribe_msg)
                    logger.info(f"✅ Sent subscription (format 1 - newline-delimited) for contract {contract_id}")
                except Exception as e:
                    logger.warning(f"Format 1 failed: {e}")
                
                # Wait a moment
                await asyncio.sleep(0.2)
                
                # Try Format 2: JSON-RPC
                try:
                    subscribe_msg = json.dumps({
                        "id": 1,
                        "method": "subscribeQuote",
                        "params": {"contractId": contract_id}
                    })
                    await tracker.ws_md.send(subscribe_msg)
                    logger.info(f"✅ Sent subscription (format 2 - JSON-RPC) for contract {contract_id}")
                except Exception as e:
                    logger.warning(f"Format 2 failed: {e}")
                
                # Wait a moment
                await asyncio.sleep(0.2)
                
                # Try Format 3: Array format
                try:
                    subscribe_msg = json.dumps(["subscribeQuote", {"contractId": contract_id}])
                    await tracker.ws_md.send(subscribe_msg)
                    logger.info(f"✅ Sent subscription (format 3 - array) for contract {contract_id}")
                except Exception as e:
                    logger.warning(f"Format 3 failed: {e}")
                
                logger.info(f"📊 Watch for quote updates for contract {contract_id} - will show which format works")
    
    # Start background tasks
    tasks = [
        asyncio.create_task(tracker.listen_user_messages()),
        asyncio.create_task(tracker.listen_market_data_messages()),
        asyncio.create_task(tracker.send_heartbeats()),
        asyncio.create_task(tracker.display_pnl_loop()),
    ]
    
    print("\n✅ P&L tracking started! Press Ctrl+C to stop.\n")
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        try:
            if tracker.ws_user:
                await tracker.ws_user.close()
            if tracker.ws_md:
                await tracker.ws_md.close()
        except:
            pass
        print("✅ Stopped")
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
        try:
            if tracker.ws_user:
                await tracker.ws_user.close()
            if tracker.ws_md:
                await tracker.ws_md.close()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(main())

