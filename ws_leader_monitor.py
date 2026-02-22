"""
WebSocket Leader Monitor for Pro Copy Trader
=============================================
Monitors leader accounts via Tradovate WebSocket for fill events.
When a fill is detected on a leader account, copies the trade to all enabled followers.

Follows the same pattern as live_max_loss_monitor.py (proven WebSocket code).

Key safety features:
- Loop prevention: clOrdId prefix 'JT_COPY_' — ignores fills from copied orders
- 4pm CT replay filter: rejects fills that occurred before WebSocket connection time
- Reconnection with exponential backoff
- Per-leader asyncio.Lock prevents duplicate copies

Usage:
    from ws_leader_monitor import start_leader_monitor
    start_leader_monitor()
"""

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List

logger = logging.getLogger('leader_monitor')

# Try to import websockets
try:
    import websockets
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logger.warning("websockets library not installed. pip install websockets")

# Global state
_monitor_running = False
_monitor_thread = None
_leader_connections: Dict[int, Any] = {}  # leader_id -> LeaderConnection
_copy_locks: Dict[int, asyncio.Lock] = {}  # leader_id -> Lock (prevents duplicate copies)

# Copy order prefix for loop prevention
COPY_ORDER_PREFIX = 'JT_COPY_'


class LeaderConnection:
    """WebSocket connection to Tradovate for monitoring a leader's fills."""

    def __init__(self, leader_id: int, account_id: int, subaccount_id: str,
                 access_token: str, is_demo: bool = True, user_id: int = None):
        self.leader_id = leader_id
        self.account_id = account_id
        self.subaccount_id = subaccount_id
        self.access_token = access_token
        self.is_demo = is_demo
        self.user_id = user_id

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
        self._connection_time = None  # When we connected — for replay filter

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def connect(self) -> bool:
        """Connect and authenticate to Tradovate WebSocket."""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets not available")
            return False

        try:
            logger.info(f"Connecting to Tradovate for leader {self.leader_id} "
                        f"(account {self.subaccount_id})")

            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=5
            )
            self.connected = True
            self._connection_time = datetime.now(timezone.utc)

            # Authenticate
            auth_msg = f"authorize\n{self._next_request_id()}\n\n{self.access_token}"
            await self.websocket.send(auth_msg)

            # Wait for auth response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)

            if 's' in response or '"s":200' in response or 'ok' in response.lower():
                self.authenticated = True
                logger.info(f"Authenticated for leader {self.leader_id}")

                # Subscribe to user/syncrequest for fill events
                await self._subscribe_sync()
                return True
            else:
                logger.error(f"Auth failed for leader {self.leader_id}: {response[:200]}")
                return False

        except Exception as e:
            logger.error(f"Connection error for leader {self.leader_id}: {e}")
            return False

    async def _subscribe_sync(self):
        """Subscribe to user/syncrequest for real-time fill events."""
        try:
            sync_msg = f"user/syncrequest\n{self._next_request_id()}\n\n{{}}"
            await self.websocket.send(sync_msg)
            logger.info(f"Subscribed to sync updates for leader {self.leader_id}")
        except Exception as e:
            logger.error(f"Failed to subscribe sync for leader {self.leader_id}: {e}")

    async def run(self, fill_callback):
        """Run the monitoring loop."""
        self._running = True

        while self._running and self.connected:
            try:
                # Send heartbeat every 2.5 seconds
                now = time.time()
                if now - self._last_heartbeat > 2.5:
                    await self.websocket.send("[]")
                    self._last_heartbeat = now

                # Receive messages
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    await self._handle_message(message, fill_callback)
                except asyncio.TimeoutError:
                    continue

            except ConnectionClosed:
                logger.warning(f"WebSocket closed for leader {self.leader_id}")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"Error in leader monitor loop {self.leader_id}: {e}")

        self._running = False

    async def _handle_message(self, raw_message: str, fill_callback):
        """Handle incoming WebSocket message — look for fill events."""
        if not raw_message or raw_message in ('o', 'h', '[]'):
            return

        try:
            data = None

            # Parse message formats
            if raw_message.startswith('a['):
                inner = raw_message[1:]
                array = json.loads(inner)
                if array and isinstance(array[0], str):
                    data = json.loads(array[0])
            elif '{' in raw_message:
                json_start = raw_message.find('{')
                json_str = raw_message[json_start:]
                data = json.loads(json_str)

            if not data:
                return

            await self._check_for_fills(data, fill_callback)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"Message parse error (leader {self.leader_id}): {e}")

    async def _check_for_fills(self, data: dict, fill_callback):
        """Check for fill events in the WebSocket data."""
        fills = []

        # Direct fill entity event
        if (data.get('e') == 'props' and
                data.get('d', {}).get('entityType') == 'fill' and
                data.get('d', {}).get('eventType') == 'Created'):
            fills.append(data['d'])

        # Fills in sync response
        if 'd' in data:
            d = data['d']
            if 'fills' in d:
                for f in d.get('fills', []):
                    if isinstance(f, dict):
                        fills.append(f)

        # Direct fills array
        if 'fills' in data:
            for f in data.get('fills', []):
                if isinstance(f, dict):
                    fills.append(f)

        for fill in fills:
            await self._process_fill(fill, fill_callback)

    async def _process_fill(self, fill: dict, fill_callback):
        """Process a single fill event."""
        fill_id = fill.get('id')
        order_id = fill.get('orderId')
        contract_id = fill.get('contractId')
        qty = fill.get('qty', 0)
        price = fill.get('price', 0)
        action = fill.get('action', '')  # Buy or Sell
        timestamp_str = fill.get('timestamp', '')

        # --- LOOP PREVENTION ---
        # Check clOrdId for our copy prefix
        cl_ord_id = fill.get('clOrdId', '') or ''
        if cl_ord_id.startswith(COPY_ORDER_PREFIX):
            logger.debug(f"Skipping copied order fill (clOrdId={cl_ord_id})")
            return

        # --- REPLAY FILTER ---
        # Reject fills that occurred before we connected (4pm CT sync replay)
        if timestamp_str and self._connection_time:
            try:
                fill_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                if fill_time < self._connection_time:
                    logger.debug(f"Skipping pre-connection fill (fill_time={fill_time}, "
                                 f"connected_at={self._connection_time})")
                    return
            except (ValueError, TypeError):
                pass  # If we can't parse, let it through

        if not action or qty == 0:
            return

        logger.info(f"FILL detected on leader {self.leader_id}: "
                    f"{action} {qty} contractId={contract_id} @ {price}")

        # Get symbol name from contract (will be resolved by callback)
        if fill_callback:
            try:
                await fill_callback(
                    leader_id=self.leader_id,
                    fill_data={
                        'fill_id': fill_id,
                        'order_id': order_id,
                        'contract_id': contract_id,
                        'symbol': fill.get('symbol', ''),
                        'action': action,
                        'qty': abs(qty),
                        'price': price,
                        'timestamp': timestamp_str,
                    }
                )
            except Exception as e:
                logger.error(f"Fill callback error for leader {self.leader_id}: {e}")

    async def close(self):
        """Close the connection."""
        self._running = False
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
        self.connected = False


