#!/usr/bin/env python3
"""
Multi-Server Architecture Example

This demonstrates how to set up multiple services similar to Trade Manager.
Each service runs on a different port and handles specific functionality.

Usage:
    python multi_server_example.py

This will start:
- Main Server (port 5000) - Frontend + routing
- API Service (port 5001) - REST API endpoints
- WebSocket Service (port 5002) - Real-time updates
- Trade Execution Service (port 5003) - Trade execution

Note: This is a simplified example. In production, you'd use:
- Process managers (systemd, supervisor)
- Reverse proxy (Nginx)
- Message queues (Redis, RabbitMQ)
- Proper error handling and logging
"""

import asyncio
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# SERVICE 1: API Service (Port 5001)
# ============================================================================

api_app = Flask(__name__)
CORS(api_app)

# In-memory storage (use database in production)
trades_db = []
strategies_db = []
accounts_db = []

@api_app.route('/api/dashboard/summary/', methods=['GET'])
def dashboard_summary():
    """Get dashboard summary statistics"""
    return jsonify({
        'active_positions': len([t for t in trades_db if t.get('status') == 'open']),
        'today_pnl': sum(t.get('pnl', 0) for t in trades_db if t.get('date') == datetime.now().date().isoformat()),
        'total_pnl': sum(t.get('pnl', 0) for t in trades_db),
        'total_strategies': len(strategies_db)
    })

@api_app.route('/api/trades/', methods=['GET'])
def get_trades():
    """Get all trades"""
    usage_type = request.args.get('usageType', 'false').lower() == 'true'
    return jsonify({'trades': trades_db})

@api_app.route('/api/trades/execute/', methods=['POST'])
def execute_trade():
    """Execute a trade (sends to trade execution service)"""
    data = request.json
    trade = {
        'id': len(trades_db) + 1,
        'strategy': data.get('strategy'),
        'symbol': data.get('ticker'),
        'side': data.get('side'),
        'quantity': data.get('quantity'),
        'price': data.get('price'),
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    }
    trades_db.append(trade)
    
    # In production, send to trade execution service via message queue
    # For now, simulate execution
    trade['status'] = 'filled'
    trade['pnl'] = 0.0
    
    return jsonify({'success': True, 'trade_id': trade['id']})

@api_app.route('/api/strategies/', methods=['GET'])
def get_strategies():
    """Get all strategies"""
    return jsonify({'strategies': strategies_db})

@api_app.route('/api/accounts/', methods=['GET'])
def get_accounts():
    """Get all accounts"""
    return jsonify(accounts_db)

def run_api_service():
    """Run API service on port 5001"""
    logger.info("🚀 Starting API Service on port 5001")
    api_app.run(port=5001, host='0.0.0.0', debug=False, threaded=True)

# ============================================================================
# SERVICE 2: WebSocket Service (Port 5002)
# ============================================================================

try:
    from flask_socketio import SocketIO, emit
    
    ws_app = Flask(__name__)
    CORS(ws_app)
    socketio = SocketIO(ws_app, cors_allowed_origins="*")
    
    @socketio.on('connect')
    def handle_connect():
        logger.info("✅ Client connected to WebSocket")
        emit('status', {'message': 'Connected to WebSocket service'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info("❌ Client disconnected from WebSocket")
    
    @socketio.on('subscribe')
    def handle_subscribe(data):
        """Subscribe to updates"""
        logger.info(f"📡 Client subscribed to: {data}")
        emit('subscribed', {'channels': data})
    
    def broadcast_position_update(position_data):
        """Broadcast position update to all connected clients"""
        socketio.emit('position_update', position_data)
    
    def broadcast_pnl_update(pnl_data):
        """Broadcast P&L update to all connected clients"""
        socketio.emit('pnl_update', pnl_data)
    
    def run_websocket_service():
        """Run WebSocket service on port 5002"""
        logger.info("🚀 Starting WebSocket Service on port 5002")
        socketio.run(ws_app, port=5002, host='0.0.0.0', debug=False)
    
    HAS_WEBSOCKET = True
except ImportError:
    logger.warning("⚠️  flask-socketio not installed. WebSocket service disabled.")
    logger.warning("   Install with: pip install flask-socketio")
    HAS_WEBSOCKET = False
    
    def run_websocket_service():
        logger.info("❌ WebSocket service not available (flask-socketio not installed)")

# ============================================================================
# SERVICE 3: Trade Execution Service (Port 5003)
# ============================================================================

trade_app = Flask(__name__)
CORS(trade_app)

@trade_app.route('/api/trades/execute/', methods=['POST'])
def execute_trade_service():
    """Execute trade via Tradovate API"""
    data = request.json
    
    # In production, this would:
    # 1. Connect to Tradovate API
    # 2. Place order
    # 3. Update database
    # 4. Emit WebSocket event
    
    logger.info(f"📈 Executing trade: {data}")
    
    # Simulate trade execution
    result = {
        'success': True,
        'order_id': f"ORD_{int(time.time())}",
        'status': 'filled',
        'filled_price': data.get('price'),
        'filled_quantity': data.get('quantity')
    }
    
    # In production, emit WebSocket event here
    # broadcast_position_update(result)
    
    return jsonify(result)

@trade_app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'trade_execution'})

