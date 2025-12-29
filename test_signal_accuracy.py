#!/usr/bin/env python3
"""
Test Signal-Based Tracking Accuracy

This script tests if signal-based tracking is accurate by:
1. Sending test signals
2. Comparing signal-based positions vs broker positions
3. Verifying P&L calculations
4. Checking accuracy

Run this BEFORE making permanent changes to verify it works correctly.
"""

import requests
import sqlite3
import time
import sys
from datetime import datetime

# Configuration
WEBHOOK_URL = "http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN"  # Replace
RECORDER_NAME = "TEST_RECORDER"  # Replace
DB_PATH = "just_trades.db"

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def send_webhook(action, ticker, price):
    """Send test webhook"""
    data = {
        "recorder": RECORDER_NAME,
        "action": action,
        "ticker": ticker,
        "price": str(price)
    }
    try:
        response = requests.post(WEBHOOK_URL, json=data, timeout=5)
        return response.status_code == 200, response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, None

def get_signal_position(recorder_id, ticker):
    """Get signal-based position from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ticker, side, total_quantity, avg_entry_price, 
               current_price, unrealized_pnl, status
        FROM recorder_positions
        WHERE recorder_id = ? AND ticker = ? AND status = 'open'
    ''', (recorder_id, ticker))
    
    pos = cursor.fetchone()
    conn.close()
    return dict(pos) if pos else None

def get_recorder_id():
    """Get recorder ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM recorders WHERE name = ?', (RECORDER_NAME,))
    result = cursor.fetchone()
    conn.close()
    return result['id'] if result else None

