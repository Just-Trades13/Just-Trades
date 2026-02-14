#!/usr/bin/env python3
"""
Trading Engine — Separate Process for Broker Execution
=======================================================
Consumes broker tasks from Redis queue, executes trades via recorder_service,
and publishes results back to Redis for the web server to read.

This process runs alongside ultra_simple_server.py when EXTERNAL_TRADING_ENGINE=1.

Start: python trading_engine.py
Stop: Kill the process (or unset EXTERNAL_TRADING_ENGINE and restart)
"""

import os
import sys
import json
import time
import uuid
import logging
import threading
from queue import Empty
from datetime import datetime

# ============================================================================
# LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [TRADING-ENGINE] %(name)s %(levelname)s %(message)s'
)
logger = logging.getLogger('trading_engine')

# ============================================================================
# REDIS CONNECTION
# ============================================================================
REDIS_URL = os.environ.get('REDIS_URL')
if not REDIS_URL:
    logger.error("REDIS_URL environment variable is required for trading engine!")
    sys.exit(1)

try:
    import redis
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info(f"Connected to Redis")
except Exception as e:
    logger.error(f"Cannot connect to Redis: {e}")
    sys.exit(1)

# ============================================================================
# REDIS QUEUE (same class as in ultra_simple_server.py)
# ============================================================================
class RedisQueue:
    """Drop-in replacement for Python Queue backed by Redis."""

    def __init__(self, redis_client, key, maxsize=5000):
        self._redis = redis_client
        self._key = key
        self._maxsize = maxsize

    def put_nowait(self, item):
        if self.qsize() >= self._maxsize:
            from queue import Full
            raise Full()
        self._redis.rpush(self._key, json.dumps(item, default=str))

    def put(self, item, timeout=None):
        self.put_nowait(item)

    def get(self, timeout=1):
        result = self._redis.blpop(self._key, timeout=int(timeout))
        if result:
            return json.loads(result[1])
        raise Empty()

    def qsize(self):
        return self._redis.llen(self._key)

    def task_done(self):
        pass

    @property
    def maxsize(self):
        return self._maxsize

broker_execution_queue = RedisQueue(redis_client, 'broker_tasks', maxsize=5000)

# ============================================================================
# IMPORTS FROM EXISTING MODULES
# ============================================================================
from recorder_service import get_db_connection
# is_using_postgres: recorder_service uses module-level variable is_postgres (set by get_db_connection)
# We define a wrapper here that reads it from recorder_service
def is_using_postgres():
    import recorder_service
    return recorder_service.is_postgres
from redis_state import (
    increment_broker_stat, update_broker_stat, get_broker_stats,
    push_broker_failure, redis_track_signal_step, redis_complete_signal,
    engine_heartbeat
)

# Discord notifications
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN', '')
DISCORD_NOTIFICATIONS_ENABLED = bool(DISCORD_BOT_TOKEN)
if DISCORD_NOTIFICATIONS_ENABLED:
    try:
        from discord_notifications import notify_trade_execution, notify_error
        logger.info("Discord notifications enabled")
    except ImportError:
        DISCORD_NOTIFICATIONS_ENABLED = False
        logger.info("Discord notifications module not available")

# SocketIO Redis bridge — emit events to browser clients via the web server
try:
    import socketio as sio_ext
    sio_manager = sio_ext.RedisManager(REDIS_URL, write_only=True)
    logger.info("SocketIO Redis bridge initialized (write-only)")
except Exception as e:
    sio_manager = None
    logger.warning(f"SocketIO Redis bridge not available: {e}")

# ============================================================================
# BROKER EXECUTION STATS (backed by Redis)
# ============================================================================
# Local cache for fast access within this process, synced to Redis periodically
_local_stats = {
    'total_queued': 0,
    'total_executed': 0,
    'total_failed': 0,
    'last_execution_time': None,
    'last_error': None
}

def _sync_stats_to_redis():
    """Sync local stats to Redis."""
    try:
        for k, v in _local_stats.items():
            update_broker_stat(k, v)
    except Exception as e:
        logger.warning(f"Failed to sync stats to Redis: {e}")

