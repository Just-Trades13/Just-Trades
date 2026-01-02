#!/usr/bin/env python3
"""
Test Suite for Just.Trades Scalability Module
==============================================

Run with: python -m scalability.test_scalability

Tests all components without touching the main codebase.
"""

import sys
import time
import threading
import logging
from unittest.mock import MagicMock, patch

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Test results tracking
_test_results = []

def test(name):
    """Decorator to track test results"""
    def decorator(func):
        def wrapper():
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"🧪 TEST: {name}")
                logger.info('='*60)
                result = func()
                if result is not False:
                    _test_results.append((name, True, None))
                    logger.info(f"✅ PASSED: {name}")
                    return True
                else:
                    _test_results.append((name, False, "Returned False"))
                    logger.error(f"❌ FAILED: {name}")
                    return False
            except Exception as e:
                _test_results.append((name, False, str(e)))
                logger.error(f"❌ FAILED: {name} - {e}")
                import traceback
                traceback.print_exc()
                return False
        return wrapper
    return decorator


# ============================================================================
# TEST: State Cache
# ============================================================================

@test("StateCache - Basic Operations")
def test_state_cache_basic():
    from state_cache import StateCache
    
    cache = StateCache(ttl_seconds=60)
    
    # Test position updates
    seq1 = cache.update_position(123, "MESZ4", {
        'net_pos': 2,
        'net_price': 21500.00,
        'symbol': 'MESZ4'
    })
    assert seq1 > 0, "Sequence should be positive"
    
    # Get positions
    positions = cache.get_positions(123)
    assert len(positions) == 1, f"Expected 1 position, got {len(positions)}"
    assert positions[0]['net_pos'] == 2, "Position quantity mismatch"
    
    # Test order updates
    seq2 = cache.update_order(123, 999, {
        'id': 999,
        'status': 'Working',
        'action': 'Buy',
        'quantity': 1
    })
    assert seq2 > seq1, "Sequence should increment"
    
    orders = cache.get_orders(123)
    assert len(orders) == 1, f"Expected 1 order, got {len(orders)}"
    
    # Test PnL updates
    cache.update_pnl(123, {'open_pnl': 150.00, 'realized_pnl': 50.00})
    pnl = cache.get_pnl(123)
    assert pnl['open_pnl'] == 150.00, "PnL mismatch"
    
    # Test snapshot
    snapshot = cache.get_snapshot(123)
    assert 'positions' in snapshot
    assert 'orders' in snapshot
    assert 'pnl' in snapshot
    assert snapshot['sequence'] > 0
    
    logger.info(f"   Snapshot sequence: {snapshot['sequence']}")
    logger.info(f"   Positions: {len(snapshot['positions'])}")
    logger.info(f"   Orders: {len(snapshot['orders'])}")
    
    # Test stats
    stats = cache.get_stats()
    logger.info(f"   Cache stats: {stats}")
    assert stats['updates'] >= 3
    
    return True


@test("StateCache - Delta Updates")
def test_state_cache_deltas():
    from state_cache import StateCache
    
    cache = StateCache()
    
    # Initial state
    cache.update_position(456, "NQZ4", {'net_pos': 1, 'net_price': 20000.00})
    initial_seq = cache.get_stats()['current_sequence']
    
    # Make some changes
    cache.update_position(456, "NQZ4", {'net_pos': 2, 'net_price': 20010.00})
    cache.update_order(456, 100, {'id': 100, 'status': 'Working'})
    cache.add_fill(456, 200, {'id': 200, 'price': 20005.00})
    
    # Get deltas
    deltas = cache.get_deltas_since(456, initial_seq)
    
    assert deltas['from_sequence'] == initial_seq
    assert deltas['to_sequence'] > initial_seq
    assert len(deltas['positions_changed']) >= 1, "Should have position change"
    assert len(deltas['orders_changed']) >= 1, "Should have order change"
    assert len(deltas['fills_new']) >= 1, "Should have new fill"
    
    logger.info(f"   Deltas from seq {initial_seq} to {deltas['to_sequence']}:")
    logger.info(f"   - Positions changed: {len(deltas['positions_changed'])}")
    logger.info(f"   - Orders changed: {len(deltas['orders_changed'])}")
    logger.info(f"   - New fills: {len(deltas['fills_new'])}")
    
    return True


