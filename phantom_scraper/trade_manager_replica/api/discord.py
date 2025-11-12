"""
Discord OAuth API endpoints
"""
from flask import Blueprint, request, jsonify, redirect, session
from api.auth import require_auth
from database import get_db
from services.discord_service import DiscordService
import os

discord_bp = Blueprint('discord', __name__)

DISCORD_CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID', '')
DISCORD_CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET', '')
DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN', '')

@discord_bp.route('/oauth/callback/', methods=['GET'])
def discord_oauth_callback():
    """
    Discord OAuth callback
    Expected: GET /api/discord/oauth/callback/?code=...&state=...
    """
    code = request.args.get('code')
    state = request.args.get('state')
    
    if not code:
        return jsonify({'error': 'No authorization code provided'}), 400
    
    redirect_uri = f"{request.scheme}://{request.host}/api/discord/oauth/callback/"
    
    # Exchange code for token
    result = DiscordService.run_async(
        DiscordService.exchange_code_for_token(
            code, DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, redirect_uri
        )
    )
    
    if 'error' in result:
        return jsonify({'error': result['error']}), 400
    
    access_token = result.get('access_token')
    
    # Get user info
    user_info = DiscordService.run_async(
        DiscordService.get_user_info(access_token)
    )
    
    if 'error' in user_info:
        return jsonify({'error': user_info['error']}), 400
    
    discord_user_id = user_info.get('id')
    
    # Update user in database
    if 'user_id' in session:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE users
            SET discord_user_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (discord_user_id, session['user_id']))
        db.commit()
        
        return redirect('/user/settings?discord=connected')
    else:
        return jsonify({'error': 'Not authenticated'}), 401

@discord_bp.route('/oauth/connect/', methods=['GET'])
@require_auth
def discord_oauth_connect():
    """
    Initiate Discord OAuth flow
    Expected: GET /api/discord/oauth/connect/
    """
    from flask import session
    state = session.get('csrf_token', '')
    redirect_uri = f"{request.scheme}://{request.host}/api/discord/oauth/callback/"
    
    oauth_url = DiscordService.get_oauth_url(DISCORD_CLIENT_ID, redirect_uri, state)
    return redirect(oauth_url)

@discord_bp.route('/send-dm/', methods=['POST'])
@require_auth
def send_discord_dm():
    """
    Send Discord DM (admin/backend only)
    Expected: POST /api/discord/send-dm/
    Body: {"user_id": 123, "message": "..."}
    """
    from flask import session
    data = request.get_json()
    target_user_id = data.get('user_id')
    message = data.get('message')
    
    if not target_user_id or not message:
        return jsonify({'error': 'user_id and message required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Get Discord user ID
    cursor.execute("SELECT discord_user_id, discord_dms_enabled FROM users WHERE id = ?", (target_user_id,))
    user = cursor.fetchone()
    
    if not user or not user[0]:
        return jsonify({'error': 'User not found or Discord not connected'}), 404
    
    if not user[1]:  # discord_dms_enabled
        return jsonify({'error': 'Discord DMs disabled for this user'}), 403
    
    # Send DM
    result = DiscordService.run_async(
        DiscordService.send_dm(user[0], message, DISCORD_BOT_TOKEN)
    )
    
    if result.get('success'):
        return jsonify({'success': True, 'message': 'DM sent successfully'})
    else:
        return jsonify({'error': result.get('error', 'Failed to send DM')}), 500


