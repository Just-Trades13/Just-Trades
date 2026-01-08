#!/usr/bin/env python3
"""
ProjectX/TopstepX Integration for Just.Trade
Based on ProjectX Gateway API documentation
https://gateway.docs.projectx.com/

This integration supports TopstepX, Apex, and other ProjectX-powered prop firms.

API Endpoints:
- Demo: https://gateway-api-demo.s2f.projectx.com
- Live: https://gateway-api.s2f.projectx.com

WebSocket (SignalR):
- User Hub (demo): https://gateway-rtc-demo.s2f.projectx.com/hubs/user
- Market Hub (demo): https://gateway-rtc-demo.s2f.projectx.com/hubs/market
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ProjectXIntegration:
    """
    ProjectX API Integration for TopstepX and other ProjectX-powered brokers.
    
    IMPORTANT: Third-party apps MUST use API Key authentication!
    - Password auth is ONLY for platform/website login (Trade Manager is BUILT-IN)
    - API subscription ($14.50/mo) is REQUIRED for external apps like Just.Trades
    - Different prop firms use different API endpoints
    
    Endpoints by Firm:
    - TopstepX: https://api.topstepx.com
    - Other ProjectX firms: https://gateway-api-demo.s2f.projectx.com (demo)
                           https://gateway-api.s2f.projectx.com (live)
    
    Token valid for 24 hours, refresh via /api/Auth/validate
    """
    
    # Order Types (per ProjectX API)
    ORDER_TYPE_LIMIT = 1
    ORDER_TYPE_MARKET = 2
    ORDER_TYPE_STOP = 3
    ORDER_TYPE_STOP_LIMIT = 4
    
    # Order Sides (per ProjectX API)
    SIDE_BUY = 0
    SIDE_SELL = 1
    
    # Order Status
    STATUS_PENDING = 0
    STATUS_WORKING = 1
    STATUS_FILLED = 2
    STATUS_CANCELLED = 3
    STATUS_REJECTED = 4
    
    # Prop firm specific endpoints
    FIRM_ENDPOINTS = {
        'topstep': {
            'demo': 'https://api.topstepx.com',
            'live': 'https://api.topstepx.com',
            'user_api': 'https://api.topstepx.com',  # Password auth endpoint
            'ws_user': 'wss://api.topstepx.com/hubs/user',
            'ws_market': 'wss://api.topstepx.com/hubs/market',
        },
        'default': {
            'demo': 'https://gateway-api-demo.s2f.projectx.com',
            'live': 'https://gateway-api.s2f.projectx.com',
            'user_api_demo': 'https://userapi-demo.s2f.projectx.com',  # Password auth endpoint
            'user_api_live': 'https://userapi.s2f.projectx.com',
            'ws_user_demo': 'https://gateway-rtc-demo.s2f.projectx.com/hubs/user',
            'ws_user_live': 'https://gateway-rtc.s2f.projectx.com/hubs/user',
            'ws_market_demo': 'https://gateway-rtc-demo.s2f.projectx.com/hubs/market',
            'ws_market_live': 'https://gateway-rtc.s2f.projectx.com/hubs/market',
        }
    }
    
    def __init__(self, demo: bool = True, prop_firm: str = 'default'):
        """
        Initialize ProjectX integration.
        
        Args:
            demo: If True, use demo endpoints. If False, use live endpoints.
            prop_firm: The prop firm identifier (e.g., 'topstep', 'alpha', etc.)
        """
        self.is_demo = demo
        self.prop_firm = prop_firm.lower() if prop_firm else 'default'
        
        # Get correct endpoints for this firm
        endpoints = self.FIRM_ENDPOINTS.get(self.prop_firm, self.FIRM_ENDPOINTS['default'])
        
        if self.prop_firm == 'topstep':
            # TopstepX has unified endpoints
            self.base_url = endpoints['demo']  # Same for demo/live
            self.user_api_url = endpoints.get('user_api', endpoints['demo'])
            self.ws_user_hub = endpoints['ws_user']
            self.ws_market_hub = endpoints['ws_market']
        else:
            # Other ProjectX firms use standard endpoints
            env = 'demo' if demo else 'live'
            self.base_url = endpoints[env]
            self.user_api_url = endpoints.get(f'user_api_{env}', 'https://userapi-demo.s2f.projectx.com')
            self.ws_user_hub = endpoints.get(f'ws_user_{env}', endpoints.get('ws_user_demo'))
            self.ws_market_hub = endpoints.get(f'ws_market_{env}', endpoints.get('ws_market_demo'))
        
        logger.info(f"🔧 ProjectX initialized for {prop_firm}, demo={demo}")
        logger.info(f"   Base URL: {self.base_url}")
        logger.info(f"   User API URL: {self.user_api_url}")
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.session_token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self.username: Optional[str] = None
        self.accounts: List[Dict[str, Any]] = []
        self.contracts_cache: Dict[str, Dict[str, Any]] = {}
        self.auth_method: Optional[str] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authorization token."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.session_token:
            headers["Authorization"] = f"Bearer {self.session_token}"
        return headers
    
    async def login_with_password(self, username: str, password: str) -> dict:
        """
        Authenticate with ProjectX using username and password (FREE method!).
        
        This is how Trade Manager authenticates - no API subscription required.
        Uses your TopstepX/prop firm credentials directly.
        
        Args:
            username: Your TopstepX/prop firm username
            password: Your TopstepX/prop firm password
        
        Returns:
            dict with 'success' and 'error' keys for detailed diagnostics
        """
        try:
            logger.info(f"🔐 Attempting ProjectX login (password method)")
            logger.info(f"   Username: {username}")
            logger.info(f"   Endpoint: {self.user_api_url}/login")
            
            login_data = {
                "username": username,
                "password": password
            }
            
            # Password auth uses userapi endpoint, NOT gateway-api
            # Note: userapi-demo works for both demo AND live/funded accounts
            # The "demo" in the URL refers to the API environment, not the account type
            endpoints_to_try = [
                "https://userapi-demo.s2f.projectx.com/login",  # Primary - works for all accounts
                "https://userapi.s2f.projectx.com/login",  # Live API (may not always be available)
                f"{self.user_api_url}/login",  # Firm-specific if different
            ]
            
            last_error = "No endpoints succeeded"
            
            for endpoint in endpoints_to_try:
                try:
                    logger.info(f"   Trying endpoint: {endpoint}")
                    
                    async with self.session.post(
                        endpoint,
                        json=login_data,
                        headers={"Content-Type": "application/json", "Accept": "application/json"}
                    ) as response:
                        response_text = await response.text()
                        logger.info(f"   Response status: {response.status}")
                        logger.info(f"   Response body: {response_text[:500]}")
                        
                        if response.status == 200:
                            try:
                                data = json.loads(response_text)
                            except:
                                data = {"raw": response_text}
                            
                            # Check for success - response format may vary
                            token = data.get("token") or data.get("accessToken") or data.get("sessionToken")
                            error_code = data.get("errorCode", 0)
                            success = data.get("success", True) if token else False
                            
                            if token and error_code == 0 and success != False:
                                self.session_token = token
                                self.username = username
                                self.auth_method = 'password'
                                self.token_expires = datetime.now() + timedelta(hours=24)
                                
                                logger.info(f"✅ Successfully logged in to ProjectX as {username}")
                                logger.info(f"   Token (first 20 chars): {token[:20]}...")
                                return {"success": True}
                            else:
                                error_msg = data.get("errorMessage") or data.get("message") or data.get("error") or "Auth failed"
                                last_error = f"Endpoint {endpoint}: {error_msg}"
                                logger.warning(f"   Auth response error: {error_msg}")
                        elif response.status == 401:
                            last_error = f"Invalid credentials (HTTP 401) at {endpoint}"
                        elif response.status == 404:
                            last_error = f"Endpoint not found (HTTP 404): {endpoint}"
                            continue  # Try next endpoint
                        else:
                            last_error = f"HTTP {response.status} at {endpoint}: {response_text[:200]}"
                            
                except Exception as endpoint_error:
                    last_error = f"Endpoint {endpoint} error: {str(endpoint_error)}"
                    logger.warning(f"   Endpoint error: {endpoint_error}")
                    continue
            
            logger.error(f"❌ All password auth endpoints failed. Last error: {last_error}")
            return {"success": False, "error": last_error}
                    
        except Exception as e:
            logger.error(f"ProjectX password login exception: {e}")
            return {"success": False, "error": f"Exception: {str(e)}"}
    
    async def login_with_api_key(self, username: str, api_key: str) -> dict:
        """
        Authenticate with ProjectX using username and API key.
        
        This is the ONLY method for third-party apps like Just.Trades.
        Requires API subscription ($14.50/mo from ProjectX Dashboard).
        
        Args:
            username: Your ProjectX Dashboard username (NOT your prop firm email!)
            api_key: API key from ProjectX Dashboard (Settings → API → API Key)
        
        Returns:
            dict with 'success' and 'error' keys for detailed diagnostics
        """
        try:
            logger.info(f"🔑 Attempting ProjectX login (API key method)")
            logger.info(f"   Prop firm: {self.prop_firm}")
            logger.info(f"   Username: {username}")
            logger.info(f"   API Key (first 10 chars): {api_key[:10] if len(api_key) >= 10 else api_key}...")
            logger.info(f"   Base URL: {self.base_url}")
            
            login_data = {
                "userName": username,
                "apiKey": api_key
            }
            
            # Try multiple endpoint variations
            endpoints_to_try = [
                f"{self.base_url}/api/Auth/loginKey",
                f"{self.base_url}/Auth/loginKey",
                f"{self.base_url}/v1/auth/loginKey",
            ]
            
            # TopstepX might use different endpoint structure
            if self.prop_firm == 'topstep':
                endpoints_to_try = [
                    f"{self.base_url}/api/Auth/loginKey",
                    f"{self.base_url}/auth/loginKey",
                    "https://api.topstepx.com/api/Auth/loginKey",
                ]
            
            last_error = "No endpoints succeeded"
            last_response = ""
            
            for endpoint in endpoints_to_try:
                try:
                    logger.info(f"   Trying endpoint: {endpoint}")
                    
                    async with self.session.post(
                        endpoint,
                        json=login_data,
                        headers={"Content-Type": "application/json", "Accept": "application/json"}
                    ) as response:
                        response_text = await response.text()
                        logger.info(f"   Response status: {response.status}")
                        logger.info(f"   Response body: {response_text[:500]}")
                        last_response = response_text
                        
                        if response.status == 200:
                            try:
                                data = json.loads(response_text)
                            except:
                                last_error = f"Invalid JSON: {response_text[:100]}"
                                continue
                            
                            # Check for token - different response formats
                            token = data.get("token") or data.get("accessToken") or data.get("sessionToken")
                            error_code = data.get("errorCode", 0)
                            success_flag = data.get("success")
                            
                            # Handle explicit success=false
                            if success_flag == False:
                                error_msg = data.get("errorMessage") or data.get("message") or "Auth rejected"
                                last_error = f"API rejected: {error_msg}"
                                continue
                            
                            if token and error_code == 0:
                                self.session_token = token
                                self.username = username
                                self.auth_method = 'apikey'
                                self.token_expires = datetime.now() + timedelta(hours=24)
                                
                                logger.info(f"✅ Successfully logged in to ProjectX (API key method)")
                                logger.info(f"   Token (first 20 chars): {token[:20]}...")
                                return {"success": True, "endpoint_used": endpoint}
                            else:
                                error_msg = data.get("errorMessage") or data.get("message") or data.get("error") or f"errorCode={error_code}"
                                last_error = f"Auth failed: {error_msg}"
                                
                        elif response.status == 401:
                            last_error = "Invalid API key or username (HTTP 401)"
                        elif response.status == 403:
                            last_error = "API access forbidden (HTTP 403) - subscription may not be active or account not linked"
                        elif response.status == 404:
                            last_error = f"Endpoint not found (HTTP 404): {endpoint}"
                            continue  # Try next endpoint
                        else:
                            last_error = f"HTTP {response.status}: {response_text[:100]}"
                            
                except Exception as endpoint_error:
                    last_error = f"Connection error to {endpoint}: {str(endpoint_error)}"
                    logger.warning(f"   Endpoint error: {endpoint_error}")
                    continue
            
            # All endpoints failed
            logger.error(f"❌ All API key auth endpoints failed")
            logger.error(f"   Last error: {last_error}")
            logger.error(f"   Last response: {last_response[:200]}")
            
            # Provide helpful error message
            help_msg = ""
            if "401" in last_error:
                help_msg = "\n\n⚠️ Common fixes:\n1. Make sure you're using your ProjectX Dashboard username (NOT your prop firm email)\n2. Verify the API key was copied correctly\n3. Check that your prop firm account is LINKED in the ProjectX Dashboard"
            elif "403" in last_error:
                help_msg = "\n\n⚠️ Your API subscription may not be active, or your trading account isn't linked to the API subscription in the ProjectX Dashboard."
            
            return {"success": False, "error": last_error + help_msg, "last_response": last_response[:200]}
                    
        except Exception as e:
            logger.error(f"ProjectX API key login exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": f"Connection error: {str(e)}"}
    
    async def login(self, username: str, password: str = None, api_key: str = None) -> dict:
        """
        Authenticate with ProjectX.
        
        Two authentication methods available:
        1. Password auth (FREE) - Uses userapi /login endpoint
        2. API Key auth ($14.50/mo) - Uses gateway-api /loginKey endpoint
        
        Args:
            username: Your username (prop firm email for password, Dashboard username for API key)
            password: Your prop firm password (for FREE auth)
            api_key: API key from ProjectX Dashboard (for paid auth)
        
        Returns:
            dict with 'success', 'error', and 'method' keys
        """
        errors = []
        
        # Try password auth first (FREE method)
        if password:
            logger.info("🔐 Trying password authentication (FREE method)...")
            result = await self.login_with_password(username, password)
            if result.get("success"):
                return {"success": True, "method": "password"}
            errors.append(f"Password: {result.get('error', 'Failed')}")
            logger.warning(f"Password auth failed: {result.get('error')}")
        
        # Try API key auth as fallback
        if api_key:
            logger.info("🔑 Trying API key authentication...")
            result = await self.login_with_api_key(username, api_key)
            if result.get("success"):
                return {"success": True, "method": "apikey"}
            errors.append(f"API Key: {result.get('error', 'Failed')}")
        
        # Both failed or no credentials provided
        if not password and not api_key:
            return {"success": False, "error": "Please provide either password or API key"}
        
        error_summary = " | ".join(errors)
        return {"success": False, "error": error_summary}
    
    async def validate_session(self) -> bool:
        """
        Validate and renew the session token.
        Call this periodically to keep the session alive.
        
        Returns:
            True if session is valid, False otherwise
        """
        try:
            if not self.session_token:
                logger.warning("No session token to validate")
                return False
            
            async with self.session.post(
                f"{self.base_url}/api/Auth/validate",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        # Extend token expiry
                        self.token_expires = datetime.now() + timedelta(hours=24)
                        logger.info("✅ ProjectX session validated and renewed")
                        return True
                    else:
                        logger.warning(f"Session validation failed: {data.get('errorMessage')}")
                        return False
                else:
                    logger.warning(f"Session validation HTTP error: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Session validation exception: {e}")
            return False
    
    async def _ensure_valid_token(self) -> bool:
        """
        Ensure session token is valid, refresh if needed.
        
        Returns:
            True if token is valid, False otherwise
        """
        if not self.session_token:
            return False
        
        # Check if token expires within 1 hour
        if self.token_expires:
            time_until_expiry = (self.token_expires - datetime.now()).total_seconds()
            if time_until_expiry < 3600:  # Less than 1 hour
                logger.info(f"Token expires in {time_until_expiry:.0f} seconds, validating...")
                return await self.validate_session()
        
        return True
    
    async def get_accounts(self, only_active: bool = True) -> List[Dict[str, Any]]:
        """
        Get list of trading accounts.
        
        Args:
            only_active: If True, only return active accounts
        
        Returns:
            List of account dictionaries
        """
        try:
            await self._ensure_valid_token()
            
            async with self.session.post(
                f"{self.base_url}/api/Account/search",
                json={"onlyActiveAccounts": only_active},
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        accounts = data.get("accounts", [])
                        self.accounts = accounts
                        logger.info(f"Retrieved {len(accounts)} accounts from ProjectX")
                        for acc in accounts:
                            logger.info(f"   Account: {acc.get('id')} - {acc.get('name', 'Unknown')}")
                        return accounts
                    else:
                        logger.error(f"Failed to get accounts: {data.get('errorMessage')}")
                        return []
                else:
                    error_text = await response.text()
                    logger.error(f"Get accounts HTTP error: {response.status} - {error_text[:200]}")
                    return []
                    
        except Exception as e:
            logger.error(f"Get accounts exception: {e}")
            return []
    
    async def get_account_info(self, account_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific account.
        
        Args:
            account_id: The account ID
        
        Returns:
            Account info dictionary or None
        """
        try:
            await self._ensure_valid_token()
            
            async with self.session.get(
                f"{self.base_url}/api/Account/{account_id}",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        return data.get("account")
                    else:
                        logger.error(f"Failed to get account info: {data.get('errorMessage')}")
                        return None
                else:
                    logger.error(f"Get account info HTTP error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Get account info exception: {e}")
            return None
    
    async def get_available_contracts(self, live: bool = True) -> List[Dict[str, Any]]:
        """
        Get list of available tradeable contracts.
        
        Args:
            live: If True, get live contracts
        
        Returns:
            List of contract dictionaries
        """
        try:
            await self._ensure_valid_token()
            
            async with self.session.post(
                f"{self.base_url}/api/Contract/available",
                json={"live": live},
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        contracts = data.get("contracts", [])
                        # Cache contracts by symbol for quick lookup
                        for contract in contracts:
                            symbol = contract.get("name") or contract.get("symbol")
                            if symbol:
                                self.contracts_cache[symbol] = contract
                        logger.info(f"Retrieved {len(contracts)} available contracts")
                        return contracts
                    else:
                        logger.error(f"Failed to get contracts: {data.get('errorMessage')}")
                        return []
                else:
                    logger.error(f"Get contracts HTTP error: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Get contracts exception: {e}")
            return []
    
    async def get_contract_by_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get contract details by symbol.
        
        Args:
            symbol: Contract symbol (e.g., "MNQ", "ES")
        
        Returns:
            Contract dictionary or None
        """
        # Check cache first
        if symbol in self.contracts_cache:
            return self.contracts_cache[symbol]
        
        # Fetch contracts if cache is empty
        if not self.contracts_cache:
            await self.get_available_contracts()
        
        return self.contracts_cache.get(symbol)
    
    async def get_positions(self, account_id: int) -> List[Dict[str, Any]]:
        """
        Get current positions for an account.
        
        Args:
            account_id: The account ID
        
        Returns:
            List of position dictionaries
        """
        try:
            await self._ensure_valid_token()
            
            async with self.session.post(
                f"{self.base_url}/api/Position/search",
                json={"accountId": account_id},
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        positions = data.get("positions", [])
                        logger.info(f"Retrieved {len(positions)} positions for account {account_id}")
                        return positions
                    else:
                        logger.error(f"Failed to get positions: {data.get('errorMessage')}")
                        return []
                else:
                    logger.error(f"Get positions HTTP error: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Get positions exception: {e}")
            return []
    
    async def get_orders(self, account_id: int, include_filled: bool = False) -> List[Dict[str, Any]]:
        """
        Get orders for an account.
        
        Args:
            account_id: The account ID
            include_filled: If True, include filled/completed orders
        
        Returns:
            List of order dictionaries
        """
        try:
            await self._ensure_valid_token()
            
            search_params = {"accountId": account_id}
            if not include_filled:
                # Only get working orders (pending, working)
                search_params["statuses"] = [self.STATUS_PENDING, self.STATUS_WORKING]
            
            async with self.session.post(
                f"{self.base_url}/api/Order/search",
                json=search_params,
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        orders = data.get("orders", [])
                        logger.info(f"Retrieved {len(orders)} orders for account {account_id}")
                        return orders
                    else:
                        logger.error(f"Failed to get orders: {data.get('errorMessage')}")
                        return []
                else:
                    logger.error(f"Get orders HTTP error: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Get orders exception: {e}")
            return []
    
    async def place_order(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Place an order.
        
        Args:
            order_data: Order dictionary with:
                - accountId: int
                - contractId: str (e.g., "CON.F.US.MNQM5.M25")
                - type: int (1=Limit, 2=Market, 3=Stop, 4=StopLimit)
                - side: int (0=Buy, 1=Sell)
                - size: int (quantity)
                - price: float (for Limit/StopLimit orders)
                - stopPrice: float (for Stop/StopLimit orders)
        
        Returns:
            Order result dictionary or None
        """
        try:
            await self._ensure_valid_token()
            
            logger.info(f"📊 Placing ProjectX order: {order_data}")
            
            async with self.session.post(
                f"{self.base_url}/api/Order/place",
                json=order_data,
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        order_id = data.get("orderId")
                        logger.info(f"✅ Order placed successfully: ID={order_id}")
                        return {
                            "success": True,
                            "orderId": order_id,
                            "data": data
                        }
                    else:
                        error_msg = data.get("errorMessage") or "Unknown error"
                        logger.error(f"❌ Order placement failed: {error_msg}")
                        return {
                            "success": False,
                            "error": error_msg,
                            "data": data
                        }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Order HTTP error: {response.status} - {error_text[:200]}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status}: {error_text[:200]}"
                    }
                    
        except Exception as e:
            logger.error(f"Place order exception: {e}")
            return {"success": False, "error": str(e)}
    
    async def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: The order ID to cancel
        
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            await self._ensure_valid_token()
            
            logger.info(f"Cancelling ProjectX order: {order_id}")
            
            async with self.session.post(
                f"{self.base_url}/api/Order/cancel",
                json={"orderId": order_id},
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        logger.info(f"✅ Order {order_id} cancelled successfully")
                        return True
                    else:
                        logger.error(f"❌ Cancel order failed: {data.get('errorMessage')}")
                        return False
                else:
                    logger.error(f"Cancel order HTTP error: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Cancel order exception: {e}")
            return False
    
    async def modify_order(self, order_id: int, new_price: float = None, 
                          new_size: int = None, new_stop_price: float = None) -> Optional[Dict[str, Any]]:
        """
        Modify an existing order.
        
        Args:
            order_id: The order ID to modify
            new_price: New limit price
            new_size: New quantity
            new_stop_price: New stop price
        
        Returns:
            Modified order result or None
        """
        try:
            await self._ensure_valid_token()
            
            modify_data = {"orderId": order_id}
            if new_price is not None:
                modify_data["price"] = float(new_price)
            if new_size is not None:
                modify_data["size"] = int(new_size)
            if new_stop_price is not None:
                modify_data["stopPrice"] = float(new_stop_price)
            
            logger.info(f"Modifying ProjectX order {order_id}: {modify_data}")
            
            async with self.session.post(
                f"{self.base_url}/api/Order/modify",
                json=modify_data,
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        logger.info(f"✅ Order {order_id} modified successfully")
                        return {"success": True, "data": data}
                    else:
                        logger.error(f"❌ Modify order failed: {data.get('errorMessage')}")
                        return {"success": False, "error": data.get("errorMessage")}
                else:
                    logger.error(f"Modify order HTTP error: {response.status}")
                    return {"success": False, "error": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Modify order exception: {e}")
            return {"success": False, "error": str(e)}
    
    async def liquidate_position(self, account_id: int, contract_id: str) -> Optional[Dict[str, Any]]:
        """
        Liquidate (close) a position at market.
        
        Args:
            account_id: The account ID
            contract_id: The contract ID to liquidate
        
        Returns:
            Result dictionary
        """
        try:
            await self._ensure_valid_token()
            
            logger.info(f"Liquidating ProjectX position: account={account_id}, contract={contract_id}")
            
            async with self.session.post(
                f"{self.base_url}/api/Position/close",
                json={
                    "accountId": account_id,
                    "contractId": contract_id
                },
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success"):
                        logger.info(f"✅ Position liquidated successfully")
                        return {"success": True, "data": data}
                    else:
                        logger.error(f"❌ Liquidate failed: {data.get('errorMessage')}")
                        return {"success": False, "error": data.get("errorMessage")}
                else:
                    logger.error(f"Liquidate HTTP error: {response.status}")
                    return {"success": False, "error": f"HTTP {response.status}"}
                    
        except Exception as e:
            logger.error(f"Liquidate position exception: {e}")
            return {"success": False, "error": str(e)}
    
    # ==========================================
    # Helper methods to create order objects
    # ==========================================
    
    def create_market_order(self, account_id: int, contract_id: str, 
                           side: str, quantity: int) -> Dict[str, Any]:
        """
        Create a market order.
        
        Args:
            account_id: Account ID
            contract_id: Contract ID (e.g., "CON.F.US.MNQM5.M25")
            side: "Buy" or "Sell"
            quantity: Number of contracts
        
        Returns:
            Order dictionary ready for place_order()
        """
        return {
            "accountId": account_id,
            "contractId": contract_id,
            "type": self.ORDER_TYPE_MARKET,
            "side": self.SIDE_BUY if side.lower() == "buy" else self.SIDE_SELL,
            "size": int(quantity)
        }
    
    def create_limit_order(self, account_id: int, contract_id: str,
                          side: str, quantity: int, price: float) -> Dict[str, Any]:
        """
        Create a limit order.
        
        Args:
            account_id: Account ID
            contract_id: Contract ID
            side: "Buy" or "Sell"
            quantity: Number of contracts
            price: Limit price
        
        Returns:
            Order dictionary ready for place_order()
        """
        return {
            "accountId": account_id,
            "contractId": contract_id,
            "type": self.ORDER_TYPE_LIMIT,
            "side": self.SIDE_BUY if side.lower() == "buy" else self.SIDE_SELL,
            "size": int(quantity),
            "price": float(price)
        }
    
    def create_stop_order(self, account_id: int, contract_id: str,
                         side: str, quantity: int, stop_price: float) -> Dict[str, Any]:
        """
        Create a stop order.
        
        Args:
            account_id: Account ID
            contract_id: Contract ID
            side: "Buy" or "Sell"
            quantity: Number of contracts
            stop_price: Stop trigger price
        
        Returns:
            Order dictionary ready for place_order()
        """
        return {
            "accountId": account_id,
            "contractId": contract_id,
            "type": self.ORDER_TYPE_STOP,
            "side": self.SIDE_BUY if side.lower() == "buy" else self.SIDE_SELL,
            "size": int(quantity),
            "stopPrice": float(stop_price)
        }
    
    def create_stop_limit_order(self, account_id: int, contract_id: str,
                               side: str, quantity: int, 
                               stop_price: float, limit_price: float) -> Dict[str, Any]:
        """
        Create a stop-limit order.
        
        Args:
            account_id: Account ID
            contract_id: Contract ID
            side: "Buy" or "Sell"
            quantity: Number of contracts
            stop_price: Stop trigger price
            limit_price: Limit price after stop triggers
        
        Returns:
            Order dictionary ready for place_order()
        """
        return {
            "accountId": account_id,
            "contractId": contract_id,
            "type": self.ORDER_TYPE_STOP_LIMIT,
            "side": self.SIDE_BUY if side.lower() == "buy" else self.SIDE_SELL,
            "size": int(quantity),
            "stopPrice": float(stop_price),
            "price": float(limit_price)
        }
    
    # ==========================================
    # TP/SL Bracket Orders (Added Jan 2026)
    # ==========================================
    
    def create_market_order_with_brackets(self, account_id: int, contract_id: str,
                                          side: str, quantity: int,
                                          tp_ticks: int = None, sl_ticks: int = None) -> Dict[str, Any]:
        """
        Create a market order with take-profit and/or stop-loss brackets.
        
        This is the ProjectX equivalent of Tradovate bracket orders.
        Brackets are attached directly to the entry order and managed as OCO.
        
        Args:
            account_id: Account ID
            contract_id: Contract ID (e.g., "CON.F.US.MNQM5.M25")
            side: "Buy" or "Sell"
            quantity: Number of contracts
            tp_ticks: Take profit in ticks (None = no TP)
            sl_ticks: Stop loss in ticks (None = no SL)
        
        Returns:
            Order dictionary ready for place_order() with brackets attached
        """
        order = {
            "accountId": account_id,
            "contractId": contract_id,
            "type": self.ORDER_TYPE_MARKET,
            "side": self.SIDE_BUY if side.lower() == "buy" else self.SIDE_SELL,
            "size": int(quantity)
        }
        
        # Add take profit bracket if specified
        if tp_ticks and tp_ticks > 0:
            order["takeProfitBracket"] = {
                "ticks": int(tp_ticks),
                "type": self.ORDER_TYPE_LIMIT  # TP is always a limit order
            }
            logger.info(f"📊 TP bracket: {tp_ticks} ticks")
        
        # Add stop loss bracket if specified
        if sl_ticks and sl_ticks > 0:
            order["stopLossBracket"] = {
                "ticks": int(sl_ticks),
                "type": self.ORDER_TYPE_STOP  # SL is a stop order
            }
            logger.info(f"📊 SL bracket: {sl_ticks} ticks")
        
        return order
    
    def create_limit_order_with_brackets(self, account_id: int, contract_id: str,
                                         side: str, quantity: int, price: float,
                                         tp_ticks: int = None, sl_ticks: int = None) -> Dict[str, Any]:
        """
        Create a limit order with take-profit and/or stop-loss brackets.
        
        Args:
            account_id: Account ID
            contract_id: Contract ID
            side: "Buy" or "Sell"
            quantity: Number of contracts
            price: Limit price for entry
            tp_ticks: Take profit in ticks (None = no TP)
            sl_ticks: Stop loss in ticks (None = no SL)
        
        Returns:
            Order dictionary ready for place_order() with brackets attached
        """
        order = {
            "accountId": account_id,
            "contractId": contract_id,
            "type": self.ORDER_TYPE_LIMIT,
            "side": self.SIDE_BUY if side.lower() == "buy" else self.SIDE_SELL,
            "size": int(quantity),
            "price": float(price)
        }
        
        if tp_ticks and tp_ticks > 0:
            order["takeProfitBracket"] = {
                "ticks": int(tp_ticks),
                "type": self.ORDER_TYPE_LIMIT
            }
        
        if sl_ticks and sl_ticks > 0:
            order["stopLossBracket"] = {
                "ticks": int(sl_ticks),
                "type": self.ORDER_TYPE_STOP
            }
        
        return order
    
    async def place_bracket_order(self, account_id: int, contract_id: str,
                                  side: str, quantity: int,
                                  tp_ticks: int = None, sl_ticks: int = None) -> Optional[Dict[str, Any]]:
        """
        Convenience method: Place a market order with TP/SL brackets in one call.
        
        Args:
            account_id: Account ID
            contract_id: Contract ID
            side: "Buy" or "Sell"
            quantity: Number of contracts
            tp_ticks: Take profit in ticks
            sl_ticks: Stop loss in ticks
        
        Returns:
            Order result from place_order()
        """
        order_data = self.create_market_order_with_brackets(
            account_id=account_id,
            contract_id=contract_id,
            side=side,
            quantity=quantity,
            tp_ticks=tp_ticks,
            sl_ticks=sl_ticks
        )
        
        logger.info(f"🎯 Placing ProjectX bracket order: {side} {quantity} @ Market, TP={tp_ticks}t, SL={sl_ticks}t")
        return await self.place_order(order_data)


# ==========================================
# Position Sync & Reconciliation (Added Jan 2026)
# ==========================================

class ProjectXPositionSync:
    """
    Position synchronization for ProjectX accounts.
    Similar to Tradovate's position reconciliation in recorder_service.
    """
    
    def __init__(self, projectx: 'ProjectXIntegration'):
        self.projectx = projectx
        self.last_sync_time: Optional[datetime] = None
        self.cached_positions: Dict[int, List[Dict]] = {}  # account_id -> positions
    
    async def sync_positions(self, account_id: int) -> Dict[str, Any]:
        """
        Sync positions from ProjectX broker.
        
        Returns:
            Dict with positions and sync status
        """
        try:
            positions = await self.projectx.get_positions(account_id)
            self.cached_positions[account_id] = positions
            self.last_sync_time = datetime.now()
            
            # Build position summary
            position_summary = []
            for pos in positions:
                position_summary.append({
                    'contract_id': pos.get('contractId'),
                    'symbol': pos.get('contractName') or pos.get('symbol'),
                    'quantity': pos.get('netPos', 0),
                    'avg_price': pos.get('netPrice', 0),
                    'unrealized_pnl': pos.get('unrealizedPnl', 0),
                    'realized_pnl': pos.get('realizedPnl', 0)
                })
            
            logger.info(f"📊 ProjectX position sync: {len(positions)} positions for account {account_id}")
            
            return {
                'success': True,
                'positions': position_summary,
                'raw_positions': positions,
                'sync_time': self.last_sync_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Position sync error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def check_position_flat(self, account_id: int, contract_id: str) -> bool:
        """
        Check if a specific position is flat (zero quantity).
        Used for position reconciliation.
        """
        try:
            positions = await self.projectx.get_positions(account_id)
            
            for pos in positions:
                if pos.get('contractId') == contract_id:
                    net_pos = pos.get('netPos', 0)
                    return net_pos == 0
            
            # Position not found = flat
            return True
            
        except Exception as e:
            logger.error(f"Check position flat error: {e}")
            return True  # Assume flat on error to be safe
    
    async def get_position_details(self, account_id: int, contract_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for a specific position.
        """
        try:
            positions = await self.projectx.get_positions(account_id)
            
            for pos in positions:
                if pos.get('contractId') == contract_id:
                    return {
                        'contract_id': contract_id,
                        'quantity': pos.get('netPos', 0),
                        'avg_price': pos.get('netPrice', 0),
                        'side': 'LONG' if pos.get('netPos', 0) > 0 else 'SHORT' if pos.get('netPos', 0) < 0 else 'FLAT',
                        'unrealized_pnl': pos.get('unrealizedPnl', 0)
                    }
            
            return None  # Position not found
            
        except Exception as e:
            logger.error(f"Get position details error: {e}")
            return None


# ==========================================
# SignalR WebSocket Support (Added Jan 2026)
# ==========================================
# Note: Requires 'signalrcore' package: pip install signalrcore
# ==========================================

class ProjectXWebSocket:
    """
    SignalR WebSocket connection for real-time ProjectX updates.
    
    Features:
    - Real-time position updates
    - Real-time order updates
    - Real-time balance updates
    
    Usage:
        ws = ProjectXWebSocket(session_token, demo=True)
        await ws.connect()
        await ws.subscribe_positions()
        # Updates received via callbacks
    """
    
    def __init__(self, session_token: str, demo: bool = True):
        self.session_token = session_token
        self.demo = demo
        
        if demo:
            self.hub_url = "https://gateway-rtc-demo.s2f.projectx.com/hubs/user"
        else:
            self.hub_url = "https://gateway-rtc.s2f.projectx.com/hubs/user"
        
        self.connection = None
        self.is_connected = False
        self.position_callbacks: List[callable] = []
        self.order_callbacks: List[callable] = []
        
    async def connect(self) -> bool:
        """
        Connect to ProjectX SignalR hub.
        
        Note: Requires signalrcore package.
        Install with: pip install signalrcore
        """
        try:
            # Try to import signalrcore
            try:
                from signalrcore.hub_connection_builder import HubConnectionBuilder
            except ImportError:
                logger.warning("signalrcore not installed. Install with: pip install signalrcore")
                logger.warning("Real-time updates will not be available. Position sync via REST API still works.")
                return False
            
            # Build connection with access token
            self.connection = HubConnectionBuilder() \
                .with_url(f"{self.hub_url}?access_token={self.session_token}") \
                .with_automatic_reconnect({
                    "type": "raw",
                    "keep_alive_interval": 10,
                    "reconnect_interval": 5,
                    "max_attempts": 5
                }) \
                .build()
            
            # Register event handlers
            self.connection.on("RealTimePosition", self._on_position_update)
            self.connection.on("RealTimeOrder", self._on_order_update)
            self.connection.on("RealTimeBalance", self._on_balance_update)
            
            # Start connection
            self.connection.start()
            self.is_connected = True
            logger.info("✅ ProjectX SignalR WebSocket connected")
            return True
            
        except Exception as e:
            logger.error(f"SignalR connection error: {e}")
            self.is_connected = False
            return False
    
    async def subscribe_positions(self) -> bool:
        """Subscribe to real-time position updates."""
        if not self.is_connected or not self.connection:
            logger.warning("Cannot subscribe - not connected")
            return False
        
        try:
            self.connection.send("SubscribePositionUpdates", [])
            logger.info("📡 Subscribed to ProjectX position updates")
            return True
        except Exception as e:
            logger.error(f"Subscribe positions error: {e}")
            return False
    
    async def subscribe_orders(self) -> bool:
        """Subscribe to real-time order updates."""
        if not self.is_connected or not self.connection:
            return False
        
        try:
            self.connection.send("SubscribeOrderUpdates", [])
            logger.info("📡 Subscribed to ProjectX order updates")
            return True
        except Exception as e:
            logger.error(f"Subscribe orders error: {e}")
            return False
    
    def on_position_update(self, callback: callable):
        """Register callback for position updates."""
        self.position_callbacks.append(callback)
    
    def on_order_update(self, callback: callable):
        """Register callback for order updates."""
        self.order_callbacks.append(callback)
    
    def _on_position_update(self, data):
        """Internal handler for position updates."""
        logger.info(f"📊 Position update: {data}")
        for callback in self.position_callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Position callback error: {e}")
    
    def _on_order_update(self, data):
        """Internal handler for order updates."""
        logger.info(f"📋 Order update: {data}")
        for callback in self.order_callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Order callback error: {e}")
    
    def _on_balance_update(self, data):
        """Internal handler for balance updates."""
        logger.debug(f"💰 Balance update: {data}")
    
    async def disconnect(self):
        """Disconnect from SignalR hub."""
        if self.connection:
            try:
                self.connection.stop()
            except:
                pass
        self.is_connected = False
        logger.info("ProjectX SignalR disconnected")


class ProjectXManager:
    """High-level manager for ProjectX operations - mirrors TradovateManager pattern"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.active_connections: Dict[str, ProjectXIntegration] = {}
    
    async def test_connection(self, username: str, api_key: str, 
                             demo: bool = True) -> Dict[str, Any]:
        """
        Test ProjectX connection and return account info.
        
        Args:
            username: ProjectX Dashboard username
            api_key: API key from ProjectX Dashboard
            demo: If True, use demo environment
        
        Returns:
            Dict with success status and account info
        """
        try:
            async with ProjectXIntegration(demo=demo) as projectx:
                # Test login
                if not await projectx.login_with_api_key(username, api_key):
                    return {
                        "success": False,
                        "error": "Login failed. Please check your username and API key."
                    }
                
                # Get accounts
                accounts = await projectx.get_accounts()
                if not accounts:
                    return {
                        "success": False,
                        "error": "No active accounts found."
                    }
                
                # Get available contracts
                contracts = await projectx.get_available_contracts()
                
                return {
                    "success": True,
                    "message": "Connection successful!",
                    "accounts": accounts,
                    "total_accounts": len(accounts),
                    "contracts_available": len(contracts),
                    "environment": "demo" if demo else "live"
                }
                
        except Exception as e:
            logger.error(f"ProjectX connection test error: {e}")
            return {
                "success": False,
                "error": f"Connection test failed: {str(e)}"
            }
    
    async def get_account_status(self, account_id: int, username: str, 
                                api_key: str, demo: bool = True) -> Dict[str, Any]:
        """
        Get current status of an account.
        
        Args:
            account_id: ProjectX account ID
            username: ProjectX username
            api_key: API key
            demo: Demo or live environment
        
        Returns:
            Dict with account status, positions, orders
        """
        try:
            async with ProjectXIntegration(demo=demo) as projectx:
                if not await projectx.login_with_api_key(username, api_key):
                    return {"success": False, "error": "Authentication failed"}
                
                account_info = await projectx.get_account_info(account_id)
                positions = await projectx.get_positions(account_id)
                orders = await projectx.get_orders(account_id)
                
                return {
                    "success": True,
                    "account_info": account_info,
                    "positions": positions,
                    "orders": orders,
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Get account status error: {e}")
            return {"success": False, "error": str(e)}


# Example usage and testing
async def main():
    """Example usage of ProjectX integration"""
    print("ProjectX Integration Test")
    print("=" * 50)
    
    # Test credentials (replace with real ones)
    username = "your_username"
    api_key = "your_api_key"
    
    manager = ProjectXManager()
    
    # Test connection
    result = await manager.test_connection(username, api_key, demo=True)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
