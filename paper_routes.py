"""
Paper Trading Routes Blueprint — Flask Blueprint + SocketIO namespace /paper.

Follows exact pattern from marketing_routes.py:
  paper_bp = Blueprint('paper', __name__)
  init_paper_routes(socketio, market_data_cache) — must be called before registration

Zero contact with broker_execution_queue, do_trade_for_account, process_webhook_directly.
"""

import json
import logging
from flask import Blueprint, request, jsonify, render_template, session
from flask_socketio import emit

logger = logging.getLogger(__name__)


def _get_user_id():
    """Get current user_id from session, or None if not logged in."""
    return session.get('user_id')


def _user_account(user_id):
    """Build the engine account key for a user_id."""
    if user_id is not None:
        return f"user_{user_id}"
    return "default"


def _lookup_user_by_token(webhook_token):
    """Look up user_id from a recorder webhook_token. Returns (user_id, recorder_id) or (None, None)."""
    try:
        from ultra_simple_server import get_db_connection, is_using_postgres
        conn = get_db_connection()
        cur = conn.cursor()
        ph = '%s' if is_using_postgres() else '?'
        cur.execute(f'SELECT id, user_id FROM recorders WHERE webhook_token = {ph}', (webhook_token,))
        row = cur.fetchone()
        conn.close()
        if row:
            if isinstance(row, dict):
                return row.get('user_id'), row.get('id')
            return row[1], row[0]
    except Exception as e:
        logger.warning(f"[PaperRoutes] Token lookup failed: {e}")
    return None, None

paper_bp = Blueprint('paper', __name__)

# Module-level state — set by init_paper_routes()
_pipeline = None
_socketio = None


def init_paper_routes(socketio, market_data_cache=None):
    """Initialize paper trading pipeline. Call before registering blueprint."""
    global _pipeline, _socketio
    _socketio = socketio

    from paper_pipeline import PaperPipeline
    _pipeline = PaperPipeline(socketio=socketio, broadcast_namespace="/paper")

    # Register SocketIO event handlers for /paper namespace
    _register_socketio_events(socketio)

    logger.info("[PaperRoutes] Paper trading blueprint initialized")


def get_paper_pipeline():
    """Expose pipeline for tick hook in ultra_simple_server.py."""
    return _pipeline


def _register_socketio_events(socketio):
    """Register SocketIO event handlers on /paper namespace."""

    @socketio.on('connect', namespace='/paper')
    def paper_connect():
        if _pipeline:
            uid = _get_user_id()
            account = _user_account(uid)
            state = _pipeline.get_state(account)
            emit('paper_state', state)

    @socketio.on('get_state', namespace='/paper')
    def paper_get_state(data=None):
        if _pipeline:
            uid = _get_user_id()
            account = _user_account(uid)
            emit('paper_state', _pipeline.get_state(account))

    @socketio.on('get_analysis', namespace='/paper')
    def paper_get_analysis(data=None):
        if _pipeline:
            uid = _get_user_id()
            account = _user_account(uid)
            strategy_id = (data or {}).get('strategy_id')
            emit('paper_analysis', _pipeline.get_analysis(account, strategy_id=strategy_id))

    @socketio.on('flatten_all', namespace='/paper')
    def paper_flatten(data=None):
        if _pipeline:
            uid = _get_user_id()
            account = _user_account(uid)
            _pipeline.flatten_all(account, reason="MANUAL_FLATTEN")
            emit('paper_state', _pipeline.get_state(account))


# ─── REST Endpoints ────────────────────────────────────────────────────────────

@paper_bp.route('/paper/signal', methods=['POST'])
def paper_signal():
    """Webhook entry point for paper trade signals (no token — uses payload account or session)."""
    if not _pipeline:
        return jsonify({"error": "paper trading not initialized"}), 503

    try:
        payload = request.get_json(force=True)
    except Exception:
        payload = None

    if not payload:
        return jsonify({"error": "no data received"}), 400

    # Use session user_id if logged in, otherwise anonymous
    uid = _get_user_id()
    result = _pipeline.on_webhook(payload, user_id=uid)
    return jsonify(result), 200


