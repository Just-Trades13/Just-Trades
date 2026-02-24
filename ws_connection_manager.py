"""
Shared WebSocket Connection Manager for Tradovate
==================================================
Consolidates all Tradovate WebSocket connections into ONE connection per token.

BEFORE: 3 services x N accounts = 6-12 WebSocket connections
  - ws_position_monitor.py: 1 WS per token (position/fill/order events)
  - ws_leader_monitor.py: 1 WS per leader (fill/order events for copy trading)
  - live_max_loss_monitor.py: 1 WS per account (cashBalance for max loss)

AFTER: 1-2 WebSocket connections (one per unique token)
  - SharedConnection handles connect/auth/subscribe/heartbeat/reconnect
  - Multiple Listeners registered on each SharedConnection
  - Each listener filters for the events it cares about

This eliminates HTTP 429 rate limit errors caused by duplicate connections
sharing the same Tradovate token (Rule 16).

Usage:
    from ws_connection_manager import get_connection_manager, Listener

    class MyListener(Listener):
        @property
        def listener_id(self) -> str:
            return 'my-listener-1'

        async def on_message(self, items: list, raw_message: str):
            for data in items:
                # process pre-parsed message items
                pass

    manager = get_connection_manager()
    manager.start()
    manager.register_listener(
        token='...', is_demo=True,
        subaccount_ids=[12345], listener=MyListener(),
        db_account_ids=[1]
    )
"""

import abc
import asyncio
import json
import logging
import os
import random
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List, Set

logger = logging.getLogger('ws_connection_manager')

# Try to import websockets
try:
    import websockets
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets library not installed — connection manager disabled")


def _is_futures_market_likely_open() -> bool:
    """Check if US futures markets are likely open (for dead-subscription detection).

    US futures: Sunday 6 PM ET -> Friday 5 PM ET, with daily 5-6 PM ET break.
    Returns True during trading hours, False during known closed periods.
    Used to avoid unnecessary reconnects when 0 data is expected.
    """
    from datetime import timedelta as _td
    utc_now = datetime.now(timezone.utc)
    et_now = utc_now + _td(hours=-5)
    weekday = et_now.weekday()  # 0=Mon, 6=Sun
    hour = et_now.hour

    if weekday == 5:  # Saturday: always closed
        return False
    if weekday == 6 and hour < 18:  # Sunday before 6 PM ET
        return False
    if weekday == 4 and hour >= 17:  # Friday after 5 PM ET
        return False
    if weekday in (0, 1, 2, 3) and 17 <= hour < 18:  # Daily break 5-6 PM ET
        return False
    return True


# ============================================================================
# LISTENER ABC — Interface for services that consume WebSocket messages
# ============================================================================

class Listener(abc.ABC):
    """Abstract base class for WebSocket message consumers.

    Each service (position monitor, leader monitor, max loss monitor)
    implements this interface and registers with the connection manager.
    """

    @property
    @abc.abstractmethod
    def listener_id(self) -> str:
        """Unique identifier for this listener (e.g., 'position-monitor', 'leader-5')."""
        ...

    @abc.abstractmethod
    async def on_message(self, items: list, raw_message: str):
        """Called when a WebSocket message is received.

        Args:
            items: Pre-parsed list of dict items from the message.
                   Message parsing is done ONCE in SharedConnection, not per-listener.
            raw_message: The original raw message string (for edge cases).
        """
        ...

    async def on_connected(self, token_key: str):
        """Called when the SharedConnection (re)connects and authenticates.
        Override in subclass if needed.
        """
        pass

    async def on_disconnected(self, token_key: str):
        """Called when the SharedConnection disconnects.
        Override in subclass if needed.
        """
        pass


# ============================================================================
# SHARED CONNECTION — One WebSocket per Tradovate token
# ============================================================================

