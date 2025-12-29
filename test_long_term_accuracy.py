#!/usr/bin/env python3
"""
Long-Term Signal-Based Tracking Accuracy Test

This test runs continuously to verify signal-based tracking accuracy over time.
It sends signals periodically and monitors:
- Position accuracy
- P&L calculation accuracy
- Signal recording accuracy
- How long it stays accurate
"""

import requests
import sqlite3
import time
import sys
from datetime import datetime, timedelta
import json

# Configuration
WEBHOOK_URL = "http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN"  # Replace
RECORDER_NAME = "TEST_RECORDER"  # Replace
DB_PATH = "just_trades.db"
TEST_DURATION_MINUTES = 60  # Run for 1 hour (adjust as needed)
CHECK_INTERVAL_SECONDS = 10  # Check accuracy every 10 seconds

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
        return False, {"error": str(e)}

def get_recorder_id():
    """Get recorder ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM recorders WHERE name = ?', (RECORDER_NAME,))
    result = cursor.fetchone()
    conn.close()
    return result['id'] if result else None

def get_signal_position(recorder_id, ticker):
    """Get signal-based position from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ticker, side, total_quantity, avg_entry_price, 
               current_price, unrealized_pnl, worst_unrealized_pnl,
               status, created_at, updated_at
        FROM recorder_positions
        WHERE recorder_id = ? AND ticker = ? AND status = 'open'
    ''', (recorder_id, ticker))
    pos = cursor.fetchone()
    conn.close()
    return dict(pos) if pos else None

def get_all_signals(recorder_id):
    """Get all signals for this recorder"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT action, ticker, price, created_at
        FROM recorded_signals
        WHERE recorder_id = ?
        ORDER BY created_at ASC
    ''', (recorder_id,))
    signals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return signals

def calculate_expected_position(signals, ticker):
    """Calculate expected position from signals"""
    qty = 0
    total_cost = 0
    side = None
    
    for sig in signals:
        if sig['ticker'] != ticker:
            continue
            
        action = sig['action'].upper()
        price = float(sig['price'])
        
        if action in ['BUY', 'LONG']:
            if side == 'SHORT' and qty > 0:
                # Close short, open long
                qty = 1
                total_cost = price
                side = 'LONG'
            elif side == 'LONG' or side is None:
                # Add to long
                qty += 1
                total_cost += price
                side = 'LONG'
        elif action in ['SELL', 'SHORT']:
            if side == 'LONG' and qty > 0:
                # Reduce long or flip to short
                if qty > 1:
                    qty -= 1
                    total_cost -= (total_cost / (qty + 1))  # Remove one entry
                else:
                    # Flip to short
                    qty = 1
                    total_cost = price
                    side = 'SHORT'
            elif side == 'SHORT' or side is None:
                # Add to short
                qty += 1
                total_cost += price
                side = 'SHORT'
        elif action == 'CLOSE':
            qty = 0
            total_cost = 0
            side = None
    
    avg_price = total_cost / qty if qty > 0 else 0
    return {
        'quantity': abs(qty),
        'side': side,
        'avg_price': avg_price
    }

def check_position_accuracy(recorder_id, ticker):
    """Check if position matches expected from signals"""
    # Get actual position
    actual_pos = get_signal_position(recorder_id, ticker)
    
    # Get all signals
    signals = get_all_signals(recorder_id)
    
    # Calculate expected position
    expected_pos = calculate_expected_position(signals, ticker)
    
    if not actual_pos:
        if expected_pos['quantity'] == 0:
            return True, "No position (expected)"  # Both are flat
        else:
            return False, f"Missing position: Expected {expected_pos['side']} {expected_pos['quantity']}"
    
    # Compare
    if actual_pos['status'] != 'open':
        return False, f"Position is {actual_pos['status']}, expected open"
    
    if actual_pos['side'] != expected_pos['side']:
        return False, f"Side mismatch: {actual_pos['side']} vs {expected_pos['side']}"
    
    if actual_pos['total_quantity'] != expected_pos['quantity']:
        return False, f"Quantity mismatch: {actual_pos['total_quantity']} vs {expected_pos['quantity']}"
    
    if abs(actual_pos['avg_entry_price'] - expected_pos['avg_price']) > 0.1:
        return False, f"Avg price mismatch: {actual_pos['avg_entry_price']:.2f} vs {expected_pos['avg_price']:.2f}"
    
    return True, "Position accurate"

