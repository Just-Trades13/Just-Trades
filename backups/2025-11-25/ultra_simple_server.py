#!/usr/bin/env python3
from __future__ import annotations
import sqlite3
import logging
import asyncio
import argparse
import sys
import os
import json
import re
import time
import requests
from flask import Flask, request, jsonify, render_template, redirect, url_for
from datetime import datetime, timedelta

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip (optional dependency)
    pass

app = Flask(__name__)
logger = logging.getLogger(__name__)

SYMBOL_FALLBACK_MAP = {
    'MNQ': 'MNQZ5',
    'MES': 'MESZ5',
    'ES': 'ESZ5',
    'NQ': 'NQZ5',
    'CL': 'CLZ5',
    'GC': 'GCZ5',
    'MCL': 'MCLZ5'
}
SYMBOL_CONVERSION_CACHE: dict[tuple[str, bool], tuple[str, datetime]] = {}
SYMBOL_CACHE_TTL = timedelta(hours=1)

TICK_INFO = {
    'MNQ': {'tick_size': 0.25, 'tick_value': 0.5},
    'NQ': {'tick_size': 0.25, 'tick_value': 5.0},
    'MES': {'tick_size': 0.25, 'tick_value': 1.25},
    'ES': {'tick_size': 0.25, 'tick_value': 12.5},
    'M2K': {'tick_size': 0.1, 'tick_value': 0.5},
    'RTY': {'tick_size': 0.1, 'tick_value': 5.0},
    'CL': {'tick_size': 0.01, 'tick_value': 10.0},
    'MCL': {'tick_size': 0.01, 'tick_value': 1.0},
    'GC': {'tick_size': 0.1, 'tick_value': 10.0}
}


def convert_tradingview_to_tradovate_symbol(symbol: str, access_token: str | None = None, demo: bool = True) -> str:
    """Convert TradingView symbol (MNQ1!) to Tradovate front-month symbol (MNQZ5)."""
    if not symbol:
        return symbol
    clean = symbol.strip().upper()
    # Already Tradovate format (no ! suffix)
    if '!' not in clean:
        return clean
    match = re.match(r'^([A-Z]+)\d*!$', clean)
    if not match:
        return clean.replace('!', '')
    root = match.group(1)
    cache_key = (root, demo)
    cached = SYMBOL_CONVERSION_CACHE.get(cache_key)
    if cached:
        value, expires = cached
        if datetime.utcnow() < expires:
            return value
    # Fallback to map
    converted = SYMBOL_FALLBACK_MAP.get(root)
    if not converted:
        # Default to December contract for safety
        converted = f"{root}Z5"
    SYMBOL_CONVERSION_CACHE[cache_key] = (converted, datetime.utcnow() + SYMBOL_CACHE_TTL)
    return converted


def extract_symbol_root(symbol: str) -> str:
    if not symbol:
        return ''
    clean = symbol.upper()
    clean = clean.replace('!', '')
    match = re.match(r'^([A-Z]+)', clean)
    return match.group(1) if match else clean


def get_tick_info(symbol: str) -> dict:
    root = extract_symbol_root(symbol)
    return TICK_INFO.get(root, {'tick_size': 0.25, 'tick_value': 1.0})


async def wait_for_position_fill(tradovate, account_id: int, symbol: str, expected_side: str, timeout: float = 7.5):
    expected_side = expected_side.lower()
    deadline = time.time() + timeout
    while time.time() < deadline:
        positions = await tradovate.get_positions(account_id)
        for pos in positions:
            if str(pos.get('symbol', '')).upper() == symbol.upper():
                net_pos = pos.get('netPos') or 0
                if (expected_side == 'buy' and net_pos > 0) or (expected_side == 'sell' and net_pos < 0):
                    return pos
        await asyncio.sleep(0.25)
    return None


def clamp_price(price: float, tick_size: float) -> float:
    if price is None:
        return None
    decimals = max(3, len(str(tick_size).split('.')[-1]))
    return round(price, decimals)


async def apply_risk_orders(tradovate, account_spec: str, account_id: int, symbol: str, entry_side: str, quantity: int, risk_config: dict):
    if not risk_config or not quantity:
        return
    symbol_upper = symbol.upper()
    fill = await wait_for_position_fill(tradovate, account_id, symbol_upper, entry_side)
    if not fill:
        logger.warning(f"Unable to locate filled position for {symbol_upper} to apply brackets")
        return
    entry_price = fill.get('netPrice') or fill.get('price')
    if not entry_price:
        logger.warning(f"No entry price found for {symbol_upper}; skipping bracket creation")
        return
    tick_info = get_tick_info(symbol_upper)
    tick_size = tick_info['tick_size']
    is_long = entry_side.lower() == 'buy'
    exit_action = 'Sell' if is_long else 'Buy'

    async def place_tp_order(ticks: float, qty: int):
        if not ticks or qty <= 0:
            return
        offset = tick_size * ticks
        target_price = entry_price + offset if is_long else entry_price - offset
        order = tradovate.create_limit_order(account_spec, symbol_upper, exit_action, qty, clamp_price(target_price, tick_size), account_id)
        await tradovate.place_order(order)

    async def place_stop_order(ticks: float, qty: int):
        if not ticks or qty <= 0:
            return
        offset = tick_size * ticks
        stop_price = entry_price - offset if is_long else entry_price + offset
        order = tradovate.create_stop_order(account_spec, symbol_upper, exit_action, qty, clamp_price(stop_price, tick_size), account_id)
        await tradovate.place_order(order)

    async def place_trailing_order(trail_ticks: float, qty: int):
        if not trail_ticks or qty <= 0:
            return
        offset = tick_size * trail_ticks
        order = tradovate.create_trailing_stop_order(account_spec, symbol_upper, exit_action, qty, float(offset), account_id)
        await tradovate.place_order(order)

    # Take profit ladder
    take_profit = risk_config.get('take_profit') or []
    remaining_qty = quantity
    for idx, tp in enumerate(take_profit):
        ticks = tp.get('gain_ticks')
        trim_percent = tp.get('trim_percent', 100 if idx == len(take_profit) - 1 else 0)
        tp_qty = int(round(quantity * (trim_percent / 100.0))) if trim_percent else 0
        if tp_qty <= 0:
            if idx == len(take_profit) - 1:
                tp_qty = remaining_qty
        tp_qty = min(max(tp_qty, 0), remaining_qty)
        remaining_qty -= tp_qty
        await place_tp_order(ticks, tp_qty)

    # Stop loss or trailing stop
    trail_cfg = risk_config.get('trail')
    stop_cfg = risk_config.get('stop_loss')
    if trail_cfg and trail_cfg.get('offset_ticks'):
        await place_trailing_order(trail_cfg.get('offset_ticks'), quantity)
    elif stop_cfg and stop_cfg.get('loss_ticks'):
        await place_stop_order(stop_cfg.get('loss_ticks'), quantity)


async def cancel_open_orders(tradovate, account_id: int, symbol: str | None = None):
    cancelled = 0
    try:
        orders = await tradovate.get_orders(str(account_id)) or []
        for order in orders:
            if not order:
                continue
            status = (order.get('status') or '').lower()
            if status not in ('working', 'pending', 'queued', 'accepted', 'new'):
                continue
            if symbol:
                order_symbol = str(order.get('symbol') or '').upper()
                if order_symbol != symbol.upper():
                    continue
            order_id = order.get('id')
            if await tradovate.cancel_order(order_id):
                cancelled += 1
    except Exception as e:
        logger.warning(f"Unable to cancel open orders for {symbol or 'account'}: {e}")
    return cancelled