# ============================================================================
# FILL CALLBACK — COPY TO FOLLOWERS
# ============================================================================
async def _copy_fill_to_followers(leader_id: int, fill_data: dict):
    """Copy a leader's fill to all enabled followers."""
    global _copy_locks

    # Per-leader lock prevents duplicate copies
    if leader_id not in _copy_locks:
        _copy_locks[leader_id] = asyncio.Lock()

    async with _copy_locks[leader_id]:
        try:
            from copy_trader_models import (
                get_followers_for_leader, log_copy_trade, update_copy_trade_log
            )

            followers = get_followers_for_leader(leader_id)
            if not followers:
                logger.debug(f"No enabled followers for leader {leader_id}")
                return

            action = fill_data.get('action', '')
            qty = fill_data.get('qty', 1)
            symbol = fill_data.get('symbol', '')
            price = fill_data.get('price', 0)

            logger.info(f"Copying {action} {qty} {symbol} from leader {leader_id} "
                        f"to {len(followers)} followers")

            for follower in followers:
                follower_id = follower['id']
                multiplier = follower.get('multiplier', 1.0) or 1.0
                follower_qty = max(1, int(round(qty * multiplier)))

                # Log the pending copy
                log_id = log_copy_trade(
                    leader_id=leader_id,
                    follower_id=follower_id,
                    symbol=symbol,
                    side=action,
                    leader_quantity=qty,
                    follower_quantity=follower_qty,
                    leader_price=price,
                    status='pending'
                )

                start_time = time.time()

                try:
                    # Execute via internal manual trade API
                    account_subaccount = f"{follower['account_id']}:{follower['subaccount_id']}"

                    # Use clOrdId with COPY prefix for loop prevention
                    import uuid
                    cl_ord_id = f"{COPY_ORDER_PREFIX}{uuid.uuid4().hex[:12]}"

                    result = await _execute_follower_trade(
                        account_subaccount=account_subaccount,
                        symbol=symbol,
                        side=action,
                        quantity=follower_qty,
                        cl_ord_id=cl_ord_id
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    if result and result.get('success'):
                        if log_id:
                            update_copy_trade_log(
                                log_id, status='filled',
                                follower_order_id=result.get('order_id'),
                                latency_ms=latency_ms
                            )
                        logger.info(f"  Copied to follower {follower_id}: "
                                    f"{action} {follower_qty} {symbol} ({latency_ms}ms)")
                    else:
                        error_msg = (result.get('error') or 'Unknown error') if result else 'No result'
                        if log_id:
                            update_copy_trade_log(
                                log_id, status='error',
                                error_message=error_msg,
                                latency_ms=latency_ms
                            )
                        logger.warning(f"  Failed to copy to follower {follower_id}: {error_msg}")

                except Exception as e:
                    latency_ms = int((time.time() - start_time) * 1000)
                    if log_id:
                        update_copy_trade_log(
                            log_id, status='error',
                            error_message=str(e),
                            latency_ms=latency_ms
                        )
                    logger.error(f"  Error copying to follower {follower_id}: {e}")

        except Exception as e:
            logger.error(f"Error in copy_fill_to_followers for leader {leader_id}: {e}")


async def _execute_follower_trade(account_subaccount: str, symbol: str,
                                   side: str, quantity: int,
                                   cl_ord_id: str = None) -> dict:
    """Execute a trade on a follower account via internal REST call."""
    import aiohttp

    # Use localhost to call our own /api/manual-trade endpoint
    platform_url = os.environ.get('PLATFORM_URL', 'http://localhost:5000')
    url = f"{platform_url}/api/manual-trade"

    payload = {
        'account_subaccount': account_subaccount,
        'symbol': symbol,
        'side': side,
        'quantity': quantity,
        'risk': {},  # No TP/SL on copy trades — leader manages risk
    }
    if cl_ord_id:
        payload['cl_ord_id'] = cl_ord_id

    try:
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                result = await resp.json()
                return result
    except Exception as e:
        logger.error(f"Error executing follower trade: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================================
# LOAD ACTIVE LEADERS FROM DB
# ============================================================================
def _load_active_leaders() -> List[Dict]:
    """Load leader accounts that have auto_copy_enabled and at least one follower."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return []

    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT
                la.id as leader_id,
                la.account_id,
                la.subaccount_id,
                la.user_id,
                a.tradovate_token,
                a.environment
            FROM leader_accounts la
            INNER JOIN follower_accounts fa ON la.id = fa.leader_id
            INNER JOIN accounts a ON la.account_id = a.id
            WHERE la.is_active = TRUE
              AND la.auto_copy_enabled = TRUE
              AND fa.is_enabled = TRUE
              AND a.tradovate_token IS NOT NULL
        ''')

        leaders = []
        for row in cursor.fetchall():
            leaders.append({
                'leader_id': row[0],
                'account_id': row[1],
                'subaccount_id': str(row[2]),
                'user_id': row[3],
                'access_token': row[4],
                'is_demo': row[5] != 'live',
            })

        conn.close()
        return leaders

    except Exception as e:
        logger.error(f"Error loading active leaders: {e}")
        return []


# ============================================================================
# MAIN ASYNC LOOP
# ============================================================================
async def _run_leader_monitor():
    """Main async loop for leader monitoring."""
    global _leader_connections, _monitor_running

    _monitor_running = True
    logger.info("Starting Pro Copy Trader leader monitor...")

    while _monitor_running:
        try:
            leaders = _load_active_leaders()

            if not leaders:
                logger.debug("No active leaders with auto_copy_enabled")
                await asyncio.sleep(15)
                continue

            logger.info(f"Monitoring {len(leaders)} active leader(s)")

            # Create connections for new leaders
            tasks = []
            for leader_info in leaders:
                lid = leader_info['leader_id']
                conn_key = lid

                # Skip if already connected
                if conn_key in _leader_connections:
                    existing = _leader_connections[conn_key]
                    if existing.connected:
                        continue

                # Create new connection
                conn = LeaderConnection(
                    leader_id=lid,
                    account_id=leader_info['account_id'],
                    subaccount_id=leader_info['subaccount_id'],
                    access_token=leader_info['access_token'],
                    is_demo=leader_info['is_demo'],
                    user_id=leader_info['user_id']
                )

                _leader_connections[conn_key] = conn
                tasks.append(asyncio.create_task(_monitor_leader(conn)))

            # Wait for any connection to drop, then reconnect
            if tasks:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                # Clean up completed tasks
                for task in done:
                    try:
                        task.result()
                    except Exception as e:
                        logger.error(f"Leader monitor task error: {e}")

            # Reconnection delay with backoff
            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Error in leader monitor main loop: {e}")
            await asyncio.sleep(10)


async def _monitor_leader(conn: LeaderConnection):
    """Monitor a single leader with reconnection and exponential backoff."""
    backoff = 1
    max_backoff = 60

    while _monitor_running:
        try:
            success = await conn.connect()
            if success:
                backoff = 1  # Reset on successful connection
                await conn.run(fill_callback=_copy_fill_to_followers)

            # Connection lost or failed
            await conn.close()

            if not _monitor_running:
                break

            logger.info(f"Reconnecting leader {conn.leader_id} in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

        except Exception as e:
            logger.error(f"Leader monitor error for {conn.leader_id}: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


# ============================================================================
# PUBLIC API
# ============================================================================
def start_leader_monitor():
    """Start the leader monitor in a background daemon thread."""
    global _monitor_thread, _monitor_running

    if _monitor_running:
        logger.info("Leader monitor already running")
        return

    def _thread_target():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_leader_monitor())
        except Exception as e:
            logger.error(f"Leader monitor thread error: {e}")
        finally:
            loop.close()

    _monitor_thread = threading.Thread(target=_thread_target, daemon=True, name="leader-monitor")
    _monitor_thread.start()
    logger.info("Leader monitor daemon thread started")


def stop_leader_monitor():
    """Stop the leader monitor."""
    global _monitor_running
    _monitor_running = False
    logger.info("Leader monitor stopping...")


def get_leader_monitor_status() -> Dict:
    """Get the current status of the leader monitor."""
    status = {
        'running': _monitor_running,
        'connections': {}
    }
    for lid, conn in _leader_connections.items():
        status['connections'][lid] = {
            'leader_id': conn.leader_id,
            'connected': conn.connected,
            'authenticated': conn.authenticated,
            'subaccount_id': conn.subaccount_id,
            'is_demo': conn.is_demo,
        }
    return status


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Leader Monitor Status:")
    print(f"  WebSockets available: {WEBSOCKETS_AVAILABLE}")
    print(f"  Copy order prefix: {COPY_ORDER_PREFIX}")
    print(f"  Monitor running: {_monitor_running}")
    print("\nTo start: from ws_leader_monitor import start_leader_monitor; start_leader_monitor()")
