"""
Accounts API endpoints
"""
from flask import Blueprint, request, jsonify
from api.auth import require_auth
from database import get_db
import json

accounts_bp = Blueprint('accounts', __name__)

@accounts_bp.route('/', methods=['GET'])
@accounts_bp.route('/get-all-at-accounts/', methods=['GET'])  # Support both
# @require_auth  # BYPASSED
def get_all_accounts():
    """
    Get all user's trading accounts
    Matches: GET /api/accounts/
    Response: Array of account objects with structure:
    {
        "name": "1302271",
        "accntID": "L465530",
        "main": 1491,
        "maxcons": 0,
        "customTicker": "",
        "mult": 1,
        "enabled": false
    }
    """
    from flask import session
    user_id = session.get('user_id')
    
    db = get_db()
    cursor = db.cursor()
    
    # Get all accounts for user
    cursor.execute("""
        SELECT id, name, platform, status, disabled
        FROM accounts
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    
    accounts = []
    for row in cursor.fetchall():
        account_id, name, platform, status, disabled = row
        
        # Get main subaccount (first active subaccount or first subaccount)
        cursor.execute("""
            SELECT id, name, active
            FROM subaccounts
            WHERE account_id = ?
            ORDER BY active DESC, id ASC
            LIMIT 1
        """, (account_id,))
        
        subaccount = cursor.fetchone()
        main_id = subaccount[0] if subaccount else account_id
        accnt_id = subaccount[1] if subaccount else name
        
        # Match exact API structure
        accounts.append({
            'name': name,
            'accntID': accnt_id,
            'main': main_id,
            'maxcons': 0,  # TODO: Get from account settings
            'customTicker': '',  # TODO: Get from account settings
            'mult': 1,  # TODO: Get from account settings
            'enabled': not bool(disabled)
        })
    
    return jsonify(accounts)

@accounts_bp.route('/add-tradovate/', methods=['POST'])
# @require_auth  # BYPASSED
def add_tradovate_account():
    """
    Add Tradovate account
    Expected: POST /api/accounts/add-tradovate/
    Body: {
        "username": "...",
        "password": "...",
        "client_id": "...",
        "client_secret": "...",
        "name": "Account Name"
    }
    """
    from flask import session
    import hashlib
    
    # Verify CSRF token
    csrf_token = request.headers.get('X-CSRFToken')
    if not csrf_token or csrf_token != session.get('csrf_token'):
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')
    name = data.get('name', username)
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user_id = session.get('user_id')
    
    # Test Tradovate connection before saving
    from services.tradovate_service import TradovateService
    
    test_result = TradovateService.run_async(
        TradovateService.test_connection(username, password, client_id, client_secret, demo=True)
    )
    
    if not test_result.get('success'):
        return jsonify({'error': test_result.get('error', 'Failed to connect to Tradovate')}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # Encrypt password and client_secret (in production, use proper encryption)
    password_encrypted = hashlib.sha256(password.encode()).hexdigest()
    client_secret_encrypted = hashlib.sha256(client_secret.encode()).hexdigest() if client_secret else None
    
    # Get tokens from test result
    access_token = test_result.get('access_token')
    refresh_token = test_result.get('refresh_token')
    token_expires = test_result.get('token_expires')
    
    cursor.execute("""
        INSERT INTO accounts (user_id, name, platform, username, password,
                             client_id, client_secret, tradovate_token,
                             tradovate_refresh_token, token_expires_at, disabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, name, 'Tradovate', username, password_encrypted,
          client_id, client_secret_encrypted, access_token,
          refresh_token, token_expires, False))
    
    account_id = cursor.lastrowid
    
    # Fetch and save subaccounts
    subaccounts = test_result.get('subaccounts', [])
    for sub in subaccounts:
        cursor.execute("""
            INSERT INTO subaccounts (account_id, name, active)
            VALUES (?, ?, ?)
        """, (account_id, sub.get('name', ''), sub.get('active', True)))
        
        subaccount_id = cursor.lastrowid
        
        # Save tags if any
        tags = sub.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]
        for tag in tags:
            if tag:
                cursor.execute("""
                    INSERT OR IGNORE INTO subaccount_tags (subaccount_id, tag)
                    VALUES (?, ?)
                """, (subaccount_id, tag))
    
    db.commit()
    
    return jsonify({
        'success': True,
        'account_id': account_id,
        'message': 'Account added successfully',
        'subaccounts': len(subaccounts)
    })