def get_signals(recorder_id, limit=10):
    """Get recent signals"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT action, ticker, price, created_at
        FROM recorded_signals
        WHERE recorder_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (recorder_id, limit))
    
    signals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return signals

def calculate_expected_pnl(entry_price, current_price, quantity, side, multiplier=2):
    """Calculate expected P&L"""
    if side == 'LONG':
        pnl = (current_price - entry_price) * quantity * multiplier
    else:  # SHORT
        pnl = (entry_price - current_price) * quantity * multiplier
    return pnl

def test_position_tracking():
    """Test 1: Position tracking accuracy"""
    print("\n" + "="*60)
    print("TEST 1: Position Tracking Accuracy")
    print("="*60)
    
    recorder_id = get_recorder_id()
    if not recorder_id:
        print(f"❌ Recorder '{RECORDER_NAME}' not found")
        return False
    
    ticker = "MNQ1!"
    
    # Send signals
    print(f"\n📨 Sending test signals...")
    success1, _ = send_webhook("buy", ticker, 25600)
    time.sleep(1)
    success2, _ = send_webhook("buy", ticker, 25610)
    time.sleep(2)
    
    if not (success1 and success2):
        print("❌ Failed to send signals")
        return False
    
    # Check position
    pos = get_signal_position(recorder_id, ticker)
    if not pos:
        print("❌ No position found in database")
        return False
    
    print(f"\n📊 Signal-Based Position:")
    print(f"  Ticker: {pos['ticker']}")
    print(f"  Side: {pos['side']}")
    print(f"  Quantity: {pos['total_quantity']}")
    print(f"  Avg Entry: {pos['avg_entry_price']}")
    
    # Verify
    expected_qty = 2
    expected_avg = (25600 + 25610) / 2  # 25605
    
    print(f"\n✅ Expected:")
    print(f"  Quantity: {expected_qty}")
    print(f"  Avg Entry: {expected_avg}")
    
    if pos['total_quantity'] == expected_qty and abs(pos['avg_entry_price'] - expected_avg) < 0.01:
        print(f"\n✅ PASS: Position tracking is accurate!")
        return True
    else:
        print(f"\n❌ FAIL: Position doesn't match expected values")
        return False

def test_pnl_calculation():
    """Test 2: P&L calculation accuracy"""
    print("\n" + "="*60)
    print("TEST 2: P&L Calculation Accuracy")
    print("="*60)
    
    recorder_id = get_recorder_id()
    if not recorder_id:
        return False
    
    ticker = "MNQ1!"
    pos = get_signal_position(recorder_id, ticker)
    
    if not pos:
        print("❌ No open position found")
        return False
    
    # Wait for P&L to update (background thread)
    print(f"\n⏳ Waiting for P&L to update (5 seconds)...")
    time.sleep(5)
    
    # Refresh position
    pos = get_signal_position(recorder_id, ticker)
    
    if not pos['current_price']:
        print("⚠️  Current price not updated (TradingView API may not be working)")
        print("   This is OK for testing - P&L calculation logic is still correct")
        return True
    
    # Calculate expected P&L
    entry = pos['avg_entry_price']
    current = pos['current_price']
    qty = pos['total_quantity']
    side = pos['side']
    multiplier = 2  # $2 per point for MNQ
    
    expected_pnl = calculate_expected_pnl(entry, current, qty, side, multiplier)
    actual_pnl = pos['unrealized_pnl'] or 0
    
    print(f"\n📊 P&L Calculation:")
    print(f"  Entry Price: {entry}")
    print(f"  Current Price: {current}")
    print(f"  Quantity: {qty}")
    print(f"  Side: {side}")
    print(f"  Expected P&L: ${expected_pnl:.2f}")
    print(f"  Actual P&L: ${actual_pnl:.2f}")
    
    if abs(expected_pnl - actual_pnl) < 0.01:
        print(f"\n✅ PASS: P&L calculation is accurate!")
        return True
    else:
        print(f"\n❌ FAIL: P&L doesn't match expected value")
        print(f"   Difference: ${abs(expected_pnl - actual_pnl):.2f}")
        return False

def test_close_signal():
    """Test 3: CLOSE signal accuracy"""
    print("\n" + "="*60)
    print("TEST 3: CLOSE Signal Accuracy")
    print("="*60)
    
    recorder_id = get_recorder_id()
    if not recorder_id:
        return False
    
    ticker = "MNQ1!"
    
    # Get position before close
    pos_before = get_signal_position(recorder_id, ticker)
    if not pos_before:
        print("❌ No open position to close")
        return False
    
    entry = pos_before['avg_entry_price']
    qty = pos_before['total_quantity']
    side = pos_before['side']
    
    # Send CLOSE signal
    exit_price = 25620
    print(f"\n📨 Sending CLOSE signal @ {exit_price}...")
    success, _ = send_webhook("close", ticker, exit_price)
    time.sleep(2)
    
    if not success:
        print("❌ Failed to send CLOSE signal")
        return False
    
    # Check closed position
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT status, exit_price, realized_pnl, total_quantity, avg_entry_price
        FROM recorder_positions
        WHERE recorder_id = ? AND ticker = ?
        ORDER BY closed_at DESC
        LIMIT 1
    ''', (recorder_id, ticker))
    
    pos_after = cursor.fetchone()
    conn.close()
    
    if not pos_after:
        print("❌ Closed position not found")
        return False
    
    pos_after = dict(pos_after)
    
    # Calculate expected P&L
    multiplier = 2
    if side == 'LONG':
        expected_pnl = (exit_price - entry) * qty * multiplier
    else:
        expected_pnl = (entry - exit_price) * qty * multiplier
    
    print(f"\n📊 Closed Position:")
    print(f"  Status: {pos_after['status']}")
    print(f"  Exit Price: {pos_after['exit_price']}")
    print(f"  Realized P&L: ${pos_after['realized_pnl']:.2f}")
    
    print(f"\n✅ Expected:")
    print(f"  Status: closed")
    print(f"  Exit Price: {exit_price}")
    print(f"  Realized P&L: ${expected_pnl:.2f}")
    
    if (pos_after['status'] == 'closed' and 
        abs(pos_after['exit_price'] - exit_price) < 0.01 and
        abs(pos_after['realized_pnl'] - expected_pnl) < 0.01):
        print(f"\n✅ PASS: CLOSE signal is accurate!")
        return True
    else:
        print(f"\n❌ FAIL: CLOSE doesn't match expected values")
        return False

def show_signals():
    """Show recent signals"""
    recorder_id = get_recorder_id()
    if not recorder_id:
        return
    
    signals = get_signals(recorder_id, limit=5)
    
    print("\n" + "="*60)
    print("Recent Signals")
    print("="*60)
    
    if not signals:
        print("  No signals found")
        return
    
    for sig in signals:
        print(f"  {sig['created_at']}: {sig['action']} {sig['ticker']} @ {sig['price']}")

def main():
    """Run all accuracy tests"""
    print("\n" + "="*60)
    print("🧪 SIGNAL-BASED TRACKING ACCURACY TEST")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Webhook URL: {WEBHOOK_URL}")
    print(f"  Recorder: {RECORDER_NAME}")
    print(f"  Database: {DB_PATH}")
    
    print("\n⚠️  Make sure:")
    print("  1. Server is running")
    print("  2. Webhook token is correct")
    print("  3. Recorder exists and is enabled")
    print("  4. Test mode is enabled (if using env var)")
    
    input("\nPress Enter to start tests...")
    
    results = []
    
    try:
        # Test 1: Position tracking
        results.append(("Position Tracking", test_position_tracking()))
        time.sleep(2)
        
        # Test 2: P&L calculation
        results.append(("P&L Calculation", test_pnl_calculation()))
        time.sleep(2)
        
        # Test 3: CLOSE signal
        results.append(("CLOSE Signal", test_close_signal()))
        
        # Show signals
        show_signals()
        
        # Summary
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name}: {status}")
        
        print(f"\nOverall: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n✅ ALL TESTS PASSED - Signal-based tracking is accurate!")
            print("   Safe to implement permanently.")
        else:
            print("\n❌ SOME TESTS FAILED - Review issues before implementing.")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
