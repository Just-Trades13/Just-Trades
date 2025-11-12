"""
Tradovate Service for Just.Trades
Wraps TradovateIntegration for use in Flask backend
"""

import asyncio
import sys
import os

# Add parent directory to path to find tradovate_integration
current_dir = os.path.dirname(os.path.abspath(__file__))
# trade_manager_replica/services -> trade_manager_replica -> phantom_scraper
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

try:
    from tradovate_integration import TradovateIntegration
except ImportError:
    # If tradovate_integration not found, create a minimal stub
    print("Warning: tradovate_integration not found, using stub implementation")
    class TradovateIntegration:
        def __init__(self, demo=True):
            self.demo = demo
            self.access_token = None
            self.refresh_token = None
            self.token_expires = None
        
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def login_with_credentials(self, *args, **kwargs):
            return False
        
        async def get_accounts(self):
            return []
        
        async def get_subaccounts(self, *args):
            return []
        
        async def get_positions(self, *args):
            return []
        
        async def place_order(self, *args):
            return None

import logging

logger = logging.getLogger(__name__)

class TradovateService:
    """Service wrapper for Tradovate integration"""
    
    @staticmethod
    async def test_connection(username: str, password: str, client_id: str = None, client_secret: str = None, demo: bool = True) -> dict:
        """Test Tradovate connection"""
        try:
            async with TradovateIntegration(demo=demo) as tradovate:
                if not await tradovate.login_with_credentials(username, password, client_id, client_secret):
                    return {
                        "success": False,
                        "error": "Login failed. Please check your credentials."
                    }
                
                accounts = await tradovate.get_accounts()
                if not accounts:
                    return {
                        "success": False,
                        "error": "No accounts found for this user."
                    }
                
                # Get subaccounts
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
                    "access_token": tradovate.access_token,
                    "refresh_token": tradovate.refresh_token,
                    "token_expires": tradovate.token_expires.isoformat() if tradovate.token_expires else None
                }
        except Exception as e:
            logger.error(f"Tradovate connection test error: {e}")
            return {
                "success": False,
                "error": f"Connection test failed: {str(e)}"
            }
    
    @staticmethod
    async def execute_trade(account_id: int, symbol: str, side: str, quantity: int, 
                          order_type: str = "Market", price: float = None, 
                          username: str = None, password: str = None, 
                          client_id: str = None, client_secret: str = None,
                          demo: bool = True) -> dict:
        """Execute a trade on Tradovate"""
        try:
            async with TradovateIntegration(demo=demo) as tradovate:
                # Login if credentials provided
                if username and password:
                    if not await tradovate.login_with_credentials(username, password, client_id, client_secret):
                        return {
                            "success": False,
                            "error": "Failed to authenticate with Tradovate"
                        }
                
                # Place order
                if side.lower() == "buy":
                    order = await tradovate.place_market_order(
                        account_id=str(account_id),
                        symbol=symbol,
                        side="Buy",
                        quantity=quantity
                    )
                elif side.lower() == "sell":
                    order = await tradovate.place_market_order(
                        account_id=str(account_id),
                        symbol=symbol,
                        side="Sell",
                        quantity=quantity
                    )
                else:
                    return {
                        "success": False,
                        "error": f"Invalid side: {side}. Must be 'buy' or 'sell'"
                    }
                
                return {
                    "success": True,
                    "order": order,
                    "message": f"Order placed successfully"
                }
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return {
                "success": False,
                "error": f"Trade execution failed: {str(e)}"
            }
    
    
    @staticmethod
    async def place_order(account_id: int, username: str, password: str,
                         client_id: str, client_secret: str, token: str,
                         refresh_token: str, symbol: str, side: str, quantity: int,
                         order_type: str = "Market", price: float = None,
                         demo: bool = True) -> dict:
        """Place an order on Tradovate"""
        try:
            async with TradovateIntegration(demo=demo) as tradovate:
                # Set tokens if provided
                if token:
                    tradovate.access_token = token
                    tradovate.refresh_token = refresh_token
                
                # Login if needed
                if not tradovate.access_token:
                    if not await tradovate.login_with_credentials(username, password, client_id, client_secret):
                        return {
                            "success": False,
                            "error": "Failed to authenticate with Tradovate"
                        }
                
                # Create order data
                order_data = {
                    "accountSpec": str(account_id),
                    "symbol": symbol,
                    "orderType": order_type,
                    "side": side,  # "Buy" or "Sell"
                    "quantity": quantity,
                    "timeInForce": "Day"
                }
                
                if order_type == "Limit" and price:
                    order_data["price"] = price
                
                # Place order
                order = await tradovate.place_order(order_data)
                
                if order:
                    return {
                        "success": True,
                        "order_id": order.get("id"),
                        "order": order,
                        "message": "Order placed successfully",
                        "access_token": tradovate.access_token,
                        "refresh_token": tradovate.refresh_token,
                        "token_expires": tradovate.token_expires.isoformat() if tradovate.token_expires else None
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to place order"
                    }
        except Exception as e:
            logger.error(f"Place order error: {e}")
            return {
                "success": False,
                "error": f"Order placement failed: {str(e)}"
            }
    
    @staticmethod
    async def close_position(account_id: int, username: str, password: str,
                            client_id: str, client_secret: str, token: str,
                            refresh_token: str, symbol: str, demo: bool = True) -> dict:
        """Close all positions for a symbol"""
        try:
            async with TradovateIntegration(demo=demo) as tradovate:
                # Set tokens if provided
                if token:
                    tradovate.access_token = token
                    tradovate.refresh_token = refresh_token
                
                # Login if needed
                if not tradovate.access_token:
                    if not await tradovate.login_with_credentials(username, password, client_id, client_secret):
                        return {
                            "success": False,
                            "error": "Failed to authenticate with Tradovate"
                        }
                
                # Get positions
                positions = await tradovate.get_positions(str(account_id))
                
                # Find position for this symbol
                position_to_close = None
                for pos in positions:
                    if pos.get("symbol") == symbol and pos.get("quantity", 0) != 0:
                        position_to_close = pos
                        break
                
                if not position_to_close:
                    return {
                        "success": False,
                        "error": f"No open position found for {symbol}"
                    }
                
                # Determine opposite side
                quantity = abs(position_to_close.get("quantity", 0))
                side = "Sell" if position_to_close.get("quantity", 0) > 0 else "Buy"
                
                # Place closing order
                order_data = {
                    "accountSpec": str(account_id),
                    "symbol": symbol,
                    "orderType": "Market",
                    "side": side,
                    "quantity": quantity,
                    "timeInForce": "Day"
                }
                
                order = await tradovate.place_order(order_data)
                
                if order:
                    return {
                        "success": True,
                        "order_id": order.get("id"),
                        "message": f"Position closed for {symbol}",
                        "access_token": tradovate.access_token,
                        "refresh_token": tradovate.refresh_token,
                        "token_expires": tradovate.token_expires.isoformat() if tradovate.token_expires else None
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to close position"
                    }
        except Exception as e:
            logger.error(f"Close position error: {e}")
            return {
                "success": False,
                "error": f"Failed to close position: {str(e)}"
            }
    
    @staticmethod
    async def get_positions(account_id: int, username: str, password: str,
                           client_id: str, client_secret: str, token: str,
                           refresh_token: str, demo: bool = True) -> dict:
        """Get positions with token refresh"""
        try:
            async with TradovateIntegration(demo=demo) as tradovate:
                # Set tokens if provided
                if token:
                    tradovate.access_token = token
                    tradovate.refresh_token = refresh_token
                
                # Login if needed
                if not tradovate.access_token:
                    if not await tradovate.login_with_credentials(username, password, client_id, client_secret):
                        return {
                            "success": False,
                            "error": "Failed to authenticate with Tradovate"
                        }
                
                positions = await tradovate.get_positions(str(account_id))
                
                return {
                    "success": True,
                    "positions": positions,
                    "access_token": tradovate.access_token,
                    "refresh_token": tradovate.refresh_token,
                    "token_expires": tradovate.token_expires.isoformat() if tradovate.token_expires else None
                }
        except Exception as e:
            logger.error(f"Get positions error: {e}")
            return {
                "success": False,
                "error": f"Failed to get positions: {str(e)}"
            }
    
    @staticmethod
    def run_async(coro):
        """Run async function in sync context"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

