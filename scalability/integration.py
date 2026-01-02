"""
Integration Module for Just.Trades Scalability
===============================================

This module provides the glue code to integrate scalability components
with the existing ultra_simple_server.py.

USAGE INSTRUCTIONS
------------------

1. IMPORT in ultra_simple_server.py (near other imports):

    # Scalability module (optional, feature-flagged)
    try:
        from scalability.integration import (
            init_scalability,
            get_scalability_status,
            register_scalability_routes,
            SCALABILITY_AVAILABLE
        )
    except ImportError:
        SCALABILITY_AVAILABLE = False

2. INITIALIZE after SocketIO setup:

    if SCALABILITY_AVAILABLE:
        init_scalability(socketio, get_db_connection)

3. REGISTER ROUTES after other routes:

    if SCALABILITY_AVAILABLE:
        register_scalability_routes(app)

4. ENABLE FEATURES via environment or runtime:

    # Environment variables:
    export SCALABILITY_UI_PUBLISHER=1
    export SCALABILITY_WS_STATE_MANAGER=1
    
    # Or runtime:
    from scalability import enable_feature
    enable_feature('ui_publisher_enabled')

This integration is ADDITIVE - it doesn't replace existing functionality.
Enable features one at a time and test before enabling the next.
"""

import logging
import time
import threading
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)

# Track initialization state
_initialized = False
_socketio = None
_db_func = None

# Export availability flag
SCALABILITY_AVAILABLE = True


