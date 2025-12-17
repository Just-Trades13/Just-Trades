"""
Position WebSocket Listener
============================
Maintains real-time broker positions in Redis via WebSocket.
This is the SOURCE OF TRUTH for position data.

Run as a background service:
    python position_websocket_listener.py

Environment variables:
    REDIS_URL - Redis connection URL
    DATABASE_URL - PostgreSQL URL (or uses SQLite)
"""

import os
import sys
import json
import asyncio
import logging
import signal
from datetime import datetime
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('position_listener')

try:
    import redis
    import websockets
    from production_db import db
except ImportError as e:
    logger.error(f"Missing dependencies: {e}")
    logger.error("Run: pip install redis websockets")
    sys.exit(1)


class PositionWebSocketListener:
    """
    Listens to Tradovate WebSocket for position updates.
    Updates Redis cache in real-time so all services have fresh position data.
    """
    
    def __init__(self):
        self.redis_client = None
        self.running = False
        self.accounts = {}  # account_id -> {token, is_demo, subaccount_id}
        self.ws_connections = {}  # account_id -> websocket
        
        self._init_redis()
        self._load_accounts()
    
    def _init_redis(self):
        """Initialize Redis connection."""
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("✅ Redis connected")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.redis_client = None
    
    def _load_accounts(self):
        """Load all linked broker accounts from database."""
        try:
            accounts = db.execute('''
                SELECT a.id, a.tradovate_token, t.is_demo, t.subaccount_id, t.subaccount_name
                FROM accounts a
                JOIN traders t ON t.account_id = a.id
                WHERE a.tradovate_token IS NOT NULL
                AND t.subaccount_id IS NOT NULL
            ''', fetch='all')
            
            for acc in (accounts or []):
                self.accounts[acc['id']] = {
                    'token': acc['tradovate_token'],
                    'is_demo': acc['is_demo'],
                    'subaccount_id': acc['subaccount_id'],
                    'name': acc.get('subaccount_name', f"Account {acc['id']}")
                }
            
            logger.info(f"📊 Loaded {len(self.accounts)} broker accounts")
        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")
    
    def _get_ws_url(self, is_demo: bool) -> str:
        """Get WebSocket URL for account type."""
        if is_demo:
            return "wss://demo.tradovateapi.com/v1/websocket"
        else:
            return "wss://live.tradovateapi.com/v1/websocket"
    
    async def _handle_position_update(self, account_id: int, data: Dict[str, Any]):
        """Handle position update from WebSocket."""
        try:
            # Extract position data
            net_pos = data.get('netPos', 0)
            net_price = data.get('netPrice', 0)
            contract_id = data.get('contractId')
            
            # Get symbol from contract (simplified - in production, cache contract lookups)
            symbol = data.get('symbol', f"contract_{contract_id}")
            
            # Update Redis
            if self.redis_client:
                key = f"broker_position:{account_id}:{symbol}"
                position_data = {
                    'qty': net_pos,
                    'avg_price': net_price,
                    'contract_id': contract_id,
                    'updated_at': datetime.utcnow().isoformat(),
                    'raw': data
                }
                self.redis_client.set(key, json.dumps(position_data))
                
                # Also set by contract_id for faster lookups
                if contract_id:
                    key2 = f"broker_position:{account_id}:contract:{contract_id}"
                    self.redis_client.set(key2, json.dumps(position_data))
                
                logger.info(f"📊 Position updated: Account {account_id} | {symbol} | {net_pos} @ {net_price}")
        except Exception as e:
            logger.error(f"Error handling position update: {e}")
    
    async def _handle_fill(self, account_id: int, data: Dict[str, Any]):
        """Handle fill notification - triggers position refresh."""
        logger.info(f"💰 Fill received: Account {account_id} | {data.get('qty')} @ {data.get('price')}")
        
        # Invalidate any cached calculations
        if self.redis_client:
            # Signal that a fill happened (other services can subscribe to this)
            self.redis_client.publish('fills', json.dumps({
                'account_id': account_id,
                'data': data,
                'timestamp': datetime.utcnow().isoformat()
            }))
    
    async def _ws_listener(self, account_id: int, account_info: Dict[str, Any]):
        """WebSocket listener for a single account."""
        ws_url = self._get_ws_url(account_info['is_demo'])
        token = account_info['token']
        
        while self.running:
            try:
                async with websockets.connect(ws_url) as ws:
                    self.ws_connections[account_id] = ws
                    logger.info(f"🔌 WebSocket connected: Account {account_id}")
                    
                    # Authenticate
                    auth_msg = f"authorize\n1\n\n{token}"
                    await ws.send(auth_msg)
                    
                    # Subscribe to positions
                    sub_msg = f"user/syncrequest\n2\n\n{{\"users\":[{account_info['subaccount_id']}]}}"
                    await ws.send(sub_msg)
                    
                    # Listen for messages
                    async for message in ws:
                        try:
                            if message.startswith('o'):
                                continue  # Heartbeat
                            
                            # Parse message
                            if '\n' in message:
                                parts = message.split('\n')
                                if len(parts) >= 4:
                                    event_type = parts[0]
                                    payload = parts[3] if len(parts) > 3 else '{}'
                                    
                                    try:
                                        data = json.loads(payload)
                                    except:
                                        data = {}
                                    
                                    # Handle position updates
                                    if 'position' in event_type.lower():
                                        await self._handle_position_update(account_id, data)
                                    elif 'fill' in event_type.lower():
                                        await self._handle_fill(account_id, data)
                                        
                        except Exception as e:
                            logger.debug(f"Message parse error: {e}")
                            
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"⚠️ WebSocket disconnected: Account {account_id} - reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"WebSocket error for account {account_id}: {e}")
                await asyncio.sleep(10)
        
        logger.info(f"WebSocket listener stopped for account {account_id}")
    
    async def start(self):
        """Start listening to all accounts."""
        self.running = True
        
        if not self.accounts:
            logger.warning("No accounts to monitor - waiting for accounts to be added...")
            while self.running and not self.accounts:
                await asyncio.sleep(30)
                self._load_accounts()
        
        # Start a listener for each account
        tasks = []
        for account_id, account_info in self.accounts.items():
            task = asyncio.create_task(self._ws_listener(account_id, account_info))
            tasks.append(task)
        
        logger.info(f"🚀 Started {len(tasks)} WebSocket listeners")
        
        # Wait for all tasks
        await asyncio.gather(*tasks)
    
    def stop(self):
        """Stop all listeners."""
        self.running = False
        for ws in self.ws_connections.values():
            asyncio.create_task(ws.close())
        logger.info("🛑 Position listener stopped")


async def main():
    """Main entry point."""
    listener = PositionWebSocketListener()
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, listener.stop)
    
    logger.info("=" * 50)
    logger.info("POSITION WEBSOCKET LISTENER")
    logger.info("=" * 50)
    logger.info("This service maintains real-time broker positions in Redis.")
    logger.info("All other services use Redis as the source of truth.")
    logger.info("=" * 50)
    
    await listener.start()


if __name__ == '__main__':
    asyncio.run(main())