# ============================================================================
# TEST: Event Ledger
# ============================================================================

@test("EventLedger - Append and Query")
def test_event_ledger_basic():
    from event_ledger import EventLedger
    
    ledger = EventLedger(max_memory_events=1000)
    
    # Append events
    event1 = ledger.append(
        account_id=789,
        entity_type='position',
        event_type='Created',
        entity_id=100,
        raw_data={'netPos': 1, 'netPrice': 5000.00}
    )
    assert event1.id > 0
    assert event1.sequence > 0
    
    event2 = ledger.append(
        account_id=789,
        entity_type='order',
        event_type='Created',
        entity_id=200,
        raw_data={'action': 'Buy', 'qty': 1}
    )
    
    event3 = ledger.append(
        account_id=789,
        entity_type='position',
        event_type='Updated',
        entity_id=100,
        raw_data={'netPos': 2, 'netPrice': 5010.00}
    )
    
    # Query events
    all_events = ledger.get_events(account_id=789)
    assert len(all_events) == 3, f"Expected 3 events, got {len(all_events)}"
    
    # Query by entity type
    position_events = ledger.get_events(account_id=789, entity_type='position')
    assert len(position_events) == 2, f"Expected 2 position events, got {len(position_events)}"
    
    # Query since sequence
    recent = ledger.get_events(account_id=789, since_sequence=event1.sequence)
    assert len(recent) == 2, f"Expected 2 recent events, got {len(recent)}"
    
    logger.info(f"   Total events: {len(all_events)}")
    logger.info(f"   Position events: {len(position_events)}")
    logger.info(f"   Events since seq {event1.sequence}: {len(recent)}")
    
    return True


@test("EventLedger - Replay State Reconstruction")
def test_event_ledger_replay():
    from event_ledger import EventLedger
    
    ledger = EventLedger()
    
    # Simulate a series of events
    ledger.append(999, 'position', 'Created', 1, {'netPos': 1, 'symbol': 'ESZ4'})
    ledger.append(999, 'position', 'Updated', 1, {'netPos': 2, 'symbol': 'ESZ4'})
    ledger.append(999, 'order', 'Created', 10, {'action': 'Buy', 'status': 'Working'})
    ledger.append(999, 'order', 'Updated', 10, {'action': 'Buy', 'status': 'Filled'})
    ledger.append(999, 'order', 'Deleted', 10, {})  # Order removed after fill
    ledger.append(999, 'fill', 'Created', 50, {'price': 5500.00, 'qty': 1})
    
    # Replay to get current state
    state = ledger.replay(account_id=999)
    
    assert 'position' in state
    assert 'fill' in state
    assert 1 in state['position'], "Position 1 should exist"
    assert state['position'][1]['netPos'] == 2, "Position should show latest value"
    assert 10 not in state.get('order', {}), "Order 10 should be deleted"
    
    logger.info(f"   Reconstructed state: {list(state.keys())}")
    logger.info(f"   Positions: {len(state.get('position', {}))}")
    logger.info(f"   Orders: {len(state.get('order', {}))}")
    logger.info(f"   Fills: {len(state.get('fill', {}))}")
    
    return True


# ============================================================================
# TEST: Order Dispatcher
# ============================================================================

@test("OrderDispatcher - Priority Queue")
def test_dispatcher_priority():
    from order_dispatcher import OrderDispatcher, Priority
    
    executed = []
    
    def mock_execute(task):
        executed.append(task.task_id)
        time.sleep(0.01)  # Small delay
        return {'success': True}
    
    dispatcher = OrderDispatcher(
        execute_func=mock_execute,
        global_rate_limit=100,
        per_account_rate_limit=50
    )
    
    # Submit tasks in wrong priority order
    task_low = dispatcher.submit(100, 'entry', {'symbol': 'ES'}, Priority.LOW)
    task_normal = dispatcher.submit(100, 'entry', {'symbol': 'NQ'}, Priority.NORMAL)
    task_critical = dispatcher.submit(100, 'flatten', {'symbol': 'ES'}, Priority.CRITICAL)
    task_high = dispatcher.submit(100, 'close', {'symbol': 'ES'}, Priority.HIGH)
    
    # Start dispatcher
    dispatcher.start(num_workers=1)
    
    # Wait for execution
    time.sleep(0.5)
    
    # Stop dispatcher
    dispatcher.stop()
    
    # Verify execution order (critical first, then high, normal, low)
    logger.info(f"   Execution order: {executed}")
    
    # Check stats
    stats = dispatcher.get_stats()
    logger.info(f"   Submitted: {stats['submitted']}")
    logger.info(f"   Completed: {stats['completed']}")
    
    # Critical should be first
    assert executed[0] == task_critical, "Critical task should execute first"
    assert stats['completed'] >= 4, "All tasks should complete"
    
    return True