def init_scalability(
    socketio,
    db_connection_func: Callable = None,
    auto_start: bool = False
) -> dict:
    """
    Initialize the scalability module.
    
    Args:
        socketio: Flask-SocketIO instance
        db_connection_func: Function that returns a database connection
        auto_start: Whether to auto-start enabled components
        
    Returns:
        Status dict with initialization results
    """
    global _initialized, _socketio, _db_func
    
    if _initialized:
        logger.warning("Scalability already initialized")
        return get_scalability_status()
    
    _socketio = socketio
    _db_func = db_connection_func
    
    results = {
        'initialized': False,
        'components': {}
    }
    
    try:
        # Import feature flags
        from . import FEATURES
        
        # Initialize Event Ledger (always, for audit trail)
        if FEATURES.get('event_ledger_enabled'):
            from .event_ledger import init_ledger
            db = db_connection_func() if db_connection_func else None
            init_ledger(db_connection=db)
            results['components']['event_ledger'] = 'initialized'
            logger.info("✅ Event Ledger initialized")
        
        # Initialize State Cache (always needed for UI publisher)
        from .state_cache import get_global_cache
        cache = get_global_cache()
        results['components']['state_cache'] = 'initialized'
        logger.info("✅ State Cache initialized")
        
        # Initialize UI Publisher if enabled
        if FEATURES.get('ui_publisher_enabled') and auto_start:
            from .ui_publisher import start_ui_publisher
            publisher = start_ui_publisher(socketio)
            results['components']['ui_publisher'] = 'started' if publisher.is_running() else 'failed'
            logger.info("✅ UI Publisher started (1 Hz updates)")
        elif FEATURES.get('ui_publisher_enabled'):
            results['components']['ui_publisher'] = 'ready (not started)'
        
        # Initialize Order Dispatcher if enabled
        if FEATURES.get('order_dispatcher_enabled'):
            from .order_dispatcher import init_dispatcher
            # Dispatcher needs an execute function - we'll provide a bridge later
            init_dispatcher(execute_func=_default_execute_func)
            results['components']['order_dispatcher'] = 'initialized (not started)'
            logger.info("✅ Order Dispatcher initialized")
        
        # Initialize WebSocket Manager if enabled
        if FEATURES.get('ws_state_manager_enabled') and auto_start:
            from .broker_ws_manager import start_ws_manager
            manager = start_ws_manager()
            results['components']['ws_state_manager'] = 'started' if manager.is_running() else 'failed'
            logger.info("✅ Broker WS Manager started")
        elif FEATURES.get('ws_state_manager_enabled'):
            results['components']['ws_state_manager'] = 'ready (not started)'
        
        _initialized = True
        results['initialized'] = True
        
        logger.info("✅ Scalability module initialized")
        logger.info(f"   Components: {results['components']}")
        
    except Exception as e:
        logger.error(f"❌ Scalability initialization failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        results['error'] = str(e)
    
    return results


def _default_execute_func(task) -> dict:
    """
    Default execute function for OrderDispatcher.
    This is a placeholder - in production, wire this to your broker execution code.
    """
    logger.warning(f"Default execute called for task {task.task_id} - wire to actual broker execution!")
    return {
        'success': False,
        'error': 'Order dispatcher not wired to broker execution'
    }


def get_scalability_status() -> dict:
    """Get current status of all scalability components"""
    from . import FEATURES, get_feature_status
    
    status = {
        'initialized': _initialized,
        'features': get_feature_status(),
        'components': {}
    }
    
    # Check each component
    try:
        from .state_cache import get_global_cache
        cache = get_global_cache()
        status['components']['state_cache'] = cache.get_stats()
    except:
        status['components']['state_cache'] = None
    
    try:
        from .event_ledger import get_ledger
        ledger = get_ledger()
        status['components']['event_ledger'] = ledger.get_stats() if ledger else None
    except:
        status['components']['event_ledger'] = None
    
    try:
        from .ui_publisher import get_ui_publisher
        publisher = get_ui_publisher()
        status['components']['ui_publisher'] = publisher.get_stats() if publisher else None
    except:
        status['components']['ui_publisher'] = None
    
    try:
        from .order_dispatcher import get_dispatcher
        dispatcher = get_dispatcher()
        status['components']['order_dispatcher'] = dispatcher.get_stats() if dispatcher else None
    except:
        status['components']['order_dispatcher'] = None
    
    try:
        from .broker_ws_manager import get_ws_manager
        manager = get_ws_manager()
        status['components']['ws_state_manager'] = manager.get_stats() if manager else None
    except:
        status['components']['ws_state_manager'] = None
    
    return status


def register_scalability_routes(app):
    """
    Register Flask routes for scalability API endpoints.
    
    Endpoints:
        GET /api/scalability/status - Get status of all components
        GET /api/scalability/health - Health check for monitoring
        POST /api/scalability/feature/<name>/enable - Enable a feature
        POST /api/scalability/feature/<name>/disable - Disable a feature
        POST /api/scalability/ui-publisher/start - Start UI publisher
        POST /api/scalability/ui-publisher/stop - Stop UI publisher
        POST /api/scalability/ws-manager/add-account - Add account to WS monitoring
    """
    from flask import jsonify, request
    
    @app.route('/api/scalability/status')
    def scalability_status():
        """Get scalability module status"""
        return jsonify(get_scalability_status())
    
    @app.route('/api/scalability/health')
    def scalability_health():
        """Health check for monitoring"""
        status = get_scalability_status()
        
        # Aggregate health
        healthy = status['initialized']
        
        components_health = {}
        for name, data in status.get('components', {}).items():
            if isinstance(data, dict) and 'healthy' in data:
                components_health[name] = data['healthy']
                if not data['healthy']:
                    healthy = False
            elif data is not None:
                components_health[name] = True
            else:
                components_health[name] = None
        
        return jsonify({
            'healthy': healthy,
            'initialized': status['initialized'],
            'components': components_health,
            'timestamp': time.time()
        })
    
    @app.route('/api/scalability/feature/<name>/enable', methods=['POST'])
    def enable_scalability_feature(name):
        """Enable a scalability feature"""
        from . import enable_feature
        success = enable_feature(name)
        return jsonify({
            'success': success,
            'feature': name,
            'status': get_scalability_status()['features']
        })
    
    @app.route('/api/scalability/feature/<name>/disable', methods=['POST'])
    def disable_scalability_feature(name):
        """Disable a scalability feature"""
        from . import disable_feature
        success = disable_feature(name)
        return jsonify({
            'success': success,
            'feature': name,
            'status': get_scalability_status()['features']
        })
    
    @app.route('/api/scalability/ui-publisher/start', methods=['POST'])
    def start_ui_publisher_route():
        """Start the UI publisher"""
        try:
            from .ui_publisher import start_ui_publisher, get_ui_publisher
            
            publisher = get_ui_publisher()
            if publisher and publisher.is_running():
                return jsonify({
                    'success': True,
                    'message': 'UI Publisher already running',
                    'stats': publisher.get_stats()
                })
            
            if not _socketio:
                return jsonify({
                    'success': False,
                    'error': 'SocketIO not initialized'
                }), 400
            
            publisher = start_ui_publisher(_socketio)
            return jsonify({
                'success': True,
                'message': 'UI Publisher started',
                'stats': publisher.get_stats()
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/scalability/ui-publisher/stop', methods=['POST'])
    def stop_ui_publisher_route():
        """Stop the UI publisher"""
        try:
            from .ui_publisher import stop_ui_publisher, get_ui_publisher
            
            publisher = get_ui_publisher()
            if not publisher or not publisher.is_running():
                return jsonify({
                    'success': True,
                    'message': 'UI Publisher not running'
                })
            
            stop_ui_publisher()
            return jsonify({
                'success': True,
                'message': 'UI Publisher stopped'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/scalability/ws-manager/add-account', methods=['POST'])
    def add_account_to_ws_manager():
        """Add an account to WebSocket monitoring"""
        try:
            from .broker_ws_manager import get_ws_manager
            
            manager = get_ws_manager()
            if not manager:
                return jsonify({
                    'success': False,
                    'error': 'WS Manager not initialized'
                }), 400
            
            data = request.json or {}
            account_id = data.get('account_id')
            access_token = data.get('access_token')
            is_demo = data.get('is_demo', True)
            
            if not account_id or not access_token:
                return jsonify({
                    'success': False,
                    'error': 'account_id and access_token required'
                }), 400
            
            manager.add_account(account_id, access_token, is_demo)
            
            return jsonify({
                'success': True,
                'message': f'Account {account_id} added to monitoring',
                'stats': manager.get_stats()
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/scalability/dispatcher/stats')
    def dispatcher_stats():
        """Get Order Dispatcher statistics"""
        try:
            from .order_dispatcher import get_dispatcher
            dispatcher = get_dispatcher()
            if not dispatcher:
                return jsonify({'error': 'Dispatcher not initialized'}), 404
            return jsonify(dispatcher.get_stats())
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/scalability/cache/stats')
    def cache_stats():
        """Get State Cache statistics"""
        try:
            from .state_cache import get_global_cache
            cache = get_global_cache()
            return jsonify(cache.get_stats())
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/scalability/ledger/stats')
    def ledger_stats():
        """Get Event Ledger statistics"""
        try:
            from .event_ledger import get_ledger
            ledger = get_ledger()
            if not ledger:
                return jsonify({'error': 'Ledger not initialized'}), 404
            return jsonify(ledger.get_stats())
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    logger.info("✅ Scalability API routes registered")


# ============================================================================
# SOCKETIO EVENT HANDLERS
# ============================================================================

def register_scalability_socketio_handlers(socketio):
    """
    Register SocketIO event handlers for scalability features.
    
    Events:
        subscribe_scalability - Client subscribes to scalability updates
        unsubscribe_scalability - Client unsubscribes
    """
    from flask import request
    
    @socketio.on('subscribe_scalability')
    def handle_subscribe_scalability(data):
        """Handle client subscription to scalability updates"""
        try:
            from .ui_publisher import get_ui_publisher
            
            publisher = get_ui_publisher()
            if not publisher:
                return {'success': False, 'error': 'UI Publisher not running'}
            
            client_id = request.sid
            account_ids = set(data.get('account_ids', []))
            
            publisher.register_client(client_id, account_ids)
            
            return {
                'success': True,
                'client_id': client_id,
                'account_ids': list(account_ids)
            }
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return {'success': False, 'error': str(e)}
    
    @socketio.on('unsubscribe_scalability')
    def handle_unsubscribe_scalability():
        """Handle client unsubscription"""
        try:
            from .ui_publisher import get_ui_publisher
            
            publisher = get_ui_publisher()
            if publisher:
                publisher.unregister_client(request.sid)
            
            return {'success': True}
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")
            return {'success': False, 'error': str(e)}
    
    @socketio.on('disconnect')
    def handle_scalability_disconnect():
        """Clean up on client disconnect"""
        try:
            from .ui_publisher import get_ui_publisher
            
            publisher = get_ui_publisher()
            if publisher:
                publisher.unregister_client(request.sid)
        except:
            pass
    
    logger.info("✅ Scalability SocketIO handlers registered")


# ============================================================================
# HELPER: WIRE ORDER DISPATCHER TO EXISTING BROKER EXECUTION
# ============================================================================

def wire_dispatcher_to_broker_execution(execute_simple_func: Callable):
    """
    Wire the Order Dispatcher to use your existing broker execution function.
    
    Usage:
        from scalability.integration import wire_dispatcher_to_broker_execution
        
        # Point dispatcher at your existing execute function
        wire_dispatcher_to_broker_execution(execute_simple)
        
    Args:
        execute_simple_func: Your existing function that places orders
    """
    from .order_dispatcher import get_dispatcher, OrderTask
    
    def execute_wrapper(task: OrderTask) -> dict:
        """Wrap the task execution"""
        try:
            # Extract parameters from task
            payload = task.payload
            
            # Call the existing execute function
            result = execute_simple_func(
                account_id=task.account_id,
                action=payload.get('action'),
                symbol=payload.get('symbol'),
                quantity=payload.get('quantity'),
                order_type=payload.get('order_type', 'Market'),
                price=payload.get('price'),
                stop_price=payload.get('stop_price')
            )
            
            # Check for penalty response
            if isinstance(result, dict):
                if result.get('p_time') or result.get('penalty'):
                    return {
                        'penalized': True,
                        'p_time': result.get('p_time', 10),
                        'p_ticket': result.get('p_ticket')
                    }
                elif result.get('status') == 429:
                    return {'rate_limited': True}
                elif result.get('success') or result.get('orderId'):
                    return {'success': True, 'result': result}
                else:
                    return {'success': False, 'error': result.get('error', 'Unknown error')}
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            logger.error(f"Execute wrapper error: {e}")
            return {'success': False, 'error': str(e)}
    
    dispatcher = get_dispatcher()
    if dispatcher:
        dispatcher._execute_func = execute_wrapper
        logger.info("✅ Order Dispatcher wired to broker execution")
    else:
        logger.warning("Order Dispatcher not initialized")


# ============================================================================
# QUICK START
# ============================================================================

def quick_start(socketio, db_func=None, features: list = None):
    """
    Quick start with specified features enabled.
    
    Usage:
        from scalability.integration import quick_start
        quick_start(socketio, features=['ui_publisher', 'event_ledger'])
    
    Args:
        socketio: Flask-SocketIO instance
        db_func: Optional database connection function
        features: List of features to enable (defaults to all)
    """
    from . import enable_feature
    
    # Enable requested features
    if features is None:
        features = ['ui_publisher_enabled', 'event_ledger_enabled']
    
    for feature in features:
        # Normalize feature name
        if not feature.endswith('_enabled'):
            feature = f"{feature}_enabled"
        enable_feature(feature)
    
    # Initialize
    return init_scalability(socketio, db_func, auto_start=True)
