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
        self.contract_cache: Dict[int, Optional[str]] = {}
        
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
                f"{self.base_url}/order/placeorder",
                json=order_data,
                headers=self._get_headers()
            ) as response:
                try:
                    data = await response.json()
                except Exception:
                    data = {}
                    try:
                        text_body = await response.text()
                    except Exception:
                        text_body = ''
                else:
                    text_body = ''

                if response.status == 200 and data.get('orderId'):
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
    
    async def get_positions(self, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get current positions; optionally filter by account_id."""
        try:
            async with self.session.get(
                f"{self.base_url}/position/list",
                headers=self._get_headers()
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to get positions: {response.status}")
                    return []
                data = await response.json() or []
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
    
    async def get_orders(self, account_id: str = None) -> List[Dict[str, Any]]:
        """
        Get orders for an account or all orders.
        If account_id is None, uses /order/list to get all orders (includes order strategies).
        """
        try:
            if account_id:
                # Get orders for specific account
                url = f"{self.base_url}/account/{account_id}/orders"
            else:
                # Get ALL orders (includes order strategies like brackets, OCOs)
                url = f"{self.base_url}/order/list"
            
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
                    
        except Exception as e:
            logger.error(f"Error getting orders: {e}", exc_info=True)
            return []
    
    async def cancel_order(self, order_id: int) -> bool:
        """Cancel an existing order"""
        try:
            if not order_id:
                logger.warning(f"Attempted to cancel order with invalid ID: {order_id}")
                return False
            
            logger.info(f"Attempting to cancel order {order_id} via {self.base_url}/order/cancelorder")
            async with self.session.post(
                f"{self.base_url}/order/cancelorder",
                json={"orderId": order_id, "isAutomated": True},
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
    
    def create_limit_order(self, account_spec: str, symbol: str, side: str, quantity: int, price: float, account_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a limit order"""
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
        
        The brackets are specified in TICKS from entry price, and Tradovate
        automatically creates OCO orders that cancel each other.
        
        Args:
            account_id: The Tradovate account ID
            account_spec: The account name/spec  
            symbol: The trading symbol
            entry_side: 'Buy' or 'Sell' for the entry
            quantity: Number of contracts
            profit_target_ticks: Profit target in ticks (positive number)
            stop_loss_ticks: Stop loss in ticks (positive number, will be negated internally)
            trailing_stop: Whether to use trailing stop instead of fixed stop
        
        Returns:
            Dict with order strategy result
        """
        try:
            # Build bracket params - Tradovate wants these in ticks
            # profitTarget is positive ticks above entry (for long) or below (for short)
            # stopLoss is negative ticks (loss from entry)
            
            bracket = {
                "qty": int(quantity),
                "profitTarget": int(profit_target_ticks) if profit_target_ticks else None,
                "stopLoss": -abs(int(stop_loss_ticks)) if stop_loss_ticks else None,  # Negative for loss
                "trailingStop": trailing_stop
            }
            
            # Entry order params
            params = {
                "entryVersion": {
                    "orderQty": int(quantity),
                    "orderType": "Market",
                    "timeInForce": "Day"
                },
                "brackets": [bracket]
            }
            
            # Full strategy request
            strategy_request = {
                "accountId": account_id,
                "accountSpec": account_spec,
                "symbol": symbol,
                "orderStrategyTypeId": 2,  # 2 = Bracket strategy type
                "action": entry_side,
                "params": json.dumps(params)
            }
            
            logger.info(f"📊 Placing bracket order strategy: entry={entry_side}, qty={quantity}, TP={profit_target_ticks} ticks, SL={stop_loss_ticks} ticks")
            logger.debug(f"Full strategy request: {strategy_request}")
            
            async with self.session.post(
                f"{self.base_url}/orderStrategy/startorderstrategy",
                json=strategy_request,
                headers=self._get_headers()
            ) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    data = json.loads(response_text)
                    strategy_id = data.get('id') or data.get('orderStrategyId')
                    logger.info(f"✅ Bracket order strategy created: ID={strategy_id}")
                    return {
                        'success': True, 
                        'data': data, 
                        'strategy_id': strategy_id,
                        'orderId': data.get('orderId')
                    }
                else:
                    logger.error(f"❌ Failed to create bracket strategy: {response.status}, {response_text[:500]}")
                    return {'success': False, 'error': response_text}
                    
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
            
            strategy_request = {
                "accountId": account_id,
                "accountSpec": account_spec,
                "symbol": symbol,
                "orderStrategyTypeId": 1,  # 1 = OCO type
                "action": exit_side,
                "params": json.dumps(params)
            }
            
            logger.info(f"📊 Placing OCO exit: {exit_side} {quantity} {symbol}, TP={take_profit_price}, SL={stop_loss_price}")
            
            async with self.session.post(
                f"{self.base_url}/orderStrategy/startorderstrategy",
                json=strategy_request,
                headers=self._get_headers()
            ) as response:
                response_text = await response.text()
                
                if response.status == 200:
                    data = json.loads(response_text)
                    
                    # Check for error in response (Tradovate returns 200 with errorText)
                    if data.get('errorText'):
                        error_msg = data.get('errorText')
                        logger.warning(f"⚠️ OCO strategy returned error: {error_msg}")
                        logger.info(f"📊 Falling back to individual TP/SL orders...")
                        # Fallback to placing individual orders
                        return await self._place_individual_exit_orders(
                            account_id, account_spec, symbol, exit_side, quantity,
                            take_profit_price, stop_loss_price
                        )
                    
                    logger.info(f"✅ OCO exit strategy created: {data}")
                    return {'success': True, 'data': data, 'strategy_id': data.get('id')}
                else:
                    logger.error(f"❌ Failed to create OCO exit: {response.status}, {response_text[:500]}")
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
