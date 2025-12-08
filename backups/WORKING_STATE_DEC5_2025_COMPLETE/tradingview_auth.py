#!/usr/bin/env python3
"""
🔐 TradingView Auto-Authentication Service

PURPOSE:
Automatically manages TradingView session cookies for the Trading Engine.
When cookies expire, this service logs into TradingView via headless browser
and extracts fresh cookies.

FEATURES:
1. Secure credential storage (encrypted in database)
2. Auto-login via Playwright headless browser
3. Cookie extraction and storage
4. Keep-alive requests to extend session life
5. Automatic refresh on WebSocket disconnect

USAGE:
    # Store credentials (one-time setup)
    python3 tradingview_auth.py store --username YOUR_EMAIL --password YOUR_PASSWORD
    
    # Refresh cookies manually
    python3 tradingview_auth.py refresh
    
    # Check cookie status
    python3 tradingview_auth.py status
    
    # Run keep-alive daemon
    python3 tradingview_auth.py keepalive

Created: December 5, 2025
"""

import os
import sys
import json
import time
import sqlite3
import logging
import hashlib
import base64
import argparse
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from pathlib import Path

# ============================================================================
# Configuration
# ============================================================================

DATABASE_PATH = 'just_trades.db'
TRADINGVIEW_URL = 'https://www.tradingview.com'
LOGIN_URL = 'https://www.tradingview.com/accounts/signin/'
CHART_URL = 'https://www.tradingview.com/chart/'

# Cookie expiry warning threshold (hours)
COOKIE_WARNING_HOURS = 24

# Keep-alive interval (hours)
KEEPALIVE_INTERVAL_HOURS = 6

# ============================================================================
# Logging
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('tradingview_auth')

# ============================================================================
# Simple Encryption (for credential storage)
# ============================================================================

def _get_machine_key() -> bytes:
    """Generate a machine-specific key for encryption"""
    # Use a combination of machine-specific values
    machine_id = f"{os.getlogin()}-{os.uname().nodename}-tradingview-auth"
    return hashlib.sha256(machine_id.encode()).digest()

def encrypt_credential(plaintext: str) -> str:
    """Simple XOR encryption with base64 encoding"""
    key = _get_machine_key()
    encrypted = bytes([ord(c) ^ key[i % len(key)] for i, c in enumerate(plaintext)])
    return base64.b64encode(encrypted).decode()

def decrypt_credential(encrypted: str) -> str:
    """Decrypt XOR encrypted credential"""
    key = _get_machine_key()
    encrypted_bytes = base64.b64decode(encrypted.encode())
    decrypted = ''.join([chr(b ^ key[i % len(key)]) for i, b in enumerate(encrypted_bytes)])
    return decrypted

# ============================================================================
# Database Functions
# ============================================================================

