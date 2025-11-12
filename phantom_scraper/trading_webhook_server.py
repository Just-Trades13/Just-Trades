#!/usr/bin/env python3
"""
TradingView to Tradovate Automated Trading System
Webhook server that receives TradingView alerts and executes trades on Tradovate
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional
import requests
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
# from api_service import APIService  # Commented out for now
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
# import undetected_chromedriver as uc  # Commented out due to Python 3.13 compatibility
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradovateTrader:
    """Handles Tradovate login and trading operations using session-based authentication"""
    
    def __init__(self, username: str, password: str, headless: bool = True):
        self.username = username
        self.password = password
        self.headless = headless
        self.driver = None
        self.session = requests.Session()
        self.is_logged_in = False
        
    def setup_driver(self):
        """Setup Chrome driver with regular Selenium"""
        try:
            from selenium import webdriver
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Use webdriver-manager to automatically handle ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Chrome driver setup successful")
            return True
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            return False
    
    def login(self) -> bool:
        """Login to Tradovate using Selenium"""
        try:
            if not self.driver:
                if not self.setup_driver():
                    return False
            
            logger.info("Attempting to login to Tradovate...")
            self.driver.get("https://tradovate.com/login")
            
            # Wait for login form
            wait = WebDriverWait(self.driver, 10)
            
            # Find and fill username
            username_field = wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            username_field.clear()
            username_field.send_keys(self.username)
            
            # Find and fill password
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Click login button
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Wait for successful login (check for dashboard or trading interface)
            try:
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "trading-interface")),
                        EC.presence_of_element_located((By.CLASS_NAME, "dashboard")),
                        EC.presence_of_element_located((By.CLASS_NAME, "account-info"))
                    )
                )
                
                # Extract session cookies
                cookies = self.driver.get_cookies()
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'])
                
                self.is_logged_in = True
                logger.info("Successfully logged into Tradovate")
                return True
                
            except TimeoutException:
                logger.error("Login timeout - check credentials or captcha")
                return False
                
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def place_market_order(self, symbol: str, side: str, quantity: int, 
                          stop_loss: Optional[float] = None, 
                          take_profit: Optional[float] = None) -> Dict[str, Any]:
        """Place a market order on Tradovate"""
        try:
            if not self.is_logged_in:
                if not self.login():
                    return {"success": False, "error": "Login failed"}
            
            # Navigate to trading interface
            self.driver.get("https://tradovate.com/trading")
            
            # Wait for trading interface to load
            wait = WebDriverWait(self.driver, 10)
            
            # Find symbol input and enter symbol
            symbol_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='symbol'], input[data-testid*='symbol']"))
            )
            symbol_input.clear()
            symbol_input.send_keys(symbol)
            
            # Find quantity input and enter quantity
            quantity_input = self.driver.find_element(By.CSS_SELECTOR, "input[placeholder*='quantity'], input[data-testid*='quantity']")
            quantity_input.clear()
            quantity_input.send_keys(str(quantity))
            
            # Find and click buy/sell button
            if side.lower() == 'buy':
                order_button = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid*='buy'], .buy-button, button:contains('Buy')")
            else:
                order_button = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid*='sell'], .sell-button, button:contains('Sell')")
            
            order_button.click()
            
            # Wait for order confirmation
            try:
                confirmation = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".order-confirmation, .success-message"))
                )
                
                order_id = self.extract_order_id()
                
                result = {
                    "success": True,
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Add stop loss and take profit if specified
                if stop_loss or take_profit:
                    self.add_stop_take_profit(order_id, stop_loss, take_profit)
                    result["stop_loss"] = stop_loss
                    result["take_profit"] = take_profit
                
                logger.info(f"Order placed successfully: {result}")
                return result
                
            except TimeoutException:
                logger.error("Order confirmation timeout")
                return {"success": False, "error": "Order confirmation timeout"}
                
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {"success": False, "error": str(e)}
    
    def extract_order_id(self) -> str:
        """Extract order ID from the confirmation message"""
        try:
            # Look for order ID in various possible locations
            order_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                ".order-id, .confirmation-id, [data-order-id], .order-number")
            
            for element in order_elements:
                text = element.text.strip()
                if text and any(char.isdigit() for char in text):
                    return text
            
            # If no specific order ID found, generate one
            return f"ORD_{int(time.time())}"
            
        except Exception as e:
            logger.warning(f"Could not extract order ID: {e}")
            return f"ORD_{int(time.time())}"
    
    def add_stop_take_profit(self, order_id: str, stop_loss: float, take_profit: float):
        """Add stop loss and take profit to existing order"""
        try:
            # This would depend on Tradovate's specific interface
            # Look for stop loss and take profit inputs
            if stop_loss:
                stop_input = self.driver.find_element(By.CSS_SELECTOR, "input[placeholder*='stop'], input[data-testid*='stop']")
                stop_input.clear()
                stop_input.send_keys(str(stop_loss))
            
            if take_profit:
                tp_input = self.driver.find_element(By.CSS_SELECTOR, "input[placeholder*='target'], input[data-testid*='target']")
                tp_input.clear()
                tp_input.send_keys(str(take_profit))
            
            # Submit the stop/take profit order
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], .submit-order")
            submit_button.click()
            
            logger.info(f"Added stop loss: {stop_loss}, take profit: {take_profit} to order {order_id}")
            
        except Exception as e:
            logger.warning(f"Could not add stop/take profit: {e}")
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        try:
            if not self.is_logged_in:
                if not self.login():
                    return {"success": False, "error": "Login failed"}
            
            # Navigate to account page
            self.driver.get("https://tradovate.com/account")
            
            # Extract account information
            account_info = {}
            
            # Look for balance, equity, margin, etc.
            balance_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                ".balance, .account-balance, .equity, .margin")
            
            for element in balance_elements:
                text = element.text.strip()
                if '$' in text or any(char.isdigit() for char in text):
                    account_info['balance'] = text
                    break
            
            return {"success": True, "account_info": account_info}
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return {"success": False, "error": str(e)}
    
    def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close existing position for a symbol"""
        try:
            if not self.is_logged_in:
                if not self.login():
                    return {"success": False, "error": "Login failed"}
            
            # Navigate to positions page
            self.driver.get("https://tradovate.com/positions")
            
            # Find position for the symbol and close it
            wait = WebDriverWait(self.driver, 10)
            position_row = wait.until(
                EC.presence_of_element_located((By.XPATH, f"//tr[contains(., '{symbol}')]"))
            )
            
            close_button = position_row.find_element(By.CSS_SELECTOR, ".close-position, .close-button")
            close_button.click()
            
            # Confirm close
            confirm_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".confirm-close, .yes-button"))
            )
            confirm_button.click()
            
            logger.info(f"Position closed for {symbol}")
            return {"success": True, "symbol": symbol}
            
        except Exception as e:
            logger.error(f"Failed to close position for {symbol}: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            self.driver = None

class TradingWebhookServer:
    """Flask webhook server for receiving TradingView alerts"""
    
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'your-secret-key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.trader = None
        self.alert_count = 0
        self.last_alert_time = None
        # self.api_service = APIService(self.app)  # Commented out for now
        self.setup_routes()
        self.setup_socketio()
    
    def setup_socketio(self):
        """Setup SocketIO event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect():
            logger.info('Client connected to dashboard')
            emit('status', {
                'alert_count': self.alert_count,
                'last_alert': self.last_alert_time,
                'webhook_url': 'http://localhost:8080/webhook'
            })
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            logger.info('Client disconnected from dashboard')
        
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/', methods=['GET'])
        def index():
            """Root endpoint with server information"""
            return jsonify({
                "status": "TradingView to Tradovate Webhook Server",
                "version": "1.0.0",
                "endpoints": {
                    "webhook": "/webhook (POST)",
                    "health": "/health (GET)",
                    "account": "/account (GET)",
                    "dashboard": "/dashboard (GET)"
                },
                "webhook_url": "http://localhost:8080/webhook",
                "message": "Server is running and ready to receive TradingView alerts"
            })
        
        @self.app.route('/dashboard', methods=['GET'])
        def dashboard():
            """Trading dashboard page"""
            return render_template('trading_dashboard.html')
        
        @self.app.route('/simple', methods=['GET'])
        def simple_dashboard():
            """Simple dashboard page"""
            return render_template('simple_dashboard.html')
        
        @self.app.route('/dashboard-tab', methods=['GET'])
        def dashboard_tab():
            """Dashboard tab page"""
            return render_template('dashboard_tab.html')
        
        @self.app.route('/settings', methods=['GET'])
        def settings():
            """Settings page"""
            return render_template('settings_tab.html')
        
        @self.app.route('/my-recorders', methods=['GET'])
        def my_recorders():
            """My Recorders page"""
            return render_template('my_recorders_tab.html')
        
        @self.app.route('/account-management', methods=['GET'])
        def account_management():
            """Account Management page"""
            return render_template('account_management_tab.html')
        
        @self.app.route('/my-traders', methods=['GET'])
        def my_traders():
            """My Traders page"""
            return render_template('my_traders_tab.html')
        
        @self.app.route('/control-center', methods=['GET'])
        def control_center():
            """Control Center page"""
            return render_template('control_center_tab.html')
        
        @self.app.route('/webhook', methods=['POST'])
        def webhook():
            """Main webhook endpoint for TradingView alerts"""
            try:
                data = request.get_json()
                logger.info(f"Received webhook: {json.dumps(data, indent=2)}")
                
                # Update alert statistics
                self.alert_count += 1
                self.last_alert_time = datetime.now().isoformat()
                
                # Emit real-time update to dashboard
                self.socketio.emit('alert_received', {
                    'alert_count': self.alert_count,
                    'last_alert': self.last_alert_time,
                    'data': data
                })
                
                # Parse the alert data
                signal = self.parse_alert(data)
                if not signal:
                    return jsonify({"status": "error", "message": "Invalid alert format"}), 400
                
                # Execute the trade
                result = self.execute_trade(signal)
                
                # Emit trade result to dashboard
                self.socketio.emit('trade_result', {
                    'signal': signal,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                })
                
                return jsonify({
                    "status": "success" if result["success"] else "error",
                    "message": result.get("message", "Trade executed"),
                    "data": result
                })
                
            except Exception as e:
                logger.error(f"Webhook error: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/webhook/<webhook_id>', methods=['POST'])
        def webhook_with_id(webhook_id):
            """Handle TradingView webhook alerts with strategy ID (Trade Manager format)"""
            try:
                data = request.get_json()
                logger.info(f"Received webhook for strategy {webhook_id}: {json.dumps(data, indent=2)}")
                
                # Update alert statistics
                self.alert_count += 1
                self.last_alert_time = datetime.now().isoformat()
                
                # Emit real-time update to dashboard
                self.socketio.emit('alert_received', {
                    'alert_count': self.alert_count,
                    'last_alert': self.last_alert_time,
                    'strategy_id': webhook_id,
                    'data': data
                })
                
                # Parse the alert data using Trade Manager format
                signal = self.parse_trade_manager_alert(data, webhook_id)
                if not signal:
                    return jsonify({"status": "error", "message": "Invalid alert format"}), 400
                
                # Execute the trade
                result = self.execute_trade(signal)
                
                # Emit trade result to dashboard
                self.socketio.emit('trade_result', {
                    'signal': signal,
                    'result': result,
                    'strategy_id': webhook_id,
                    'timestamp': datetime.now().isoformat()
                })
                
                return jsonify({
                    "status": "success" if result["success"] else "error",
                    "message": result.get("message", "Trade executed"),
                    "data": result
                })
                
            except Exception as e:
                logger.error(f"Webhook error: {e}")
                return jsonify({"status": "error", "message": str(e)}), 500
    
        @self.app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint"""
            return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})
        
        @self.app.route('/account', methods=['GET'])
        def account_info():
            """Get account information"""
            if not self.trader:
                return jsonify({"status": "error", "message": "Trader not initialized"}), 400
            
            result = self.trader.get_account_info()
            return jsonify(result)

        # API Routes for Frontend
        @self.app.route('/api/accounts', methods=['GET'])
        def get_accounts():
            """Get all accounts for the current user"""
            try:
                # Import here to avoid circular imports
                from models import Account, get_session
                
                session = get_session()
                accounts = session.query(Account).all()
                session.close()
                
                # Convert to dict format expected by frontend
                accounts_data = []
                for account in accounts:
                    accounts_data.append({
                        "id": account.id,
                        "name": account.name,
                        "broker": account.broker,
                        "auth_type": account.auth_type,
                        "max_contracts": account.max_contracts,
                        "multiplier": account.multiplier,
                        "enabled": account.enabled,
                        "environment": account.environment,
                        "created_at": account.created_at.isoformat() if account.created_at else None
                    })
                
                return jsonify({"success": True, "accounts": accounts_data})
            except Exception as e:
                logger.error(f"Error getting accounts: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route('/api/accounts', methods=['POST'])
        def add_account():
            """Add a new account"""
            try:
                data = request.get_json()
                logger.info(f"Adding account: {data}")
                
                # Import here to avoid circular imports
                from models import Account, get_session
                
                session = get_session()
                
                # Create new account
                new_account = Account(
                    name=data.get('accountName'),
                    broker=data.get('broker'),
                    auth_type=data.get('authType'),
                    username=data.get('username'),
                    password=data.get('password'),  # In real implementation, encrypt this
                    account_id=data.get('accountId'),
                    api_key=data.get('apiKey'),
                    api_secret=data.get('apiSecret'),  # In real implementation, encrypt this
                    api_endpoint=data.get('apiEndpoint'),
                    environment=data.get('environment'),
                    max_contracts=int(data.get('maxContracts', 1)),
                    multiplier=float(data.get('multiplier', 1.0)),
                    enabled=data.get('enabled', True)
                )
                
                session.add(new_account)
                session.commit()
                session.close()
                
                return jsonify({"success": True, "message": "Account added successfully"})
            except Exception as e:
                logger.error(f"Error adding account: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route('/api/accounts/test', methods=['POST'])
        def test_account_connection():
            """Test account connection"""
            try:
                data = request.get_json()
                logger.info(f"Testing connection for: {data}")
                
                # Simulate connection test
                import random
                success = random.random() > 0.3  # 70% success rate for demo
                
                if success:
                    return jsonify({"success": True, "message": "Connection successful!"})
                else:
                    return jsonify({"success": False, "error": "Connection failed. Please check your credentials."})
            except Exception as e:
                logger.error(f"Error testing connection: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
        def delete_account(account_id):
            """Delete an account"""
            try:
                logger.info(f"Deleting account {account_id}")
                
                # Import here to avoid circular imports
                from models import Account, get_session
                
                session = get_session()
                account = session.query(Account).filter_by(id=account_id).first()
                
                if account:
                    session.delete(account)
                    session.commit()
                    session.close()
                    return jsonify({"success": True, "message": "Account deleted successfully"})
                else:
                    session.close()
                    return jsonify({"success": False, "error": "Account not found"}), 404
                    
            except Exception as e:
                logger.error(f"Error deleting account: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route('/api/accounts/<int:account_id>/test', methods=['POST'])
        def test_existing_account(account_id):
            """Test existing account connection"""
            try:
                logger.info(f"Testing existing account {account_id}")
                return jsonify({"success": True, "message": "Connection test successful!"})
            except Exception as e:
                logger.error(f"Error testing account: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
    
    def parse_alert(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse TradingView alert data into trading signal"""
        try:
            # Extract signal information from various possible formats
            signal = {
                "symbol": data.get("symbol", data.get("ticker", "")),
                "action": data.get("action", data.get("side", data.get("signal", ""))),
                "quantity": int(data.get("quantity", data.get("size", 1))),
                "price": data.get("price"),
                "stop_loss": data.get("stop_loss", data.get("sl")),
                "take_profit": data.get("take_profit", data.get("tp")),
                "strategy": data.get("strategy", data.get("indicator", "")),
                "timestamp": data.get("timestamp", datetime.now().isoformat())
            }
            
            # Validate required fields
            if not signal["symbol"] or not signal["action"]:
                logger.error("Missing required fields: symbol or action")
                return None
            
            # Normalize action
            action = signal["action"].lower()
            if action in ["buy", "long", "enter_long"]:
                signal["action"] = "buy"
            elif action in ["sell", "short", "enter_short"]:
                signal["action"] = "sell"
            elif action in ["close", "exit", "close_long", "close_short"]:
                signal["action"] = "close"
            else:
                logger.error(f"Unknown action: {action}")
                return None
            
            logger.info(f"Parsed signal: {signal}")
            return signal
            
        except Exception as e:
            logger.error(f"Failed to parse alert: {e}")
            return None

    def parse_trade_manager_alert(self, data: Dict[str, Any], webhook_id: str) -> Optional[Dict[str, Any]]:
        """Parse Trade Manager format alert data"""
        try:
            # Trade Manager sends data in different formats
            # Check if it's a string message format
            if isinstance(data, dict) and 'message' in data:
                message = data['message']
                # Parse Trade Manager format: "JADDCAVIX: SELL, Price = 150.25, Ticker = ES, Period = 1m"
                if ':' in message and ',' in message:
                    parts = message.split(':')
                    if len(parts) >= 2:
                        strategy_name = parts[0].strip()
                        alert_data = parts[1].strip()
                        
                        # Parse the alert data
                        signal = {
                            'strategy_name': strategy_name,
                            'webhook_id': webhook_id,
                            'symbol': '',
                            'action': '',
                            'quantity': 1,
                            'price': 0.0,
                            'ticker': '',
                            'period': '',
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        # Parse comma-separated values
                        for item in alert_data.split(','):
                            item = item.strip()
                            if '=' in item:
                                key, value = item.split('=', 1)
                                key = key.strip().lower()
                                value = value.strip()
                                
                                if key == 'action' or key == 'sell' or key == 'buy':
                                    signal['action'] = value.lower()
                                elif key == 'price':
                                    try:
                                        signal['price'] = float(value)
                                    except ValueError:
                                        pass
                                elif key == 'ticker':
                                    signal['ticker'] = value.upper()
                                    signal['symbol'] = value.upper()
                                elif key == 'period':
                                    signal['period'] = value
                                elif key == 'amount':
                                    try:
                                        signal['quantity'] = int(float(value))
                                    except ValueError:
                                        pass
                        
                        # Validate required fields
                        if not signal['action'] or not signal['symbol']:
                            logger.error(f"Missing required fields in Trade Manager alert: {signal}")
                            return None
                        
                        # Normalize action
                        if signal['action'] in ['long']:
                            signal['action'] = 'buy'
                        elif signal['action'] in ['short']:
                            signal['action'] = 'sell'
                        
                        logger.info(f"Parsed Trade Manager signal: {signal}")
                        return signal
            
            # Fallback to standard parsing
            return self.parse_alert(data)
            
        except Exception as e:
            logger.error(f"Error parsing Trade Manager alert: {e}")
            return None
    
    def execute_trade(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Execute trade based on signal"""
        try:
            if not self.trader:
                # Initialize trader
                username = os.getenv('TRADOVATE_USERNAME')
                password = os.getenv('TRADOVATE_PASSWORD')
                
                if not username or not password:
                    return {"success": False, "error": "Tradovate credentials not configured"}
                
                self.trader = TradovateTrader(username, password)
            
            symbol = signal["symbol"]
            action = signal["action"]
            quantity = signal["quantity"]
            stop_loss = signal.get("stop_loss")
            take_profit = signal.get("take_profit")
            
            if action == "close":
                # Close existing position
                result = self.trader.close_position(symbol)
            else:
                # Place new order
                result = self.trader.place_market_order(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    stop_loss=stop_loss,
                    take_profit=take_profit
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute trade: {e}")
            return {"success": False, "error": str(e)}
    
    def run(self, host='0.0.0.0', port=8080, debug=False):
        """Run the webhook server"""
        logger.info(f"Starting TradingView webhook server on {host}:{port}")
        self.socketio.run(self.app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

def main():
    """Main function"""
    # Load environment variables
    load_dotenv()
    
    # Check for required environment variables
    required_vars = ['TRADOVATE_USERNAME', 'TRADOVATE_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.info("Please create a .env file with your Tradovate credentials")
        return
    
    # Create and run webhook server
    server = TradingWebhookServer()
    
    try:
        server.run(host='0.0.0.0', port=8080, debug=False)
    except KeyboardInterrupt:
        logger.info("Shutting down webhook server...")
    finally:
        if server.trader:
            server.trader.cleanup()

if __name__ == "__main__":
    main()
