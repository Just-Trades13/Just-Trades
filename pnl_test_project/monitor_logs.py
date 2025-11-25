#!/usr/bin/env python3
"""
Monitor Server Logs for P&L Testing

This script monitors the server output for:
- WebSocket connections
- Quote subscriptions
- Quote updates
- P&L calculations
- Position updates

Run this while testing in the browser to see what's happening.
"""

import subprocess
import sys
import re
from datetime import datetime

# Keywords to highlight
HIGHLIGHTS = {
    'websocket': '\033[94m',  # Blue
    'quote': '\033[92m',      # Green
    'pnl': '\033[93m',        # Yellow
    'position': '\033[96m',   # Cyan
    'error': '\033[91m',      # Red
    'success': '\033[92m',    # Green
    'warning': '\033[93m',    # Yellow
}
RESET = '\033[0m'

def highlight_text(text):
    """Highlight keywords in text"""
    for keyword, color in HIGHLIGHTS.items():
        if keyword.lower() in text.lower():
            # Case-insensitive replace
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            text = pattern.sub(f'{color}{keyword.upper()}{RESET}', text)
    return text

def monitor_server_logs():
    """Monitor server process output"""
    print("="*80)
    print("MONITORING SERVER LOGS FOR P&L TESTING")
    print("="*80)
    print("\nWatching for:")
    print("  🔵 WebSocket connections")
    print("  🟢 Quote subscriptions and updates")
    print("  🟡 P&L calculations")
    print("  🔵 Position updates")
    print("  🔴 Errors")
    print("\n" + "="*80 + "\n")
    
    # Find server process
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        
        # Find ultra_simple_server.py process
        for line in result.stdout.split('\n'):
            if 'ultra_simple_server.py' in line and 'grep' not in line:
                parts = line.split()
                if len(parts) > 1:
                    pid = parts[1]
                    print(f"✅ Found server process (PID: {pid})")
                    print(f"   Monitoring logs...\n")
                    break
        else:
            print("⚠️  Server process not found")
            print("   Make sure ultra_simple_server.py is running")
            return
    except Exception as e:
        print(f"❌ Error finding server: {e}")
        return
    
    # Monitor by tailing log file or watching process
    # Since we can't easily tail a running process, we'll provide instructions
    print("="*80)
    print("MONITORING INSTRUCTIONS")
    print("="*80)
    print("\nTo see real-time logs, you have two options:\n")
    print("OPTION 1: Watch server terminal")
    print("  - Look at the terminal where you started ultra_simple_server.py")
    print("  - You should see logs there\n")
    print("OPTION 2: Check server output file (if logging to file)")
    print("  - If server logs to a file, tail it:\n")
    print("    tail -f server.log\n")
    print("="*80)
    print("\nWHAT TO LOOK FOR IN LOGS:\n")
    print("✅ WebSocket Connection:")
    print("   - 'Connected to Tradovate Market Data WebSocket'")
    print("   - 'Sent authorization message'")
    print("   - 'Connected to Tradovate User Data WebSocket'\n")
    print("✅ Quote Subscription:")
    print("   - 'Sent market data subscription'")
    print("   - 'Updated quote for contract'\n")
    print("✅ P&L Calculation:")
    print("   - 'Using WebSocket quote for'")
    print("   - 'Calculated unrealized P&L'")
    print("   - 'Using WebSocket openPnl'\n")
    print("❌ Errors:")
    print("   - 'Could not connect'")
    print("   - 'Failed to subscribe'")
    print("   - 'Token is INVALID'\n")
    print("="*80)
    print("\nPress Ctrl+C to stop monitoring\n")
    
    # Keep running and provide periodic status
    try:
        import time
        while True:
            time.sleep(5)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring... (check server terminal for logs)")
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")

if __name__ == "__main__":
    monitor_server_logs()