def get_db_connection():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_credentials_table():
    """Create credentials table if it doesn't exist"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tradingview_credentials (
            id INTEGER PRIMARY KEY,
            username_encrypted TEXT NOT NULL,
            password_encrypted TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.debug("Credentials table initialized")

def store_credentials(username: str, password: str) -> bool:
    """Store encrypted TradingView credentials"""
    try:
        init_credentials_table()
        
        username_enc = encrypt_credential(username)
        password_enc = encrypt_credential(password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if credentials exist
        cursor.execute('SELECT id FROM tradingview_credentials LIMIT 1')
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute('''
                UPDATE tradingview_credentials
                SET username_encrypted = ?, password_encrypted = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (username_enc, password_enc, existing['id']))
        else:
            cursor.execute('''
                INSERT INTO tradingview_credentials (username_encrypted, password_encrypted)
                VALUES (?, ?)
            ''', (username_enc, password_enc))
        
        conn.commit()
        conn.close()
        logger.info("✅ TradingView credentials stored securely")
        return True
        
    except Exception as e:
        logger.error(f"Error storing credentials: {e}")
        return False

def get_credentials() -> Optional[Tuple[str, str]]:
    """Retrieve decrypted TradingView credentials"""
    try:
        init_credentials_table()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT username_encrypted, password_encrypted FROM tradingview_credentials LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        username = decrypt_credential(row['username_encrypted'])
        password = decrypt_credential(row['password_encrypted'])
        return (username, password)
        
    except Exception as e:
        logger.error(f"Error retrieving credentials: {e}")
        return None

def store_session_cookies(sessionid: str, sessionid_sign: str) -> bool:
    """Store TradingView session cookies in database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        session_data = json.dumps({
            'sessionid': sessionid,
            'sessionid_sign': sessionid_sign,
            'updated_at': datetime.now().isoformat(),
            'auto_refreshed': True
        })
        
        # Store in accounts table (same location as manual storage)
        cursor.execute('SELECT id FROM accounts LIMIT 1')
        account = cursor.fetchone()
        
        if account:
            cursor.execute('''
                UPDATE accounts SET tradingview_session = ? WHERE id = ?
            ''', (session_data, account['id']))
        else:
            # Create a placeholder account if none exists
            cursor.execute('''
                INSERT INTO accounts (name, tradingview_session) VALUES (?, ?)
            ''', ('Default', session_data))
        
        conn.commit()
        conn.close()
        logger.info("✅ TradingView session cookies stored")
        return True
        
    except Exception as e:
        logger.error(f"Error storing session cookies: {e}")
        return False

