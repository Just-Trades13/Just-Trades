"""
Authentication API endpoints
"""
from flask import Blueprint, request, jsonify, session
from functools import wraps
from database import get_db
import hashlib

auth_bp = Blueprint('auth', __name__)

def require_auth(f):
    """Decorator to require authentication - BYPASSED FOR TESTING"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # BYPASS: Allow access without authentication for testing
        # Set a default user_id if not in session
        if 'user_id' not in session:
            # Try to get a test user from database
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id FROM users LIMIT 1")
            user = cursor.fetchone()
            if user:
                session['user_id'] = user[0]
            else:
                # If no users exist, create a default session
                session['user_id'] = 1
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/check-auth/', methods=['GET'])
def check_auth():
    """
    Check if user is authenticated and return user info
    Matches: GET /api/auth/check-auth/
    """
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""
        SELECT id, username, email, admin, discord_user_id, 
               discord_dms_enabled, is_email_verified
        FROM users
        WHERE id = ?
    """, (session['user_id'],))
    
    user = cursor.fetchone()
    
    if not user:
        session.clear()
        return jsonify({'error': 'User not found'}), 401
    
    return jsonify({
        'user': {
            'username': user[1],
            'email': user[2],
            'admin': bool(user[3]),
            'DiscordID': user[4] if user[4] else None,
            'access': 'full',  # Can be customized based on user plan
            'signed': True,
            'is_email_verified': bool(user[6]),
            'sessionId': session.get('session_id', session['user_id'])
        }
    })

@auth_bp.route('/login/', methods=['POST'])
def login():
    """
    Login endpoint
    Expected: POST /api/auth/login/
    Body: {"username": "...", "password": "...", "captchaToken": "..."}
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    captcha_token = data.get('captchaToken')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    # TODO: Verify reCAPTCHA token
    # For now, we'll accept any non-empty captcha token
    if not captcha_token:
        return jsonify({'error': 'reCAPTCHA verification required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Hash password (in production, use bcrypt)
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    cursor.execute("""
        SELECT id, username, email, admin, discord_user_id,
               discord_dms_enabled, is_email_verified
        FROM users
        WHERE username = ? AND password_hash = ?
    """, (username, password_hash))
    
    user = cursor.fetchone()
    
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Set session
    session['user_id'] = user[0]
    session['session_id'] = session.get('session_id', str(user[0]))
    session.permanent = True
    
    # Match exact API response structure (no 'success' flag, no 'sessionId' in response)
    return jsonify({
        'user': {
            'username': user[1],
            'email': user[2],
            'admin': bool(user[3]),
            'DiscordID': user[4] if user[4] else None,
            'access': 'full',
            'signed': True,
            'is_email_verified': bool(user[6])
        }
    })

@auth_bp.route('/logout/', methods=['POST'])
def logout():
    """
    Logout endpoint
    Expected: POST /api/auth/logout/
    """
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

