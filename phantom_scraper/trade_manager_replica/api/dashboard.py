"""
Dashboard API endpoints
"""
from flask import Blueprint, request, jsonify
from api.auth import require_auth
from database import get_db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/summary/', methods=['GET'])
# @require_auth  # BYPASSED
def get_dashboard_summary():
    """
    Get dashboard summary
    Expected: GET /api/dashboard/summary/
    """
    from flask import session
    user_id = session.get('user_id')
    
    db = get_db()
    cursor = db.cursor()
    
    # Get total strategies
    cursor.execute("SELECT COUNT(*) FROM strategies WHERE user_id = ?", (user_id,))
    total_strategies = cursor.fetchone()[0]
    
    # Get active positions
    cursor.execute("""
        SELECT COUNT(*) FROM recorded_positions
        WHERE strategy_id IN (SELECT id FROM strategies WHERE user_id = ?)
        AND status = 'open'
    """, (user_id,))
    active_positions = cursor.fetchone()[0]
    
    # Get total P&L
    cursor.execute("""
        SELECT COALESCE(SUM(pnl), 0) FROM recorded_positions
        WHERE strategy_id IN (SELECT id FROM strategies WHERE user_id = ?)
        AND status = 'closed'
    """, (user_id,))
    total_pnl = cursor.fetchone()[0] or 0
    
    # Get today's P&L
    cursor.execute("""
        SELECT COALESCE(SUM(pnl), 0) FROM recorded_positions
        WHERE strategy_id IN (SELECT id FROM strategies WHERE user_id = ?)
        AND status = 'closed'
        AND DATE(exit_timestamp) = DATE('now')
    """, (user_id,))
    today_pnl = cursor.fetchone()[0] or 0
    
    return jsonify({
        'total_strategies': total_strategies,
        'active_positions': active_positions,
        'total_pnl': float(total_pnl),
        'today_pnl': float(today_pnl)
    })

@dashboard_bp.route('/analytics/<int:strategy_id>/', methods=['GET'])
# @require_auth  # BYPASSED
def get_strategy_analytics(strategy_id):
    """
    Get strategy analytics
    Expected: GET /api/dashboard/analytics/{strategy_id}/
    """
    from flask import session
    user_id = session.get('user_id')
    
    db = get_db()
    cursor = db.cursor()
    
    # Verify strategy ownership
    cursor.execute("SELECT user_id FROM strategies WHERE id = ?", (strategy_id,))
    strategy = cursor.fetchone()
    if not strategy or strategy[0] != user_id:
        return jsonify({'error': 'Strategy not found'}), 404
    
    # Get closed positions
    cursor.execute("""
        SELECT pnl, exit_reason FROM recorded_positions
        WHERE strategy_id = ? AND status = 'closed'
    """, (strategy_id,))
    
    positions = cursor.fetchall()
    total_trades = len(positions)
    
    if total_trades == 0:
        return jsonify({
            'total_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'average_win': 0,
            'average_loss': 0,
            'largest_win': 0,
            'largest_loss': 0
        })
    
    wins = [p[0] for p in positions if p[0] and p[0] > 0]
    losses = [p[0] for p in positions if p[0] and p[0] < 0]
    
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    total_pnl = sum(p[0] for p in positions if p[0]) or 0
    average_win = sum(wins) / len(wins) if wins else 0
    average_loss = sum(losses) / len(losses) if losses else 0
    largest_win = max(wins) if wins else 0
    largest_loss = min(losses) if losses else 0
    
    return jsonify({
        'total_trades': total_trades,
        'win_rate': round(win_rate, 2),
        'total_pnl': float(total_pnl),
        'average_win': float(average_win),
        'average_loss': float(average_loss),
        'largest_win': float(largest_win),
        'largest_loss': float(largest_loss)
    })

