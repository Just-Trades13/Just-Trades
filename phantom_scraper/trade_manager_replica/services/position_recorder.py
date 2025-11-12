"""
Position Recorder Service
Background service that polls Tradovate demo accounts and matches positions to strategies
"""

import threading
import time
import logging
from datetime import datetime
from database import get_db
from services.tradovate_service import TradovateService
from websocket_handlers import broadcast_position_update

logger = logging.getLogger(__name__)

class PositionRecorder:
    """Service to record positions from demo accounts and match them to strategies"""
    
    def __init__(self):
        self.running = False
        self.recording_strategies = {}  # strategy_id -> thread
        self.poll_interval = 30  # seconds
    
    def start_recording(self, strategy_id):
        """Start recording positions for a strategy"""
        if strategy_id in self.recording_strategies:
            logger.warning(f"Strategy {strategy_id} is already being recorded")
            return False
        
        thread = threading.Thread(
            target=self._record_loop,
            args=(strategy_id,),
            daemon=True
        )
        thread.start()
        self.recording_strategies[strategy_id] = thread
        logger.info(f"Started recording for strategy {strategy_id}")
        return True
    
    def stop_recording(self, strategy_id):
        """Stop recording positions for a strategy"""
        if strategy_id not in self.recording_strategies:
            return False
        
        # Mark as stopped (thread will check this)
        self.running = False
        del self.recording_strategies[strategy_id]
        logger.info(f"Stopped recording for strategy {strategy_id}")
        return True
    
    def _record_loop(self, strategy_id):
        """Main recording loop for a strategy"""
        db = get_db()
        cursor = db.cursor()
        
        # Get strategy details
        cursor.execute("""
            SELECT demo_account_id, symbol, account_id, user_id
            FROM strategies
            WHERE id = ? AND recording_enabled = 1
        """, (strategy_id,))
        
        strategy = cursor.fetchone()
        if not strategy:
            logger.error(f"Strategy {strategy_id} not found or recording disabled")
            return
        
        demo_account_id, symbol, account_id, user_id = strategy
        
        if not demo_account_id:
            logger.error(f"Strategy {strategy_id} has no demo account configured")
            return
        
        # Get account credentials
        cursor.execute("""
            SELECT username, password, client_id, client_secret,
                   tradovate_token, tradovate_refresh_token
            FROM accounts
            WHERE id = ?
        """, (demo_account_id,))
        
        account = cursor.fetchone()
        if not account:
            logger.error(f"Account {demo_account_id} not found")
            return
        
        username, password, client_id, client_secret, token, refresh_token = account
        
        # Initialize Tradovate service
        tradovate = TradovateService()
        
        # Track known positions
        known_positions = {}  # position_id -> position data
        
        self.running = True
        
        while self.running and strategy_id in self.recording_strategies:
            try:
                # Get positions from Tradovate
                positions_result = TradovateService.run_async(
                    tradovate.get_positions(demo_account_id, username, password, client_id, client_secret, token, refresh_token)
                )
                
                if positions_result.get('success'):
                    positions = positions_result.get('positions', [])
                    
                    # Filter positions for this strategy's symbol
                    symbol_positions = [
                        p for p in positions 
                        if p.get('symbol') == symbol
                    ]
                    
                    # Process each position
                    for pos in symbol_positions:
                        position_id = pos.get('id')
                        quantity = pos.get('quantity', 0)
                        side = 'long' if quantity > 0 else 'short' if quantity < 0 else 'flat'
                        
                        # Check if this is a new position
                        if position_id not in known_positions:
                            if quantity != 0:  # New open position
                                self._record_position_entry(
                                    strategy_id, account_id, symbol, side, 
                                    abs(quantity), pos
                                )
                                known_positions[position_id] = pos
                        else:
                            # Check if position changed or closed
                            old_pos = known_positions[position_id]
                            old_quantity = old_pos.get('quantity', 0)
                            
                            if quantity == 0 and old_quantity != 0:
                                # Position closed
                                self._record_position_exit(
                                    strategy_id, position_id, pos
                                )
                                del known_positions[position_id]
                            elif quantity != old_quantity:
                                # Position size changed
                                known_positions[position_id] = pos
                                # Could log this as a position update
                
                # Update token if refreshed
                if 'access_token' in positions_result:
                    cursor.execute("""
                        UPDATE accounts
                        SET tradovate_token = ?, tradovate_refresh_token = ?,
                            token_expires_at = ?
                        WHERE id = ?
                    """, (
                        positions_result.get('access_token'),
                        positions_result.get('refresh_token'),
                        positions_result.get('token_expires'),
                        demo_account_id
                    ))
                    db.commit()
                
            except Exception as e:
                logger.error(f"Error recording positions for strategy {strategy_id}: {e}")
            
            # Wait before next poll
            time.sleep(self.poll_interval)
    
    def _record_position_entry(self, strategy_id, account_id, symbol, side, quantity, position_data):
        """Record a new position entry"""
        db = get_db()
        cursor = db.cursor()
        
        entry_price = position_data.get('averagePrice', 0)
        entry_timestamp = datetime.now()
        
        # Get strategy TP/SL
        cursor.execute("""
            SELECT take_profit, stop_loss, tpsl_units
            FROM strategies
            WHERE id = ?
        """, (strategy_id,))
        
        strategy = cursor.fetchone()
        take_profit = strategy[0] if strategy else None
        stop_loss = strategy[1] if strategy else None
        tpsl_units = strategy[2] if strategy else 'Ticks'
        
        # Calculate stop loss and take profit prices
        stop_loss_price = None
        take_profit_price = None
        
        if stop_loss and tpsl_units == 'Ticks':
            # Assuming NQ contract (each tick = $5, 0.25 points = 1 tick)
            tick_value = 0.25
            if side == 'long':
                stop_loss_price = entry_price - (stop_loss * tick_value)
                if take_profit:
                    take_profit_price = entry_price + (take_profit * tick_value)
            else:  # short
                stop_loss_price = entry_price + (stop_loss * tick_value)
                if take_profit:
                    take_profit_price = entry_price - (take_profit * tick_value)
        
        cursor.execute("""
            INSERT INTO recorded_positions (
                strategy_id, account_id, symbol, side, quantity,
                entry_price, entry_timestamp, stop_loss_price, take_profit_price,
                tradovate_position_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            strategy_id, account_id, symbol, side, quantity,
            entry_price, entry_timestamp, stop_loss_price, take_profit_price,
            position_data.get('id'), 'open'
        ))
        
        position_record_id = cursor.lastrowid
        
        # Log entry
        cursor.execute("""
            INSERT INTO strategy_logs (strategy_id, log_type, message, data)
            VALUES (?, ?, ?, ?)
        """, (
            strategy_id,
            'position_entry',
            f'Position opened: {side} {quantity} {symbol} @ {entry_price}',
            str(position_data)
        ))
        
        db.commit()
        
        # Broadcast update
        broadcast_position_update(
            None,  # socketio will be injected
            strategy_id,
            {
                'type': 'entry',
                'position_id': position_record_id,
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'entry_price': entry_price
            }
        )
        
        logger.info(f"Recorded position entry for strategy {strategy_id}: {side} {quantity} {symbol}")
    
    def _record_position_exit(self, strategy_id, position_id, position_data):
        """Record a position exit"""
        db = get_db()
        cursor = db.cursor()
        
        # Find the open position
        cursor.execute("""
            SELECT id, entry_price, quantity, side
            FROM recorded_positions
            WHERE strategy_id = ? AND tradovate_position_id = ? AND status = 'open'
            ORDER BY entry_timestamp DESC
            LIMIT 1
        """, (strategy_id, position_id))
        
        position = cursor.fetchone()
        if not position:
            logger.warning(f"Could not find open position for strategy {strategy_id}, position {position_id}")
            return
        
        record_id, entry_price, quantity, side = position
        exit_price = position_data.get('averagePrice', entry_price)
        exit_timestamp = datetime.now()
        
        # Calculate PnL
        if side == 'long':
            pnl = (exit_price - entry_price) * quantity
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        else:  # short
            pnl = (entry_price - exit_price) * quantity
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100 if entry_price > 0 else 0
        
        # Update position record
        cursor.execute("""
            UPDATE recorded_positions
            SET exit_price = ?, exit_timestamp = ?, exit_reason = 'closed',
                pnl = ?, pnl_percent = ?, status = 'closed'
            WHERE id = ?
        """, (exit_price, exit_timestamp, pnl, pnl_percent, record_id))
        
        # Log exit
        cursor.execute("""
            INSERT INTO strategy_logs (strategy_id, log_type, message, data)
            VALUES (?, ?, ?, ?)
        """, (
            strategy_id,
            'position_exit',
            f'Position closed: {side} {quantity} @ {exit_price}, PnL: ${pnl:.2f} ({pnl_percent:.2f}%)',
            str(position_data)
        ))
        
        db.commit()
        
        # Broadcast update
        broadcast_position_update(
            None,  # socketio will be injected
            strategy_id,
            {
                'type': 'exit',
                'position_id': record_id,
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_percent': pnl_percent
            }
        )
        
        logger.info(f"Recorded position exit for strategy {strategy_id}: PnL ${pnl:.2f}")

# Global recorder instance
recorder = PositionRecorder()