def run_trade_service():
    """Run trade execution service on port 5003"""
    logger.info("🚀 Starting Trade Execution Service on port 5003")
    trade_app.run(port=5003, host='0.0.0.0', debug=False, threaded=True)

# ============================================================================
# SERVICE 4: Main Server (Port 5000) - Frontend + Routing
# ============================================================================

main_app = Flask(__name__)
CORS(main_app)

@main_app.route('/')
def index():
    """Main page - serves frontend"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Multi-Server Architecture Example</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .service { border: 1px solid #ddd; padding: 20px; margin: 20px 0; }
            .status { color: green; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>Multi-Server Architecture Example</h1>
        <p>This demonstrates Trade Manager's multi-server architecture.</p>
        
        <div class="service">
            <h2>Services Running:</h2>
            <ul>
                <li>Main Server: <span class="status">Port 5000</span></li>
                <li>API Service: <span class="status">Port 5001</span></li>
                <li>WebSocket Service: <span class="status">Port 5002</span></li>
                <li>Trade Execution Service: <span class="status">Port 5003</span></li>
            </ul>
        </div>
        
        <div class="service">
            <h2>Test Endpoints:</h2>
            <ul>
                <li><a href="http://localhost:5001/api/dashboard/summary/" target="_blank">Dashboard Summary</a></li>
                <li><a href="http://localhost:5001/api/trades/" target="_blank">Get Trades</a></li>
                <li><a href="http://localhost:5001/api/strategies/" target="_blank">Get Strategies</a></li>
                <li><a href="http://localhost:5001/api/accounts/" target="_blank">Get Accounts</a></li>
                <li><a href="http://localhost:5003/health" target="_blank">Trade Service Health</a></li>
            </ul>
        </div>
        
        <div class="service">
            <h2>WebSocket Test:</h2>
            <p>Open browser console and run:</p>
            <pre>
const ws = new WebSocket('ws://localhost:5002');
ws.onopen = () => console.log('Connected!');
ws.onmessage = (e) => console.log('Message:', e.data);
ws.send(JSON.stringify({event: 'subscribe', data: ['positions', 'pnl']}));
            </pre>
        </div>
    </body>
    </html>
    """

@main_app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_api(path):
    """Proxy API requests to API service"""
    import requests
    
    # Forward request to API service
    api_url = f"http://localhost:5001/api/{path}"
    
    try:
        if request.method == 'GET':
            response = requests.get(api_url, params=request.args)
        elif request.method == 'POST':
            response = requests.post(api_url, json=request.json)
        elif request.method == 'PUT':
            response = requests.put(api_url, json=request.json)
        elif request.method == 'DELETE':
            response = requests.delete(api_url)
        else:
            return jsonify({'error': 'Method not allowed'}), 405
        
        return response.json(), response.status_code
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'API service not available'}), 503

def run_main_server():
    """Run main server on port 5000"""
    logger.info("🚀 Starting Main Server on port 5000")
    main_app.run(port=5000, host='0.0.0.0', debug=False, threaded=True)

# ============================================================================
# Main: Start All Services
# ============================================================================

def main():
    """Start all services in separate threads"""
    print("=" * 80)
    print("🚀 Starting Multi-Server Architecture")
    print("=" * 80)
    print()
    print("Services:")
    print("  - Main Server:      http://localhost:5000")
    print("  - API Service:      http://localhost:5001")
    if HAS_WEBSOCKET:
        print("  - WebSocket Service: ws://localhost:5002")
    else:
        print("  - WebSocket Service: ❌ Not available (install flask-socketio)")
    print("  - Trade Service:    http://localhost:5003")
    print()
    print("Press Ctrl+C to stop all services")
    print("=" * 80)
    print()
    
    # Start services in separate threads
    threads = []
    
    # API Service
    api_thread = threading.Thread(target=run_api_service, daemon=True)
    api_thread.start()
    threads.append(api_thread)
    time.sleep(1)  # Give services time to start
    
    # WebSocket Service
    if HAS_WEBSOCKET:
        ws_thread = threading.Thread(target=run_websocket_service, daemon=True)
        ws_thread.start()
        threads.append(ws_thread)
        time.sleep(1)
    
    # Trade Execution Service
    trade_thread = threading.Thread(target=run_trade_service, daemon=True)
    trade_thread.start()
    threads.append(trade_thread)
    time.sleep(1)
    
    # Main Server (runs in main thread)
    try:
        run_main_server()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down all services...")
        print("✅ All services stopped")

if __name__ == "__main__":
    main()

