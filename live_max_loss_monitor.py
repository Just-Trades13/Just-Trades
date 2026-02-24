"""
Live Max Loss Monitor for Just.Trades
=====================================

Monitors live trading accounts via WebSocket for max daily loss protection.
Uses Tradovate's user/syncrequest to get real-time P&L updates without REST polling.

For each connected account:
1. Subscribes to real-time cashBalance updates via WebSocket
2. Monitors openPnL against trader's max_daily_loss setting
3. Auto-flattens all positions when max loss is breached

Usage:
    from live_max_loss_monitor import start_live_max_loss_monitor
    start_live_max_loss_monitor()
"""

import asyncio
import json
import logging
import os
import threading
import time
from typing import Dict, Optional, Any, List
from datetime import datetime, date

logger = logging.getLogger(__name__)

# Import shared connection manager
try:
    from ws_connection_manager import get_connection_manager, Listener
    CONNECTION_MANAGER_AVAILABLE = True
except ImportError:
    CONNECTION_MANAGER_AVAILABLE = False
    logger.warning("ws_connection_manager not available — falling back to standalone connections")

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
_account_connections: Dict[int, Any] = {}  # account_id -> connection info
_max_loss_settings: Dict[int, float] = {}  # account_id -> max_daily_loss
_daily_realized_pnl: Dict[int, float] = {}  # account_id -> today's realized P&L
_last_pnl_check: Dict[int, float] = {}  # account_id -> last openPnL value
_breached_today: Dict[int, bool] = {}  # account_id -> already breached today
_max_loss_listeners: Dict[str, Any] = {}  # token_key -> MaxLossMonitorListener
_projectx_thread = None  # Separate thread for ProjectX REST polling


# ============================================================================
# MAX LOSS MONITOR LISTENER — Uses shared connection manager
# ============================================================================

