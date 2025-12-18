#!/usr/bin/env python3
"""
Tradovate API Access Module

Handles API Access login to get both accessToken and mdAccessToken.
This is separate from OAuth and is used for:
- Market data WebSocket (mdAccessToken)
- Trading WebSocket (accessToken)

This follows the same pattern TradingView and TradeManager use.
"""

import aiohttp
import asyncio
import json
import logging
import sqlite3
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TradovateAPIAccess:
    """
    API Access login module for Tradovate.
    
    Uses /auth/accesstokenrequest endpoint to get:
    - accessToken (for trading WebSocket)
    - mdAccessToken (for market data WebSocket)
    """
    
    def __init__(self, demo: bool = True, cid: int = None, sec: str = None):
        """
        Initialize API Access client.
        
        Args:
            demo: Use demo environment (True) or live (False)
            cid: Per-account Client ID (API key). If None, uses global default.
            sec: Per-account Secret. If None, uses global default.
        """
        self.demo = demo
        self.base_url = "https://demo.tradovateapi.com/v1" if demo else "https://live.tradovateapi.com/v1"
        
        # API Access credentials - use per-account if provided, else global default
        import os
        self.app_id = os.getenv("TRADOVATE_APP_ID", "")
        
        # Per-account API key (TradeManager's approach - each user has their own API key)
        # This is the KEY to scaling - each user's rate limits are separate!
        if cid and sec:
            self.cid = int(cid)
            self.sec = sec
            logger.info(f"TradovateAPIAccess using PER-ACCOUNT API key (cid: {cid})")
        else:
            # Fallback to global API key (only works for accounts linked to this key)
            self.cid = int(os.getenv("TRADOVATE_API_CID", "8949"))
            self.sec = os.getenv("TRADOVATE_API_SECRET", "c8440ba5-6315-4845-8c69-977651d5c77a")
        
        self.app_version = os.getenv("TRADOVATE_APP_VERSION", "1.0.0")
        self.device_id = os.getenv("TRADOVATE_DEVICE_ID", "JUST_TRADES_ENGINE")
        
        logger.info(f"TradovateAPIAccess initialized ({'demo' if demo else 'live'})")
    
    async def login(
        self,
        username: str,
        password: str,
        db_path: str = "just_trades.db",
        account_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Login via API Access and store tokens in database.
        
        Uses per-account API keys if available (TradeManager's scalable approach).
        Each user having their own API key means separate rate limit buckets!
        
        Args:
            username: Tradovate username
            password: Tradovate password
            db_path: Path to database
            account_id: Account ID to update (if None, creates new or updates first)
        
        Returns:
            Dict with 'success', 'accessToken', 'mdAccessToken', 'expirationTime', etc.
        """
        try:
            # SCALABLE: Look up per-account API keys (TradeManager's approach)
            # Each user's API key = separate rate limit bucket = no 429 errors at scale!
            use_cid = self.cid
            use_sec = self.sec
            
            # Per-account device ID (TradeManager's approach - unique deviceId per user!)
            # This builds device trust with Tradovate, avoiding captcha challenges
            use_device_id = self.device_id
            
            if account_id:
                try:
                    conn = sqlite3.connect(db_path, timeout=10)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute('SELECT api_key, api_secret, device_id FROM accounts WHERE id = ?', (account_id,))
                    row = cursor.fetchone()
                    conn.close()
                    
                    if row and row['api_key'] and row['api_secret']:
                        use_cid = int(row['api_key'])
                        use_sec = row['api_secret']
                        logger.info(f"🔑 Using PER-ACCOUNT API key for account {account_id} (cid: {use_cid})")
                    
                    # Use per-account device ID (critical for avoiding captcha!)
                    if row and row['device_id']:
                        use_device_id = row['device_id']
                        logger.info(f"📱 Using PER-ACCOUNT device_id for account {account_id}")
                except Exception as e:
                    logger.debug(f"Could not look up per-account settings: {e}")
            
            # Prepare request body with per-account credentials and device ID
            body = {
                "name": username,
                "password": password,
                "appId": self.app_id,
                "appVersion": self.app_version,
                "cid": use_cid,
                "sec": use_sec,
                "deviceId": use_device_id  # Per-account device ID for device trust!
            }
            
            logger.info(f"Calling /auth/accesstokenrequest for {username}...")
            
            # Call API Access endpoint
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/auth/accesstokenrequest",
                    json=body,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API Access login failed: {response.status} - {error_text}")
                        return {
                            'success': False,
                            'error': f'HTTP {response.status}: {error_text}'
                        }
                    
                    data = await response.json()
                    
                    # Check for captcha challenge (device not trusted)
                    if data.get('p-captcha'):
                        p_time = data.get('p-time', 60)
                        logger.warning(f"⚠️ CAPTCHA required for {username} - device not trusted")
                        logger.warning(f"   Device ID: {use_device_id}")
                        logger.warning(f"   Wait time: {p_time}s before retry")
                        logger.warning(f"   Solution: Complete OAuth flow in browser to establish device trust")
                        return {
                            'success': False,
                            'error': 'CAPTCHA required - device not trusted. Use OAuth flow instead.',
                            'p_captcha': True,
                            'p_time': p_time,
                            'device_id': use_device_id
                        }
                    
                    # Check for rate limit / penalty ticket (without captcha)
                    if 'p-ticket' in data and not data.get('accessToken'):
                        p_time = data.get('p-time', 60)
                        logger.warning(f"⚠️ Rate limited for {username} - wait {p_time}s")
                        return {
                            'success': False,
                            'error': f'Rate limited - wait {p_time}s',
                            'p_time': p_time
                        }
                    
                    # Check for errors in response
                    if 'error' in data:
                        logger.error(f"API Access error: {data['error']}")
                        return {
                            'success': False,
                            'error': data['error']
                        }
                    
                    # Extract tokens
                    access_token = data.get('accessToken')
                    md_access_token = data.get('mdAccessToken')
                    expiration_time = data.get('expirationTime')
                    user_id = data.get('userId')
                    has_market_data = data.get('hasMarketData', False)
                    has_live = data.get('hasLive', False)
                    
                    if not access_token:
                        logger.error("No accessToken in response")
                        return {
                            'success': False,
                            'error': 'No accessToken in response'
                        }
                    
                    if not md_access_token:
                        logger.warning("No mdAccessToken in response - account may not have market data access")
                    
                    # Store tokens in database
                    await self._store_tokens(
                        db_path=db_path,
                        account_id=account_id,
                        access_token=access_token,
                        md_access_token=md_access_token,
                        expiration_time=expiration_time,
                        user_id=user_id,
                        username=username,
                        has_market_data=has_market_data,
                        has_live=has_live
                    )
                    
                    logger.info(f"✅ API Access login successful for {username}")
                    logger.info(f"   AccessToken: {bool(access_token)}")
                    logger.info(f"   MDAccessToken: {bool(md_access_token)}")
                    logger.info(f"   HasMarketData: {has_market_data}")
                    logger.info(f"   HasLive: {has_live}")
                    
                    return {
                        'success': True,
                        'accessToken': access_token,
                        'mdAccessToken': md_access_token,
                        'expirationTime': expiration_time,
                        'userId': user_id,
                        'hasMarketData': has_market_data,
                        'hasLive': has_live,
                        'name': data.get('name', username)
                    }
                    
        except Exception as e:
            logger.error(f"API Access login error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _store_tokens(
        self,
        db_path: str,
        account_id: Optional[int],
        access_token: str,
        md_access_token: Optional[str],
        expiration_time: str,
        user_id: int,
        username: str,
        has_market_data: bool,
        has_live: bool
    ) -> None:
        """Store tokens in database with retry logic for database locks."""
        import time
        max_retries = 5
        retry_delay = 0.1  # Start with 100ms
        
        for attempt in range(max_retries):
            try:
                # Use timeout to handle database locks
                conn = sqlite3.connect(db_path, timeout=10.0)
                cursor = conn.cursor()
                
                # Parse expiration time
                try:
                    # Tradovate returns ISO format: "2025-12-11T12:00:00.000Z"
                    expires_at = datetime.fromisoformat(expiration_time.replace('Z', '+00:00'))
                except:
                    # Fallback: assume 24 hours from now
                    expires_at = datetime.now() + timedelta(hours=24)
                
                if account_id:
                    # Update existing account (only update columns that exist in schema)
                    cursor.execute("""
                        UPDATE accounts
                        SET tradovate_token = ?,
                            md_access_token = ?,
                            token_expires_at = ?
                        WHERE id = ?
                    """, (
                        access_token,
                        md_access_token,
                        expires_at.isoformat(),
                        account_id
                    ))
                else:
                    # Find existing account by username or create new
                    cursor.execute("""
                        SELECT id FROM accounts
                        WHERE tradovate_username = ? OR name = ?
                        LIMIT 1
                    """, (username, username))
                    
                    row = cursor.fetchone()
                    if row:
                        account_id = row[0]
                        cursor.execute("""
                            UPDATE accounts
                            SET tradovate_token = ?,
                                md_access_token = ?,
                                token_expires_at = ?,
                                tradovate_user_id = ?,
                                has_market_data = ?,
                                has_live = ?
                            WHERE id = ?
                        """, (
                            access_token,
                            md_access_token,
                            expires_at.isoformat(),
                            user_id,
                            1 if has_market_data else 0,
                            1 if has_live else 0,
                            account_id
                        ))
                    else:
                        # Create new account record
                        cursor.execute("""
                            INSERT INTO accounts (
                                name, tradovate_username,
                                tradovate_token, md_access_token,
                                token_expires_at, tradovate_user_id,
                                has_market_data, has_live,
                                created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            username, username,
                            access_token, md_access_token,
                            expires_at.isoformat(), user_id,
                            1 if has_market_data else 0,
                            1 if has_live else 0,
                            datetime.now().isoformat()
                        ))
                
                conn.commit()
                conn.close()
                
                logger.info(f"✅ Tokens stored in database (account_id: {account_id})")
                return  # Success - exit retry loop
                
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"⚠️ Database locked (attempt {attempt + 1}/{max_retries}), retrying in {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Error storing tokens: {e}", exc_info=True)
                    raise
            except Exception as e:
                logger.error(f"Error storing tokens: {e}", exc_info=True)
                raise
    
    async def refresh_tokens(
        self,
        username: str,
        password: str,
        db_path: str = "just_trades.db",
        account_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Refresh tokens by logging in again.
        
        This is a convenience method that calls login().
        """
        return await self.login(username, password, db_path, account_id)


# Convenience function for async usage
async def get_md_access_token(
    username: str,
    password: str,
    demo: bool = True,
    db_path: str = "just_trades.db",
    account_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get MD access token via API Access login.
    
    Args:
        username: Tradovate username
        password: Tradovate password
        demo: Use demo environment
        db_path: Database path
        account_id: Account ID to update
    
    Returns:
        Dict with login result
    """
    client = TradovateAPIAccess(demo=demo)
    return await client.login(username, password, db_path, account_id)


# Example usage
if __name__ == "__main__":
    import asyncio
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    # Get credentials from environment or prompt
    username = os.getenv("TRADOVATE_USERNAME", "")
    password = os.getenv("TRADOVATE_PASSWORD", "")
    demo = os.getenv("TRADOVATE_DEMO", "1") == "1"
    
    if not username or not password:
        print("Set TRADOVATE_USERNAME and TRADOVATE_PASSWORD environment variables")
        sys.exit(1)
    
    async def main():
        client = TradovateAPIAccess(demo=demo)
        result = await client.login(username, password)
        
        if result['success']:
            print("✅ Login successful!")
            print(f"   AccessToken: {result['accessToken'][:20]}...")
            print(f"   MDAccessToken: {result['mdAccessToken'][:20] if result.get('mdAccessToken') else 'None'}...")
            print(f"   HasMarketData: {result.get('hasMarketData', False)}")
        else:
            print(f"❌ Login failed: {result.get('error')}")
    
    asyncio.run(main())

