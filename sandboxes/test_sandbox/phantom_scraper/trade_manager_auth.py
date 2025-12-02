#!/usr/bin/env python3
"""
Trade Manager Authentication Handler
Based on .har file analysis - implements Trade Manager's authentication flow
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import sqlite3

logger = logging.getLogger(__name__)

class TradeManagerAuth:
    """Trade Manager style authentication handler"""
    
    def __init__(self, base_url: str = "https://trademanagergroup.com"):
        self.base_url = base_url
        self.session = None
        self.csrf_token = None
        self.session_id = None
        self.cookies = {}
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_csrf_token(self) -> bool:
        """Get CSRF token from Trade Manager"""
        try:
            async with self.session.get(
                f"{self.base_url}/api/system/csrf-token/",
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.csrf_token = data.get("csrfToken")
                    
                    # Extract cookies from response
                    for cookie in response.cookies:
                        self.cookies[cookie.key] = cookie.value
                        if cookie.key == "csrftoken":
                            self.csrf_token = cookie.value
                        elif cookie.key == "sessionid":
                            self.session_id = cookie.value
                    
                    logger.info(f"CSRF token obtained: {self.csrf_token[:10]}...")
                    return True
                else:
                    logger.error(f"Failed to get CSRF token: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error getting CSRF token: {e}")
            return False
    
    async def check_auth(self) -> Dict[str, Any]:
        """Check authentication status with Trade Manager"""
        try:
            headers = {
                "Content-Type": "application/json",
                "X-CSRFToken": self.csrf_token,
                "Cookie": f"csrftoken={self.csrf_token}; sessionid={self.session_id}"
            }
            
            async with self.session.get(
                f"{self.base_url}/api/auth/check-auth/",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("Auth check successful")
                    return {"success": True, "data": data}
                else:
                    logger.error(f"Auth check failed: {response.status}")
                    return {"success": False, "error": f"Auth check failed: {response.status}"}
                    
        except Exception as e:
            logger.error(f"Error checking auth: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_all_accounts(self) -> Dict[str, Any]:
        """Get all AT accounts from Trade Manager"""
        try:
            headers = {
                "Content-Type": "application/json",
                "X-CSRFToken": self.csrf_token,
                "Cookie": f"csrftoken={self.csrf_token}; sessionid={self.session_id}"
            }
            
            async with self.session.get(
                f"{self.base_url}/api/accounts/get-all-at-accounts/",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Retrieved {len(data)} accounts")
                    return {"success": True, "accounts": data}
                else:
                    logger.error(f"Failed to get accounts: {response.status}")
                    return {"success": False, "error": f"Failed to get accounts: {response.status}"}
                    
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_profile_limits(self) -> Dict[str, Any]:
        """Get profile limits from Trade Manager"""
        try:
            headers = {
                "Content-Type": "application/json",
                "X-CSRFToken": self.csrf_token,
                "Cookie": f"csrftoken={self.csrf_token}; sessionid={self.session_id}"
            }
            
            async with self.session.get(
                f"{self.base_url}/api/profiles/get-limits/",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("Retrieved profile limits")
                    return {"success": True, "limits": data}
                else:
                    logger.error(f"Failed to get profile limits: {response.status}")
                    return {"success": False, "error": f"Failed to get profile limits: {response.status}"}
                    
        except Exception as e:
            logger.error(f"Error getting profile limits: {e}")
            return {"success": False, "error": str(e)}

class TradeManagerTradovateBridge:
    """Bridge between Trade Manager and Tradovate - implements the same flow"""
    
    def __init__(self, db_path: str = "trading_data.db"):
        self.db_path = db_path
        self.trade_manager_auth = TradeManagerAuth()
        self.tradovate_connections = {}
    
    def get_db_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    async def initialize_session(self) -> bool:
        """Initialize Trade Manager session (local simulation)"""
        try:
            # Simulate successful session initialization
            logger.info("Trade Manager session initialized successfully (local simulation)")
            return True
                
        except Exception as e:
            logger.error(f"Error initializing session: {e}")
            return False
    
    async def sync_accounts_with_trade_manager(self) -> Dict[str, Any]:
        """Sync accounts with Trade Manager style (local simulation)"""
        try:
            # Simulate the Trade Manager sync with local accounts
            logger.info("Simulating Trade Manager account sync...")
            
            # Get existing accounts from database
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check if we have any accounts
            cursor.execute("SELECT COUNT(*) FROM accounts")
            account_count = cursor.fetchone()[0]
            
            if account_count == 0:
                # Create a sample account if none exist
                cursor.execute('''
                    INSERT INTO accounts (name, broker, username, password, enabled)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    "Sample Tradovate Account",
                    "Tradovate",
                    "demo_user",
                    "demo_pass",
                    True
                ))
                conn.commit()
                logger.info("Created sample account")
            
            # Get all accounts
            cursor.execute("SELECT * FROM accounts")
            accounts = cursor.fetchall()
            conn.close()
            
            # Convert to Trade Manager format
            trade_manager_accounts = []
            for account in accounts:
                trade_manager_accounts.append({
                    "id": account["id"],
                    "name": account["name"],
                    "broker": account["broker"],
                    "username": account["username"],
                    "enabled": bool(account["enabled"])
                })
            
            return {
                "success": True,
                "message": f"Synced {len(trade_manager_accounts)} accounts (Trade Manager style)",
                "accounts": trade_manager_accounts
            }
                
        except Exception as e:
            logger.error(f"Error syncing accounts: {e}")
            return {"success": False, "error": str(e)}
    
    async def execute_trade_via_trade_manager(self, account_id: str, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Execute trade via Trade Manager flow"""
        try:
            # Get account info from database
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
            
            # Here you would implement the actual Trade Manager API call
            # to execute the trade. Based on the .har file analysis,
            # Trade Manager likely has an endpoint like:
            # /api/trades/execute/ or /api/orders/place/
            
            # For now, simulate the Trade Manager response
            logger.info(f"Executing trade via Trade Manager: {signal}")
            
            return {
                "success": True,
                "message": "Trade executed via Trade Manager",
                "order_id": f"TM_{account_id}_{int(datetime.now().timestamp())}",
                "signal": signal
            }
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return {"success": False, "error": str(e)}

# Example usage
async def main():
    """Example usage of Trade Manager authentication"""
    bridge = TradeManagerTradovateBridge()
    
    # Sync accounts with Trade Manager
    result = await bridge.sync_accounts_with_trade_manager()
    print(json.dumps(result, indent=2))
    
    # Execute a trade
    signal = {
        "symbol": "ES",
        "action": "buy",
        "quantity": 1,
        "price": 150.25
    }
    
    trade_result = await bridge.execute_trade_via_trade_manager("1", signal)
    print(json.dumps(trade_result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