def get_session_cookies() -> Optional[Dict]:
    """Get current TradingView session cookies"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT tradingview_session FROM accounts LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        if row and row['tradingview_session']:
            return json.loads(row['tradingview_session'])
        return None
        
    except Exception as e:
        logger.error(f"Error getting session cookies: {e}")
        return None

# ============================================================================
# Playwright Auto-Login
# ============================================================================

def login_and_extract_cookies() -> Optional[Dict[str, str]]:
    """
    Login to TradingView using Playwright and extract session cookies.
    Returns dict with 'sessionid' and 'sessionid_sign' or None on failure.
    """
    credentials = get_credentials()
    if not credentials:
        logger.error("❌ No TradingView credentials stored. Run: python3 tradingview_auth.py store --username EMAIL --password PASSWORD")
        return None
    
    username, password = credentials
    
    try:
        from playwright.sync_api import sync_playwright
        
        logger.info("🔄 Starting TradingView auto-login...")
        
        with sync_playwright() as p:
            # Launch headless browser
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            # Go to login page
            logger.info("📍 Navigating to TradingView login...")
            page.goto(LOGIN_URL, wait_until='networkidle', timeout=30000)
            time.sleep(2)
            
            # Check if already logged in (redirected to chart)
            if '/chart/' in page.url or 'signin' not in page.url:
                logger.info("✅ Already logged in, extracting cookies...")
            else:
                # Click "Email" tab if visible
                try:
                    email_tab = page.locator('button:has-text("Email")')
                    if email_tab.is_visible(timeout=3000):
                        email_tab.click()
                        time.sleep(1)
                except:
                    pass
                
                # Fill in credentials
                logger.info("📝 Entering credentials...")
                
                # Try different selectors for email field
                email_selectors = [
                    'input[name="id"]',
                    'input[name="username"]',
                    'input[type="email"]',
                    'input[placeholder*="Email"]',
                    '#id-input',
                ]
                
                email_filled = False
                for selector in email_selectors:
                    try:
                        email_input = page.locator(selector).first
                        if email_input.is_visible(timeout=2000):
                            email_input.fill(username)
                            email_filled = True
                            logger.debug(f"Email filled using selector: {selector}")
                            break
                    except:
                        continue
                
                if not email_filled:
                    logger.error("❌ Could not find email input field")
                    browser.close()
                    return None
                
                # Try different selectors for password field
                password_selectors = [
                    'input[name="password"]',
                    'input[type="password"]',
                    '#password-input',
                ]
                
                password_filled = False
                for selector in password_selectors:
                    try:
                        password_input = page.locator(selector).first
                        if password_input.is_visible(timeout=2000):
                            password_input.fill(password)
                            password_filled = True
                            logger.debug(f"Password filled using selector: {selector}")
                            break
                    except:
                        continue
                
                if not password_filled:
                    logger.error("❌ Could not find password input field")
                    browser.close()
                    return None
                
                # Click sign in button
                logger.info("🔐 Clicking sign in...")
                signin_selectors = [
                    'button[type="submit"]',
                    'button:has-text("Sign in")',
                    'button:has-text("Log in")',
                    '[data-name="submitButton"]',
                ]
                
                signin_clicked = False
                for selector in signin_selectors:
                    try:
                        signin_btn = page.locator(selector).first
                        if signin_btn.is_visible(timeout=2000):
                            signin_btn.click()
                            signin_clicked = True
                            break
                    except:
                        continue
                
                if not signin_clicked:
                    # Try pressing Enter
                    page.keyboard.press('Enter')
                
                # Wait for login to complete
                logger.info("⏳ Waiting for login to complete...")
                time.sleep(5)
                
                # Check for errors
                try:
                    error = page.locator('.tv-signin-dialog__error, .error-message').first
                    if error.is_visible(timeout=2000):
                        error_text = error.text_content()
                        logger.error(f"❌ Login error: {error_text}")
                        browser.close()
                        return None
                except:
                    pass
                
                # Navigate to chart page to ensure session is fully established
                page.goto(CHART_URL, wait_until='networkidle', timeout=30000)
                time.sleep(3)
            
            # Extract cookies
            logger.info("🍪 Extracting cookies...")
            cookies = context.cookies()
            
            sessionid = None
            sessionid_sign = None
            
            for cookie in cookies:
                if cookie['name'] == 'sessionid':
                    sessionid = cookie['value']
                elif cookie['name'] == 'sessionid_sign':
                    sessionid_sign = cookie['value']
            
            browser.close()
            
            if sessionid and sessionid_sign:
                logger.info("✅ Successfully extracted TradingView cookies!")
                return {
                    'sessionid': sessionid,
                    'sessionid_sign': sessionid_sign
                }
            else:
                logger.error(f"❌ Could not find session cookies. Found cookies: {[c['name'] for c in cookies]}")
                return None
                
    except Exception as e:
        logger.error(f"❌ Error during auto-login: {e}")
        import traceback
        traceback.print_exc()
        return None

# ============================================================================
# Keep-Alive Function
# ============================================================================

def send_keepalive() -> bool:
    """Send keep-alive request to TradingView to extend session"""
    session = get_session_cookies()
    if not session:
        logger.warning("No session cookies to keep alive")
        return False
    
    try:
        import requests
        
        cookies = {
            'sessionid': session.get('sessionid'),
            'sessionid_sign': session.get('sessionid_sign', '')
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
        }
        
        # Make a simple API call to keep session active
        response = requests.get(
            'https://www.tradingview.com/accounts/settings/',
            cookies=cookies,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info("✅ Keep-alive successful")
            return True
        elif response.status_code == 401 or response.status_code == 403:
            logger.warning("⚠️ Session expired, need to re-authenticate")
            return False
        else:
            logger.warning(f"Keep-alive returned status {response.status_code}")
            return True  # Don't fail on other status codes
            
    except Exception as e:
        logger.error(f"Keep-alive error: {e}")
        return False

# ============================================================================
# Main Refresh Function
# ============================================================================

def refresh_cookies() -> bool:
    """
    Main function to refresh TradingView cookies.
    Called when cookies expire or WebSocket disconnects.
    """
    logger.info("🔄 Starting cookie refresh process...")
    
    # First try keep-alive
    if send_keepalive():
        logger.info("✅ Keep-alive successful, cookies still valid")
        return True
    
    # If keep-alive failed, do full re-login
    logger.info("🔐 Keep-alive failed, attempting full re-login...")
    
    cookies = login_and_extract_cookies()
    if cookies:
        # Store the new cookies
        if store_session_cookies(cookies['sessionid'], cookies['sessionid_sign']):
            logger.info("✅ Cookies refreshed and stored!")
            return True
    
    logger.error("❌ Failed to refresh cookies")
    return False

# ============================================================================
# Status Check
# ============================================================================

def check_status():
    """Check current status of TradingView authentication"""
    print("\n" + "="*60)
    print("🔐 TradingView Authentication Status")
    print("="*60)
    
    # Check credentials
    credentials = get_credentials()
    if credentials:
        username, _ = credentials
        # Mask email
        if '@' in username:
            parts = username.split('@')
            masked = parts[0][:3] + '***@' + parts[1]
        else:
            masked = username[:3] + '***'
        print(f"\n📧 Credentials: ✅ Stored ({masked})")
    else:
        print(f"\n📧 Credentials: ❌ Not configured")
        print("   Run: python3 tradingview_auth.py store --username EMAIL --password PASSWORD")
    
    # Check session cookies
    session = get_session_cookies()
    if session:
        updated = session.get('updated_at', 'Unknown')
        auto = "✅ Yes" if session.get('auto_refreshed') else "❌ No"
        print(f"\n🍪 Session Cookies: ✅ Present")
        print(f"   Last updated: {updated}")
        print(f"   Auto-refreshed: {auto}")
        
        # Check if cookies are working
        if send_keepalive():
            print(f"   Status: ✅ Valid and working")
        else:
            print(f"   Status: ⚠️ May be expired")
    else:
        print(f"\n🍪 Session Cookies: ❌ Not configured")
    
    print("\n" + "="*60)

# ============================================================================
# Keep-Alive Daemon
# ============================================================================

def run_keepalive_daemon():
    """Run keep-alive daemon that periodically refreshes cookies"""
    logger.info(f"🔄 Starting keep-alive daemon (every {KEEPALIVE_INTERVAL_HOURS} hours)")
    
    while True:
        try:
            # Check and refresh if needed
            if not send_keepalive():
                logger.warning("Keep-alive failed, attempting refresh...")
                refresh_cookies()
            
            # Sleep until next check
            sleep_seconds = KEEPALIVE_INTERVAL_HOURS * 3600
            logger.info(f"💤 Sleeping for {KEEPALIVE_INTERVAL_HOURS} hours...")
            time.sleep(sleep_seconds)
            
        except KeyboardInterrupt:
            logger.info("Daemon stopped by user")
            break
        except Exception as e:
            logger.error(f"Daemon error: {e}")
            time.sleep(60)  # Wait a minute before retrying

# ============================================================================
# CLI Interface
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='TradingView Auto-Authentication Service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  Store credentials:     python3 tradingview_auth.py store --username email@example.com --password mypassword
  Refresh cookies:       python3 tradingview_auth.py refresh
  Check status:          python3 tradingview_auth.py status
  Run keep-alive daemon: python3 tradingview_auth.py keepalive
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Store command
    store_parser = subparsers.add_parser('store', help='Store TradingView credentials')
    store_parser.add_argument('--username', '-u', required=True, help='TradingView email/username')
    store_parser.add_argument('--password', '-p', required=True, help='TradingView password')
    
    # Refresh command
    subparsers.add_parser('refresh', help='Refresh TradingView cookies')
    
    # Status command
    subparsers.add_parser('status', help='Check authentication status')
    
    # Keep-alive command
    subparsers.add_parser('keepalive', help='Run keep-alive daemon')
    
    args = parser.parse_args()
    
    if args.command == 'store':
        if store_credentials(args.username, args.password):
            print("✅ Credentials stored successfully!")
            print("Now run: python3 tradingview_auth.py refresh")
        else:
            print("❌ Failed to store credentials")
            sys.exit(1)
            
    elif args.command == 'refresh':
        if refresh_cookies():
            print("✅ Cookies refreshed successfully!")
        else:
            print("❌ Failed to refresh cookies")
            sys.exit(1)
            
    elif args.command == 'status':
        check_status()
        
    elif args.command == 'keepalive':
        run_keepalive_daemon()
        
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
