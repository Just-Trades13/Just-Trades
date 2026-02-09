"""
Discord Settings & Admin Routes for Just Trades Platform.
Flask Blueprint extracted from ultra_simple_server.py.

Usage:
    from discord_routes import discord_bp, init_discord_routes

    init_discord_routes(
        user_auth_available=USER_AUTH_AVAILABLE,
        is_logged_in=is_logged_in,
        get_current_user=get_current_user,
        get_auth_db_connection=get_auth_db_connection,
        discord_notifications_enabled=DISCORD_NOTIFICATIONS_ENABLED,
        send_discord_dm_fn=send_discord_dm,
        broadcast_announcement_fn=broadcast_announcement,
    )
    app.register_blueprint(discord_bp)
"""
import os
import logging
import secrets
import requests as http_requests  # avoid shadowing Flask's request
from urllib.parse import urlencode
from flask import Blueprint, request, jsonify, session, redirect, url_for, flash

logger = logging.getLogger(__name__)

discord_bp = Blueprint('discord', __name__)

# Module-level state, initialized via init_discord_routes()
_user_auth_available = False
_is_logged_in = None
_get_current_user = None
_get_auth_db_connection = None
_discord_notifications_enabled = False
_send_discord_dm = None
_broadcast_announcement = None


def init_discord_routes(
    user_auth_available,
    is_logged_in,
    get_current_user,
    get_auth_db_connection,
    discord_notifications_enabled,
    send_discord_dm_fn,
    broadcast_announcement_fn
):
    """Initialize Discord routes with required dependencies."""
    global _user_auth_available, _is_logged_in, _get_current_user
    global _get_auth_db_connection
    global _discord_notifications_enabled
    global _send_discord_dm, _broadcast_announcement

    _user_auth_available = user_auth_available
    _is_logged_in = is_logged_in
    _get_current_user = get_current_user
    _get_auth_db_connection = get_auth_db_connection
    _discord_notifications_enabled = discord_notifications_enabled
    _send_discord_dm = send_discord_dm_fn
    _broadcast_announcement = broadcast_announcement_fn


# ============================================================================
# USER DISCORD SETTINGS ROUTES
# ============================================================================