@paper_bp.route('/paper/signal/<webhook_token>', methods=['POST'])
def paper_signal_token(webhook_token):
    """Token-based webhook — same token as live /webhook/<token>, identifies user automatically."""
    if not _pipeline:
        return jsonify({"error": "paper trading not initialized"}), 503

    try:
        payload = request.get_json(force=True)
    except Exception:
        payload = None

    if not payload:
        return jsonify({"error": "no data received"}), 400

    user_id, recorder_id = _lookup_user_by_token(webhook_token)
    if user_id is None:
        return jsonify({"error": "invalid webhook token"}), 404

    # Enrich payload with recorder context
    payload['recorder_id'] = recorder_id
    result = _pipeline.on_webhook(payload, user_id=user_id)
    return jsonify(result), 200


@paper_bp.route('/paper/state', methods=['GET'])
def paper_state():
    """Get current paper trading state (session-authenticated, per-user)."""
    if not _pipeline:
        return jsonify({"error": "not initialized"}), 503
    uid = _get_user_id()
    account = _user_account(uid)
    return jsonify(_pipeline.get_state(account))


@paper_bp.route('/paper/analysis', methods=['GET'])
def paper_analysis():
    """Get MAE/MFE analytics (session-authenticated, per-user)."""
    if not _pipeline:
        return jsonify({"error": "not initialized"}), 503
    uid = _get_user_id()
    account = _user_account(uid)
    strategy_id = request.args.get('strategy_id', '').strip() or None
    return jsonify(_pipeline.get_analysis(account, strategy_id=strategy_id))


@paper_bp.route('/paper/strategies', methods=['GET'])
def paper_strategies():
    """List distinct strategy_ids (session-authenticated, per-user)."""
    if not _pipeline:
        return jsonify({"error": "not initialized"}), 503
    uid = _get_user_id()
    account = _user_account(uid)
    state = _pipeline.get_state(account)
    seen = set()
    for t in state.get('history', []):
        sid = t.get('strategy_id', '').strip()
        if sid:
            seen.add(sid)
    for p in state.get('open_positions', []):
        sid = p.get('strategy_id', '').strip()
        if sid:
            seen.add(sid)
    return jsonify({"strategies": sorted(seen)})


@paper_bp.route('/paper/history', methods=['GET'])
def paper_history():
    """Get closed trade history from DB (session-authenticated, per-user)."""
    if not _pipeline:
        return jsonify({"error": "not initialized"}), 503
    uid = _get_user_id()
    account = _user_account(uid)
    limit = int(request.args.get('limit', 500))
    history = _pipeline.db.load_history(account, limit, user_id=uid)
    return jsonify({"history": history, "count": len(history)})


@paper_bp.route('/paper/flatten', methods=['POST'])
def paper_flatten():
    """Emergency flatten all paper positions (session-authenticated, per-user)."""
    if not _pipeline:
        return jsonify({"error": "not initialized"}), 503
    uid = _get_user_id()
    account = _user_account(uid)
    _pipeline.flatten_all(account, reason="HTTP_FLATTEN")
    return jsonify({"status": "ok"})


@paper_bp.route('/paper-trading')
def paper_trading_page():
    """Serve paper trading dashboard (requires login)."""
    uid = _get_user_id()
    if uid is None:
        from flask import redirect, url_for, flash
        session['next_url'] = request.url
        flash('Please log in to access paper trading.', 'warning')
        return redirect(url_for('login'))
    return render_template('paper_trading.html')


# ─── Backtest Trades Endpoint ──────────────────────────────────────────────────

@paper_bp.route('/api/backtest/<int:import_id>/trades', methods=['GET'])
def backtest_trades(import_id):
    """Get individual trade rows from a backtest import."""
    try:
        from app.models import TVBacktestTrade
        from app.database import SessionLocal
        db = SessionLocal()
        trades = db.query(TVBacktestTrade).filter(
            TVBacktestTrade.import_id == import_id
        ).order_by(TVBacktestTrade.trade_num).all()

        result = []
        for t in trades:
            result.append({
                'id': t.id,
                'trade_num': t.trade_num,
                'type': t.type,
                'signal': t.signal,
                'date_time': t.date_time,
                'price': t.price,
                'contracts': t.contracts,
                'profit': t.profit,
                'cumulative_profit': t.cumulative_profit,
                'run_up': t.run_up,
                'drawdown': t.drawdown,
            })
        db.close()
        return jsonify({"success": True, "trades": result, "count": len(result)})
    except ImportError:
        return jsonify({"success": False, "error": "backtest models not available"}), 404
    except Exception as e:
        logger.error(f"[PaperRoutes] backtest trades error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