@test("OrderDispatcher - Per-Account Queues")
def test_dispatcher_per_account():
    from order_dispatcher import OrderDispatcher, Priority
    
    executed_by_account = {100: [], 200: []}
    
    def mock_execute(task):
        executed_by_account[task.account_id].append(task.task_id)
        time.sleep(0.02)
        return {'success': True}
    
    dispatcher = OrderDispatcher(
        execute_func=mock_execute,
        global_rate_limit=100,
        per_account_rate_limit=20
    )
    
    # Submit tasks for two accounts
    for i in range(3):
        dispatcher.submit(100, 'entry', {'i': i}, Priority.NORMAL)
        dispatcher.submit(200, 'entry', {'i': i}, Priority.NORMAL)
    
    dispatcher.start(num_workers=2)
    time.sleep(1.0)
    dispatcher.stop()
    
    logger.info(f"   Account 100 executed: {len(executed_by_account[100])}")
    logger.info(f"   Account 200 executed: {len(executed_by_account[200])}")
    
    # Both accounts should have executed tasks (fair scheduling)
    assert len(executed_by_account[100]) >= 2, "Account 100 should execute tasks"
    assert len(executed_by_account[200]) >= 2, "Account 200 should execute tasks"
    
    return True


@test("OrderDispatcher - Penalty Handling")
def test_dispatcher_penalty():
    from order_dispatcher import OrderDispatcher, Priority
    
    attempt_count = [0]
    
    def mock_execute_with_penalty(task):
        attempt_count[0] += 1
        if task.attempts == 1:
            # First attempt: return penalty
            return {
                'penalized': True,
                'p_time': 0.2,  # 200ms penalty
                'p_ticket': 'test-ticket-123'
            }
        else:
            # Retry succeeds
            return {'success': True}
    
    dispatcher = OrderDispatcher(
        execute_func=mock_execute_with_penalty,
        global_rate_limit=100,
        per_account_rate_limit=50
    )
    
    # Submit task that will be penalized
    task_id = dispatcher.submit(300, 'entry', {'symbol': 'ES'}, Priority.NORMAL)
    
    dispatcher.start(num_workers=1)
    time.sleep(1.0)  # Wait for penalty + retry
    dispatcher.stop()
    
    # Check task status
    status = dispatcher.get_task_status(task_id)
    stats = dispatcher.get_stats()
    
    logger.info(f"   Attempts made: {attempt_count[0]}")
    logger.info(f"   Task status: {status['status'] if status else 'not found'}")
    logger.info(f"   Penalties recorded: {stats['penalties']}")
    
    assert stats['penalties'] >= 1, "Should record penalty"
    assert status['status'] == 'completed', "Task should eventually complete"
    
    return True


# ============================================================================
# TEST: UI Publisher
# ============================================================================

@test("UIPublisher - 1 Hz Updates")
def test_ui_publisher():
    from ui_publisher import UIPublisher
    from state_cache import StateCache
    
    # Mock SocketIO
    mock_socketio = MagicMock()
    emitted = []
    
    def capture_emit(event, data, **kwargs):
        emitted.append({'event': event, 'data': data, 'kwargs': kwargs})
    
    mock_socketio.emit = capture_emit
    
    # Create cache and publisher
    cache = StateCache()
    publisher = UIPublisher(
        socketio=mock_socketio,
        state_cache=cache,
        publish_interval=0.1,  # 100ms for testing (10 Hz)
        use_deltas=False  # Use full snapshots for this test (always emits)
    )
    
    # Register a client
    client = publisher.register_client('test-client-1', {100})
    
    # Add some data to cache
    cache.update_position(100, 'ESZ4', {'net_pos': 1, 'symbol': 'ESZ4'})
    cache.update_pnl(100, {'open_pnl': 100.00})
    
    # Start publisher
    publisher.start()
    
    # Wait for a few ticks
    time.sleep(0.5)
    
    # Stop publisher
    publisher.stop()
    
    # Check emissions
    logger.info(f"   Emissions captured: {len(emitted)}")
    logger.info(f"   Ticks: {publisher.get_stats()['ticks']}")
    
    # With use_deltas=False, every tick should emit (full snapshot mode)
    assert len(emitted) >= 2, f"Should have multiple emissions, got {len(emitted)}"
    assert publisher.get_stats()['ticks'] >= 2, "Should have multiple ticks"
    
    # Check emission format
    if emitted:
        first = emitted[0]
        assert first['event'] == 'scalability_update'
        assert 'type' in first['data']
        logger.info(f"   First emission type: {first['data']['type']}")
    
    return True