# ============================================================================
# BREAK-EVEN MONITOR REGISTRATION VIA REDIS
# ============================================================================
def register_break_even_via_redis(account_id, symbol, entry_price, is_long,
                                   activation_ticks, tick_size, sl_order_id,
                                   quantity, account_spec):
    """Publish break-even registration request to Redis.
    The web server's break-even monitor thread picks this up."""
    try:
        data = json.dumps({
            'account_id': account_id,
            'symbol': symbol,
            'entry_price': entry_price,
            'is_long': is_long,
            'activation_ticks': activation_ticks,
            'tick_size': tick_size,
            'sl_order_id': sl_order_id,
            'quantity': quantity,
            'account_spec': account_spec
        }, default=str)
        redis_client.rpush('jt:break_even_requests', data)
    except Exception as e:
        logger.warning(f"Failed to publish break-even request: {e}")

# ============================================================================
# BROKER EXECUTION WORKER
# ============================================================================
# Adapted from ultra_simple_server.py broker_execution_worker()
# Changes:
#   - Uses Redis queue instead of Python Queue
#   - Uses redis_state for stats/tracking instead of in-memory dicts
#   - Uses register_break_even_via_redis instead of direct function call
#   - Discord notifications imported directly

def broker_execution_worker(worker_id=0):
    """
    Background worker that processes broker execution queue.
    HIVE MIND: Multiple workers process in parallel for instant execution.
    """
    logger.info(f"Broker execution worker #{worker_id} started (HIVE MIND)")
    logger.info(f"   Queue: Redis key 'broker_tasks', maxsize: {broker_execution_queue.maxsize}")

    while True:
        try:
            # Get next broker execution task (blocking with timeout)
            task = broker_execution_queue.get(timeout=1)

            recorder_id = task.get('recorder_id')
            action = task.get('action')
            ticker = task.get('ticker')
            quantity = task.get('quantity')
            tp_ticks = task.get('tp_ticks', 10)
            sl_ticks = task.get('sl_ticks', 0)
            break_even_enabled = task.get('break_even_enabled', False)
            break_even_ticks = task.get('break_even_ticks', 10)
            entry_price = task.get('entry_price', 0)
            is_long = task.get('is_long', True)
            risk_config = task.get('risk_config', {})
            sl_type = task.get('sl_type', 'Fixed')
            queued_at = task.get('queued_at', 0)
            signal_price = task.get('signal_price', 0)
            signal_id = task.get('signal_id', f'sig_broker_{uuid.uuid4().hex[:8]}')

            # STEP 7: Broker worker picked up task
            redis_track_signal_step(signal_id, 'STEP7_BROKER_WORKER_PICKED', {
                'worker_id': worker_id,
                'action': action,
                'ticker': ticker,
                'queue_remaining': broker_execution_queue.qsize()
            })

            logger.info(f"Worker #{worker_id} received task: {action} {quantity} {ticker} signal={signal_id} (recorder_id={recorder_id})")

            # STALENESS CHECK - Reject signals that are too old
            SIGNAL_MAX_AGE_SECONDS = 30
            if queued_at > 0:
                signal_age = time.time() - queued_at
                if signal_age > SIGNAL_MAX_AGE_SECONDS:
                    logger.warning(f"STALE SIGNAL REJECTED: {action} {ticker} was {signal_age:.1f}s old (max {SIGNAL_MAX_AGE_SECONDS}s)")
                    redis_track_signal_step(signal_id, 'STEP7_STALE_REJECTED', {'age_seconds': signal_age})
                    redis_complete_signal(signal_id, 'failed', f'Stale signal ({signal_age:.1f}s old)')
                    _local_stats['total_failed'] += 1
                    _local_stats['last_error'] = f'Stale signal rejected ({signal_age:.1f}s old)'
                    increment_broker_stat('total_failed')
                    update_broker_stat('last_error', f'Stale signal rejected ({signal_age:.1f}s old)')
                    broker_execution_queue.task_done()
                    continue
                else:
                    logger.info(f"Signal age: {signal_age:.2f}s (within {SIGNAL_MAX_AGE_SECONDS}s limit)")

            # NO RETRIES - Try once, if fail log and move on
            try:
                from recorder_service import execute_trade_simple

                # STEP 8: Calling Tradovate API
                redis_track_signal_step(signal_id, 'STEP8_CALLING_BROKER', {
                    'action': action,
                    'quantity': quantity,
                    'ticker': ticker,
                    'tp_ticks': tp_ticks,
                    'sl_ticks': sl_ticks,
                    'sl_type': sl_type,
                    'risk_config': risk_config
                })

                logger.info(f"Broker execution: {action} {quantity} {ticker} signal={signal_id}")
                logger.info(f"Calling execute_trade_simple: recorder_id={recorder_id}, action={action}, ticker={ticker}, quantity={quantity}")
                if risk_config:
                    logger.info(f"Risk config: {risk_config}")

                result = execute_trade_simple(
                    recorder_id=recorder_id,
                    action=action,
                    ticker=ticker,
                    quantity=quantity,
                    tp_ticks=tp_ticks,
                    sl_ticks=sl_ticks if sl_ticks > 0 else 0,
                    risk_config=risk_config
                )

                logger.info(f"execute_trade_simple returned: success={result.get('success')}, error={result.get('error')}, accounts_traded={result.get('accounts_traded', 0)}")

                if result.get('success'):
                    accounts_traded = result.get('accounts_traded', 0)
                    # STEP 9: Trade executed successfully
                    redis_track_signal_step(signal_id, 'STEP9_TRADE_SUCCESS', {
                        'accounts_traded': accounts_traded,
                        'fill_price': result.get('fill_price'),
                        'tp_price': result.get('tp_price')
                    })
                    redis_complete_signal(signal_id, 'complete')
                    logger.info(f"Broker execution successful: {action} {quantity} {ticker} on {accounts_traded} account(s) signal={signal_id}")
                    _local_stats['total_executed'] += 1
                    _local_stats['last_execution_time'] = time.time()
                    increment_broker_stat('total_executed')
                    update_broker_stat('last_execution_time', time.time())

                    # SocketIO emit: trade executed
                    if sio_manager:
                        try:
                            sio_manager.emit('trade_executed', {
                                'action': action,
                                'ticker': ticker,
                                'quantity': quantity,
                                'recorder_id': recorder_id,
                                'accounts_traded': accounts_traded,
                                'signal_id': signal_id
                            }, namespace='/')
                        except Exception:
                            pass

                    # Discord notification for successful trade
                    try:
                        if DISCORD_NOTIFICATIONS_ENABLED:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            if is_using_postgres():
                                cursor.execute('SELECT user_id, name FROM recorders WHERE id = %s', (recorder_id,))
                            else:
                                cursor.execute('SELECT user_id, name FROM recorders WHERE id = ?', (recorder_id,))
                            rec_row = cursor.fetchone()
                            conn.close()
                            if rec_row:
                                rec_user_id = rec_row[0] if isinstance(rec_row, tuple) else rec_row.get('user_id')
                                rec_name = rec_row[1] if isinstance(rec_row, tuple) else rec_row.get('name')
                                notify_trade_execution(
                                    action=action,
                                    symbol=ticker,
                                    quantity=quantity,
                                    price=entry_price if entry_price else 0,
                                    recorder_name=rec_name,
                                    recorder_id=recorder_id
                                )
                    except Exception as notif_err:
                        logger.warning(f"Discord notification failed: {notif_err}")

                    # Register break-even monitor if enabled (via Redis → web server)
                    if break_even_enabled and break_even_ticks > 0 and entry_price > 0:
                        try:
                            subaccount_id = result.get('subaccount_id')
                            account_spec = result.get('account_spec')
                            broker_avg = result.get('broker_avg') or entry_price

                            if subaccount_id:
                                from recorder_service import get_tick_size
                                tick_size_val = get_tick_size(ticker) if ticker else 0.25

                                register_break_even_via_redis(
                                    account_id=int(subaccount_id),
                                    symbol=ticker.upper(),
                                    entry_price=float(broker_avg),
                                    is_long=is_long,
                                    activation_ticks=break_even_ticks,
                                    tick_size=tick_size_val,
                                    sl_order_id=None,
                                    quantity=quantity,
                                    account_spec=account_spec or str(subaccount_id)
                                )
                                logger.info(f"Break-even monitor request published: {ticker} @ {broker_avg}, trigger={break_even_ticks} ticks")
                            else:
                                # Fallback: try executed_accounts list
                                executed_accounts = result.get('executed_accounts', [])
                                for acct_info in executed_accounts:
                                    acct_id = acct_info.get('subaccount_id') or acct_info.get('account_id')
                                    if acct_id:
                                        from recorder_service import get_tick_size
                                        tick_size_val = get_tick_size(ticker) if ticker else 0.25
                                        broker_avg_val = acct_info.get('broker_avg') or entry_price

                                        register_break_even_via_redis(
                                            account_id=int(acct_id),
                                            symbol=ticker.upper(),
                                            entry_price=float(broker_avg_val),
                                            is_long=is_long,
                                            activation_ticks=break_even_ticks,
                                            tick_size=tick_size_val,
                                            sl_order_id=None,
                                            quantity=quantity,
                                            account_spec=acct_info.get('account_spec') or str(acct_id)
                                        )
                        except Exception as be_err:
                            logger.warning(f"Could not register break-even monitor: {be_err}")
                            import traceback
                            logger.warning(traceback.format_exc())
                else:
                    error = result.get('error') or 'Unknown error'
                    logger.error(f"Broker execution FAILED: {error}")
                    logger.error(f"   Recorder ID: {recorder_id}, Action: {action}, Quantity: {quantity}, Ticker: {ticker}")
                    logger.error(f"   Full result: {result}")

                    # Enhanced diagnostics for common failures
                    if 'No accounts to trade on' in error or 'No trader linked' in error:
                        logger.error(f"   DIAGNOSTIC: Checking trader configuration for recorder {recorder_id}...")
                        try:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            is_postgres = is_using_postgres()
                            placeholder = '%s' if is_postgres else '?'

                            cursor.execute(f'''
                                SELECT t.id, t.enabled, t.enabled_accounts, t.recorder_id
                                FROM traders t
                                WHERE t.recorder_id = {placeholder}
                            ''', (recorder_id,))
                            traders = cursor.fetchall()
                            logger.error(f"   Found {len(traders)} trader(s) linked to recorder {recorder_id}")
                            for trader_row in traders:
                                trader = dict(trader_row) if hasattr(trader_row, 'keys') else {
                                    'id': trader_row[0],
                                    'enabled': trader_row[1],
                                    'enabled_accounts': trader_row[2],
                                    'recorder_id': trader_row[3]
                                }
                                enabled_accts = trader.get('enabled_accounts')
                                enabled_accts_str = str(enabled_accts)[:200] if enabled_accts else 'None'
                                logger.error(f"   Trader {trader.get('id')}: enabled={trader.get('enabled')}, enabled_accounts={enabled_accts_str}")

                            conn.close()
                        except Exception as diag_err:
                            logger.error(f"   Could not run diagnostics: {diag_err}")

                    logger.error(f"   NO RETRY - task abandoned to prevent duplicate trades")
                    # STEP 9: Trade failed
                    redis_track_signal_step(signal_id, 'STEP9_TRADE_FAILED', {'error': error[:200]})
                    redis_complete_signal(signal_id, 'failed', error)
                    _local_stats['total_failed'] += 1
                    _local_stats['last_error'] = error
                    increment_broker_stat('total_failed')
                    update_broker_stat('last_error', error[:200])

                    # Log failure to Redis
                    failed_accts = result.get('failed_accounts', []) if result else []
                    push_broker_failure(recorder_id, action, ticker, error, failed_accts)

                    # Discord notification for failed trade
                    try:
                        if DISCORD_NOTIFICATIONS_ENABLED:
                            conn = get_db_connection()
                            cursor = conn.cursor()
                            if is_using_postgres():
                                cursor.execute('SELECT user_id, name FROM recorders WHERE id = %s', (recorder_id,))
                            else:
                                cursor.execute('SELECT user_id, name FROM recorders WHERE id = ?', (recorder_id,))
                            rec_row = cursor.fetchone()
                            conn.close()
                            if rec_row:
                                rec_user_id = rec_row[0] if isinstance(rec_row, tuple) else rec_row.get('user_id')
                                rec_name = rec_row[1] if isinstance(rec_row, tuple) else rec_row.get('name')
                                if rec_user_id:
                                    notify_error(
                                        user_id=rec_user_id,
                                        error_type="Trade Execution Failed",
                                        error_message=f"{action} {quantity} {ticker} failed",
                                        details=f"Strategy: {rec_name}. Error: {error[:100]}"
                                    )
                    except Exception as notif_err:
                        logger.warning(f"Discord error notification failed: {notif_err}")

            except Exception as e:
                logger.error(f"Broker execution exception: {e}")
                import traceback
                traceback.print_exc()
                logger.error(f"   NO RETRY - task abandoned to prevent duplicate trades")
                _local_stats['total_failed'] += 1
                _local_stats['last_error'] = str(e)
                increment_broker_stat('total_failed')
                update_broker_stat('last_error', str(e)[:200])

            # Mark task as done
            broker_execution_queue.task_done()

        except Empty:
            # Timeout - no tasks, continue loop
            continue
        except Exception as e:
            logger.error(f"Broker execution worker error: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(1)


# ============================================================================
# WORKER MANAGEMENT
# ============================================================================
_broker_execution_threads = []
_broker_execution_worker_count = 10
_engine_start_time = time.time()


def start_broker_execution_workers():
    """Start multiple broker execution workers for HIVE MIND parallel execution."""
    global _broker_execution_threads
    logger.info(f"HIVE MIND: Starting {_broker_execution_worker_count} parallel broker execution workers...")

    for i in range(_broker_execution_worker_count):
        t = threading.Thread(
            target=broker_execution_worker, args=(i,),
            daemon=True, name=f"Engine-Broker-Worker-{i}"
        )
        t.start()
        _broker_execution_threads.append(t)

    # Verify workers started
    time.sleep(0.5)
    alive_count = sum(1 for t in _broker_execution_threads if t.is_alive())
    if alive_count == 0:
        logger.error("CRITICAL: No broker execution workers started!")
    else:
        logger.info(f"HIVE MIND ACTIVE: {alive_count}/{_broker_execution_worker_count} broker execution workers running")
        logger.info(f"   Queue: Redis key 'broker_tasks', maxsize: {broker_execution_queue.maxsize}")


# ============================================================================
# HEARTBEAT THREAD
# ============================================================================
def heartbeat_loop():
    """Publish engine health status to Redis every 10 seconds."""
    while True:
        try:
            alive_count = sum(1 for t in _broker_execution_threads if t.is_alive())
            uptime = time.time() - _engine_start_time
            engine_heartbeat(worker_count=alive_count, uptime=uptime)

            # Also sync local stats to Redis
            _sync_stats_to_redis()
        except Exception as e:
            logger.warning(f"Heartbeat error: {e}")
        time.sleep(10)


# ============================================================================
# WORKER WATCHDOG
# ============================================================================
def worker_watchdog():
    """Monitor broker workers and restart any that die."""
    while True:
        try:
            alive_count = sum(1 for t in _broker_execution_threads if t.is_alive())
            if alive_count < _broker_execution_worker_count:
                dead_count = _broker_execution_worker_count - alive_count
                logger.warning(f"WATCHDOG: {dead_count} broker worker(s) died! Restarting...")

                # Find and replace dead threads
                for i, t in enumerate(_broker_execution_threads):
                    if not t.is_alive():
                        new_t = threading.Thread(
                            target=broker_execution_worker, args=(i,),
                            daemon=True, name=f"Engine-Broker-Worker-{i}"
                        )
                        new_t.start()
                        _broker_execution_threads[i] = new_t
                        logger.info(f"WATCHDOG: Restarted broker worker #{i}")
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
        time.sleep(30)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("TRADING ENGINE STARTING")
    logger.info(f"PID: {os.getpid()}")
    logger.info(f"Redis: {REDIS_URL[:30]}..." if len(REDIS_URL) > 30 else f"Redis: {REDIS_URL}")
    logger.info("=" * 60)

    # Start broker execution workers
    start_broker_execution_workers()

    # Start heartbeat thread
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True, name="Engine-Heartbeat")
    heartbeat_thread.start()
    logger.info("Heartbeat thread started (every 10s)")

    # Start worker watchdog
    watchdog_thread = threading.Thread(target=worker_watchdog, daemon=True, name="Engine-Watchdog")
    watchdog_thread.start()
    logger.info("Worker watchdog started (every 30s)")

    logger.info("Trading engine ready. Waiting for broker tasks on Redis queue...")

    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
            alive = sum(1 for t in _broker_execution_threads if t.is_alive())
            queue_size = broker_execution_queue.qsize()
            logger.info(f"[STATUS] Workers: {alive}/{_broker_execution_worker_count} alive, Queue: {queue_size}, Stats: executed={_local_stats['total_executed']} failed={_local_stats['total_failed']}")
    except KeyboardInterrupt:
        logger.info("Trading engine shutting down...")
        sys.exit(0)
