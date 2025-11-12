"""
System API endpoints
"""
from flask import Blueprint, jsonify, session
from datetime import datetime

system_bp = Blueprint('system', __name__)

@system_bp.route('/csrf-token/', methods=['GET'])
@system_bp.route('/csrf-token', methods=['GET'])  # Support both with and without trailing slash
def get_csrf_token():
    """
    Get CSRF token for form submissions
    Matches: GET /api/system/csrf-token
    Response: {"csrfToken": "..."}
    """
    import secrets
    # Generate or retrieve CSRF token
    csrf_token = session.get('csrf_token')
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        session['csrf_token'] = csrf_token
    
    # Match exact API response structure (csrfToken, not csrf_token)
    return jsonify({
        'csrfToken': csrf_token
    })

