"""
PaperTradingEngine v3 — In-memory paper trading engine with MAE/MFE tracking.

Zero contact with broker execution pipeline. Uses FUTURES_SPECS from tv_price_service.py
for tick sizes and P&L calculation.

Interface:
    on_signal(payload)  — route webhook to entry/DCA/close/flip
    on_tick(symbol, price) — update MAE/MFE, check TP/SL/trail, auto-close
    get_state(account)  — full snapshot for dashboard broadcast
    get_mae_mfe_analysis(account) — analytics + auto-generated insights
"""

import json
import time
import uuid
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Import futures specs from existing price service
try:
    from tv_price_service import FUTURES_SPECS, get_futures_spec, calculate_pnl
except ImportError:
    logger.warning("tv_price_service not available, using built-in specs")
    FUTURES_SPECS = {
        'MNQ': {'tick_size': 0.25, 'tick_value': 0.50, 'point_value': 2.00, 'exchange': 'CME'},
        'MES': {'tick_size': 0.25, 'tick_value': 1.25, 'point_value': 5.00, 'exchange': 'CME'},
        'NQ':  {'tick_size': 0.25, 'tick_value': 5.00, 'point_value': 20.00, 'exchange': 'CME'},
        'ES':  {'tick_size': 0.25, 'tick_value': 12.50, 'point_value': 50.00, 'exchange': 'CME'},
    }

    def get_futures_spec(symbol):
        clean = symbol.upper()
        if ':' in clean:
            clean = clean.split(':')[-1]
        clean = clean.replace('1!', '').replace('!', '')
        clean_symbol = ''.join(c for c in clean if c.isalpha())
        if clean_symbol in FUTURES_SPECS:
            return FUTURES_SPECS[clean_symbol]
        for key in sorted(FUTURES_SPECS.keys(), key=len, reverse=True):
            if clean_symbol.startswith(key) or key.startswith(clean_symbol):
                return FUTURES_SPECS[key]
        return {'tick_size': 0.01, 'tick_value': 1.00, 'point_value': 1.00, 'exchange': 'UNKNOWN'}

    def calculate_pnl(symbol, entry_price, exit_price, quantity, side):
        spec = get_futures_spec(symbol)
        point_value = spec['point_value']
        if side.upper() in ['LONG', 'BUY']:
            points = exit_price - entry_price
        else:
            points = entry_price - exit_price
        return points * point_value * quantity


# Commission table (mirrors ultra_simple_server.py _PAPER_COMMISSION_PER_SIDE)
_COMMISSION_PER_SIDE = {
    'MNQ': 0.52, 'MES': 0.52, 'MYM': 0.52, 'M2K': 0.52, 'MGC': 0.52, 'MCL': 0.52, 'SIL': 0.52,
    'NQ': 1.29, 'ES': 1.29, 'YM': 1.29, 'RTY': 1.29, 'GC': 1.29, 'CL': 1.29, 'SI': 1.29,
}
_COMMISSION_DEFAULT = 0.52


def _symbol_root(symbol):
    """Extract symbol root from TV-style ticker (e.g., 'MNQ1!' -> 'MNQ')."""
    clean = symbol.upper()
    if ':' in clean:
        clean = clean.split(':')[-1]
    clean = clean.replace('1!', '').replace('!', '')
    return ''.join(c for c in clean if c.isalpha())


def _calc_commission(symbol, quantity):
    """Round-turn commission for a paper trade."""
    root = _symbol_root(symbol)
    per_side = _COMMISSION_PER_SIDE.get(root, _COMMISSION_DEFAULT)
    return quantity * per_side * 2


