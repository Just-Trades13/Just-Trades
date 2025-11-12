"""
Strategies API endpoints
"""
from flask import Blueprint, request, jsonify
from api.auth import require_auth
from database import get_db

strategies_bp = Blueprint('strategies', __name__)

@strategies_bp.route('/', methods=['GET'])
# @require_auth  # BYPASSED
def get_strategies():
    """
    Get all strategies for user with optional filters
    Expected: GET /api/strategies/?style=at&manual=true&val=DirStrat
    Response: {"strategies": [{"name": "..."}, ...]} or full strategy objects
    """
    from flask import session
    import json
    user_id = session.get('user_id')
    
    style = request.args.get('style')  # 'at' for My Trader strategies
    manual = request.args.get('manual')  # 'true' for manual trading strategies
    val = request.args.get('val')  # Filter value (e.g., "DirStrat")
    
    db = get_db()
    cursor = db.cursor()
    
    # If val=DirStrat, return simplified list with just names (for dropdowns)
    if val == 'DirStrat':
        query = """
            SELECT name
            FROM strategies
            WHERE user_id = ?
            ORDER BY name
        """
        cursor.execute(query, (user_id,))
        strategies = [{'name': row[0]} for row in cursor.fetchall()]
        return jsonify({'strategies': strategies})
    
    # Otherwise, return full strategy objects
    query = """
        SELECT id, name, account_id, position_size, position_add,
               take_profit_json, stop_loss, tpsl_units, symbol,
               recording_enabled, demo_account_id, active,
               strat_type, days_to_expiry, strike_offset, trim,
               directional_strategy, manual_trading_enabled,
               enabled, private, algo_driven, delay_add, maxcons, leverage,
               alternate_name, description, discord_channel, sub_ticker, sub_timeframe, premium_filter,
               created_at, updated_at
        FROM strategies
        WHERE user_id = ?
    """
    params = [user_id]
    
    if style == 'at':
        # My Trader strategies - active strategies for live trading
        query += " AND active = 1 AND enabled = 1"
    
    if manual == 'true':
        # Manual trading strategies
        query += " AND manual_trading_enabled = 1"
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    
    strategies = []
    for row in cursor.fetchall():
        # Parse take_profit_json if it exists, otherwise use take_profit
        take_profit = row[5]  # take_profit_json column
        if take_profit:
            try:
                take_profit = json.loads(take_profit)
            except:
                # Fallback to old take_profit format
                take_profit = [take_profit] if take_profit else [0]
        else:
            take_profit = [0]
        
        strategies.append({
            'id': row[0],
            'name': row[1],
            'Strat_Name': row[1],  # API uses Strat_Name
            'account_id': row[2],
            'Position_Size': row[3],
            'Position_Add': row[4],
            'TakeProfit': take_profit if isinstance(take_profit, list) else [take_profit],
            'Stoploss': row[6],
            'TPSL_Units': row[7],
            'symbol': row[8],
            'Recorder': bool(row[9]),
            'demo_account_id': row[10],
            'active': bool(row[11]),
            'Strat_Type': row[12],
            'Days2Expo': row[13],
            'Strike_Offset': row[14],
            'Trim': row[15] if row[15] else [0],
            'DirStrat': row[16],
            'Manual': bool(row[17]),
            'Enabled': bool(row[18]),
            'Private': bool(row[19]),
            'AlgoDriven': bool(row[20]),
            'Delay_Add': row[21],
            'Maxcons': row[22],
            'Leverage': row[23],
            'Alternate_Name': row[24] or '',
            'Description': row[25] or '',
            'Discord_Channel': row[26] or '',
            'SubTicker': row[27] or 'ALL',
            'SubTimeFrame': row[28] or 'ALL',
            'PremiumFilter': row[29] or 0,
            'created_at': row[30],
            'updated_at': row[31]
        })
    
    return jsonify({'strategies': strategies})

