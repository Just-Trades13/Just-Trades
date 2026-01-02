"""
Broker WebSocket Manager for Just.Trades Scalability
=====================================================

Manages WebSocket connections to Tradovate for real-time state updates.
Uses the `user/syncrequest` subscription to receive `props` events.

Key features:
- One WS connection per account (not per user)
- Heartbeat management (every 2.5s)
- Auto-reconnect with exponential backoff + jitter
- Feeds events to EventLedger and StateCache

Architecture:
    Tradovate WS → BrokerWSManager → EventLedger → StateCache → UIPublisher
    
Usage:
    from scalability.broker_ws_manager import BrokerWSManager, start_ws_manager
    
    manager = start_ws_manager()
    
    # Add an account to monitor
    await manager.add_account(
        account_id=12345,
        access_token='...',
        is_demo=True
    )
    
    # Events automatically flow to EventLedger and StateCache
"""

import asyncio
import json
import time
import logging
import random
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import websockets
try:
    import websockets
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets library not installed. pip install websockets")


@dataclass
class AccountConnection:
    """Track state for a single account's WebSocket connection"""
    account_id: int
    access_token: str
    is_demo: bool = True
    
    # Connection state
    websocket: Any = None
    connected: bool = False
    authenticated: bool = False
    synced: bool = False
    
    # Reconnect tracking
    reconnect_attempts: int = 0
    last_connect_at: float = 0
    last_message_at: float = 0
    last_heartbeat_at: float = 0
    
    # Stats
    messages_received: int = 0
    errors: int = 0


