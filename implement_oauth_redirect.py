#!/usr/bin/env python3
"""
Implement TradersPost-Style OAuth Redirect Flow
This will be added to ultra_simple_server.py
"""

# OAuth Redirect Flow Implementation
# Add these routes to ultra_simple_server.py

"""
@app.route('/auth/tradovate/connect', methods=['GET'])
def tradovate_oauth_connect():
    '''
    Initiate OAuth flow - redirect user to Tradovate
    Like TradersPost does it
    '''
    from urllib.parse import urlencode
    
    # Get account_id from query params or session
    account_id = request.args.get('account_id', type=int)
    
    if not account_id:
        return jsonify({'error': 'account_id required'}), 400
    
    # Store account_id in session for callback
    session['tradovate_account_id'] = account_id
    
    # OAuth parameters
    CLIENT_ID = "8552"
    REDIRECT_URI = url_for('tradovate_oauth_callback', _external=True)
    
    # Build OAuth authorization URL
    # Need to verify the exact endpoint with Tradovate API docs
    oauth_params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'read write',  # Adjust based on Tradovate requirements
        'state': str(account_id)  # For security
    }
    
    # Try different possible OAuth endpoints
    # Need to verify which one Tradovate actually uses
    possible_endpoints = [
        'https://demo.tradovate.com/oauth/authorize',
        'https://tradovate.com/oauth/authorize',
        'https://demo.tradovate.com/api/oauth/authorize',
        'https://tradovate.com/api/oauth/authorize',
    ]
    
    # For now, use the first one (need to verify)
    auth_url = f"{possible_endpoints[0]}?{urlencode(oauth_params)}"
    
    # Redirect user to Tradovate OAuth page
    return redirect(auth_url)


@app.route('/auth/tradovate/callback', methods=['GET'])
def tradovate_oauth_callback():
    '''
    OAuth callback - Tradovate redirects here after user authorizes
    Exchange authorization code for access token
    '''
    # Get authorization code from query params
    code = request.args.get('code')
    state = request.args.get('state')  # Should match account_id
    error = request.args.get('error')
    
    if error:
        return jsonify({
            'success': False,
            'error': f'OAuth error: {error}',
            'error_description': request.args.get('error_description')
        }), 400
    
    if not code:
        return jsonify({'error': 'No authorization code received'}), 400
    
    # Get account_id from state or session
    account_id = int(state) if state else session.get('tradovate_account_id')
    
    if not account_id:
        return jsonify({'error': 'Account ID not found'}), 400
    
    # Exchange authorization code for access token
    async def exchange_token():
        CLIENT_ID = "8552"
        CLIENT_SECRET = "d7d4fc4c-43f1-4f5d-a132-dd3e95213239"
        REDIRECT_URI = url_for('tradovate_oauth_callback', _external=True)
        
        # Token exchange request
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }
        
        # Try different token endpoints
        possible_endpoints = [
            'https://demo.tradovateapi.com/v1/auth/accesstokenrequest',
            'https://live.tradovateapi.com/v1/auth/accesstokenrequest',
            'https://demo.tradovate.com/api/oauth/token',
            'https://tradovate.com/api/oauth/token',
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in possible_endpoints:
                try:
                    async with session.post(
                        endpoint,
                        json=token_data,
                        headers={'Content-Type': 'application/json'}
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if 'accessToken' in data:
                                access_token = data.get('accessToken')
                                refresh_token = data.get('refreshToken')
                                expires_in = data.get('expiresIn', 86400)
                                
                                # Store token in database
                                conn = sqlite3.connect('just_trades.db')
                                cursor = conn.cursor()
                                expires_at = datetime.now() + timedelta(seconds=expires_in)
                                
                                cursor.execute("""
                                    UPDATE accounts
                                    SET tradovate_token = ?,
                                        tradovate_refresh_token = ?,
                                        token_expires_at = ?
                                    WHERE id = ?
                                """, (access_token, refresh_token, expires_at.isoformat(), account_id))
                                conn.commit()
                                conn.close()
                                
                                logger.info(f"✅ OAuth token stored for account {account_id}")
                                
                                # Redirect to success page
                                return redirect(url_for('accounts') + f'?connected={account_id}')
                            
                            # If this endpoint didn't work, try next one
                            continue
                except Exception as e:
                    logger.warning(f"Token exchange failed at {endpoint}: {e}")
                    continue
        
        # If all endpoints failed
        return jsonify({
            'success': False,
            'error': 'Failed to exchange authorization code for token',
            'message': 'Please check Tradovate API documentation for correct OAuth endpoints'
        }), 500
    
    # Run async token exchange
    result = asyncio.run(exchange_token())
    return result
"""

print("""
OAuth Redirect Flow Implementation
==================================

This code should be added to ultra_simple_server.py

Key Points:
1. User clicks "Connect Tradovate" → redirects to /auth/tradovate/connect
2. Redirects user to Tradovate OAuth page
3. User authorizes → Tradovate redirects to /auth/tradovate/callback
4. Exchange code for token → store in database
5. Done! No add-on required (like TradersPost)

Next Steps:
1. Verify OAuth endpoints with Tradovate API docs
2. Add these routes to ultra_simple_server.py
3. Update frontend to use /auth/tradovate/connect
4. Test OAuth flow
""")

