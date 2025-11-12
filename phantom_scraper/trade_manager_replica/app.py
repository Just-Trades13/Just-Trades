#!/usr/bin/env python3
"""
Trade Manager Replica - Main Flask Application
Reverse engineered from trademanagergroup.com
"""

from flask import Flask, request, jsonify, session, send_from_directory, Response
from flask_cors import CORS
from flask_session import Session
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timedelta
import secrets
import os
from functools import wraps

# Import blueprints
from api.auth import auth_bp
from api.accounts import accounts_bp
from api.strategies import strategies_bp
from api.recorder import recorder_bp
from api.dashboard import dashboard_bp
from api.system import system_bp
from api.trades import trades_bp
from api.profiles import profiles_bp
from api.discord import discord_bp
from api.webhook import webhook_bp

# Import database
from database import init_db, get_db

# Determine if we're in production (serving built files) or development
FRONTEND_BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist')
print(f"🔍 Frontend build directory: {FRONTEND_BUILD_DIR}")
print(f"🔍 Exists: {os.path.exists(FRONTEND_BUILD_DIR)}")
if os.path.exists(FRONTEND_BUILD_DIR):
    print(f"🔍 Contents: {os.listdir(FRONTEND_BUILD_DIR)}")
# Don't use Flask's default static handler - we'll handle static files manually
app = Flask(__name__, static_folder=None, static_url_path=None)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_COOKIE_NAME'] = 'sessionid'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)

# CORS configuration
CORS(app, supports_credentials=True, origins=[
    'http://localhost:3000',
    'http://localhost:5000',
    'http://localhost:5173',  # Vite default port
    'http://127.0.0.1:5173',
    'http://127.0.0.1:5000',
    'https://trademanagergroup.com'
])

# Initialize session
Session(app)

# Initialize SocketIO for WebSocket support
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Register WebSocket handlers
from websocket_handlers import register_websocket_handlers
register_websocket_handlers(socketio)

# Initialize database
init_db()

# Register blueprints
app.register_blueprint(system_bp, url_prefix='/api/system')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(accounts_bp, url_prefix='/api/accounts')
app.register_blueprint(strategies_bp, url_prefix='/api/strategies')
app.register_blueprint(recorder_bp, url_prefix='/api/recorder')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
app.register_blueprint(trades_bp, url_prefix='/api/trades')
app.register_blueprint(profiles_bp, url_prefix='/api/profiles')
app.register_blueprint(discord_bp, url_prefix='/api/discord')
app.register_blueprint(webhook_bp, url_prefix='/api/webhook')

# Serve static files directly (JS, CSS, images from assets folder)
@app.route('/assets/<path:filename>')
def serve_static_assets(filename):
    """Serve static assets from frontend/dist/assets/"""
    if os.path.exists(FRONTEND_BUILD_DIR):
        assets_dir = os.path.join(FRONTEND_BUILD_DIR, 'assets')
        file_path = os.path.join(assets_dir, filename)
        if os.path.exists(file_path):
            return send_from_directory(assets_dir, filename)
    return jsonify({'error': 'Asset not found'}), 404

@app.route('/vite.svg')
def serve_vite_svg():
    """Serve vite.svg"""
    if os.path.exists(FRONTEND_BUILD_DIR):
        file_path = os.path.join(FRONTEND_BUILD_DIR, 'vite.svg')
        if os.path.exists(file_path):
            return send_from_directory(FRONTEND_BUILD_DIR, 'vite.svg')
    return jsonify({'error': 'Not found'}), 404

# Serve React app for all non-API routes
# This must be registered AFTER all blueprints and static routes
@app.route('/', defaults={'path': ''}, methods=['GET'])
@app.route('/<path:path>', methods=['GET'])
def serve_react_app(path):
    """Serve React app for all non-API routes - SPA fallback"""
    # Debug logging
    print(f"🔍 serve_react_app called with path='{path}', request.path='{request.path}'")
    
    # Don't serve React app for API routes (they're handled by blueprints above)
    if path and (path.startswith('api') or path.startswith('assets') or path == 'vite.svg'):
        print(f"❌ Rejecting path '{path}' - not an SPA route")
        return jsonify({'error': 'Not found'}), 404
    
    # Check if static folder exists (built frontend)
    if not os.path.exists(FRONTEND_BUILD_DIR):
        # Development mode - frontend not built, show helpful message
        return f"""
        <html>
            <head><title>Just.Trades - Development Mode</title></head>
            <body style="font-family: Arial; padding: 50px; text-align: center;">
                <h1>🚀 Just.Trades Backend</h1>
                <p>Frontend not built. Run in development mode:</p>
                <p><code>cd frontend && npm run dev</code></p>
                <p>Then open: <a href="http://localhost:5173">http://localhost:5173</a></p>
                <hr>
                <p>Or build the frontend: <code>cd frontend && npm run build</code></p>
                <p><small>Build directory expected: {FRONTEND_BUILD_DIR}</small></p>
            </body>
        </html>
        """, 200
    
    # Serve index.html for all SPA routes (/, /dashboard, /login, etc.)
    index_path = os.path.join(FRONTEND_BUILD_DIR, 'index.html')
    print(f"   Serving index.html from: {index_path}")
    print(f"   File exists: {os.path.exists(index_path)}")
    if os.path.exists(index_path):
        with open(index_path, 'r') as f:
            content = f.read()
        print(f"   ✅ Serving {len(content)} bytes of HTML")
        return Response(content, mimetype='text/html')
    else:
        print(f"   ❌ index.html not found!")
        return jsonify({'error': 'index.html not found in build directory'}), 500

# Error handlers - but don't catch routes that should serve index.html
@app.errorhandler(404)
def not_found(error):
    # If it's an API route, return JSON error
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    # For non-API routes, try to serve index.html (SPA fallback)
    if os.path.exists(FRONTEND_BUILD_DIR):
        index_path = os.path.join(FRONTEND_BUILD_DIR, 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r') as f:
                content = f.read()
            return Response(content, mimetype='text/html')
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 5001))  # Use 5001 to avoid AirPlay conflict
    
    print("=" * 60)
    print("🚀 Just.Trades Backend Server Starting...")
    print("=" * 60)
    print(f"📡 Backend API: http://localhost:{PORT}")
    print(f"🔌 WebSocket: ws://localhost:{PORT}")
    print(f"📚 API Docs: http://localhost:{PORT}/api/system/csrf-token/")
    print("=" * 60)
    print("Press Ctrl+C to stop the server")
    print("")
    socketio.run(app, debug=True, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True)