def init_db():
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            method TEXT NOT NULL,
            headers TEXT,
            body TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def fetch_and_store_tradovate_accounts(account_id: int, access_token: str, base_url: str = "https://demo.tradovateapi.com") -> dict:
    """
    Fetch Tradovate accounts/subaccounts for the given account_id and persist them.
    Returns a dict with success flag and parsed subaccounts.
    """
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Always attempt both demo and live endpoints so we capture all accounts
        base_urls = []
        if base_url:
            base_urls.append(base_url.rstrip('/'))
        for candidate in ("https://demo.tradovateapi.com", "https://live.tradovateapi.com"):
            if candidate not in base_urls:
                base_urls.append(candidate)
        
        combined_accounts = []
        formatted_subaccounts = []
        success = False
        for candidate_base in base_urls:
            try:
                response = requests.get(f"{candidate_base}/v1/account/list", headers=headers, timeout=15)
            except Exception as req_err:
                logger.error(f"Error fetching Tradovate accounts from {candidate_base}: {req_err}")
                continue
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch Tradovate accounts from {candidate_base}: {response.status_code} - {response.text}")
                continue
            
            success = True
            environment = "demo" if "demo." in candidate_base else "live"
            accounts_payload = response.json() or []
            for account in accounts_payload:
                account_copy = dict(account) if isinstance(account, dict) else {}
                account_copy["environment"] = environment
                account_copy["is_demo"] = environment == "demo"
                combined_accounts.append(account_copy)
                
                parent_name = account_copy.get('name') or account_copy.get('accountName', 'Tradovate')
                for sub in account_copy.get('subAccounts', []) or []:
                    tags = sub.get('tags') or []
                    if isinstance(tags, str):
                        tags = [tags]
                    name = sub.get('name') or ''
                    is_demo = True if environment == "demo" else False
                    formatted_subaccounts.append({
                        "id": sub.get('id'),
                        "name": name,
                        "parent": parent_name,
                        "tags": tags,
                        "active": sub.get('active', True),
                        "environment": environment,
                        "is_demo": is_demo
                    })
        
        if not success:
            return {"success": False, "error": "Failed to fetch Tradovate accounts from demo or live endpoints"}
        
        conn = sqlite3.connect('just_trades.db')
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE accounts
            SET tradovate_accounts = ?, subaccounts = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (json.dumps(combined_accounts), json.dumps(formatted_subaccounts), account_id))
        conn.commit()
        conn.close()
        logger.info(f"Stored {len(formatted_subaccounts)} Tradovate subaccounts for account {account_id}")
        return {"success": True, "subaccounts": formatted_subaccounts}
    except Exception as e:
        logger.error(f"Error storing Tradovate accounts: {e}")
        return {"success": False, "error": str(e)}

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/accounts')
def accounts():
    return render_template('account_management.html')

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts"""
    try:
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts")
        accounts = cursor.fetchall()
        conn.close()
        
        accounts_list = []
        for account in accounts:
            parsed_subaccounts = []
            try:
                if 'subaccounts' in account.keys() and account['subaccounts']:
                    parsed_subaccounts = json.loads(account['subaccounts'])
            except Exception as parse_err:
                logger.warning(f"Unable to parse subaccounts for account {account['id']}: {parse_err}")
                parsed_subaccounts = []
            
            parsed_tradovate_accounts = []
            try:
                if 'tradovate_accounts' in account.keys() and account['tradovate_accounts']:
                    raw_tradovate_accounts = json.loads(account['tradovate_accounts'])
                    if isinstance(raw_tradovate_accounts, list):
                        for raw_acct in raw_tradovate_accounts:
                            acct_copy = dict(raw_acct) if isinstance(raw_acct, dict) else {}
                            if 'is_demo' not in acct_copy:
                                env_value = acct_copy.get('environment') or acct_copy.get('env')
                                name_value = acct_copy.get('name') or ''
                                inferred_demo = False
                                if isinstance(env_value, str):
                                    inferred_demo = env_value.lower() == 'demo'
                                elif isinstance(name_value, str):
                                    inferred_demo = name_value.upper().startswith('DEMO')
                                acct_copy['is_demo'] = inferred_demo
                            parsed_tradovate_accounts.append(acct_copy)
            except Exception as parse_err:
                logger.warning(f"Unable to parse tradovate_accounts for account {account['id']}: {parse_err}")
                parsed_tradovate_accounts = []
            
            has_demo = any(sub.get('is_demo') for sub in parsed_subaccounts) or \
                any(trad.get('is_demo') for trad in parsed_tradovate_accounts)
            has_live = any(not sub.get('is_demo') for sub in parsed_subaccounts) or \
                any(not trad.get('is_demo') for trad in parsed_tradovate_accounts)
            accounts_list.append({
                'id': account['id'],
                'name': account['name'],
                'broker': account['broker'] if 'broker' in account.keys() else '',
                'enabled': bool(account['enabled'] if 'enabled' in account.keys() else True),
                'created_at': account['created_at'] if 'created_at' in account.keys() else '',
                'tradovate_token': bool(account['tradovate_token'] if 'tradovate_token' in account.keys() else False),
                'is_connected': bool(account['tradovate_token'] if 'tradovate_token' in account.keys() else False),
                'subaccounts': parsed_subaccounts,
                'tradovate_accounts': parsed_tradovate_accounts,
                'has_demo': has_demo,
                'has_live': has_live
            })
        
        return jsonify({'success': True, 'accounts': accounts_list, 'count': len(accounts_list)})
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts', methods=['POST'])
def create_account():
    """Create a new account"""
    try:
        data = request.get_json()
        account_name = data.get('accountName') or data.get('name', '').strip()
        
        if not account_name:
            return jsonify({'success': False, 'error': 'Account name is required'}), 400
        
        conn = sqlite3.connect('just_trades.db')
        cursor = conn.cursor()
        
        # Check if account name already exists
        cursor.execute("SELECT id FROM accounts WHERE name = ?", (account_name,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Account name already exists'}), 400
        
        # Insert new account with default auth_type
        cursor.execute("""
            INSERT INTO accounts (name, broker, auth_type, enabled, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (account_name, 'Tradovate', 'oauth', 1, datetime.now().isoformat()))
        
        account_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Return success with redirect URL for broker selection
        return jsonify({
            'success': True,
            'account_id': account_id,
            'redirect': True,
            'broker_selection_url': f'/accounts/{account_id}/broker-selection',
            'connect_url': f'/api/accounts/{account_id}/connect'
        })
    except sqlite3.IntegrityError as e:
        logger.error(f"Database integrity error creating account: {e}")
        return jsonify({'success': False, 'error': 'Account name already exists or invalid data'}), 400
    except Exception as e:
        logger.error(f"Error creating account: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/accounts/<int:account_id>/broker-selection')
def broker_selection(account_id):
    """Render the broker selection page for a new account"""
    return render_template('broker_selection.html', account_id=account_id)

@app.route('/api/accounts/<int:account_id>/set-broker', methods=['POST'])
def set_broker(account_id):
    """Set broker for an account"""
    try:
        data = request.get_json()
        broker_name = data.get('broker') or data.get('brokerName', 'Tradovate')
        
        conn = sqlite3.connect('just_trades.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET broker = ? WHERE id = ?", (broker_name, account_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'broker': broker_name})
    except Exception as e:
        logger.error(f"Error setting broker: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>/connect')
def connect_account(account_id):
    """Redirect to Tradovate OAuth connection"""
    try:
        # ALWAYS use these OAuth app credentials: cid: 8699, secret: 7c74576b-20b1-4ea5-a2a0-eaeb11326a95
        # Do not use database values - these are the only credentials that work
        DEFAULT_CLIENT_ID = "8699"
        DEFAULT_CLIENT_SECRET = "7c74576b-20b1-4ea5-a2a0-eaeb11326a95"
        
        client_id = DEFAULT_CLIENT_ID  # Always use 8699
        
        # Build redirect URI - use fixed pattern without query parameters (OAuth standard)
        # OAuth apps need a fixed redirect URI registered in Tradovate
        # Use state parameter to pass account_id (OAuth standard practice)
        redirect_uri = None
        try:
            with open('ngrok_url.txt', 'r') as f:
                ngrok_url = f.read().strip()
                if ngrok_url and ngrok_url.startswith('http'):
                    # Use fixed redirect URI without query parameters
                    redirect_uri = f'{ngrok_url.rstrip("/")}/api/oauth/callback'
                    logger.info(f"Using ngrok redirect_uri: {redirect_uri}")
        except Exception as e:
            pass
        
        if not redirect_uri:
            # Use fixed redirect URI without query parameters
            redirect_uri = f'http://localhost:8082/api/oauth/callback'
        
        # Build OAuth URL - Tradovate OAuth endpoint (TradersPost pattern)
        # TradersPost uses: https://trader.tradovate.com/oauth with scope=All
        # Use state parameter to pass account_id (OAuth standard)
        from urllib.parse import quote_plus
        encoded_redirect_uri = quote_plus(redirect_uri)
        encoded_state = quote_plus(str(account_id))  # Pass account_id via state parameter
        # Try trader.tradovate.com first (TradersPost pattern), fallback to demo
        oauth_url = f'https://trader.tradovate.com/oauth?response_type=code&client_id={client_id}&redirect_uri={encoded_redirect_uri}&scope=All&state={encoded_state}'
        
        # Log to verify we're using the correct domain
        logger.info(f"OAuth URL domain check: {'demo.tradovate.com' if 'demo.tradovate.com' in oauth_url else 'WRONG DOMAIN - ' + oauth_url}")
        
        logger.info(f"Redirecting account {account_id} to OAuth: {oauth_url}")
        logger.info(f"Redirect URI (decoded): {redirect_uri}")
        return redirect(oauth_url)
    except Exception as e:
        logger.error(f"Error connecting account: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/oauth/callback')
def oauth_callback():
    """Handle OAuth callback from Tradovate"""
    try:
        # Get account_id from state parameter (OAuth standard way to pass data)
        account_id = request.args.get('state')
        if not account_id:
            logger.error("No account_id (state) in OAuth callback")
            return redirect(f'/accounts?error=no_account_id')
        
        account_id = int(account_id)
        
        code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            error_msg = request.args.get('error_description', error)
            logger.error(f"OAuth error for account {account_id}: {error_msg}")
            return redirect(f'/accounts?error=oauth_error&message={error_msg}')
        
        if not code:
            logger.error(f"No authorization code received for account {account_id}")
            return redirect(f'/accounts?error=no_code')
        
        # ALWAYS use these OAuth app credentials: cid: 8699, secret: 7c74576b-20b1-4ea5-a2a0-eaeb11326a95
        # Do not use database values - these are the only credentials that work
        DEFAULT_CLIENT_ID = "8699"
        DEFAULT_CLIENT_SECRET = "7c74576b-20b1-4ea5-a2a0-eaeb11326a95"
        
        client_id = DEFAULT_CLIENT_ID  # Always use 8699
        client_secret = DEFAULT_CLIENT_SECRET  # Always use the secret
        
        # Build redirect_uri to match what was sent (fixed URI without query parameters)
        redirect_uri = None
        try:
            with open('ngrok_url.txt', 'r') as f:
                ngrok_url = f.read().strip()
                if ngrok_url and ngrok_url.startswith('http'):
                    redirect_uri = f'{ngrok_url.rstrip("/")}/api/oauth/callback'
        except Exception as e:
            pass
        
        if not redirect_uri:
            redirect_uri = f'http://localhost:8082/api/oauth/callback'
        
        # Exchange authorization code for access token
        # According to OpenAPI spec, this endpoint expects JSON, not form data
        import requests
        token_url = 'https://demo.tradovateapi.com/v1/auth/oauthtoken'
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
            'client_id': client_id,
            'client_secret': client_secret  # Always include the secret
        }
        
        # Send as JSON according to OpenAPI spec
        response = requests.post(token_url, json=token_data, headers={'Content-Type': 'application/json'})
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('accessToken') or token_data.get('access_token')
            refresh_token = token_data.get('refreshToken') or token_data.get('refresh_token')
            md_access_token = token_data.get('mdAccessToken') or token_data.get('md_access_token')
            
            # Store tokens in database
            conn = sqlite3.connect('just_trades.db')
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE accounts 
                SET tradovate_token = ?, 
                    tradovate_refresh_token = ?,
                    md_access_token = ?,
                    token_expires_at = datetime('now', '+24 hours')
                WHERE id = ?
            """, (access_token, refresh_token, md_access_token, account_id))
            conn.commit()
            conn.close()
            
            # Fetch and store Tradovate account + subaccount metadata (TradersPost-style)
            if access_token:
                fetch_result = fetch_and_store_tradovate_accounts(account_id, access_token)
                if not fetch_result.get("success"):
                    logger.warning(f"Unable to fetch subaccounts after OAuth for account {account_id}: {fetch_result.get('error')}")
            
            logger.info(f"Successfully stored tokens for account {account_id}")
            return redirect(f'/accounts?success=true&connected={account_id}')
        else:
            logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
            return redirect(f'/accounts?error=token_exchange_failed&message={response.text[:100]}')
            
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return redirect(f'/accounts?error=callback_error&message={str(e)}')

@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """Delete an account"""
    try:
        conn = sqlite3.connect('just_trades.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        if deleted > 0:
            logger.info(f"Deleted account {account_id}")
            return jsonify({'success': True, 'message': 'Account deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Account not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>/refresh-subaccounts', methods=['POST'])
def refresh_account_subaccounts(account_id):
    """Refresh Tradovate subaccounts for an account using stored tokens"""
    try:
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tradovate_token 
            FROM accounts 
            WHERE id = ?
        """, (account_id,))
        row = cursor.fetchone()
        conn.close()
        if not row or not row['tradovate_token']:
            return jsonify({'success': False, 'error': 'Account not connected to Tradovate'}), 400
        
        fetch_result = fetch_and_store_tradovate_accounts(account_id, row['tradovate_token'])
        if fetch_result.get('success'):
            return jsonify({'success': True, 'subaccounts': fetch_result.get('subaccounts', [])})
        return jsonify({'success': False, 'error': fetch_result.get('error', 'Unable to refresh subaccounts')}), 400
    except Exception as e:
        logger.error(f"Error refreshing subaccounts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    """Get all strategies"""
    try:
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM strategies")
        strategies = cursor.fetchall()
        conn.close()
        
        strategies_list = []
        for strategy in strategies:
            strategies_list.append({
                'id': strategy['id'],
                'name': strategy['name'] if 'name' in strategy.keys() else None,
                'symbol': strategy['symbol'] if 'symbol' in strategy.keys() else None,
                'enabled': bool(strategy['enabled'] if 'enabled' in strategy.keys() else 1),
                'created_at': strategy['created_at'] if 'created_at' in strategy.keys() else None
            })
        
        return jsonify({'success': True, 'strategies': strategies_list})
    except Exception as e:
        logger.error(f"Error getting strategies: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/live-strategies', methods=['GET'])
def get_live_strategies():
    """Get all live/active strategies"""
    try:
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Try to get enabled strategies, fallback to all if enabled column doesn't exist
        try:
            cursor.execute("SELECT * FROM strategies WHERE enabled = 1")
        except sqlite3.OperationalError:
            # enabled column doesn't exist, get all strategies
            cursor.execute("SELECT * FROM strategies")
        strategies = cursor.fetchall()
        conn.close()
        
        strategies_list = []
        for strategy in strategies:
            strategies_list.append({
                'id': strategy['id'],
                'name': strategy['name'] if 'name' in strategy.keys() else None,
                'symbol': strategy['symbol'] if 'symbol' in strategy.keys() else None,
                'enabled': True,
                'created_at': strategy['created_at'] if 'created_at' in strategy.keys() else None
            })
        
        return jsonify({'success': True, 'strategies': strategies_list})
    except Exception as e:
        logger.error(f"Error getting live strategies: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/strategies')
def strategies():
    return render_template('strategies.html')

@app.route('/recorders', methods=['GET'])
def recorders_list():
    demo_recorders = [
        {'id': idx, 'name': name}
        for idx, name in enumerate([
            'JADDCAVIX', 'JADDCAVIXES', 'JADES', 'JADIND50', 'JADNQ', 'TEST2'
        ], start=1)
    ]
    return render_template('recorders_list.html', recorders=demo_recorders)

@app.route('/recorders/new')
def recorders_new():
    return render_template('recorders.html')

@app.route('/recorders/<int:recorder_id>')
def recorders_edit(recorder_id):
    return render_template('recorders.html')

@app.route('/traders')
def traders_list():
    demo_traders = [
        {'id': idx, 'name': name}
        for idx, name in enumerate(['JADDCAVIXES', 'JADES', 'JADIND50', 'JADNQ'], start=1)
    ]
    return render_template(
        'traders.html',
        mode='list',
        traders=demo_traders
    )

@app.route('/traders/new')
def traders_new():
    accounts = ['1302271','1367612','1381296','1393592','1492972','1503862','1523896','1536745','DEMO3890283','DEMO4419847-2','DEMO5253444']
    return render_template(
        'traders.html',
        mode='builder',
        header_title='Create New Trader',
        header_cta='Create Trader',
        strategy_names=['JADDCAVIX','JADES','JADIND50','JADNQ'],
        accounts=accounts
    )

@app.route('/traders/<int:trader_id>')
def traders_edit(trader_id):
    accounts = ['1302271','1367612','1381296','1393592','1492972','1503862','1523896','1536745','DEMO3890283','DEMO4419847-2','DEMO5253444']
    return render_template(
        'traders.html',
        mode='builder',
        header_title='Edit Trader',
        header_cta='Update Trader',
        strategy_names=['JADDCAVIX','JADES','JADIND50','JADNQ'],
        accounts=accounts
    )

@app.route('/control-center')
def control_center():
    return render_template('control_center.html')

@app.route('/manual-trader')
def manual_trader_page():
    return render_template('manual_copy_trader.html')

@app.route('/api/manual-trade', methods=['POST'])
def manual_trade():
    """Place a manual trade order"""
    try:
        data = request.get_json() or {}
        account_subaccount = data.get('account_subaccount', '')
        symbol = data.get('symbol', '').strip()
        side = data.get('side', '').strip()
        quantity = int(data.get('quantity', 1))
        risk_settings = data.get('risk') or {}
        
        if not account_subaccount:
            return jsonify({'success': False, 'error': 'Account not specified'}), 400
        if not symbol:
            return jsonify({'success': False, 'error': 'Symbol not specified'}), 400
        if not side:
            return jsonify({'success': False, 'error': 'Side not specified (Buy/Sell/Close)'}), 400
        if quantity < 1:
            return jsonify({'success': False, 'error': 'Quantity must be at least 1'}), 400
        
        parts = account_subaccount.split(':')
        account_id = int(parts[0])
        subaccount_id = parts[1] if len(parts) > 1 and parts[1] else None
        
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, tradovate_token, tradovate_refresh_token, md_access_token,
                   token_expires_at, tradovate_accounts
            FROM accounts 
            WHERE id = ? AND tradovate_token IS NOT NULL
        """, (account_id,))
        account = cursor.fetchone()
        if not account:
            conn.close()
            return jsonify({'success': False, 'error': 'Account not found or not connected'}), 400
        
        tradovate_accounts = []
        try:
            if account['tradovate_accounts']:
                tradovate_accounts = json.loads(account['tradovate_accounts'])
        except Exception as parse_err:
            logger.warning(f"Unable to parse tradovate_accounts for account {account_id}: {parse_err}")
            tradovate_accounts = []
        
        selected_subaccount = None
        if subaccount_id:
            for ta in tradovate_accounts:
                if str(ta.get('id')) == subaccount_id:
                    selected_subaccount = ta
                    break
        if not selected_subaccount and tradovate_accounts:
            selected_subaccount = tradovate_accounts[0]
            subaccount_id = str(selected_subaccount.get('id'))
        demo = True
        if selected_subaccount:
            if 'is_demo' in selected_subaccount:
                demo = bool(selected_subaccount.get('is_demo'))
            elif selected_subaccount.get('environment'):
                demo = selected_subaccount['environment'].lower() == 'demo'
        account_spec = (selected_subaccount.get('name') if selected_subaccount else None) or account['name'] or str(account_id)
        account_numeric_id = int(subaccount_id) if subaccount_id else account_id
        
        token_container = {
            'access_token': account['tradovate_token'],
            'refresh_token': account['tradovate_refresh_token'],
            'md_access_token': account['md_access_token']
        }
        
        expires_at = account['token_expires_at']
        needs_refresh = False
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at)
                if datetime.utcnow() >= exp_dt - timedelta(minutes=5):
                    needs_refresh = True
            except Exception:
                needs_refresh = False
        
        async def refresh_tokens(force=False):
            if not token_container.get('refresh_token'):
                return False
            if not force and not needs_refresh:
                return False
            from phantom_scraper.tradovate_integration import TradovateIntegration
            async with TradovateIntegration(demo=demo) as tradovate:
                tradovate.access_token = token_container['access_token']
                tradovate.refresh_token = token_container['refresh_token']
                tradovate.md_access_token = token_container['md_access_token']
                refreshed = await tradovate.refresh_access_token()
                if refreshed:
                    token_container['access_token'] = tradovate.access_token
                    token_container['refresh_token'] = tradovate.refresh_token
                return refreshed
        
        if needs_refresh and token_container['refresh_token']:
            refreshed = asyncio.run(refresh_tokens())
            if refreshed:
                new_expiry = (datetime.utcnow() + timedelta(hours=24)).isoformat()
                cursor.execute("""
                    UPDATE accounts
                    SET tradovate_token = ?, tradovate_refresh_token = ?, token_expires_at = ?
                    WHERE id = ?
                """, (token_container['access_token'], token_container['refresh_token'], new_expiry, account_id))
                conn.commit()
        conn.close()
        
        tradovate_symbol = convert_tradingview_to_tradovate_symbol(symbol, access_token=token_container['access_token'], demo=demo)
        trade_side = side.lower()
        if trade_side not in ('buy', 'sell', 'close'):
            return jsonify({'success': False, 'error': 'Invalid side supplied'}), 400
        order_side = 'Buy' if trade_side == 'buy' else 'Sell'
        if trade_side == 'close':
            order_side = 'Sell'
        
        from phantom_scraper.tradovate_integration import TradovateIntegration
        async def place_trade():
            async with TradovateIntegration(demo=demo) as tradovate:
                tradovate.access_token = token_container['access_token']
                tradovate.refresh_token = token_container['refresh_token']
                tradovate.md_access_token = token_container['md_access_token']
                
                if trade_side == 'close':
                    symbol_upper = tradovate_symbol.upper()
                    cancelled_before = await cancel_open_orders(tradovate, account_numeric_id, None)
                    positions = await tradovate.get_positions(account_numeric_id)
                    matched_positions = [pos for pos in positions if str(pos.get('symbol', '')).upper() == symbol_upper and pos.get('netPos')]
                    if not matched_positions:
                        if cancelled_before:
                            return {'success': True, 'message': f'Cancelled {cancelled_before} working orders for {symbol_upper}'}
                        return {'success': False, 'error': f'No open position found for {symbol}'}
                    results = []
                    total_closed = 0
                    for pos in matched_positions:
                        net_pos = pos.get('netPos')
                        if net_pos is None:
                            qty_field = pos.get('position') or pos.get('quantity') or pos.get('orderQty') or 0
                            net_pos = qty_field
                        qty = abs(int(net_pos or 0))
                        if qty == 0:
                            continue
                        close_side = 'Sell' if net_pos > 0 else 'Buy'
                        order_data = tradovate.create_market_order(
                            account_spec,
                            pos.get('symbol'),
                            close_side,
                            qty,
                            account_numeric_id
                        )
                        result = await tradovate.place_order(order_data)
                        if not result or not result.get('success'):
                            return result or {'success': False, 'error': 'Failed to close position'}
                        results.append(result)
                        total_closed += qty
                    cancelled_after = await cancel_open_orders(tradovate, account_numeric_id, None)
                    total_cancelled = cancelled_before + cancelled_after
                    message = f'Closed {total_closed} contracts for {symbol_upper}'
                    if total_cancelled:
                        message += f' and cancelled {total_cancelled} working orders'
                    if results:
                        last = results[-1]
                        last['message'] = message
                        return last
                    return {'success': True, 'message': message}
                else:
                    order_data = tradovate.create_market_order(
                        account_spec,
                        tradovate_symbol,
                        order_side,
                        quantity,
                        account_numeric_id
                    )
                    if risk_settings:
                        order_data.setdefault('customFields', {})['riskSettings'] = risk_settings
                    result = await tradovate.place_order(order_data)
                    if result and result.get('success') and risk_settings:
                        await apply_risk_orders(
                            tradovate,
                            account_spec,
                            account_numeric_id,
                            tradovate_symbol,
                            order_side,
                            quantity,
                            risk_settings
                        )
                    return result or {'success': False, 'error': 'Failed to place order'}
        
        result = asyncio.run(place_trade())
        if not result.get('success'):
            error_text = str(result.get('error', '')).lower()
            if any(msg in error_text for msg in ['access is denied', 'expired access token']):
                refreshed = asyncio.run(refresh_tokens(force=True))
                if refreshed:
                    result = asyncio.run(place_trade())
        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error', 'Failed to place order')}), 400

        return jsonify({
            'success': True,
            'message': f'{side} order placed for {quantity} {symbol}',
            'order_id': result.get('orderId', 'N/A')
        })
            
    except Exception as e:
        logger.error(f"Error placing manual trade: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/affiliate')
def affiliate():
    return render_template('affiliate.html')

# API Endpoints for Dashboard Filters
@app.route('/api/dashboard/users', methods=['GET'])
def api_dashboard_users():
    """Get list of users for filter dropdown"""
    try:
        try:
            from app.database import SessionLocal
            from app.models import User
            
            db = SessionLocal()
            users = db.query(User).order_by(User.username).all()
            db.close()
            
            return jsonify({
                'users': [{'id': u.id, 'username': u.username, 'email': u.email} for u in users],
                'current_user_id': None  # TODO: Get from session when auth is implemented
            })
        except ImportError:
            # Database modules not available, return empty list
            return jsonify({'error': 'Database not configured', 'users': []}), 200
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return jsonify({'error': 'Failed to fetch users', 'users': []}), 500

@app.route('/api/dashboard/strategies', methods=['GET'])
def api_dashboard_strategies():
    """Get list of strategies for filter dropdown"""
    try:
        try:
            from app.database import SessionLocal
            from app.models import Strategy
            
            db = SessionLocal()
            # Get all active strategies, or all if none specified
            user_id = request.args.get('user_id')
            query = db.query(Strategy)
            if user_id:
                query = query.filter(Strategy.user_id == user_id)
            strategies = query.filter(Strategy.active == True).order_by(Strategy.name).all()
            db.close()
            
            return jsonify({
                'strategies': [{
                    'id': s.id,
                    'name': s.name,
                    'symbol': s.symbol,
                    'user_id': s.user_id,
                    'recording_enabled': s.recording_enabled
                } for s in strategies]
            })
        except ImportError:
            return jsonify({'error': 'Database not configured', 'strategies': []}), 200
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        return jsonify({'error': 'Failed to fetch strategies', 'strategies': []}), 500

@app.route('/api/dashboard/chart-data', methods=['GET'])
def api_dashboard_chart_data():
    """Get chart data (profit vs drawdown) with optional filters"""
    try:
        from app.database import SessionLocal
        from app.models import RecordedPosition, Strategy
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        db = SessionLocal()
        
        # Get filter parameters (empty = show all)
        user_id = request.args.get('user_id')
        strategy_id = request.args.get('strategy_id')
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', 'all')
        
        # Build query for recorded positions
        query = db.query(RecordedPosition)
        
        # Apply filters
        if user_id:
            # Filter by user's strategies
            strategy_ids = db.query(Strategy.id).filter(Strategy.user_id == user_id).subquery()
            query = query.filter(RecordedPosition.strategy_id.in_(strategy_ids))
        if strategy_id:
            query = query.filter(RecordedPosition.strategy_id == strategy_id)
        if symbol:
            query = query.filter(RecordedPosition.symbol == symbol)
        
        # Apply timeframe filter
        if timeframe and timeframe != 'all':
            now = datetime.utcnow()
            if timeframe == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif timeframe == 'week':
                start_date = now - timedelta(days=7)
            elif timeframe == 'month':
                start_date = now - timedelta(days=30)
            elif timeframe == '3months':
                start_date = now - timedelta(days=90)
            elif timeframe == '6months':
                start_date = now - timedelta(days=180)
            elif timeframe == 'year':
                start_date = now - timedelta(days=365)
            else:
                start_date = None
            
            if start_date:
                query = query.filter(RecordedPosition.entry_timestamp >= start_date)
        
        # Get all positions
        positions = query.order_by(RecordedPosition.entry_timestamp).all()
        
        # Calculate cumulative profit and max drawdown per day
        # Group by date and calculate daily totals
        daily_data = {}
        for pos in positions:
            if pos.exit_timestamp:  # Use exit timestamp for closed positions
                date_key = pos.exit_timestamp.date()
                if date_key not in daily_data:
                    daily_data[date_key] = {'profit': 0, 'max_drawdown': 0, 'daily_losses': []}
                if pos.pnl:
                    daily_data[date_key]['profit'] += pos.pnl
                    # Track individual losses for max DD calculation
                    if pos.pnl < 0:
                        daily_data[date_key]['daily_losses'].append(abs(pos.pnl))
        
        # Calculate max drawdown per day (worst single loss or sum of losses if all negative)
        for date_key in daily_data:
            if daily_data[date_key]['daily_losses']:
                # Max DD is the worst single loss OR the total of all losses if all trades were losses
                daily_losses = daily_data[date_key]['daily_losses']
                max_single_loss = max(daily_losses)
                total_losses = sum(daily_losses)
                # Use the maximum of single worst loss or total losses
                daily_data[date_key]['max_drawdown'] = max(max_single_loss, total_losses)
            else:
                daily_data[date_key]['max_drawdown'] = 0
        
        # Sort by date and calculate cumulative profit, but keep max DD per day (not cumulative)
        sorted_dates = sorted(daily_data.keys())
        labels = [date.strftime('%b %d') for date in sorted_dates]
        cumulative_profit = []
        max_drawdown_per_day = []  # Max DD for each day (not cumulative)
        running_profit = 0
        
        for date in sorted_dates:
            running_profit += daily_data[date]['profit']
            cumulative_profit.append(running_profit)
            # Max DD per day (not cumulative - represents that day's worst drawdown)
            max_drawdown_per_day.append(daily_data[date]['max_drawdown'])
        
        db.close()
        
        # If no data, return empty arrays (will show empty chart)
        if not labels:
            return jsonify({
                'labels': [],
                'profit': [],
                'drawdown': []
            })
        
        return jsonify({
            'labels': labels,
            'profit': cumulative_profit,
            'drawdown': max_drawdown_per_day  # Max DD per day, not cumulative
        })
    except Exception as e:
        logger.error(f"Error fetching chart data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch chart data', 'labels': [], 'profit': [], 'drawdown': []}), 500

@app.route('/api/dashboard/trade-history', methods=['GET'])
def api_dashboard_trade_history():
    """Get trade history with optional filters"""
    try:
        from app.database import SessionLocal
        from app.models import RecordedPosition, Strategy, Trade
        from datetime import datetime, timedelta
        
        db = SessionLocal()
        
        # Get filter parameters (empty = show all)
        user_id = request.args.get('user_id')
        strategy_id = request.args.get('strategy_id')
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', 'all')
        
        # Use recorded_positions as the source (recorder tracks all trades)
        query = db.query(RecordedPosition)
        
        # Apply filters
        if user_id:
            strategy_ids = db.query(Strategy.id).filter(Strategy.user_id == user_id).subquery()
            query = query.filter(RecordedPosition.strategy_id.in_(strategy_ids))
        if strategy_id:
            query = query.filter(RecordedPosition.strategy_id == strategy_id)
        if symbol:
            query = query.filter(RecordedPosition.symbol == symbol)
        
        # Apply timeframe filter
        if timeframe and timeframe != 'all':
            now = datetime.utcnow()
            if timeframe == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif timeframe == 'week':
                start_date = now - timedelta(days=7)
            elif timeframe == 'month':
                start_date = now - timedelta(days=30)
            elif timeframe == '3months':
                start_date = now - timedelta(days=90)
            elif timeframe == '6months':
                start_date = now - timedelta(days=180)
            elif timeframe == 'year':
                start_date = now - timedelta(days=365)
            else:
                start_date = None
            
            if start_date:
                query = query.filter(RecordedPosition.entry_timestamp >= start_date)
        
        # Get closed positions (trades) with pagination
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page
        
        # Get total count for pagination
        total_count = query.filter(RecordedPosition.status == 'closed').count()
        
        # Get paginated results
        positions = query.filter(RecordedPosition.status == 'closed').order_by(RecordedPosition.exit_timestamp.desc()).limit(per_page).offset(offset).all()
        
        # Format for frontend
        trades = []
        for pos in positions:
            strategy = db.query(Strategy).filter(Strategy.id == pos.strategy_id).first()
            trades.append({
                'open_time': pos.entry_timestamp.isoformat() if pos.entry_timestamp else None,
                'closed_time': pos.exit_timestamp.isoformat() if pos.exit_timestamp else None,
                'strategy': strategy.name if strategy else 'N/A',
                'symbol': pos.symbol,
                'side': pos.side,
                'size': pos.quantity,
                'entry_price': pos.entry_price,
                'exit_price': pos.exit_price,
                'profit': pos.pnl or 0,
                'drawdown': pos.pnl if pos.pnl and pos.pnl < 0 else 0
            })
        
        db.close()
        
        # Calculate pagination info
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        
        return jsonify({
            'trades': trades,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        })
    except Exception as e:
        logger.error(f"Error fetching trade history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch trade history', 'trades': []}), 500

@app.route('/api/dashboard/metrics', methods=['GET'])
def api_dashboard_metrics():
    """Get metric cards data with optional filters"""
    try:
        from app.database import SessionLocal
        from app.models import RecordedPosition, Strategy
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        db = SessionLocal()
        
        # Get filter parameters (empty = show all)
        user_id = request.args.get('user_id')
        strategy_id = request.args.get('strategy_id')
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', 'all')
        
        # Build query for recorded positions
        query = db.query(RecordedPosition)
        
        # Apply filters
        if user_id:
            strategy_ids = db.query(Strategy.id).filter(Strategy.user_id == user_id).subquery()
            query = query.filter(RecordedPosition.strategy_id.in_(strategy_ids))
        if strategy_id:
            query = query.filter(RecordedPosition.strategy_id == strategy_id)
        if symbol:
            query = query.filter(RecordedPosition.symbol == symbol)
        
        # Apply timeframe filter
        if timeframe and timeframe != 'all':
            now = datetime.utcnow()
            if timeframe == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif timeframe == 'week':
                start_date = now - timedelta(days=7)
            elif timeframe == 'month':
                start_date = now - timedelta(days=30)
            elif timeframe == '3months':
                start_date = now - timedelta(days=90)
            elif timeframe == '6months':
                start_date = now - timedelta(days=180)
            elif timeframe == 'year':
                start_date = now - timedelta(days=365)
            else:
                start_date = None
            
            if start_date:
                query = query.filter(RecordedPosition.entry_timestamp >= start_date)
        
        # Get all closed positions for calculations
        positions = query.filter(RecordedPosition.status == 'closed').all()
        
        # Calculate metrics
        total_trades = len(positions)
        wins = [p for p in positions if p.pnl and p.pnl > 0]
        losses = [p for p in positions if p.pnl and p.pnl < 0]
        
        total_profit = sum(p.pnl for p in positions if p.pnl)
        total_wins = sum(p.pnl for p in wins)
        total_losses = abs(sum(p.pnl for p in losses))
        
        # Cumulative Return
        cumulative_return = {
            'return': total_profit or 0,
            'time_traded': calculate_time_traded(positions)
        }
        
        # Win Rate
        win_rate = {
            'wins': len(wins),
            'losses': len(losses),
            'percentage': round((len(wins) / total_trades * 100) if total_trades > 0 else 0, 1)
        }
        
        # Drawdown
        drawdowns = [abs(p.pnl) for p in losses if p.pnl]
        drawdown = {
            'max': max(drawdowns) if drawdowns else 0,
            'avg': sum(drawdowns) / len(drawdowns) if drawdowns else 0,
            'run': max(drawdowns) if drawdowns else 0  # Same as max for now
        }
        
        # Total ROI (simplified - would need initial capital)
        total_roi = 0  # TODO: Calculate based on initial capital
        
        # Contracts Held
        quantities = [p.quantity for p in positions if p.quantity]
        contracts_held = {
            'max': max(quantities) if quantities else 0,
            'avg': round(sum(quantities) / len(quantities)) if quantities else 0
        }
        
        # Max/Avg PNL
        win_pnls = [p.pnl for p in wins if p.pnl]
        loss_pnls = [abs(p.pnl) for p in losses if p.pnl]
        pnl = {
            'max_profit': max(win_pnls) if win_pnls else 0,
            'avg_profit': sum(win_pnls) / len(win_pnls) if win_pnls else 0,
            'max_loss': max(loss_pnls) if loss_pnls else 0,
            'avg_loss': sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0
        }
        
        # Profit Factor
        profit_factor = (total_wins / total_losses) if total_losses > 0 else (total_wins if total_wins > 0 else 0)
        
        db.close()
        
        return jsonify({
            'metrics': {
                'cumulative_return': cumulative_return,
                'win_rate': win_rate,
                'drawdown': drawdown,
                'total_roi': total_roi,
                'contracts_held': contracts_held,
                'pnl': pnl,
                'profit_factor': round(profit_factor, 2)
            }
        })
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch metrics', 'metrics': {}}), 500

def calculate_time_traded(positions):
    """Calculate time traded string like '1M 1D'"""
    if not positions:
        return '0D'
    
    dates = [p.entry_timestamp.date() for p in positions if p.entry_timestamp]
    if not dates:
        return '0D'
    
    min_date = min(dates)
    max_date = max(dates)
    delta = max_date - min_date
    
    months = delta.days // 30
    days = delta.days % 30
    
    if months > 0 and days > 0:
        return f'{months}M {days}D'
    elif months > 0:
        return f'{months}M'
    else:
        return f'{days}D'

@app.route('/api/dashboard/calendar-data', methods=['GET'])
def api_dashboard_calendar_data():
    """Get daily PnL data for calendar view"""
    try:
        from app.database import SessionLocal
        from app.models import RecordedPosition, Strategy
        from datetime import datetime, timedelta
        from sqlalchemy import func, extract
        
        db = SessionLocal()
        
        # Get filter parameters (empty = show all)
        user_id = request.args.get('user_id')
        strategy_id = request.args.get('strategy_id')
        symbol = request.args.get('symbol')
        timeframe = request.args.get('timeframe', 'all')
        
        # Use recorded_positions as the source
        query = db.query(RecordedPosition)
        
        # Apply filters
        if user_id:
            strategy_ids = db.query(Strategy.id).filter(Strategy.user_id == user_id).subquery()
            query = query.filter(RecordedPosition.strategy_id.in_(strategy_ids))
        if strategy_id:
            query = query.filter(RecordedPosition.strategy_id == strategy_id)
        if symbol:
            query = query.filter(RecordedPosition.symbol == symbol)
        
        # Apply timeframe filter
        if timeframe and timeframe != 'all':
            now = datetime.utcnow()
            if timeframe == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif timeframe == 'week':
                start_date = now - timedelta(days=7)
            elif timeframe == 'month':
                start_date = now - timedelta(days=30)
            elif timeframe == '3months':
                start_date = now - timedelta(days=90)
            elif timeframe == '6months':
                start_date = now - timedelta(days=180)
            elif timeframe == 'year':
                start_date = now - timedelta(days=365)
            else:
                start_date = None
            
            if start_date:
                query = query.filter(RecordedPosition.entry_timestamp >= start_date)
        
        # Get closed positions only
        query = query.filter(RecordedPosition.status == 'closed')
        
        # Group by date and calculate daily PnL
        positions = query.all()
        
        # Group by date
        daily_data = {}
        for pos in positions:
            if pos.exit_timestamp:
                date_key = pos.exit_timestamp.date()
                pnl = pos.pnl or 0
                
                if date_key not in daily_data:
                    daily_data[date_key] = {
                        'pnl': 0,
                        'trades': 0
                    }
                
                daily_data[date_key]['pnl'] += pnl
                daily_data[date_key]['trades'] += 1
        
        # Format for frontend
        calendar_data = {}
        for date_key, data in daily_data.items():
            date_str = date_key.isoformat()
            calendar_data[date_str] = {
                'pnl': round(data['pnl'], 2),
                'trades': data['trades']
            }
        
        db.close()
        
        return jsonify({'calendar_data': calendar_data})
    except Exception as e:
        logger.error(f"Error fetching calendar data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to fetch calendar data', 'calendar_data': {}}), 500

@app.route('/api/news-feed', methods=['GET'])
def api_news_feed():
    """Get financial news from RSS feeds"""
    try:
        import feedparser
        import urllib.parse
        
        # Try Yahoo Finance RSS (free, no API key needed)
        feeds = [
            'https://feeds.finance.yahoo.com/rss/2.0/headline?s=ES=F,NQ=F,YM=F&region=US&lang=en-US',
            'https://www.financialjuice.com/feed'
        ]
        
        news_items = []
        
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:  # Get first 5 items
                    title = entry.get('title', '')[:80]  # Limit length
                    if title:
                        news_items.append({
                            'title': title,
                            'link': entry.get('link', '#')
                        })
            except Exception as e:
                logger.warning(f"Error parsing feed {feed_url}: {e}")
                continue
        
        # If no news, return sample data
        if not news_items:
            news_items = [
                {'title': 'Markets open higher on positive economic data', 'link': '#'},
                {'title': 'Fed signals potential rate adjustments ahead', 'link': '#'},
                {'title': 'Tech stocks rally on strong earnings reports', 'link': '#'},
                {'title': 'Futures trading volume hits record highs', 'link': '#'}
            ]
        
        return jsonify({'news': news_items[:10]})  # Return up to 10 items
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        # Return sample data on error
        return jsonify({
            'news': [
                {'title': 'Markets open higher on positive economic data', 'link': '#'},
                {'title': 'Fed signals potential rate adjustments ahead', 'link': '#'},
                {'title': 'Tech stocks rally on strong earnings reports', 'link': '#'}
            ]
        })

@app.route('/api/market-data', methods=['GET'])
def api_market_data():
    """Get market data for ticker"""
    try:
        # Sample market data (in production, you'd fetch from an API)
        market_data = [
            {'symbol': 'ES1!', 'change': '+1.25%', 'direction': 'up'},
            {'symbol': 'NQ1!', 'change': '+0.89%', 'direction': 'up'},
            {'symbol': 'MNQ1!', 'change': '-0.42%', 'direction': 'down'},
            {'symbol': 'YM1!', 'change': '+0.67%', 'direction': 'up'},
            {'symbol': 'RTY1!', 'change': '+1.12%', 'direction': 'up'},
            {'symbol': 'CL1!', 'change': '+2.34%', 'direction': 'up'},
            {'symbol': 'GC1!', 'change': '-0.15%', 'direction': 'down'},
        ]
        return jsonify({'data': market_data})
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")
        return jsonify({'data': []})

@app.route('/api/stock-heatmap', methods=['GET'])
def api_stock_heatmap():
    """Get stock heatmap data from Finnhub (primary) or Yahoo Finance (fallback)"""
    try:
        # Check if Finnhub API key is set (optional - falls back to Yahoo if not)
        finnhub_api_key = os.environ.get('FINNHUB_API_KEY', None)
        
        # Try Finnhub first if API key is available
        if finnhub_api_key:
            try:
                return get_finnhub_heatmap_data(finnhub_api_key)
            except Exception as e:
                logger.warning(f"Finnhub API failed, falling back to Yahoo Finance: {e}")
        
        # Fallback to Yahoo Finance (current implementation)
        return get_yahoo_heatmap_data()
    except Exception as e:
        logger.error(f"Error fetching heatmap data: {e}")
        return get_sample_heatmap_data()

def get_finnhub_heatmap_data(api_key):
    """Fetch stock data from Finnhub API"""
    symbols_with_cap = [
        {'symbol': 'NVDA', 'market_cap': 3000},
        {'symbol': 'MSFT', 'market_cap': 3200},
        {'symbol': 'AAPL', 'market_cap': 3500},
        {'symbol': 'GOOGL', 'market_cap': 2000},
        {'symbol': 'AMZN', 'market_cap': 1900},
        {'symbol': 'META', 'market_cap': 1300},
        {'symbol': 'TSLA', 'market_cap': 800},
        {'symbol': 'AVGO', 'market_cap': 600},
        {'symbol': 'ORCL', 'market_cap': 500},
        {'symbol': 'AMD', 'market_cap': 300},
        {'symbol': 'NFLX', 'market_cap': 280},
        {'symbol': 'CSCO', 'market_cap': 250},
        {'symbol': 'INTC', 'market_cap': 200},
        {'symbol': 'MU', 'market_cap': 150},
        {'symbol': 'PLTR', 'market_cap': 50},
        {'symbol': 'HOOD', 'market_cap': 20},
    ]
    
    heatmap_data = []
    successful_fetches = 0
    
    for stock_info in symbols_with_cap[:16]:
        symbol = stock_info['symbol']
        market_cap = stock_info['market_cap']
        
        try:
            # Finnhub quote endpoint
            url = f'https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}'
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                current_price = data.get('c', 0)  # Current price
                previous_close = data.get('pc', current_price)  # Previous close
                
                # Finnhub returns change percentage directly as 'dp' (daily percent change)
                change_pct_raw = data.get('dp', None)
                
                if change_pct_raw is not None:
                    # Finnhub returns percentage directly (e.g., 1.65 for 1.65%)
                    change_pct = change_pct_raw
                elif current_price > 0 and previous_close > 0 and previous_close != current_price:
                    # Calculate from price difference
                    change_pct = ((current_price - previous_close) / previous_close) * 100
                else:
                    change_pct = 0
                
                if current_price > 0:
                    
                    # Get market cap from company profile
                    profile_url = f'https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={api_key}'
                    profile_response = requests.get(profile_url, timeout=2)
                    real_market_cap = market_cap  # Default to provided market cap
                    
                    if profile_response.status_code == 200:
                        profile = profile_response.json()
                        if 'marketCapitalization' in profile:
                            finnhub_market_cap = profile['marketCapitalization']
                            # Finnhub returns market cap in raw number, convert to billions
                            if finnhub_market_cap and finnhub_market_cap > 1000:  # Sanity check
                                real_market_cap = finnhub_market_cap / 1_000_000_000  # Convert to billions
                            # If the value seems wrong (too small), use fallback
                            if real_market_cap < 10:  # If less than 10B, it's probably wrong
                                real_market_cap = market_cap  # Use provided fallback
                    
                    heatmap_data.append({
                        'symbol': symbol,
                        'price': round(current_price, 2),
                        'change': round(change_pct, 2),
                        'change_pct': f"{'+' if change_pct >= 0 else ''}{round(change_pct, 2)}%",
                        'market_cap': real_market_cap
                    })
                    successful_fetches += 1
                    logger.info(f"Finnhub: Successfully fetched {symbol}: ${current_price:.2f} ({change_pct:+.2f}%)")
        except Exception as e:
            logger.warning(f"Error fetching {symbol} from Finnhub: {e}")
            continue
    
    logger.info(f"Finnhub API: Successfully fetched {successful_fetches} stocks")
    
    if heatmap_data:
        return jsonify({'stocks': heatmap_data})
    else:
        raise Exception("No data from Finnhub")

def get_yahoo_heatmap_data():
    """Get stock heatmap data from Yahoo Finance (fallback)"""
    try:
        # Most active tech stocks with approximate market cap order (largest first)
        # Market cap data for sizing the treemap
        symbols_with_cap = [
            {'symbol': 'NVDA', 'market_cap': 3000},  # Largest - top left
            {'symbol': 'MSFT', 'market_cap': 3200},
            {'symbol': 'AAPL', 'market_cap': 3500},
            {'symbol': 'GOOGL', 'market_cap': 2000},
            {'symbol': 'AMZN', 'market_cap': 1900},
            {'symbol': 'META', 'market_cap': 1300},
            {'symbol': 'TSLA', 'market_cap': 800},
            {'symbol': 'AVGO', 'market_cap': 600},
            {'symbol': 'ORCL', 'market_cap': 500},
            {'symbol': 'AMD', 'market_cap': 300},
            {'symbol': 'NFLX', 'market_cap': 280},
            {'symbol': 'CSCO', 'market_cap': 250},
            {'symbol': 'INTC', 'market_cap': 200},
            {'symbol': 'MU', 'market_cap': 150},
            {'symbol': 'PLTR', 'market_cap': 50},
            {'symbol': 'HOOD', 'market_cap': 20},
        ]
        
        # Fetch data from Yahoo Finance (using their public API)
        heatmap_data = []
        successful_fetches = 0
        for stock_info in symbols_with_cap[:16]:  # Limit to 16 for treemap layout
            symbol = stock_info['symbol']
            market_cap = stock_info['market_cap']
            try:
                # Yahoo Finance quote endpoint (no API key needed)
                url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d'
                response = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code == 200:
                    data = response.json()
                    if 'chart' in data and 'result' in data['chart'] and len(data['chart']['result']) > 0:
                        result = data['chart']['result'][0]
                        if 'meta' in result:
                            meta = result['meta']
                            current_price = meta.get('regularMarketPrice', 0)
                            previous_close = meta.get('previousClose', current_price)
                            
                            # Try to get change percentage directly from Yahoo Finance
                            # This is more accurate, especially when market is closed
                            change_pct_raw = meta.get('regularMarketChangePercent', None)
                            
                            if change_pct_raw is not None:
                                # Yahoo Finance returns as decimal (e.g., 0.0165 for 1.65%)
                                change_pct = change_pct_raw * 100
                            elif current_price > 0 and previous_close > 0 and previous_close != current_price:
                                # Calculate from price difference
                                change_pct = ((current_price - previous_close) / previous_close) * 100
                            else:
                                # If no change data available, skip this stock or use 0
                                change_pct = 0
                            
                            # Try to get real market cap from Yahoo Finance
                            real_market_cap = meta.get('marketCap', None)
                            if real_market_cap:
                                # Convert to billions for easier comparison
                                market_cap_billions = real_market_cap / 1_000_000_000
                            else:
                                # Fallback to provided market cap
                                market_cap_billions = market_cap
                            
                            if current_price > 0:
                                heatmap_data.append({
                                    'symbol': symbol,
                                    'price': round(current_price, 2),
                                    'change': round(change_pct, 2),
                                    'change_pct': f"{'+' if change_pct >= 0 else ''}{round(change_pct, 2)}%",
                                    'market_cap': market_cap_billions  # Real market cap in billions
                                })
                                successful_fetches += 1
                                logger.info(f"Successfully fetched {symbol}: ${current_price:.2f} ({change_pct:+.2f}%)")
            except Exception as e:
                logger.warning(f"Error fetching data for {symbol}: {e}")
                continue
        
        logger.info(f"Yahoo Finance API: Successfully fetched {successful_fetches} stocks out of {len(symbols_with_cap[:16])}")
        
        if heatmap_data:
            return jsonify({'stocks': heatmap_data})
        else:
            raise Exception("No data from Yahoo Finance")
    except Exception as e:
        logger.error(f"Error in Yahoo Finance API: {e}")
        raise

def get_sample_heatmap_data():
    """Return sample data as last resort"""
    return jsonify({
        'stocks': [
            {'symbol': 'NVDA', 'price': 189.94, 'change': 1.65, 'change_pct': '+1.65%', 'market_cap': 3000},
            {'symbol': 'MSFT', 'price': 428.50, 'change': 1.29, 'change_pct': '+1.29%', 'market_cap': 3200},
            {'symbol': 'AAPL', 'price': 189.94, 'change': 1.65, 'change_pct': '+1.65%', 'market_cap': 3500},
            {'symbol': 'GOOGL', 'price': 175.20, 'change': -0.16, 'change_pct': '-0.16%', 'market_cap': 2000},
            {'symbol': 'AMZN', 'price': 185.30, 'change': -0.11, 'change_pct': '-0.11%', 'market_cap': 1900},
            {'symbol': 'META', 'price': 512.80, 'change': 0.28, 'change_pct': '+0.28%', 'market_cap': 1300},
            {'symbol': 'TSLA', 'price': 408.83, 'change': 1.70, 'change_pct': '+1.70%', 'market_cap': 800},
            {'symbol': 'AVGO', 'price': 150.20, 'change': 1.20, 'change_pct': '+1.20%', 'market_cap': 600},
            {'symbol': 'ORCL', 'price': 145.30, 'change': 3.87, 'change_pct': '+3.87%', 'market_cap': 500},
            {'symbol': 'AMD', 'price': 185.50, 'change': 1.91, 'change_pct': '+1.91%', 'market_cap': 300},
        ]
    })

@app.route('/webhooks', methods=['POST'])
def create_webhook():
    data = request.get_json()
    url = data.get('url')
    method = data.get('method')
    headers = data.get('headers')
    body = data.get('body')

    if not url or not method:
        return jsonify({'error': 'URL and method are required'}), 400

    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO webhooks (url, method, headers, body)
        VALUES (?, ?, ?, ?)
    ''', (url, method, headers, body))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Webhook created successfully'}), 201

@app.route('/webhooks', methods=['GET'])
def get_webhooks():
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM webhooks')
    webhooks = cursor.fetchall()
    conn.close()

    return jsonify([{
        'id': w[0],
        'url': w[1],
        'method': w[2],
        'headers': w[3],
        'body': w[4],
        'created_at': w[5]
    } for w in webhooks])

@app.route('/webhooks/<int:id>', methods=['GET'])
def get_webhook(id):
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM webhooks WHERE id = ?', (id,))
    webhook = cursor.fetchone()
    conn.close()

    if webhook:
        return jsonify({
            'id': webhook[0],
            'url': webhook[1],
            'method': webhook[2],
            'headers': webhook[3],
            'body': webhook[4],
            'created_at': webhook[5]
        })
    return jsonify({'error': 'Webhook not found'}), 404

@app.route('/webhooks/<int:id>', methods=['DELETE'])
def delete_webhook(id):
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM webhooks WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return '', 204

# Initialize database on import (for gunicorn)
try:
    init_db()
except Exception as e:
    logger.warning(f"Database initialization warning: {e}")

# Configure logging for production
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == '__main__':
    # For local development
    parser = argparse.ArgumentParser(description='Start the trading webhook server.')
    parser.add_argument('--port', type=int, default=8082, help='Port to run the server on.')
    args = parser.parse_args()

    port = args.port
    logger.info(f"Starting Just.Trades. server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
