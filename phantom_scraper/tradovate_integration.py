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

logger = logging.getLogger(__name__)

class TradovateIntegration:
    def __init__(self, demo=True):
        self.base_url = "https://demo.tradovateapi.com/v1" if demo else "https://live.tradovateapi.com/v1"
        self.session = None
        self.access_token = None
        self.refresh_token = None
        self.token_expires = None
        self.accounts = []
        self.subaccounts = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
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
    
    async def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        try:
            if not self.refresh_token:
                return False
                
            refresh_data = {
                "refreshToken": self.refresh_token
            }
            
            async with self.session.post(
                f"{self.base_url}/auth/refresh-token",
                json=refresh_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data.get("accessToken")
                    self.refresh_token = data.get("refreshToken")
                    
                    expires_in = data.get("expiresIn", 86400)
                    self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                    
                    logger.info("Access token refreshed successfully")
                    return True
                else:
                    logger.error("Failed to refresh access token")
                    return False
                    
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authorization token"""
        if not self.access_token:
            raise Exception("Not authenticated. Please login first.")
            
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def get_accounts(self) -> List[Dict[str, Any]]:
        """Get all accounts for the authenticated user"""
        try:
            async with self.session.get(
                f"{self.base_url}/account/list",
                headers=self._get_headers()
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
    
    async def get_subaccounts(self, account_id: str) -> List[Dict[str, Any]]:
        """Get subaccounts for a specific account"""
        try:
            async with self.session.get(
                f"{self.base_url}/account/{account_id}/subaccounts",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.subaccounts.extend(data)
                    logger.info(f"Retrieved {len(data)} subaccounts for account {account_id}")
                    return data
                else:
                    logger.error(f"Failed to get subaccounts: {response.status}")
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
            # Ensure we have a valid token
            if self.token_expires and datetime.now() >= self.token_expires:
                if not await self.refresh_access_token():
                    logger.error("Failed to refresh token before placing order")
                    return None
            
            async with self.session.post(
                f"{self.base_url}/order/place-order",
                json=order_data,
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Order placed successfully: {data.get('orderId')}")
                    return data
                else:
                    error_data = await response.json()
                    logger.error(f"Failed to place order: {error_data}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    async def get_positions(self, account_id: str) -> List[Dict[str, Any]]:
        """Get current positions for an account"""
        try:
            async with self.session.get(
                f"{self.base_url}/account/{account_id}/positions",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Retrieved {len(data)} positions for account {account_id}")
                    return data
                else:
                    logger.error(f"Failed to get positions: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_orders(self, account_id: str) -> List[Dict[str, Any]]:
        """Get orders for an account"""
        try:
            async with self.session.get(
                f"{self.base_url}/account/{account_id}/orders",
                headers=self._get_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Retrieved {len(data)} orders for account {account_id}")
                    return data
                else:
                    logger.error(f"Failed to get orders: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    def create_market_order(self, account_id: str, symbol: str, side: str, quantity: int) -> Dict[str, Any]:
        """Create a market order"""
        return {
            "accountSpec": account_id,
            "symbol": symbol,
            "orderType": "Market",
            "side": side,  # "Buy" or "Sell"
            "quantity": quantity,
            "timeInForce": "Day"
        }
    
    def create_limit_order(self, account_id: str, symbol: str, side: str, quantity: int, price: float) -> Dict[str, Any]:
        """Create a limit order"""
        return {
            "accountSpec": account_id,
            "symbol": symbol,
            "orderType": "Limit",
            "side": side,  # "Buy" or "Sell"
            "quantity": quantity,
            "price": price,
            "timeInForce": "Day"
        }
    
    def create_stop_order(self, account_id: str, symbol: str, side: str, quantity: int, stop_price: float) -> Dict[str, Any]:
        """Create a stop order"""
        return {
            "accountSpec": account_id,
            "symbol": symbol,
            "orderType": "Stop",
            "side": side,  # "Buy" or "Sell"
            "quantity": quantity,
            "stopPrice": stop_price,
            "timeInForce": "Day"
        }

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