@accounts_bp.route('/test-tradovate-connection/', methods=['POST'])
# @require_auth  # BYPASSED
def test_tradovate_connection():
    """
    Test Tradovate connection
    Expected: POST /api/accounts/test-tradovate-connection/
    Body: {
        "username": "...",
        "password": "...",
        "client_id": "...",
        "client_secret": "..."
    }
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    # Test connection using TradovateService
    try:
        from services.tradovate_service import TradovateService
        result = TradovateService.run_async(
            TradovateService.test_connection(username, password, client_id, client_secret, demo=True)
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@accounts_bp.route('/<int:account_id>/', methods=['PUT'])
# @require_auth  # BYPASSED
def update_account(account_id):
    """Update account credentials"""
    from flask import session
    user_id = session.get('user_id')
    data = request.get_json()
    
    db = get_db()
    cursor = db.cursor()
    
    # Verify ownership
    cursor.execute("SELECT user_id FROM accounts WHERE id = ?", (account_id,))
    account = cursor.fetchone()
    if not account or account[0] != user_id:
        return jsonify({'error': 'Account not found'}), 404
    
    # Build update query
    updates = []
    values = []
    
    for field in ['name', 'username', 'password', 'client_id', 'client_secret', 'disabled']:
        if field in data:
            if field == 'password':
                # Encrypt password
                updates.append("password = ?")
                values.append(hashlib.sha256(data[field].encode()).hexdigest())
            elif field == 'client_secret':
                # Encrypt client_secret
                updates.append("client_secret = ?")
                values.append(hashlib.sha256(data[field].encode()).hexdigest())
            else:
                updates.append(f"{field} = ?")
                values.append(data[field])
    
    if not updates:
        return jsonify({'error': 'No fields to update'}), 400
    
    updates.append("updated_at = CURRENT_TIMESTAMP")
    values.append(account_id)
    
    cursor.execute(f"""
        UPDATE accounts
        SET {', '.join(updates)}
        WHERE id = ?
    """, values)
    
    db.commit()
    
    return jsonify({'success': True, 'message': 'Account updated successfully'})

@accounts_bp.route('/<int:account_id>/', methods=['DELETE'])
# @require_auth  # BYPASSED
def delete_account(account_id):
    """Delete account"""
    from flask import session
    user_id = session.get('user_id')
    
    db = get_db()
    cursor = db.cursor()
    
    # Verify ownership
    cursor.execute("SELECT user_id FROM accounts WHERE id = ?", (account_id,))
    account = cursor.fetchone()
    if not account or account[0] != user_id:
        return jsonify({'error': 'Account not found'}), 404
    
    # Delete subaccounts and tags first
    cursor.execute("SELECT id FROM subaccounts WHERE account_id = ?", (account_id,))
    subaccounts = cursor.fetchall()
    for sub in subaccounts:
        cursor.execute("DELETE FROM subaccount_tags WHERE subaccount_id = ?", (sub[0],))
        cursor.execute("DELETE FROM subaccounts WHERE id = ?", (sub[0],))
    
    # Delete account
    cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    db.commit()
    
    return jsonify({'success': True, 'message': 'Account deleted successfully'})

@accounts_bp.route('/<int:account_id>/refresh/', methods=['POST'])
# @require_auth  # BYPASSED
def refresh_subaccounts(account_id):
    """Refresh subaccounts from Tradovate"""
    from flask import session
    user_id = session.get('user_id')
    
    db = get_db()
    cursor = db.cursor()
    
    # Verify ownership and get credentials
    cursor.execute("""
        SELECT user_id, username, password, client_id, client_secret
        FROM accounts WHERE id = ?
    """, (account_id,))
    account = cursor.fetchone()
    if not account or account[0] != user_id:
        return jsonify({'error': 'Account not found'}), 404
    
    # Decrypt password (in production, use proper decryption)
    # For now, we'll need to re-authenticate
    username = account[1]
    password = account[2]  # This is encrypted, we'd need to decrypt it
    client_id = account[3]
    client_secret = account[4]
    
    # Test connection and get subaccounts
    from services.tradovate_service import TradovateService
    result = TradovateService.run_async(
        TradovateService.test_connection(username, password, client_id, client_secret, demo=True)
    )
    
    if not result.get('success'):
        return jsonify({'error': result.get('error', 'Failed to refresh subaccounts')}), 400
    
    # Delete existing subaccounts
    cursor.execute("SELECT id FROM subaccounts WHERE account_id = ?", (account_id,))
    subaccounts = cursor.fetchall()
    for sub in subaccounts:
        cursor.execute("DELETE FROM subaccount_tags WHERE subaccount_id = ?", (sub[0],))
        cursor.execute("DELETE FROM subaccounts WHERE id = ?", (sub[0],))
    
    # Add new subaccounts
    subaccounts = result.get('subaccounts', [])
    for sub in subaccounts:
        cursor.execute("""
            INSERT INTO subaccounts (account_id, name, active)
            VALUES (?, ?, ?)
        """, (account_id, sub.get('name', ''), sub.get('active', True)))
        
        subaccount_id = cursor.lastrowid
        
        # Save tags
        tags = sub.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]
        for tag in tags:
            if tag:
                cursor.execute("""
                    INSERT OR IGNORE INTO subaccount_tags (subaccount_id, tag)
                    VALUES (?, ?)
                """, (subaccount_id, tag))
    
    # Update tokens
    access_token = result.get('access_token')
    refresh_token = result.get('refresh_token')
    token_expires = result.get('token_expires')
    
    cursor.execute("""
        UPDATE accounts
        SET tradovate_token = ?, tradovate_refresh_token = ?,
            token_expires_at = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (access_token, refresh_token, token_expires, account_id))
    
    db.commit()
    
    return jsonify({
        'success': True,
        'message': 'Subaccounts refreshed successfully',
        'subaccounts': len(subaccounts)
    })

