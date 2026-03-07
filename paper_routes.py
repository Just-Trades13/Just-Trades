"""
Paper Trading Routes Blueprint — Flask Blueprint + SocketIO namespace /paper.

Follows exact pattern from marketing_routes.py:
  paper_bp = Blueprint('paper', __name__)
  init_paper_routes(socketio, market_data_cache) — must be called before registration

Zero contact with broker_execution_queue, do_trade_for_account, process_webhook_directly.
"""

import json
import logging
from flask import Blueprint, request, jsonify, render_template
from flask_socketio import emit

logger = logging.getLogger(__name__)

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
            state = _pipeline.get_state()
            emit('paper_state', state)

    @socketio.on('get_state', namespace='/paper')
    def paper_get_state(data=None):
        if _pipeline:
            account = (data or {}).get('account', 'default')
            emit('paper_state', _pipeline.get_state(account))

    @socketio.on('get_analysis', namespace='/paper')
    def paper_get_analysis(data=None):
        if _pipeline:
            account = (data or {}).get('account', 'default')
            emit('paper_analysis', _pipeline.get_analysis(account))

    @socketio.on('flatten_all', namespace='/paper')
    def paper_flatten(data=None):
        if _pipeline:
            account = (data or {}).get('account', 'default')
            _pipeline.flatten_all(account, reason="MANUAL_FLATTEN")
            emit('paper_state', _pipeline.get_state(account))


# ─── REST Endpoints ────────────────────────────────────────────────────────────

@paper_bp.route('/paper/signal', methods=['POST'])
def paper_signal():
    """Webhook entry point for paper trade signals (CSRF exempt)."""
    if not _pipeline:
        return jsonify({"error": "paper trading not initialized"}), 503

    try:
        payload = request.get_json(force=True)
    except Exception:
        payload = None

    if not payload:
        return jsonify({"error": "no data received"}), 400

    result = _pipeline.on_webhook(payload)
    return jsonify(result), 200


@paper_bp.route('/paper/state', methods=['GET'])
def paper_state():
    """Get current paper trading state."""
    if not _pipeline:
        return jsonify({"error": "not initialized"}), 503
    account = request.args.get('account', 'default')
    return jsonify(_pipeline.get_state(account))


@paper_bp.route('/paper/analysis', methods=['GET'])
def paper_analysis():
    """Get MAE/MFE analytics."""
    if not _pipeline:
        return jsonify({"error": "not initialized"}), 503
    account = request.args.get('account', 'default')
    return jsonify(_pipeline.get_analysis(account))


@paper_bp.route('/paper/history', methods=['GET'])
def paper_history():
    """Get closed trade history from DB (paginated)."""
    if not _pipeline:
        return jsonify({"error": "not initialized"}), 503
    account = request.args.get('account', 'default')
    limit = int(request.args.get('limit', 500))
    history = _pipeline.db.load_history(account, limit)
    return jsonify({"history": history, "count": len(history)})


@paper_bp.route('/paper/flatten', methods=['POST'])
def paper_flatten():
    """Emergency flatten all paper positions."""
    if not _pipeline:
        return jsonify({"error": "not initialized"}), 503
    data = request.get_json(force=True) or {}
    account = data.get('account', 'default')
    _pipeline.flatten_all(account, reason=data.get('reason', 'HTTP_FLATTEN'))
    return jsonify({"status": "ok"})


@paper_bp.route('/paper-trading')
def paper_trading_page():
    """Serve paper trading dashboard."""
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
