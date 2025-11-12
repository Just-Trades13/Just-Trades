"""
WebSocket event handlers for Just.Trades
Handles real-time updates for Control Center and other features
"""

from flask_socketio import emit, join_room, leave_room
from database import get_db
import json

def register_websocket_handlers(socketio):
    """Register all WebSocket event handlers"""
    
    @socketio.on('connect')
    def handle_connect(auth):
        """Handle client connection"""
        # In production, verify auth token
        print(f"Client connected: {auth}")
        emit('connected', {'status': 'connected'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection"""
        print("Client disconnected")
    
    @socketio.on('join_control_center')
    def handle_join_control_center(data):
        """Join Control Center room for real-time updates"""
        strategy_id = data.get('strategy_id')
        if strategy_id:
            room = f'strategy_{strategy_id}'
            join_room(room)
            emit('joined', {'room': room, 'strategy_id': strategy_id})
    
    @socketio.on('leave_control_center')
    def handle_leave_control_center(data):
        """Leave Control Center room"""
        strategy_id = data.get('strategy_id')
        if strategy_id:
            room = f'strategy_{strategy_id}'
            leave_room(room)
            emit('left', {'room': room})
    
    @socketio.on('subscribe_dashboard')
    def handle_subscribe_dashboard(data):
        """Subscribe to dashboard updates"""
        user_id = data.get('user_id')
        if user_id:
            room = f'user_{user_id}'
            join_room(room)
            emit('subscribed', {'room': room})
    
    @socketio.on('unsubscribe_dashboard')
    def handle_unsubscribe_dashboard(data):
        """Unsubscribe from dashboard updates"""
        user_id = data.get('user_id')
        if user_id:
            room = f'user_{user_id}'
            leave_room(room)
            emit('unsubscribed', {'room': room})

def broadcast_strategy_update(socketio, strategy_id, update_type, data):
    """Broadcast strategy update to all clients in strategy room"""
    room = f'strategy_{strategy_id}'
    socketio.emit('strategy_update', {
        'strategy_id': strategy_id,
        'type': update_type,
        'data': data
    }, room=room)

def broadcast_dashboard_update(socketio, user_id, update_type, data):
    """Broadcast dashboard update to user"""
    room = f'user_{user_id}'
    socketio.emit('dashboard_update', {
        'type': update_type,
        'data': data
    }, room=room)

def broadcast_trade_update(socketio, strategy_id, trade_data):
    """Broadcast trade execution update"""
    broadcast_strategy_update(socketio, strategy_id, 'trade', trade_data)

def broadcast_position_update(socketio, strategy_id, position_data):
    """Broadcast position update"""
    broadcast_strategy_update(socketio, strategy_id, 'position', position_data)

def broadcast_log_update(socketio, strategy_id, log_data):
    """Broadcast log update"""
    broadcast_strategy_update(socketio, strategy_id, 'log', log_data)
