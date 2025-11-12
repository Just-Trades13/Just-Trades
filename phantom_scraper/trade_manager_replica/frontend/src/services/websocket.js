/**
 * WebSocket Service for Just.Trades
 * Handles real-time updates via Socket.IO
 */

import { io } from 'socket.io-client';

// WebSocket URL - connect directly to backend
const getWSURL = () => {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  
  // In dev mode (Vite), connect to backend directly
  // In production, would use same origin
  if (import.meta.env.DEV) {
    return 'http://localhost:5001';
  }
  
  // Production: use same origin
  if (typeof window !== 'undefined' && window.location) {
    const origin = window.location.origin;
    return origin;
  }
  
  return 'http://localhost:5001';
};
const WS_URL = getWSURL();

class WebSocketService {
  constructor() {
    this.socket = null;
    this.listeners = new Map();
  }

  connect() {
    if (this.socket?.connected) {
      return;
    }
    
    // Prevent multiple connection attempts
    if (this.connecting) {
      return;
    }
    this.connecting = true;

    this.socket = io(WS_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 5000, // Increased delay to prevent rapid reconnects
      reconnectionAttempts: 3, // Reduced attempts
    });

    this.socket.on('connect', () => {
      console.log('WebSocket connected');
      this.connecting = false;
      this.emit('connected', { status: 'connected' });
    });

    this.socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      this.connecting = false;
    });
    
    this.socket.on('connect_error', () => {
      this.connecting = false;
    });

    this.socket.on('strategy_update', (data) => {
      this.notifyListeners('strategy_update', data);
    });

    this.socket.on('dashboard_update', (data) => {
      this.notifyListeners('dashboard_update', data);
    });

    this.socket.on('trade_result', (data) => {
      this.notifyListeners('trade_result', data);
    });

    this.socket.on('position_update', (data) => {
      this.notifyListeners('position_update', data);
    });

    this.socket.on('log_update', (data) => {
      this.notifyListeners('log_update', data);
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  off(event, callback) {
    if (this.listeners.has(event)) {
      const callbacks = this.listeners.get(event);
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  notifyListeners(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach((callback) => callback(data));
    }
  }

  emit(event, data) {
    if (this.socket?.connected) {
      this.socket.emit(event, data);
    }
  }

  joinControlCenter(strategyId) {
    this.emit('join_control_center', { strategy_id: strategyId });
  }

  leaveControlCenter(strategyId) {
    this.emit('leave_control_center', { strategy_id: strategyId });
  }

  subscribeDashboard(userId) {
    this.emit('subscribe_dashboard', { user_id: userId });
  }

  unsubscribeDashboard(userId) {
    this.emit('unsubscribe_dashboard', { user_id: userId });
  }

  isConnected() {
    return this.socket?.connected || false;
  }
}

// Export singleton instance
export const wsService = new WebSocketService();
export default wsService;

