#!/usr/bin/env python3
"""
Web Authentication Endpoint
This allows users to authenticate through your web interface
(like Trade Manager does) - they solve CAPTCHA, you store the token
"""

import asyncio
import aiohttp
import json
import sqlite3
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from phantom_scraper.tradovate_integration import TradovateIntegration
    TRADOVATE_AVAILABLE = True
except ImportError:
    TRADOVATE_AVAILABLE = False

DB_PATH = os.getenv('DB_PATH', 'just_trades.db')

async def authenticate_and_store_token(account_id: int, username: str, password: str, 
                                      client_id: str, client_secret: str, demo: bool = True):
    """
    Authenticate with Tradovate and store the token
    This should be called from a web interface where user can solve CAPTCHA
    """
    
    print(f"Authenticating account {account_id}...")
    print(f"Note: If CAPTCHA is required, user must solve it in browser")
    print()
    
    if not TRADOVATE_AVAILABLE:
        return {
            "success": False,
            "error": "Tradovate integration not available"
        }
    
    try:
        async with TradovateIntegration(demo=demo) as tradovate:
            # Try to authenticate
            login_data = {
                "name": username,
                "password": password,
                "appId": "Just.Trade",
                "appVersion": "1.0.0",
                "cid": client_id,
                "sec": client_secret
            }
            
            base_url = "https://demo.tradovateapi.com/v1" if demo else "https://live.tradovateapi.com/v1"
            
            async with tradovate.session.post(
                f"{base_url}/auth/accesstokenrequest",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                data = await response.json()
                
                # Check for CAPTCHA
                if "p-captcha" in data and data.get("p-captcha"):
                    return {
                        "success": False,
                        "error": "CAPTCHA_REQUIRED",
                        "captcha_ticket": data.get("p-ticket"),
                        "message": "CAPTCHA verification required. Please authenticate through web interface."
                    }
                
                # Check for access token
                if "accessToken" in data:
                    access_token = data.get("accessToken")
                    refresh_token = data.get("refreshToken")
                    expires_in = data.get("expiresIn", 86400)  # Default 24 hours
                    
                    # Calculate expiration
                    expires_at = datetime.now() + timedelta(seconds=expires_in)
                    
                    # Store in database
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE accounts
                        SET tradovate_token = ?,
                            tradovate_refresh_token = ?,
                            token_expires_at = ?
                        WHERE id = ?
                    """, (access_token, refresh_token, expires_at.isoformat(), account_id))
                    conn.commit()
                    conn.close()
                    
                    print(f"✅ Token stored for account {account_id}")
                    print(f"   Token expires: {expires_at}")
                    
                    return {
                        "success": True,
                        "message": "Authentication successful, token stored",
                        "expires_at": expires_at.isoformat()
                    }
                else:
                    error = data.get("errorText", "Unknown error")
                    return {
                        "success": False,
                        "error": error
                    }
                    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def main():
    """Test authentication and token storage"""
    # Get account from database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, password, client_id, client_secret
        FROM accounts
        WHERE id = 4
    """)
    
    account = cursor.fetchone()
    conn.close()
    
    if not account:
        print("Account not found!")
        return
    
    result = await authenticate_and_store_token(
        account['id'],
        account['username'],
        account['password'],
        account['client_id'],
        account['client_secret'],
        demo=True
    )
    
    print("\n" + "="*60)
    if result.get("success"):
        print("✅ Authentication successful!")
        print("Token stored in database")
        print("Recorder backend can now use this token (no CAPTCHA needed)")
    else:
        if result.get("error") == "CAPTCHA_REQUIRED":
            print("⚠️  CAPTCHA Required")
            print("\nSolution:")
            print("1. Create a web interface endpoint for users to authenticate")
            print("2. User enters credentials in browser")
            print("3. User solves CAPTCHA")
            print("4. Token is stored automatically")
            print("5. Recorder backend uses stored token (no CAPTCHA)")
        else:
            print(f"❌ Authentication failed: {result.get('error')}")


if __name__ == '__main__':
    asyncio.run(main())

