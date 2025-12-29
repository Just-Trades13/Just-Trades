#!/usr/bin/env python3
"""
Check Webhook Signals - Real-time monitoring

This script checks what signals are being received from TradingView
"""

import sqlite3
import time
import sys
from datetime import datetime

DB_PATH = 'just_trades.db'
RECORDER_NAME = 'LIVE_TEST_RECORDER'

def get_db_connection():
    """Get database connection"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"❌ Database error: {e}")
        return None

def check_tables():
    """Check if required tables exist"""
    conn = get_db_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    required = ['recorders', 'recorded_signals', 'recorder_positions']
    missing = [t for t in required if t not in tables]
    
    if missing:
        print(f"⚠️  Missing tables: {', '.join(missing)}")
        print("   Server needs to run once to initialize database")
        return False
    
    return True

def check_signals():
    """Check for recent signals"""
    if not check_tables():
        return
    
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    # Get recorder
    cursor.execute("SELECT id, name, webhook_token, tp_ticks FROM recorders WHERE name = ?", (RECORDER_NAME,))
    recorder = cursor.fetchone()
    
    if not recorder:
        print(f"❌ Recorder '{RECORDER_NAME}' not found")
        conn.close()
        return
    
    recorder_id = recorder['id']
    print(f"\n📊 Recorder: {recorder['name']} (ID: {recorder_id})")
    print(f"   TP Ticks: {recorder['tp_ticks']}")
    print(f"   Webhook Token: {recorder['webhook_token'][:20]}...")
    print()
    
    # Check if recorded_signals table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recorded_signals'")
    if not cursor.fetchone():
        print("⚠️  'recorded_signals' table doesn't exist yet")
        print("   Server needs to process a webhook first to create tables")
        conn.close()
        return
    
    # Get recent signals
    cursor.execute('''
        SELECT action, ticker, price, created_at, raw_signal
        FROM recorded_signals
        WHERE recorder_id = ?
        ORDER BY created_at DESC
        LIMIT 20
    ''', (recorder_id,))
    
    signals = cursor.fetchall()
    print(f"📨 Recent Signals ({len(signals)} total):")
    print("=" * 60)
    
    if signals:
        for sig in signals:
            print(f"  [{sig['created_at']}] {sig['action']} {sig['ticker']} @ {sig['price']}")
            if sig.get('raw_signal'):
                try:
                    import json
                    raw = json.loads(sig['raw_signal'])
                    # Show key fields
                    keys = ['recorder', 'action', 'ticker', 'price']
                    filtered = {k: raw.get(k) for k in keys if k in raw}
                    if filtered:
                        print(f"     Data: {filtered}")
                except:
                    pass
    else:
        print("  ⏳ No signals received yet")
        print("  Waiting for TradingView to send webhook...")
        print()
        print("  💡 Make sure:")
        print("     1. Server is running")
        print("     2. Webhook URL is correct in TradingView")
        print("     3. Alert has triggered")
    
    print()
    
    # Check positions
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recorder_positions'")
    if cursor.fetchone():
        cursor.execute('''
            SELECT ticker, side, total_quantity, avg_entry_price, 
                   unrealized_pnl, worst_unrealized_pnl,
                   status, created_at
            FROM recorder_positions
            WHERE recorder_id = ? AND status = 'open'
            ORDER BY created_at DESC
        ''', (recorder_id,))
        
        positions = cursor.fetchall()
        print(f"📈 Open Positions ({len(positions)} total):")
        print("=" * 60)
        
        if positions:
            for pos in positions:
                print(f"  {pos['ticker']}: {pos['side']} {pos['total_quantity']} @ {pos['avg_entry_price']:.2f}")
                if pos.get('unrealized_pnl'):
                    print(f"     P&L: ${pos['unrealized_pnl']:.2f}")
                    if pos.get('worst_unrealized_pnl'):
                        print(f"     Worst Drawdown: ${pos['worst_unrealized_pnl']:.2f}")
                print(f"     Opened: {pos['created_at']}")
                print()
        else:
            print("  No open positions")
        
        # Closed positions
        cursor.execute('''
            SELECT ticker, side, total_quantity, avg_entry_price, exit_price,
                   realized_pnl, status, closed_at
            FROM recorder_positions
            WHERE recorder_id = ? AND status = 'closed'
            ORDER BY closed_at DESC
            LIMIT 10
        ''', (recorder_id,))
        
        closed = cursor.fetchall()
        if closed:
            print(f"📉 Closed Positions ({len(closed)} total):")
            print("=" * 60)
            for pos in closed:
                print(f"  {pos['ticker']}: {pos['side']} {pos['total_quantity']} @ {pos['avg_entry_price']:.2f}")
                print(f"     Exit: {pos['exit_price']:.2f} | P&L: ${pos['realized_pnl']:.2f}")
                print(f"     Closed: {pos['closed_at']}")
                print()
    
    conn.close()

def monitor_signals(interval=5):
    """Monitor signals in real-time"""
    print("\n🔍 Monitoring for new signals...")
    print("   Press Ctrl+C to stop\n")
    
    last_count = 0
    
    try:
        while True:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM recorded_signals WHERE recorder_id = (SELECT id FROM recorders WHERE name = ?)", (RECORDER_NAME,))
                current_count = cursor.fetchone()[0]
                conn.close()
                
                if current_count > last_count:
                    print(f"\n✅ New signal received! (Total: {current_count})")
                    check_signals()
                    last_count = current_count
                else:
                    print(f"⏳ Waiting... ({current_count} signals so far)", end='\r')
            
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoring stopped")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--monitor':
        monitor_signals()
    else:
        check_signals()
        print("\n💡 Run with --monitor to watch for new signals in real-time:")
        print("   python3 check_webhook_signals.py --monitor")