@strategies_bp.route('/create/', methods=['POST'])
# @require_auth  # BYPASSED
def create_strategy():
    """
    Create new strategy
    Expected: POST /api/strategies/create/
    Body: See STRATEGY_CREATE_API_ANALYSIS.md for full structure
    Response: {"message": "...", "id": 15038, "webhook_key": "..."}
    """
    from flask import session
    import json
    import secrets
    data = request.get_json()
    user_id = session.get('user_id')
    
    # Validate required fields - API uses Strat_Name (not name)
    strat_name = data.get('Strat_Name') or data.get('name')
    if not strat_name:
        return jsonify({'error': 'Strategy name is required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Extract all fields matching the API structure
    # Handle nested objects: Accounts, TimeFilter, SLTP_Data
    # Handle arrays: TakeProfit, Trim
    
    # Generate webhook key
    webhook_key = secrets.token_urlsafe(24)
    
    # Store webhook key in database
    cursor.execute("""
        INSERT INTO strategies (
            user_id, name, strat_type, position_size, position_add,
            take_profit_json, stop_loss, tpsl_units, recording_enabled, active,
            days_to_expiry, strike_offset, directional_strategy, manual_trading_enabled,
            enabled, private, algo_driven, delay_add, maxcons, leverage,
            alternate_name, description, discord_channel, sub_ticker, sub_timeframe, premium_filter,
            webhook_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        strat_name,
        data.get('Strat_Type', 'Stock'),
        data.get('Position_Size', 1),
        data.get('Position_Add', 1),
        json.dumps(data.get('TakeProfit', [0])),  # Store as JSON
        data.get('Stoploss', 0),
        data.get('TPSL_Units', 'Ticks'),
        data.get('Recorder', True),
        data.get('Enabled', True),
        data.get('Days2Expo', 0),
        data.get('Strike_Offset', 0),
        data.get('DirStrat', ''),
        data.get('Manual', False),
        data.get('Enabled', True),
        data.get('Private', False),
        data.get('AlgoDriven', False),
        data.get('Delay_Add', 1),
        data.get('Maxcons', 0),
        data.get('Leverage', 1),
        data.get('Alternate_Name', ''),
        data.get('Description', ''),
        data.get('Discord_Channel', ''),
        data.get('SubTicker', 'ALL'),
        data.get('SubTimeFrame', 'ALL'),
        data.get('PremiumFilter', 0),
        webhook_key
    ))
    
    strategy_id = cursor.lastrowid
    db.commit()
    
    # Match exact API response structure
    return jsonify({
        'message': 'Strategy created successfully.',
        'id': strategy_id,
        'webhook_key': webhook_key
    })

@strategies_bp.route('/get-strat/', methods=['GET'])
# @require_auth  # BYPASSED
def get_strategy_by_id():
    """
    Get single strategy details
    Expected: GET /api/strategies/get-strat/?id=14330
    Response: Full strategy object matching API structure
    """
    from flask import session
    import json
    user_id = session.get('user_id')
    strategy_id = request.args.get('id')
    
    if not strategy_id:
        return jsonify({'error': 'Strategy ID is required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Get strategy with all fields
    cursor.execute("""
        SELECT id, name, account_id, position_size, position_add,
               take_profit_json, stop_loss, tpsl_units, symbol,
               recording_enabled, demo_account_id, active,
               strat_type, days_to_expiry, strike_offset, trim,
               directional_strategy, manual_trading_enabled,
               enabled, private, algo_driven, delay_add, maxcons, leverage,
               alternate_name, description, discord_channel, sub_ticker, sub_timeframe, premium_filter,
               created_at, updated_at
        FROM strategies
        WHERE id = ? AND user_id = ?
    """, (strategy_id, user_id))
    
    strategy = cursor.fetchone()
    if not strategy:
        return jsonify({'error': 'Strategy not found'}), 404
    
    # Parse take_profit_json if it exists
    take_profit = strategy[5]  # take_profit_json column
    if take_profit:
        try:
            take_profit = json.loads(take_profit)
        except:
            take_profit = [take_profit] if take_profit else [0]
    else:
        take_profit = [0]
    
    # Build response matching exact API structure
    return jsonify({
        'id': strategy[0],
        'Strat_Name': strategy[1],
        'Owner': 'J.T.M.J',  # TODO: Get from user table
        'Strat_Type': strategy[12] or 'Stock',
        'Days2Expo': strategy[13],
        'Strike_Offset': strategy[14],
        'Stoploss': str(strategy[6]) if strategy[6] else '0',
        'Position_Size': str(strategy[3]) if strategy[3] else '1',
        'Position_Add': str(strategy[4]) if strategy[4] else '1',
        'TakeProfit': take_profit if isinstance(take_profit, list) else [take_profit],
        'Trim': [strategy[15]] if strategy[15] else [0],
        'TradeTrim': '0',
        'TPSL_Units': strategy[7] or 'Ticks',
        'DirStrat': strategy[16] or '',
        'Description': strategy[25] or '',
        'Discord_Server': 'TRADE_MANAGER',
        'AlgoDriven': bool(strategy[20]),
        'Private': bool(strategy[19]),
        'Enabled': bool(strategy[18]),
        'SubTicker': strategy[27] or 'ALL',
        'PremiumFilter': strategy[29] or 0,
        'SubTimeFrame': strategy[28] or 'ALL',
        'Accounts': {'1': {'TM': ['', '', '']}},  # TODO: Get actual account mapping
        'TimeFilter': {'start1': None, 'stop1': None, 'start2': None, 'stop2': None},
        'IP_Address': '',
        'SLTP_Data': {
            'sl': str(strategy[6]) if strategy[6] else '0',
            'avgdn': 0,
            'SL_Type': 'Fixed',
            'SL_Units': 'Price',
            'avgdnAmnt': 1,
            'avgdnType': 'Ticks',
            'Trim_Units': 'Contracts'
        },
        'Recorder': bool(strategy[9]),
        'Manual': bool(strategy[17]),
        'Discord_Channel': strategy[26] or '',
        'Lock': None,
        'Profit': '0.00',
        'Delay_Add': str(strategy[21]) if strategy[21] else '1',
        'Maxcons': str(strategy[22]) if strategy[22] else '0',
        'UseLimits': False,
        'Alternate_Name': strategy[24] or '',
        'Linked_Strat': '',
        'Inverse': False,
        'IgnoreAlgoSpecs': False,
        'Leverage': str(strategy[23]) if strategy[23] else '1'
    })

@strategies_bp.route('/<int:strategy_id>/', methods=['GET'])
# @require_auth  # BYPASSED
def get_strategy(strategy_id):
    """
    Get strategy details with logs
    Expected: GET /api/strategies/{id}/
    """
    from flask import session
    user_id = session.get('user_id')
    
    db = get_db()
    cursor = db.cursor()
    
    # Get strategy
    cursor.execute("""
        SELECT id, name, account_id, position_size, position_add,
               take_profit, stop_loss, tpsl_units, symbol,
               recording_enabled, demo_account_id, active,
               created_at, updated_at
        FROM strategies
        WHERE id = ? AND user_id = ?
    """, (strategy_id, user_id))
    
    strategy = cursor.fetchone()
    if not strategy:
        return jsonify({'error': 'Strategy not found'}), 404
    
    # Get logs
    cursor.execute("""
        SELECT id, log_type, message, data, created_at
        FROM strategy_logs
        WHERE strategy_id = ?
        ORDER BY created_at DESC
        LIMIT 100
    """, (strategy_id,))
    
    logs = [
        {
            'id': row[0],
            'log_type': row[1],
            'message': row[2],
            'data': row[3],
            'created_at': row[4]
        }
        for row in cursor.fetchall()
    ]
    
    return jsonify({
        'strategy': {
            'id': strategy[0],
            'name': strategy[1],
            'account_id': strategy[2],
            'position_size': strategy[3],
            'position_add': strategy[4],
            'take_profit': strategy[5],
            'stop_loss': strategy[6],
            'tpsl_units': strategy[7],
            'symbol': strategy[8],
            'recording_enabled': bool(strategy[9]),
            'demo_account_id': strategy[10],
            'active': bool(strategy[11]),
            'created_at': strategy[12],
            'updated_at': strategy[13]
        },
        'logs': logs
    })

@strategies_bp.route('/update/', methods=['POST'])
# @require_auth  # BYPASSED
def update_strategy():
    """
    Update strategy (partial update - enable/disable, etc.)
    Expected: POST /api/strategies/update/
    Body: {"id": 14995, "Enabled": false, "Owner": "J.T.M.J"}
    Response: {"message": "...", "id": 14995, "webhook_key": "..."}
    """
    from flask import session
    import secrets
    user_id = session.get('user_id')
    data = request.get_json()
    
    strategy_id = data.get('id')
    if not strategy_id:
        return jsonify({'error': 'Strategy ID is required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Verify ownership
    cursor.execute("SELECT user_id FROM strategies WHERE id = ?", (strategy_id,))
    strategy = cursor.fetchone()
    if not strategy or strategy[0] != user_id:
        return jsonify({'error': 'Strategy not found'}), 404
    
    # Build update query - handle API field names
    updates = []
    values = []
    
    # Map API field names to database field names
    field_mapping = {
        'Enabled': 'enabled',
        'Strat_Name': 'name',
        'Position_Size': 'position_size',
        'Position_Add': 'position_add',
        'Stoploss': 'stop_loss',
        'TPSL_Units': 'tpsl_units',
        'Recorder': 'recording_enabled',
        'Manual': 'manual_trading_enabled',
        'Enabled': 'enabled',
        'Private': 'private',
        'AlgoDriven': 'algo_driven',
        'Delay_Add': 'delay_add',
        'Maxcons': 'maxcons',
        'Leverage': 'leverage'
    }
    
    for api_field, db_field in field_mapping.items():
        if api_field in data:
            updates.append(f"{db_field} = ?")
            values.append(data[api_field])
    
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(strategy_id)
    
    cursor.execute(f"""
        UPDATE strategies
        SET {', '.join(updates)}
        WHERE id = ?
    """, values)
    
    db.commit()
    
    # Generate webhook key (could be stored or generated)
    webhook_key = secrets.token_urlsafe(24)
    
    # Match exact API response structure
    return jsonify({
        'message': 'Strategy updated successfully.',
        'id': strategy_id,
        'webhook_key': webhook_key
    })

@strategies_bp.route('/<int:strategy_id>/', methods=['PUT'])
# @require_auth  # BYPASSED
def update_strategy_full(strategy_id):
    """
    Full strategy update (for editing all fields)
    Expected: PUT /api/strategies/{id}/
    """
    from flask import session
    user_id = session.get('user_id')
    data = request.get_json()
    
    db = get_db()
    cursor = db.cursor()
    
    # Verify ownership
    cursor.execute("SELECT user_id FROM strategies WHERE id = ?", (strategy_id,))
    strategy = cursor.fetchone()
    if not strategy or strategy[0] != user_id:
        return jsonify({'error': 'Strategy not found'}), 404
    
    # Build update query
    updates = []
    values = []
    
    for field in ['name', 'account_id', 'position_size', 'position_add',
                  'take_profit', 'stop_loss', 'tpsl_units', 'symbol',
                  'recording_enabled', 'demo_account_id', 'active']:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])
    
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(strategy_id)
    
    cursor.execute(f"""
        UPDATE strategies
        SET {', '.join(updates)}
        WHERE id = ?
    """, values)
    
    db.commit()
    
    return jsonify({'success': True, 'message': 'Strategy updated successfully'})

@strategies_bp.route('/<int:strategy_id>/', methods=['DELETE'])
# @require_auth  # BYPASSED
def delete_strategy(strategy_id):
    """
    Delete strategy
    Expected: DELETE /api/strategies/{id}/
    """
    from flask import session
    user_id = session.get('user_id')
    
    db = get_db()
    cursor = db.cursor()
    
    # Verify ownership
    cursor.execute("SELECT user_id FROM strategies WHERE id = ?", (strategy_id,))
    strategy = cursor.fetchone()
    if not strategy or strategy[0] != user_id:
        return jsonify({'error': 'Strategy not found'}), 404
    
    cursor.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
    db.commit()
    
    return jsonify({'success': True, 'message': 'Strategy deleted successfully'})

