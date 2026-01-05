"""
Legacy Bridge for Just.Trades Scalability Module
=================================================

Bridges the new StateCache (fed by WebSocket) to the legacy `position_update` 
SocketIO channel that the Manual Copy Trader and Control Center expect.

This allows instant PnL updates without changing any existing UI code.

Architecture:
    BrokerWSManager → StateCache → LegacyBridge → emit('position_update', {...})
                                                       ↑
                                      Same format existing UI expects

Enable with:
    export SCALABILITY_LEGACY_BRIDGE=1
    
Requires:
    - SCALABILITY_WS_STATE_MANAGER=1 (to feed StateCache)
    - SCALABILITY_UI_PUBLISHER=1 (to hook into publish cycle)
"""

import os
import time
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Feature flag
LEGACY_BRIDGE_ENABLED = os.environ.get('SCALABILITY_LEGACY_BRIDGE', '0') == '1'


class LegacyBridge:
    """
    Bridges StateCache data to legacy `position_update` SocketIO events.
    
    Runs as a hook on the UIPublisher's publish cycle, ensuring:
    - 1 Hz update rate (same as UIPublisher)
    - No duplicate emits
    - Graceful handling when StateCache has no data
    """
    
    def __init__(self, socketio, state_cache=None, db_connection_func=None):
        """
        Initialize the Legacy Bridge.
        
        Args:
            socketio: Flask-SocketIO instance
            state_cache: StateCache instance (uses global if not provided)
            db_connection_func: Function to get DB connection for account metadata
        """
        self._socketio = socketio
        self._db_func = db_connection_func
        
        # Get or create state cache
        if state_cache is None:
            from scalability.state_cache import get_state_cache
            state_cache = get_state_cache()
        self._cache = state_cache
        
        # Track last emitted sequence to avoid duplicate emits
        self._last_emitted_sequence = 0
        
        # Account metadata cache (account_id -> {name, is_demo, user_id})
        self._account_meta: Dict[int, dict] = {}
        self._account_meta_lock = threading.Lock()
        self._last_meta_refresh = 0
        self._meta_refresh_interval = 60  # Refresh account metadata every 60s
        
        # Stats
        self._stats = {
            'emits': 0,
            'skipped_no_change': 0,
            'skipped_no_data': 0,
            'errors': 0,
        }
        
        logger.info("🔗 LegacyBridge initialized")
    
    def _refresh_account_metadata(self):
        """Load account metadata from database"""
        if not self._db_func:
            return
        
        now = time.time()
        if now - self._last_meta_refresh < self._meta_refresh_interval:
            return  # Not time to refresh yet
        
        try:
            conn = self._db_func()
            cursor = conn.cursor()
            
            # Query from accounts table - tradovate_accounts is a JSON column
            cursor.execute('''
                SELECT id, name, environment, user_id, tradovate_accounts 
                FROM accounts 
                WHERE tradovate_token IS NOT NULL AND tradovate_token != ''
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            with self._account_meta_lock:
                self._account_meta.clear()
                for row in rows:
                    account_id = row[0]
                    account_name = row[1]
                    is_demo = (row[2] or 'demo').lower() == 'demo'
                    user_id = row[3]
                    tradovate_accounts_json = row[4]
                    
                    # Parse subaccounts from JSON
                    if tradovate_accounts_json:
                        try:
                            import json
                            subaccounts = json.loads(tradovate_accounts_json)
                            for sub in subaccounts:
                                sub_id = sub.get('id') or sub.get('accountId')
                                if sub_id:
                                    self._account_meta[sub_id] = {
                                        'account_name': sub.get('name', account_name),
                                        'is_demo': sub.get('is_demo', is_demo),
                                        'user_id': user_id,
                                        'parent_account_id': account_id,
                                    }
                        except json.JSONDecodeError:
                            pass
                    
                    # Also store parent account
                    self._account_meta[account_id] = {
                        'account_name': account_name,
                        'is_demo': is_demo,
                        'user_id': user_id,
                    }
            
            self._last_meta_refresh = now
            logger.debug(f"🔗 Refreshed account metadata: {len(self._account_meta)} accounts")
            
        except Exception as e:
            logger.warning(f"🔗 Failed to refresh account metadata: {e}")
    
    def _get_account_meta(self, account_id: int) -> dict:
        """Get metadata for an account"""
        with self._account_meta_lock:
            return self._account_meta.get(account_id, {
                'account_name': f'Account-{account_id}',
                'is_demo': True,
                'user_id': None,
            })
    
    def publish_hook(self, publisher):
        """
        Hook called by UIPublisher before each publish tick.
        
        This is where we emit the legacy `position_update` event.
        """
        try:
            # Check if StateCache has new data
            cache_stats = self._cache.get_stats()
            current_sequence = cache_stats.get('current_sequence', 0)
            
            # Skip if no change since last emit
            if current_sequence <= self._last_emitted_sequence:
                self._stats['skipped_no_change'] += 1
                return
            
            # Refresh account metadata periodically
            self._refresh_account_metadata()
            
            # Build pnl_data in legacy format
            pnl_data = self._build_legacy_pnl_data()
            
            if not pnl_data:
                self._stats['skipped_no_data'] += 1
                return
            
            # Build positions list
            positions_list = self._build_legacy_positions()
            
            # Emit on legacy channel
            self._socketio.emit('position_update', {
                'positions': positions_list,
                'count': len(positions_list),
                'pnl_data': pnl_data,
                'timestamp': datetime.now().isoformat(),
                'source': 'scalability_bridge',  # Mark source for debugging
            })
            
            self._last_emitted_sequence = current_sequence
            self._stats['emits'] += 1
            
            if self._stats['emits'] % 60 == 0:  # Log every minute
                logger.debug(f"🔗 LegacyBridge: {self._stats['emits']} emits, "
                           f"{self._stats['skipped_no_change']} skipped (no change)")
            
        except Exception as e:
            self._stats['errors'] += 1
            logger.warning(f"🔗 LegacyBridge error: {e}")
    
    def _build_legacy_pnl_data(self) -> Dict[int, dict]:
        """
        Build pnl_data dict in the format the legacy UI expects.
        
        Expected format:
        {
            account_id: {
                'account_name': str,
                'is_demo': bool,
                'user_id': int|None,
                'open_pnl': float,      # Unrealized PnL
                'realized_pnl': float,  # Today's realized
                'net_liq': float,       # Net liquidation value
                'total_cash_value': float,
                'total_pnl': float,
                ...
            }
        }
        """
        pnl_data = {}
        
        # Get all accounts with PnL data in cache
        all_snapshot = self._cache.get_all_accounts_snapshot()
        accounts = all_snapshot.get('accounts', {})
        
        for acc_id, snapshot in accounts.items():
            pnl = snapshot.get('pnl') or {}
            balance = snapshot.get('balance') or {}
            meta = self._get_account_meta(acc_id)
            
            # Map Tradovate WebSocket field names to legacy format
            # Tradovate sends: openPnL, realizedPnL, netLiq, totalCashValue, etc.
            pnl_data[acc_id] = {
                'account_name': meta.get('account_name', f'Account-{acc_id}'),
                'is_demo': meta.get('is_demo', True),
                'user_id': meta.get('user_id'),
                
                # Core PnL fields (from cashBalance entity)
                'open_pnl': pnl.get('openPnL', 0) or pnl.get('open_pnl', 0),
                'realized_pnl': pnl.get('realizedPnL', 0) or pnl.get('realized_pnl', 0),
                'net_liq': pnl.get('netLiq', 0) or pnl.get('net_liq', 0),
                'total_cash_value': pnl.get('totalCashValue', 0) or pnl.get('total_cash_value', 0),
                'total_pnl': pnl.get('totalPnL', 0) or pnl.get('total_pnl', 0),
                'week_realized_pnl': pnl.get('weekRealizedPnL', 0) or pnl.get('week_realized_pnl', 0),
                
                # Margin fields (from marginSnapshot entity)
                'initial_margin': balance.get('initialMargin', 0) or balance.get('initial_margin', 0),
                'maintenance_margin': balance.get('maintenanceMargin', 0) or balance.get('maintenance_margin', 0),
            }
        
        return pnl_data
    
    def _build_legacy_positions(self) -> list:
        """
        Build positions list in the format the legacy UI expects.
        
        Expected format:
        [
            {
                'account_id': int,
                'account_name': str,
                'is_demo': bool,
                'user_id': int|None,
                'contract_id': int,
                'symbol': str,
                'net_quantity': int,
                'avg_price': float,
                ...
            }
        ]
        """
        positions_list = []
        
        all_snapshot = self._cache.get_all_accounts_snapshot()
        accounts = all_snapshot.get('accounts', {})
        
        for acc_id, snapshot in accounts.items():
            positions = snapshot.get('positions', [])
            meta = self._get_account_meta(acc_id)
            
            for pos in positions:
                # Skip flat positions
                net_qty = pos.get('netPos', 0) or pos.get('net_quantity', 0)
                if net_qty == 0:
                    continue
                
                positions_list.append({
                    'account_id': acc_id,
                    'account_name': meta.get('account_name', f'Account-{acc_id}'),
                    'is_demo': meta.get('is_demo', True),
                    'user_id': meta.get('user_id'),
                    'contract_id': pos.get('contractId', pos.get('contract_id')),
                    'symbol': pos.get('symbol', pos.get('contractName', 'Unknown')),
                    'net_quantity': net_qty,
                    'bought': pos.get('bought', 0),
                    'bought_value': pos.get('boughtValue', pos.get('bought_value', 0)),
                    'sold': pos.get('sold', 0),
                    'sold_value': pos.get('soldValue', pos.get('sold_value', 0)),
                    'avg_price': pos.get('avgPrice', pos.get('avg_price', 0)),
                    'timestamp': pos.get('timestamp'),
                })
        
        return positions_list
    
    def get_stats(self) -> dict:
        """Get bridge statistics"""
        return {
            **self._stats,
            'last_emitted_sequence': self._last_emitted_sequence,
            'accounts_tracked': len(self._account_meta),
        }


# Module-level singleton
_legacy_bridge: Optional[LegacyBridge] = None
_bridge_lock = threading.Lock()


def get_legacy_bridge() -> Optional[LegacyBridge]:
    """Get the global LegacyBridge instance"""
    return _legacy_bridge


def init_legacy_bridge(socketio, state_cache=None, db_connection_func=None) -> Optional[LegacyBridge]:
    """
    Initialize and return the LegacyBridge singleton.
    
    Should be called after UIPublisher is initialized.
    """
    global _legacy_bridge
    
    if not LEGACY_BRIDGE_ENABLED:
        logger.info("🔗 LegacyBridge disabled (set SCALABILITY_LEGACY_BRIDGE=1 to enable)")
        return None
    
    with _bridge_lock:
        if _legacy_bridge is None:
            _legacy_bridge = LegacyBridge(
                socketio=socketio,
                state_cache=state_cache,
                db_connection_func=db_connection_func,
            )
            logger.info("✅ LegacyBridge created")
        return _legacy_bridge


def attach_to_publisher(publisher) -> bool:
    """
    Attach the LegacyBridge to a UIPublisher instance.
    
    Call this after both are initialized.
    """
    bridge = get_legacy_bridge()
    if bridge is None:
        return False
    
    publisher.add_pre_publish_hook(bridge.publish_hook)
    logger.info("✅ LegacyBridge attached to UIPublisher")
    return True
