#!/usr/bin/env python3
"""
Test Signal-Based Tracking (Trade Manager Style)

This script tests if signal-based position tracking works without broker sync.
Run this to verify signal-based tracking is working correctly.
"""

import requests
import time
import json
import sys

# Configuration
WEBHOOK_URL = "http://localhost:5000/webhook/YOUR_WEBHOOK_TOKEN"  # Replace with your webhook token
RECORDER_NAME = "TEST_RECORDER"  # Replace with your recorder name
TICKER = "MNQ1!"

def send_webhook(action, ticker, price, verbose=True):
    """Send test webhook signal"""
    data = {
        "recorder": RECORDER_NAME,
        "action": action,
        "ticker": ticker,
        "price": str(price)
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=data, timeout=5)
        if verbose:
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {action.upper()} {ticker} @ {price}: HTTP {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    print(f"   → Success: {result.get('message', 'Signal processed')}")
                else:
                    print(f"   → Error: {result.get('error', 'Unknown error')}")
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        if verbose:
            print(f"❌ Error sending webhook: {e}")
        return None

def test_single_buy():
    """Test 1: Single BUY signal"""
    print("\n" + "="*60)
    print("TEST 1: Single BUY Signal")
    print("="*60)
    print(f"Sending: BUY 1 {TICKER} @ 25600")
    result = send_webhook("buy", TICKER, 25600)
    time.sleep(1)
    print("✅ Expected: Position created: +1 MNQ @ 25600")
    return result

def test_dca():
    """Test 2: DCA (Multiple BUY signals)"""
    print("\n" + "="*60)
    print("TEST 2: DCA (Multiple BUY Signals)")
    print("="*60)
    
    print("Signal 1: BUY 1 MNQ @ 25600")
    send_webhook("buy", TICKER, 25600)
    time.sleep(1)
    
    print("\nSignal 2: BUY 1 MNQ @ 25610 (DCA)")
    result = send_webhook("buy", TICKER, 25610)
    time.sleep(1)
    
    print("\n✅ Expected: Position updated: +2 MNQ @ 25605 avg (weighted average)")
    return result

def test_partial_exit():
    """Test 3: Partial exit (SELL signal)"""
    print("\n" + "="*60)
    print("TEST 3: Partial Exit (SELL Signal)")
    print("="*60)
    
    # First create position
    print("Creating position: BUY 2 MNQ @ 25605")
    send_webhook("buy", TICKER, 25600)
    time.sleep(0.5)
    send_webhook("buy", TICKER, 25610)
    time.sleep(1)
    
    # Partial exit
    print(f"\nPartial exit: SELL 1 {TICKER} @ 25620")
    result = send_webhook("sell", TICKER, 25620)
    time.sleep(1)
    
    print("\n✅ Expected: Position reduced: +1 MNQ @ 25605 (from +2)")
    return result

def test_close():
    """Test 4: CLOSE signal"""
    print("\n" + "="*60)
    print("TEST 4: CLOSE Signal")
    print("="*60)
    
    # First create position
    print("Creating position: BUY 1 MNQ @ 25605")
    send_webhook("buy", TICKER, 25605)
    time.sleep(1)
    
    # Close
    print(f"\nClosing position: CLOSE {TICKER} @ 25620")
    result = send_webhook("close", TICKER, 25620)
    time.sleep(1)
    
    print("\n✅ Expected: Position closed: 0 MNQ")
    print("   → Exit price: 25620")
    print("   → P&L: (25620 - 25605) × 1 × $2 = $30")
    return result

def test_opposite_side():
    """Test 5: Opposite side (flip position)"""
    print("\n" + "="*60)
    print("TEST 5: Opposite Side (Position Flip)")
    print("="*60)
    
    # Create LONG position
    print("Creating LONG position: BUY 1 MNQ @ 25600")
    send_webhook("buy", TICKER, 25600)
    time.sleep(1)
    
    # Flip to SHORT
    print(f"\nFlipping to SHORT: SELL 1 {TICKER} @ 25610")
    result = send_webhook("sell", TICKER, 25610)
    time.sleep(1)
    
    print("\n✅ Expected: LONG closed, SHORT opened: -1 MNQ @ 25610")
    return result

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 SIGNAL-BASED TRACKING TEST SUITE")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Webhook URL: {WEBHOOK_URL}")
    print(f"  Recorder: {RECORDER_NAME}")
    print(f"  Ticker: {TICKER}")
    print("\n⚠️  Make sure:")
    print("  1. Server is running on localhost:5000")
    print("  2. Webhook token is correct")
    print("  3. Recorder exists and is enabled")
    print("  4. Broker sync is disabled (for testing)")
    
    input("\nPress Enter to start tests...")
    
    try:
        # Run tests
        test_single_buy()
        time.sleep(2)
        
        test_dca()
        time.sleep(2)
        
        test_partial_exit()
        time.sleep(2)
        
        test_close()
        time.sleep(2)
        
        test_opposite_side()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETE")
        print("="*60)
        print("\n📊 Next Steps:")
        print("  1. Check database for positions:")
        print("     SELECT * FROM recorder_positions WHERE recorder_id = ?;")
        print("  2. Check signals were recorded:")
        print("     SELECT * FROM recorded_signals WHERE recorder_id = ?;")
        print("  3. Verify NO broker API calls in server logs")
        print("  4. Check P&L is updating (if background thread is running)")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error running tests: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
