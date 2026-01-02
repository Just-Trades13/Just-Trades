"""
UI Publisher for Just.Trades Scalability
=========================================

Publishes consolidated state updates to UI clients at 1 Hz (once per second).

Key benefits:
- Stable UI performance regardless of broker event rate
- Reduces WebSocket traffic (coalesced updates vs. per-event)
- Insulates clients from bursty patterns during fills
- Supports both full snapshots and delta updates

Architecture:
    Broker Events → StateCache → UIPublisher (1 Hz) → UI Clients
    
Usage:
    from scalability.ui_publisher import UIPublisher, start_ui_publisher
    
    # Start the publisher (runs in background thread)
    publisher = start_ui_publisher(socketio_instance)
    
    # Publisher automatically reads from StateCache and emits to clients
    # No further action needed - it runs autonomously
    
    # To stop:
    publisher.stop()
"""

import threading
import time
import logging
from typing import Dict, Set, Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ClientSession:
    """Track state for each connected UI client"""
    client_id: str
    account_ids: Set[int] = field(default_factory=set)  # Which accounts they're subscribed to
    last_sequence: int = 0  # Last sequence number sent (for delta calculation)
    connected_at: float = field(default_factory=time.time)
    last_update_at: float = 0
    updates_sent: int = 0
    use_deltas: bool = True  # Whether to send deltas or full snapshots


