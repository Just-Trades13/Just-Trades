#!/usr/bin/env python3
"""
Tradovate Integration for Just.Trade
Based on Trade Manager's approach - credentials-based authentication
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sqlite3

# WebSocket support
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

logger = logging.getLogger(__name__)

if not WEBSOCKETS_AVAILABLE:
    logger.warning("websockets library not installed. WebSocket order strategies will not work. Install with: pip install websockets")

class TradovateIntegration:
    def __init__(self, demo=True):
        self.base_url = "https://demo.tradovateapi.com/v1" if demo else "https://live.tradovateapi.com/v1"
        # Demo: demo.tradovateapi.com, Live: api.tradovate.com (per API docs)
        self.ws_url = "wss://demo.tradovateapi.com/v1/websocket" if demo else "wss://api.tradovate.com/v1/websocket"
        self.session = None
        self.websocket = None
        self.ws_connected = False
        self.access_token = None
        self.refresh_token = None
        self.token_expires = None
        self.accounts = []
        self.subaccounts = []
        self.contract_cache: Dict[int, Optional[str]] = {}
        
        # ========================================================
        # CRITICAL: TradingView Routing Mode Detection
        # ========================================================
        # When tradingViewTradingEnabled is TRUE:
        #   - WebSocket gets TV-grade tick stream
        #   - Orders route through TradingView router
        #   - Low-latency execution window
        #   - Instant partial fills
        #   - Chart-synchronized PnL
        # 
        # When FALSE:
        #   - Standard (slower) routing
        #   - Delayed exit fills
        #   - Dropped WS events
        #   - TP/SL drifting
        # ========================================================
        self.tradingview_trading_enabled: bool = False
        self.user_features: Dict[str, Any] = {}
        self.user_id: Optional[int] = None
    
    def _update_ws_url_from_base(self):
        """Align websocket URL with current base_url (demo vs live)."""
        if "demo.tradovateapi.com" in (self.base_url or ""):
            self.ws_url = "wss://demo.tradovateapi.com/v1/websocket"
        else:
            self.ws_url = "wss://api.tradovate.com/v1/websocket"
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
            self.ws_connected = False
    
    async def login_with_credentials(self, username: str, password: str, client_id: str = None, client_secret: str = None) -> bool:
        """Login to Tradovate using username/password credentials with Client ID and Secret"""
        try:
            # Use provided client ID and secret, or defaults
            cid = client_id or "your_client_id_here"
            sec = client_secret or "your_client_secret_here"
            
            # Try different authentication approaches
            # Approach 1: With Client ID and Secret
            if cid and sec and cid != "your_client_id_here":
                login_data = {
                    "name": username,
                    "password": password,
                    "appId": "Just.Trade",
                    "appVersion": "1.0.0",
                    "cid": cid,
                    "sec": sec
                }
            else:
                # Approach 2: Try with just device ID (like Trade Manager might do)
                import uuid
                device_id = str(uuid.uuid4())
                
                # Try different app IDs that might work
                app_ids_to_try = [
                    "Tradovate",  # Try official app ID first
                    "TradovateAPI",
                    "TradingApp",
                    "MyApp",
                    "Just.Trade"
                ]
                
                for app_id in app_ids_to_try:
                    login_data = {
                        "name": username,
                        "password": password,
                        "appId": app_id,
                        "appVersion": "1.0.0",
                        "deviceId": device_id
                    }
                    
                    logger.info(f"Trying app ID: {app_id}")
                    
                    # Try live endpoint first with correct endpoint
                    async with self.session.post(
                        f"{live_url}/auth/accesstokenrequest",
                        json=login_data,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        logger.info(f"Live login response status for {app_id}: {response.status}")
                        
                        if response.status == 200:
                            data = await response.json()
                            logger.info(f"Login response data for {app_id}: {data}")
                            
                            if "errorText" not in data and "accessToken" in data:
                                self.access_token = data.get("accessToken")
                                self.refresh_token = data.get("refreshToken")
                                
                                if not self.access_token:
                                    logger.error("No access token received from Tradovate")
                                    continue
                                
                                # Calculate token expiration (usually 24 hours)
                                expires_in = data.get("expiresIn", 86400)  # Default 24 hours
                                self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                                
                                # Update base URL to live
                                self.base_url = live_url
                                
                                logger.info(f"Successfully logged in to LIVE Tradovate as {username} with app ID: {app_id}")
                                logger.info(f"Access token: {self.access_token[:20]}...")
                                return True
                            else:
                                logger.info(f"App ID {app_id} failed: {data.get('errorText', 'Unknown error')}")
                                continue
                        else:
                            logger.info(f"App ID {app_id} failed with status: {response.status}")
                            continue
                
                # If all app IDs failed, try demo endpoint
                logger.info("All app IDs failed on live, trying demo endpoint...")
                login_data = {
                    "name": username,
                    "password": password,
                    "appId": "Tradovate",
                    "appVersion": "1.0.0",
                    "deviceId": device_id
                }
            
            # Try live endpoint first with correct endpoint
            live_url = "https://live.tradovateapi.com/v1"
            demo_url = "https://demo.tradovateapi.com/v1"
            
            logger.info(f"Attempting login to: {live_url}/auth/accesstokenrequest")
            logger.info(f"Login data: {login_data}")
            
            # Try live endpoint first with correct endpoint
            async with self.session.post(
                f"{live_url}/auth/accesstokenrequest",
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                logger.info(f"Live login response status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Login response data: {data}")
                    
                    self.access_token = data.get("accessToken")
                    self.refresh_token = data.get("refreshToken")
                    
                    if not self.access_token:
                        logger.error("No access token received from Tradovate")
                        return False
                    
                    # Calculate token expiration (usually 24 hours)
                    expires_in = data.get("expiresIn", 86400)  # Default 24 hours
                    self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                    
                    # Update base URL to live
                    self.base_url = live_url
                    
                    logger.info(f"Successfully logged in to LIVE Tradovate as {username}")
                    logger.info(f"Access token: {self.access_token[:20]}...")
                    return True
                else:
                    # Try demo endpoint if live fails
                    logger.info("Live login failed, trying demo endpoint...")
                    async with self.session.post(
                        f"{demo_url}/auth/access-token",
                        json=login_data,
                        headers={"Content-Type": "application/json"}
                    ) as response2:
                        logger.info(f"Demo login response status: {response2.status}")
                        
                        if response2.status == 200:
                            data = await response2.json()
                            logger.info(f"Demo login response data: {data}")
                            
                            self.access_token = data.get("accessToken")
                            self.refresh_token = data.get("refreshToken")
                            
                            if not self.access_token:
                                logger.error("No access token received from Tradovate demo")
                                return False
                            
                            expires_in = data.get("expiresIn", 86400)
                            self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                            
                            # Update base URL to demo
                            self.base_url = demo_url
                            
                            logger.info(f"Successfully logged in to DEMO Tradovate as {username}")
                            return True
                        else:
                            try:
                                error_data = await response2.json()
                                logger.error(f"Demo login failed: {error_data}")
                            except:
                                error_text = await response2.text()
                                logger.error(f"Demo login failed: {response2.status} - {error_text}")
                            return False
                    
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    async def refresh_access_token(self) -> Dict[str, Any]:
        """
        Refresh the access token using the renewAccessToken endpoint.
        
        FIXED Dec 9, 2025: Tradovate OAuth tokens are refreshed by calling /auth/renewAccessToken
        with the CURRENT access token in the Authorization header (NOT a refresh token body).
        
        Returns dict with success, access_token, refresh_token, expires_at if successful.
        Returns dict with success=False if failed.
        """
        try:
            if not self.access_token:
                return {'success': False, 'error': 'No access token available for renewal'}
            
            async def try_refresh(base_url: str) -> Dict[str, Any]:
                # FIXED: Use Authorization header with current token, not refreshToken in body
                async with self.session.post(
                    f"{base_url}/auth/renewAccessToken",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json"
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        new_access_token = data.get("accessToken")
                        if new_access_token:
                            return {
                                'success': True,
                                'access_token': new_access_token,
                                'refresh_token': self.refresh_token,  # Keep existing refresh token
                                'expires_in': data.get("expiresIn", 5400)  # Default 90 min
                            }
                        else:
                            return {'success': False, 'error': 'No access token in response'}
                    elif response.status == 401:
                        return {'success': False, 'error': 'Token expired - re-authentication required'}
                    else:
                        error_text = await response.text()
                        return {'success': False, 'error': f'HTTP {response.status}: {error_text}'}
            
            # Try current base_url first, then live, then demo as fallback
            bases = []
            if self.base_url:
                bases.append(self.base_url.rstrip('/'))
            bases.extend([
                "https://live.tradovateapi.com/v1",
                "https://demo.tradovateapi.com/v1"
            ])
            
            tried = set()
            last_error = None
            for b in bases:
                if b in tried:
                    continue
                tried.add(b)
                res = await try_refresh(b)
                if res.get('success'):
                    self.access_token = res['access_token']
                    self.refresh_token = res['refresh_token']
                    expires_in = res.get('expires_in', 86400)
                    self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                    # Keep base_url aligned with the successful refresh host
                    self.base_url = b
                    # Align WS URL with refreshed base
                    self._update_ws_url_from_base()
                    logger.info(f"Access token refreshed successfully via {b}")
                    return {
                        'success': True,
                        'access_token': self.access_token,
                        'refresh_token': self.refresh_token,
                        'expires_at': self.token_expires
                    }
                else:
                    last_error = res.get('error')
                    logger.warning(f"Refresh attempt failed on {b}: {last_error}")
            
            return {'success': False, 'error': last_error or 'Refresh failed on all endpoints'}
                    
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def check_tradingview_routing_enabled(self) -> Dict[str, Any]:
        """
        Check if the account has TradingView routing mode enabled.
        
        THIS IS THE KEY TO TRADERMANAGER-GRADE EXECUTION.
        
        When tradingViewTradingEnabled is TRUE:
        - WebSocket gets the high-frequency TV tick stream
        - Orders route through TradingView router
        - Low-latency execution window (microsecond fills)
        - Instant partial fills
        - Chart-synchronized PnL
        - Enhanced order-state messages
        
        When FALSE:
        - Standard (slower) routing
        - Delayed exit fills
        - Worse DCA timing
        - Dropped WS events
        - TP/SL drifting
        - Mismatched PnL
        
        Returns:
            Dict with:
                - 'enabled': bool - TRUE if TradingView routing is active
                - 'user_id': int - User ID
                - 'features': dict - All user features
                - 'error': str - Error message if failed
        """
        try:
            if not self.access_token:
                return {'enabled': False, 'error': 'Not authenticated'}
            
            # Call /auth/me to get user profile with features
            async with self.session.get(
                f"{self.base_url}/auth/me",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    self.user_id = data.get('userId')
                    self.user_features = data
                    
                    # Check for TradingView routing flag
                    # Tradovate may use different field names:
                    #   - tradingViewTradingEnabled (primary)
                    #   - features.tradingViewTradingEnabled
                    #   - orderRouting.tradingViewAuthorized
                    #   - activePlugins containing 'tradingView'
                    
                    tv_enabled = False
                    detection_method = None
                    
                    # Method 1: Direct field
                    if data.get('tradingViewTradingEnabled'):
                        tv_enabled = True
                        detection_method = 'tradingViewTradingEnabled'
                    
                    # Method 2: Nested in features
                    elif data.get('features', {}).get('tradingViewTradingEnabled'):
                        tv_enabled = True
                        detection_method = 'features.tradingViewTradingEnabled'
                    
                    # Method 3: Order routing
                    elif data.get('orderRouting', {}).get('tradingViewAuthorized'):
                        tv_enabled = True
                        detection_method = 'orderRouting.tradingViewAuthorized'
                    
                    # Method 4: Active plugins
                    active_plugins = data.get('activePlugins', [])
                    if isinstance(active_plugins, list):
                        for plugin in active_plugins:
                            plugin_str = str(plugin).lower()
                            if 'tradingview' in plugin_str or 'tv' in plugin_str:
                                tv_enabled = True
                                detection_method = f'activePlugins: {plugin}'
                                break
                    
                    # Method 5: Market data subscriptions (CME TradingView bundle)
                    md_subs = data.get('currentMDSubs', [])
                    if isinstance(md_subs, list):
                        for sub in md_subs:
                            if 'tradingview' in str(sub).lower():
                                tv_enabled = True
                                detection_method = f'currentMDSubs: {sub}'
                                break
                    
                    self.tradingview_trading_enabled = tv_enabled
                    
                    if tv_enabled:
                        logger.info(f"✅ TRADINGVIEW ROUTING ENABLED via {detection_method}")
                        logger.info("   → WebSocket will receive TV-grade tick stream")
                        logger.info("   → Orders will route through TradingView router")
                        logger.info("   → Low-latency execution mode ACTIVE")
                    else:
                        logger.warning("⚠️ TRADINGVIEW ROUTING NOT DETECTED")
                        logger.warning("   → Standard (slower) routing will be used")
                        logger.warning("   → User should enable TradingView Add-On in Tradovate")
                    
                    return {
                        'enabled': tv_enabled,
                        'detection_method': detection_method,
                        'user_id': self.user_id,
                        'features': data,
                        'active_plugins': active_plugins,
                        'md_subscriptions': md_subs,
                    }
                else:
                    error = await response.text()
                    logger.error(f"Failed to get user profile: {response.status} - {error[:200]}")
                    return {'enabled': False, 'error': f'HTTP {response.status}'}
                    
        except Exception as e:
            logger.error(f"Error checking TradingView routing: {e}")
            return {'enabled': False, 'error': str(e)}
    
    def is_tradingview_routing_active(self) -> bool:
        """
        Quick check if TradingView routing is active.
        Call check_tradingview_routing_enabled() first to populate this.
        """
        return self.tradingview_trading_enabled
    
    async def require_tradingview_routing(self) -> None:
        """
        Enforce TradingView routing requirement.
        Raises exception if not enabled.
        
        Use this at the start of any auto-trading operation.
        """
        result = await self.check_tradingview_routing_enabled()
        if not result.get('enabled'):
            raise Exception(
                "TradingView Add-On Required for Auto-Trading. "
                "Enable the TradingView Add-On in your Tradovate account settings."
            )
    
    async def _ensure_websocket_connected(self) -> bool:
        """
        Ensure WebSocket is connected and authenticated.
        Returns True if connected, False otherwise.
        """
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library not installed. Cannot use WebSocket order strategies.")
            logger.error("Install with: pip install websockets")
            return False
        
        # Ensure we have a valid token before connecting
        if not self.access_token:
            logger.error("Cannot connect WebSocket: No access token. Please login first.")
            return False
        
        # Check token validity and refresh if needed
        await self._ensure_valid_token()
        
        if self.ws_connected and self.websocket:
            try:
                # Check if connection is still alive
                # Check websocket state - websockets library uses closed property
                if hasattr(self.websocket, 'closed') and not self.websocket.closed:
                    return True
                elif hasattr(self.websocket, 'open') and self.websocket.open:
                    return True
                else:
                    # Connection closed
                    logger.info("WebSocket connection closed, will reconnect...")
                    self.ws_connected = False
                    self.websocket = None
            except Exception as e:
                # Connection dead, reconnect
                logger.warning(f"WebSocket connection check failed: {e}, reconnecting...")
                self.ws_connected = False
                if self.websocket:
                    try:
                        await self.websocket.close()
                    except:
                        pass
                    self.websocket = None
        
        try:
            async def connect_and_auth() -> bool:
                # Connect to WebSocket (URL aligned with base_url)
                logger.info(f"🔌 Connecting to Tradovate WebSocket: {self.ws_url}")
                # Some websockets versions don't support extra_headers; send token via auth message only
                self.websocket = await websockets.connect(self.ws_url)
                
                # Authenticate via WebSocket
                auth_message = {
                    "url": "authorize",
                    "token": self.access_token
                }
                logger.debug(f"🔐 Sending WebSocket auth with token: {self.access_token[:20]}...")
                await self.websocket.send(json.dumps(auth_message))
                
                # Wait for authentication response
                response = await asyncio.wait_for(self.websocket.recv(), timeout=10.0)
                raw_response = response
                if not raw_response:
                    logger.error("WebSocket auth response is empty/None")
                else:
                    logger.error(f"WebSocket auth raw (first 200 chars): {str(raw_response)[:200]}")
                try:
                    auth_result = json.loads(response)
                except Exception:
                    auth_result = raw_response
                
                # Check if auth was successful
                is_ok = False
                if isinstance(auth_result, dict):
                    is_ok = auth_result.get('ok') or auth_result.get('success') or auth_result.get('status') == 'ok'
                elif isinstance(auth_result, list) and len(auth_result) > 0:
                    is_ok = auth_result[0] == 'ok' or (isinstance(auth_result[0], dict) and auth_result[0].get('ok'))
                
                if is_ok or (isinstance(auth_result, str) and auth_result and 'error' not in str(auth_result).lower()):
                    self.ws_connected = True
                    logger.info("✅ WebSocket authenticated successfully")
                    return True
                else:
                    logger.error(f"WebSocket authentication failed: {auth_result}")
                    await self.websocket.close()
                    self.websocket = None
                    return False
            
            # Attempt auth; if it fails, force a refresh and retry once
            success = await connect_and_auth()
            if not success:
                logger.warning("WebSocket auth failed - attempting token refresh and one retry")
                refresh_res = await self.refresh_access_token()
                if refresh_res.get('success'):
                    self._last_refresh_result = refresh_res
                    self._update_ws_url_from_base()
                    # Reconnect with new token
                    success = await connect_and_auth()
            
            if success:
                return True
            else:
                return False
            
        except Exception as e:
            logger.error(f"Failed to connect/authenticate WebSocket: {e}")
            if self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
                self.websocket = None
            self.ws_connected = False
            return False
    
    async def _send_websocket_message(self, message_type: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send a message via WebSocket using Tradovate's format.
        
        Format: {"n": "messageType", "o": {payload}}
        """
        if not await self._ensure_websocket_connected():
            return None
        
        try:
            # Per DCA guide: {"n": "orderStrategy/startOrderStrategy", "o": {...}}
            message = {
                "n": message_type,
                "o": payload
            }
            
            message_json = json.dumps(message)
            logger.info(f"📤 Sending WebSocket message: {message_type}")
            logger.debug(f"   Payload: {json.dumps(payload, indent=2)}")
            
            await self.websocket.send(message_json)
            
            # Wait for response (with timeout)
            # Note: Tradovate WebSocket may send multiple messages, we need the response to our request
            response = await asyncio.wait_for(self.websocket.recv(), timeout=30.0)
            result = json.loads(response)
            
            logger.info(f"📥 WebSocket response received for {message_type}")
            logger.debug(f"   Response: {result}")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"WebSocket message timeout for {message_type}")
            return None
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            self.ws_connected = False
            return None
    
    def _get_headers(self, use_basic_auth: bool = False, username: str = None, password: str = None) -> Dict[str, str]:
        """
        Get headers with authorization token or Basic Auth.
        
        Args:
            use_basic_auth: If True, use Basic Auth with username/password instead of token
            username: Username for Basic Auth (required if use_basic_auth=True)
            password: Password for Basic Auth (required if use_basic_auth=True)
        """
        headers = {"Content-Type": "application/json"}
        
        if use_basic_auth and username and password:
            # Use Basic Authentication (like Trade Manager does)
            import base64
            credentials = f"{username}:{password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_credentials}"
            logger.debug(f"Using Basic Auth for {username}")
        elif self.access_token:
            # Use Bearer token (standard method)
            headers["Authorization"] = f"Bearer {self.access_token}"
        else:
            # No auth - might work for some public endpoints
            logger.warning("No authentication method available - request may fail")
            
        return headers
    
    async def _ensure_valid_token(self) -> bool:
        """
        Check if token is expired and refresh if needed.
        Returns True if token is valid (or was successfully refreshed), False otherwise.
        """
        try:
            # Check if token expires within 5 minutes (refresh proactively)
            if self.token_expires:
                time_until_expiry = (self.token_expires - datetime.now()).total_seconds()
                if time_until_expiry < 300:  # Less than 5 minutes
                    logger.info(f"Token expires in {time_until_expiry:.0f} seconds, refreshing...")
                    result = await self.refresh_access_token()
                    if result.get('success'):
                        # Store refresh result for caller to persist to DB
                        self._last_refresh_result = result
                        return True
                    else:
                        logger.error("Failed to refresh token proactively")
                        return False
                elif time_until_expiry <= 0:
                    # Token already expired
                    logger.warning("Token has expired, refreshing...")
                    result = await self.refresh_access_token()
                    if result.get('success'):
                        # Store refresh result for caller to persist to DB
                        self._last_refresh_result = result
                        return True
                    else:
                        logger.error("Failed to refresh expired token")
                        return False
            return True  # Token is valid or no expiry set
        except Exception as e:
            logger.error(f"Error checking token validity: {e}")
            return False
    
    async def get_accounts(self, username: str = None, password: str = None) -> List[Dict[str, Any]]:
        """
        Get all accounts for the authenticated user.
        
        Args:
            username: Optional username for Basic Auth (like Trade Manager)
            password: Optional password for Basic Auth (like Trade Manager)
        """
        try:
            # Try Basic Auth first if credentials provided (Trade Manager style)
            if username and password:
                logger.info(f"Getting accounts using Basic Auth (Trade Manager style)...")
                headers = self._get_headers(use_basic_auth=True, username=username, password=password)
            else:
                headers = self._get_headers()
            
            async with self.session.get(
                f"{self.base_url}/account/list",
                headers=headers
            ) as response:
                logger.info(f"Account list response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    self.accounts = data
                    logger.info(f"Retrieved {len(self.accounts)} real accounts from Tradovate")
                    for account in data:
                        logger.info(f"Account: {account}")
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get accounts: {response.status} - {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            return []
    
    async def get_subaccounts(self, account_id: str, username: str = None, password: str = None) -> List[Dict[str, Any]]:
        """
        Get subaccounts for a specific account.
        
        Args:
            account_id: Account ID to get subaccounts for
            username: Optional username for Basic Auth (like Trade Manager)
            password: Optional password for Basic Auth (like Trade Manager)
        """
        try:
            # Try Basic Auth first if credentials provided (Trade Manager style)
            if username and password:
                logger.info(f"Getting subaccounts using Basic Auth (Trade Manager style)...")
                headers = self._get_headers(use_basic_auth=True, username=username, password=password)
            else:
                headers = self._get_headers()
            
            async with self.session.get(
                f"{self.base_url}/account/{account_id}/subaccounts",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.subaccounts.extend(data)
                    logger.info(f"Retrieved {len(data)} subaccounts for account {account_id}")
                    return data
                elif response.status == 401 and username and password:
                    # If Basic Auth failed, try with token
                    logger.info("Basic Auth failed, trying with token...")
                    headers = self._get_headers()
                    async with self.session.get(
                        f"{self.base_url}/account/{account_id}/subaccounts",
                        headers=headers
                    ) as response2:
                        if response2.status == 200:
                            data = await response2.json()
                            self.subaccounts.extend(data)
                            logger.info(f"Retrieved {len(data)} subaccounts for account {account_id} (using token)")
                            return data
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get subaccounts: {response.status} - {error_text[:200]}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting subaccounts: {e}")
            return []
    
    async def get_account_info(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific account"""
        try:
            async with self.session.get(
                f"{self.base_url}/account/{account_id}",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Retrieved account info for {account_id}")
                    return data
                else:
                    logger.error(f"Failed to get account info: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    async def place_order(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place an order on Tradovate"""
        try:
            # Ensure we have a valid token before making request
            if not await self._ensure_valid_token():
                logger.error("Cannot place order: token invalid and refresh failed")
                return {'success': False, 'error': 'Token invalid and refresh failed'}
            
            async def do_place():
                async with self.session.post(
                    f"{self.base_url}/order/placeorder",
                    json=order_data,
                    headers=self._get_headers()
                ) as response_inner:
                    try:
                        data_inner = await response_inner.json()
                    except Exception:
                        data_inner = {}
                        try:
                            text_body_inner = await response_inner.text()
                        except Exception:
                            text_body_inner = ''
                    else:
                        text_body_inner = ''
                    return response_inner.status, data_inner, text_body_inner
            
            status, data, text_body = await do_place()

            # If token expired or unauthorized, try to refresh and retry once
            if status == 401:
                error_text = text_body or str(data)
                logger.warning(f"401 during place_order, attempting refresh... details={error_text}")
                refresh_result = await self.refresh_access_token()
                if refresh_result.get('success'):
                    self._last_refresh_result = refresh_result
                    status, data, text_body = await do_place()
                    if status == 200 and data.get('orderId'):
                        logger.info(f"Order placed successfully after token refresh: {data.get('orderId')}")
                        data['success'] = True
                        return data
                    else:
                        retry_error = data.get('failureText') or data.get('details') or text_body or data
                        logger.error(f"Failed to place order after refresh: {retry_error}")
                        return {'success': False, 'error': retry_error, 'raw': data or text_body}
                else:
                    logger.error(f"Failed to refresh token after 401 error: {refresh_result.get('error', 'Unknown')}")
                    return {'success': False, 'error': 'Expired Access Token - refresh failed'}
            # Handle 429 with exponential backoff/retry (more aggressive for critical order placement)
            elif status == 429:
                max_retries = 5
                retry_delays = [1.0, 2.0, 4.0, 8.0, 16.0]  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                
                for retry_num in range(max_retries):
                    delay = retry_delays[retry_num]
                    logger.warning(f"429 during place_order - backing off {delay}s and retrying ({retry_num + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    status, data, text_body = await do_place()
                    
                    if status == 200 and data.get('orderId'):
                        logger.info(f"✅ Order placed successfully after 429 retry {retry_num + 1}: {data.get('orderId')}")
                        data['success'] = True
                        return data
                    elif status != 429:
                        # Non-429 error, break and return
                        break
                
                # If still 429 after all retries
                if status == 429:
                    logger.error(f"❌ Rate limited (429) on place_order after {max_retries} retries - giving up")
                    return {'success': False, 'error': f'Rate limited (429) on place_order after {max_retries} retries', 'raw': data or text_body}
            if status == 200 and data.get('orderId'):
                logger.info(f"Order placed successfully: {data.get('orderId')}")
                data['success'] = True
                return data
            else:
                error_text = data.get('failureText') or data.get('details') or text_body or data
                logger.error(f"Failed to place order: {error_text}")
                return {'success': False, 'error': error_text, 'raw': data or text_body}
                    
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_fills(self, account_id: Optional[int] = None, order_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get fills for an account or specific order"""
        try:
            params = {}
            if account_id:
                params['accountId'] = account_id
            if order_id:
                params['orderId'] = order_id
            
            async with self.session.get(
                f"{self.base_url}/fill/list",
                params=params,
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json() or []
                    logger.info(f"Retrieved {len(data)} fills for account={account_id}, order={order_id}")
                    return data
                else:
                    logger.warning(f"Failed to get fills: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error getting fills: {e}")
            return []
    
    async def get_positions(self, account_id: Optional[int] = None, username: str = None, password: str = None) -> List[Dict[str, Any]]:
        """
        Get current positions; optionally filter by account_id.
        
        Args:
            account_id: Optional account ID to filter positions
            username: Optional username for Basic Auth (like Trade Manager)
            password: Optional password for Basic Auth (like Trade Manager)
        """
        try:
            # If using Basic Auth, skip token validation
            if not username or not password:
                # Ensure token is valid before making request
                if not await self._ensure_valid_token():
                    logger.error("Cannot get positions: token invalid and refresh failed")
                    return []
            
            async def fetch_positions() -> (int, Any):
                # Try Basic Auth first if credentials provided (Trade Manager style)
                if username and password:
                    logger.info(f"Getting positions using Basic Auth (Trade Manager style)...")
                    headers = self._get_headers(use_basic_auth=True, username=username, password=password)
                else:
                    headers = self._get_headers()
                
                # CRITICAL: Use the CORRECT endpoint for the account type
                # Demo positions ONLY exist on demo API, live positions ONLY exist on live API
                # DO NOT try cross-API calls - they will return 0 positions
                urls_to_try = [self.base_url]  # Use the configured endpoint only
                
                last_error = None
                for url in urls_to_try:
                    try:
                        async with self.session.get(
                            f"{url}/position/list",
                            headers=headers
                        ) as resp:
                            status = resp.status
                            try:
                                payload = await resp.json()
                            except Exception:
                                payload = await resp.text()
                            
                            # If successful, return immediately
                            if status == 200:
                                if url != self.base_url:
                                    logger.debug(f"✅ Got positions from {url} (fallback endpoint)")
                                return status, payload
                            
                            # If 401 or 403, try next URL (might be account type mismatch)
                            if status in [401, 403]:
                                logger.debug(f"Got {status} from {url}, trying next endpoint...")
                                last_error = f"HTTP {status}"
                                continue
                            
                            # For other errors, return immediately
                            return status, payload
                    except Exception as e:
                        logger.debug(f"Error with {url}: {e}, trying next endpoint...")
                        last_error = str(e)
                        continue
                
                # If all URLs failed, return error
                logger.warning(f"All endpoints failed for get_positions, last error: {last_error}")
                return 500, {'error': f'All endpoints failed: {last_error}'}
            
            status, payload = await fetch_positions()
            
            # On any 401, try Basic Auth if credentials provided, or attempt token refresh
            if status == 401:
                if username and password:
                    logger.warning("401 during get_positions, trying Basic Auth...")
                    headers = self._get_headers(use_basic_auth=True, username=username, password=password)
                    async with self.session.get(
                        f"{self.base_url}/position/list",
                        headers=headers
                    ) as resp2:
                        status2 = resp2.status
                        if status2 == 200:
                            try:
                                payload2 = await resp2.json()
                                logger.info("✅ Got positions using Basic Auth (Trade Manager style)")
                                return payload2 if isinstance(payload2, list) else []
                            except Exception:
                                payload2 = await resp2.text()
                                return []
                
                logger.warning("401 during get_positions, attempting token refresh and retry...")
                refresh_result = await self.refresh_access_token()
                if refresh_result.get('success'):
                    self._last_refresh_result = refresh_result
                    status, payload = await fetch_positions()
                else:
                    logger.error(f"Failed to refresh token after 401 error: {refresh_result.get('error', 'unknown')}")
                    return []
            
            # On 429 (rate limit), try two short backoffs/retries
            if status == 429:
                # More aggressive retry for get_positions (but fewer retries since it's less critical)
                max_retries = 3
                retry_delays = [1.0, 2.0, 4.0]  # Exponential backoff: 1s, 2s, 4s
                
                for retry_num in range(max_retries):
                    delay = retry_delays[retry_num]
                    logger.warning(f"429 during get_positions - backing off {delay}s and retrying ({retry_num + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                    status, payload = await fetch_positions()
                    
                    if status == 200:
                        break  # Success
                    elif status != 429:
                        # Non-429 error, break and return empty
                        break
            
            if status != 200:
                if status == 429:
                    logger.error(f"Failed to get positions after {max_retries} retries: 429 (rate limited)")
                else:
                    logger.error(f"Failed to get positions: {status} | payload={payload}")
                return []  # Return empty list on error (caller should handle gracefully)
            
            data = payload or []
            
            if account_id is not None:
                data = [pos for pos in data if str(pos.get('accountId')) == str(account_id)]
            enriched = []
            for pos in data:
                contract_id = pos.get('contractId')
                if contract_id:
                    symbol = await self._get_contract_symbol(contract_id)
                    if symbol:
                        pos['symbol'] = symbol
                enriched.append(pos)
            logger.info(f"Retrieved {len(enriched)} positions for account {account_id}")
            return enriched
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    async def _get_contract_symbol(self, contract_id: int) -> Optional[str]:
        if not contract_id:
            return None
        if contract_id in self.contract_cache:
            return self.contract_cache[contract_id]
        try:
            async with self.session.get(
                f"{self.base_url}/contract/item",
                params={'id': contract_id},
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json() or {}
                    symbol = data.get('symbol') or data.get('name') or data.get('contractName')
                    self.contract_cache[contract_id] = symbol
                    return symbol
                else:
                    logger.error(f"Failed to fetch contract {contract_id}: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching contract {contract_id}: {e}")
        self.contract_cache[contract_id] = None
        return None
    
    async def get_contract_id(self, symbol: str) -> Optional[int]:
        """
        Get contract ID from symbol name.
        
        This is needed for liquidate_position which requires contract_id.
        
        Args:
            symbol: The contract symbol (e.g., "MNQZ5")
        
        Returns:
            Contract ID if found, None otherwise
        """
        try:
            # First check cache (reverse lookup)
            for cid, cached_symbol in self.contract_cache.items():
                if cached_symbol == symbol:
                    return cid
            
            # Search via contract/find
            async with self.session.get(
                f"{self.base_url}/contract/find",
                params={'name': symbol},
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and isinstance(data, dict):
                        contract_id = data.get('id')
                        if contract_id:
                            self.contract_cache[contract_id] = symbol
                            logger.info(f"Resolved symbol {symbol} to contract ID {contract_id}")
                            return contract_id
                else:
                    logger.warning(f"Contract lookup for {symbol} returned status {response.status}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting contract ID for {symbol}: {e}")
            return None
    
    async def get_orders(self, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get orders for an account or all orders.
        If account_id is None, uses /order/list to get all orders (includes order strategies).
        Fallback: if account-scoped fetch returns empty, retry with /order/list to avoid missing working exits.
        """
        try:
            async def fetch(url: str) -> List[Dict[str, Any]]:
                async with self.session.get(url, headers=self._get_headers()) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Retrieved {len(data)} orders from {url}")
                        return data if isinstance(data, list) else []
                    elif response.status == 404:
                        return []
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get orders from {url}: {response.status}, {error_text[:200]}")
                        return []
            
            if account_id:
                primary_url = f"{self.base_url}/account/{account_id}/orders"
                orders = await fetch(primary_url)
                if not orders:
                    fallback_url = f"{self.base_url}/order/list"
                    logger.info(f"Account-scoped orders empty, retrying with {fallback_url}")
                    orders = await fetch(fallback_url)
                return orders
            else:
                url = f"{self.base_url}/order/list"
                return await fetch(url)
                    
        except Exception as e:
            logger.error(f"Error getting orders: {e}", exc_info=True)
            return []
    
    async def get_order_item(self, order_id: int) -> Optional[Dict[str, Any]]:
        """
        Get full details for a specific order using order/item endpoint.
        Returns all order fields including symbol, orderType, price, orderQty, ordStatus.
        """
        try:
            if not order_id:
                return None
                
            url = f"{self.base_url}/order/item"
            async with self.session.get(
                url,
                params={"id": order_id},
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📋 Order {order_id} details: status={data.get('ordStatus')}, price={data.get('price')}, qty={data.get('orderQty')}")
                    return data
                elif response.status == 404:
                    logger.info(f"📋 Order {order_id} not found (may be filled/cancelled)")
                    return None
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to get order {order_id}: {response.status}, {error_text[:200]}")
                    return None
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    async def cancel_order(self, order_id: int) -> bool:
        """Cancel an existing order"""
        try:
            if not order_id:
                logger.warning(f"Attempted to cancel order with invalid ID: {order_id}")
                return False
            
            logger.info(f"Attempting to cancel order {order_id} via {self.base_url}/order/cancelorder")
            # Per Tradovate JSON reference Section 7.2: Cancel order format
            # Only requires orderId - isAutomated is optional for order placement, not cancellation
            async with self.session.post(
                f"{self.base_url}/order/cancelorder",
                json={"orderId": order_id},
                headers=self._get_headers()
            ) as response:
                response_text = await response.text()
                logger.info(f"Cancel order {order_id} response: status={response.status}, body={response_text[:500]}")
                
                if response.status == 200:
                    try:
                        data = await response.json()
                        logger.info(f"✅ Successfully cancelled order {order_id}, response: {data}")
                        return True
                    except:
                        logger.info(f"✅ Successfully cancelled order {order_id} (no JSON response)")
                        return True
                else:
                    try:
                        error = await response.json()
                        logger.error(f"❌ Failed to cancel order {order_id}: HTTP {response.status}, error: {error}")
                    except:
                        logger.error(f"❌ Failed to cancel order {order_id}: HTTP {response.status}, response: {response_text[:500]}")
                    return False
        except Exception as e:
            logger.error(f"Exception cancelling order {order_id}: {e}", exc_info=True)
            return False
    
    async def modify_order(self, order_id: int, new_price: float = None, new_qty: int = None, 
                          stop_price: float = None, order_type: str = None, 
                          time_in_force: str = None, is_automated: bool = True) -> Optional[Dict[str, Any]]:
        """
        Modify an existing order (change price, quantity, or stop price).
        
        Per tradovate_single_tp_dca_bulletproof.md: MUST include orderQty, orderType, and timeInForce.
        
        Args:
            order_id: The order ID to modify
            new_price: New limit price (for limit orders)
            new_qty: New quantity (REQUIRED for limit orders)
            stop_price: New stop price (for stop orders)
            order_type: Order type (REQUIRED: "Limit" for limit orders)
            time_in_force: Time in force (REQUIRED: must match existing, typically "GTC")
            is_automated: Whether order is automated (default True)
        
        Returns:
            Dict with success flag and order result, or None on error
        """
        try:
            if not order_id:
                logger.warning(f"Attempted to modify order with invalid ID: {order_id}")
                return {'success': False, 'error': 'Invalid order ID'}
            
            # Build modification payload - per spec: MUST include orderQty, orderType, timeInForce
            modify_data = {"orderId": order_id}
            
            if new_price is not None:
                modify_data["price"] = float(new_price)
            if new_qty is not None:
                modify_data["orderQty"] = int(new_qty)  # REQUIRED
            if stop_price is not None:
                modify_data["stopPrice"] = float(stop_price)
            if order_type:
                modify_data["orderType"] = str(order_type)  # REQUIRED
            if time_in_force:
                modify_data["timeInForce"] = str(time_in_force)  # REQUIRED (must match existing)
            modify_data["isAutomated"] = bool(is_automated)
            
            logger.info(f"Modifying order {order_id}: {modify_data}")
            
            async with self.session.post(
                f"{self.base_url}/order/modifyorder",
                json=modify_data,
                headers=self._get_headers()
            ) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        logger.info(f"✅ Modified order {order_id} successfully")
                        return {'success': True, 'data': data, 'orderId': order_id}
                    except:
                        logger.info(f"✅ Modified order {order_id} (no JSON response)")
                        return {'success': True, 'orderId': order_id}
                else:
                    logger.error(f"❌ Failed to modify order {order_id}: HTTP {response.status}, response: {response_text[:500]}")
                    return {'success': False, 'error': response_text, 'status': response.status}
                    
        except Exception as e:
            logger.error(f"Exception modifying order {order_id}: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def get_order_strategies(self, account_id: int = None) -> List[Dict[str, Any]]:
        """
        Get all order strategies (bracket orders, OCO orders, etc.)
        These need to be interrupted separately from regular orders.
        """
        try:
            url = f"{self.base_url}/orderStrategy/list"
            async with self.session.get(url, headers=self._get_headers()) as response:
                if response.status == 200:
                    data = await response.json()
                    strategies = data if isinstance(data, list) else []
                    
                    # Filter by account if specified
                    if account_id and strategies:
                        strategies = [s for s in strategies if str(s.get('accountId')) == str(account_id)]
                    
                    logger.info(f"Retrieved {len(strategies)} order strategies")
                    return strategies
                else:
                    error_text = await response.text()
                    logger.warning(f"Failed to get order strategies: {response.status}, {error_text[:200]}")
                    return []
        except Exception as e:
            logger.error(f"Error getting order strategies: {e}")
            return []
    
    async def interrupt_order_strategy(self, order_strategy_id: int) -> Optional[Dict[str, Any]]:
        """
        Interrupt/stop a running order strategy (bracket, OCO, etc.)
        This cancels all orders in the strategy.
        """
        try:
            async with self.session.post(
                f"{self.base_url}/orderStrategy/interruptorderstrategy",
                json={"orderStrategyId": order_strategy_id},
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Interrupted order strategy {order_strategy_id}")
                    return {'success': True, 'data': data}
                else:
                    try:
                        error = await response.json()
                    except Exception:
                        error = await response.text()
                    logger.error(f"Failed to interrupt order strategy {order_strategy_id}: {error}")
                    return {'success': False, 'error': error}
        except Exception as e:
            logger.error(f"Error interrupting order strategy: {e}")
            return {'success': False, 'error': str(e)}
    
    async def liquidate_position(self, account_id: int, contract_id: int, admin: bool = False) -> Optional[Dict[str, Any]]:
        """
        Liquidate a position and cancel all related orders for a contract.
        This is Tradovate's official "exit at market and cancel orders" endpoint.
        
        Args:
            account_id: The account ID
            contract_id: The contract ID (not symbol - must resolve symbol to contractId)
            admin: Whether this is an admin action (usually False)
        
        Returns:
            Dict with success flag and order result, or None on error
        """
        try:
            async with self.session.post(
                f"{self.base_url}/order/liquidateposition",
                json={
                    "accountId": account_id,
                    "contractId": contract_id,
                    "admin": admin
                },
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Liquidated position for contract {contract_id} (account {account_id})")
                    return {'success': True, 'data': data}
                else:
                    try:
                        error = await response.json()
                    except Exception:
                        error = await response.text()
                    logger.error(f"Failed to liquidate position: {error}")
                    return {'success': False, 'error': error}
        except Exception as e:
            logger.error(f"Error liquidating position: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_market_order(self, account_spec: str, symbol: str, side: str, quantity: int, account_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a market order"""
        order = {
            "accountSpec": account_spec,
            "orderType": "Market",
            "action": side,
            "symbol": symbol,
            "orderQty": int(quantity),
            "timeInForce": "Day",
            "isAutomated": True
        }
        if account_id is not None:
            order["accountId"] = account_id
        return order
    
    def create_limit_order(self, account_spec: str, symbol: str, side: str, quantity: int, price: float, account_id: Optional[int] = None, cl_ord_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a limit order with optional client order ID for tagging"""
        order = {
            "accountSpec": account_spec,
            "orderType": "Limit",
            "action": side,
            "symbol": symbol,
            "orderQty": int(quantity),
            "price": float(price),
            "timeInForce": "Day",
            "isAutomated": True
        }
        if account_id is not None:
            order["accountId"] = account_id
        if cl_ord_id:
            order["clOrdId"] = cl_ord_id  # Client order ID for tagging/reconciliation
        return order
    
    def create_stop_order(self, account_spec: str, symbol: str, side: str, quantity: int, stop_price: float, account_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a stop order"""
        order = {
            "accountSpec": account_spec,
            "orderType": "Stop",
            "action": side,
            "symbol": symbol,
            "orderQty": int(quantity),
            "stopPrice": float(stop_price),
            "timeInForce": "Day",
            "isAutomated": True
        }
        if account_id is not None:
            order["accountId"] = account_id
        return order

    def create_trailing_stop_order(self, account_spec: str, symbol: str, side: str, quantity: int, offset: float, account_id: Optional[int] = None, initial_stop_price: float = None) -> Dict[str, Any]:
        """
        Create a trailing stop order.
        
        Args:
            account_spec: Account specification
            symbol: Trading symbol
            side: 'Buy' or 'Sell' (exit side)
            quantity: Number of contracts
            offset: Trail offset in price (not ticks)
            account_id: Optional account ID
            initial_stop_price: Initial stop price (required by Tradovate)
        """
        order = {
            "accountSpec": account_spec,
            "orderType": "TrailingStop",
            "action": side,
            "symbol": symbol,
            "orderQty": int(quantity),
            "pegDifference": float(offset),
            "timeInForce": "Day",
            "isAutomated": True
        }
        
        # Tradovate requires stopPrice for trailing stops
        if initial_stop_price is not None:
            order["stopPrice"] = float(initial_stop_price)
        
        if account_id is not None:
            order["accountId"] = account_id
        return order
    
    async def place_bracket_order(self, account_id: int, account_spec: str, symbol: str, 
                                   entry_side: str, quantity: int,
                                   profit_target_ticks: int = None, 
                                   stop_loss_ticks: int = None,
                                   trailing_stop: bool = False) -> Optional[Dict[str, Any]]:
        """
        Place a market entry order with bracket (TP/SL) as an order strategy.
        This is the CORRECT way to place OCO brackets in Tradovate.
        
        IMPORTANT: Tradovate bracket API expects profitTarget/stopLoss in POINTS,
        not ticks! We convert from ticks to points here.
        
        Args:
            account_id: The Tradovate account ID
            account_spec: The account name/spec  
            symbol: The trading symbol
            entry_side: 'Buy' or 'Sell' for the entry
            quantity: Number of contracts
            profit_target_ticks: Profit target in ticks (we convert to points)
            stop_loss_ticks: Stop loss in ticks (we convert to points)
            trailing_stop: Whether to use trailing stop instead of fixed stop
        
        Returns:
            Dict with order strategy result
        """
        try:
            # Get tick size for this symbol to convert ticks to points
            # Tradovate bracket API wants POINTS, not ticks!
            symbol_root = ''.join(c for c in symbol if c.isalpha())[:3].upper()
            tick_sizes = {
                'MNQ': 0.25, 'NQ': 0.25, 'MES': 0.25, 'ES': 0.25,
                'M2K': 0.1, 'RTY': 0.1, 'MYM': 1.0, 'YM': 1.0,
                'CL': 0.01, 'MCL': 0.01, 'GC': 0.1, 'MGC': 0.1
            }
            tick_size = tick_sizes.get(symbol_root, 0.25)
            
            # Convert ticks to points for Tradovate API
            # e.g., 5 ticks * 0.25 tick_size = 1.25 points
            profit_target_points = profit_target_ticks * tick_size if profit_target_ticks else None
            stop_loss_points = stop_loss_ticks * tick_size if stop_loss_ticks else None
            
            logger.info(f"📊 Converting: {profit_target_ticks} ticks → {profit_target_points} points (tick_size={tick_size})")
            
            # Build bracket params - Tradovate wants POINTS
            bracket = {
                "qty": int(quantity),
                "profitTarget": float(profit_target_points) if profit_target_points else None,
                "stopLoss": -abs(float(stop_loss_points)) if stop_loss_points else None,  # Negative for loss
                "trailingStop": trailing_stop
            }
            
            logger.info(f"📊 Bracket params: profitTarget={bracket['profitTarget']} points, stopLoss={bracket['stopLoss']} points")
            
            # Entry order params
            params = {
                "entryVersion": {
                    "orderQty": int(quantity),
                    "orderType": "Market",
                    "timeInForce": "Day"
                },
                "brackets": [bracket]
            }
            
            # Build WebSocket message payload (REQUIRED per documentation)
            # Format: {"n": "orderStrategy/startOrderStrategy", "o": {...}}
            # Per Tradovate documentation: accountId, symbol, orderStrategyTypeId, action, params
            strategy_payload = {
                "accountId": account_id,
                "symbol": symbol,
                "orderStrategyTypeId": 2,  # 2 = Bracket strategy type
                "action": entry_side,
                "params": json.dumps(params)  # Must be stringified JSON
            }
            # Note: accountSpec not needed for WebSocket strategy messages per documentation
            
            logger.info(f"📊 Placing bracket order strategy via WebSocket: entry={entry_side}, qty={quantity}, TP={profit_target_ticks} ticks, SL={stop_loss_ticks} ticks")
            logger.debug(f"Strategy payload: {strategy_payload}")
            
            # Send via WebSocket (REQUIRED per Tradovate documentation)
            ws_response = await self._send_websocket_message(
                "orderStrategy/startOrderStrategy",
                strategy_payload
            )
            
            if ws_response:
                if isinstance(ws_response, dict):
                    if ws_response.get('ok') or ws_response.get('id'):
                        strategy_id = ws_response.get('id') or ws_response.get('orderStrategyId') or ws_response.get('data', {}).get('id')
                        logger.info(f"✅ Bracket order strategy created via WebSocket: ID={strategy_id}")
                        return {
                            'success': True,
                            'data': ws_response,
                            'strategy_id': strategy_id,
                            'orderId': ws_response.get('orderId')
                        }
                    else:
                        error_msg = ws_response.get('errorText') or ws_response.get('error') or str(ws_response)
                        logger.error(f"❌ Bracket strategy failed: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg
                        }
                else:
                    logger.error(f"❌ Unexpected WebSocket response format: {ws_response}")
                    return {
                        'success': False,
                        'error': f'Unexpected response format: {ws_response}'
                    }
            else:
                logger.error("❌ Failed to send bracket strategy via WebSocket (no response)")
                return {
                    'success': False,
                    'error': 'WebSocket connection failed or no response received'
                }
                    
        except Exception as e:
            logger.error(f"Error creating bracket order strategy: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def place_exit_oco(self, account_id: int, account_spec: str, symbol: str,
                             exit_side: str, quantity: int,
                             take_profit_price: float = None,
                             stop_loss_price: float = None) -> Optional[Dict[str, Any]]:
        """
        Place OCO exit orders (TP + SL) for an existing position.
        
        For exits on existing positions, we create an OCO order strategy
        with limit (TP) and stop (SL) orders.
        
        Args:
            account_id: The Tradovate account ID
            account_spec: The account name/spec
            symbol: The trading symbol
            exit_side: 'Sell' for long exit, 'Buy' for short exit
            quantity: Number of contracts
            take_profit_price: Absolute price for take profit limit order
            stop_loss_price: Absolute price for stop loss order
        """
        try:
            # For OCO exit orders, we use orderStrategyTypeId 1 (OCO)
            # with two orders: a limit for TP and a stop for SL
            
            # Build the OCO with two legs
            params = {
                "entryVersion": {
                    "orderQty": int(quantity),
                    "orderType": "Limit",
                    "price": float(take_profit_price) if take_profit_price else 0,
                    "timeInForce": "GTC"
                },
                "closeVersion": {
                    "orderQty": int(quantity),
                    "orderType": "Stop", 
                    "stopPrice": float(stop_loss_price) if stop_loss_price else 0,
                    "timeInForce": "GTC"
                }
            }
            
            # Build WebSocket message payload (REQUIRED per documentation)
            # Per Tradovate documentation: accountId, symbol, orderStrategyTypeId, action, params
            strategy_payload = {
                "accountId": account_id,
                "symbol": symbol,
                "orderStrategyTypeId": 1,  # 1 = OCO type
                "action": exit_side,
                "params": json.dumps(params)  # Must be stringified JSON
            }
            # Note: accountSpec not needed for WebSocket strategy messages
            
            logger.info(f"📊 Placing OCO exit via WebSocket: {exit_side} {quantity} {symbol}, TP={take_profit_price}, SL={stop_loss_price}")
            
            # Send via WebSocket (REQUIRED per Tradovate documentation)
            ws_response = await self._send_websocket_message(
                "orderStrategy/startOrderStrategy",
                strategy_payload
            )
            
            if ws_response:
                if isinstance(ws_response, dict):
                    if ws_response.get('ok') or ws_response.get('id'):
                        strategy_id = ws_response.get('id') or ws_response.get('orderStrategyId') or ws_response.get('data', {}).get('id')
                        logger.info(f"✅ OCO exit strategy created via WebSocket: ID={strategy_id}")
                        return {
                            'success': True,
                            'data': ws_response,
                            'strategy_id': strategy_id
                        }
                    else:
                        error_msg = ws_response.get('errorText') or ws_response.get('error') or str(ws_response)
                        logger.warning(f"⚠️ OCO strategy returned error: {error_msg}")
                        logger.info(f"📊 Falling back to individual TP/SL orders...")
                        # Fallback to placing individual orders
                        return await self._place_individual_exit_orders(
                            account_id, account_spec, symbol, exit_side, quantity,
                            take_profit_price, stop_loss_price
                        )
                else:
                    logger.warning(f"⚠️ Unexpected WebSocket response format: {ws_response}")
                    logger.info(f"📊 Falling back to individual TP/SL orders...")
                    return await self._place_individual_exit_orders(
                        account_id, account_spec, symbol, exit_side, quantity,
                        take_profit_price, stop_loss_price
                    )
            else:
                logger.warning("⚠️ Failed to send OCO strategy via WebSocket, falling back to individual orders")
                # Fallback to placing individual orders
                return await self._place_individual_exit_orders(
                    account_id, account_spec, symbol, exit_side, quantity,
                    take_profit_price, stop_loss_price
                )
                    
        except Exception as e:
            logger.error(f"Error creating OCO exit: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}
    
    async def _place_individual_exit_orders(self, account_id: int, account_spec: str, symbol: str,
                                            exit_side: str, quantity: int,
                                            take_profit_price: float = None,
                                            stop_loss_price: float = None) -> Optional[Dict[str, Any]]:
        """
        Fallback: Place TP and SL as individual orders with custom OCO monitoring.
        The server will monitor these orders and cancel the partner when one fills.
        """
        results = {'success': False, 'tp_order': None, 'sl_order': None, 'tp_order_id': None, 'sl_order_id': None}
        
        try:
            tp_order_id = None
            sl_order_id = None
            
            if take_profit_price:
                tp_data = self.create_limit_order(account_spec, symbol, exit_side, quantity, take_profit_price, account_id)
                tp_result = await self.place_order(tp_data)
                results['tp_order'] = tp_result
                if tp_result and tp_result.get('success'):
                    results['success'] = True
                    tp_order_id = tp_result.get('orderId') or tp_result.get('data', {}).get('orderId')
                    results['tp_order_id'] = tp_order_id
                    logger.info(f"✅ TP order placed: ID={tp_order_id}, Price={take_profit_price}")
            
            if stop_loss_price:
                sl_data = self.create_stop_order(account_spec, symbol, exit_side, quantity, stop_loss_price, account_id)
                sl_result = await self.place_order(sl_data)
                results['sl_order'] = sl_result
                if sl_result and sl_result.get('success'):
                    results['success'] = True
                    sl_order_id = sl_result.get('orderId') or sl_result.get('data', {}).get('orderId')
                    results['sl_order_id'] = sl_order_id
                    logger.info(f"✅ SL order placed: ID={sl_order_id}, Price={stop_loss_price}")
            
            # Register the pair for custom OCO monitoring
            if tp_order_id and sl_order_id:
                results['oco_registered'] = True
                logger.info(f"🔗 TP/SL pair will be monitored for OCO behavior: TP={tp_order_id} <-> SL={sl_order_id}")
            elif results['success']:
                logger.warning("⚠️ Only one side of bracket placed - no OCO monitoring")
                
            return results
            
        except Exception as e:
            logger.error(f"Error placing individual exit orders: {e}")
            return results
    
    async def place_dca_strategy(self, account_id: int, account_spec: str, symbol: str,
                                 entry_side: str, initial_qty: int,
                                 scale_levels: List[Dict[str, Any]] = None,
                                 tp_ticks: int = None,
                                 sl_ticks: int = None) -> Optional[Dict[str, Any]]:
        """
        Place a DCA (Dollar Cost Averaging) order strategy using Tradovate's Order Strategy Engine.
        
        This is the CORRECT way to implement DCA on Tradovate - all entries and exits
        are managed atomically by the broker.
        
        Args:
            account_id: The Tradovate account ID
            account_spec: The account name/spec
            symbol: The trading symbol (e.g., "MESM5")
            entry_side: 'Buy' or 'Sell' for the entry direction
            initial_qty: Initial entry quantity
            scale_levels: List of DCA scale-in levels, each with:
                - 'offset': Price offset in ticks (negative = against position)
                - 'qty': Quantity to add at this level
            tp_ticks: Take profit offset in ticks from average price
            sl_ticks: Stop loss offset in ticks from average price (negative)
        
        Returns:
            Dict with strategy result including strategy_id
        """
        try:
            # Get tick size for this symbol to convert ticks to points
            symbol_root = ''.join(c for c in symbol if c.isalpha())[:3].upper()
            tick_sizes = {
                'MNQ': 0.25, 'NQ': 0.25, 'MES': 0.25, 'ES': 0.25,
                'M2K': 0.1, 'RTY': 0.1, 'MYM': 1.0, 'YM': 1.0,
                'CL': 0.01, 'MCL': 0.01, 'GC': 0.1, 'MGC': 0.1,
                'SI': 0.005, 'NG': 0.001, 'ZB': 0.03125, 'ZN': 0.015625,
                '6E': 0.0001
            }
            tick_size = tick_sizes.get(symbol_root, 0.25)
            
            # Build entry version
            entry_version = {
                "orderType": "Market",
                "orderQty": int(initial_qty)
            }
            
            # Build scale array (DCA ladder)
            # Offsets should be in points (convert from ticks)
            # Negative offsets = price moves against position (for DCA scale-ins)
            scale = []
            if scale_levels:
                for level in scale_levels:
                    offset_ticks = level.get('offset', 0)
                    scale_qty = level.get('qty', 1)
                    # Convert ticks to points (same as bracket orders)
                    # Offset is negative when price moves against position (for DCA)
                    offset_points = float(offset_ticks * tick_size)
                    scale.append({
                        "offset": offset_points,  # Negative = against position (DCA scale-in)
                        "qty": int(scale_qty)
                    })
            
            # Build exit parameters
            # avgPriceOffset: TP offset from average price (positive for LONG, negative for SHORT)
            # stopLoss: Stop loss offset from entry (negative)
            exit_params = {}
            if tp_ticks is not None:
                # For LONG: TP = avg + offset (positive)
                # For SHORT: TP = avg - offset (negative)
                # The guide shows avgPriceOffset as a single value, broker handles direction
                exit_params["avgPriceOffset"] = float(tp_ticks * tick_size)  # Convert to points
            
            if sl_ticks is not None:
                # Stop loss is always negative (loss direction)
                exit_params["stopLoss"] = -abs(float(sl_ticks * tick_size))  # Convert to points, make negative
            
            # Build params JSON (must be stringified per Tradovate spec)
            params_dict = {
                "entryVersion": entry_version
            }
            
            if scale:
                params_dict["scale"] = scale
            
            if exit_params:
                params_dict["exit"] = exit_params
            
            params_json = json.dumps(params_dict)
            
            # Build strategy request
            # Per DCA guide: orderStrategyTypeId 2 is for bracket strategies
            # We'll use 2 for DCA as well (it's a coordinated entry/exit strategy)
            # Build WebSocket message payload per DCA guide format
            # Format: {"n": "orderStrategy/startOrderStrategy", "o": {...}}
            # Per DCA guide example: accountId, symbol, orderStrategyTypeId, action, params
            strategy_payload = {
                "accountId": account_id,
                "symbol": symbol,
                "orderStrategyTypeId": 2,  # Bracket/Strategy type
                "action": entry_side,
                "params": params_json  # Must be stringified JSON
            }
            # Note: accountSpec not needed for WebSocket strategy messages per guide
            
            logger.info(f"📊 Placing DCA strategy via WebSocket: {entry_side} {initial_qty} {symbol}")
            logger.info(f"   Scale levels: {len(scale)}")
            logger.info(f"   TP: {tp_ticks} ticks, SL: {sl_ticks} ticks")
            logger.debug(f"   Params: {params_json}")
            
            # Send via WebSocket (REQUIRED per DCA guide)
            ws_response = await self._send_websocket_message(
                "orderStrategy/startOrderStrategy",
                strategy_payload
            )
            
            if ws_response:
                # Check response format - Tradovate WebSocket responses vary
                # Could be {"ok": true, "data": {...}} or {"id": ..., ...}
                if isinstance(ws_response, dict):
                    if ws_response.get('ok') or ws_response.get('id'):
                        strategy_id = ws_response.get('id') or ws_response.get('orderStrategyId') or ws_response.get('data', {}).get('id')
                        logger.info(f"✅ DCA strategy created via WebSocket: ID={strategy_id}")
                        return {
                            'success': True,
                            'data': ws_response,
                            'strategy_id': strategy_id,
                            'orderId': ws_response.get('orderId')
                        }
                    else:
                        error_msg = ws_response.get('errorText') or ws_response.get('error') or str(ws_response)
                        logger.error(f"❌ DCA strategy failed: {error_msg}")
                        return {
                            'success': False,
                            'error': error_msg
                        }
                else:
                    logger.error(f"❌ Unexpected WebSocket response format: {ws_response}")
                    return {
                        'success': False,
                        'error': f'Unexpected response format: {ws_response}'
                    }
            else:
                logger.error("❌ Failed to send DCA strategy via WebSocket (no response)")
                return {
                    'success': False,
                    'error': 'WebSocket connection failed or no response received'
                }
                    
        except Exception as e:
            logger.error(f"Error creating DCA strategy: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}


class TradovateManager:
    """High-level manager for Tradovate operations"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.active_connections = {}
    
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    async def test_connection(self, username: str, password: str, client_id: str = None, client_secret: str = None) -> Dict[str, Any]:
        """Test Tradovate connection and return account info"""
        try:
            async with TradovateIntegration(demo=True) as tradovate:
                # Test login
                if not await tradovate.login_with_credentials(username, password, client_id, client_secret):
                    return {
                        "success": False,
                        "error": "Login failed. Please check your credentials and ensure you have Client ID and Secret."
                    }
                
                # Get accounts
                accounts = await tradovate.get_accounts()
                if not accounts:
                    return {
                        "success": False,
                        "error": "No accounts found for this user."
                    }
                
                # Get subaccounts for each account
                all_subaccounts = []
                for account in accounts:
                    subaccounts = await tradovate.get_subaccounts(account.get("id"))
                    for sub in subaccounts:
                        sub["parent_account"] = account.get("name", "Unknown")
                    all_subaccounts.extend(subaccounts)
                
                return {
                    "success": True,
                    "message": "Connection successful!",
                    "accounts": accounts,
                    "subaccounts": all_subaccounts,
                    "total_accounts": len(accounts),
                    "total_subaccounts": len(all_subaccounts)
                }
                
        except Exception as e:
            logger.error(f"Connection test error: {e}")
            return {
                "success": False,
                "error": f"Connection test failed: {str(e)}"
            }
    
    async def execute_trade(self, account_id: str, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a trade using the signal data"""
        try:
            # Get account credentials from database
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT username, password FROM accounts 
                WHERE id = ? AND enabled = 1
            """, (account_id,))
            
            account = cursor.fetchone()
            conn.close()
            
            if not account:
                return {
                    "success": False,
                    "error": "Account not found or disabled"
                }
            
            username, password = account
            
            async with TradovateIntegration(demo=True) as tradovate:
                # Login
                if not await tradovate.login_with_credentials(username, password):
                    return {
                        "success": False,
                        "error": "Failed to authenticate with Tradovate"
                    }
                
                # Create order based on signal
                symbol = signal.get("symbol", "ES")
                action = signal.get("action", "buy")
                quantity = signal.get("quantity", 1)
                price = signal.get("price")
                
                # Convert action to Tradovate format
                side = "Buy" if action.lower() in ["buy", "long"] else "Sell"
                
                # Create order
                if price and price > 0:
                    order_data = tradovate.create_limit_order(account_id, symbol, side, quantity, price)
                else:
                    order_data = tradovate.create_market_order(account_id, symbol, side, quantity)
                
                # Place order
                result = await tradovate.place_order(order_data)
                
                if result:
                    return {
                        "success": True,
                        "message": f"Trade executed successfully",
                        "order_id": result.get("orderId"),
                        "signal": signal
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to place order"
                    }
                    
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return {
                "success": False,
                "error": f"Trade execution failed: {str(e)}"
            }
    
    async def get_account_status(self, account_id: str) -> Dict[str, Any]:
        """Get current status of an account"""
        try:
            # Get account credentials
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT username, password FROM accounts 
                WHERE id = ? AND enabled = 1
            """, (account_id,))
            
            account = cursor.fetchone()
            conn.close()
            
            if not account:
                return {
                    "success": False,
                    "error": "Account not found or disabled"
                }
            
            username, password = account
            
            async with TradovateIntegration(demo=True) as tradovate:
                # Login
                if not await tradovate.login_with_credentials(username, password):
                    return {
                        "success": False,
                        "error": "Failed to authenticate with Tradovate"
                    }
                
                # Get account info
                account_info = await tradovate.get_account_info(account_id)
                positions = await tradovate.get_positions(account_id)
                orders = await tradovate.get_orders(account_id)
                
                return {
                    "success": True,
                    "account_info": account_info,
                    "positions": positions,
                    "orders": orders,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Account status error: {e}")
            return {
                "success": False,
                "error": f"Failed to get account status: {str(e)}"
            }

# Example usage
async def main():
    """Example usage of Tradovate integration"""
    manager = TradovateManager()
    
    # Test connection
    result = await manager.test_connection("your_username", "your_password")
    print(json.dumps(result, indent=2))
    
    # Execute a trade
    signal = {
        "symbol": "ES",
        "action": "buy",
        "quantity": 1,
        "price": 150.25
    }
    
    trade_result = await manager.execute_trade("account_id", signal)
    print(json.dumps(trade_result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
