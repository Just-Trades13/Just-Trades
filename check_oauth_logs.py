#!/usr/bin/env python3
"""
Check OAuth logs to see which accounts logged in
"""

import re
import sys

log_file = 'server.log'

def parse_oauth_logs():
    """Parse server logs for OAuth activity"""
    
    print("=" * 60)
    print("OAuth Flow Log Analysis")
    print("=" * 60)
    print()
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Look for OAuth-related entries
        oauth_events = []
        redirects = []
        callbacks = []
        token_stores = []
        
        for i, line in enumerate(lines):
            # OAuth redirects
            if 'Redirecting account' in line or 'OAuth' in line:
                redirects.append((i, line.strip()))
            
            # Callback received
            if 'callback' in line.lower() or 'code' in line.lower():
                callbacks.append((i, line.strip()))
            
            # Token stored
            if 'token stored' in line.lower() or 'OAuth token' in line:
                token_stores.append((i, line.strip()))
            
            # GET requests that might be callbacks
            if 'GET /' in line and ('code=' in line or 'state=' in line):
                callbacks.append((i, line.strip()))
        
        print("OAuth Redirects:")
        print("-" * 60)
        for idx, line in redirects[-10:]:  # Last 10
            # Extract account ID
            account_match = re.search(r'account (\d+)', line)
            if account_match:
                account_id = account_match.group(1)
                print(f"  Account {account_id}: {line[:100]}")
            else:
                print(f"  {line[:100]}")
        print()
        
        print("OAuth Callbacks (redirects back from Tradovate):")
        print("-" * 60)
        for idx, line in callbacks[-10:]:  # Last 10
            # Extract state/code info
            if 'state=' in line or 'code=' in line:
                print(f"  {line[:120]}")
        print()
        
        print("Token Storage Events:")
        print("-" * 60)
        for idx, line in token_stores[-10:]:  # Last 10
            # Extract account ID
            account_match = re.search(r'account (\d+)', line)
            if account_match:
                account_id = account_match.group(1)
                print(f"  Account {account_id}: Token stored!")
            else:
                print(f"  {line[:100]}")
        print()
        
        # Check for any GET requests to root with query params
        print("Recent GET Requests (might be OAuth callbacks):")
        print("-" * 60)
        recent_gets = []
        for i, line in enumerate(lines[-50:]):  # Last 50 lines
            if 'GET /' in line or 'GET /?' in line:
                recent_gets.append(line.strip())
        
        for line in recent_gets[-10:]:
            print(f"  {line[:120]}")
        print()
        
    except FileNotFoundError:
        print(f"❌ Log file not found: {log_file}")
    except Exception as e:
        print(f"❌ Error reading logs: {e}")


if __name__ == '__main__':
    parse_oauth_logs()