class MaxLossMonitorListener:
    """Listener for max daily loss monitoring via shared WebSocket connection.

    One listener per token group — handles multiple accounts with different
    max_daily_loss thresholds. Checks accountId on cashBalance entities to
    route breach detection to the correct account config.
    """

    def __init__(self, token_key: str, access_token: str, is_demo: bool,
                 accounts: List[dict]):
        """
        Args:
            token_key: Short hash of token for logging
            access_token: Tradovate access token
            is_demo: Demo or live environment
            accounts: List of account dicts with keys:
                subaccount_id, max_daily_loss, trader_id, recorder_id, account_id, account_name
        """
        self._token_key = token_key
        self.access_token = access_token
        self.is_demo = is_demo
        self.connected = False

        # Map subaccount_id -> account config for breach routing
        self._account_configs: Dict[int, dict] = {}
        for acc in accounts:
            sub_id = int(acc['subaccount_id'])
            self._account_configs[sub_id] = {
                'subaccount_id': sub_id,
                'max_daily_loss': float(acc['max_daily_loss']),
                'trader_id': acc.get('trader_id'),
                'recorder_id': acc.get('recorder_id'),
                'account_id': acc.get('account_id'),
                'account_name': acc.get('account_name', f'Account-{sub_id}'),
            }

    @property
    def listener_id(self) -> str:
        return f'max-loss-monitor-{self._token_key}'

    async def on_connected(self, token_key: str):
        """Called when SharedConnection (re)connects."""
        self.connected = True
        sub_ids = list(self._account_configs.keys())
        logger.info(f"[MaxLoss] Connected on {token_key} — monitoring {len(sub_ids)} accounts: {sub_ids}")

    async def on_disconnected(self, token_key: str):
        """Called when SharedConnection disconnects."""
        self.connected = False
        logger.info(f"[MaxLoss] Disconnected from {token_key}")

    async def on_message(self, items: list, raw_message: str):
        """Process pre-parsed message items from shared connection.

        Filters for cashBalance entities and routes to correct account
        based on accountId field.
        """
        for data in items:
            try:
                await self._check_pnl_from_item(data)
            except Exception as e:
                logger.error(f"[MaxLoss] Error processing message item: {e}")

    async def _check_pnl_from_item(self, data: dict):
        """Check a single parsed message item for cashBalance P&L data."""
        global _breached_today

        cash_balances = []

        # Props event with cashBalance entity
        if data.get('e') == 'props' and data.get('d'):
            entity = data.get('d')
            if isinstance(entity, dict) and entity.get('entityType') == 'cashBalance':
                cb_data = entity.get('entity') or entity
                cash_balances.append(cb_data)

        # Sync response with cashBalances array
        if 'd' in data and isinstance(data.get('d'), dict):
            d = data['d']
            if 'cashBalances' in d:
                cash_balances.extend(d.get('cashBalances', []))

        # Direct cashBalances in response
        if 'cashBalances' in data:
            cash_balances.extend(data.get('cashBalances', []))

        for cb in cash_balances:
            if not isinstance(cb, dict):
                continue

            # Route to correct account by accountId
            cb_account_id = cb.get('accountId')
            if cb_account_id is not None:
                cb_account_id = int(cb_account_id)

            # Find the matching account config
            config = None
            if cb_account_id and cb_account_id in self._account_configs:
                config = self._account_configs[cb_account_id]
            elif len(self._account_configs) == 1:
                # Single account — always matches
                config = list(self._account_configs.values())[0]
            else:
                # No accountId and multiple accounts — skip to avoid wrong routing
                continue

            if not config:
                continue

            account_id = config['subaccount_id']
            max_daily_loss = config['max_daily_loss']
            trader_id = config.get('trader_id')
            recorder_id = config.get('recorder_id')

            # Skip if already breached today
            today = date.today().isoformat()
            breach_key = f"{account_id}_{today}"
            if _breached_today.get(breach_key):
                continue

            open_pnl = cb.get('openPnL', 0)
            realized_pnl = cb.get('realizedPnL', 0)
            total_pnl = open_pnl + realized_pnl

            # Check against max daily loss
            if max_daily_loss > 0 and total_pnl <= -max_daily_loss:
                logger.warning(f"🚨 MAX DAILY LOSS BREACHED for account {account_id}!")
                logger.warning(f"   Open P&L: ${open_pnl:.2f} | Realized: ${realized_pnl:.2f} | "
                             f"Total: ${total_pnl:.2f} | Limit: -${max_daily_loss:.2f}")

                _breached_today[breach_key] = True

                try:
                    await flatten_account_positions(account_id, trader_id, recorder_id, total_pnl)
                except Exception as e:
                    logger.error(f"Flatten callback error for account {account_id}: {e}")

    def add_account(self, acc: dict):
        """Add an account to monitor (for dynamic registration)."""
        sub_id = int(acc['subaccount_id'])
        self._account_configs[sub_id] = {
            'subaccount_id': sub_id,
            'max_daily_loss': float(acc['max_daily_loss']),
            'trader_id': acc.get('trader_id'),
            'recorder_id': acc.get('recorder_id'),
            'account_id': acc.get('account_id'),
            'account_name': acc.get('account_name', f'Account-{sub_id}'),
        }

    def get_subaccount_ids(self) -> List[int]:
        """Get all monitored subaccount IDs."""
        return list(self._account_configs.keys())


# ============================================================================
# LEGACY — TradovateMaxLossConnection kept for rollback
# ============================================================================

