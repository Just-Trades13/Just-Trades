"""
TradingView Webhook API endpoints
"""
from flask import Blueprint, request, jsonify
from database import get_db
from services.tradovate_service import TradovateService
from websocket_handlers import broadcast_trade_update
import logging
import re

logger = logging.getLogger(__name__)
webhook_bp = Blueprint('webhook', __name__)

def parse_tradingview_alert(alert_data):
    """
    Parse TradingView alert in Trade Manager format
    Format: "JADNQ: action, Price = X, Ticker = Y, Period = Z, Action = action, Amount = N, StopLoss = S, TakeProfit = T"
    """
    try:
        # Try to parse as JSON first
        if isinstance(alert_data, dict):
            # Extract from JSON structure
            action = alert_data.get('action', '').lower()
            price = float(alert_data.get('price', 0))
            ticker = alert_data.get('ticker', '').upper()
            amount = int(alert_data.get('amount', 1))
            stop_loss = alert_data.get('stopLoss') or alert_data.get('StopLoss')
            take_profit = alert_data.get('takeProfit') or alert_data.get('TakeProfit')
            
            # Map action to Trade Manager format
            if action in ['long', 'buy']:
                action = 'buy'
            elif action in ['short', 'sell']:
                action = 'sell'
            elif action in ['flat', 'close']:
                action = 'close'
            
            return {
                'action': action,
                'price': price,
                'ticker': ticker,
                'amount': amount,
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
        
        # Parse from string format
        alert_text = str(alert_data)
        
        # Extract strategy name (e.g., "JADNQ")
        strategy_match = re.search(r'([A-Z]+):', alert_text)
        strategy_name = strategy_match.group(1) if strategy_match else None
        
        # Extract action
        action_match = re.search(r'Action\s*=\s*(\w+)', alert_text, re.IGNORECASE)
        if not action_match:
            action_match = re.search(r'([a-z]+):', alert_text)
        action = action_match.group(1).lower() if action_match else None
        
        # Map action
        if action in ['long', 'buy']:
            action = 'buy'
        elif action in ['short', 'sell']:
            action = 'sell'
        elif action in ['flat', 'close']:
            action = 'close'
        
        # Extract price
        price_match = re.search(r'Price\s*=\s*([\d.]+)', alert_text, re.IGNORECASE)
        price = float(price_match.group(1)) if price_match else 0
        
        # Extract ticker
        ticker_match = re.search(r'Ticker\s*=\s*(\w+)', alert_text, re.IGNORECASE)
        ticker = ticker_match.group(1).upper() if ticker_match else None
        
        # Extract amount
        amount_match = re.search(r'Amount\s*=\s*(\d+)', alert_text, re.IGNORECASE)
        amount = int(amount_match.group(1)) if amount_match else 1
        
        # Extract stop loss
        sl_match = re.search(r'StopLoss\s*=\s*([\d.]+)', alert_text, re.IGNORECASE)
        stop_loss = float(sl_match.group(1)) if sl_match else None
        
        # Extract take profit
        tp_match = re.search(r'TakeProfit\s*=\s*([\d.]+)', alert_text, re.IGNORECASE)
        take_profit = float(tp_match.group(1)) if tp_match else None
        
        return {
            'strategy_name': strategy_name,
            'action': action,
            'price': price,
            'ticker': ticker,
            'amount': amount,
            'stop_loss': stop_loss,
            'take_profit': take_profit
        }
    
    except Exception as e:
        logger.error(f"Error parsing alert: {e}")
        return None

@webhook_bp.route('/<strategy_id>', methods=['POST'])
def webhook_handler(strategy_id):
    """
    Handle TradingView webhook for a specific strategy
    Expected: POST /api/webhook/{strategy_id}
    """
    try:
        data = request.get_json() or request.form.to_dict()
        logger.info(f"Received webhook for strategy {strategy_id}: {data}")
        
        # Parse alert
        parsed = parse_tradingview_alert(data)
        if not parsed:
            return jsonify({
                'status': 'error',
                'message': 'Invalid alert format'
            }), 400
        
        # Get strategy from database
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id, account_id, symbol, position_size, take_profit, stop_loss,
                   tpsl_units, active
            FROM strategies
            WHERE id = ? AND active = 1
        """, (strategy_id,))
        
        strategy = cursor.fetchone()
        if not strategy:
            logger.warning(f"Strategy {strategy_id} not found or inactive")
            return jsonify({
                'status': 'error',
                'message': 'Strategy not found or inactive'
            }), 404
        
        strategy_id_db, account_id, symbol, position_size, take_profit, stop_loss, tpsl_units, active = strategy
        
        # Verify symbol matches
        if parsed.get('ticker') and parsed['ticker'] != symbol:
            logger.warning(f"Symbol mismatch: alert={parsed['ticker']}, strategy={symbol}")
        
        # Get account credentials
        cursor.execute("""
            SELECT username, password, client_id, client_secret,
                   tradovate_token, tradovate_refresh_token
            FROM accounts
            WHERE id = ?
        """, (account_id,))
        
        account = cursor.fetchone()
        if not account:
            return jsonify({
                'status': 'error',
                'message': 'Account not found'
            }), 404
        
        username, password, client_id, client_secret, token, refresh_token = account
        
        # Execute trade
        tradovate = TradovateService()
        action = parsed.get('action')
        quantity = parsed.get('amount', position_size)
        price = parsed.get('price')
        
        if action == 'close':
            # Close all positions for this symbol
            result = TradovateService.run_async(
                tradovate.close_position(account_id, username, password, client_id, 
                                       client_secret, token, refresh_token, symbol)
            )
        elif action in ['buy', 'sell']:
            # Place market order
            order_type = 'Market'
            side = 'Buy' if action == 'buy' else 'Sell'
            
            result = TradovateService.run_async(
                tradovate.place_order(
                    account_id, username, password, client_id, client_secret,
                    token, refresh_token, symbol, side, quantity, order_type, price
                )
            )
        else:
            return jsonify({
                'status': 'error',
                'message': f'Invalid action: {action}'
            }), 400
        
        # Log webhook
        cursor.execute("""
            INSERT INTO webhook_logs (strategy_id, payload, response, status_code)
            VALUES (?, ?, ?, ?)
        """, (
            strategy_id_db,
            str(data),
            str(result),
            200 if result.get('success') else 500
        ))
        
        # Log trade
        if result.get('success'):
            cursor.execute("""
                INSERT INTO trades (
                    account_id, strategy_id, symbol, side, quantity,
                    price, order_type, status, tradovate_order_id, usage_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_id, strategy_id_db, symbol, action, quantity,
                price, 'market', 'filled', result.get('order_id'), 'webhook'
            ))
            
            # Log strategy log
            cursor.execute("""
                INSERT INTO strategy_logs (strategy_id, log_type, message, data)
                VALUES (?, ?, ?, ?)
            """, (
                strategy_id_db,
                'trade_executed',
                f'Trade executed: {action} {quantity} {symbol}',
                str(result)
            ))
        
        db.commit()
        
        # Broadcast update
        broadcast_trade_update(
            None,  # socketio will be injected
            strategy_id_db,
            {
                'action': action,
                'symbol': symbol,
                'quantity': quantity,
                'result': result
            }
        )
        
        if result.get('success'):
            return jsonify({
                'status': 'success',
                'message': 'Trade executed successfully',
                'data': result
            })
        else:
            return jsonify({
                'status': 'error',
                'message': result.get('error', 'Trade execution failed'),
                'data': result
            }), 500
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