class PaperTradingEngine:
    """
    In-memory paper trading engine. Thread-safe.

    Tracks: positions, MAE/MFE, DCA legs, TP/SL/trail brackets.
    On every tick: updates excursion, checks bracket conditions, auto-closes.
    """

    def __init__(self, socketio=None, broadcast_namespace="/paper"):
        self._lock = threading.Lock()
        # account -> symbol -> position dict
        self._positions = {}
        # list of closed trades (most recent last)
        self._history = []
        # symbol -> last known price
        self._marks = {}
        # account -> cumulative realized PnL
        self._realized = {}
        self._socketio = socketio
        self._namespace = broadcast_namespace

    # ── Signal routing ──────────────────────────────────────────────────────

    def on_signal(self, payload):
        """Route incoming webhook signal to the appropriate handler."""
        account = str(payload.get("account", "default"))
        action = str(payload.get("action", "")).lower().strip()
        symbol = str(payload.get("ticker", payload.get("symbol", ""))).upper().strip()
        price = float(payload.get("price", payload.get("close", 0)))
        qty = int(payload.get("quantity", payload.get("contracts", 1)))
        comment = str(payload.get("comment", payload.get("message", "")))
        strategy_id = str(payload.get("strategy_id", payload.get("strategy", "")))

        # Bracket params
        tp = payload.get("tp")
        sl = payload.get("sl")
        trail_points = payload.get("trail_points", payload.get("trail"))
        trail_ticks = payload.get("trail_ticks")

        # Convert trail_ticks to trail_points if needed
        if trail_ticks is not None and trail_points is None:
            spec = get_futures_spec(symbol)
            trail_points = float(trail_ticks) * spec['tick_size']

        tp = float(tp) if tp is not None else None
        sl = float(sl) if sl is not None else None
        trail_points = float(trail_points) if trail_points is not None else None

        if not symbol or price <= 0:
            return {"status": "error", "message": "missing symbol or price"}

        # Update mark price
        self._marks[symbol] = price

        # Determine side from action
        side = None
        if action in ('buy', 'long'):
            side = 'long'
        elif action in ('sell', 'short'):
            side = 'short'

        # Close/exit/flatten actions
        if action in ('close', 'exit', 'flatten', 'flat'):
            return self._handle_exit(account, symbol, price, comment=comment)

        # Partial close
        reduce_qty = payload.get("reduce_qty")
        if reduce_qty is not None:
            return self._handle_partial_close(account, symbol, int(reduce_qty), price, comment)

        if side is None:
            return {"status": "error", "message": f"unknown action: {action}"}

        with self._lock:
            pos = self._get_position_locked(account, symbol)

            # No existing position -> fresh entry
            if pos is None:
                return self._open_position_locked(
                    account, symbol, side, qty, price, tp, sl,
                    trail_points, comment, strategy_id
                )

            # Same side -> DCA add
            if pos['side'] == side:
                return self._add_to_position_locked(
                    account, symbol, qty, price, comment
                )

            # Opposite side -> flip (close + re-enter)
            self._close_position_locked(account, symbol, price, comment="FLIP")
            return self._open_position_locked(
                account, symbol, side, qty, price, tp, sl,
                trail_points, comment, strategy_id
            )

    # ── Tick processing ─────────────────────────────────────────────────────

    def on_tick(self, symbol, price):
        """Update all open positions on this symbol with new price."""
        symbol = symbol.upper()
        if price <= 0:
            return
        self._marks[symbol] = price

        with self._lock:
            closed_accounts = []
            for account in list(self._positions.keys()):
                pos = self._positions.get(account, {}).get(symbol)
                if pos is None or pos.get('status') != 'open':
                    continue

                self._update_excursion_locked(pos, price)
                self._update_unrealized_locked(pos, price)
                pos['mark_price'] = price

                # Check brackets
                close_reason = self._check_brackets_locked(pos, price)
                if close_reason:
                    closed_accounts.append((account, close_reason))

            # Close triggered positions (outside position iteration)
            for account, reason in closed_accounts:
                self._close_position_locked(account, symbol, price, comment=f"AUTO:{reason}")

    # ── Position operations (must hold self._lock) ──────────────────────────

    def _get_position_locked(self, account, symbol):
        """Get open position or None."""
        acct = self._positions.get(account, {})
        pos = acct.get(symbol)
        if pos is not None and pos.get('status') == 'open':
            return pos
        return None

    def _get_position(self, account, symbol):
        """Thread-safe position getter for external use."""
        with self._lock:
            return self._get_position_locked(account, symbol)

    def _open_position_locked(self, account, symbol, side, qty, price,
                               tp=None, sl=None, trail_points=None,
                               comment="", strategy_id=""):
        """Open a new paper position."""
        if account not in self._positions:
            self._positions[account] = {}

        now = datetime.now(timezone.utc).isoformat()
        spec = get_futures_spec(symbol)
        tick_size = spec['tick_size']

        pos = {
            'id': str(uuid.uuid4())[:8],
            'symbol': symbol,
            'side': side,
            'qty': qty,
            'avg_entry': price,
            'mark_price': price,
            'unrealized_pnl': 0.0,
            'tp': tp,
            'sl': sl,
            'trail_points': trail_points,
            'trail_stop': None,
            'entry_time': now,
            'exit_time': None,
            'exit_price': None,
            'comment': comment,
            'exit_comment': '',
            'strategy_id': strategy_id,
            'status': 'open',
            'legs': [{'qty': qty, 'price': price, 'time': now, 'comment': comment}],
            'excursion': {
                'mae_points': 0.0,
                'mfe_points': 0.0,
                'mae_ticks': 0,
                'mfe_ticks': 0,
                'mae_dollars': 0.0,
                'mfe_dollars': 0.0,
                'mae_price': price,
                'mfe_price': price,
                'mae_time': now,
                'mfe_time': now,
                'capture_ratio': None,
                'efficiency': None,
                'highest_seen': price,
                'lowest_seen': price,
                'tick_count': 0,
            },
            '_tick_size': tick_size,
            '_point_value': spec['point_value'],
        }

        # Initialize trail stop if trailing
        if trail_points is not None:
            if side == 'long':
                pos['trail_stop'] = price - trail_points
            else:
                pos['trail_stop'] = price + trail_points

        self._positions[account][symbol] = pos
        logger.info(f"[PaperEngine] OPEN {side.upper()} {qty}x {symbol} @ {price} "
                    f"account={account} id={pos['id']}")
        return {"status": "opened", "id": pos['id'], "side": side, "qty": qty, "price": price}

    def _add_to_position_locked(self, account, symbol, qty, price, comment=""):
        """DCA: add contracts to existing position."""
        pos = self._get_position_locked(account, symbol)
        if pos is None:
            return {"status": "error", "message": "no position to add to"}

        old_qty = pos['qty']
        old_avg = pos['avg_entry']
        new_qty = old_qty + qty
        new_avg = ((old_avg * old_qty) + (price * qty)) / new_qty

        pos['qty'] = new_qty
        pos['avg_entry'] = new_avg
        pos['legs'].append({
            'qty': qty, 'price': price,
            'time': datetime.now(timezone.utc).isoformat(),
            'comment': comment or 'DCA'
        })

        logger.info(f"[PaperEngine] DCA +{qty}x {symbol} @ {price} "
                    f"(now {new_qty}x avg {new_avg:.2f}) account={account}")
        return {"status": "added", "qty": new_qty, "avg_entry": new_avg}

    def _close_position_locked(self, account, symbol, exit_price, comment=""):
        """Close entire position and move to history."""
        pos = self._get_position_locked(account, symbol)
        if pos is None:
            return

        now = datetime.now(timezone.utc).isoformat()
        pnl = calculate_pnl(symbol, pos['avg_entry'], exit_price, pos['qty'], pos['side'])
        commission = _calc_commission(symbol, pos['qty'])
        net_pnl = pnl - commission

        # Finalize excursion
        exc = pos['excursion']
        if exc['mfe_points'] > 0:
            current_pts = abs(exit_price - pos['avg_entry']) if pos['side'] == 'long' \
                else abs(pos['avg_entry'] - exit_price)
            # Capture = how much of MFE was captured (can be negative)
            side_mult = 1 if pos['side'] == 'long' else -1
            realized_pts = (exit_price - pos['avg_entry']) * side_mult
            exc['capture_ratio'] = round(realized_pts / exc['mfe_points'], 3) if exc['mfe_points'] > 0 else None
            # Efficiency = MFE / (MFE + MAE) — edge quality
            total_exc = exc['mfe_points'] + exc['mae_points']
            exc['efficiency'] = round(exc['mfe_points'] / total_exc, 3) if total_exc > 0 else None

        # Calculate hold time
        try:
            entry_dt = datetime.fromisoformat(pos['entry_time'].replace('Z', '+00:00'))
            exit_dt = datetime.now(timezone.utc)
            hold_time = int((exit_dt - entry_dt).total_seconds())
        except Exception:
            hold_time = 0

        # Build closed trade record
        trade = {
            'id': pos['id'],
            'symbol': symbol,
            'side': pos['side'],
            'qty': pos['qty'],
            'avg_entry': pos['avg_entry'],
            'exit_price': exit_price,
            'realized_pnl': round(net_pnl, 2),
            'gross_pnl': round(pnl, 2),
            'commission': round(commission, 2),
            'mae_points': exc['mae_points'],
            'mfe_points': exc['mfe_points'],
            'mae_ticks': exc['mae_ticks'],
            'mfe_ticks': exc['mfe_ticks'],
            'mae_dollars': exc['mae_dollars'],
            'mfe_dollars': exc['mfe_dollars'],
            'mae_price': exc['mae_price'],
            'mfe_price': exc['mfe_price'],
            'capture_ratio': exc['capture_ratio'],
            'efficiency': exc['efficiency'],
            'tick_count': exc['tick_count'],
            'highest_seen': exc['highest_seen'],
            'lowest_seen': exc['lowest_seen'],
            'entry_time': pos['entry_time'],
            'exit_time': now,
            'hold_time_seconds': hold_time,
            'comment': pos['comment'],
            'exit_comment': comment,
            'tp': pos['tp'],
            'sl': pos['sl'],
            'trail_points': pos['trail_points'],
            'legs': pos['legs'],
            'strategy_id': pos.get('strategy_id', ''),
            'status': 'closed',
            'source': 'webhook',
        }

        self._history.append(trade)

        # Track realized PnL
        if account not in self._realized:
            self._realized[account] = 0.0
        self._realized[account] += net_pnl

        # Remove from open positions
        self._positions[account].pop(symbol, None)

        logger.info(f"[PaperEngine] CLOSE {pos['side'].upper()} {pos['qty']}x {symbol} "
                    f"@ {exit_price} PnL=${net_pnl:.2f} ({comment}) account={account}")

    def _partial_close_locked(self, account, symbol, close_qty, exit_price, comment=""):
        """Partial close: reduce qty, record partial trade in history."""
        pos = self._get_position_locked(account, symbol)
        if pos is None:
            return

        close_qty = min(close_qty, pos['qty'])
        if close_qty >= pos['qty']:
            self._close_position_locked(account, symbol, exit_price, comment)
            return

        pnl = calculate_pnl(symbol, pos['avg_entry'], exit_price, close_qty, pos['side'])
        commission = _calc_commission(symbol, close_qty)
        net_pnl = pnl - commission

        now = datetime.now(timezone.utc).isoformat()
        exc = pos['excursion']

        trade = {
            'id': f"{pos['id']}-p{len(self._history)}",
            'symbol': symbol,
            'side': pos['side'],
            'qty': close_qty,
            'avg_entry': pos['avg_entry'],
            'exit_price': exit_price,
            'realized_pnl': round(net_pnl, 2),
            'gross_pnl': round(pnl, 2),
            'commission': round(commission, 2),
            'mae_points': exc['mae_points'],
            'mfe_points': exc['mfe_points'],
            'mae_ticks': exc['mae_ticks'],
            'mfe_ticks': exc['mfe_ticks'],
            'mae_dollars': exc['mae_dollars'],
            'mfe_dollars': exc['mfe_dollars'],
            'capture_ratio': exc.get('capture_ratio'),
            'efficiency': exc.get('efficiency'),
            'tick_count': exc['tick_count'],
            'entry_time': pos['entry_time'],
            'exit_time': now,
            'comment': pos['comment'],
            'exit_comment': f"PARTIAL:{comment}",
            'tp': pos['tp'],
            'sl': pos['sl'],
            'trail_points': pos['trail_points'],
            'legs': pos['legs'],
            'strategy_id': pos.get('strategy_id', ''),
            'status': 'closed',
            'source': 'webhook',
        }
        self._history.append(trade)

        if account not in self._realized:
            self._realized[account] = 0.0
        self._realized[account] += net_pnl

        pos['qty'] -= close_qty
        logger.info(f"[PaperEngine] PARTIAL CLOSE {close_qty}x {symbol} @ {exit_price} "
                    f"PnL=${net_pnl:.2f} remaining={pos['qty']} account={account}")

    # ── Excursion tracking ──────────────────────────────────────────────────

    def _update_excursion_locked(self, pos, price):
        """Update MAE/MFE for a position on new tick."""
        exc = pos['excursion']
        entry = pos['avg_entry']
        side = pos['side']
        tick_size = pos['_tick_size']
        point_value = pos['_point_value']
        qty = pos['qty']

        exc['tick_count'] += 1
        exc['highest_seen'] = max(exc['highest_seen'], price)
        exc['lowest_seen'] = min(exc['lowest_seen'], price)
        now = datetime.now(timezone.utc).isoformat()

        if side == 'long':
            favorable = max(0, price - entry)
            adverse = max(0, entry - price)
        else:
            favorable = max(0, entry - price)
            adverse = max(0, price - entry)

        # Update MFE
        if favorable > exc['mfe_points']:
            exc['mfe_points'] = round(favorable, 6)
            exc['mfe_ticks'] = int(round(favorable / tick_size)) if tick_size > 0 else 0
            exc['mfe_dollars'] = round(favorable * point_value * qty, 2)
            exc['mfe_price'] = price
            exc['mfe_time'] = now

        # Update MAE
        if adverse > exc['mae_points']:
            exc['mae_points'] = round(adverse, 6)
            exc['mae_ticks'] = int(round(adverse / tick_size)) if tick_size > 0 else 0
            exc['mae_dollars'] = round(adverse * point_value * qty, 2)
            exc['mae_price'] = price
            exc['mae_time'] = now

    def _update_unrealized_locked(self, pos, price):
        """Recalculate unrealized PnL at current mark."""
        pnl = calculate_pnl(pos['symbol'], pos['avg_entry'], price, pos['qty'], pos['side'])
        pos['unrealized_pnl'] = round(pnl, 2)

    # ── Bracket checking ────────────────────────────────────────────────────

    def _check_brackets_locked(self, pos, price):
        """Check TP/SL/trail conditions. Returns close reason or None."""
        side = pos['side']

        # Take Profit
        tp = pos.get('tp')
        if tp is not None:
            if (side == 'long' and price >= tp) or (side == 'short' and price <= tp):
                return 'TP'

        # Stop Loss
        sl = pos.get('sl')
        if sl is not None:
            if (side == 'long' and price <= sl) or (side == 'short' and price >= sl):
                return 'SL'

        # Trailing Stop
        trail_pts = pos.get('trail_points')
        trail_stop = pos.get('trail_stop')
        if trail_pts is not None and trail_stop is not None:
            # Update trail stop HWM
            if side == 'long':
                new_stop = price - trail_pts
                if new_stop > trail_stop:
                    pos['trail_stop'] = new_stop
                if price <= pos['trail_stop']:
                    return 'TRAIL'
            else:
                new_stop = price + trail_pts
                if new_stop < trail_stop:
                    pos['trail_stop'] = new_stop
                if price >= pos['trail_stop']:
                    return 'TRAIL'

        return None

    # ── Exit handlers ───────────────────────────────────────────────────────

    def _handle_exit(self, account, symbol, price, comment=""):
        """Close all open positions for a symbol."""
        with self._lock:
            pos = self._get_position_locked(account, symbol)
            if pos is None:
                return {"status": "no_position", "message": f"no open position for {symbol}"}
            self._close_position_locked(account, symbol, price, comment=comment or "CLOSE")
            return {"status": "closed", "symbol": symbol}

    def _handle_partial_close(self, account, symbol, reduce_qty, price, comment=""):
        """Reduce position size by reduce_qty contracts."""
        with self._lock:
            pos = self._get_position_locked(account, symbol)
            if pos is None:
                return {"status": "no_position"}
            self._partial_close_locked(account, symbol, reduce_qty, price, comment)
            return {"status": "partial_closed", "reduced_by": reduce_qty}

    # ── State snapshots ─────────────────────────────────────────────────────

    def get_state(self, account="default"):
        """Full state snapshot for dashboard."""
        with self._lock:
            open_positions = []
            acct_positions = self._positions.get(account, {})
            for symbol, pos in acct_positions.items():
                if pos is not None and pos.get('status') == 'open':
                    # Clean copy without internal fields
                    p = {k: v for k, v in pos.items() if not k.startswith('_')}
                    open_positions.append(p)

            # Recent history (last 200)
            history = [t for t in self._history[-200:]]

            # Stats
            closed_count = len(self._history)
            wins = sum(1 for t in self._history if t.get('realized_pnl', 0) > 0)
            total_realized = self._realized.get(account, 0.0)
            total_unrealized = sum(p.get('unrealized_pnl', 0) for p in open_positions)

            return {
                'open_positions': open_positions,
                'history': history,
                'marks': dict(self._marks),
                'stats': {
                    'open_count': len(open_positions),
                    'closed_count': closed_count,
                    'wins': wins,
                    'win_rate': round(wins / closed_count * 100, 1) if closed_count > 0 else 0,
                    'realized_pnl': round(total_realized, 2),
                    'unrealized_pnl': round(total_unrealized, 2),
                    'net_pnl': round(total_realized + total_unrealized, 2),
                },
                'account': account,
            }

    def get_mae_mfe_analysis(self, account="default", strategy_id=None):
        """Analytics: MAE/MFE distributions, strategy insights. Optional strategy_id filter."""
        trades = [t for t in self._history
                  if t.get('mae_points') is not None and t.get('mfe_points') is not None]
        if strategy_id:
            trades = [t for t in trades if t.get('strategy_id') == strategy_id]

        if not trades:
            return {'trades_analyzed': 0, 'insights': []}

        avg_mae = sum(t['mae_points'] for t in trades) / len(trades)
        avg_mfe = sum(t['mfe_points'] for t in trades) / len(trades)

        caps = [t['capture_ratio'] for t in trades if t.get('capture_ratio') is not None]
        avg_cap = sum(caps) / len(caps) if caps else None

        sorted_mae = sorted(trades, key=lambda t: t['mae_points'])
        p80_mae = sorted_mae[int(len(sorted_mae) * 0.8)]['mae_points'] if len(sorted_mae) >= 2 else 0

        sorted_mfe = sorted(trades, key=lambda t: t['mfe_points'])
        p50_mfe = sorted_mfe[int(len(sorted_mfe) * 0.5)]['mfe_points'] if len(sorted_mfe) >= 2 else 0

        winners = [t for t in trades if t.get('realized_pnl', 0) > 0]
        losers = [t for t in trades if t.get('realized_pnl', 0) < 0]
        w_mae = sum(t['mae_points'] for t in winners) / len(winners) if winners else 0
        l_mae = sum(t['mae_points'] for t in losers) / len(losers) if losers else 0

        # Auto insights
        insights = []
        if avg_cap is not None and avg_cap < 0.6:
            insights.append(
                f"Capture rate {int(avg_cap * 100)}% — exiting before moves complete. "
                f"Try {p50_mfe:.0f}-pt target or trailing stop."
            )
        if losers and winners and l_mae > w_mae * 1.5:
            insights.append(
                f"Loser MAE ({l_mae:.1f}pts) is {l_mae / w_mae:.1f}x winner MAE — "
                f"holding losers too long."
            )
        if p80_mae > 0:
            insights.append(
                f"{p80_mae:.1f}-pt stop survives 80% of your trades. "
                f"Minimum viable stop for this strategy."
            )
        if avg_mae > 0 and avg_mfe > avg_mae * 2:
            insights.append(
                f"Avg MFE ({avg_mfe:.1f}pts) is {avg_mfe / avg_mae:.1f}x avg MAE — "
                f"good edge. Keep running."
            )

        return {
            'trades_analyzed': len(trades),
            'avg_mae': round(avg_mae, 2),
            'avg_mfe': round(avg_mfe, 2),
            'avg_capture': round(avg_cap * 100, 1) if avg_cap is not None else None,
            'p80_mae': round(p80_mae, 2),
            'p50_mfe': round(p50_mfe, 2),
            'winner_mae': round(w_mae, 2),
            'loser_mae': round(l_mae, 2),
            'insights': insights,
            'mae_distribution': [
                {
                    'mae': round(t['mae_points'], 2),
                    'pnl': round(t.get('realized_pnl', 0), 2),
                    'win': t.get('realized_pnl', 0) > 0
                }
                for t in sorted_mae
            ],
        }