class SharedConnection:
    """Manages a single Tradovate WebSocket connection shared by multiple listeners.

    Lifecycle:
    1. Connect -> wait for 'o' frame
    2. Authenticate: authorize\\n0\\n\\n{token} -> wait for a[{"i":0,"s":200}]
    3. Subscribe: user/syncrequest with UNION of all listener accounts (no entityTypes filter)
    4. Heartbeat [] every 2.5s, server timeout 10s
    5. Dead-sub detection: 3 x 30s zero-data windows during market hours
    6. Proactive reconnect at 70 min (before 85-min token expiry)
    7. Exponential backoff: 1->2->4->8->...->60s max
    8. Fresh token from DB before each reconnect
    """

    def __init__(self, token_key: str, access_token: str, is_demo: bool,
                 db_account_ids: List[int]):
        self.token_key = token_key  # Short hash for logging
        self.access_token = access_token
        self.is_demo = is_demo
        self.db_account_ids = list(db_account_ids)  # For fresh token lookup

        # WebSocket URL
        self.ws_url = ("wss://demo.tradovateapi.com/v1/websocket"
                       if is_demo else "wss://live.tradovateapi.com/v1/websocket")

        # Connection state
        self.websocket = None
        self.connected = False
        self.authenticated = False
        self._running = False
        self._last_heartbeat = 0
        self._request_id = 0
        self._connection_time = None

        # Subscribed accounts — UNION of all listeners' requested subaccount_ids
        self._subscribed_accounts: Set[int] = set()

        # Registered listeners
        self._listeners: Dict[str, Listener] = {}  # listener_id -> Listener
        self._listener_accounts: Dict[str, Set[int]] = {}  # listener_id -> set of subaccount_ids

        # Dynamic subscription: flag when new accounts need to be added
        self._pending_account_adds = False

        # Dead-subscription detection
        self._zero_data_windows = 0

        # Max connection: 60-75 min (jittered, before 85-min token expiry)
        # Jitter prevents all connections from reconnecting at the same time
        self._max_connection_seconds = random.randint(3600, 4500)

        # Stats
        self._msg_count = 0
        self._data_msg_count = 0
        self._last_stats_log = 0
        self._last_server_msg = 0

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def add_listener(self, listener: Listener, subaccount_ids: Set[int]):
        """Register a listener and its requested accounts. Thread-safe via event loop."""
        lid = listener.listener_id
        self._listeners[lid] = listener
        self._listener_accounts[lid] = set(subaccount_ids)

        # Check if new accounts need to be subscribed
        new_accounts = subaccount_ids - self._subscribed_accounts
        if new_accounts:
            self._pending_account_adds = True
            logger.info(f"[{self.token_key}] Listener '{lid}' added {len(new_accounts)} new accounts: {new_accounts}")

    def remove_listener(self, listener_id: str):
        """Unregister a listener."""
        self._listeners.pop(listener_id, None)
        self._listener_accounts.pop(listener_id, None)
        logger.info(f"[{self.token_key}] Listener '{listener_id}' removed")

    def _get_all_accounts(self) -> List[int]:
        """Get UNION of all listeners' requested subaccount_ids."""
        all_accounts: Set[int] = set()
        for accounts in self._listener_accounts.values():
            all_accounts.update(accounts)
        return sorted(all_accounts)

    async def connect(self) -> bool:
        """Connect and authenticate to Tradovate WebSocket."""
        if not WEBSOCKETS_AVAILABLE:
            return False

        all_accounts = self._get_all_accounts()
        if not all_accounts:
            logger.warning(f"[{self.token_key}] No accounts to subscribe — skipping connect")
            return False

        try:
            logger.info(f"[{self.token_key}] Connecting to Tradovate "
                        f"({len(all_accounts)} accounts, {len(self._listeners)} listeners, "
                        f"{'demo' if self.is_demo else 'live'})")

            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=5
            )
            self.connected = True
            self._connection_time = datetime.now(timezone.utc)

            # Wait for 'o' (open) frame
            open_frame = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            logger.debug(f"[{self.token_key}] Open frame: {open_frame[:50] if open_frame else 'empty'}")

            # Authenticate with request ID 0
            auth_msg = f"authorize\n0\n\n{self.access_token}"
            await self.websocket.send(auth_msg)

            # Wait for auth response
            auth_success = False
            for _ in range(10):
                response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
                if not response or response in ('o', 'h', '[]'):
                    continue

                if response.startswith('a['):
                    try:
                        array = json.loads(response[1:])
                        for item in array:
                            if isinstance(item, dict) and item.get('i') == 0 and item.get('s') == 200:
                                auth_success = True
                                break
                            elif isinstance(item, str):
                                parsed = json.loads(item)
                                if isinstance(parsed, dict) and parsed.get('i') == 0 and parsed.get('s') == 200:
                                    auth_success = True
                                    break
                    except (json.JSONDecodeError, TypeError):
                        pass

                if auth_success:
                    break

            if auth_success:
                self.authenticated = True
                logger.info(f"[{self.token_key}] Authenticated")
                await self._subscribe_sync(all_accounts)

                # Notify all listeners
                for listener in list(self._listeners.values()):
                    try:
                        await listener.on_connected(self.token_key)
                    except Exception as e:
                        logger.error(f"[{self.token_key}] Listener {listener.listener_id} on_connected error: {e}")

                return True
            else:
                logger.error(f"[{self.token_key}] Auth failed — no s:200 response")
                return False

        except Exception as e:
            logger.error(f"[{self.token_key}] Connection error: {e}")
            return False

    async def _subscribe_sync(self, account_ids: List[int]):
        """Subscribe to user/syncrequest for ALL accounts on this token.

        No entityTypes filter — Tradovate sends ALL entity types by default.
        This ensures cashBalance (max loss), orderStrategy (leader), and
        position/fill/order (position monitor) are all received.
        """
        try:
            req_id = self._next_request_id()
            sync_body = json.dumps({
                "accounts": [int(sid) for sid in account_ids]
            })
            sync_msg = f"user/syncrequest\n{req_id}\n\n{sync_body}"
            await self.websocket.send(sync_msg)
            self._subscribed_accounts = set(account_ids)
            self._pending_account_adds = False
            logger.info(f"[{self.token_key}] Subscribed to sync for {len(account_ids)} accounts: {account_ids}")

            # Wait for subscription response
            for _ in range(5):
                response = await asyncio.wait_for(self.websocket.recv(), timeout=10)
                if response and response not in ('o', 'h', '[]'):
                    logger.debug(f"[{self.token_key}] Sync response: "
                                 f"{response[:300] if response else 'empty'}")
                    break
        except Exception as e:
            logger.error(f"[{self.token_key}] Failed to subscribe: {e}")

    async def run(self):
        """Main monitoring loop — receive messages and dispatch to all listeners."""
        self._running = True
        self._last_server_msg = time.time()
        self._msg_count = 0
        self._data_msg_count = 0
        self._last_stats_log = time.time()

        while self._running and self.connected:
            try:
                now = time.time()

                # Heartbeat every 2.5s
                if now - self._last_heartbeat > 2.5:
                    await self.websocket.send("[]")
                    self._last_heartbeat = now

                    # Check for pending account additions (dynamic subscription)
                    if self._pending_account_adds:
                        new_accounts = self._get_all_accounts()
                        if set(new_accounts) != self._subscribed_accounts:
                            logger.info(f"[{self.token_key}] Re-subscribing with expanded account list: "
                                        f"{len(self._subscribed_accounts)} -> {len(new_accounts)}")
                            await self._subscribe_sync(new_accounts)

                # Server timeout: 10s no message = dead
                if now - self._last_server_msg > 10.0:
                    logger.warning(f"[{self.token_key}] Server timeout — no message in 10s")
                    self.connected = False
                    break

                # Proactive reconnect before token expiry (70 min)
                if self._connection_time:
                    age_seconds = (datetime.now(timezone.utc) - self._connection_time).total_seconds()
                    if age_seconds > self._max_connection_seconds:
                        logger.info(f"[{self.token_key}] Proactive reconnect "
                                    f"(age {int(age_seconds)}s > {self._max_connection_seconds}s)")
                        self.connected = False
                        break

                # Stats + dead-subscription detection every 30s
                if now - self._last_stats_log > 30.0:
                    listener_names = [lid for lid in self._listeners.keys()]
                    logger.info(f"[{self.token_key}] WS stats: {self._msg_count} msgs "
                                f"({self._data_msg_count} data) in 30s, "
                                f"listeners={listener_names}")

                    if self._data_msg_count == 0:
                        self._zero_data_windows += 1
                        if self._zero_data_windows >= 10 and _is_futures_market_likely_open():
                            logger.warning(f"[{self.token_key}] No data for "
                                           f"{self._zero_data_windows * 30}s — forcing reconnect")
                            self.connected = False
                            break
                        elif self._zero_data_windows == 10:
                            logger.info(f"[{self.token_key}] 0 data but market closed — staying connected")
                    else:
                        self._zero_data_windows = 0

                    self._msg_count = 0
                    self._data_msg_count = 0
                    self._last_stats_log = now

                # Receive messages
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    self._last_server_msg = time.time()
                    self._msg_count += 1
                    await self._dispatch_message(message)
                except asyncio.TimeoutError:
                    continue

            except ConnectionClosed:
                logger.warning(f"[{self.token_key}] WebSocket closed")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"[{self.token_key}] Monitor loop error: {e}")

        self._running = False

    async def _dispatch_message(self, raw_message: str):
        """Parse message ONCE, then dispatch pre-parsed items to all listeners."""
        if not raw_message or raw_message in ('o', 'h', '[]'):
            return

        self._data_msg_count += 1

        # Parse the message once (same proven pattern from ws_position_monitor.py)
        items = []
        try:
            if raw_message.startswith('a['):
                array = json.loads(raw_message[1:])
                for element in array:
                    if isinstance(element, dict):
                        items.append(element)
                    elif isinstance(element, str):
                        try:
                            parsed = json.loads(element)
                            if isinstance(parsed, dict):
                                items.append(parsed)
                        except (json.JSONDecodeError, TypeError):
                            pass
            elif '{' in raw_message:
                json_start = raw_message.find('{')
                parsed = json.loads(raw_message[json_start:])
                if isinstance(parsed, dict):
                    items.append(parsed)
        except json.JSONDecodeError:
            return
        except Exception as e:
            logger.debug(f"[{self.token_key}] Message parse error: {e}")
            return

        if not items and not raw_message.startswith('a['):
            return

        # Dispatch to ALL registered listeners — each listener's errors are isolated
        for listener in list(self._listeners.values()):
            try:
                await listener.on_message(items, raw_message)
            except Exception as e:
                logger.error(f"[{self.token_key}] Listener '{listener.listener_id}' error: {e}")

    async def close(self):
        """Close the WebSocket connection and notify listeners."""
        self._running = False

        # Notify all listeners
        for listener in list(self._listeners.values()):
            try:
                await listener.on_disconnected(self.token_key)
            except Exception as e:
                logger.error(f"[{self.token_key}] Listener {listener.listener_id} on_disconnected error: {e}")

        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
        self.connected = False
        self.authenticated = False