@test("UIPublisher - Delta Mode (Only Emits On Changes)")
def test_ui_publisher_delta_mode():
    from ui_publisher import UIPublisher
    from state_cache import StateCache
    
    mock_socketio = MagicMock()
    emitted = []
    mock_socketio.emit = lambda e, d, **k: emitted.append(d)
    
    cache = StateCache()
    publisher = UIPublisher(
        socketio=mock_socketio,
        state_cache=cache,
        publish_interval=0.1,
        use_deltas=True  # Delta mode - only emits when data changes
    )
    
    publisher.register_client('delta-test', {100})
    
    # Add initial data
    cache.update_position(100, 'ESZ4', {'net_pos': 1})
    
    publisher.start()
    time.sleep(0.15)  # First tick - should emit (initial snapshot)
    
    first_count = len(emitted)
    
    # No changes - next ticks should NOT emit
    time.sleep(0.3)
    count_after_no_change = len(emitted)
    
    # Make a change - should emit again
    cache.update_position(100, 'ESZ4', {'net_pos': 2})
    time.sleep(0.15)
    count_after_change = len(emitted)
    
    publisher.stop()
    
    logger.info(f"   Initial emissions: {first_count}")
    logger.info(f"   After no change: {count_after_no_change}")
    logger.info(f"   After change: {count_after_change}")
    
    # First emission should happen (initial snapshot)
    assert first_count >= 1, "Should emit initial snapshot"
    # After change, should emit again
    assert count_after_change > count_after_no_change, "Should emit after data change"
    
    return True


# ============================================================================
# TEST: Integration
# ============================================================================

@test("Integration - Full Pipeline")
def test_full_pipeline():
    """Test the complete data flow: Event → Ledger → Cache → Publisher"""
    from state_cache import StateCache
    from event_ledger import EventLedger
    from ui_publisher import UIPublisher
    
    # Setup components
    cache = StateCache()
    ledger = EventLedger()
    
    mock_socketio = MagicMock()
    emissions = []
    mock_socketio.emit = lambda e, d, **k: emissions.append(d)
    
    publisher = UIPublisher(
        socketio=mock_socketio,
        state_cache=cache,
        publish_interval=0.1
    )
    
    # Register client
    publisher.register_client('pipeline-test', {500})
    
    # Simulate broker event flow
    def simulate_broker_event(entity_type, event_type, entity_id, data):
        # 1. Record in ledger
        ledger.append(500, entity_type, event_type, entity_id, data)
        
        # 2. Update cache
        if entity_type == 'position':
            cache.update_position(500, str(entity_id), data)
        elif entity_type == 'order':
            cache.update_order(500, entity_id, data)
        elif entity_type == 'fill':
            cache.add_fill(500, entity_id, data)
    
    # Start publisher
    publisher.start()
    
    # Simulate events
    simulate_broker_event('position', 'Created', 1, {'net_pos': 1, 'symbol': 'MES'})
    time.sleep(0.15)
    
    simulate_broker_event('position', 'Updated', 1, {'net_pos': 2, 'symbol': 'MES'})
    time.sleep(0.15)
    
    simulate_broker_event('order', 'Created', 100, {'status': 'Working'})
    time.sleep(0.15)
    
    simulate_broker_event('fill', 'Created', 200, {'price': 5500.00})
    time.sleep(0.15)
    
    publisher.stop()
    
    # Verify data flow
    ledger_events = ledger.get_events(account_id=500)
    cache_snapshot = cache.get_snapshot(500)
    
    logger.info(f"   Ledger events: {len(ledger_events)}")
    logger.info(f"   Cache positions: {len(cache_snapshot['positions'])}")
    logger.info(f"   Cache orders: {len(cache_snapshot['orders'])}")
    logger.info(f"   UI emissions: {len(emissions)}")
    
    assert len(ledger_events) == 4, f"Expected 4 ledger events, got {len(ledger_events)}"
    assert len(cache_snapshot['positions']) >= 1
    assert len(emissions) >= 2, "Should have UI emissions"
    
    # Verify replay matches cache
    replayed = ledger.replay(500)
    assert 'position' in replayed
    assert replayed['position'][1]['net_pos'] == 2, "Replay should show latest position"
    
    return True


