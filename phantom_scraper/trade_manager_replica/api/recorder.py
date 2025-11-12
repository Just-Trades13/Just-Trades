"""
Recorder API endpoints
"""
from flask import Blueprint, request, jsonify, session
from api.auth import require_auth
from database import get_db
from services.position_recorder import recorder

recorder_bp = Blueprint('recorder', __name__)

@recorder_bp.route('/start/<int:strategy_id>/', methods=['POST'])
@require_auth
def start_recording(strategy_id):
    """
    Start recording positions for a strategy
    Expected: POST /api/recorder/start/{strategy_id}/
    """
    user_id = session.get('user_id')
    db = get_db()
    cursor = db.cursor()
    
    # Verify strategy ownership
    cursor.execute("SELECT user_id FROM strategies WHERE id = ?", (strategy_id,))
    strategy = cursor.fetchone()
    if not strategy or strategy[0] != user_id:
        return jsonify({'error': 'Strategy not found'}), 404
    
    # Verify strategy has recording enabled and demo account
    cursor.execute("""
        SELECT recording_enabled, demo_account_id
        FROM strategies
        WHERE id = ?
    """, (strategy_id,))
    
    strategy_details = cursor.fetchone()
    if not strategy_details or not strategy_details[0]:
        return jsonify({'error': 'Recording not enabled for this strategy'}), 400
    
    if not strategy_details[1]:
        return jsonify({'error': 'Strategy has no demo account configured'}), 400
    
    # Start recording
    success = recorder.start_recording(strategy_id)
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Recording started for strategy {strategy_id}'
        })
    else:
        return jsonify({'error': 'Failed to start recording'}), 500

@recorder_bp.route('/stop/<int:strategy_id>/', methods=['POST'])
@require_auth
def stop_recording(strategy_id):
    """
    Stop recording positions for a strategy
    Expected: POST /api/recorder/stop/{strategy_id}/
    """
    user_id = session.get('user_id')
    db = get_db()
    cursor = db.cursor()
    
    # Verify strategy ownership
    cursor.execute("SELECT user_id FROM strategies WHERE id = ?", (strategy_id,))
    strategy = cursor.fetchone()
    if not strategy or strategy[0] != user_id:
        return jsonify({'error': 'Strategy not found'}), 404
    
    # Stop recording
    success = recorder.stop_recording(strategy_id)
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Recording stopped for strategy {strategy_id}'
        })
    else:
        return jsonify({'error': 'Recording not active for this strategy'}), 400

@recorder_bp.route('/positions/<int:strategy_id>/', methods=['GET'])
@require_auth
def get_recorded_positions(strategy_id):
    """
    Get recorded positions for a strategy
    Expected: GET /api/recorder/positions/{strategy_id}/
    """
    from flask import session
    from database import get_db
    
    user_id = session.get('user_id')
    db = get_db()
    cursor = db.cursor()
    
    # Verify strategy ownership
    cursor.execute("SELECT user_id FROM strategies WHERE id = ?", (strategy_id,))
    strategy = cursor.fetchone()
    if not strategy or strategy[0] != user_id:
        return jsonify({'error': 'Strategy not found'}), 404
    
    # Get positions
    cursor.execute("""
        SELECT id, symbol, side, quantity, entry_price, entry_timestamp,
               exit_price, exit_timestamp, exit_reason, pnl, pnl_percent,
               stop_loss_price, take_profit_price, status
        FROM recorded_positions
        WHERE strategy_id = ?
        ORDER BY entry_timestamp DESC
    """, (strategy_id,))
    
    positions = []
    for row in cursor.fetchall():
        positions.append({
            'id': row[0],
            'symbol': row[1],
            'side': row[2],
            'quantity': row[3],
            'entry_price': row[4],
            'entry_timestamp': row[5],
            'exit_price': row[6],
            'exit_timestamp': row[7],
            'exit_reason': row[8],
            'pnl': row[9],
            'pnl_percent': row[10],
            'stop_loss_price': row[11],
            'take_profit_price': row[12],
            'status': row[13]
        })
    
    return jsonify({'positions': positions})

