#!/usr/bin/env python3
"""
Webull OpenAPI Integration for Just.Trades
https://developer.webull.com/api-doc/

Supports: Stocks, ETFs, Options, Futures, Crypto

Requirements:
- Webull brokerage account with $5,000+ minimum
- API access approval (1-2 business days)
- App Key and App Secret from Webull API Management

Authentication Flow:
1. User provides App Key + App Secret
2. We get access token via /openapi/account/token
3. Use token for all API requests
"""

import asyncio
import aiohttp
import json
import logging
import hashlib
import hmac
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class WebullIntegration:
    """
    Webull OpenAPI Integration for automated trading.
    
    Authentication: App Key + App Secret → Access Token
    
    Supported:
    - US Stocks & ETFs
    - Options
    - Futures
    - Crypto
    """
    
    # API Base URLs
    BASE_URL = "https://api.webull.com/api"
    OPENAPI_URL = "https://openapi.webull.com"
    
    # Order Types
    ORDER_TYPE_MARKET = "MARKET"
    ORDER_TYPE_LIMIT = "LIMIT"
    ORDER_TYPE_STOP = "STOP"
    ORDER_TYPE_STOP_LIMIT = "STOP_LIMIT"
    ORDER_TYPE_TRAILING_STOP = "TRAILING_STOP"
    
    # Order Sides
    SIDE_BUY = "BUY"
    SIDE_SELL = "SELL"
    
    # Time in Force
    TIF_DAY = "DAY"
    TIF_GTC = "GTC"  # Good 'Til Canceled
    TIF_IOC = "IOC"  # Immediate or Cancel
    TIF_FOK = "FOK"  # Fill or Kill
    
    def __init__(self, app_key: str = None, app_secret: str = None):
        """
        Initialize Webull integration.
        
        Args:
            app_key: Your Webull App Key from API Management
            app_secret: Your Webull App Secret from API Management
        """
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self.account_id: Optional[str] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.accounts: List[Dict[str, Any]] = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _generate_signature(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """
        Generate HMAC signature for API request.
        
        Webull uses HMAC-SHA256 signature for authentication.
        """
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_headers(self, method: str = "GET", path: str = "", body: str = "") -> Dict[str, str]:
        """Get headers with authentication for API requests."""
        timestamp = str(int(time.time() * 1000))
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-app-key": self.app_key,
            "x-timestamp": timestamp,
        }
        
        if self.app_secret:
            signature = self._generate_signature(timestamp, method, path, body)
            headers["x-signature"] = signature
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        return headers
    
    async def login(self, app_key: str = None, app_secret: str = None) -> dict:
        """
        Authenticate with Webull using App Key and App Secret.
        
        Args:
            app_key: Webull App Key (optional if passed to constructor)
            app_secret: Webull App Secret (optional if passed to constructor)
        
        Returns:
            dict with 'success' and 'error' keys
        """
        if app_key:
            self.app_key = app_key
        if app_secret:
            self.app_secret = app_secret
            
        if not self.app_key or not self.app_secret:
            return {"success": False, "error": "App Key and App Secret are required"}
        
        try:
            logger.info(f"🔑 Attempting Webull login")
            logger.info(f"   App Key (first 10 chars): {self.app_key[:10]}...")
            
            # Get access token
            path = "/openapi/account/token"
            body_data = {
                "app_key": self.app_key,
                "app_secret": self.app_secret
            }
            body = json.dumps(body_data)
            
            headers = self._get_headers("POST", path, body)
            
            async with self.session.post(
                f"{self.OPENAPI_URL}{path}",
                data=body,
                headers=headers
            ) as response:
                response_text = await response.text()
                logger.info(f"   Response status: {response.status}")
                logger.info(f"   Response: {response_text[:500]}")
                
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                    except:
                        return {"success": False, "error": f"Invalid JSON response: {response_text[:200]}"}
                    
                    # Check for access token
                    token = data.get("access_token") or data.get("token")
                    
                    if token:
                        self.access_token = token
                        # Token typically valid for the duration specified
                        expires_in = data.get("expires_in", 86400)  # Default 24 hours
                        self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                        
                        logger.info(f"✅ Successfully authenticated with Webull")
                        logger.info(f"   Token expires: {self.token_expires}")
                        return {"success": True}
                    else:
                        error_msg = data.get("msg") or data.get("message") or data.get("error") or "No token received"
                        return {"success": False, "error": f"Auth failed: {error_msg}"}
                        
                elif response.status == 401:
                    return {"success": False, "error": "Invalid App Key or App Secret (HTTP 401)"}
                elif response.status == 403:
                    return {"success": False, "error": "API access not approved or expired (HTTP 403)"}
                else:
                    return {"success": False, "error": f"HTTP {response.status}: {response_text[:200]}"}
                    
        except Exception as e:
            logger.error(f"Webull login exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": f"Connection error: {str(e)}"}
    
    async def get_accounts(self) -> List[Dict[str, Any]]:
        """
        Get list of trading accounts.
        
        Returns:
            List of account dictionaries
        """
        try:
            path = "/openapi/account/list"
            headers = self._get_headers("GET", path)
            
            async with self.session.get(
                f"{self.OPENAPI_URL}{path}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    accounts = data.get("data", []) or data.get("accounts", [])
                    self.accounts = accounts
                    
                    if accounts:
                        # Set default account
                        self.account_id = accounts[0].get("account_id") or accounts[0].get("id")
                    
                    logger.info(f"Retrieved {len(accounts)} Webull accounts")
                    return accounts
                else:
                    error_text = await response.text()
                    logger.error(f"Get accounts error: {response.status} - {error_text[:200]}")
                    return []
                    
        except Exception as e:
            logger.error(f"Get accounts exception: {e}")
            return []
    
    async def get_account_info(self, account_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Get detailed account information including balance and positions.
        
        Args:
            account_id: Account ID (uses default if not provided)
        
        Returns:
            Account info dictionary
        """
        account_id = account_id or self.account_id
        if not account_id:
            logger.error("No account ID available")
            return None
            
        try:
            path = f"/openapi/account/{account_id}"
            headers = self._get_headers("GET", path)
            
            async with self.session.get(
                f"{self.OPENAPI_URL}{path}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data") or data
                else:
                    error_text = await response.text()
                    logger.error(f"Get account info error: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Get account info exception: {e}")
            return None
    
    async def get_positions(self, account_id: str = None) -> List[Dict[str, Any]]:
        """
        Get current positions for an account.
        
        Args:
            account_id: Account ID (uses default if not provided)
        
        Returns:
            List of position dictionaries
        """
        account_id = account_id or self.account_id
        if not account_id:
            return []
            
        try:
            path = f"/openapi/account/{account_id}/positions"
            headers = self._get_headers("GET", path)
            
            async with self.session.get(
                f"{self.OPENAPI_URL}{path}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    positions = data.get("data", []) or data.get("positions", [])
                    logger.info(f"Retrieved {len(positions)} positions")
                    return positions
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Get positions exception: {e}")
            return []
    
    async def get_orders(self, account_id: str = None, status: str = "WORKING") -> List[Dict[str, Any]]:
        """
        Get orders for an account.
        
        Args:
            account_id: Account ID
            status: Order status filter (WORKING, FILLED, CANCELLED, etc.)
        
        Returns:
            List of order dictionaries
        """
        account_id = account_id or self.account_id
        if not account_id:
            return []
            
        try:
            path = f"/openapi/account/{account_id}/orders"
            params = {"status": status} if status else {}
            headers = self._get_headers("GET", path)
            
            async with self.session.get(
                f"{self.OPENAPI_URL}{path}",
                params=params,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    orders = data.get("data", []) or data.get("orders", [])
                    return orders
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Get orders exception: {e}")
            return []
    
    async def search_instrument(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Search for an instrument by symbol to get its instrument_id.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL", "TSLA")
        
        Returns:
            Instrument info including instrument_id
        """
        try:
            path = "/openapi/instrument/search"
            params = {"keyword": symbol}
            headers = self._get_headers("GET", path)
            
            async with self.session.get(
                f"{self.OPENAPI_URL}{path}",
                params=params,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    instruments = data.get("data", []) or data.get("instruments", [])
                    
                    # Find exact match
                    for inst in instruments:
                        if inst.get("symbol", "").upper() == symbol.upper():
                            return inst
                    
                    # Return first result if no exact match
                    return instruments[0] if instruments else None
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Search instrument exception: {e}")
            return None
    
    async def place_order(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Place an order.
        
        Args:
            order_data: Order dictionary with:
                - account_id: str
                - instrument_id: str
                - side: "BUY" or "SELL"
                - order_type: "MARKET", "LIMIT", etc.
                - qty: int
                - limit_price: str (for limit orders)
                - stop_price: str (for stop orders)
                - tif: "DAY", "GTC", etc.
        
        Returns:
            Order result dictionary
        """
        try:
            account_id = order_data.get("account_id") or self.account_id
            
            path = "/trade/order/place"
            body_data = {
                "account_id": account_id,
                "stock_order": {
                    "client_order_id": order_data.get("client_order_id", f"jt_{int(time.time()*1000)}"),
                    "side": order_data.get("side", self.SIDE_BUY),
                    "order_type": order_data.get("order_type", self.ORDER_TYPE_MARKET),
                    "instrument_id": order_data.get("instrument_id"),
                    "qty": int(order_data.get("qty", 1)),
                    "tif": order_data.get("tif", self.TIF_DAY),
                }
            }
            
            # Add price fields if applicable
            if order_data.get("limit_price"):
                body_data["stock_order"]["limit_price"] = str(order_data["limit_price"])
            if order_data.get("stop_price"):
                body_data["stock_order"]["stop_price"] = str(order_data["stop_price"])
            if order_data.get("extended_hours_trading") is not None:
                body_data["stock_order"]["extended_hours_trading"] = order_data["extended_hours_trading"]
            
            body = json.dumps(body_data)
            headers = self._get_headers("POST", path, body)
            
            logger.info(f"📊 Placing Webull order: {body_data}")
            
            async with self.session.post(
                f"{self.OPENAPI_URL}{path}",
                data=body,
                headers=headers
            ) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    data = json.loads(response_text)
                    
                    if data.get("success") or data.get("order_id"):
                        order_id = data.get("order_id") or data.get("data", {}).get("order_id")
                        logger.info(f"✅ Order placed successfully: {order_id}")
                        return {"success": True, "order_id": order_id, "data": data}
                    else:
                        error_msg = data.get("msg") or data.get("message") or "Order rejected"
                        logger.error(f"❌ Order rejected: {error_msg}")
                        return {"success": False, "error": error_msg}
                else:
                    logger.error(f"❌ Order HTTP error: {response.status} - {response_text[:200]}")
                    return {"success": False, "error": f"HTTP {response.status}: {response_text[:200]}"}
                    
        except Exception as e:
            logger.error(f"Place order exception: {e}")
            return {"success": False, "error": str(e)}
    
    async def cancel_order(self, order_id: str, account_id: str = None) -> bool:
        """
        Cancel an existing order.
        
        Args:
            order_id: Order ID to cancel
            account_id: Account ID
        
        Returns:
            True if cancelled successfully
        """
        try:
            account_id = account_id or self.account_id
            
            path = "/trade/order/cancel"
            body_data = {
                "account_id": account_id,
                "order_id": order_id
            }
            body = json.dumps(body_data)
            headers = self._get_headers("POST", path, body)
            
            async with self.session.post(
                f"{self.OPENAPI_URL}{path}",
                data=body,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        logger.info(f"✅ Order {order_id} cancelled")
                        return True
                return False
                
        except Exception as e:
            logger.error(f"Cancel order exception: {e}")
            return False
    
    # ==========================================
    # Helper methods for creating orders
    # ==========================================
    
    def create_market_order(self, instrument_id: str, side: str, qty: int) -> Dict[str, Any]:
        """Create a market order."""
        return {
            "instrument_id": instrument_id,
            "side": side.upper(),
            "order_type": self.ORDER_TYPE_MARKET,
            "qty": qty,
            "tif": self.TIF_DAY
        }
    
    def create_limit_order(self, instrument_id: str, side: str, qty: int, 
                          limit_price: float) -> Dict[str, Any]:
        """Create a limit order."""
        return {
            "instrument_id": instrument_id,
            "side": side.upper(),
            "order_type": self.ORDER_TYPE_LIMIT,
            "qty": qty,
            "limit_price": str(limit_price),
            "tif": self.TIF_DAY
        }
    
    def create_stop_order(self, instrument_id: str, side: str, qty: int,
                         stop_price: float) -> Dict[str, Any]:
        """Create a stop order."""
        return {
            "instrument_id": instrument_id,
            "side": side.upper(),
            "order_type": self.ORDER_TYPE_STOP,
            "qty": qty,
            "stop_price": str(stop_price),
            "tif": self.TIF_DAY
        }
    
    async def place_market_order(self, symbol: str, side: str, qty: int) -> Optional[Dict[str, Any]]:
        """
        Convenience method: Place a market order by symbol.
        
        Args:
            symbol: Stock symbol (e.g., "AAPL")
            side: "BUY" or "SELL"
            qty: Number of shares
        
        Returns:
            Order result
        """
        # Get instrument ID
        instrument = await self.search_instrument(symbol)
        if not instrument:
            return {"success": False, "error": f"Symbol {symbol} not found"}
        
        instrument_id = instrument.get("instrument_id") or instrument.get("id")
        
        order = self.create_market_order(instrument_id, side, qty)
        return await self.place_order(order)


class WebullManager:
    """High-level manager for Webull operations."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebullIntegration] = {}
    
    async def test_connection(self, app_key: str, app_secret: str) -> Dict[str, Any]:
        """
        Test Webull connection and return account info.
        
        Args:
            app_key: Webull App Key
            app_secret: Webull App Secret
        
        Returns:
            Dict with success status and account info
        """
        try:
            async with WebullIntegration(app_key, app_secret) as webull:
                login_result = await webull.login()
                
                if not login_result.get("success"):
                    return login_result
                
                accounts = await webull.get_accounts()
                
                return {
                    "success": True,
                    "message": "Connection successful!",
                    "accounts": accounts,
                    "total_accounts": len(accounts)
                }
                
        except Exception as e:
            logger.error(f"Webull connection test error: {e}")
            return {"success": False, "error": str(e)}


# Example usage
async def main():
    """Example usage of Webull integration"""
    print("Webull Integration Test")
    print("=" * 50)
    
    # Test credentials (replace with real ones)
    app_key = "your_app_key"
    app_secret = "your_app_secret"
    
    manager = WebullManager()
    result = await manager.test_connection(app_key, app_secret)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