def check_pnl_accuracy(recorder_id, ticker):
    """Check if P&L calculation is accurate"""
    pos = get_signal_position(recorder_id, ticker)
    if not pos or pos['status'] != 'open':
        return True, "No open position"
    
    if not pos['current_price']:
        return None, "No current price (TradingView API may not be working)"
    
    # Calculate expected P&L
    entry = pos['avg_entry_price']
    current = pos['current_price']
    qty = pos['total_quantity']
    side = pos['side']
    multiplier = 2  # $2 per point for MNQ
    
    if side == 'LONG':
        expected_pnl = (current - entry) * qty * multiplier
    else:
        expected_pnl = (entry - current) * qty * multiplier
    
    actual_pnl = pos['unrealized_pnl'] or 0
    
    if abs(expected_pnl - actual_pnl) < 0.01:
        return True, f"P&L accurate: ${actual_pnl:.2f}"
    else:
        return False, f"P&L mismatch: ${actual_pnl:.2f} vs ${expected_pnl:.2f}"

def run_accuracy_check(recorder_id, ticker, check_number):
    """Run a single accuracy check"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Check position accuracy
    pos_accurate, pos_msg = check_position_accuracy(recorder_id, ticker)
    
    # Check P&L accuracy
    pnl_accurate, pnl_msg = check_pnl_accuracy(recorder_id, ticker)
    
    # Get position details
    pos = get_signal_position(recorder_id, ticker)
    
    status = "✅" if (pos_accurate and (pnl_accurate is None or pnl_accurate)) else "❌"
    
    print(f"\n[{timestamp}] Check #{check_number} {status}")
    print(f"  Position: {pos_msg}")
    if pnl_accurate is not None:
        print(f"  P&L: {pnl_msg}")
    else:
        print(f"  P&L: {pnl_msg}")
    
    if pos:
        print(f"  Current: {pos['side']} {pos['total_quantity']} @ {pos['avg_entry_price']:.2f}")
        if pos['current_price']:
            print(f"  Price: {pos['current_price']:.2f} | P&L: ${pos['unrealized_pnl']:.2f}")
    
    return pos_accurate and (pnl_accurate is None or pnl_accurate)

def send_test_signals(recorder_id, ticker):
    """Send a series of test signals"""
    print("\n📨 Sending test signals...")
    
    # Signal 1: BUY
    success, _ = send_webhook("buy", ticker, 25600)
    if success:
        print("  ✅ BUY 1 MNQ @ 25600")
    time.sleep(1)
    
    # Signal 2: BUY (DCA)
    success, _ = send_webhook("buy", ticker, 25610)
    if success:
        print("  ✅ BUY 1 MNQ @ 25610 (DCA)")
    time.sleep(1)
    
    # Signal 3: BUY (DCA again)
    success, _ = send_webhook("buy", ticker, 25620)
    if success:
        print("  ✅ BUY 1 MNQ @ 25620 (DCA)")
    time.sleep(2)
    
    print("  ✅ Signals sent, waiting for processing...")
    time.sleep(3)

def main():
    """Run long-term accuracy test"""
    print("\n" + "="*60)
    print("🧪 LONG-TERM SIGNAL-BASED TRACKING ACCURACY TEST")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Webhook URL: {WEBHOOK_URL}")
    print(f"  Recorder: {RECORDER_NAME}")
    print(f"  Test Duration: {TEST_DURATION_MINUTES} minutes")
    print(f"  Check Interval: {CHECK_INTERVAL_SECONDS} seconds")
    
    # Get recorder ID
    recorder_id = get_recorder_id()
    if not recorder_id:
        print(f"\n❌ Recorder '{RECORDER_NAME}' not found")
        print("   Please create the recorder first or update RECORDER_NAME")
        sys.exit(1)
    
    ticker = "MNQ1!"
    
    print(f"\n⚠️  Make sure:")
    print("  1. Server is running")
    print("  2. Webhook token is correct")
    print("  3. SIGNAL_BASED_TEST=true is set (if using env var)")
    print("  4. Recorder is enabled")
    
    input("\nPress Enter to start test...")
    
    # Send initial test signals
    send_test_signals(recorder_id, ticker)
    
    # Track accuracy over time
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=TEST_DURATION_MINUTES)
    check_number = 0
    accurate_checks = 0
    total_checks = 0
    first_failure_time = None
    consecutive_failures = 0
    max_consecutive_failures = 0
    
    print(f"\n⏱️  Starting accuracy monitoring...")
    print(f"   Will run until {end_time.strftime('%H:%M:%S')}")
    print(f"   Checking every {CHECK_INTERVAL_SECONDS} seconds\n")
    
    try:
        while datetime.now() < end_time:
            check_number += 1
            total_checks += 1
            
            # Run accuracy check
            is_accurate = run_accuracy_check(recorder_id, ticker, check_number)
            
            if is_accurate:
                accurate_checks += 1
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                max_consecutive_failures = max(max_consecutive_failures, consecutive_failures)
                if first_failure_time is None:
                    first_failure_time = datetime.now()
                    elapsed = (first_failure_time - start_time).total_seconds()
                    print(f"\n⚠️  FIRST FAILURE at {elapsed:.0f} seconds")
            
            # Wait before next check
            time.sleep(CHECK_INTERVAL_SECONDS)
            
            # Progress update every 10 checks
            if check_number % 10 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                accuracy_rate = (accurate_checks / total_checks) * 100
                print(f"\n📊 Progress: {elapsed:.0f}s elapsed | Accuracy: {accuracy_rate:.1f}% ({accurate_checks}/{total_checks})")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    
    # Final summary
    elapsed = (datetime.now() - start_time).total_seconds()
    accuracy_rate = (accurate_checks / total_checks) * 100 if total_checks > 0 else 0
    
    print("\n" + "="*60)
    print("📊 FINAL TEST RESULTS")
    print("="*60)
    print(f"\nTest Duration: {elapsed:.0f} seconds ({elapsed/60:.1f} minutes)")
    print(f"Total Checks: {total_checks}")
    print(f"Accurate Checks: {accurate_checks}")
    print(f"Accuracy Rate: {accuracy_rate:.1f}%")
    print(f"Max Consecutive Failures: {max_consecutive_failures}")
    
    if first_failure_time:
        time_to_first_failure = (first_failure_time - start_time).total_seconds()
        print(f"\n⚠️  First Failure: {time_to_first_failure:.0f} seconds ({time_to_first_failure/60:.1f} minutes)")
        print(f"   Time Accurate: {time_to_first_failure:.0f} seconds")
    else:
        print(f"\n✅ NO FAILURES - Stayed accurate for entire test duration!")
        print(f"   Time Accurate: {elapsed:.0f} seconds ({elapsed/60:.1f} minutes)")
    
    # Get final position state
    pos = get_signal_position(recorder_id, ticker)
    if pos:
        print(f"\n📊 Final Position State:")
        print(f"  {pos['side']} {pos['total_quantity']} @ {pos['avg_entry_price']:.2f}")
        if pos['current_price']:
            print(f"  Current Price: {pos['current_price']:.2f}")
            print(f"  Unrealized P&L: ${pos['unrealized_pnl']:.2f}")
            print(f"  Worst Drawdown: ${pos['worst_unrealized_pnl']:.2f}")
    
    # Get signal count
    signals = get_all_signals(recorder_id)
    print(f"\n📨 Total Signals Processed: {len(signals)}")
    
    if accuracy_rate >= 99.0:
        print("\n✅ EXCELLENT: Signal-based tracking is highly accurate!")
        print("   Safe to implement permanently.")
    elif accuracy_rate >= 95.0:
        print("\n✅ GOOD: Signal-based tracking is mostly accurate.")
        print("   Minor issues detected, but generally reliable.")
    else:
        print("\n❌ POOR: Signal-based tracking has accuracy issues.")
        print("   Review failures before implementing.")

if __name__ == "__main__":
    main()
