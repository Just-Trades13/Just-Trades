"""
State Cache for Just.Trades Scalability
========================================

Thread-safe server-side cache that holds the latest state for each user/account.
The UI Publisher reads from this cache at 1 Hz to send consolidated updates.

This decouples:
- Broker event ingestion (can be bursty, 10-100 events/sec during fills)
- UI publishing (steady 1 Hz regardless of event rate)

Usage:
    cache = StateCache()
    
    # On broker event:
    cache.update_position(account_id, position_data)
    cache.update_order(account_id, order_data)
    cache.update_pnl(account_id, pnl_data)
    
    # UI Publisher reads at 1 Hz:
    snapshot = cache.get_snapshot(account_id)
    deltas = cache.get_deltas_since(account_id, last_seq)
"""

import threading
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry with versioning for delta detection"""
    data: Any
    updated_at: float = field(default_factory=time.time)
    sequence: int = 0


class StateCache:
    """
    Thread-safe state cache for broker data.
    
    Design principles:
    - One writer per account stream (from WS or REST reconciliation)
    - Many readers (UI publisher, analytics, etc.)
    - Delta tracking via sequence numbers
    - TTL for stale data cleanup
    """
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize the state cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries (default 5 minutes)
        """
        self._lock = threading.RLock()
        self._ttl = ttl_seconds
        
        # Per-account state
        # Structure: {account_id: {entity_type: {entity_id: CacheEntry}}}
        self._positions: Dict[int, Dict[str, CacheEntry]] = defaultdict(dict)  # keyed by contract_id or symbol
        self._orders: Dict[int, Dict[int, CacheEntry]] = defaultdict(dict)  # keyed by order_id
        self._fills: Dict[int, Dict[int, CacheEntry]] = defaultdict(dict)  # keyed by fill_id
        self._pnl: Dict[int, CacheEntry] = {}  # one PnL entry per account
        self._balances: Dict[int, CacheEntry] = {}  # cash balance per account
        
        # Global sequence counter for delta tracking
        self._sequence = 0
        
        # Track last snapshot sequence per client for delta calculation
        self._client_sequences: Dict[str, int] = {}
        
        # Metrics
        self._stats = {
            'updates': 0,
            'reads': 0,
            'cache_hits': 0,
            'deltas_sent': 0,
        }
        
        logger.info("📦 StateCache initialized (TTL: %d seconds)", ttl_seconds)
    
    def _next_sequence(self) -> int:
        """Get next sequence number (thread-safe)"""
        self._sequence += 1
        return self._sequence
    
    # ========================================================================
    # POSITION UPDATES
    # ========================================================================
    
    def update_position(self, account_id: int, contract_id: str, position_data: dict) -> int:
        """
        Update a position in the cache.
        
        Args:
            account_id: Tradovate account ID
            contract_id: Contract ID or symbol
            position_data: Position data from broker
            
        Returns:
            Sequence number of this update
        """
        with self._lock:
            seq = self._next_sequence()
            self._positions[account_id][contract_id] = CacheEntry(
                data=position_data,
                updated_at=time.time(),
                sequence=seq
            )
            self._stats['updates'] += 1
            logger.debug(f"Position updated: account={account_id}, contract={contract_id}, seq={seq}")
            return seq
    
    def remove_position(self, account_id: int, contract_id: str) -> int:
        """Remove a position (when flat)"""
        with self._lock:
            seq = self._next_sequence()
            if contract_id in self._positions.get(account_id, {}):
                del self._positions[account_id][contract_id]
                logger.debug(f"Position removed: account={account_id}, contract={contract_id}")
            return seq
    
    def get_positions(self, account_id: int) -> List[dict]:
        """Get all positions for an account"""
        with self._lock:
            self._stats['reads'] += 1
            return [entry.data for entry in self._positions.get(account_id, {}).values()]
    
    # ========================================================================
    # ORDER UPDATES
    # ========================================================================
    
    def update_order(self, account_id: int, order_id: int, order_data: dict) -> int:
        """Update an order in the cache"""
        with self._lock:
            seq = self._next_sequence()
            self._orders[account_id][order_id] = CacheEntry(
                data=order_data,
                updated_at=time.time(),
                sequence=seq
            )
            self._stats['updates'] += 1
            return seq
    
    def remove_order(self, account_id: int, order_id: int) -> int:
        """Remove an order (when filled/cancelled)"""
        with self._lock:
            seq = self._next_sequence()
            if order_id in self._orders.get(account_id, {}):
                del self._orders[account_id][order_id]
            return seq
    
    def get_orders(self, account_id: int, status_filter: str = None) -> List[dict]:
        """Get orders for an account, optionally filtered by status"""
        with self._lock:
            self._stats['reads'] += 1
            orders = [entry.data for entry in self._orders.get(account_id, {}).values()]
            if status_filter:
                orders = [o for o in orders if o.get('status') == status_filter]
            return orders
    
    # ========================================================================
    # FILL UPDATES
    # ========================================================================
    
    def add_fill(self, account_id: int, fill_id: int, fill_data: dict) -> int:
        """Add a fill to the cache"""
        with self._lock:
            seq = self._next_sequence()
            self._fills[account_id][fill_id] = CacheEntry(
                data=fill_data,
                updated_at=time.time(),
                sequence=seq
            )
            self._stats['updates'] += 1
            return seq
    
    def get_recent_fills(self, account_id: int, limit: int = 10) -> List[dict]:
        """Get recent fills for an account"""
        with self._lock:
            self._stats['reads'] += 1
            fills = list(self._fills.get(account_id, {}).values())
            # Sort by sequence (most recent first)
            fills.sort(key=lambda x: x.sequence, reverse=True)
            return [f.data for f in fills[:limit]]
    
    # ========================================================================
    # PNL UPDATES
    # ========================================================================
    
    def update_pnl(self, account_id: int, pnl_data: dict) -> int:
        """Update PnL for an account"""
        with self._lock:
            seq = self._next_sequence()
            now = time.time()
            # Inject timestamp into data for freshness checking
            pnl_data_with_ts = {**pnl_data, '_updated_at': now}
            self._pnl[account_id] = CacheEntry(
                data=pnl_data_with_ts,
                updated_at=now,
                sequence=seq
            )
            self._stats['updates'] += 1
            return seq
    
    def get_pnl(self, account_id: int) -> Optional[dict]:
        """Get PnL for an account"""
        with self._lock:
            self._stats['reads'] += 1
            entry = self._pnl.get(account_id)
            return entry.data if entry else None
    
    # ========================================================================
    # BALANCE UPDATES
    # ========================================================================
    
    def update_balance(self, account_id: int, balance_data: dict) -> int:
        """Update cash balance for an account"""
        with self._lock:
            seq = self._next_sequence()
            self._balances[account_id] = CacheEntry(
                data=balance_data,
                updated_at=time.time(),
                sequence=seq
            )
            self._stats['updates'] += 1
            return seq
    
    def get_balance(self, account_id: int) -> Optional[dict]:
        """Get cash balance for an account"""
        with self._lock:
            self._stats['reads'] += 1
            entry = self._balances.get(account_id)
            return entry.data if entry else None
    
    # ========================================================================
    # SNAPSHOTS & DELTAS
    # ========================================================================
    
    def get_snapshot(self, account_id: int) -> dict:
        """
        Get complete state snapshot for an account.
        Used for initial load or after reconnect.
        """
        with self._lock:
            self._stats['reads'] += 1
            return {
                'account_id': account_id,
                'sequence': self._sequence,
                'timestamp': time.time(),
                'positions': self.get_positions(account_id),
                'orders': self.get_orders(account_id),
                'fills': self.get_recent_fills(account_id),
                'pnl': self.get_pnl(account_id),
                'balance': self.get_balance(account_id),
            }
    
    def get_all_accounts_snapshot(self) -> dict:
        """Get snapshot for all accounts (for platform-wide view)"""
        with self._lock:
            account_ids = set()
            account_ids.update(self._positions.keys())
            account_ids.update(self._orders.keys())
            account_ids.update(self._pnl.keys())
            
            return {
                'sequence': self._sequence,
                'timestamp': time.time(),
                'accounts': {
                    acc_id: self.get_snapshot(acc_id)
                    for acc_id in account_ids
                }
            }
    
    def get_deltas_since(self, account_id: int, since_sequence: int) -> dict:
        """
        Get changes since a given sequence number.
        Used for efficient delta updates to UI.
        
        Returns only entities that changed since since_sequence.
        """
        with self._lock:
            self._stats['reads'] += 1
            
            deltas = {
                'account_id': account_id,
                'from_sequence': since_sequence,
                'to_sequence': self._sequence,
                'timestamp': time.time(),
                'positions_changed': [],
                'orders_changed': [],
                'fills_new': [],
                'pnl_changed': False,
                'balance_changed': False,
            }
            
            # Check positions
            for contract_id, entry in self._positions.get(account_id, {}).items():
                if entry.sequence > since_sequence:
                    deltas['positions_changed'].append(entry.data)
            
            # Check orders
            for order_id, entry in self._orders.get(account_id, {}).items():
                if entry.sequence > since_sequence:
                    deltas['orders_changed'].append(entry.data)
            
            # Check fills
            for fill_id, entry in self._fills.get(account_id, {}).items():
                if entry.sequence > since_sequence:
                    deltas['fills_new'].append(entry.data)
            
            # Check PnL
            pnl_entry = self._pnl.get(account_id)
            if pnl_entry and pnl_entry.sequence > since_sequence:
                deltas['pnl_changed'] = True
                deltas['pnl'] = pnl_entry.data
            
            # Check balance
            balance_entry = self._balances.get(account_id)
            if balance_entry and balance_entry.sequence > since_sequence:
                deltas['balance_changed'] = True
                deltas['balance'] = balance_entry.data
            
            # Track deltas sent
            has_changes = (
                deltas['positions_changed'] or 
                deltas['orders_changed'] or 
                deltas['fills_new'] or 
                deltas['pnl_changed'] or
                deltas['balance_changed']
            )
            if has_changes:
                self._stats['deltas_sent'] += 1
            
            return deltas
    
    # ========================================================================
    # MAINTENANCE
    # ========================================================================
    
    def cleanup_stale(self) -> int:
        """Remove entries older than TTL. Returns count of removed entries."""
        with self._lock:
            now = time.time()
            cutoff = now - self._ttl
            removed = 0
            
            # Cleanup old fills (keep positions and orders)
            for account_id in list(self._fills.keys()):
                for fill_id in list(self._fills[account_id].keys()):
                    if self._fills[account_id][fill_id].updated_at < cutoff:
                        del self._fills[account_id][fill_id]
                        removed += 1
            
            if removed:
                logger.debug(f"Cleaned up {removed} stale cache entries")
            return removed
    
    def clear_account(self, account_id: int):
        """Clear all cached data for an account"""
        with self._lock:
            self._positions.pop(account_id, None)
            self._orders.pop(account_id, None)
            self._fills.pop(account_id, None)
            self._pnl.pop(account_id, None)
            self._balances.pop(account_id, None)
            logger.info(f"Cleared cache for account {account_id}")
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        with self._lock:
            total_positions = sum(len(p) for p in self._positions.values())
            total_orders = sum(len(o) for o in self._orders.values())
            total_fills = sum(len(f) for f in self._fills.values())
            
            return {
                **self._stats,
                'current_sequence': self._sequence,
                'accounts_tracked': len(set(
                    list(self._positions.keys()) + 
                    list(self._orders.keys()) + 
                    list(self._pnl.keys())
                )),
                'total_positions': total_positions,
                'total_orders': total_orders,
                'total_fills': total_fills,
                'total_pnl_entries': len(self._pnl),
            }


# Global instance (created on first import)
_global_cache: Optional[StateCache] = None

def get_global_cache() -> StateCache:
    """Get or create the global state cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = StateCache()
    return _global_cache
