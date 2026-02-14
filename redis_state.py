"""
Redis Shared State Module
=========================
Provides Redis-backed shared state for the split architecture.
When EXTERNAL_TRADING_ENGINE=1, both the web server and trading engine
use these functions to read/write shared state via Redis.

When running in single-process mode, falls back to in-memory dicts.
"""

import os
import json
import time
import logging
import threading
from datetime import datetime

logger = logging.getLogger('redis_state')

REDIS_URL = os.environ.get('REDIS_URL')
_redis_client = None


def _get_redis():
    """Get Redis client for state operations."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not REDIS_URL:
        return None
    try:
        import redis
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis state connection failed: {e}")
        return None


# ============================================================================
# BROKER EXECUTION STATS (Redis Hash: "jt:broker_stats")
# ============================================================================

def update_broker_stat(field, value):
    """Set a broker execution stat field."""
    r = _get_redis()
    if r:
        try:
            r.hset('jt:broker_stats', field, json.dumps(value, default=str))
        except Exception as e:
            logger.warning(f"Redis update_broker_stat error: {e}")


def increment_broker_stat(field, amount=1):
    """Increment a numeric broker stat."""
    r = _get_redis()
    if r:
        try:
            r.hincrby('jt:broker_stats', field, amount)
        except Exception as e:
            logger.warning(f"Redis increment_broker_stat error: {e}")


def get_broker_stats():
    """Get all broker execution stats."""
    r = _get_redis()
    if r:
        try:
            raw = r.hgetall('jt:broker_stats')
            result = {}
            for k, v in raw.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            return result
        except Exception as e:
            logger.warning(f"Redis get_broker_stats error: {e}")
    return {
        'total_queued': 0,
        'total_executed': 0,
        'total_failed': 0,
        'last_execution_time': None,
        'last_error': None
    }


# ============================================================================
# BROKER FAILURES (Redis List: "jt:broker_failures", capped at 50)
# ============================================================================

def push_broker_failure(recorder_id, action, ticker, error, failed_accounts=None):
    """Log a broker execution failure to Redis."""
    r = _get_redis()
    if r:
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'recorder_id': recorder_id,
                'action': action,
                'ticker': ticker,
                'error': str(error)[:200],
                'failed_accounts': failed_accounts or []
            }
            r.rpush('jt:broker_failures', json.dumps(entry, default=str))
            r.ltrim('jt:broker_failures', -50, -1)  # Keep last 50
        except Exception as e:
            logger.warning(f"Redis push_broker_failure error: {e}")


def get_broker_failures_from_redis(limit=20):
    """Get recent broker failures from Redis."""
    r = _get_redis()
    if r:
        try:
            raw = r.lrange('jt:broker_failures', -limit, -1)
            failures = []
            for item in reversed(raw):
                try:
                    failures.append(json.loads(item))
                except (json.JSONDecodeError, TypeError):
                    pass
            return failures
        except Exception as e:
            logger.warning(f"Redis get_broker_failures error: {e}")
    return []


# ============================================================================
# SIGNAL TRACKING (Redis Hash: "jt:signal_pipeline")
# ============================================================================

def redis_track_signal_step(signal_id, step, details=None):
    """Track a signal step in Redis."""
    r = _get_redis()
    if r:
        try:
            key = f'jt:signal:{signal_id}'
            existing = r.get(key)
            if existing:
                data = json.loads(existing)
            else:
                data = {
                    'created': datetime.now().isoformat(),
                    'steps': [],
                    'status': 'pending',
                    'last_update': datetime.now().isoformat()
                }
            data['steps'].append({
                'step': step,
                'timestamp': datetime.now().isoformat(),
                'details': details or {}
            })
            data['last_update'] = datetime.now().isoformat()
            r.setex(key, 3600, json.dumps(data, default=str))  # TTL 1 hour
        except Exception as e:
            logger.warning(f"Redis track_signal_step error: {e}")


def redis_complete_signal(signal_id, status='complete', error=None):
    """Mark a signal as complete/failed in Redis."""
    r = _get_redis()
    if r:
        try:
            key = f'jt:signal:{signal_id}'
            existing = r.get(key)
            if existing:
                data = json.loads(existing)
                data['status'] = status
                if error:
                    data['error'] = error
                r.setex(key, 3600, json.dumps(data, default=str))
        except Exception as e:
            logger.warning(f"Redis complete_signal error: {e}")


# ============================================================================
# BREAK-EVEN MONITORS (Redis Hash: "jt:be_monitors")
# ============================================================================

def redis_register_break_even(key, monitor_data):
    """Register a break-even monitor in Redis."""
    r = _get_redis()
    if r:
        try:
            r.hset('jt:be_monitors', key, json.dumps(monitor_data, default=str))
        except Exception as e:
            logger.warning(f"Redis register_break_even error: {e}")


def redis_get_break_even_monitors():
    """Get all break-even monitors from Redis."""
    r = _get_redis()
    if r:
        try:
            raw = r.hgetall('jt:be_monitors')
            result = {}
            for k, v in raw.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    pass
            return result
        except Exception as e:
            logger.warning(f"Redis get_break_even_monitors error: {e}")
    return {}


def redis_remove_break_even(key):
    """Remove a break-even monitor from Redis."""
    r = _get_redis()
    if r:
        try:
            r.hdel('jt:be_monitors', key)
        except Exception as e:
            logger.warning(f"Redis remove_break_even error: {e}")


# ============================================================================
# OCO PAIRS (Redis Hash: "jt:oco_pairs" and "jt:oco_details")
# ============================================================================

def redis_register_oco(tp_order_id, sl_order_id, account_id, symbol):
    """Register an OCO pair in Redis."""
    r = _get_redis()
    if r:
        try:
            # Store bidirectional mapping
            r.hset('jt:oco_pairs', str(tp_order_id), str(sl_order_id))
            r.hset('jt:oco_pairs', str(sl_order_id), str(tp_order_id))
            # Store details
            r.hset('jt:oco_details', str(tp_order_id), json.dumps({
                'account_id': account_id, 'symbol': symbol, 'type': 'tp', 'partner_id': sl_order_id
            }))
            r.hset('jt:oco_details', str(sl_order_id), json.dumps({
                'account_id': account_id, 'symbol': symbol, 'type': 'sl', 'partner_id': tp_order_id
            }))
        except Exception as e:
            logger.warning(f"Redis register_oco error: {e}")


def redis_get_oco_pairs():
    """Get all OCO pairs from Redis."""
    r = _get_redis()
    if r:
        try:
            return r.hgetall('jt:oco_pairs')
        except Exception as e:
            logger.warning(f"Redis get_oco_pairs error: {e}")
    return {}


def redis_get_oco_details():
    """Get all OCO details from Redis."""
    r = _get_redis()
    if r:
        try:
            raw = r.hgetall('jt:oco_details')
            result = {}
            for k, v in raw.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    pass
            return result
        except Exception as e:
            logger.warning(f"Redis get_oco_details error: {e}")
    return {}


def redis_remove_oco(order_id):
    """Remove an OCO pair from Redis."""
    r = _get_redis()
    if r:
        try:
            partner = r.hget('jt:oco_pairs', str(order_id))
            r.hdel('jt:oco_pairs', str(order_id))
            r.hdel('jt:oco_details', str(order_id))
            if partner:
                r.hdel('jt:oco_pairs', partner)
                r.hdel('jt:oco_details', partner)
        except Exception as e:
            logger.warning(f"Redis remove_oco error: {e}")


# ============================================================================
# WEBHOOK DEDUP (Redis key with TTL: "jt:dedup:{hash}")
# ============================================================================

def redis_check_dedup(dedup_key, window_seconds=1):
    """Check and set dedup key. Returns True if duplicate (already exists)."""
    r = _get_redis()
    if r:
        try:
            # SET NX (only if not exists) with EX (expiry)
            result = r.set(f'jt:dedup:{dedup_key}', '1', nx=True, ex=window_seconds)
            return result is None  # None means key already existed = duplicate
        except Exception as e:
            logger.warning(f"Redis dedup error: {e}")
    return False  # If Redis fails, allow through


# ============================================================================
# ENGINE HEALTH (Redis key: "jt:engine_heartbeat")
# ============================================================================

def engine_heartbeat(worker_count=0, uptime=0):
    """Trading engine publishes its health status."""
    r = _get_redis()
    if r:
        try:
            r.setex('jt:engine_heartbeat', 30, json.dumps({
                'timestamp': time.time(),
                'workers_alive': worker_count,
                'uptime_seconds': uptime,
                'pid': os.getpid()
            }))
        except Exception as e:
            logger.warning(f"Redis engine_heartbeat error: {e}")


def get_engine_health():
    """Web server reads trading engine health."""
    r = _get_redis()
    if r:
        try:
            raw = r.get('jt:engine_heartbeat')
            if raw:
                data = json.loads(raw)
                data['age_seconds'] = time.time() - data.get('timestamp', 0)
                data['healthy'] = data['age_seconds'] < 30
                return data
        except Exception as e:
            logger.warning(f"Redis get_engine_health error: {e}")
    return {'healthy': False, 'error': 'No heartbeat from trading engine'}