@discord_bp.route('/api/settings/discord/toggle', methods=['POST'])
def api_toggle_discord_dms():
    """Toggle Discord DM notifications."""
    if not _user_auth_available:
        return jsonify({'success': False, 'error': 'Auth system not available'}), 400

    if not _is_logged_in():
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    user = _get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    conn, db_type = _get_auth_db_connection()
    cursor = conn.cursor()

    try:
        # Get current state
        if db_type == 'postgresql':
            cursor.execute('SELECT discord_dms_enabled FROM users WHERE id = %s', (user.id,))
        else:
            cursor.execute('SELECT discord_dms_enabled FROM users WHERE id = ?', (user.id,))
        row = cursor.fetchone()
        current_state = bool(row['discord_dms_enabled'] if hasattr(row, 'keys') else row[0]) if row else False

        # Toggle
        new_state = not current_state
        if db_type == 'postgresql':
            cursor.execute('UPDATE users SET discord_dms_enabled = %s WHERE id = %s', (new_state, user.id))
        else:
            cursor.execute('UPDATE users SET discord_dms_enabled = ? WHERE id = ?', (1 if new_state else 0, user.id))

        conn.commit()
        return jsonify({'success': True, 'enabled': new_state, 'message': 'Discord notifications ' + ('enabled' if new_state else 'disabled')})
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Failed to toggle Discord DMs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@discord_bp.route('/api/settings/discord/status', methods=['GET'])
def api_discord_status():
    """Get Discord notification status for current user."""
    if not _user_auth_available or not _is_logged_in():
        return jsonify({'linked': False, 'enabled': False, 'bot_configured': _discord_notifications_enabled, 'debug': 'not_logged_in'})

    user = _get_current_user()
    if not user:
        return jsonify({'linked': False, 'enabled': False, 'bot_configured': _discord_notifications_enabled, 'debug': 'no_user'})

    try:
        conn, db_type = _get_auth_db_connection()
        cursor = conn.cursor()

        if db_type == 'postgresql':
            cursor.execute('SELECT discord_user_id, discord_dms_enabled FROM users WHERE id = %s', (user.id,))
        else:
            cursor.execute('SELECT discord_user_id, discord_dms_enabled FROM users WHERE id = ?', (user.id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            discord_user_id = row[0] if isinstance(row, tuple) else row.get('discord_user_id')
            dms_enabled_raw = row[1] if isinstance(row, tuple) else row.get('discord_dms_enabled')
            discord_linked = bool(discord_user_id)
            dms_enabled = bool(dms_enabled_raw)
            return jsonify({
                'linked': discord_linked,
                'enabled': dms_enabled,
                'bot_configured': _discord_notifications_enabled,
                'debug': {
                    'user_id': user.id,
                    'discord_user_id': discord_user_id,
                    'dms_enabled_raw': dms_enabled_raw
                }
            })
    except Exception as e:
        logger.error(f"Error checking Discord status: {e}")
        return jsonify({'linked': False, 'enabled': False, 'bot_configured': _discord_notifications_enabled, 'debug': f'error: {str(e)}'})

    return jsonify({'linked': False, 'enabled': False, 'bot_configured': _discord_notifications_enabled, 'debug': 'no_row'})


@discord_bp.route('/api/settings/discord/test', methods=['POST'])
def api_test_discord_notification():
    """Send a test Discord notification to the current user."""
    if not _user_auth_available or not _is_logged_in():
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    if not _discord_notifications_enabled:
        return jsonify({'success': False, 'error': 'Discord bot not configured. Set DISCORD_BOT_TOKEN in Railway.'}), 400

    user = _get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    # Get user's Discord ID directly (don't require DMs enabled for test)
    try:
        conn, db_type = _get_auth_db_connection()
        cursor = conn.cursor()

        if db_type == 'postgresql':
            cursor.execute('SELECT discord_user_id, discord_dms_enabled FROM users WHERE id = %s', (user.id,))
        else:
            cursor.execute('SELECT discord_user_id, discord_dms_enabled FROM users WHERE id = ?', (user.id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({'success': False, 'error': 'User not found in database'}), 404

        discord_user_id = row[0] if isinstance(row, tuple) else row.get('discord_user_id')
        dms_enabled = row[1] if isinstance(row, tuple) else row.get('discord_dms_enabled')

        logger.info(f"🔍 Discord test: user_id={user.id}, discord_user_id={discord_user_id}, dms_enabled={dms_enabled}")

        if not discord_user_id:
            return jsonify({'success': False, 'error': 'Discord not linked. Click "Link Discord" first.'}), 400

    except Exception as e:
        logger.error(f"❌ Error checking Discord status: {e}")
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500

    # Send test message
    test_message = "🧪 **Test Notification**\n\nThis is a test message from Just.Trades!\n\nIf you see this, Discord notifications are working correctly. ✅"

    success = _send_discord_dm(discord_user_id, test_message)

    if success:
        return jsonify({'success': True, 'message': 'Test notification sent! Check your Discord DMs.'})
    else:
        return jsonify({'success': False, 'error': 'Failed to send DM. Make sure your Discord DMs are open (not blocked).'}), 500


@discord_bp.route('/api/settings/discord/link', methods=['GET'])
def api_discord_oauth_start():
    """Initiate Discord OAuth flow."""
    if not _user_auth_available:
        flash('Authentication system not available.', 'error')
        return redirect(url_for('settings'))

    if not _is_logged_in():
        return redirect(url_for('login'))

    # Discord OAuth URL
    discord_client_id = os.environ.get('DISCORD_CLIENT_ID', '')
    discord_redirect_uri = os.environ.get('DISCORD_REDIRECT_URI', request.url_root.rstrip('/') + '/api/settings/discord/callback')

    logger.info(f"🔗 Discord OAuth: client_id exists={bool(discord_client_id)}, redirect_uri={discord_redirect_uri}")

    if not discord_client_id:
        logger.warning("⚠️ DISCORD_CLIENT_ID environment variable not set")
        flash('Discord OAuth is not configured. Please contact an administrator.', 'error')
        return redirect(url_for('settings'))

    # Store state in session
    state = secrets.token_urlsafe(32)
    session['discord_oauth_state'] = state

    oauth_params = {
        'client_id': discord_client_id,
        'redirect_uri': discord_redirect_uri,
        'response_type': 'code',
        'scope': 'identify',
        'state': state
    }

    oauth_url = f"https://discord.com/api/oauth2/authorize?{urlencode(oauth_params)}"
    return redirect(oauth_url)


@discord_bp.route('/api/settings/discord/callback', methods=['GET'])
def api_discord_oauth_callback():
    """Discord OAuth callback."""
    if not _user_auth_available:
        flash('Authentication system not available.', 'error')
        return redirect(url_for('settings'))

    if not _is_logged_in():
        return redirect(url_for('login'))

    user = _get_current_user()
    if not user:
        return redirect(url_for('settings'))

    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        flash(f'Discord authorization failed: {error}', 'error')
        return redirect(url_for('settings'))

    if not code or state != session.get('discord_oauth_state'):
        flash('Invalid Discord authorization.', 'error')
        return redirect(url_for('settings'))

    # Exchange code for token
    discord_client_id = os.environ.get('DISCORD_CLIENT_ID', '')
    discord_client_secret = os.environ.get('DISCORD_CLIENT_SECRET', '')
    discord_redirect_uri = os.environ.get('DISCORD_REDIRECT_URI', request.url_root.rstrip('/') + '/api/settings/discord/callback')

    if not discord_client_id or not discord_client_secret:
        flash('Discord OAuth is not configured. Please contact an administrator.', 'error')
        return redirect(url_for('settings'))

    try:
        # Exchange code for access token
        token_data = {
            'client_id': discord_client_id,
            'client_secret': discord_client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': discord_redirect_uri
        }

        token_response = http_requests.post('https://discord.com/api/oauth2/token', data=token_data)
        if token_response.status_code != 200:
            flash('Failed to exchange Discord authorization code.', 'error')
            return redirect(url_for('settings'))

        token_json = token_response.json()
        access_token = token_json.get('access_token')

        # Get user info
        user_response = http_requests.get('https://discord.com/api/users/@me', headers={
            'Authorization': f'Bearer {access_token}'
        })
        if user_response.status_code != 200:
            flash('Failed to get Discord user information.', 'error')
            return redirect(url_for('settings'))

        discord_user_info = user_response.json()
        discord_user_id = discord_user_info.get('id')

        # Store in database
        conn, db_type = _get_auth_db_connection()
        cursor = conn.cursor()

        try:
            if db_type == 'postgresql':
                cursor.execute('''
                    UPDATE users SET discord_user_id = %s, discord_access_token = %s
                    WHERE id = %s
                ''', (discord_user_id, access_token, user.id))
            else:
                cursor.execute('''
                    UPDATE users SET discord_user_id = ?, discord_access_token = ?
                    WHERE id = ?
                ''', (discord_user_id, access_token, user.id))
            conn.commit()
            flash('Discord account linked successfully!', 'success')
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Failed to link Discord: {e}")
            flash('Failed to link Discord account.', 'error')
        finally:
            cursor.close()
            conn.close()

        # Clear state
        session.pop('discord_oauth_state', None)
        return redirect(url_for('settings'))
    except Exception as e:
        logger.error(f"❌ Discord OAuth error: {e}")
        flash('Discord authorization failed.', 'error')
        return redirect(url_for('settings'))


# ============================================================================
# ADMIN DISCORD ROUTES
# ============================================================================

@discord_bp.route('/api/admin/discord/broadcast', methods=['POST'])
def admin_discord_broadcast():
    """Admin: Send a Discord DM broadcast to all users with Discord linked."""
    if not _user_auth_available or not _is_logged_in():
        return jsonify({'error': 'Not logged in'}), 401

    user = _get_current_user()
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    if not _discord_notifications_enabled:
        return jsonify({'error': 'Discord notifications not configured. Set DISCORD_BOT_TOKEN environment variable.'}), 400

    data = request.json
    title = data.get('title', '').strip()
    message = data.get('message', '').strip()
    ann_type = data.get('type', 'info')

    if not title or not message:
        return jsonify({'error': 'Title and message are required'}), 400

    sent_count = _broadcast_announcement(title, message, ann_type)
    logger.info(f"Admin {user.username} sent Discord broadcast: {title} (sent to {sent_count} users)")

    return jsonify({
        'success': True,
        'sent_count': sent_count,
        'message': f'Broadcast sent to {sent_count} Discord users'
    })


@discord_bp.route('/api/admin/discord/check/<int:user_id>', methods=['GET'])
def admin_check_discord_status(user_id):
    """Admin: Check Discord status for a specific user."""
    if not _user_auth_available or not _is_logged_in():
        return jsonify({'error': 'Not logged in'}), 401

    user = _get_current_user()
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    try:
        conn, db_type = _get_auth_db_connection()
        cursor = conn.cursor()

        if db_type == 'postgresql':
            cursor.execute('SELECT id, username, discord_user_id, discord_dms_enabled FROM users WHERE id = %s', (user_id,))
        else:
            cursor.execute('SELECT id, username, discord_user_id, discord_dms_enabled FROM users WHERE id = ?', (user_id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            # Handle both tuple and dict-like rows
            if isinstance(row, tuple):
                uid, uname, discord_id, dms_enabled = row
            else:
                uid = row['id']
                uname = row['username']
                discord_id = row['discord_user_id']
                dms_enabled = row['discord_dms_enabled']
            return jsonify({
                'user_id': uid,
                'username': uname,
                'discord_user_id': discord_id,
                'discord_dms_enabled': dms_enabled,
                'notifications_would_work': bool(discord_id) and bool(dms_enabled)
            })
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@discord_bp.route('/api/admin/discord/all-users', methods=['GET'])
def admin_list_all_discord_status():
    """Admin: List Discord status for ALL users with pagination."""
    if not _user_auth_available or not _is_logged_in():
        return jsonify({'error': 'Not logged in'}), 401

    user = _get_current_user()
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 200)  # Cap at 200
    offset = (page - 1) * per_page

    try:
        conn, db_type = _get_auth_db_connection()
        cursor = conn.cursor()

        # Get total count
        cursor.execute('SELECT COUNT(*) FROM users')
        count_row = cursor.fetchone()
        total = count_row[0] if isinstance(count_row, tuple) else count_row.get('count', 0)

        # Get paginated results
        if db_type == 'postgresql':
            cursor.execute('SELECT id, username, discord_user_id, discord_dms_enabled FROM users ORDER BY id LIMIT %s OFFSET %s', (per_page, offset))
        else:
            cursor.execute('SELECT id, username, discord_user_id, discord_dms_enabled FROM users ORDER BY id LIMIT ? OFFSET ?', (per_page, offset))

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        users = []
        for row in rows:
            if isinstance(row, tuple):
                uid, uname, discord_id, dms_enabled = row
            else:
                uid = row['id']
                uname = row['username']
                discord_id = row['discord_user_id']
                dms_enabled = row['discord_dms_enabled']
            users.append({
                'user_id': uid,
                'username': uname,
                'discord_linked': bool(discord_id),
                'dms_enabled': bool(dms_enabled),
                'notifications_work': bool(discord_id) and bool(dms_enabled)
            })

        return jsonify({
            'users': users,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@discord_bp.route('/api/admin/discord/enable/<int:user_id>', methods=['POST'])
def admin_enable_discord_for_user(user_id):
    """Admin: Force enable Discord DMs for a specific user."""
    if not _user_auth_available or not _is_logged_in():
        return jsonify({'error': 'Not logged in'}), 401

    user = _get_current_user()
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin access required'}), 403

    try:
        conn, db_type = _get_auth_db_connection()
        cursor = conn.cursor()

        if db_type == 'postgresql':
            cursor.execute('UPDATE users SET discord_dms_enabled = TRUE WHERE id = %s', (user_id,))
        else:
            cursor.execute('UPDATE users SET discord_dms_enabled = 1 WHERE id = ?', (user_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': f'Discord DMs enabled for user {user_id}'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
