#!/usr/bin/env python3
"""
Debug P&L Calculation - See exactly why P&L is $0.00
"""

import sqlite3
import asyncio
import aiohttp
import json
from phantom_scraper.tradovate_integration import TradovateIntegration

async def debug_pnl():
    """Debug why P&L is $0.00"""
    
    print("="*60)
    print("DEBUGGING P&L CALCULATION")
    print("="*60)
    
    # Get account
    db_path = "/Users/mylesjadwin/Trading Projects/just_trades.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, tradovate_token, md_access_token
        FROM accounts 
        WHERE broker = 'Tradovate' 
        LIMIT 1
    """)
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print("❌ No account found")
        return
    
    acc_id, access_token, md_token = account
    
    print(f"\n✅ Account ID: {acc_id}")
    print(f"   Has access_token: {bool(access_token)}")
    print(f"   Has md_access_token: {bool(md_token)}")
    
    # Get positions
    async with TradovateIntegration(demo=True, access_token=access_token) as tradovate:
        if md_token:
            tradovate.md_access_token = md_token
        
        # Get account ID
        accounts = await tradovate.get_accounts()
        if not accounts:
            print("❌ No accounts found")
            return
        
        account_id = str(accounts[0].get('id'))
        print(f"\n✅ Using account ID: {account_id}")
        
        # Get positions
        positions = await tradovate.get_positions(account_id)
        open_positions = [p for p in positions if abs(p.get('netPos', 0)) > 0]
        
        if not open_positions:
            print("❌ No open positions")
            return
        
        print(f"\n✅ Found {len(open_positions)} open position(s)")
        
        for pos in open_positions:
            contract_id = pos.get('contractId')
            symbol = pos.get('symbol', 'N/A')
            net_pos = pos.get('netPos', 0)
            net_price = pos.get('netPrice')
            prev_price = pos.get('prevPrice')
            open_pnl = pos.get('openPnl') or pos.get('unrealizedPnl')
            
            print(f"\n{'='*60}")
            print(f"Position: {symbol} (Contract ID: {contract_id})")
            print(f"{'='*60}")
            print(f"Net Pos: {net_pos}")
            print(f"Net Price (entry): {net_price}")
            print(f"Prev Price (last): {prev_price}")
            print(f"Open P&L (from API): {open_pnl}")
            
            # Check WebSocket quotes
            contract_id_str = str(contract_id)
            ws_quote = tradovate.ws_quotes.get(contract_id_str)
            print(f"\nWebSocket Quote Cache:")
            if ws_quote:
                print(f"  ✅ Found: {ws_quote}")
            else:
                print(f"  ❌ Empty - no quotes received")
            
            # Check WebSocket position updates
            ws_key = f"{account_id}_{contract_id}"
            ws_position = tradovate.ws_positions.get(ws_key)
            print(f"\nWebSocket Position Cache:")
            if ws_position:
                print(f"  ✅ Found: {ws_position}")
                ws_open_pnl = ws_position.get('openPnl')
                if ws_open_pnl is not None:
                    print(f"  ✅ Has openPnl: {ws_open_pnl}")
            else:
                print(f"  ❌ Empty - no position updates received")
            
            # Try to get quote
            print(f"\nTrying to get quote via REST API...")
            try:
                quote = await tradovate.get_quote(str(contract_id), contract_symbol=symbol)
                if quote:
                    print(f"  ✅ Got quote: {quote}")
                else:
                    print(f"  ❌ get_quote() returned None")
            except Exception as e:
                print(f"  ❌ Error: {e}")
            
            # Calculate P&L manually
            print(f"\nManual P&L Calculation:")
            if net_price and net_pos:
                # Try with prevPrice
                if prev_price:
                    price_diff = prev_price - net_price
                    multiplier = 2.0 if 'MNQ' in symbol else 1.0
                    pnl = price_diff * net_pos * multiplier
                    print(f"  Using prevPrice: {prev_price}")
                    print(f"  Price diff: {price_diff}")
                    print(f"  Multiplier: {multiplier}")
                    print(f"  Calculated P&L: ${pnl:.2f}")
                else:
                    print(f"  ❌ No prevPrice available")
                
                # Try with WebSocket quote
                if ws_quote:
                    current_price = ws_quote.get('last') or ws_quote.get('bid') or ws_quote.get('ask')
                    if current_price:
                        price_diff = current_price - net_price
                        multiplier = 2.0 if 'MNQ' in symbol else 1.0
                        pnl = price_diff * net_pos * multiplier
                        print(f"  Using WebSocket quote: {current_price}")
                        print(f"  Price diff: {price_diff}")
                        print(f"  Calculated P&L: ${pnl:.2f}")
                else:
                    print(f"  ❌ No WebSocket quote available")
            
            # Check WebSocket connection status
            print(f"\nWebSocket Status:")
            print(f"  Market Data: {'✅ Connected' if tradovate.ws_connection and not tradovate.ws_connection.closed else '❌ Not connected'}")
            print(f"  User Data: {'✅ Connected' if tradovate.ws_user_connection and not tradovate.ws_user_connection.closed else '❌ Not connected'}")

if __name__ == "__main__":
    asyncio.run(debug_pnl())

