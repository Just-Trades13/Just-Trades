#!/usr/bin/env python3
"""
Simplified TradingView to Tradovate Webhook Server
Focus on core functionality: webhook processing and trade execution
"""

import json
import logging
import sqlite3
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Simple database setup
def init_db():
    """Initialize SQLite database with simple schema"""
    conn = sqlite3.connect('trading_data.db')
    cursor = conn.cursor()
    
    # Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            broker TEXT NOT NULL,
            username TEXT,
            password TEXT,
            api_key TEXT,
            api_secret TEXT,
            enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            symbol TEXT,
            action TEXT,
            quantity INTEGER,
            price REAL,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('trading_data.db')
    conn.row_factory = sqlite3.Row
    return conn

# Simple account management
@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts"""
    try:
        conn = get_db_connection()
        accounts = conn.execute('SELECT * FROM accounts').fetchall()
        conn.close()
        
        accounts_list = []
        for account in accounts:
            accounts_list.append({
                'id': account['id'],
                'name': account['name'],
                'broker': account['broker'],
                'enabled': bool(account['enabled']),
                'created_at': account['created_at']
            })
        
        return jsonify({'success': True, 'accounts': accounts_list})
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts', methods=['POST'])
def add_account():
    """Add new account"""
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO accounts (name, broker, username, password, api_key, api_secret, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('accountName'),
            data.get('broker'),
            data.get('username'),
            data.get('password'),
            data.get('apiKey'),
            data.get('apiSecret'),
            data.get('enabled', True)
        ))
        
        conn.commit()
        account_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'account_id': account_id, 'message': 'Account added successfully'})
    except Exception as e:
        logger.error(f"Error adding account: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Delete account"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Account deleted successfully'})
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/test', methods=['POST'])
def test_connection():
    """Test account connection (simplified)"""
    try:
        data = request.get_json()
        logger.info(f"Testing connection for: {data.get('accountName', 'Unknown')}")
        
        # Simple validation - in real implementation, test actual connection
        if data.get('username') and data.get('password'):
            return jsonify({'success': True, 'message': 'Connection test successful!'})
        else:
            return jsonify({'success': False, 'error': 'Missing credentials'})
    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Webhook processing
@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint"""
    try:
        data = request.get_json()
        logger.info(f"Received webhook: {data}")
        
        # Parse alert data
        signal = parse_alert(data)
        if not signal:
            return jsonify({'status': 'error', 'message': 'Invalid alert format'}), 400
        
        # Log the trade
        log_trade(signal)
        
        # In real implementation, execute trade here
        logger.info(f"Webhook processed successfully: {signal}")
        
        return jsonify({
            'status': 'success',
            'message': 'Webhook processed successfully',
            'signal': signal
        })
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/webhook/<webhook_id>', methods=['POST'])
def webhook_with_id(webhook_id):
    """Webhook with strategy ID"""
    try:
        data = request.get_json()
        logger.info(f"Received webhook for strategy {webhook_id}: {data}")
        
        # Parse alert data
        signal = parse_alert(data)
        if not signal:
            return jsonify({'status': 'error', 'message': 'Invalid alert format'}), 400
        
        signal['strategy_id'] = webhook_id
        
        # Log the trade
        log_trade(signal)
        
        # In real implementation, execute trade here
        logger.info(f"Would execute trade for strategy {webhook_id}: {signal}")
        
        return jsonify({
            'status': 'success',
            'message': 'Webhook processed successfully',
            'signal': signal
        })
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def parse_alert(data):
    """Parse TradingView alert data"""
    try:
        # Handle Trade Manager format
        if isinstance(data, dict) and 'message' in data:
            message = data['message']
            if ':' in message and ',' in message:
                parts = message.split(':')
                if len(parts) >= 2:
                    strategy_name = parts[0].strip()
                    alert_data = parts[1].strip()
                    
                    signal = {
                        'strategy_name': strategy_name,
                        'symbol': '',
                        'action': '',
                        'quantity': 1,
                        'price': 0.0,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Parse comma-separated values
                    for item in alert_data.split(','):
                        item = item.strip()
                        if '=' in item:
                            key, value = item.split('=', 1)
                            key = key.strip().lower()
                            value = value.strip()
                            
                            if key in ['action', 'sell', 'buy']:
                                signal['action'] = value.lower()
                            elif key == 'price':
                                try:
                                    signal['price'] = float(value)
                                except ValueError:
                                    pass
                            elif key == 'ticker':
                                signal['symbol'] = value.upper()
                            elif key == 'amount':
                                try:
                                    signal['quantity'] = int(float(value))
                                except ValueError:
                                    pass
                    
                    if signal['action'] and signal['symbol']:
                        return signal
        
        # Handle standard format
        signal = {
            'symbol': data.get('symbol', data.get('ticker', '')),
            'action': data.get('action', data.get('side', '')),
            'quantity': int(data.get('quantity', data.get('size', 1))),
            'price': data.get('price', 0),
            'timestamp': datetime.now().isoformat()
        }
        
        if signal['symbol'] and signal['action']:
            return signal
        
        return None
        
    except Exception as e:
        logger.error(f"Error parsing alert: {e}")
        return None

def log_trade(signal):
    """Log trade to database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (symbol, action, quantity, price, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            signal.get('symbol'),
            signal.get('action'),
            signal.get('quantity'),
            signal.get('price'),
            'processed'
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Trade logged: {signal}")
    except Exception as e:
        logger.error(f"Error logging trade: {e}")

# Simple routes
@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'status': 'Just.Trade Webhook Server',
        'version': '2.0.0',
        'endpoints': {
            'webhook': '/webhook (POST)',
            'webhook_id': '/webhook/{id} (POST)',
            'accounts': '/api/accounts (GET/POST)',
            'health': '/health (GET)'
        },
        'message': 'Server is running and ready to receive TradingView alerts'
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Simple dashboard"""
    return render_template('simple_dashboard.html')

@app.route('/accounts', methods=['GET'])
def accounts_page():
    """Simple accounts page"""
    return render_template('simple_accounts.html')

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Start server
    logger.info("Starting simplified trading webhook server on 0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