class TradovateMaxLossConnection:
    """WebSocket connection to Tradovate for max loss monitoring"""

    def __init__(self, account_id: int, access_token: str, is_demo: bool = True,
                 max_daily_loss: float = 0, trader_id: int = None, recorder_id: int = None):
        self.account_id = account_id
        self.access_token = access_token
        self.is_demo = is_demo
        self.max_daily_loss = max_daily_loss
        self.trader_id = trader_id
        self.recorder_id = recorder_id

        # WebSocket URL
        self.ws_url = "wss://demo.tradovateapi.com/v1/websocket" if is_demo else "wss://live.tradovateapi.com/v1/websocket"

        # Connection state
        self.websocket = None
        self.connected = False
        self.authenticated = False
        self._running = False
        self._last_heartbeat = 0
        self._request_id = 0

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def connect(self):
        """Connect and authenticate to Tradovate WebSocket"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets not available")
            return False

        try:
            logger.info(f"🔌 Connecting to Tradovate for account {self.account_id} (max_loss=${self.max_daily_loss})")

            self.websocket = await websockets.connect(
                self.ws_url,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=5
            )
            self.connected = True

            # Authenticate
            auth_msg = f"authorize\n{self._next_request_id()}\n\n{self.access_token}"
            await self.websocket.send(auth_msg)

            # Wait for auth response
            response = await asyncio.wait_for(self.websocket.recv(), timeout=10)

            if 's' in response or '"s":200' in response or 'ok' in response.lower():
                self.authenticated = True
                logger.info(f"✅ Authenticated for account {self.account_id}")

                # Subscribe to user/syncrequest for P&L updates
                await self._subscribe_sync()
                return True
            else:
                logger.error(f"❌ Auth failed for account {self.account_id}: {response[:200]}")
                return False

        except Exception as e:
            logger.error(f"❌ Connection error for account {self.account_id}: {e}")
            return False

    async def _subscribe_sync(self):
        """Subscribe to user/syncrequest for real-time updates"""
        try:
            # user/syncrequest needs empty body
            sync_msg = f"user/syncrequest\n{self._next_request_id()}\n\n{{}}"
            await self.websocket.send(sync_msg)
            logger.info(f"📡 Subscribed to sync updates for account {self.account_id}")
        except Exception as e:
            logger.error(f"Failed to subscribe sync for account {self.account_id}: {e}")

    async def run(self, flatten_callback):
        """Run the monitoring loop"""
        self._running = True

        while self._running and self.connected:
            try:
                # Send heartbeat every 2.5 seconds
                now = time.time()
                if now - self._last_heartbeat > 2.5:
                    await self.websocket.send("[]")
                    self._last_heartbeat = now

                # Receive messages (non-blocking with short timeout)
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    await self._handle_message(message, flatten_callback)
                except asyncio.TimeoutError:
                    continue

            except ConnectionClosed:
                logger.warning(f"WebSocket closed for account {self.account_id}")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"Error in monitor loop for account {self.account_id}: {e}")

        self._running = False

    async def _handle_message(self, raw_message: str, flatten_callback):
        """Handle incoming WebSocket message"""
        if not raw_message or raw_message in ('o', 'h', '[]'):
            return

        try:
            # Parse message - could be various formats
            data = None

            # Try to find JSON in the message
            if raw_message.startswith('a['):
                # Array format: a["json_string"]
                inner = raw_message[1:]
                array = json.loads(inner)
                if array and isinstance(array[0], str):
                    data = json.loads(array[0])
            elif '{' in raw_message:
                # Direct JSON or response format
                json_start = raw_message.find('{')
                json_str = raw_message[json_start:]
                data = json.loads(json_str)

            if not data:
                return

            # Check for cashBalance in response (contains openPnL)
            await self._check_pnl_update(data, flatten_callback)

        except json.JSONDecodeError:
            pass  # Not JSON, ignore
        except Exception as e:
            logger.debug(f"Message parse error: {e}")

    async def _check_pnl_update(self, data: dict, flatten_callback):
        """Check for P&L updates and enforce max loss"""
        global _breached_today

        # Skip if already breached today
        today = date.today().isoformat()
        breach_key = f"{self.account_id}_{today}"
        if _breached_today.get(breach_key):
            return

        # Look for cashBalance data which contains openPnL
        cash_balances = []

        # Direct cashBalance update
        if data.get('e') == 'props' and data.get('d', {}).get('entityType') == 'cashBalance':
            cash_balances.append(data['d'])
        # Sync response with cashBalances array
        elif 'd' in data and 'cashBalances' in data.get('d', {}):
            cash_balances = data['d'].get('cashBalances', [])
        # Direct cashBalances in response
        elif 'cashBalances' in data:
            cash_balances = data.get('cashBalances', [])

        for cb in cash_balances:
            if not isinstance(cb, dict):
                continue

            open_pnl = cb.get('openPnL', 0)
            realized_pnl = cb.get('realizedPnL', 0)

            # Calculate total daily P&L
            total_pnl = open_pnl + realized_pnl

            # Check against max daily loss
            if self.max_daily_loss > 0 and total_pnl <= -self.max_daily_loss:
                logger.warning(f"🚨 MAX DAILY LOSS BREACHED for account {self.account_id}!")
                logger.warning(f"   Open P&L: ${open_pnl:.2f} | Realized: ${realized_pnl:.2f} | Total: ${total_pnl:.2f} | Limit: -${self.max_daily_loss:.2f}")

                # Mark as breached to prevent repeated flattens
                _breached_today[breach_key] = True

                # Call flatten callback
                if flatten_callback:
                    try:
                        await flatten_callback(self.account_id, self.trader_id, self.recorder_id, total_pnl)
                    except Exception as e:
                        logger.error(f"Flatten callback error: {e}")

    async def close(self):
        """Close the connection"""
        self._running = False
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
        self.connected = False


async def flatten_account_positions(account_id: int, trader_id: int = None, recorder_id: int = None, current_pnl: float = 0):
    """Flatten all positions for an account via REST API"""
    import os
    import aiohttp

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        logger.error("No DATABASE_URL - cannot flatten")
        return

    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # Get account details
        cursor.execute('''
            SELECT a.tradovate_token, a.environment, a.name, a.user_id
            FROM accounts a
            WHERE a.tradovate_account_id = %s OR a.id = %s
        ''', (account_id, account_id))

        row = cursor.fetchone()
        if not row:
            logger.error(f"Account {account_id} not found")
            conn.close()
            return

        access_token, environment, account_name, user_id = row
        is_demo = environment != 'live'
        conn.close()

        # Use TradovateIntegration to flatten
        from phantom_scraper.tradovate_integration import TradovateIntegration

        async with aiohttp.ClientSession() as session:
            ti = TradovateIntegration(demo=is_demo)
            ti.session = session
            ti.access_token = access_token

            # Get all positions
            positions = await ti.get_positions(account_id)

            if not positions:
                logger.info(f"No positions to flatten for account {account_id}")
                return

            # Liquidate each position with netPos != 0
            flattened_count = 0
            for pos in positions:
                net_pos = pos.get('netPos', 0)
                if net_pos == 0:
                    continue

                contract_id = pos.get('contractId')
                if not contract_id:
                    continue

                result = await ti.liquidate_position(account_id, contract_id)
                if result and result.get('success'):
                    flattened_count += 1
                    logger.info(f"   Liquidated contract {contract_id} (netPos: {net_pos})")
                else:
                    logger.error(f"   Failed to liquidate contract {contract_id}: {result}")

            if flattened_count > 0:
                logger.info(f"💀 FLATTENED {flattened_count} positions for [{account_name}] due to max loss breach (P&L: ${current_pnl:.2f})")
            else:
                logger.info(f"No open positions to flatten for [{account_name}]")

    except Exception as e:
        logger.error(f"Error flattening account {account_id}: {e}")


def _load_max_loss_accounts() -> dict:
    """Load all accounts with max_daily_loss set from database"""
    import os

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        return {'tradovate': [], 'projectx': []}

    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        result = {'tradovate': [], 'projectx': []}

        # Get Tradovate/NinjaTrader accounts with max_daily_loss > 0
        # Note: NinjaTrader Brokerage uses Tradovate's backend API (same tokens, same WebSocket)
        # subaccount_id in traders table is the actual Tradovate account ID
        cursor.execute('''
            SELECT
                t.id as trader_id,
                t.recorder_id,
                t.account_id,
                t.max_daily_loss,
                t.subaccount_id,
                a.tradovate_token,
                a.environment,
                a.name as account_name,
                a.broker
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.enabled = TRUE
              AND t.max_daily_loss > 0
              AND a.tradovate_token IS NOT NULL
              AND t.subaccount_id IS NOT NULL
              AND (a.broker IS NULL OR a.broker IN ('Tradovate', 'tradovate', 'NinjaTrader', 'ninjatrader', ''))
        ''')

        for row in cursor.fetchall():
            broker_type = row[8] or 'Tradovate'  # Default to Tradovate if NULL
            result['tradovate'].append({
                'trader_id': row[0],
                'recorder_id': row[1],
                'account_id': row[2],
                'max_daily_loss': float(row[3]),
                'subaccount_id': row[4],  # This is the Tradovate account ID
                'access_token': row[5],
                'is_demo': row[6] != 'live',
                'account_name': row[7],
                'broker': broker_type  # Could be 'Tradovate' or 'NinjaTrader'
            })

        # Get ProjectX accounts with max_daily_loss > 0
        cursor.execute('''
            SELECT
                t.id as trader_id,
                t.recorder_id,
                t.account_id,
                t.max_daily_loss,
                a.projectx_account_id,
                a.tradovate_token,
                a.environment,
                a.name as account_name,
                a.projectx_prop_firm
            FROM traders t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.enabled = TRUE
              AND t.max_daily_loss > 0
              AND a.broker IN ('ProjectX', 'projectx')
              AND a.tradovate_token IS NOT NULL
        ''')

        for row in cursor.fetchall():
            result['projectx'].append({
                'trader_id': row[0],
                'recorder_id': row[1],
                'account_id': row[2],
                'max_daily_loss': float(row[3]),
                'projectx_account_id': row[4],
                'access_token': row[5],
                'is_demo': row[6] != 'live',
                'account_name': row[7],
                'prop_firm': row[8] or 'default',
                'broker': 'projectx'
            })

        conn.close()
        return result

    except Exception as e:
        logger.error(f"Error loading max loss accounts: {e}")
        return {'tradovate': [], 'projectx': []}


async def _run_max_loss_monitor():
    """Main async loop for max loss monitoring"""
    global _account_connections, _monitor_running

    _monitor_running = True
    logger.info("🛡️ Starting live max loss monitor...")

    while _monitor_running:
        try:
            # Load accounts with max_daily_loss configured
            accounts_by_broker = _load_max_loss_accounts()

            tradovate_accounts = accounts_by_broker.get('tradovate', [])
            projectx_accounts = accounts_by_broker.get('projectx', [])
            total_accounts = len(tradovate_accounts) + len(projectx_accounts)

            if total_accounts == 0:
                logger.debug("No accounts with max_daily_loss configured")
                await asyncio.sleep(30)
                continue

            logger.info(f"📊 Monitoring {total_accounts} accounts for max daily loss "
                       f"(Tradovate: {len(tradovate_accounts)}, ProjectX: {len(projectx_accounts)})")

            # Create connections for new accounts
            tasks = []

            # Handle Tradovate accounts
            for acc in tradovate_accounts:
                subaccount_id = acc['subaccount_id']
                conn_key = f"tradovate_{subaccount_id}"

                # Skip if already connected
                if conn_key in _account_connections:
                    existing = _account_connections[conn_key]
                    if existing.connected:
                        continue

                # Create new Tradovate connection
                conn = TradovateMaxLossConnection(
                    account_id=subaccount_id,
                    access_token=acc['access_token'],
                    is_demo=acc['is_demo'],
                    max_daily_loss=acc['max_daily_loss'],
                    trader_id=acc['trader_id'],
                    recorder_id=acc['recorder_id']
                )

                _account_connections[conn_key] = conn

                # Connect and start monitoring
                if await conn.connect():
                    tasks.append(asyncio.create_task(conn.run(flatten_account_positions)))

            # Handle ProjectX accounts (uses REST polling since SignalR requires extra dep)
            # For now, we'll check ProjectX via periodic REST calls
            for acc in projectx_accounts:
                conn_key = f"projectx_{acc['account_id']}"

                # Skip if already being monitored
                if conn_key in _account_connections:
                    continue

                # Store account info for REST-based monitoring
                _account_connections[conn_key] = {
                    'broker': 'projectx',
                    'account_id': acc['account_id'],
                    'projectx_account_id': acc['projectx_account_id'],
                    'access_token': acc['access_token'],
                    'is_demo': acc['is_demo'],
                    'max_daily_loss': acc['max_daily_loss'],
                    'trader_id': acc['trader_id'],
                    'prop_firm': acc['prop_firm'],
                    'connected': True
                }

                # Start ProjectX REST monitoring task
                tasks.append(asyncio.create_task(
                    _monitor_projectx_account(acc, flatten_projectx_positions)
                ))

            # Wait for tasks or timeout for refresh
            if tasks:
                done, pending = await asyncio.wait(tasks, timeout=60, return_when=asyncio.FIRST_COMPLETED)

                # Cancel pending if monitor stopped
                if not _monitor_running:
                    for task in pending:
                        task.cancel()
            else:
                await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Max loss monitor error: {e}")
            await asyncio.sleep(10)

    # Cleanup
    for key, conn in _account_connections.items():
        if hasattr(conn, 'close'):
            await conn.close()
    _account_connections.clear()

    logger.info("🛡️ Live max loss monitor stopped")


async def _monitor_projectx_account(acc: dict, flatten_callback):
    """Monitor a ProjectX account for max daily loss via REST API polling"""
    global _breached_today, _monitor_running

    account_id = acc['account_id']
    projectx_account_id = acc.get('projectx_account_id')
    max_daily_loss = acc['max_daily_loss']
    access_token = acc['access_token']
    is_demo = acc['is_demo']
    prop_firm = acc.get('prop_firm', 'default')

    today = date.today().isoformat()
    breach_key = f"projectx_{account_id}_{today}"

    logger.info(f"📡 Starting ProjectX monitor for account {account_id} (max_loss=${max_daily_loss})")

    while _monitor_running:
        try:
            # Skip if already breached today
            if _breached_today.get(breach_key):
                await asyncio.sleep(60)
                continue

            # Get current P&L via REST
            from phantom_scraper.projectx_integration import ProjectXIntegration

            async with ProjectXIntegration(demo=is_demo, prop_firm=prop_firm) as px:
                px.session_token = access_token

                # Get account info which may contain P&L
                account_info = await px.get_account_info(projectx_account_id or account_id)

                # Calculate P&L from account info or positions
                total_pnl = 0
                open_pnl = 0
                realized_pnl = 0

                if account_info:
                    # Try to get P&L from account info
                    open_pnl = float(account_info.get('unrealizedPnL', 0) or account_info.get('openPnL', 0) or 0)
                    realized_pnl = float(account_info.get('realizedPnL', 0) or account_info.get('closedPnL', 0) or 0)
                    total_pnl = open_pnl + realized_pnl

                    # Also check trailingDrawdown if available
                    trailing_dd = float(account_info.get('trailingDrawdown', 0) or 0)
                    if trailing_dd < 0 and abs(trailing_dd) > abs(total_pnl):
                        total_pnl = trailing_dd

                # Check max loss
                if total_pnl <= -max_daily_loss:
                    logger.warning(f"🚨 MAX DAILY LOSS BREACHED for ProjectX account {account_id}!")
                    logger.warning(f"   Open P&L: ${open_pnl:.2f} | Realized: ${realized_pnl:.2f} | Total: ${total_pnl:.2f}")

                    _breached_today[breach_key] = True

                    if flatten_callback:
                        await flatten_callback(acc, total_pnl)

            # Poll every 5 seconds (reasonable for REST)
            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"ProjectX monitor error for account {account_id}: {e}")
            await asyncio.sleep(30)


async def flatten_projectx_positions(acc: dict, current_pnl: float = 0):
    """Flatten all positions for a ProjectX account using liquidate_position"""
    try:
        from phantom_scraper.projectx_integration import ProjectXIntegration

        account_id = acc.get('projectx_account_id') or acc.get('account_id')
        is_demo = acc.get('is_demo', True)
        prop_firm = acc.get('prop_firm', 'default')
        access_token = acc.get('access_token')
        account_name = acc.get('account_name', f'ProjectX-{account_id}')

        async with ProjectXIntegration(demo=is_demo, prop_firm=prop_firm) as px:
            px.session_token = access_token

            # Get all positions
            positions = await px.get_positions(account_id)

            if not positions:
                logger.info(f"No positions to flatten for ProjectX account {account_id}")
                return

            # Liquidate each position with quantity != 0
            flattened = 0
            for pos in positions:
                qty = pos.get('quantity', 0) or pos.get('netPos', 0)
                if qty == 0:
                    continue

                contract_id = pos.get('contractId') or pos.get('contract_id')
                if not contract_id:
                    continue

                # Use liquidate_position to close the position
                result = await px.liquidate_position(account_id, contract_id)

                if result and result.get('success'):
                    flattened += 1
                    logger.info(f"   Liquidated ProjectX position: contract {contract_id} qty={qty}")
                else:
                    logger.error(f"   Failed to liquidate ProjectX position {contract_id}: {result}")

            if flattened > 0:
                logger.info(f"💀 FLATTENED {flattened} positions for [{account_name}] due to max loss breach (P&L: ${current_pnl:.2f})")

    except Exception as e:
        logger.error(f"Error flattening ProjectX account: {e}")


async def _run_projectx_max_loss_monitor(projectx_accounts: list):
    """Run REST polling loop for ProjectX accounts' max daily loss.

    ProjectX uses REST (not Tradovate WebSocket), so it stays in its own thread.
    """
    global _monitor_running

    logger.info(f"🛡️ ProjectX max loss REST polling started for {len(projectx_accounts)} accounts")

    tasks = []
    for acc in projectx_accounts:
        tasks.append(asyncio.create_task(
            _monitor_projectx_account(acc, flatten_projectx_positions)
        ))

    if tasks:
        await asyncio.gather(*tasks)


def start_live_max_loss_monitor():
    """Start the live max loss monitor.

    Tradovate accounts: registered as listeners on the shared connection manager.
    ProjectX accounts: monitored via REST polling in a separate daemon thread.
    """
    global _monitor_thread, _monitor_running, _max_loss_listeners, _projectx_thread

    if _monitor_running:
        logger.info("Live max loss monitor already running")
        return

    _monitor_running = True

    # Load accounts with max_daily_loss configured
    accounts_by_broker = _load_max_loss_accounts()
    tradovate_accounts = accounts_by_broker.get('tradovate', [])
    projectx_accounts = accounts_by_broker.get('projectx', [])

    total = len(tradovate_accounts) + len(projectx_accounts)
    if total == 0:
        logger.info("🛡️ No accounts with max_daily_loss configured — max loss monitor idle")
        return

    logger.info(f"🛡️ Starting live max loss monitor — "
                f"Tradovate: {len(tradovate_accounts)}, ProjectX: {len(projectx_accounts)}")

    # --- Tradovate: Register with shared connection manager ---
    if tradovate_accounts and CONNECTION_MANAGER_AVAILABLE:
        manager = get_connection_manager()

        # Group accounts by token (same pattern as ws_position_monitor.py)
        token_groups: Dict[str, dict] = {}
        for acc in tradovate_accounts:
            token = acc['access_token']
            token_key = f"...{token[-8:]}" if len(token) > 8 else token

            if token_key not in token_groups:
                token_groups[token_key] = {
                    'access_token': token,
                    'is_demo': acc['is_demo'],
                    'accounts': [],
                    'subaccount_ids': [],
                    'db_account_ids': [],
                }
            group = token_groups[token_key]
            group['accounts'].append(acc)
            group['subaccount_ids'].append(int(acc['subaccount_id']))
            if acc['account_id'] not in group['db_account_ids']:
                group['db_account_ids'].append(acc['account_id'])

        for token_key, group in token_groups.items():
            listener = MaxLossMonitorListener(
                token_key=token_key,
                access_token=group['access_token'],
                is_demo=group['is_demo'],
                accounts=group['accounts'],
            )
            _max_loss_listeners[token_key] = listener

            manager.register_listener(
                token=group['access_token'],
                is_demo=group['is_demo'],
                subaccount_ids=group['subaccount_ids'],
                listener=listener,
                db_account_ids=group['db_account_ids'],
            )
            logger.info(f"[MaxLoss] Registered listener for token {token_key} "
                        f"with {len(group['accounts'])} accounts")

    elif tradovate_accounts:
        logger.warning("🛡️ Connection manager not available — Tradovate max loss monitoring disabled")

    # --- ProjectX: REST polling in separate thread ---
    if projectx_accounts:
        def _run_projectx_polling():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_run_projectx_max_loss_monitor(projectx_accounts))
            except Exception as e:
                logger.error(f"ProjectX max loss monitor thread error: {e}")
            finally:
                loop.close()

        _projectx_thread = threading.Thread(
            target=_run_projectx_polling, daemon=True, name="ProjectXMaxLossMonitor"
        )
        _projectx_thread.start()
        logger.info(f"🛡️ ProjectX max loss monitor thread started "
                    f"({len(projectx_accounts)} accounts)")

    logger.info("🛡️ Live max loss monitor started")


def stop_live_max_loss_monitor():
    """Stop the live max loss monitor — unregister all listeners."""
    global _monitor_running, _max_loss_listeners
    _monitor_running = False

    if CONNECTION_MANAGER_AVAILABLE and _max_loss_listeners:
        manager = get_connection_manager()
        for token_key, listener in list(_max_loss_listeners.items()):
            manager.unregister_listener(listener.listener_id)
        _max_loss_listeners.clear()

    logger.info("🛡️ Stopping live max loss monitor...")


def get_max_loss_monitor_status() -> dict:
    """Get current status of the max loss monitor."""
    tradovate_connected = 0
    tradovate_total = 0

    for token_key, listener in _max_loss_listeners.items():
        account_count = len(listener.get_subaccount_ids())
        tradovate_total += account_count
        if listener.connected:
            tradovate_connected += account_count

    # ProjectX accounts from _account_connections (REST polling)
    projectx_connected = 0
    for key, conn in _account_connections.items():
        if key.startswith('projectx_'):
            if isinstance(conn, dict) and conn.get('connected'):
                projectx_connected += 1

    return {
        'running': _monitor_running,
        'tradovate_accounts': tradovate_connected,
        'projectx_accounts': projectx_connected,
        'total_accounts': tradovate_total + projectx_connected,
        'breached_today': list(_breached_today.keys())
    }


# Reset breach flags at midnight
def _reset_daily_breach_flags():
    """Reset breach flags at start of new day"""
    global _breached_today
    today = date.today().isoformat()

    # Remove old dates
    old_keys = [k for k in _breached_today.keys() if not k.endswith(today)]
    for k in old_keys:
        del _breached_today[k]


if __name__ == '__main__':
    # Test run
    logging.basicConfig(level=logging.INFO)
    start_live_max_loss_monitor()

    try:
        while True:
            time.sleep(10)
            print(f"Status: {get_max_loss_monitor_status()}")
    except KeyboardInterrupt:
        stop_live_max_loss_monitor()