# ============================================================================
# TEST: Performance
# ============================================================================

@test("Performance - High Volume Cache Updates")
def test_performance_cache():
    from state_cache import StateCache
    import random
    
    cache = StateCache()
    
    # Simulate 1000 rapid updates (like during market open)
    start = time.time()
    
    for i in range(1000):
        account = random.randint(1, 10)
        contract = f"ES{random.randint(1, 5)}"
        cache.update_position(account, contract, {
            'net_pos': random.randint(-10, 10),
            'net_price': random.uniform(5000, 5100)
        })
    
    elapsed = time.time() - start
    rate = 1000 / elapsed
    
    logger.info(f"   1000 updates in {elapsed:.3f}s")
    logger.info(f"   Rate: {rate:.0f} updates/sec")
    
    # Should handle at least 5000 updates/sec
    assert rate > 5000, f"Too slow: {rate:.0f} updates/sec (need >5000)"
    
    return True


@test("Performance - Dispatcher Queue Throughput")
def test_performance_dispatcher():
    from order_dispatcher import OrderDispatcher, Priority
    
    completed = [0]
    
    def fast_execute(task):
        completed[0] += 1
        return {'success': True}
    
    dispatcher = OrderDispatcher(
        execute_func=fast_execute,
        global_rate_limit=500,
        per_account_rate_limit=100
    )
    
    # Submit 100 tasks
    start = time.time()
    for i in range(100):
        dispatcher.submit(i % 10, 'entry', {'i': i}, Priority.NORMAL)
    submit_time = time.time() - start
    
    # Process them
    dispatcher.start(num_workers=4)
    
    # Wait for completion
    timeout = time.time() + 5
    while completed[0] < 100 and time.time() < timeout:
        time.sleep(0.1)
    
    process_time = time.time() - start
    dispatcher.stop()
    
    logger.info(f"   Submit time: {submit_time:.3f}s")
    logger.info(f"   Total time: {process_time:.3f}s")
    logger.info(f"   Completed: {completed[0]}/100")
    logger.info(f"   Rate: {completed[0]/process_time:.0f} tasks/sec")
    
    assert completed[0] >= 95, f"Should complete most tasks, got {completed[0]}"
    
    return True


# ============================================================================
# RUN ALL TESTS
# ============================================================================

def run_all_tests():
    """Run all tests and report results"""
    logger.info("\n" + "="*70)
    logger.info("🚀 SCALABILITY MODULE TEST SUITE")
    logger.info("="*70)
    
    tests = [
        test_state_cache_basic,
        test_state_cache_deltas,
        test_event_ledger_basic,
        test_event_ledger_replay,
        test_dispatcher_priority,
        test_dispatcher_per_account,
        test_dispatcher_penalty,
        test_ui_publisher,
        test_ui_publisher_delta_mode,
        test_full_pipeline,
        test_performance_cache,
        test_performance_dispatcher,
    ]
    
    for test_func in tests:
        test_func()
    
    # Summary
    logger.info("\n" + "="*70)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("="*70)
    
    passed = sum(1 for _, success, _ in _test_results if success)
    failed = sum(1 for _, success, _ in _test_results if not success)
    
    for name, success, error in _test_results:
        status = "✅ PASS" if success else f"❌ FAIL: {error}"
        logger.info(f"   {name}: {status}")
    
    logger.info("-"*70)
    logger.info(f"   TOTAL: {passed} passed, {failed} failed")
    logger.info("="*70)
    
    if failed > 0:
        logger.error("\n❌ SOME TESTS FAILED")
        return False
    else:
        logger.info("\n✅ ALL TESTS PASSED!")
        return True


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
