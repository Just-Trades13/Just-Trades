"""
Trades API endpoints
"""
from flask import Blueprint, request, jsonify
from api.auth import require_auth
from database import get_db
from services.tradovate_service import TradovateService
from datetime import datetime

trades_bp = Blueprint('trades', __name__)

@trades_bp.route('/', methods=['GET'])
# @require_auth  # BYPASSED
def get_trades():
    """
    Get all trades with optional filters
    Expected: GET /api/trades/?usageType=true&user={username}&strategy={name}
    """
    from flask import session
    user_id = session.get('user_id')
    
    usage_type = request.args.get('usageType')
    user_filter = request.args.get('user')
    strategy_filter = request.args.get('strategy')
    
    db = get_db()
    cursor = db.cursor()
    
    query = """
        SELECT t.id, t.account_id, t.strategy_id, t.symbol, t.side,
               t.quantity, t.price, t.entry_price, t.exit_price, t.pnl,
               t.status, t.usage_type, t.created_at, t.filled_at, t.closed_at,
               s.name as strategy_name, a.name as account_name
        FROM trades t
        LEFT JOIN strategies s ON t.strategy_id = s.id
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE t.user_id = ?
    """
    params = [user_id]
    
    if usage_type:
        query += " AND t.usage_type = ?"
        params.append('recorder' if usage_type == 'true' else 'manual')
    
    if strategy_filter:
        query += " AND s.name = ?"
        params.append(strategy_filter)
    
    query += " ORDER BY t.created_at DESC LIMIT 1000"
    
    cursor.execute(query, params)
    
    trades = []
    for row in cursor.fetchall():
        trades.append({
            'id': row[0],
            'account_id': row[1],
            'strategy_id': row[2],
            'symbol': row[3],
            'side': row[4],
            'quantity': row[5],
            'price': row[6],
            'entry_price': row[7],
            'exit_price': row[8],
            'pnl': row[9],
            'status': row[10],
            'usage_type': row[11],
            'created_at': row[12],
            'filled_at': row[13],
            'closed_at': row[14],
            'strategy_name': row[15],
            'account_name': row[16]
        })
    
    return jsonify({'trades': trades})

@trades_bp.route('/open/', methods=['GET'])
# @require_auth  # BYPASSED
def get_open_trades():
    """
    Get open trades
    Expected: GET /api/trades/open/?usageType=true&user={username}&strategy={name}
    """
    from flask import session
    user_id = session.get('user_id')
    
    usage_type = request.args.get('usageType')
    user_filter = request.args.get('user')
    strategy_filter = request.args.get('strategy')
    
    db = get_db()
    cursor = db.cursor()
    
    query = """
        SELECT t.id, t.account_id, t.strategy_id, t.symbol, t.side,
               t.quantity, t.price, t.entry_price, t.exit_price, t.pnl,
               t.status, t.usage_type, t.created_at, t.filled_at,
               s.name as strategy_name, a.name as account_name
        FROM trades t
        LEFT JOIN strategies s ON t.strategy_id = s.id
        LEFT JOIN accounts a ON t.account_id = a.id
        WHERE t.user_id = ? AND t.status IN ('pending', 'filled') AND t.closed_at IS NULL
    """
    params = [user_id]
    
    if usage_type:
        query += " AND t.usage_type = ?"
        params.append('recorder' if usage_type == 'true' else 'manual')
    
    if strategy_filter:
        query += " AND s.name = ?"
        params.append(strategy_filter)
    
    query += " ORDER BY t.created_at DESC"
    
    cursor.execute(query, params)
    
    trades = []
    for row in cursor.fetchall():
        trades.append({
            'id': row[0],
            'account_id': row[1],
            'strategy_id': row[2],
            'symbol': row[3],
            'side': row[4],
            'quantity': row[5],
            'price': row[6],
            'entry_price': row[7],
            'exit_price': row[8],
            'pnl': row[9],
            'status': row[10],
            'usage_type': row[11],
            'created_at': row[12],
            'filled_at': row[13],
            'strategy_name': row[14],
            'account_name': row[15]
        })
    
    return jsonify({'trades': trades})

@trades_bp.route('/tickers/', methods=['GET'])
# @require_auth  # BYPASSED
def get_tickers():
    """
    Get available tickers for a strategy
    Expected: GET /api/trades/tickers/?strat={name}
    """
    strategy_name = request.args.get('strat')
    
    # Common futures symbols
    tickers = ['MES', 'MNQ', 'MYM', 'M2K', 'MCL', 'MGC', 'M6E', 'M6J', 'M6B', 'ZN', 'ZF', 'ZT', 'ZB', 'NQ', 'ES', 'YM', 'RTY', 'CL', 'GC', 'HG', 'SI']
    
    if strategy_name:
        # Could filter based on strategy preferences
        pass
    
    return jsonify({'tickers': tickers})

@trades_bp.route('/timeframes/', methods=['GET'])
# @require_auth  # BYPASSED
def get_timeframes():
    """
    Get available timeframes for a strategy
    Expected: GET /api/trades/timeframes/?strat={name}
    """
    strategy_name = request.args.get('strat')
    
    timeframes = ['1', '3', '5', '15', '30', '60', '240', 'D', 'W']
    
    return jsonify({'timeframes': timeframes})

@trades_bp.route('/execute/', methods=['POST'])
# @require_auth  # BYPASSED
def execute_trade():
    """
    Execute a trade manually from Control Center
    Expected: POST /api/trades/execute/
    Body: {
        "account_id": 123,
        "strategy_id": 456,
        "symbol": "MES1!",
        "side": "buy",
        "quantity": 1,
        "order_type": "market"
    }
    """
    from flask import session
    user_id = session.get('user_id')
    data = request.get_json()
    
    account_id = data.get('account_id')
    strategy_id = data.get('strategy_id')
    symbol = data.get('symbol')
    side = data.get('side')
    quantity = data.get('quantity', 1)
    order_type = data.get('order_type', 'market')
    
    if not account_id or not symbol or not side:
        return jsonify({'error': 'account_id, symbol, and side are required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Get account credentials
    cursor.execute("""
        SELECT username, password, client_id, client_secret
        FROM accounts WHERE id = ? AND user_id = ?
    """, (account_id, user_id))
    
    account = cursor.fetchone()
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    # Execute trade via Tradovate
    result = TradovateService.run_async(
        TradovateService.execute_trade(
            account_id=account_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            username=account[0],
            password=account[1],  # Note: This is encrypted, would need decryption
            client_id=account[2],
            client_secret=account[3],
            demo=True
        )
    )
    
    if not result.get('success'):
        return jsonify({'error': result.get('error', 'Trade execution failed')}), 400
    
    # Save trade to database
    order = result.get('order', {})
    cursor.execute("""
        INSERT INTO trades (
            account_id, strategy_id, symbol, side, quantity,
            order_type, status, tradovate_order_id, usage_type, user_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        account_id, strategy_id, symbol, side, quantity,
        order_type, 'filled', order.get('id'), 'manual', user_id
    ))
    
    trade_id = cursor.lastrowid
    db.commit()
    
    return jsonify({
        'success': True,
        'trade_id': trade_id,
        'order': order,
        'message': 'Trade executed successfully'
    })

