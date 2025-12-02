from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Base, Account, Strategy, Trade, WebhookLog, create_database, get_session
from tradovate_api import TradovateAPI
from datetime import datetime, timedelta
import json
import logging
from cryptography.fernet import Fernet
import base64
import os

logger = logging.getLogger(__name__)

class APIService:
    def __init__(self, app: Flask):
        self.app = app
        self.engine = create_database()
        self.Session = sessionmaker(bind=self.engine)
        
        # Initialize encryption key for sensitive data
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
        self.setup_routes()
    
    def _get_or_create_encryption_key(self):
        """Get or create encryption key for sensitive data"""
        key_file = 'encryption.key'
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            return key
    
    def _encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def setup_routes(self):
        """Setup API routes"""
        
        @self.app.route('/api/accounts', methods=['GET'])
        def get_accounts():
            """Get all accounts"""
            try:
                session = self.Session()
                accounts = session.query(Account).all()
                
                result = []
                for account in accounts:
                    account_data = {
                        'id': account.id,
                        'name': account.name,
                        'broker': account.broker,
                        'auth_type': account.auth_type,
                        'max_contracts': account.max_contracts,
                        'multiplier': account.multiplier,
                        'enabled': account.enabled,
                        'environment': account.environment,
                        'created_at': account.created_at.isoformat() if account.created_at else None
                    }
                    result.append(account_data)
                
                session.close()
                return jsonify({'success': True, 'accounts': result})
                
            except Exception as e:
                logger.error(f"Error getting accounts: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/accounts', methods=['POST'])
        def create_account():
            """Create a new account"""
            try:
                data = request.get_json()
                session = self.Session()
                
                # Create new account
                account = Account(
                    name=data['accountName'],
                    broker=data['broker'],
                    auth_type=data['authType'],
                    max_contracts=data.get('maxContracts', 1),
                    multiplier=data.get('multiplier', 1.0),
                    enabled=data.get('enabled', True)
                )
                
                if data['authType'] == 'credentials':
                    account.username = data['username']
                    account.password = self._encrypt_data(data['password'])
                    account.account_id = data.get('accountId')
                else:  # API authentication
                    account.api_key = data['apiKey']
                    account.api_secret = self._encrypt_data(data['apiSecret'])
                    account.api_endpoint = data['apiEndpoint']
                    account.environment = data.get('environment', 'demo')
                
                session.add(account)
                session.commit()
                
                # Test connection if Tradovate
                if account.broker == 'tradovate':
                    test_result = self._test_tradovate_connection(account)
                    if test_result['success']:
                        # Store tokens
                        account.tradovate_token = test_result.get('access_token')
                        account.tradovate_refresh_token = test_result.get('refresh_token')
                        if test_result.get('expires_at'):
                            account.token_expires_at = datetime.fromisoformat(test_result['expires_at'].replace('Z', '+00:00'))
                        session.commit()
                
                session.close()
                
                return jsonify({
                    'success': True, 
                    'message': 'Account created successfully',
                    'account_id': account.id
                })
                
            except Exception as e:
                logger.error(f"Error creating account: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/accounts/<int:account_id>/test', methods=['POST'])
        def test_account_connection(account_id):
            """Test account connection"""
            try:
                session = self.Session()
                account = session.query(Account).filter_by(id=account_id).first()
                
                if not account:
                    return jsonify({'success': False, 'error': 'Account not found'}), 404
                
                if account.broker == 'tradovate':
                    result = self._test_tradovate_connection(account)
                else:
                    result = {'success': False, 'error': 'Broker not supported for testing'}
                
                session.close()
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"Error testing account connection: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
        def delete_account(account_id):
            """Delete an account"""
            try:
                session = self.Session()
                account = session.query(Account).filter_by(id=account_id).first()
                
                if not account:
                    return jsonify({'success': False, 'error': 'Account not found'}), 404
                
                session.delete(account)
                session.commit()
                session.close()
                
                return jsonify({'success': True, 'message': 'Account deleted successfully'})
                
            except Exception as e:
                logger.error(f"Error deleting account: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/strategies', methods=['GET'])
        def get_strategies():
            """Get all strategies"""
            try:
                session = self.Session()
                strategies = session.query(Strategy).all()
                
                result = []
                for strategy in strategies:
                    strategy_data = {
                        'id': strategy.id,
                        'name': strategy.name,
                        'account_id': strategy.account_id,
                        'strat_type': strategy.strat_type,
                        'days_to_expiry': strategy.days_to_expiry,
                        'strike_offset': strategy.strike_offset,
                        'position_size': strategy.position_size,
                        'position_add': strategy.position_add,
                        'take_profit': strategy.take_profit,
                        'stop_loss': strategy.stop_loss,
                        'trim': strategy.trim,
                        'tpsl_units': strategy.tpsl_units,
                        'directional_strategy': strategy.directional_strategy,
                        'active': strategy.active,
                        'created_at': strategy.created_at.isoformat() if strategy.created_at else None
                    }
                    result.append(strategy_data)
                
                session.close()
                return jsonify({'success': True, 'strategies': result})
                
            except Exception as e:
                logger.error(f"Error getting strategies: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/strategies', methods=['POST'])
        def create_strategy():
            """Create a new strategy"""
            try:
                data = request.get_json()
                session = self.Session()
                
                strategy = Strategy(
                    name=data['name'],
                    account_id=data['account_id'],
                    strat_type=data.get('strat_type'),
                    days_to_expiry=data.get('days_to_expiry'),
                    strike_offset=data.get('strike_offset'),
                    position_size=data.get('position_size'),
                    position_add=data.get('position_add'),
                    take_profit=data.get('take_profit'),
                    stop_loss=data.get('stop_loss'),
                    trim=data.get('trim'),
                    tpsl_units=data.get('tpsl_units'),
                    directional_strategy=data.get('directional_strategy'),
                    active=data.get('active', True)
                )
                
                session.add(strategy)
                session.commit()
                session.close()
                
                return jsonify({
                    'success': True, 
                    'message': 'Strategy created successfully',
                    'strategy_id': strategy.id
                })
                
            except Exception as e:
                logger.error(f"Error creating strategy: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/trades', methods=['GET'])
        def get_trades():
            """Get all trades"""
            try:
                session = self.Session()
                trades = session.query(Trade).all()
                
                result = []
                for trade in trades:
                    trade_data = {
                        'id': trade.id,
                        'account_id': trade.account_id,
                        'strategy_id': trade.strategy_id,
                        'symbol': trade.symbol,
                        'side': trade.side,
                        'quantity': trade.quantity,
                        'price': trade.price,
                        'order_type': trade.order_type,
                        'status': trade.status,
                        'tradovate_order_id': trade.tradovate_order_id,
                        'entry_price': trade.entry_price,
                        'exit_price': trade.exit_price,
                        'pnl': trade.pnl,
                        'created_at': trade.created_at.isoformat() if trade.created_at else None,
                        'filled_at': trade.filled_at.isoformat() if trade.filled_at else None,
                        'closed_at': trade.closed_at.isoformat() if trade.closed_at else None
                    }
                    result.append(trade_data)
                
                session.close()
                return jsonify({'success': True, 'trades': result})
                
            except Exception as e:
                logger.error(f"Error getting trades: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/webhook', methods=['POST'])
        def handle_webhook():
            """Handle TradingView webhook"""
            try:
                data = request.get_json()
                
                # Log webhook
                session = self.Session()
                webhook_log = WebhookLog(webhook_data=json.dumps(data))
                session.add(webhook_log)
                session.commit()
                webhook_id = webhook_log.id
                
                # Process webhook
                result = self._process_webhook(data)
                
                # Update webhook log
                webhook_log.processed = True
                if not result['success']:
                    webhook_log.error_message = result['error']
                session.commit()
                session.close()
                
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"Error handling webhook: {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    def _test_tradovate_connection(self, account: Account) -> dict:
        """Test Tradovate connection for an account"""
        try:
            if account.auth_type == 'credentials':
                api = TradovateAPI(account.api_key or '', account.api_secret or '', account.environment or 'demo')
                result = api.authenticate(account.username, self._decrypt_data(account.password))
            else:
                api = TradovateAPI(account.api_key, self._decrypt_data(account.api_secret), account.environment or 'demo')
                result = api.test_connection()
            
            return result
            
        except Exception as e:
            logger.error(f"Error testing Tradovate connection: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _process_webhook(self, data: dict) -> dict:
        """Process TradingView webhook and execute trades"""
        try:
            # Extract trade information from webhook
            symbol = data.get('symbol', '').upper()
            action = data.get('action', '').lower()  # 'buy' or 'sell'
            quantity = int(data.get('quantity', 1))
            strategy_name = data.get('strategy', 'default')
            
            if not symbol or not action:
                return {'success': False, 'error': 'Missing required fields: symbol, action'}
            
            # Find active account for this symbol/strategy
            session = self.Session()
            account = session.query(Account).filter_by(enabled=True).first()
            
            if not account:
                return {'success': False, 'error': 'No active trading account found'}
            
            # Execute trade
            if account.broker == 'tradovate':
                trade_result = self._execute_tradovate_trade(account, symbol, action, quantity)
            else:
                return {'success': False, 'error': f'Broker {account.broker} not supported'}
            
            if trade_result['success']:
                # Log trade in database
                trade = Trade(
                    account_id=account.id,
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    order_type='market',
                    status='pending'
                )
                session.add(trade)
                session.commit()
                session.close()
                
                return {'success': True, 'message': f'Trade executed: {action.upper()} {quantity} {symbol}'}
            else:
                session.close()
                return trade_result
                
        except Exception as e:
            logger.error(f"Error processing webhook: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _execute_tradovate_trade(self, account: Account, symbol: str, side: str, quantity: int) -> dict:
        """Execute trade on Tradovate"""
        try:
            # Check if token needs refresh
            if account.token_expires_at and account.token_expires_at <= datetime.utcnow():
                if account.tradovate_refresh_token:
                    api = TradovateAPI(account.api_key, self._decrypt_data(account.api_secret), account.environment)
                    refresh_result = api.refresh_access_token(account.tradovate_refresh_token)
                    if refresh_result['success']:
                        # Update tokens in database
                        session = self.Session()
                        account.tradovate_token = refresh_result['access_token']
                        account.tradovate_refresh_token = refresh_result['refresh_token']
                        account.token_expires_at = datetime.fromisoformat(refresh_result['expires_at'].replace('Z', '+00:00'))
                        session.commit()
                        session.close()
                    else:
                        return {'success': False, 'error': 'Failed to refresh token'}
                else:
                    return {'success': False, 'error': 'Token expired and no refresh token available'}
            
            # Create API instance and set token
            api = TradovateAPI(account.api_key, self._decrypt_data(account.api_secret), account.environment)
            api.access_token = account.tradovate_token
            
            # Place order
            result = api.place_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type='market',
                account_id=account.account_id
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing Tradovate trade: {str(e)}")
            return {'success': False, 'error': str(e)}