class UIPublisher:
    """
    Publishes state updates to UI clients at a fixed cadence (default 1 Hz).
    
    Design:
    - Reads from StateCache (populated by broker events)
    - Emits to SocketIO clients
    - Tracks per-client state for delta optimization
    - Gracefully handles client connect/disconnect
    """
    
    def __init__(
        self,
        socketio,
        state_cache=None,
        publish_interval: float = 1.0,
        use_deltas: bool = True
    ):
        """
        Initialize the UI Publisher.
        
        Args:
            socketio: Flask-SocketIO instance for emitting updates
            state_cache: StateCache instance (uses global if not provided)
            publish_interval: Seconds between publishes (default 1.0 = 1 Hz)
            use_deltas: Whether to use delta updates (vs full snapshots)
        """
        self._socketio = socketio
        self._interval = publish_interval
        self._use_deltas = use_deltas
        
        # Get or create state cache
        if state_cache is None:
            from .state_cache import get_global_cache
            state_cache = get_global_cache()
        self._cache = state_cache
        
        # Client tracking
        self._clients: Dict[str, ClientSession] = {}
        self._clients_lock = threading.Lock()
        
        # Publisher thread control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Stats
        self._stats = {
            'ticks': 0,
            'updates_emitted': 0,
            'errors': 0,
            'clients_peak': 0,
        }
        
        # Callbacks for extensibility
        self._pre_publish_hooks: list = []
        self._post_publish_hooks: list = []
        
        logger.info(f"📡 UIPublisher initialized (interval={publish_interval}s, deltas={use_deltas})")
    
    # ========================================================================
    # CLIENT MANAGEMENT
    # ========================================================================
    
    def register_client(self, client_id: str, account_ids: Set[int] = None) -> ClientSession:
        """
        Register a new UI client.
        Call this when a client connects via SocketIO.
        
        Args:
            client_id: Unique client identifier (usually SocketIO session ID)
            account_ids: Set of account IDs the client wants updates for
        """
        with self._clients_lock:
            session = ClientSession(
                client_id=client_id,
                account_ids=account_ids or set(),
                last_sequence=0,  # Will get full snapshot on first update
                use_deltas=self._use_deltas,
            )
            self._clients[client_id] = session
            
            # Track peak clients
            if len(self._clients) > self._stats['clients_peak']:
                self._stats['clients_peak'] = len(self._clients)
            
            logger.info(f"📱 Client registered: {client_id} (accounts: {account_ids})")
            return session
    
    def unregister_client(self, client_id: str):
        """Unregister a client when they disconnect"""
        with self._clients_lock:
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"📱 Client unregistered: {client_id}")
    
    def subscribe_client_to_account(self, client_id: str, account_id: int):
        """Add an account subscription for a client"""
        with self._clients_lock:
            if client_id in self._clients:
                self._clients[client_id].account_ids.add(account_id)
                logger.debug(f"Client {client_id} subscribed to account {account_id}")
    
    def unsubscribe_client_from_account(self, client_id: str, account_id: int):
        """Remove an account subscription for a client"""
        with self._clients_lock:
            if client_id in self._clients:
                self._clients[client_id].account_ids.discard(account_id)
    
    def get_client_count(self) -> int:
        """Get current number of connected clients"""
        with self._clients_lock:
            return len(self._clients)
    
    # ========================================================================
    # PUBLISHER LOOP
    # ========================================================================
    
    def start(self):
        """Start the publisher background thread"""
        if self._running:
            logger.warning("UIPublisher already running")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._publish_loop,
            daemon=True,
            name="UI-Publisher-1Hz"
        )
        self._thread.start()
        logger.info("✅ UIPublisher started (1 Hz updates)")
    
    def stop(self):
        """Stop the publisher"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("🛑 UIPublisher stopped")
    
    def is_running(self) -> bool:
        """Check if publisher is running"""
        return self._running and self._thread and self._thread.is_alive()
    
    def _publish_loop(self):
        """Main publish loop - runs at 1 Hz"""
        logger.info("📡 UIPublisher loop started")
        
        while self._running:
            tick_start = time.time()
            
            try:
                self._publish_tick()
                self._stats['ticks'] += 1
            except Exception as e:
                self._stats['errors'] += 1
                logger.error(f"UIPublisher tick error: {e}")
                import traceback
                logger.debug(traceback.format_exc())
            
            # Sleep for remainder of interval
            elapsed = time.time() - tick_start
            sleep_time = max(0, self._interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        logger.info("📡 UIPublisher loop ended")
    
    def _publish_tick(self):
        """Execute one publish tick - send updates to all clients"""
        
        # Run pre-publish hooks
        for hook in self._pre_publish_hooks:
            try:
                hook(self)
            except Exception as e:
                logger.warning(f"Pre-publish hook error: {e}")
        
        # Get snapshot of clients (to avoid holding lock during emit)
        with self._clients_lock:
            clients = list(self._clients.values())
        
        if not clients:
            return  # No clients connected
        
        # Get current sequence for tracking
        cache_stats = self._cache.get_stats()
        current_sequence = cache_stats['current_sequence']
        
        # Build and send updates for each client
        for client in clients:
            try:
                self._publish_to_client(client, current_sequence)
            except Exception as e:
                logger.warning(f"Error publishing to client {client.client_id}: {e}")
        
        # Run post-publish hooks
        for hook in self._post_publish_hooks:
            try:
                hook(self)
            except Exception as e:
                logger.warning(f"Post-publish hook error: {e}")
    
    def _publish_to_client(self, client: ClientSession, current_sequence: int):
        """Publish update to a single client"""
        
        # If client has no account subscriptions, send all accounts summary
        if not client.account_ids:
            # Send platform-wide summary
            snapshot = self._cache.get_all_accounts_snapshot()
            payload = {
                'type': 'full_snapshot',
                'sequence': current_sequence,
                'timestamp': time.time(),
                'data': snapshot,
            }
        elif client.use_deltas and client.last_sequence > 0:
            # Send deltas for each subscribed account
            deltas = {}
            has_changes = False
            
            for account_id in client.account_ids:
                account_deltas = self._cache.get_deltas_since(account_id, client.last_sequence)
                if (account_deltas['positions_changed'] or 
                    account_deltas['orders_changed'] or 
                    account_deltas['fills_new'] or
                    account_deltas['pnl_changed'] or
                    account_deltas['balance_changed']):
                    has_changes = True
                    deltas[account_id] = account_deltas
            
            if not has_changes:
                return  # No changes, skip this tick for this client
            
            payload = {
                'type': 'delta',
                'from_sequence': client.last_sequence,
                'to_sequence': current_sequence,
                'timestamp': time.time(),
                'accounts': deltas,
            }
        else:
            # Send full snapshot for each subscribed account
            snapshots = {}
            for account_id in client.account_ids:
                snapshots[account_id] = self._cache.get_snapshot(account_id)
            
            payload = {
                'type': 'full_snapshot',
                'sequence': current_sequence,
                'timestamp': time.time(),
                'accounts': snapshots,
            }
        
        # Emit to client via SocketIO
        # Using room=client_id ensures only that client receives it
        self._socketio.emit(
            'scalability_update',
            payload,
            room=client.client_id
        )
        
        # Update client tracking
        client.last_sequence = current_sequence
        client.last_update_at = time.time()
        client.updates_sent += 1
        self._stats['updates_emitted'] += 1
    
    # ========================================================================
    # HOOKS FOR EXTENSIBILITY
    # ========================================================================
    
    def add_pre_publish_hook(self, hook: Callable):
        """Add a function to run before each publish tick"""
        self._pre_publish_hooks.append(hook)
    
    def add_post_publish_hook(self, hook: Callable):
        """Add a function to run after each publish tick"""
        self._post_publish_hooks.append(hook)
    
    # ========================================================================
    # STATS & HEALTH
    # ========================================================================
    
    def get_stats(self) -> dict:
        """Get publisher statistics"""
        with self._clients_lock:
            client_count = len(self._clients)
        
        return {
            **self._stats,
            'running': self.is_running(),
            'interval_seconds': self._interval,
            'use_deltas': self._use_deltas,
            'clients_connected': client_count,
            'cache_stats': self._cache.get_stats(),
        }
    
    def health_check(self) -> dict:
        """Check publisher health"""
        is_healthy = self.is_running()
        
        return {
            'healthy': is_healthy,
            'running': self.is_running(),
            'thread_alive': self._thread.is_alive() if self._thread else False,
            'ticks': self._stats['ticks'],
            'errors': self._stats['errors'],
            'error_rate': self._stats['errors'] / max(1, self._stats['ticks']),
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_global_publisher: Optional[UIPublisher] = None


def start_ui_publisher(socketio, **kwargs) -> UIPublisher:
    """
    Start the global UI publisher.
    
    Args:
        socketio: Flask-SocketIO instance
        **kwargs: Additional args passed to UIPublisher
        
    Returns:
        The UIPublisher instance
    """
    global _global_publisher
    
    if _global_publisher and _global_publisher.is_running():
        logger.warning("UIPublisher already running, returning existing instance")
        return _global_publisher
    
    _global_publisher = UIPublisher(socketio, **kwargs)
    _global_publisher.start()
    return _global_publisher


def get_ui_publisher() -> Optional[UIPublisher]:
    """Get the global UI publisher instance"""
    return _global_publisher


def stop_ui_publisher():
    """Stop the global UI publisher"""
    global _global_publisher
    if _global_publisher:
        _global_publisher.stop()
        _global_publisher = None