class BrokerWSManager:
    """
    Manages WebSocket connections to Tradovate for multiple accounts.
    
    Each account gets its own WebSocket connection that:
    1. Authenticates with access token
    2. Subscribes to user/syncrequest
    3. Receives props events for positions/orders/fills
    4. Sends heartbeats every 2.5 seconds
    5. Auto-reconnects on disconnect
    """
    
    def __init__(
        self,
        state_cache=None,
        event_ledger=None,
        heartbeat_interval: float = 2.5,
        max_reconnect_delay: float = 60.0,
        on_event_callback: Callable = None
    ):
        """
        Initialize the WebSocket manager.
        
        Args:
            state_cache: StateCache instance for storing state
            event_ledger: EventLedger instance for recording events
            heartbeat_interval: Seconds between heartbeats (Tradovate requires ~2.5s)
            max_reconnect_delay: Maximum seconds between reconnect attempts
            on_event_callback: Optional callback for each event
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library required. pip install websockets")
        
        # Dependencies (lazy load if not provided)
        self._state_cache = state_cache
        self._event_ledger = event_ledger
        self._on_event = on_event_callback
        
        # Configuration
        self._heartbeat_interval = heartbeat_interval
        self._max_reconnect_delay = max_reconnect_delay
        
        # Account connections
        self._accounts: Dict[int, AccountConnection] = {}
        self._accounts_lock = threading.Lock()
        
        # Event loop management
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._main_task: Optional[asyncio.Task] = None
        
        # Background thread for running async loop
        self._thread: Optional[threading.Thread] = None
        
        # Stats
        self._stats = {
            'total_messages': 0,
            'total_reconnects': 0,
            'total_errors': 0,
        }
        
        # Debug: capture recent raw messages
        self._debug_messages: List[dict] = []
        self._debug_max_messages = 50
        
        logger.info("🔌 BrokerWSManager initialized")
    
    def get_debug_messages(self) -> List[dict]:
        """Get recent raw messages for debugging"""
        return list(self._debug_messages)
    
    def _capture_debug_message(self, account_id: int, message: str):
        """Capture a message for debugging"""
        self._debug_messages.append({
            'account_id': account_id,
            'timestamp': time.time(),
            'length': len(message),
            'preview': message[:500] if message else '',
            'starts_with': message[:20] if message else '',
        })
        # Keep only recent messages
        if len(self._debug_messages) > self._debug_max_messages:
            self._debug_messages = self._debug_messages[-self._debug_max_messages:]
    
    def _get_state_cache(self):
        """Lazy load state cache"""
        if self._state_cache is None:
            from .state_cache import get_global_cache
            self._state_cache = get_global_cache()
        return self._state_cache
    
    def _get_event_ledger(self):
        """Lazy load event ledger"""
        if self._event_ledger is None:
            from .event_ledger import get_ledger
            self._event_ledger = get_ledger()
        return self._event_ledger
    
    # ========================================================================
    # ACCOUNT MANAGEMENT
    # ========================================================================
    
    def add_account(self, account_id: int, access_token: str, is_demo: bool = True):
        """
        Add an account to monitor.
        The connection will be established in the background.
        """
        with self._accounts_lock:
            if account_id in self._accounts:
                logger.warning(f"Account {account_id} already being monitored")
                return
            
            self._accounts[account_id] = AccountConnection(
                account_id=account_id,
                access_token=access_token,
                is_demo=is_demo
            )
            
            logger.info(f"📍 Account {account_id} added for monitoring (demo={is_demo})")
    
    def remove_account(self, account_id: int):
        """Stop monitoring an account"""
        with self._accounts_lock:
            if account_id in self._accounts:
                conn = self._accounts[account_id]
                if conn.websocket:
                    # Schedule close in event loop
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            conn.websocket.close(),
                            self._loop
                        )
                del self._accounts[account_id]
                logger.info(f"📍 Account {account_id} removed from monitoring")
    
    def update_token(self, account_id: int, access_token: str):
        """Update access token for an account (after refresh)"""
        with self._accounts_lock:
            if account_id in self._accounts:
                self._accounts[account_id].access_token = access_token
                logger.debug(f"Token updated for account {account_id}")
    
    def get_account_ids(self) -> List[int]:
        """Get list of monitored account IDs"""
        with self._accounts_lock:
            return list(self._accounts.keys())
    
    # ========================================================================
    # START / STOP
    # ========================================================================
    
    def start(self):
        """Start the WebSocket manager in a background thread"""
        if self._running:
            logger.warning("BrokerWSManager already running")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._run_event_loop,
            daemon=True,
            name="BrokerWS-Manager"
        )
        self._thread.start()
        logger.info("✅ BrokerWSManager started")
    
    def stop(self):
        """Stop the WebSocket manager"""
        self._running = False
        
        # Cancel main task
        if self._main_task and self._loop:
            self._loop.call_soon_threadsafe(self._main_task.cancel)
        
        # Wait for thread to finish
        if self._thread:
            self._thread.join(timeout=5.0)
        
        logger.info("🛑 BrokerWSManager stopped")
    
    def is_running(self) -> bool:
        """Check if manager is running"""
        return self._running and self._thread and self._thread.is_alive()
    
    def _run_event_loop(self):
        """Run the async event loop in background thread"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._main_task = self._loop.create_task(self._main_loop())
            self._loop.run_until_complete(self._main_task)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Event loop error: {e}")
        finally:
            self._loop.close()
    
    # ========================================================================
    # MAIN LOOP
    # ========================================================================
    
    async def _main_loop(self):
        """Main async loop - manages all account connections"""
        logger.info("📡 BrokerWSManager main loop started")
        
        while self._running:
            try:
                # Get accounts that need connections
                accounts_needing_connection = []
                
                with self._accounts_lock:
                    for account_id, conn in self._accounts.items():
                        if not conn.connected:
                            accounts_needing_connection.append(account_id)
                
                # Start connection tasks for disconnected accounts
                connection_tasks = []
                for account_id in accounts_needing_connection:
                    task = asyncio.create_task(self._connect_account(account_id))
                    connection_tasks.append(task)
                
                if connection_tasks:
                    # Wait for connections (with timeout)
                    await asyncio.wait(connection_tasks, timeout=30.0)
                
                # Sleep before next check
                await asyncio.sleep(1.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(5.0)
        
        # Close all connections
        await self._close_all_connections()
        logger.info("📡 BrokerWSManager main loop ended")
    
    async def _close_all_connections(self):
        """Close all WebSocket connections"""
        with self._accounts_lock:
            for conn in self._accounts.values():
                if conn.websocket:
                    try:
                        await conn.websocket.close()
                    except:
                        pass
                conn.connected = False
    
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    async def _connect_account(self, account_id: int):
        """Establish WebSocket connection for an account"""
        with self._accounts_lock:
            conn = self._accounts.get(account_id)
            if not conn:
                return
        
        # Calculate reconnect delay with exponential backoff + jitter
        if conn.reconnect_attempts > 0:
            delay = min(
                self._max_reconnect_delay,
                (2 ** conn.reconnect_attempts) + random.uniform(0, 1)
            )
            logger.info(f"Waiting {delay:.1f}s before reconnecting account {account_id}")
            await asyncio.sleep(delay)
        
        ws_url = self._get_ws_url(conn.is_demo)
        
        try:
            logger.info(f"🔌 Connecting WebSocket for account {account_id} ({ws_url})")
            
            # Connect
            conn.websocket = await websockets.connect(
                ws_url,
                ping_interval=None,  # We handle heartbeats manually
                close_timeout=10
            )
            conn.last_connect_at = time.time()
            
            # Authenticate
            if not await self._authenticate(conn):
                raise Exception("Authentication failed")
            
            # Subscribe to user/syncrequest
            if not await self._subscribe_sync(conn):
                raise Exception("Sync subscription failed")
            
            conn.connected = True
            conn.reconnect_attempts = 0
            self._stats['total_reconnects'] += 1
            
            logger.info(f"✅ Account {account_id} WebSocket connected and synced")
            
            # Start message handler and heartbeat tasks
            await asyncio.gather(
                self._message_handler(conn),
                self._heartbeat_task(conn),
                return_exceptions=True
            )
            
        except Exception as e:
            logger.error(f"Connection error for account {account_id}: {e}")
            conn.connected = False
            conn.authenticated = False
            conn.synced = False
            conn.reconnect_attempts += 1
            conn.errors += 1
            self._stats['total_errors'] += 1
            
            if conn.websocket:
                try:
                    await conn.websocket.close()
                except:
                    pass
                conn.websocket = None
    
    def _get_ws_url(self, is_demo: bool) -> str:
        """Get WebSocket URL for demo or live"""
        if is_demo:
            return "wss://demo.tradovateapi.com/v1/websocket"
        return "wss://api.tradovate.com/v1/websocket"
    
    async def _authenticate(self, conn: AccountConnection) -> bool:
        """Authenticate WebSocket connection using Tradovate's custom format"""
        try:
            # Tradovate WebSocket uses custom format: "authorize\n{request_id}\n\n{token}"
            # NOT JSON! This is critical for authentication to work.
            request_id = 0
            auth_message = f"authorize\n{request_id}\n\n{conn.access_token}"
            
            await conn.websocket.send(auth_message)
            
            # Wait for auth response
            response = await asyncio.wait_for(conn.websocket.recv(), timeout=10.0)
            logger.debug(f"Account {conn.account_id} auth response: {response[:200] if response else 'empty'}")
            
            # Tradovate returns "o" for open, then auth response
            # Successful auth typically contains 'accessToken' or doesn't contain 'error'
            is_ok = response and 'error' not in response.lower() and 'invalid' not in response.lower()
            
            # Also check for explicit success indicators
            if response:
                try:
                    # Sometimes response is JSON after the initial 'o'
                    if response.startswith('a['):
                        # Array format: a["json_string"]
                        inner = response[2:-1]  # Remove a[ and ]
                        data = json.loads(json.loads(inner))
                        is_ok = not data.get('s') or data.get('s') == 200
                    elif response == 'o':
                        # Just 'o' means connection open, wait for next message
                        response2 = await asyncio.wait_for(conn.websocket.recv(), timeout=10.0)
                        logger.debug(f"Account {conn.account_id} auth response2: {response2[:200] if response2 else 'empty'}")
                        is_ok = response2 and 'error' not in response2.lower()
                except:
                    pass
            
            conn.authenticated = is_ok
            
            if is_ok:
                logger.info(f"✅ Account {conn.account_id} authenticated via WebSocket")
            else:
                logger.error(f"❌ Account {conn.account_id} auth failed: {response[:200] if response else 'no response'}")
            
            return is_ok
            
        except asyncio.TimeoutError:
            logger.error(f"Auth timeout for account {conn.account_id}")
            return False
        except Exception as e:
            logger.error(f"Auth error for account {conn.account_id}: {e}")
            return False
    
    async def _subscribe_sync(self, conn: AccountConnection) -> bool:
        """Subscribe to user/syncrequest for real-time updates"""
        try:
            # Tradovate sync request format: "url\nrequest_id\n\njson_body"
            # user/syncrequest needs an empty JSON object as body
            request_id = 1
            sync_message = f"user/syncrequest\n{request_id}\n\n{{}}"
            
            await conn.websocket.send(sync_message)
            logger.info(f"📡 Sent sync request for account {conn.account_id}")
            
            # Wait for initial sync responses - Tradovate may send multiple messages
            try:
                # Read up to 5 messages to capture all sync data
                for i in range(5):
                    try:
                        response = await asyncio.wait_for(conn.websocket.recv(), timeout=5.0)
                        logger.info(f"📡 Sync response #{i+1} for account {conn.account_id}: {len(response)} bytes, starts={response[:30] if response else 'empty'}")
                        
                        # Capture for debugging
                        self._capture_debug_message(conn.account_id, f"SYNC_{i+1}: {response}")
                        
                        # Skip heartbeats and empty responses
                        if response in ('h', 'o', ''):
                            continue
                        
                        # Process the sync response which contains initial state
                        await self._process_sync_response(conn, response)
                        
                        # If we got a substantial response, we might be done
                        if len(response) > 100:
                            break
                            
                    except asyncio.TimeoutError:
                        logger.debug(f"No more sync messages for account {conn.account_id}")
                        break
                
            except Exception as e:
                logger.warning(f"Sync response error for account {conn.account_id}: {e}")
            
            conn.synced = True
            logger.debug(f"Account {conn.account_id} sync subscription complete")
            
            return True
            
        except Exception as e:
            logger.error(f"Sync subscription error for account {conn.account_id}: {e}")
            return False
    
    async def _process_sync_response(self, conn: AccountConnection, response: str):
        """Process the initial sync response containing full state"""
        try:
            # Sync response format varies - could be:
            # - a["json_array"] with multiple entities
            # - Direct JSON with users/accounts/positions/orders
            
            if not response:
                return
            
            # Handle 'o' or 'h' messages
            if response in ('o', 'h'):
                return
            
            # Try to parse the response
            data = None
            
            if response.startswith('a['):
                # Array format
                try:
                    inner = response[1:]  # Remove 'a'
                    array = json.loads(inner)
                    for item in array:
                        if isinstance(item, str):
                            try:
                                data = json.loads(item)
                                await self._process_sync_data(conn, data)
                            except:
                                pass
                        elif isinstance(item, dict):
                            await self._process_sync_data(conn, item)
                except json.JSONDecodeError:
                    pass
            else:
                try:
                    data = json.loads(response)
                    await self._process_sync_data(conn, data)
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON sync response: {response[:200]}")
                    
        except Exception as e:
            logger.error(f"Error processing sync response: {e}")
    
    async def _process_sync_data(self, conn: AccountConnection, data: dict):
        """Process sync data containing positions/orders/etc"""
        if not isinstance(data, dict):
            return
        
        cache = self._get_state_cache()
        ledger = self._get_event_ledger()
        
        # Check for different data formats
        # Format 1: {"d": {"positions": [...], "orders": [...], ...}}
        # Format 2: {"positions": [...], "orders": [...], ...}
        # Format 3: {"s": 200, "d": {...}}  (response with status)
        
        d = data.get('d', data)  # Use 'd' sub-object if present
        
        # Process positions
        positions = d.get('positions', [])
        for pos in positions:
            if isinstance(pos, dict):
                contract_id = str(pos.get('contractId', pos.get('id', 'unknown')))
                cache.update_position(conn.account_id, contract_id, pos)
                ledger.append(conn.account_id, 'position', 'Sync', pos.get('id'), pos)
                logger.info(f"📊 Synced position: {contract_id} netPos={pos.get('netPos', 0)}")
        
        # Process orders
        orders = d.get('orders', [])
        for order in orders:
            if isinstance(order, dict):
                order_id = order.get('id', order.get('orderId'))
                if order_id:
                    cache.update_order(conn.account_id, order_id, order)
                    ledger.append(conn.account_id, 'order', 'Sync', order_id, order)
        
        # Process cash balances
        cash_balances = d.get('cashBalances', [])
        for cb in cash_balances:
            if isinstance(cb, dict) and cb.get('accountId') == conn.account_id:
                cache.update_pnl(conn.account_id, cb)
                ledger.append(conn.account_id, 'cashBalance', 'Sync', cb.get('id'), cb)
                logger.info(f"💰 Synced cashBalance: openPnL={cb.get('openPnL', 0)}")
        
        # Process accounts (may contain nested data)
        accounts = d.get('accounts', [])
        for acc in accounts:
            if isinstance(acc, dict):
                logger.debug(f"📋 Account in sync: {acc.get('id')} - {acc.get('name')}")
        
        if positions or orders or cash_balances:
            logger.info(f"📡 Sync complete for account {conn.account_id}: {len(positions)} positions, {len(orders)} orders, {len(cash_balances)} balances")
    
    # ========================================================================
    # MESSAGE HANDLING
    # ========================================================================
    
    async def _message_handler(self, conn: AccountConnection):
        """Handle incoming messages for an account"""
        try:
            while self._running and conn.connected:
                try:
                    message = await asyncio.wait_for(
                        conn.websocket.recv(),
                        timeout=self._heartbeat_interval * 2
                    )
                    
                    conn.last_message_at = time.time()
                    conn.messages_received += 1
                    self._stats['total_messages'] += 1
                    
                    # Capture for debugging
                    self._capture_debug_message(conn.account_id, message)
                    
                    # Process the message
                    await self._process_message(conn, message)
                    
                except asyncio.TimeoutError:
                    # No message received, but connection might still be alive
                    continue
                except ConnectionClosed:
                    logger.warning(f"WebSocket closed for account {conn.account_id}")
                    break
                    
        except Exception as e:
            logger.error(f"Message handler error for account {conn.account_id}: {e}")
        finally:
            conn.connected = False
    
    async def _process_message(self, conn: AccountConnection, raw_message: str):
        """Process a single WebSocket message"""
        try:
            # Tradovate WebSocket message formats:
            # - 'o' = connection open
            # - 'h' = heartbeat from server
            # - 'a["json"]' = array with JSON payload
            # - 'c[code,"reason"]' = close
            # - Direct JSON for some responses
            
            if not raw_message:
                return
            
            # Handle special single-char messages
            if raw_message == 'o':
                logger.debug(f"Account {conn.account_id}: connection open")
                return
            elif raw_message == 'h':
                logger.debug(f"Account {conn.account_id}: server heartbeat")
                return
            elif raw_message.startswith('c['):
                logger.warning(f"Account {conn.account_id}: connection closed by server: {raw_message}")
                conn.connected = False
                return
            
            # Handle array format: a["json_string"]
            data = None
            if raw_message.startswith('a['):
                try:
                    # Extract inner JSON array, then parse the first element
                    inner = raw_message[1:]  # Remove 'a' prefix
                    array = json.loads(inner)
                    if array and isinstance(array, list):
                        for item in array:
                            if isinstance(item, str):
                                # Parse the JSON string inside
                                try:
                                    data = json.loads(item)
                                    if isinstance(data, dict):
                                        await self._handle_dict_message(conn, data)
                                    elif isinstance(data, list):
                                        for d in data:
                                            if isinstance(d, dict):
                                                await self._handle_dict_message(conn, d)
                                except json.JSONDecodeError:
                                    logger.debug(f"Non-JSON in array: {item[:100]}")
                            elif isinstance(item, dict):
                                await self._handle_dict_message(conn, item)
                    return
                except json.JSONDecodeError:
                    logger.debug(f"Failed to parse array message: {raw_message[:100]}")
            
            # Try direct JSON parse
            try:
                data = json.loads(raw_message)
            except json.JSONDecodeError:
                logger.debug(f"Non-JSON message: {raw_message[:100]}")
                return
            
            # Handle different message types
            if isinstance(data, dict):
                await self._handle_dict_message(conn, data)
            elif isinstance(data, list):
                # Could be a batch of messages
                for item in data:
                    if isinstance(item, dict):
                        await self._handle_dict_message(conn, item)
                        
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    async def _handle_dict_message(self, conn: AccountConnection, data: dict):
        """Handle a dictionary message"""
        event_type = data.get('e')
        
        if event_type == 'props':
            # This is a state update event
            await self._handle_props_event(conn, data)
        elif event_type == 'clock':
            # Clock sync message, ignore
            pass
        elif 's' in data:
            # Response to a request (has status code)
            logger.debug(f"Response message: {data.get('s')} - {data.get('i')}")
        else:
            # Unknown message type, log but don't crash
            logger.debug(f"Unknown message type for account {conn.account_id}: {list(data.keys())}")
    
    async def _handle_props_event(self, conn: AccountConnection, data: dict):
        """
        Handle a props event (state update from Tradovate).
        
        Expected format:
            {"e": "props", "d": {"entityType": "position", "event": "Updated", "entity": {...}}}
        """
        try:
            d = data.get('d', {})
            entity_type = d.get('entityType')
            event_type = d.get('event')
            entity = d.get('entity', {})
            entity_id = entity.get('id')
            
            if not entity_type:
                return
            
            # Record in event ledger
            ledger = self._get_event_ledger()
            ledger.append(
                account_id=conn.account_id,
                entity_type=entity_type,
                event_type=event_type,
                entity_id=entity_id,
                raw_data=entity
            )
            
            # Update state cache based on entity type
            cache = self._get_state_cache()
            
            if entity_type == 'position':
                self._update_position_cache(cache, conn.account_id, entity, event_type)
            elif entity_type == 'order':
                self._update_order_cache(cache, conn.account_id, entity, event_type)
            elif entity_type == 'fill':
                self._update_fill_cache(cache, conn.account_id, entity)
            elif entity_type == 'cashBalance':
                cache.update_pnl(conn.account_id, entity)
            elif entity_type == 'marginSnapshot':
                cache.update_balance(conn.account_id, entity)
            # Add more entity types as needed
            
            # Call external callback if provided
            if self._on_event:
                try:
                    self._on_event(conn.account_id, entity_type, event_type, entity)
                except Exception as e:
                    logger.warning(f"Event callback error: {e}")
            
            logger.debug(f"Props event: {entity_type}.{event_type} for account {conn.account_id}")
            
        except Exception as e:
            logger.error(f"Error handling props event: {e}")
    
    def _update_position_cache(self, cache, account_id: int, entity: dict, event_type: str):
        """Update position in state cache"""
        contract_id = str(entity.get('contractId', entity.get('id', 'unknown')))
        net_pos = entity.get('netPos', 0)
        
        if event_type == 'Deleted' or net_pos == 0:
            cache.remove_position(account_id, contract_id)
        else:
            cache.update_position(account_id, contract_id, {
                'id': entity.get('id'),
                'account_id': account_id,
                'contract_id': entity.get('contractId'),
                'net_pos': net_pos,
                'net_price': entity.get('netPrice'),
                'timestamp': entity.get('timestamp'),
            })
    
    def _update_order_cache(self, cache, account_id: int, entity: dict, event_type: str):
        """Update order in state cache"""
        order_id = entity.get('id')
        if not order_id:
            return
        
        status = entity.get('status', entity.get('ordStatus'))
        
        # Remove completed/cancelled orders from "open" cache
        if status in ('Filled', 'Cancelled', 'Rejected', 'Expired') or event_type == 'Deleted':
            cache.remove_order(account_id, order_id)
        else:
            cache.update_order(account_id, order_id, {
                'id': order_id,
                'account_id': account_id,
                'contract_id': entity.get('contractId'),
                'action': entity.get('action'),
                'order_type': entity.get('orderType'),
                'quantity': entity.get('qty', entity.get('orderQty')),
                'price': entity.get('price'),
                'stop_price': entity.get('stopPrice'),
                'status': status,
                'timestamp': entity.get('timestamp'),
            })
    
    def _update_fill_cache(self, cache, account_id: int, entity: dict):
        """Add fill to state cache"""
        fill_id = entity.get('id')
        if fill_id:
            cache.add_fill(account_id, fill_id, {
                'id': fill_id,
                'account_id': account_id,
                'order_id': entity.get('orderId'),
                'contract_id': entity.get('contractId'),
                'quantity': entity.get('qty'),
                'price': entity.get('price'),
                'timestamp': entity.get('timestamp'),
                'action': entity.get('action'),
            })
    
    # ========================================================================
    # HEARTBEAT
    # ========================================================================
    
    async def _heartbeat_task(self, conn: AccountConnection):
        """Send heartbeats to keep connection alive"""
        try:
            while self._running and conn.connected:
                await asyncio.sleep(self._heartbeat_interval)
                
                if conn.websocket and conn.connected:
                    try:
                        # Tradovate expects empty array as heartbeat
                        await conn.websocket.send('[]')
                        conn.last_heartbeat_at = time.time()
                    except Exception as e:
                        logger.warning(f"Heartbeat failed for account {conn.account_id}: {e}")
                        conn.connected = False
                        break
                        
        except Exception as e:
            logger.error(f"Heartbeat task error for account {conn.account_id}: {e}")
    
    # ========================================================================
    # STATS & HEALTH
    # ========================================================================
    
    def get_stats(self) -> dict:
        """Get manager statistics"""
        with self._accounts_lock:
            accounts_status = {
                acc_id: {
                    'connected': conn.connected,
                    'authenticated': conn.authenticated,
                    'synced': conn.synced,
                    'messages': conn.messages_received,
                    'errors': conn.errors,
                    'last_message': conn.last_message_at,
                }
                for acc_id, conn in self._accounts.items()
            }
        
        return {
            **self._stats,
            'running': self.is_running(),
            'accounts': len(self._accounts),
            'connected_accounts': sum(1 for c in self._accounts.values() if c.connected),
            'accounts_status': accounts_status,
        }
    
    def health_check(self) -> dict:
        """Check manager health"""
        with self._accounts_lock:
            connected = sum(1 for c in self._accounts.values() if c.connected)
            total = len(self._accounts)
        
        return {
            'healthy': self.is_running() and (connected == total or total == 0),
            'running': self.is_running(),
            'accounts_total': total,
            'accounts_connected': connected,
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_global_manager: Optional[BrokerWSManager] = None


def start_ws_manager(**kwargs) -> BrokerWSManager:
    """Start the global WebSocket manager"""
    global _global_manager
    
    if _global_manager and _global_manager.is_running():
        logger.warning("BrokerWSManager already running")
        return _global_manager
    
    _global_manager = BrokerWSManager(**kwargs)
    _global_manager.start()
    return _global_manager


def get_ws_manager() -> Optional[BrokerWSManager]:
    """Get the global WebSocket manager"""
    return _global_manager


def stop_ws_manager():
    """Stop the global WebSocket manager"""
    global _global_manager
    if _global_manager:
        _global_manager.stop()
        _global_manager = None
