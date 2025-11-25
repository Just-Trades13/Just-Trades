#!/usr/bin/env python3
"""Quick script to verify credentials are stored correctly"""

import sqlite3

conn = sqlite3.connect('just_trades.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT id, name, username, password, client_id, client_secret FROM accounts WHERE id = 4")
account = cursor.fetchone()

if account:
    print("Account stored in database:")
    print(f"  ID: {account['id']}")
    print(f"  Name: {account['name']}")
    print(f"  Username: '{account['username']}' (length: {len(account['username'])})")
    print(f"  Password: '{account['password']}' (length: {len(account['password'])})")
    print(f"  Client ID: {account['client_id']}")
    print(f"  Client Secret: {account['client_secret'][:20]}...")
    
    # Check for hidden characters
    print("\nPassword analysis:")
    print(f"  Has leading/trailing spaces: {account['password'] != account['password'].strip()}")
    print(f"  Contains newlines: {'\\n' in account['password'] or '\\r' in account['password']}")
    print(f"  First 5 chars: {repr(account['password'][:5])}")
    print(f"  Last 5 chars: {repr(account['password'][-5:])}")
else:
    print("Account not found!")

conn.close()