# ============================================================================
# CONNECTION MANAGER — Singleton managing all SharedConnections
# ============================================================================

# Module-level state
_manager_instance = None
_manager_lock = threading.Lock()


class TradovateConnectionManager:
    """Singleton manager for all Tradovate WebSocket connections.

    Runs one daemon thread with one asyncio event loop.
    All SharedConnections run as tasks in that event loop.
    Thread-safe registration via asyncio.run_coroutine_threadsafe().
    """

    def __init__(self):
        self._connections: Dict[str, SharedConnection] = {}  # token_key -> SharedConnection
        self._thread = None
        self._loop = None
        self._running = False
        self._started = False

        # Map token_key -> (access_token, is_demo, db_account_ids)
        self._token_info: Dict[str, dict] = {}

        # Track pending registrations (before event loop is ready)
        self._pending_registrations: List[dict] = []
        self._loop_ready = threading.Event()

    def start(self):
        """Start the connection manager daemon thread. Idempotent."""
        if self._started:
            logger.debug("Connection manager already started")
            return

        self._started = True
        self._running = True

        def _thread_target():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop_ready.set()
            try:
                self._loop.run_until_complete(self._run_manager())
            except Exception as e:
                logger.error(f"Connection manager thread error: {e}")
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=_thread_target, daemon=True,
                                         name="ws-connection-manager")
        self._thread.start()
        logger.info("WebSocket connection manager daemon thread started")

    def register_listener(self, token: str, is_demo: bool,
                          subaccount_ids: List[int], listener: Listener,
                          db_account_ids: List[int]):
        """Register a listener for a Tradovate token. Thread-safe.

        If the event loop is running, schedules registration on it.
        If not yet started, queues for processing when loop starts.
        """
        reg = {
            'token': token,
            'is_demo': is_demo,
            'subaccount_ids': subaccount_ids,
            'listener': listener,
            'db_account_ids': db_account_ids,
        }

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._async_register(reg), self._loop
            )
        else:
            self._pending_registrations.append(reg)
            logger.info(f"Queued listener '{listener.listener_id}' for registration "
                        f"(event loop not ready)")

    def unregister_listener(self, listener_id: str):
        """Unregister a listener from all connections. Thread-safe."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._async_unregister(listener_id), self._loop
            )

    async def _async_register(self, reg: dict):
        """Register a listener on the event loop thread."""
        token = reg['token']
        is_demo = reg['is_demo']
        subaccount_ids = set(int(s) for s in reg['subaccount_ids'])
        listener = reg['listener']
        db_account_ids = reg['db_account_ids']

        # Token key for connection lookup
        token_key = f"...{token[-8:]}" if len(token) > 8 else token

        # Get or create SharedConnection for this token
        if token_key not in self._connections:
            conn = SharedConnection(
                token_key=token_key,
                access_token=token,
                is_demo=is_demo,
                db_account_ids=db_account_ids,
            )
            self._connections[token_key] = conn
            self._token_info[token_key] = {
                'access_token': token,
                'is_demo': is_demo,
                'db_account_ids': list(db_account_ids),
            }
            logger.info(f"Created SharedConnection for token {token_key} "
                        f"({'demo' if is_demo else 'live'})")

        conn = self._connections[token_key]

        # Merge db_account_ids
        existing_db_ids = set(conn.db_account_ids)
        for db_id in db_account_ids:
            if db_id not in existing_db_ids:
                conn.db_account_ids.append(db_id)

        # Add listener with its requested accounts
        conn.add_listener(listener, subaccount_ids)
        logger.info(f"Registered listener '{listener.listener_id}' on token {token_key} "
                     f"with accounts {sorted(subaccount_ids)}")

    async def _async_unregister(self, listener_id: str):
        """Remove a listener from all connections."""
        for conn in self._connections.values():
            if listener_id in conn._listeners:
                conn.remove_listener(listener_id)

    async def _run_manager(self):
        """Main async loop — manages all SharedConnections."""
        logger.info("WebSocket connection manager starting...")

        # Process any pending registrations
        while self._pending_registrations:
            reg = self._pending_registrations.pop(0)
            await self._async_register(reg)

        while self._running:
            try:
                # Start tasks for connections that need (re)connecting
                tasks = []
                for token_key, conn in list(self._connections.items()):
                    if not conn._listeners:
                        continue  # No listeners, skip
                    if conn.connected:
                        continue  # Already running

                    tasks.append(asyncio.create_task(
                        self._run_connection(token_key, conn)
                    ))

                if tasks:
                    # Wait for any connection to drop
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        try:
                            task.result()
                        except Exception as e:
                            logger.error(f"Connection task error: {e}")
                else:
                    await asyncio.sleep(5)

                # Process pending registrations that may have arrived
                while self._pending_registrations:
                    reg = self._pending_registrations.pop(0)
                    await self._async_register(reg)

                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Connection manager main loop error: {e}")
                await asyncio.sleep(10)

    async def _run_connection(self, token_key: str, conn: SharedConnection):
        """Run a single SharedConnection with reconnection and exponential backoff."""
        backoff = 1
        max_backoff = 60

        # Stagger initial connection: random 0-30s delay to prevent 429 storms
        # when all connections start simultaneously on deploy.
        # 16+ connections need wider spread to stay under Tradovate WS rate limit.
        initial_delay = random.uniform(0, 30)
        logger.info(f"[{token_key}] Starting connection in {initial_delay:.1f}s (staggered)")
        await asyncio.sleep(initial_delay)

        while self._running and conn._listeners:
            try:
                # Refresh token from DB before each reconnect
                fresh_token = self._get_fresh_token(conn.db_account_ids)
                if fresh_token:
                    if fresh_token != conn.access_token:
                        logger.info(f"[{token_key}] Refreshed token from DB")
                    conn.access_token = fresh_token

                success = await conn.connect()
                if success:
                    backoff = 1
                    conn._zero_data_windows = 0
                    await conn.run()

                    # If disconnected due to dead-subscription (zero data windows hit limit),
                    # use a longer backoff to prevent 429 storms from 16+ connections
                    # all reconnecting at once during thin market hours.
                    if conn._zero_data_windows >= 10:
                        backoff = max(backoff, 30)

                await conn.close()

                if not self._running:
                    break

                if not conn._listeners:
                    logger.info(f"[{token_key}] No listeners remaining — stopping reconnect")
                    break

                jittered_delay = backoff + random.uniform(0, 15)
                logger.info(f"[{token_key}] Reconnecting in {jittered_delay:.1f}s...")
                await asyncio.sleep(jittered_delay)
                backoff = min(backoff * 2, max_backoff)

            except Exception as e:
                logger.error(f"[{token_key}] Connection error: {e}")
                jittered_delay = backoff + random.uniform(0, 5)
                await asyncio.sleep(jittered_delay)
                backoff = min(backoff * 2, max_backoff)

    def _get_fresh_token(self, db_account_ids: List[int]) -> Optional[str]:
        """Read latest Tradovate token from accounts table."""
        if not db_account_ids:
            return None
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            return None
        try:
            import psycopg2
            db_url = database_url.replace('postgres://', 'postgresql://', 1)
            conn = psycopg2.connect(db_url, connect_timeout=5)
            cursor = conn.cursor()
            cursor.execute('SELECT tradovate_token FROM accounts WHERE id = %s',
                           (db_account_ids[0],))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception as e:
            logger.warning(f"Error reading fresh token: {e}")
            return None

    def get_status(self) -> Dict:
        """Get the current status of all connections and listeners."""
        status = {
            'running': self._running,
            'connections': {},
        }
        for token_key, conn in self._connections.items():
            listeners = {}
            for lid, listener in conn._listeners.items():
                listeners[lid] = {
                    'accounts': sorted(conn._listener_accounts.get(lid, set())),
                }
            status['connections'][token_key] = {
                'connected': conn.connected,
                'authenticated': conn.authenticated,
                'is_demo': conn.is_demo,
                'subscribed_accounts': sorted(conn._subscribed_accounts),
                'num_accounts': len(conn._subscribed_accounts),
                'num_listeners': len(conn._listeners),
                'listeners': listeners,
            }
        return status

    def stop(self):
        """Stop the connection manager."""
        self._running = False
        logger.info("Connection manager stopping...")

    def is_connected_for_account(self, subaccount_id: int) -> bool:
        """Check if any SharedConnection covers this subaccount and is connected."""
        for conn in self._connections.values():
            if subaccount_id in conn._subscribed_accounts and conn.connected and conn.authenticated:
                return True
        return False

    def get_connection_time(self, token_key: str) -> Optional[datetime]:
        """Get the connection time for a specific token (for replay filtering)."""
        conn = self._connections.get(token_key)
        if conn:
            return conn._connection_time
        return None


def get_connection_manager() -> TradovateConnectionManager:
    """Get the singleton TradovateConnectionManager instance."""
    global _manager_instance
    if _manager_instance is None:
        with _manager_lock:
            if _manager_instance is None:
                _manager_instance = TradovateConnectionManager()
    return _manager_instance
