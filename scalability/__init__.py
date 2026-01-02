"""
Scalability Module for Just.Trades
==================================

This module provides scalable infrastructure for 100+ concurrent users:
- Real-time state from WebSocket (not REST polling)
- 1 Hz consolidated UI updates
- Per-account order queuing with priority lanes
- Penalty-aware retry for rate limiting

FEATURE FLAGS
-------------
All features are disabled by default. Enable gradually:

    from scalability import FEATURES
    FEATURES['ui_publisher_enabled'] = True

Or via environment variables:
    SCALABILITY_UI_PUBLISHER=1
    SCALABILITY_WS_STATE_MANAGER=1
    SCALABILITY_ORDER_DISPATCHER=1

This module is ADDITIVE - it doesn't modify existing code.
Enable features one at a time and test before enabling the next.
"""

import os
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# FEATURE FLAGS - All disabled by default for safety
# ============================================================================
FEATURES = {
    # 1 Hz UI Publisher - coalesces updates into 1-second packets
    'ui_publisher_enabled': os.environ.get('SCALABILITY_UI_PUBLISHER', '0') == '1',
    
    # WebSocket State Manager - uses user/syncrequest instead of REST polling
    'ws_state_manager_enabled': os.environ.get('SCALABILITY_WS_STATE_MANAGER', '0') == '1',
    
    # Order Dispatcher - per-account queues with priority lanes
    'order_dispatcher_enabled': os.environ.get('SCALABILITY_ORDER_DISPATCHER', '0') == '1',
    
    # Event Ledger - append-only event store for audit trail
    'event_ledger_enabled': os.environ.get('SCALABILITY_EVENT_LEDGER', '0') == '1',
}

def enable_feature(feature_name: str) -> bool:
    """Enable a feature at runtime"""
    if feature_name in FEATURES:
        FEATURES[feature_name] = True
        logger.info(f"✅ Scalability feature enabled: {feature_name}")
        return True
    logger.warning(f"⚠️ Unknown feature: {feature_name}")
    return False

def disable_feature(feature_name: str) -> bool:
    """Disable a feature at runtime"""
    if feature_name in FEATURES:
        FEATURES[feature_name] = False
        logger.info(f"🔴 Scalability feature disabled: {feature_name}")
        return True
    logger.warning(f"⚠️ Unknown feature: {feature_name}")
    return False

def get_feature_status() -> dict:
    """Get current status of all features"""
    return {
        'features': FEATURES.copy(),
        'all_enabled': all(FEATURES.values()),
        'any_enabled': any(FEATURES.values()),
    }

# Log feature status on import
def _log_feature_status():
    enabled = [k for k, v in FEATURES.items() if v]
    disabled = [k for k, v in FEATURES.items() if not v]
    
    if enabled:
        logger.info(f"📊 Scalability features ENABLED: {', '.join(enabled)}")
    if disabled:
        logger.debug(f"📊 Scalability features disabled: {', '.join(disabled)}")

_log_feature_status()

# ============================================================================
# Module Exports
# ============================================================================
__all__ = [
    # Feature flags
    'FEATURES',
    'enable_feature',
    'disable_feature', 
    'get_feature_status',
    # Components (lazy loaded)
    'get_ui_publisher',
    'get_state_cache',
    'get_event_ledger',
    'get_order_dispatcher',
    'get_ws_manager',
    # Integration
    'init_scalability',
    'get_scalability_status',
    'quick_start',
]

# Lazy imports to avoid circular dependencies
def get_ui_publisher():
    """Get the UI Publisher instance (lazy load)"""
    from .ui_publisher import get_ui_publisher as _get
    return _get()

def get_state_cache():
    """Get the State Cache instance (lazy load)"""
    from .state_cache import get_global_cache
    return get_global_cache()

def get_event_ledger():
    """Get the Event Ledger instance (lazy load)"""
    from .event_ledger import get_ledger
    return get_ledger()

def get_order_dispatcher():
    """Get the Order Dispatcher instance (lazy load)"""
    from .order_dispatcher import get_dispatcher
    return get_dispatcher()

def get_ws_manager():
    """Get the Broker WS Manager instance (lazy load)"""
    from .broker_ws_manager import get_ws_manager as _get
    return _get()

# Integration shortcuts
def init_scalability(socketio, db_func=None, auto_start=False):
    """Initialize the scalability module"""
    from .integration import init_scalability as _init
    return _init(socketio, db_func, auto_start)

def get_scalability_status():
    """Get status of all scalability components"""
    from .integration import get_scalability_status as _get
    return _get()

def quick_start(socketio, db_func=None, features=None):
    """Quick start with default features"""
    from .integration import quick_start as _quick
    return _quick(socketio, db_func, features)
