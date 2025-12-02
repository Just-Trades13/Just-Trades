#!/usr/bin/env python3
"""
⚠️ CRITICAL FOR AI ASSISTANTS: READ START_HERE.md BEFORE MODIFYING THIS FILE

PROTECTION RULES:
- Tab Isolation: Only modify files for the tab you're working on (see TAB_ISOLATION_MAP.md)
- Protected Functions: Account management functions are PROTECTED (see ACCOUNT_MGMT_SNAPSHOT.md)
- Verify Before Fixing: Don't fix things that aren't broken
- One Change at a Time: Make minimal, focused changes

See START_HERE.md for complete protection rules.
"""
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
import threading
import requests
from typing import Optional
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta

# WebSocket support for Tradovate market data
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    # Logger not defined yet, will log later


# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed, skip (optional dependency)
    pass

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Initialize SocketIO for WebSocket support (like Trade Manager)
# Use 'eventlet' or 'gevent' if available, otherwise fall back to threading
try:
    import eventlet
    eventlet.monkey_patch()
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
    logger.info("SocketIO using eventlet async mode")
except ImportError:
    try:
        import gevent
        from gevent import monkey
        monkey.patch_all()
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')
        logger.info("SocketIO using gevent async mode")
    except ImportError:
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=True, engineio_logger=True)
        logger.info("SocketIO using threading async mode (fallback)")

# ⚠️ SECURITY WARNING: API credentials should be stored in environment variables or secure config
# These are default credentials - prefer storing in .env file or environment variables
# Example: TRADOVATE_API_CID=8720, TRADOVATE_API_SECRET=your-secret
TRADOVATE_API_CID = int(os.getenv('TRADOVATE_API_CID', '8720'))
TRADOVATE_API_SECRET = os.getenv('TRADOVATE_API_SECRET', 'e76ee8d1-d168-4252-a59e-f11a8b0cdae4')

# Contract multipliers for PnL calculation
CONTRACT_MULTIPLIERS = {
    'MES': 5.0,    # Micro E-mini S&P 500: $5 per point
    'MNQ': 2.0,    # Micro E-mini Nasdaq: $2 per point
    'ES': 50.0,    # E-mini S&P 500: $50 per point
    'NQ': 20.0,    # E-mini Nasdaq: $20 per point
    'MYM': 5.0,    # Micro E-mini Dow: $5 per point
    'YM': 5.0,     # E-mini Dow: $5 per point
    'M2K': 5.0,    # Micro E-mini Russell 2000: $5 per point
    'RTY': 50.0,   # E-mini Russell 2000: $50 per point
}

def get_contract_multiplier(symbol: str) -> float:
    """Get contract multiplier for a symbol"""
    symbol_upper = symbol.upper().strip()
    
    # Try to match known base symbols (2-3 characters)
    # Check 3-char symbols first (MES, MNQ, M2K, etc.)
    if symbol_upper[:3] in CONTRACT_MULTIPLIERS:
        return CONTRACT_MULTIPLIERS[symbol_upper[:3]]
    
    # Check 2-char symbols (ES, NQ, YM, etc.)
    if symbol_upper[:2] in CONTRACT_MULTIPLIERS:
        return CONTRACT_MULTIPLIERS[symbol_upper[:2]]
    
    # Fallback: remove month codes and numbers
    # Month codes: F, G, H, J, K, M, N, Q, U, V, X, Z
    base_symbol = re.sub(r'[0-9!]+', '', symbol_upper)  # Remove numbers and !
    base_symbol = re.sub(r'[FGHJKMNQUVXZ]$', '', base_symbol)  # Remove trailing month code
    
    return CONTRACT_MULTIPLIERS.get(base_symbol, 1.0)

def get_market_price_simple(symbol: str) -> Optional[float]:
    """
    Get current market price using a simple HTTP endpoint.
    This is a placeholder - you'll need to integrate with:
    - TradingView API (free tier available)
    - Tradovate WebSocket market data (requires subscription)
    - Or another market data provider
    """
    try:
        # For now, return None - will be implemented with market data source
        # TradingView has a free API: https://symbol-search.tradingview.com/
        # Or use: https://scanner.tradingview.com/symbols?exchange=CME&symbol=MES1!
        logger.debug(f"Market data not yet implemented for {symbol}")
        return None
    except Exception as e:
        logger.error(f"Error getting market price for {symbol}: {e}")
        return None

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
    """
    Apply risk management orders (TP/SL) as OCO (One-Cancels-Other) using Tradovate's order strategy.
    When TP hits, SL is automatically cancelled (and vice versa).
    """
    logger.info(f"🎯 apply_risk_orders called: symbol={symbol}, side={entry_side}, qty={quantity}")
    logger.info(f"🎯 Risk config: {risk_config}")
    
    if not risk_config or not quantity:
        logger.info(f"🎯 No risk config or quantity=0, skipping bracket orders")
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

    # Get risk settings
    take_profit_list = risk_config.get('take_profit') or []
    stop_cfg = risk_config.get('stop_loss')
    trail_cfg = risk_config.get('trail')
    
    # Get tick values
    tp_ticks = None
    sl_ticks = None
    
    if take_profit_list:
        first_tp = take_profit_list[0]
        tp_ticks = first_tp.get('gain_ticks')
    
    if stop_cfg:
        sl_ticks = stop_cfg.get('loss_ticks')
    
    # Calculate absolute prices for OCO exit orders
    tp_price = None
    sl_price = None
    
    if tp_ticks:
        tp_offset = tick_size * tp_ticks
        tp_price = entry_price + tp_offset if is_long else entry_price - tp_offset
        tp_price = clamp_price(tp_price, tick_size)
    
    if sl_ticks:
        sl_offset = tick_size * sl_ticks
        sl_price = entry_price - sl_offset if is_long else entry_price + sl_offset
        sl_price = clamp_price(sl_price, tick_size)
    
    # Track order IDs for break-even and trailing stop integration
    tp_order_id = None
    sl_order_id = None
    
    # If we have BOTH TP and SL, try to place as OCO order strategy
    if tp_price and sl_price:
        logger.info(f"📊 Placing OCO exit orders: TP @ {tp_price}, SL @ {sl_price}, Qty: {quantity}")
        logger.info(f"   Entry: {entry_price}, TP ticks: {tp_ticks}, SL ticks: {sl_ticks}")
        
        # Use the new OCO exit method
        result = await tradovate.place_exit_oco(
            account_id=account_id,
            account_spec=account_spec,
            symbol=symbol_upper,
            exit_side=exit_action,
            quantity=quantity,
            take_profit_price=tp_price,
            stop_loss_price=sl_price
        )
        
        if result and result.get('success'):
            logger.info(f"✅ OCO exit orders placed successfully")
            
            # Register the pair for custom OCO monitoring (if they were placed as individual orders)
            tp_order_id = result.get('tp_order_id')
            sl_order_id = result.get('sl_order_id')
            
            if tp_order_id and sl_order_id:
                register_oco_pair(tp_order_id, sl_order_id, account_id, symbol_upper)
        else:
            logger.warning(f"⚠️ OCO exit failed, orders may have been placed individually: {result}")
    
    # If only TP (no SL)
    elif tp_price:
        logger.info(f"📊 Placing Take Profit only @ {tp_price}, Qty: {quantity}")
        tp_order_data = tradovate.create_limit_order(account_spec, symbol_upper, exit_action, quantity, tp_price, account_id)
        tp_result = await tradovate.place_order(tp_order_data)
        if tp_result and tp_result.get('success'):
            tp_order_id = tp_result.get('orderId') or tp_result.get('data', {}).get('orderId')
    
    # If only SL (no TP)
    elif sl_price:
        logger.info(f"📊 Placing Stop Loss only @ {sl_price}, Qty: {quantity}")
        sl_order_data = tradovate.create_stop_order(account_spec, symbol_upper, exit_action, quantity, sl_price, account_id)
        sl_result = await tradovate.place_order(sl_order_data)
        if sl_result and sl_result.get('success'):
            sl_order_id = sl_result.get('orderId') or sl_result.get('data', {}).get('orderId')
    
    # Handle trailing stop (can be used with or instead of fixed SL)
    if trail_cfg and trail_cfg.get('offset_ticks'):
        trail_ticks = trail_cfg.get('offset_ticks')
        trail_offset = tick_size * trail_ticks
        
        # Calculate initial stop price (entry - offset for long, entry + offset for short)
        if is_long:
            initial_stop_price = entry_price - trail_offset
        else:
            initial_stop_price = entry_price + trail_offset
        initial_stop_price = clamp_price(initial_stop_price, tick_size)
        
        logger.info(f"📊 Placing Trailing Stop: offset={trail_offset} ({trail_ticks} ticks), initial stop={initial_stop_price}")
        trail_order = tradovate.create_trailing_stop_order(
            account_spec, symbol_upper, exit_action, quantity, 
            float(trail_offset), account_id, initial_stop_price
        )
        trail_result = await tradovate.place_order(trail_order)
        
        if trail_result and trail_result.get('success'):
            trail_order_id = trail_result.get('orderId') or trail_result.get('data', {}).get('orderId')
            logger.info(f"✅ Trailing Stop placed: Order ID={trail_order_id}")
            
            # If we placed a trailing stop AND an SL, register them for OCO
            if sl_order_id and trail_order_id:
                # The trailing stop and fixed SL are alternatives - register as OCO
                register_oco_pair(trail_order_id, sl_order_id, account_id, symbol_upper)
                logger.info(f"🔗 Trailing Stop and SL registered as OCO: Trail={trail_order_id} <-> SL={sl_order_id}")
        else:
            error_msg = trail_result.get('error', 'Unknown error') if trail_result else 'No response'
            logger.warning(f"⚠️ Failed to place trailing stop: {error_msg}")
    
    # Handle break-even (monitor position and move SL to entry when profitable)
    break_even_cfg = risk_config.get('break_even')
    if break_even_cfg and break_even_cfg.get('activation_ticks'):
        be_ticks = break_even_cfg.get('activation_ticks')
        logger.info(f"📊 Break-even enabled: Will move SL to entry after {be_ticks} ticks profit")
        
        # Register for break-even monitoring
        register_break_even_monitor(
            account_id=account_id,
            symbol=symbol_upper,
            entry_price=entry_price,
            is_long=is_long,
            activation_ticks=be_ticks,
            tick_size=tick_size,
            sl_order_id=sl_order_id,  # We'll modify this order
            quantity=quantity,
            account_spec=account_spec
        )
    
    # Handle multiple TP levels (if any beyond the first)
    if len(take_profit_list) > 1:
        logger.info(f"📊 Processing {len(take_profit_list) - 1} additional TP levels")
        first_tp_percent = take_profit_list[0].get('trim_percent', 100)
        first_tp_qty = int(round(quantity * (first_tp_percent / 100.0))) if first_tp_percent else quantity
        remaining_qty = quantity - first_tp_qty
        
        for idx, tp in enumerate(take_profit_list[1:], start=1):
            ticks = tp.get('gain_ticks')
            trim_percent = tp.get('trim_percent', 0)
            
            level_qty = int(round(quantity * (trim_percent / 100.0))) if trim_percent else 0
            if idx == len(take_profit_list) - 1 and level_qty == 0:
                level_qty = remaining_qty  # Last level gets remaining
            
            level_qty = min(max(level_qty, 0), remaining_qty)
            if level_qty <= 0:
                continue
                
            remaining_qty -= level_qty
            
            if ticks:
                tp_offset = tick_size * ticks
                level_price = entry_price + tp_offset if is_long else entry_price - tp_offset
                level_price = clamp_price(level_price, tick_size)
                
                logger.info(f"  TP Level {idx + 1}: Price={level_price}, Qty={level_qty}")
                tp_order = tradovate.create_limit_order(account_spec, symbol_upper, exit_action, level_qty, level_price, account_id)
                await tradovate.place_order(tp_order)


def normalize_symbol(symbol: str) -> str:
    """Normalize symbol for comparison (remove !, handle different formats)"""
    if not symbol:
        return ''
    normalized = symbol.upper().strip()
    # Remove trailing ! (TradingView format)
    normalized = normalized.rstrip('!')
    return normalized

async def cancel_open_orders(tradovate, account_id: int, symbol: str | None = None, cancel_all: bool = False):
    cancelled = 0
    try:
        # Try getting all orders first (includes order strategies), then filter by account
        # This ensures we get bracket orders, OCO orders, etc. that might not show up in account-specific endpoint
        all_orders = await tradovate.get_orders(None) or []  # Get all orders
        orders = [o for o in all_orders if str(o.get('accountId', '')) == str(account_id)]
        
        # If we got no orders from /order/list, fallback to account-specific endpoint
        if not orders:
            logger.info(f"No orders found via /order/list, trying account-specific endpoint")
            orders = await tradovate.get_orders(str(account_id)) or []
        logger.info(f"Retrieved {len(orders)} orders for account {account_id}, filtering for symbol: {symbol}, cancel_all: {cancel_all}")
        
        # Log all orders for debugging
        if orders:
            logger.info(f"=== ALL ORDERS RETRIEVED ===")
            for idx, order in enumerate(orders[:10]):  # Log first 10 orders
                logger.info(f"Order #{idx+1}: id={order.get('id')}, status={order.get('status')}, ordStatus={order.get('ordStatus')}, "
                           f"symbol={order.get('symbol')}, contractId={order.get('contractId')}, "
                           f"orderType={order.get('orderType')}, orderQty={order.get('orderQty')}, "
                           f"action={order.get('action')}, strategyId={order.get('orderStrategyId')}, "
                           f"keys={list(order.keys())[:15]}")
            if len(orders) > 10:
                logger.info(f"... and {len(orders) - 10} more orders")
            logger.info(f"=== END ORDER LIST ===")
        
        # Statuses that represent active/resting orders that can be cancelled
        # According to Tradovate docs, statuses are: Working, Filled, Canceled, Rejected, Expired
        # Also check: PendingNew, PendingReplace, PendingCancel, Stopped, Suspended
        # We check both lowercase and capitalized versions for robustness
        cancellable_statuses = {
            'working', 'pending', 'queued', 'accepted', 'new', 
            'pendingnew', 'pendingreplace', 'pendingcancel',
            'stopped', 'suspended',
            # Capitalized versions (Tradovate standard format)
            'Working', 'Pending', 'Queued', 'Accepted', 'New',
            'PendingNew', 'PendingReplace', 'PendingCancel',
            'Stopped', 'Suspended'
        }
        
        # Normalize target symbol if provided
        target_symbol_normalized = None
        target_contract_ids = set()
        if symbol:
            target_symbol_normalized = normalize_symbol(symbol)
            logger.info(f"Target symbol normalized: {target_symbol_normalized}")
        
        # Resolve target symbol to contractId(s) if we have a symbol to match
        if symbol and target_symbol_normalized:
            try:
                # Get positions to find matching contractIds
                positions = await tradovate.get_positions(account_id)
                for pos in positions:
                    pos_symbol = str(pos.get('symbol') or '').upper()
                    if normalize_symbol(pos_symbol) == target_symbol_normalized:
                        contract_id = pos.get('contractId')
                        if contract_id:
                            target_contract_ids.add(contract_id)
                            logger.info(f"Found matching contractId {contract_id} for symbol {target_symbol_normalized}")
            except Exception as e:
                logger.warning(f"Error resolving contractIds for symbol matching: {e}")
        
        for order in orders:
            if not order:
                continue
            
            # Check both 'status' and 'ordStatus' fields (Tradovate uses ordStatus per docs)
            # Also check 'action' which sometimes indicates buy/sell (meaning order is active)
            status = order.get('ordStatus') or order.get('status') or ''
            status_lower = status.lower() if status else ''
            order_id = order.get('id')
            order_type = order.get('orderType') or order.get('order_type') or 'Unknown'
            order_strategy_id = order.get('orderStrategyId')  # For bracket/OCO orders
            order_action = order.get('action')  # Buy/Sell indicates active order
            
            # Non-cancellable final statuses (order is already complete)
            non_cancellable = {'filled', 'canceled', 'cancelled', 'rejected', 'expired', 'complete', 'completed'}
            
            # Skip if status indicates order is already done
            if status_lower and status_lower in non_cancellable:
                logger.debug(f"Skipping order {order_id} - status '{status}' is final (not cancellable)")
                continue
            
            # If status is empty but order has action (Buy/Sell), it's likely an active order
            if not status and not order_action:
                # If no status and no action, check if it has position-related fields (might be position data, not order)
                if 'netPos' in order:
                    logger.debug(f"Skipping order {order_id} - appears to be position data, not order")
                    continue
            
            # Log what we're about to try to cancel
            logger.info(f"Order {order_id} may be active: status='{status}', ordStatus='{order.get('ordStatus')}', action={order_action}, strategyId={order_strategy_id}")
            
            # Get symbol from order - could be direct symbol field or need to resolve from contractId
            order_symbol = str(order.get('symbol') or '').upper()
            order_contract_id = order.get('contractId')
            
            # Resolve contractId to symbol if we don't have symbol
            if not order_symbol and order_contract_id:
                try:
                    resolved_symbol = await tradovate._get_contract_symbol(order_contract_id)
                    if resolved_symbol:
                        order_symbol = resolved_symbol.upper()
                        order['symbol'] = resolved_symbol  # Cache it for future use
                        logger.debug(f"Resolved contractId {order_contract_id} to symbol {order_symbol}")
                except Exception as e:
                    logger.debug(f"Could not resolve contractId {order_contract_id}: {e}")
            
            # Filter by symbol if provided - try multiple matching strategies
            should_cancel = True
            if cancel_all:
                # Cancel all cancellable orders regardless of symbol
                should_cancel = True
                logger.info(f"Cancel-all mode: Will cancel order {order_id} ({order_symbol or f'contractId:{order_contract_id}' or 'no symbol'}, {order_type}, status: {status})")
            elif symbol:
                should_cancel = False
                
                # Strategy 1: Exact symbol match (after normalization)
                if order_symbol:
                    order_symbol_normalized = normalize_symbol(order_symbol)
                    if order_symbol_normalized == target_symbol_normalized:
                        should_cancel = True
                        logger.info(f"Order {order_id} matches by normalized symbol: {order_symbol} -> {order_symbol_normalized}")
                
                # Strategy 2: ContractId match
                if not should_cancel and order_contract_id and order_contract_id in target_contract_ids:
                    should_cancel = True
                    logger.info(f"Order {order_id} matches by contractId: {order_contract_id}")
                
                # Strategy 3: Partial symbol match (in case of format differences)
                if not should_cancel and order_symbol:
                    # Try matching base symbol (e.g., "ES" in "ESM1" or "ES1!")
                    order_base = normalize_symbol(order_symbol)
                    target_base = target_symbol_normalized
                    # Extract base symbol (remove month codes and numbers)
                    order_base_only = re.sub(r'\d+[A-Z]*$', '', order_base)
                    target_base_only = re.sub(r'\d+[A-Z]*$', '', target_base)
                    if order_base_only and target_base_only and order_base_only == target_base_only:
                        # If base matches and one contains the other, it's likely a match
                        if target_base_only in order_base or order_base_only in target_base:
                            should_cancel = True
                            logger.info(f"Order {order_id} matches by base symbol: {order_base} vs {target_base}")
                
                if not should_cancel:
                    logger.debug(f"Skipping order {order_id} ({order_symbol or 'no symbol'}) - doesn't match {symbol}")
                    continue
            
            # Attempt to cancel the order
            logger.info(f"Attempting to cancel order {order_id} ({order_symbol or f'contractId:{order_contract_id}' or 'no symbol'}, {order_type}, status: {status})")
            if await tradovate.cancel_order(order_id):
                cancelled += 1
                logger.info(f"✅ Successfully cancelled order {order_id} ({order_symbol or 'no symbol'})")
            else:
                logger.warning(f"❌ Failed to cancel order {order_id} ({order_symbol or 'no symbol'})")
                
    except Exception as e:
        logger.error(f"Unable to cancel open orders for {symbol or 'account'}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    logger.info(f"Total cancelled: {cancelled} orders for symbol {symbol or 'all'}")
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
    # Strategy P&L history table (for recording strategy performance like Trade Manager)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_pnl_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER,
            strategy_name TEXT,
            pnl REAL,
            drawdown REAL DEFAULT 0.0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_strategy_pnl_timestamp 
        ON strategy_pnl_history(strategy_id, timestamp)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_strategy_pnl_date 
        ON strategy_pnl_history(DATE(timestamp))
    ''')
    conn.commit()
    conn.close()
    
    # Initialize just_trades.db with positions table (like Trade Manager)
    conn = sqlite3.connect('just_trades.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS open_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            subaccount_id TEXT,
            account_name TEXT,
            symbol TEXT NOT NULL,
            quantity REAL NOT NULL,
            avg_price REAL NOT NULL,
            current_price REAL DEFAULT 0.0,
            unrealized_pnl REAL DEFAULT 0.0,
            order_id TEXT,
            strategy_name TEXT,
            direction TEXT,  -- 'BUY' or 'SELL'
            open_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(account_id, subaccount_id, symbol)
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_open_positions_account 
        ON open_positions(account_id, subaccount_id)
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
    # Inject the fetch MD token script into the template context
    return render_template('account_management.html', include_md_token_script=True)

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

@app.route('/accounts/<int:account_id>/credentials')
def collect_credentials(account_id):
    """Render credentials collection page for Tradovate account"""
    return render_template('collect_credentials.html', account_id=account_id)

@app.route('/api/accounts/<int:account_id>/store-credentials', methods=['POST'])
def store_credentials(account_id):
    """Store username/password for an account (optional, for mdAccessToken)"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        environment = data.get('environment', 'demo')  # 'live' or 'demo'
        
        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Username and password are required'
            }), 400
        
        # Store credentials in database
        conn = sqlite3.connect('just_trades.db')
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE accounts 
            SET username = ?, 
                password = ?,
                environment = ?
            WHERE id = ?
        """, (username, password, environment, account_id))
        conn.commit()
        conn.close()
        
        logger.info(f"Stored credentials for account {account_id}")
        
        # Optionally fetch mdAccessToken immediately if we want
        # For now, just store and continue to OAuth
        
        return jsonify({
            'success': True,
            'message': 'Credentials stored successfully',
            'redirect_url': f'/api/accounts/{account_id}/connect'
        })
    except Exception as e:
        logger.error(f"Error storing credentials: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
            logger.info(f"OAuth token response keys: {list(token_data.keys())}")
            access_token = token_data.get('accessToken') or token_data.get('access_token')
            refresh_token = token_data.get('refreshToken') or token_data.get('refresh_token')
            md_access_token = token_data.get('mdAccessToken') or token_data.get('md_access_token')
            
            logger.info(f"Tokens extracted - accessToken: {bool(access_token)}, refreshToken: {bool(refresh_token)}, mdAccessToken: {bool(md_access_token)}")
            
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
            
            # OAuth token exchange doesn't return mdAccessToken - try to get it via accessTokenRequest
            if not md_access_token and access_token:
                try:
                    # Check if we have username/password stored
                    conn = sqlite3.connect('just_trades.db')
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT username, password, client_id, client_secret, environment
                        FROM accounts WHERE id = ?
                    """, (account_id,))
                    creds = cursor.fetchone()
                    conn.close()
                    
                    if creds and creds[0] and creds[1]:  # Has username and password
                        username, password, client_id, client_secret, environment = creds
                        base_url = "https://live.tradovateapi.com/v1" if environment == 'live' else "https://demo.tradovateapi.com/v1"
                        
                        # Use OAuth client credentials for accessTokenRequest (same as OAuth flow)
                        # Use API credentials: cid: 8720, secret: e76ee8d1-d168-4252-a59e-f11a8b0cdae4
                        # These are used for fetching mdAccessToken via /auth/accesstokenrequest
                        DEFAULT_CLIENT_ID = str(TRADOVATE_API_CID)  # Use global API CID
                        DEFAULT_CLIENT_SECRET = TRADOVATE_API_SECRET  # Use global API secret
                        
                        # Make accessTokenRequest to get mdAccessToken
                        login_data = {
                            "name": username,
                            "password": password,
                            "appId": "Just.Trade",
                            "appVersion": "1.0.0",
                            "deviceId": f"Just.Trade-{account_id}",
                            "cid": DEFAULT_CLIENT_ID,  # Use OAuth client ID
                            "sec": DEFAULT_CLIENT_SECRET  # Use OAuth client secret
                        }
                        
                        logger.info(f"Fetching mdAccessToken via /auth/accesstokenrequest for account {account_id}")
                        token_response = requests.post(
                            f"{base_url}/auth/accesstokenrequest",
                            json=login_data,
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if token_response.status_code == 200:
                            token_data = token_response.json()
                            logger.info(f"accessTokenRequest response keys: {list(token_data.keys())}")
                            
                            # Check for errors first
                            if 'errorText' in token_data:
                                error_msg = token_data.get('errorText', 'Unknown error')
                                logger.warning(f"accessTokenRequest returned error: {error_msg}")
                                if 'not registered' in error_msg.lower():
                                    logger.info("App not registered - this is expected if using OAuth client credentials with accessTokenRequest")
                                    logger.info("mdAccessToken may not be available via this method. WebSocket will use accessToken instead.")
                                elif 'incorrect username' in error_msg.lower() or 'password' in error_msg.lower():
                                    logger.warning("Credentials may be incorrect or don't match OAuth account")
                            else:
                                md_access_token = token_data.get('mdAccessToken') or token_data.get('md_access_token')
                                if md_access_token:
                                    # Update mdAccessToken in database
                                    conn = sqlite3.connect('just_trades.db')
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE accounts SET md_access_token = ? WHERE id = ?
                                    """, (md_access_token, account_id))
                                    conn.commit()
                                    conn.close()
                                    logger.info(f"✅ Successfully retrieved and stored mdAccessToken for account {account_id}")
                                else:
                                    logger.warning(f"mdAccessToken not in accessTokenRequest response for account {account_id}")
                                    logger.info(f"Full response: {token_data}")
                        else:
                            error_text = token_response.text[:200] if hasattr(token_response, 'text') else str(token_response.status_code)
                            logger.warning(f"Failed to get mdAccessToken: {token_response.status_code} - {error_text}")
                    else:
                        logger.info(f"Account {account_id} doesn't have username/password stored. MD Token will be fetched when credentials are added.")
                        logger.info("Note: WebSocket will work with OAuth accessToken, but mdAccessToken provides better market data access.")
                except Exception as e:
                    logger.error(f"Error fetching mdAccessToken: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
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

@app.route('/api/accounts/<int:account_id>/fetch-md-token', methods=['POST'])
def fetch_md_access_token(account_id):
    """Fetch mdAccessToken for an account - accepts credentials in request or uses stored ones"""
    try:
        data = request.get_json() or {}
        
        # Get credentials from request or database
        username = data.get('username')
        password = data.get('password')
        use_stored = data.get('use_stored', True)  # Default to using stored credentials
        
        if not username or not password:
            if use_stored:
                # Try to get from database
                conn = sqlite3.connect('just_trades.db')
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT username, password, client_id, client_secret, environment
                    FROM accounts WHERE id = ?
                """, (account_id,))
                creds = cursor.fetchone()
                conn.close()
                
                if not creds or not creds[0] or not creds[1]:
                    return jsonify({
                        'success': False,
                        'error': 'No credentials provided and account does not have username/password stored.',
                        'instructions': 'Either provide username/password in the request body, or add them to the account first.'
                    }), 400
                
                username, password, client_id, client_secret, environment = creds
            else:
                return jsonify({
                    'success': False,
                    'error': 'Username and password required in request body'
                }), 400
        else:
            # Get environment and client credentials from database
            conn = sqlite3.connect('just_trades.db')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT client_id, client_secret, environment
                FROM accounts WHERE id = ?
            """, (account_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                client_id, client_secret, environment = row
            else:
                environment = 'demo'  # Default
                client_id = None
                client_secret = None
        
        base_url = "https://live.tradovateapi.com/v1" if environment == 'live' else "https://demo.tradovateapi.com/v1"
        
        # Make accessTokenRequest to get mdAccessToken
        # Use provided API credentials (prefer stored, fallback to defaults)
        login_data = {
            "name": username,
            "password": password,
            "appId": "Just.Trade",
            "appVersion": "1.0.0",
            "deviceId": f"Just.Trade-{account_id}",
            "cid": client_id or str(TRADOVATE_API_CID),  # Use stored or default API CID
            "sec": client_secret or TRADOVATE_API_SECRET  # Use stored or default API secret
        }
        
        logger.info(f"Fetching mdAccessToken for account {account_id} via /auth/accesstokenrequest")
        token_response = requests.post(
            f"{base_url}/auth/accesstokenrequest",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        if token_response.status_code == 200:
            token_data = token_response.json()
            md_access_token = token_data.get('mdAccessToken') or token_data.get('md_access_token')
            access_token = token_data.get('accessToken') or token_data.get('access_token')
            refresh_token = token_data.get('refreshToken') or token_data.get('refresh_token')
            
            if md_access_token:
                # Update tokens in database
                conn = sqlite3.connect('just_trades.db')
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE accounts 
                    SET md_access_token = ?,
                        tradovate_token = COALESCE(?, tradovate_token),
                        tradovate_refresh_token = COALESCE(?, tradovate_refresh_token),
                        token_expires_at = datetime('now', '+24 hours')
                    WHERE id = ?
                """, (md_access_token, access_token, refresh_token, account_id))
                conn.commit()
                conn.close()
                
                logger.info(f"✅ Successfully stored mdAccessToken for account {account_id}")
                return jsonify({
                    'success': True,
                    'message': 'mdAccessToken fetched and stored successfully. WebSocket will now work properly.',
                    'has_md_token': True
                })
            else:
                logger.warning(f"mdAccessToken not in response: {list(token_data.keys())}")
                return jsonify({
                    'success': False,
                    'error': 'mdAccessToken not in response from Tradovate',
                    'response_keys': list(token_data.keys())
                }), 400
        else:
            error_text = token_response.text[:200]
            logger.error(f"Failed to fetch mdAccessToken: {token_response.status_code} - {error_text}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch mdAccessToken: {token_response.status_code}',
                'details': error_text
            }), token_response.status_code
            
    except Exception as e:
        logger.error(f"Error fetching mdAccessToken: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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

@app.route('/api/trades/open/', methods=['GET'])
def get_open_trades():
    """Get open positions (like Trade Manager's /api/trades/open/)"""
    try:
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all open positions
        cursor.execute('''
            SELECT * FROM open_positions
            ORDER BY open_time DESC
        ''')
        positions = cursor.fetchall()
        conn.close()
        
        # Format like Trade Manager
        formatted_positions = []
        for pos in positions:
            formatted_positions.append({
                'id': pos['id'],
                'Strat_Name': pos.get('strategy_name') or 'Manual Trade',
                'Ticker': pos['symbol'],
                'TimeFrame': '',
                'Direction': pos['direction'],
                'Open_Price': str(pos['avg_price']),
                'Open_Time': pos['open_time'],
                'Running_Pos': float(pos['quantity']),
                'Account': pos['account_name'] or f"Account {pos['account_id']}",
                'Nickname': '',
                'Expo': None,
                'Strike': None,
                'Drawdown': f"{pos['unrealized_pnl']:.2f}",
                'StratTicker': pos['symbol'],
                'Stoploss': '0.00',
                'TakeProfit': [],
                'SLTP_Data': {},
                'Opt_Name': pos['symbol'],
                'IfOption': False
            })
        
        return jsonify(formatted_positions)
    except Exception as e:
        logger.error(f"Error fetching open trades: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

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
        
        # DEBUG: Log received risk settings
        logger.info(f"📋 Manual trade request: symbol={symbol}, side={side}, qty={quantity}")
        logger.info(f"📋 Risk settings received: {risk_settings}")
        
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
                    logger.info(f"=== CLOSING POSITION + CANCELLING ALL ORDERS FOR {symbol_upper} ===")
                    
                    results = []
                    total_closed = 0
                    total_cancelled = 0
                    
                    # STEP 1: Get positions FIRST to find what we need to close
                    positions = await tradovate.get_positions(account_numeric_id)
                    logger.info(f"Step 1: Retrieved {len(positions)} positions for account {account_numeric_id}")
                    
                    # Log all positions for debugging
                    for idx, pos in enumerate(positions):
                        pos_symbol = pos.get('symbol', 'N/A')
                        pos_net = pos.get('netPos', 0)
                        pos_contract = pos.get('contractId')
                        logger.info(f"  Position {idx+1}: symbol={pos_symbol}, netPos={pos_net}, contractId={pos_contract}")
                    
                    # Match positions - try multiple matching strategies
                    matched_positions = []
                    normalized_target = normalize_symbol(symbol_upper)
                    
                    for pos in positions:
                        pos_symbol = str(pos.get('symbol', '')).upper()
                        pos_net = pos.get('netPos', 0)
                        
                        if not pos_net:  # Skip flat positions
                            continue
                        
                        # Try exact match first
                        if pos_symbol == symbol_upper:
                            matched_positions.append(pos)
                            continue
                        
                        # Try normalized match (handles MNQ vs MNQZ4, etc.)
                        pos_normalized = normalize_symbol(pos_symbol)
                        if pos_normalized == normalized_target:
                            matched_positions.append(pos)
                            continue
                        
                        # Try base symbol match (MNQ matches MNQZ4)
                        pos_base = re.sub(r'[A-Z]\d+$', '', pos_normalized)  # Remove month+year
                        target_base = re.sub(r'[A-Z]\d+$', '', normalized_target)
                        if pos_base and target_base and (pos_base == target_base or pos_base in target_base or target_base in pos_base):
                            matched_positions.append(pos)
                            continue
                    
                    logger.info(f"Step 1b: Found {len(matched_positions)} matching positions for {symbol_upper}")
                    
                    # STEP 2: Close positions using liquidateposition (this also cancels related orders)
                    for pos in matched_positions:
                        contract_id = pos.get('contractId')
                        pos_symbol = pos.get('symbol', symbol_upper)
                        net_pos = pos.get('netPos', 0)
                        
                        if not contract_id:
                            logger.warning(f"Position for {pos_symbol} has no contractId, using manual close")
                            # Manual close
                            qty = abs(int(net_pos))
                            if qty > 0:
                                close_side = 'Sell' if net_pos > 0 else 'Buy'
                                order_data = tradovate.create_market_order(account_spec, pos_symbol, close_side, qty, account_numeric_id)
                                result = await tradovate.place_order(order_data)
                                if result and result.get('success'):
                                    results.append(result)
                                    total_closed += qty
                            continue
                        
                        logger.info(f"Step 2: Liquidating position for {pos_symbol} (contractId: {contract_id}, netPos: {net_pos})")
                        
                        # Use liquidateposition endpoint - this SHOULD close position AND cancel related orders
                        result = await tradovate.liquidate_position(account_numeric_id, contract_id, admin=False)
                        
                        if result and result.get('success'):
                            results.append(result)
                            total_closed += abs(int(net_pos))
                            logger.info(f"✅ Successfully liquidated position for {pos_symbol}")
                        else:
                            error_msg = result.get('error', 'Unknown error') if result else 'No response'
                            logger.warning(f"⚠️ liquidateposition returned: {error_msg}, falling back to manual close")
                            
                            # Fallback: Manual close
                            qty = abs(int(net_pos))
                            if qty > 0:
                                close_side = 'Sell' if net_pos > 0 else 'Buy'
                                logger.info(f"Manual close: {close_side} {qty} {pos_symbol}")
                                order_data = tradovate.create_market_order(account_spec, pos_symbol, close_side, qty, account_numeric_id)
                                result = await tradovate.place_order(order_data)
                                if result and result.get('success'):
                                    results.append(result)
                                    total_closed += qty
                    
                    # STEP 3: Cancel ALL remaining orders and strategies (cleanup)
                    logger.info(f"Step 3: Cancelling any remaining orders and strategies")
                    
                    # Get and interrupt order strategies
                    try:
                        all_strategies = await tradovate.get_order_strategies(account_numeric_id)
                        for strategy in all_strategies:
                            strategy_id = strategy.get('id')
                            strategy_status = (strategy.get('status') or '').lower()
                            if strategy_status not in ['completed', 'complete', 'cancelled', 'canceled', 'failed']:
                                logger.info(f"Interrupting order strategy {strategy_id}")
                                await tradovate.interrupt_order_strategy(strategy_id)
                    except Exception as e:
                        logger.warning(f"Error interrupting order strategies: {e}")
                    
                    # Cancel all individual orders
                    cancelled_after = await cancel_open_orders(tradovate, account_numeric_id, None, cancel_all=True)
                    total_cancelled += cancelled_after
                    logger.info(f"Cancelled {cancelled_after} additional orders")
                    
                    # STEP 4: Final verification
                    final_positions = await tradovate.get_positions(account_numeric_id)
                    still_open = [p for p in final_positions if normalize_symbol(p.get('symbol', '')) == normalized_target and p.get('netPos', 0) != 0]
                    
                    logger.info(f"=== CLOSE COMPLETE: Closed {total_closed} contracts, cancelled {total_cancelled} orders ===")
                    
                    if still_open:
                        logger.warning(f"⚠️ Position still open after close attempt!")
                        # Try one more time with direct market order
                        for pos in still_open:
                            qty = abs(int(pos.get('netPos', 0)))
                            close_side = 'Sell' if pos.get('netPos', 0) > 0 else 'Buy'
                            order_data = tradovate.create_market_order(account_spec, pos.get('symbol'), close_side, qty, account_numeric_id)
                            result = await tradovate.place_order(order_data)
                            if result and result.get('success'):
                                total_closed += qty
                                results.append(result)
                    
                    # Build response
                    if total_closed > 0 or total_cancelled > 0:
                        message = f'Closed {total_closed} contracts for {symbol_upper}'
                        if total_cancelled > 0:
                            message += f' and cancelled {total_cancelled} resting orders'
                        
                        response = {
                            'success': True,
                            'message': message,
                            'closed_quantity': total_closed,
                            'cancelled_orders': total_cancelled
                        }
                        if results:
                            response['orderId'] = results[-1].get('data', {}).get('orderId') or results[-1].get('orderId')
                        return response
                    
                    # Nothing to close or cancel
                    if not matched_positions:
                        return {'success': True, 'message': f'No open position found for {symbol_upper}. Nothing to close.'}
                    
                    return {'success': False, 'error': 'Failed to close position'}
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

        # Log the order response to see what accountId it was placed on
        order_id = result.get('orderId') or result.get('data', {}).get('orderId')
        order_response = result.get('raw') or result
        logger.info(f"Order placed - Order ID: {order_id}, Account used: {account_numeric_id} ({account_spec}), Full response: {order_response}")
        
        # The order response doesn't include accountId, but we know which one we used
        logger.info(f"✅ Order {order_id} placed on account {account_numeric_id} ({account_spec})")
        
        # Since Tradovate's position API returns 0, we need to track positions from filled orders
        # Get fill price from order status after a short delay
        if result.get('success') and order_id:
            import threading
            def get_fill_price_and_update_position():
                import time
                time.sleep(2)  # Wait 2 seconds for order to fill
                try:
                    from phantom_scraper.tradovate_integration import TradovateIntegration
                    async def fetch_order_details():
                        async with TradovateIntegration(demo=demo) as tradovate:
                            tradovate.access_token = token_container['access_token']
                            tradovate.refresh_token = token_container['refresh_token']
                            tradovate.md_access_token = token_container['md_access_token']
                            
                            # Try to get order details - but orders API returns 0
                            # Instead, check if fill price is in the order response itself
                            # Or use a different approach: get fill price from order history
                            
                            # Method 1: Check order response (might have fill price immediately)
                            # This is handled in the main trade function
                            
                            # Method 1: Try /fill/list endpoint (BEST - gets actual fill prices)
                            avg_fill_price = 0.0
                            fills = await tradovate.get_fills(order_id=order_id)
                            if fills:
                                # Get the most recent fill for this order
                                for fill in fills:
                                    if str(fill.get('orderId')) == str(order_id):
                                        avg_fill_price = fill.get('price') or fill.get('fillPrice') or 0.0
                                        logger.info(f"✅ Found fill price from /fill/list: {avg_fill_price}")
                                        break
                            
                            # Method 2: Query order by ID directly
                            if avg_fill_price == 0:
                                try:
                                    async with tradovate.session.get(
                                        f"{tradovate.base_url}/order/item",
                                        params={'id': order_id},
                                        headers=tradovate._get_headers()
                                    ) as order_response:
                                        if order_response.status == 200:
                                            order_data = await order_response.json()
                                            avg_fill_price = order_data.get('avgFillPrice') or order_data.get('price') or 0.0
                                            order_status = order_data.get('ordStatus') or order_data.get('status', '')
                                            logger.info(f"Order {order_id} from /order/item: status={order_status}, avgFillPrice={avg_fill_price}")
                                            if avg_fill_price > 0:
                                                logger.info(f"✅ Found fill price from /order/item: {avg_fill_price}")
                                except Exception as e:
                                    logger.warning(f"Error fetching order item: {e}")
                            
                            # Method 3: Try orders list (fallback)
                            if avg_fill_price == 0:
                                orders = await tradovate.get_orders(None)
                                if orders:
                                    for o in orders:
                                        if str(o.get('id')) == str(order_id):
                                            avg_fill_price = o.get('avgFillPrice') or o.get('price') or o.get('fillPrice') or 0.0
                                            order_status = o.get('ordStatus') or o.get('status', '')
                                            logger.info(f"Order {order_id} from list: status={order_status}, avgFillPrice={avg_fill_price}")
                                            if avg_fill_price > 0:
                                                logger.info(f"✅ Found fill price from /order/list: {avg_fill_price}")
                                            break
                            
                            # If we found a fill price, update the position
                            if avg_fill_price > 0:
                                # Update position with fill price
                                net_qty = quantity if side.lower() == 'buy' else -quantity
                                cache_key = f"{symbol}_{account_numeric_id}"
                                
                                # Get or create position
                                position = _position_cache.get(cache_key, {
                                    'symbol': symbol,
                                    'quantity': net_qty,
                                    'net_quantity': net_qty,
                                    'avg_price': avg_fill_price,
                                    'last_price': avg_fill_price,  # Start with fill price
                                    'unrealized_pnl': 0.0,
                                    'account_id': account_id,
                                    'subaccount_id': str(account_numeric_id),
                                    'account_name': account_spec,
                                    'order_id': order_id,
                                    'open_time': datetime.now().isoformat()
                                })
                                
                                # Update with fill price
                                position['avg_price'] = avg_fill_price
                                position['last_price'] = avg_fill_price
                                _position_cache[cache_key] = position
                                
                                # Store position in database (like Trade Manager)
                                conn = sqlite3.connect('just_trades.db')
                                cursor = conn.cursor()
                                cursor.execute('''
                                    INSERT OR REPLACE INTO open_positions 
                                    (symbol, net_quantity, avg_price, last_price, unrealized_pnl, 
                                     account_id, subaccount_id, account_name, order_id, open_time)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                ''', (
                                    position['symbol'], position['net_quantity'], position['avg_price'],
                                    position['last_price'], position['unrealized_pnl'], position['account_id'],
                                    position['subaccount_id'], position['account_name'], position['order_id'],
                                    position['open_time']
                                ))
                                conn.commit()
                                conn.close()
                                logger.info(f"✅ Stored position in database: {symbol} qty={net_qty} @ {avg_fill_price}")
                                
                                # Update PnL (will be 0 initially since current = fill)
                                update_position_pnl()
                                
                                # Emit updated position
                                socketio.emit('position_update', {
                                    'positions': [position],
                                    'count': 1,
                                    'timestamp': datetime.now().isoformat(),
                                    'source': 'order_fill'
                                })
                                logger.info(f"Updated position with fill price: {avg_fill_price}")
                            else:
                                logger.warning(f"⚠️ Could not get fill price for order {order_id} - will retry later")
                                # Will need to poll again or use market data estimate
                    asyncio.run(fetch_order_details())
                except Exception as e:
                    logger.warning(f"Error fetching fill price: {e}")
            
            # Start background thread to get fill price
            threading.Thread(target=get_fill_price_and_update_position, daemon=True).start()
            
            # Emit initial position (without fill price for now)
            net_qty = quantity if side.lower() == 'buy' else -quantity
            synthetic_position = {
                'symbol': symbol,
                'quantity': net_qty,
                'net_quantity': net_qty,
                'avg_price': 0.0,  # Will be updated when we get fill price
                'last_price': 0.0,  # Will be updated with market data
                'unrealized_pnl': 0.0,
                'account_id': account_id,
                'subaccount_id': str(account_numeric_id),
                'account_name': account_spec,
                'order_id': order_id
            }
            logger.info(f"Emitting initial position for order {order_id} (fill price will be updated)")
            
            # Store in global cache
            cache_key = f"{symbol}_{account_numeric_id}"
            _position_cache[cache_key] = synthetic_position
            
            # Emit the position update
            socketio.emit('position_update', {
                'positions': [synthetic_position],
                'count': 1,
                'timestamp': datetime.now().isoformat(),
                'source': 'order_fill'
            })

        # Emit WebSocket events for real-time updates (like Trade Manager)
        try:
            # Emit log entry
            socketio.emit('log_entry', {
                'type': 'trade',
                'message': f'Trade executed: {side} {quantity} {symbol}',
                'time': datetime.now().isoformat()
            })
            
            # Emit position update
            socketio.emit('position_update', {
                'strategy': 'Manual Trade',
                'symbol': symbol,
                'quantity': quantity,
                'side': side,
                'account': account_spec,
                'timestamp': datetime.now().isoformat()
            })
            
            # Trigger immediate position refresh by clearing cache
            if hasattr(emit_realtime_updates, '_last_position_fetch'):
                emit_realtime_updates._last_position_fetch = 0  # Force refresh on next cycle
            
            # Emit trade executed event
            socketio.emit('trade_executed', {
                'strategy': 'Manual Trade',
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'order_id': result.get('orderId', 'N/A'),
                'account': account_spec,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as ws_error:
            logger.error(f"Error emitting WebSocket events: {ws_error}")

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

@app.route('/api/dashboard/pnl-calendar', methods=['GET'])
def api_pnl_calendar():
    """Get P&L data for calendar view (like Trade Manager)"""
    try:
        start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        
        conn = sqlite3.connect('trading_webhook.db')
        cursor = conn.execute('''
            SELECT DATE(timestamp) as date, SUM(pnl) as daily_pnl
            FROM strategy_pnl_history
            WHERE DATE(timestamp) BETWEEN ? AND ?
            GROUP BY DATE(timestamp)
            ORDER BY date
        ''', (start_date, end_date))
        
        data = [{'date': row[0], 'pnl': float(row[1]) if row[1] else 0.0} for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({'calendar_data': data})
    except Exception as e:
        logger.error(f"Error fetching P&L calendar: {e}")
        return jsonify({'calendar_data': []})

@app.route('/api/dashboard/pnl-drawdown-chart', methods=['GET'])
def api_pnl_drawdown_chart():
    """Get P&L and drawdown data for chart (like Trade Manager)"""
    try:
        strategy_id = request.args.get('strategy_id', None)
        limit = int(request.args.get('limit', 1000))
        
        query = '''
            SELECT timestamp, pnl, drawdown
            FROM strategy_pnl_history
        '''
        params = []
        
        if strategy_id:
            query += ' WHERE strategy_id = ?'
            params.append(strategy_id)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        conn = sqlite3.connect('trading_webhook.db')
        cursor = conn.execute(query, params)
        
        data = [{
            'timestamp': row[0],
            'pnl': float(row[1]) if row[1] else 0.0,
            'drawdown': float(row[2]) if row[2] else 0.0
        } for row in cursor.fetchall()]
        data.reverse()  # Reverse to get chronological order
        conn.close()
        
        return jsonify({'chart_data': data})
    except Exception as e:
        logger.error(f"Error fetching P&L chart: {e}")
        return jsonify({'chart_data': []})

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

# ============================================================================
# WebSocket Handlers (Real-time updates like Trade Manager)
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info('Client connected to WebSocket')
    emit('status', {
        'connected': True,
        'message': 'Connected to server',
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info('Client disconnected from WebSocket')

@socketio.on('subscribe')
def handle_subscribe(data):
    """Subscribe to specific update channels"""
    channels = data.get('channels', [])
    logger.info(f'Client subscribed to: {channels}')
    emit('subscribed', {'channels': channels})

# ============================================================================
# Strategy P&L Recording Functions
# ============================================================================

def record_strategy_pnl(strategy_id, strategy_name, pnl, drawdown=0.0):
    """Record strategy P&L to database (like Trade Manager)"""
    try:
        conn = sqlite3.connect('trading_webhook.db')
        conn.execute('''
            INSERT INTO strategy_pnl_history (strategy_id, strategy_name, pnl, drawdown, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (strategy_id, strategy_name, pnl, drawdown, datetime.now()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error recording strategy P&L: {e}")

def calculate_strategy_pnl(strategy_id):
    """Calculate current P&L for a strategy from trades database"""
    try:
        # Try to get P&L from just_trades.db (SQLAlchemy models)
        try:
            from app.database import SessionLocal
            from app.models import Trade, Position
            
            db = SessionLocal()
            
            # Calculate realized P&L from closed trades
            closed_trades = db.query(Trade).filter(
                Trade.strategy_id == strategy_id,
                Trade.status == 'filled',
                Trade.closed_at.isnot(None)
            ).all()
            
            realized_pnl = sum(trade.pnl or 0.0 for trade in closed_trades)
            
            # Calculate unrealized P&L from open positions
            positions = db.query(Position).filter(
                Position.account_id.in_(
                    db.query(Trade.account_id).filter(Trade.strategy_id == strategy_id).distinct()
                )
            ).all()
            
            unrealized_pnl = sum(pos.unrealized_pnl or 0.0 for pos in positions)
            
            total_pnl = realized_pnl + unrealized_pnl
            db.close()
            
            return total_pnl
            
        except ImportError:
            # Fallback to SQLite direct query
            conn = sqlite3.connect('just_trades.db')
            cursor = conn.execute('''
                SELECT COALESCE(SUM(pnl), 0.0) as total_pnl
                FROM trades
                WHERE strategy_id = ? AND status = 'filled'
            ''', (strategy_id,))
            result = cursor.fetchone()
            pnl = float(result[0]) if result and result[0] else 0.0
            conn.close()
            return pnl
            
    except Exception as e:
        logger.error(f"Error calculating strategy P&L: {e}")
        return 0.0

def calculate_strategy_drawdown(strategy_id):
    """Calculate current drawdown for a strategy"""
    try:
        # Get historical P&L to calculate drawdown
        conn = sqlite3.connect('trading_webhook.db')
        cursor = conn.execute('''
            SELECT pnl FROM strategy_pnl_history
            WHERE strategy_id = ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (strategy_id,))
        
        pnl_history = [float(row[0]) for row in cursor.fetchall() if row[0] is not None]
        conn.close()
        
        if not pnl_history:
            return 0.0
        
        # Calculate drawdown: peak - current
        peak = max(pnl_history)
        current = pnl_history[0] if pnl_history else 0.0
        drawdown = max(0.0, peak - current)
        
        return drawdown
        
    except Exception as e:
        logger.error(f"Error calculating strategy drawdown: {e}")
        return 0.0

# ============================================================================
# Background Threads for Real-Time Updates (Every Second, like Trade Manager)
# ============================================================================

# Global position cache to persist positions across updates
_position_cache = {}

# Market data cache for real-time prices
_market_data_cache = {}

# Market data WebSocket connection
_market_data_ws = None
_market_data_ws_task = None
_market_data_subscribed_symbols = set()

async def connect_tradovate_market_data_websocket():
    """Connect to Tradovate market data WebSocket and subscribe to quotes"""
    global _market_data_cache, _market_data_ws, _market_data_subscribed_symbols
    
    if not WEBSOCKETS_AVAILABLE:
        logger.error("websockets library not available. Cannot connect to market data.")
        return
    
    # Get md_access_token from database
    md_token = None
    demo = True  # Default to demo
    
    try:
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT md_access_token, environment FROM accounts 
            WHERE md_access_token IS NOT NULL AND md_access_token != ''
            LIMIT 1
        ''')
        row = cursor.fetchone()
        if row:
            md_token = row['md_access_token']
            # Check if environment is 'demo' or 'live'
            # Note: sqlite3.Row doesn't have .get() method, use dict() or direct access
            env = row['environment'] if row['environment'] else 'demo'
            demo = (env == 'demo' or env is None)
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching md_access_token: {e}")
        return
    
    if not md_token:
        logger.warning("No md_access_token found. Market data WebSocket will not connect.")
        return
    
    # WebSocket URL (demo or live)
    ws_url = "wss://demo.tradovateapi.com/v1/websocket" if demo else "wss://live.tradovateapi.com/v1/websocket"
    
    while True:
        try:
            logger.info(f"Connecting to Tradovate market data WebSocket: {ws_url}")
            async with websockets.connect(ws_url) as ws:
                _market_data_ws = ws
                logger.info("✅ Market data WebSocket connected")
                
                # Authorize with md_access_token
                # Format: "authorize\n0\n\n{token}"
                auth_message = f"authorize\n0\n\n{md_token}"
                await ws.send(auth_message)
                
                # Wait for authorization response
                response = await ws.recv()
                logger.info(f"Market data auth response: {response[:200]}")
                
                # Subscribe to quotes for symbols we have positions in
                await subscribe_to_market_data_symbols(ws)
                
                # Listen for market data updates
                async for message in ws:
                    try:
                        # Parse message (format: "frame\n{id}\n\n{json_data}")
                        if message.startswith("frame"):
                            parts = message.split("\n", 3)
                            if len(parts) >= 4:
                                json_data = json.loads(parts[3])
                                await process_market_data_message(json_data)
                        elif message.startswith("["):
                            # Direct JSON array format
                            data = json.loads(message)
                            await process_market_data_message(data)
                    except json.JSONDecodeError as e:
                        logger.debug(f"Could not parse market data message: {e}")
                    except Exception as e:
                        logger.warning(f"Error processing market data message: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            logger.warning("Market data WebSocket connection closed. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Market data WebSocket error: {e}. Reconnecting in 10 seconds...")
            await asyncio.sleep(10)

async def subscribe_to_market_data_symbols(ws):
    """Subscribe to market data quotes for symbols we have positions in"""
    global _position_cache, _market_data_subscribed_symbols
    
    # Get symbols from positions
    symbols_to_subscribe = set()
    for position in _position_cache.values():
        symbol = position.get('symbol', '')
        if symbol:
            # Convert TradingView symbol to Tradovate format if needed
            # MES1! -> MESM1 (front month)
            tradovate_symbol = convert_symbol_for_tradovate_md(symbol)
            symbols_to_subscribe.add(tradovate_symbol)
    
    # Also check database for open positions
    try:
        conn = sqlite3.connect('just_trades.db')
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM open_positions WHERE symbol IS NOT NULL")
        for row in cursor.fetchall():
            symbol = row[0]
            if symbol:
                tradovate_symbol = convert_symbol_for_tradovate_md(symbol)
                symbols_to_subscribe.add(tradovate_symbol)
        conn.close()
    except Exception as e:
        logger.warning(f"Error getting symbols from database: {e}")
    
    # Subscribe to each symbol
    for symbol in symbols_to_subscribe:
        if symbol not in _market_data_subscribed_symbols:
            try:
                # Subscribe to quote data
                # Format: "quote/subscribe\n{id}\n\n{json}"
                subscribe_msg = f"quote/subscribe\n1\n\n{json.dumps({'symbol': symbol})}"
                await ws.send(subscribe_msg)
                _market_data_subscribed_symbols.add(symbol)
                logger.info(f"Subscribed to market data for {symbol}")
            except Exception as e:
                logger.warning(f"Error subscribing to {symbol}: {e}")

def convert_symbol_for_tradovate_md(symbol: str) -> str:
    """Convert symbol format for Tradovate market data (MES1! -> MESM1)"""
    # Remove ! and convert month codes
    symbol = symbol.upper().replace('!', '')
    # If it ends with a number, it's already in Tradovate format
    if symbol[-1].isdigit():
        return symbol
    # Otherwise, try to get front month (simplified - you may need contract lookup)
    # For now, just return the symbol as-is
    return symbol

async def process_market_data_message(data):
    """Process incoming market data message and update cache"""
    global _market_data_cache
    
    try:
        # Handle different message formats
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    symbol = item.get('symbol') or item.get('s')
                    if symbol:
                        # Update cache with latest price
                        if symbol not in _market_data_cache:
                            _market_data_cache[symbol] = {}
                        
                        # Extract price data
                        last = item.get('last') or item.get('lastPrice') or item.get('l')
                        bid = item.get('bid') or item.get('b')
                        ask = item.get('ask') or item.get('a')
                        
                        if last:
                            _market_data_cache[symbol]['last'] = float(last)
                        if bid:
                            _market_data_cache[symbol]['bid'] = float(bid)
                        if ask:
                            _market_data_cache[symbol]['ask'] = float(ask)
                        
                        # Update PnL for positions with this symbol
                        update_position_pnl()
                        
        elif isinstance(data, dict):
            symbol = data.get('symbol') or data.get('s')
            if symbol:
                if symbol not in _market_data_cache:
                    _market_data_cache[symbol] = {}
                
                last = data.get('last') or data.get('lastPrice') or data.get('l')
                bid = data.get('bid') or data.get('b')
                ask = data.get('ask') or data.get('a')
                
                if last:
                    _market_data_cache[symbol]['last'] = float(last)
                if bid:
                    _market_data_cache[symbol]['bid'] = float(bid)
                if ask:
                    _market_data_cache[symbol]['ask'] = float(ask)
                
                update_position_pnl()
                
    except Exception as e:
        logger.warning(f"Error processing market data: {e}")

def start_market_data_websocket():
    """Start the market data WebSocket in a background thread"""
    global _market_data_ws_task
    if _market_data_ws_task and not _market_data_ws_task.done():
        return  # Already running
    
    def run_websocket():
        asyncio.run(connect_tradovate_market_data_websocket())
    
    _market_data_ws_task = threading.Thread(target=run_websocket, daemon=True)
    _market_data_ws_task.start()
    logger.info("Market data WebSocket thread started")

def update_position_pnl():
    """Update PnL for all cached positions based on current market prices"""
    global _position_cache, _market_data_cache
    
    for cache_key, position in _position_cache.items():
        symbol = position.get('symbol', '')
        if not symbol:
            continue
        
        # Get current price from market data cache
        current_price = _market_data_cache.get(symbol, {}).get('last', 0.0)
        if current_price == 0:
            # Try to get from bid/ask
            market_data = _market_data_cache.get(symbol, {})
            current_price = market_data.get('bid', 0.0) or market_data.get('ask', 0.0)
        
        if current_price > 0 and position.get('avg_price', 0) > 0:
            # Calculate PnL: (current_price - avg_price) * quantity * contract_multiplier
            contract_multiplier = get_contract_multiplier(symbol)
            quantity = position.get('net_quantity', 0)
            avg_price = position.get('avg_price', 0)
            
            # PnL = (current - entry) * quantity * multiplier
            # For long: (current - entry) * qty * mult
            # For short: (entry - current) * qty * mult = (current - entry) * (-qty) * mult
            pnl = (current_price - avg_price) * quantity * contract_multiplier
            
            position['last_price'] = current_price
            position['unrealized_pnl'] = pnl
            
            # Update in database
            try:
                conn = sqlite3.connect('just_trades.db')
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE open_positions 
                    SET last_price = ?, unrealized_pnl = ?, updated_at = ?
                    WHERE symbol = ? AND subaccount_id = ?
                ''', (current_price, pnl, datetime.now().isoformat(), symbol, position.get('subaccount_id')))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.warning(f"Error updating position PnL in database: {e}")
            
            logger.debug(f"Updated PnL for {symbol}: price={current_price}, avg={avg_price}, qty={quantity}, mult={contract_multiplier}, PnL={pnl}")

# ============================================================================
# Custom OCO Monitor - Tracks TP/SL pairs and cancels the other when one fills
# ============================================================================

# Store paired orders: {tp_order_id: sl_order_id, sl_order_id: tp_order_id}
_oco_pairs = {}
# Store order details for monitoring: {order_id: {account_id, symbol, type: 'tp'|'sl', partner_id}}
_oco_order_details = {}
_oco_lock = threading.Lock()

def register_oco_pair(tp_order_id: int, sl_order_id: int, account_id: int, symbol: str):
    """Register a TP/SL pair for OCO monitoring"""
    global _oco_pairs, _oco_order_details
    
    with _oco_lock:
        # Store the pairing both ways for easy lookup
        _oco_pairs[tp_order_id] = sl_order_id
        _oco_pairs[sl_order_id] = tp_order_id
        
        # Store details for each order
        _oco_order_details[tp_order_id] = {
            'account_id': account_id,
            'symbol': symbol,
            'type': 'tp',
            'partner_id': sl_order_id,
            'created_at': time.time()
        }
        _oco_order_details[sl_order_id] = {
            'account_id': account_id,
            'symbol': symbol,
            'type': 'sl',
            'partner_id': tp_order_id,
            'created_at': time.time()
        }
        
        logger.info(f"🔗 OCO pair registered: TP={tp_order_id} <-> SL={sl_order_id} for {symbol}")

def unregister_oco_pair(order_id: int):
    """Remove an OCO pair from monitoring (called when one side fills/cancels)"""
    global _oco_pairs, _oco_order_details
    
    with _oco_lock:
        if order_id in _oco_pairs:
            partner_id = _oco_pairs.pop(order_id, None)
            if partner_id and partner_id in _oco_pairs:
                _oco_pairs.pop(partner_id, None)
            
            # Remove details
            _oco_order_details.pop(order_id, None)
            if partner_id:
                _oco_order_details.pop(partner_id, None)

def monitor_oco_orders():
    """
    Background thread that monitors OCO order pairs across ALL accounts.
    When one order fills, it cancels the partner order on the SAME account.
    """
    logger.info("🔄 OCO Monitor started - watching for TP/SL fills...")
    
    while True:
        try:
            # Only process if we have pairs to monitor
            with _oco_lock:
                if not _oco_pairs:
                    time.sleep(1)
                    continue
                
                # Get a copy of current pairs
                pairs_to_check = dict(_oco_pairs)
                details_copy = dict(_oco_order_details)
            
            if not pairs_to_check:
                time.sleep(1)
                continue
            
            # Get ALL accounts with tokens (for multi-account support)
            conn = sqlite3.connect('just_trades.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, tradovate_token, environment, tradovate_accounts, subaccounts
                FROM accounts 
                WHERE tradovate_token IS NOT NULL AND tradovate_token != ''
            ''')
            all_accounts = cursor.fetchall()
            conn.close()
            
            if not all_accounts:
                time.sleep(2)
                continue
            
            # Group OCO pairs by account_id for efficient processing
            account_orders = {}  # {account_id: [order_ids]}
            for order_id, details in details_copy.items():
                acc_id = details.get('account_id')
                if acc_id:
                    if acc_id not in account_orders:
                        account_orders[acc_id] = []
                    account_orders[acc_id].append(order_id)
            
            # Build a map of account_id -> account info (token, env)
            # Account IDs in our system are the tradovate subaccount IDs (like 26029294)
            account_info_map = {}
            for acc in all_accounts:
                token = acc['tradovate_token']
                env = acc['environment'] or 'demo'
                
                # Try tradovate_accounts field (JSON format)
                tradovate_accounts_str = acc['tradovate_accounts'] or ''
                if tradovate_accounts_str:
                    try:
                        import json
                        tradovate_accounts = json.loads(tradovate_accounts_str)
                        for ta in tradovate_accounts:
                            acc_id = ta.get('id') or ta.get('accountId')
                            if acc_id:
                                account_info_map[int(acc_id)] = {'token': token, 'env': env}
                    except:
                        pass
                
                # Also try subaccounts field (comma-separated or JSON)
                subaccounts_str = acc['subaccounts'] or ''
                if subaccounts_str:
                    try:
                        import json
                        subaccounts = json.loads(subaccounts_str)
                        for sa in subaccounts:
                            if isinstance(sa, dict):
                                acc_id = sa.get('id') or sa.get('accountId')
                            else:
                                acc_id = sa
                            if acc_id:
                                account_info_map[int(acc_id)] = {'token': token, 'env': env}
                    except:
                        # Try comma-separated
                        for tid in subaccounts_str.split(','):
                            tid = tid.strip()
                            if tid:
                                try:
                                    account_info_map[int(tid)] = {'token': token, 'env': env}
                                except ValueError:
                                    pass
            
            # Process each account's orders
            orders_to_remove = []
            partners_to_cancel = []  # [(partner_id, filled_id, symbol, account_id)]
            
            for account_id, order_ids in account_orders.items():
                # Get token for this account
                acc_info = account_info_map.get(account_id)
                if not acc_info:
                    # Try to find any token (fallback for accounts not in our map)
                    if all_accounts:
                        acc_info = {
                            'token': all_accounts[0]['tradovate_token'],
                            'env': all_accounts[0]['environment'] or 'demo'
                        }
                    else:
                        continue
                
                token = acc_info['token']
                env = acc_info['env']
                base_url = 'https://demo.tradovateapi.com/v1' if env == 'demo' else 'https://live.tradovateapi.com/v1'
                headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                
                # Get orders for this account
                try:
                    response = requests.get(f'{base_url}/order/list', headers=headers, timeout=5)
                    if response.status_code != 200:
                        continue
                    
                    orders = response.json()
                    order_status_map = {o.get('id'): o.get('ordStatus', '') for o in orders}
                except Exception as e:
                    logger.debug(f"OCO monitor fetch error for account {account_id}: {e}")
                    continue
                
                # Check each order for this account
                for order_id in order_ids:
                    if order_id not in pairs_to_check:
                        continue
                    
                    partner_id = pairs_to_check.get(order_id)
                    details = details_copy.get(order_id, {})
                    status = order_status_map.get(order_id, '')
                    
                    # If order is filled, we need to cancel the partner
                    if status.lower() == 'filled':
                        order_type = details.get('type', 'unknown')
                        symbol = details.get('symbol', 'unknown')
                        
                        logger.info(f"🎯 OCO: {order_type.upper()} order {order_id} FILLED for {symbol} (account {account_id})")
                        logger.info(f"🎯 OCO: Cancelling partner order {partner_id}...")
                        
                        partners_to_cancel.append((partner_id, order_id, symbol, account_id, token, env))
                        orders_to_remove.append(order_id)
                    
                    # If order is cancelled/rejected, just remove from monitoring
                    elif status.lower() in ['canceled', 'cancelled', 'rejected', 'expired']:
                        orders_to_remove.append(order_id)
            
            # Cancel partner orders (using the correct token for each account)
            for partner_id, filled_id, symbol, account_id, token, env in partners_to_cancel:
                try:
                    base_url = 'https://demo.tradovateapi.com/v1' if env == 'demo' else 'https://live.tradovateapi.com/v1'
                    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                    
                    cancel_response = requests.post(
                        f'{base_url}/order/cancelorder',
                        json={'orderId': partner_id, 'isAutomated': True},
                        headers=headers,
                        timeout=5
                    )
                    if cancel_response.status_code == 200:
                        result = cancel_response.json()
                        if result.get('errorText'):
                            logger.warning(f"⚠️ OCO: Cancel returned error for {partner_id}: {result.get('errorText')}")
                        else:
                            logger.info(f"✅ OCO: Successfully cancelled partner order {partner_id} for {symbol} (account {account_id})")
                        
                        # Emit event to frontend
                        socketio.emit('oco_triggered', {
                            'filled_order': filled_id,
                            'cancelled_order': partner_id,
                            'symbol': symbol,
                            'account_id': account_id,
                            'message': f'OCO triggered: cancelled partner order for {symbol}'
                        })
                    else:
                        logger.warning(f"⚠️ OCO: Failed to cancel partner order {partner_id}: {cancel_response.text[:200]}")
                except Exception as e:
                    logger.error(f"❌ OCO: Error cancelling partner order {partner_id}: {e}")
            
            # Remove processed orders from monitoring
            for order_id in orders_to_remove:
                unregister_oco_pair(order_id)
            
            time.sleep(1)  # Check every second
            
        except Exception as e:
            logger.error(f"OCO Monitor error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            time.sleep(2)

# Start OCO monitor thread
oco_monitor_thread = threading.Thread(target=monitor_oco_orders, daemon=True)
oco_monitor_thread.start()
logger.info("🔄 OCO Monitor thread started")

# ============================================================================
# Break-Even Monitor - Moves SL to entry price when position goes profitable
# ============================================================================

# Store break-even monitors: {key: {account_id, symbol, entry_price, is_long, activation_ticks, ...}}
_break_even_monitors = {}
_break_even_lock = threading.Lock()

def register_break_even_monitor(account_id: int, symbol: str, entry_price: float, is_long: bool,
                                 activation_ticks: int, tick_size: float, sl_order_id: int,
                                 quantity: int, account_spec: str):
    """Register a position for break-even monitoring"""
    global _break_even_monitors
    
    key = f"{account_id}:{symbol}"
    
    with _break_even_lock:
        _break_even_monitors[key] = {
            'account_id': account_id,
            'symbol': symbol,
            'entry_price': entry_price,
            'is_long': is_long,
            'activation_ticks': activation_ticks,
            'tick_size': tick_size,
            'sl_order_id': sl_order_id,
            'quantity': quantity,
            'account_spec': account_spec,
            'triggered': False,
            'created_at': time.time()
        }
        
        activation_price = entry_price + (tick_size * activation_ticks) if is_long else entry_price - (tick_size * activation_ticks)
        logger.info(f"📊 Break-even monitor registered: {symbol} on account {account_id}")
        logger.info(f"   Entry: {entry_price}, Activation: {activation_price} ({activation_ticks} ticks)")

def unregister_break_even_monitor(key: str):
    """Remove a break-even monitor"""
    global _break_even_monitors
    
    with _break_even_lock:
        if key in _break_even_monitors:
            _break_even_monitors.pop(key)

def monitor_break_even():
    """
    Background thread that monitors positions for break-even activation.
    When price reaches activation_ticks profit, cancels old SL and places new SL at entry.
    """
    logger.info("📊 Break-Even Monitor started")
    
    while True:
        try:
            with _break_even_lock:
                if not _break_even_monitors:
                    time.sleep(2)
                    continue
                
                monitors_copy = dict(_break_even_monitors)
            
            if not monitors_copy:
                time.sleep(2)
                continue
            
            # Get tokens from database
            conn = sqlite3.connect('just_trades.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, tradovate_token, environment, tradovate_accounts, subaccounts
                FROM accounts 
                WHERE tradovate_token IS NOT NULL AND tradovate_token != ''
            ''')
            all_accounts = cursor.fetchall()
            conn.close()
            
            if not all_accounts:
                time.sleep(2)
                continue
            
            # Build account info map
            account_info_map = {}
            for acc in all_accounts:
                token = acc['tradovate_token']
                env = acc['environment'] or 'demo'
                
                tradovate_accounts_str = acc['tradovate_accounts'] or ''
                if tradovate_accounts_str:
                    try:
                        tradovate_accounts = json.loads(tradovate_accounts_str)
                        for ta in tradovate_accounts:
                            acc_id = ta.get('id') or ta.get('accountId')
                            is_demo = ta.get('is_demo', True)
                            if acc_id:
                                account_info_map[int(acc_id)] = {'token': token, 'env': 'demo' if is_demo else 'live'}
                    except:
                        pass
            
            # Check each monitored position
            monitors_to_remove = []
            
            for key, monitor in monitors_copy.items():
                if monitor.get('triggered'):
                    continue
                
                account_id = monitor['account_id']
                symbol = monitor['symbol']
                entry_price = monitor['entry_price']
                is_long = monitor['is_long']
                activation_ticks = monitor['activation_ticks']
                tick_size = monitor['tick_size']
                sl_order_id = monitor['sl_order_id']
                quantity = monitor['quantity']
                account_spec = monitor['account_spec']
                
                acc_info = account_info_map.get(account_id)
                if not acc_info:
                    continue
                
                token = acc_info['token']
                env = acc_info['env']
                base_url = 'https://demo.tradovateapi.com/v1' if env == 'demo' else 'https://live.tradovateapi.com/v1'
                headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
                
                try:
                    # Get current positions
                    pos_response = requests.get(f'{base_url}/position/list', headers=headers, timeout=5)
                    if pos_response.status_code != 200:
                        continue
                    
                    positions = pos_response.json()
                    
                    # Find matching position
                    position = None
                    for p in positions:
                        if p.get('accountId') == account_id:
                            pos_symbol = p.get('contractId')  # Need to resolve
                            # For now, check by netPos direction matching
                            net_pos = p.get('netPos', 0)
                            if (is_long and net_pos > 0) or (not is_long and net_pos < 0):
                                position = p
                                break
                    
                    if not position:
                        # Position closed, remove monitor
                        monitors_to_remove.append(key)
                        continue
                    
                    # Get current price (from position's netPrice or last trade)
                    current_price = position.get('netPrice', 0)
                    if not current_price:
                        continue
                    
                    # Calculate profit in ticks
                    if is_long:
                        profit_ticks = (current_price - entry_price) / tick_size
                    else:
                        profit_ticks = (entry_price - current_price) / tick_size
                    
                    # Check if activation threshold reached
                    if profit_ticks >= activation_ticks:
                        logger.info(f"🎯 Break-even triggered for {symbol}! Profit: {profit_ticks:.1f} ticks >= {activation_ticks} ticks")
                        
                        # Cancel old SL order
                        if sl_order_id:
                            cancel_response = requests.post(
                                f'{base_url}/order/cancelorder',
                                json={'orderId': sl_order_id, 'isAutomated': True},
                                headers=headers,
                                timeout=5
                            )
                            if cancel_response.status_code == 200:
                                logger.info(f"✅ Cancelled old SL order {sl_order_id}")
                        
                        # Place new SL at entry price (break-even)
                        exit_side = 'Sell' if is_long else 'Buy'
                        new_sl_data = {
                            "accountSpec": account_spec,
                            "orderType": "Stop",
                            "action": exit_side,
                            "symbol": symbol,
                            "orderQty": int(quantity),
                            "stopPrice": float(entry_price),
                            "timeInForce": "GTC",
                            "isAutomated": True
                        }
                        
                        sl_response = requests.post(
                            f'{base_url}/order/placeorder',
                            json=new_sl_data,
                            headers=headers,
                            timeout=5
                        )
                        
                        if sl_response.status_code == 200:
                            result = sl_response.json()
                            new_sl_id = result.get('orderId')
                            logger.info(f"✅ Break-even SL placed at {entry_price}, Order ID: {new_sl_id}")
                            
                            # Emit to frontend
                            socketio.emit('break_even_triggered', {
                                'symbol': symbol,
                                'account_id': account_id,
                                'entry_price': entry_price,
                                'new_sl_order_id': new_sl_id,
                                'message': f'Break-even activated for {symbol}'
                            })
                        else:
                            logger.warning(f"⚠️ Failed to place break-even SL: {sl_response.text[:200]}")
                        
                        # Mark as triggered
                        with _break_even_lock:
                            if key in _break_even_monitors:
                                _break_even_monitors[key]['triggered'] = True
                        
                        monitors_to_remove.append(key)
                
                except Exception as e:
                    logger.debug(f"Break-even monitor error for {key}: {e}")
                    continue
            
            # Remove processed monitors
            for key in monitors_to_remove:
                unregister_break_even_monitor(key)
            
            time.sleep(2)  # Check every 2 seconds
            
        except Exception as e:
            logger.error(f"Break-Even Monitor error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            time.sleep(3)

# Start break-even monitor thread
break_even_thread = threading.Thread(target=monitor_break_even, daemon=True)
break_even_thread.start()
logger.info("📊 Break-Even Monitor thread started")

# ============================================================================
# Tradovate PnL Fetching (Direct from API - No Market Data Required!)
# ============================================================================

# Cache for Tradovate PnL data
_tradovate_pnl_cache = {
    'last_fetch': 0,
    'data': {},
    'positions': []
}

def fetch_tradovate_pnl_sync():
    """
    Fetch real-time PnL directly from Tradovate's cashBalance API.
    This is the CORRECT way to get PnL - Tradovate calculates it for us!
    No market data subscription required.
    """
    global _tradovate_pnl_cache
    
    current_time = time.time()
    
    # Dynamic throttling based on account count to avoid rate limits
    # Tradovate allows ~120 requests/min, each account needs 2 calls (cashBalance + positions)
    # 
    # SCALING TABLE:
    # Accounts | Calls/update | Safe interval | Updates/min
    # ---------|--------------|---------------|------------
    #    1     |      2       |    0.5s       |    120
    #    2     |      4       |    0.5s       |    120  
    #    5     |     10       |    1.0s       |     60
    #   10     |     20       |    2.0s       |     30
    #   20     |     40       |    4.0s       |     15
    #   50     |    100       |   10.0s       |      6
    #
    # Formula: interval = max(0.5, num_accounts * 0.2) to stay under 120 req/min
    num_accounts = _tradovate_pnl_cache.get('account_count', 2)
    if not isinstance(num_accounts, int) or num_accounts < 1:
        num_accounts = 2
    min_interval = max(0.5, num_accounts * 0.2)  # Scale up as accounts increase
    
    if current_time - _tradovate_pnl_cache['last_fetch'] < min_interval:
        return _tradovate_pnl_cache['data'], _tradovate_pnl_cache['positions']
    
    try:
        # Get ALL connected accounts from database (multi-account support for copy trading)
        conn = sqlite3.connect('just_trades.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, tradovate_token, tradovate_accounts, environment
            FROM accounts 
            WHERE tradovate_token IS NOT NULL AND tradovate_token != ''
        ''')
        all_linked_accounts = cursor.fetchall()
        conn.close()
        
        if not all_linked_accounts:
            return {}, []
        
        all_pnl_data = {}
        all_positions = []
        total_subaccounts = 0
        
        # Process each linked account (user may have multiple Tradovate logins)
        for account in all_linked_accounts:
            token = account['tradovate_token']
            env = account['environment'] or 'demo'
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Parse tradovate_accounts to get subaccount IDs
            tradovate_accounts = []
            try:
                if account['tradovate_accounts']:
                    tradovate_accounts = json.loads(account['tradovate_accounts'])
            except:
                pass
            
            total_subaccounts += len(tradovate_accounts)
            
            # Fetch PnL for each subaccount under this linked account
            for ta in tradovate_accounts:
                acc_id = ta.get('id')
                acc_name = ta.get('name', str(acc_id))
                is_demo = ta.get('is_demo', True)
                
                # Use correct base URL for demo vs live accounts
                acc_base_url = 'https://demo.tradovateapi.com/v1' if is_demo else 'https://live.tradovateapi.com/v1'
                
                try:
                    # Get cash balance snapshot (includes openPnL!)
                    response = requests.get(
                        f'{acc_base_url}/cashBalance/getCashBalanceSnapshot?accountId={acc_id}',
                        headers=headers,
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        snap = response.json()
                        all_pnl_data[acc_id] = {
                            'account_id': acc_id,
                            'account_name': acc_name,
                            'is_demo': is_demo,
                            'total_cash_value': snap.get('totalCashValue', 0),
                            'net_liq': snap.get('netLiq', 0),
                            'open_pnl': snap.get('openPnL', 0),  # Unrealized PnL!
                            'realized_pnl': snap.get('realizedPnL', 0),
                            'total_pnl': snap.get('totalPnL', 0),
                            'week_realized_pnl': snap.get('weekRealizedPnL', 0),
                            'initial_margin': snap.get('initialMargin', 0),
                            'maintenance_margin': snap.get('maintenanceMargin', 0)
                        }
                        logger.debug(f"Fetched PnL for {acc_name}: openPnL=${snap.get('openPnL', 0):.2f}, realizedPnL=${snap.get('realizedPnL', 0):.2f}")
                    elif response.status_code == 429:
                        # Rate limited - back off by increasing cache time
                        logger.warning(f"Rate limited by Tradovate (429)! Slowing down...")
                        _tradovate_pnl_cache['account_count'] = max(10, _tradovate_pnl_cache.get('account_count', 2) * 2)
                        return _tradovate_pnl_cache.get('data', {}), _tradovate_pnl_cache.get('positions', [])
                    elif response.status_code == 401:
                        logger.warning(f"Token expired for account {acc_id} - will refresh on next trade")
                        continue
                    else:
                        logger.debug(f"Cash balance API returned {response.status_code} for {acc_id}: {response.text[:100]}")
                    
                    # Get positions for this account
                    pos_response = requests.get(
                        f'{acc_base_url}/position/list',
                        headers=headers,
                        timeout=5
                    )
                    
                    if pos_response.status_code == 200:
                        positions = pos_response.json()
                        for pos in positions:
                            if pos.get('netPos', 0) != 0:  # Only open positions
                                # Get contract name
                                contract_id = pos.get('contractId')
                                contract_name = get_contract_name_cached(contract_id, acc_base_url, headers)
                                
                                all_positions.append({
                                    'account_id': acc_id,
                                    'account_name': acc_name,
                                    'is_demo': is_demo,
                                    'contract_id': contract_id,
                                    'symbol': contract_name,
                                    'net_quantity': pos.get('netPos', 0),
                                    'bought': pos.get('bought', 0),
                                    'bought_value': pos.get('boughtValue', 0),
                                    'sold': pos.get('sold', 0),
                                    'sold_value': pos.get('soldValue', 0),
                                    # Calculate avg price from bought/sold values
                                    'avg_price': calculate_avg_price(pos),
                                    'timestamp': pos.get('timestamp')
                                })
                                
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Error fetching PnL for account {acc_id}: {e}")
                    continue
        
        # Update cache (including total subaccount count for dynamic throttling)
        _tradovate_pnl_cache['last_fetch'] = current_time
        _tradovate_pnl_cache['data'] = all_pnl_data
        _tradovate_pnl_cache['positions'] = all_positions
        _tradovate_pnl_cache['account_count'] = total_subaccounts  # Total across all linked accounts
        
        if total_subaccounts > 5:
            logger.info(f"Monitoring {total_subaccounts} subaccounts, update interval: {max(0.5, total_subaccounts * 0.2):.1f}s")
        
        return all_pnl_data, all_positions
        
    except Exception as e:
        logger.error(f"Error fetching Tradovate PnL: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return _tradovate_pnl_cache.get('data', {}), _tradovate_pnl_cache.get('positions', [])

# Cache for contract names
_contract_name_cache = {}

def get_contract_name_cached(contract_id, base_url, headers):
    """Get contract name from ID, with caching"""
    global _contract_name_cache
    
    if contract_id in _contract_name_cache:
        return _contract_name_cache[contract_id]
    
    try:
        response = requests.get(
            f'{base_url}/contract/item?id={contract_id}',
            headers=headers,
            timeout=5
        )
        if response.status_code == 200:
            contract = response.json()
            name = contract.get('name', str(contract_id))
            _contract_name_cache[contract_id] = name
            return name
    except:
        pass
    
    return str(contract_id)

def calculate_avg_price(position):
    """Calculate average entry price from position data"""
    net_pos = position.get('netPos', 0)
    if net_pos == 0:
        return 0
    
    if net_pos > 0:
        # Long position - use bought value
        bought = position.get('bought', 0)
        bought_value = position.get('boughtValue', 0)
        if bought > 0:
            return bought_value / bought
    else:
        # Short position - use sold value
        sold = position.get('sold', 0)
        sold_value = position.get('soldValue', 0)
        if sold > 0:
            return sold_value / sold
    
    return 0

def emit_realtime_updates():
    """Emit real-time updates every second (like Trade Manager)"""
    global _position_cache
    while True:
        try:
            # ============================================================
            # FETCH REAL-TIME PnL DIRECTLY FROM TRADOVATE
            # This is the correct approach - no market data needed!
            # ============================================================
            
            total_pnl = 0.0
            today_pnl = 0.0
            open_pnl = 0.0
            active_positions = 0
            positions_list = []
            
            # Fetch PnL from Tradovate's cashBalance API
            pnl_data, tradovate_positions = fetch_tradovate_pnl_sync()
            
            if pnl_data:
                # Sum up PnL from all accounts
                for acc_id, acc_data in pnl_data.items():
                    open_pnl += acc_data.get('open_pnl', 0)
                    today_pnl += acc_data.get('realized_pnl', 0)
                    total_pnl += acc_data.get('total_pnl', 0)
                
                logger.debug(f"Tradovate PnL: open=${open_pnl:.2f}, realized=${today_pnl:.2f}, total=${total_pnl:.2f}")
            
            if tradovate_positions:
                active_positions = len(tradovate_positions)
                positions_list = [{
                    'symbol': pos.get('symbol', 'Unknown'),
                    'net_quantity': pos.get('net_quantity', 0),
                    'avg_price': pos.get('avg_price', 0),
                    'account_id': pos.get('account_id'),
                    'account_name': pos.get('account_name'),
                    'is_demo': pos.get('is_demo', True),
                    # Note: unrealized_pnl per position requires market data
                    # But we have total open_pnl from cashBalance
                } for pos in tradovate_positions]
            
            # Also include any synthetic positions from manual trades
            if _position_cache:
                for cache_key, pos in _position_cache.items():
                    # Check if this position is already in tradovate_positions
                    exists = any(
                        p.get('symbol') == pos.get('symbol') and 
                        p.get('account_id') == pos.get('account_id')
                        for p in positions_list
                    )
                    if not exists and pos.get('net_quantity', 0) != 0:
                        positions_list.append(pos)
                        active_positions = len(positions_list)
            
            # Emit P&L updates with REAL data from Tradovate
            socketio.emit('pnl_update', {
                'total_pnl': total_pnl,
                'open_pnl': open_pnl,  # Unrealized PnL
                'today_pnl': today_pnl,  # Realized PnL today
                'active_positions': active_positions,
                'timestamp': datetime.now().isoformat()
            })
            
            # Emit position updates
            socketio.emit('position_update', {
                'positions': positions_list,
                'count': active_positions,
                'pnl_data': pnl_data,  # Include full PnL data per account
                'timestamp': datetime.now().isoformat()
            })
            
            # Note: Position and PnL fetching is now handled by fetch_tradovate_pnl_sync() above
            # The new implementation uses Tradovate's cashBalance API which provides 
            # real-time PnL without needing market data subscription
            
        except Exception as e:
            logger.error(f"Error emitting real-time updates: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
        time.sleep(0.5)  # Every 0.5 seconds for maximum speed

def record_strategy_pnl_continuously():
    """Record P&L for all active strategies every second (like Trade Manager)"""
    while True:
        try:
            strategies = []
            
            # Try SQLAlchemy models first
            try:
                from app.database import SessionLocal
                from app.models import Strategy
                
                db = SessionLocal()
                active_strategies = db.query(Strategy).filter(Strategy.active == True).all()
                strategies = [(s.id, s.name) for s in active_strategies]
                db.close()
                
            except (ImportError, Exception):
                # Fallback to SQLite direct query
                try:
                    conn = sqlite3.connect('trading_webhook.db')
                    cursor = conn.execute('''
                        SELECT id, name FROM strategies WHERE enabled = 1
                    ''')
                    strategies = cursor.fetchall()
                    conn.close()
                except sqlite3.OperationalError as e:
                    # If strategies table doesn't exist yet, that's okay
                    if 'no such table' not in str(e).lower():
                        logger.debug(f"Strategies table not found: {e}")
                    strategies = []
            
            # Record P&L for each strategy
            for strategy_id, strategy_name in strategies:
                try:
                    # Calculate current P&L for strategy
                    pnl = calculate_strategy_pnl(strategy_id)
                    drawdown = calculate_strategy_drawdown(strategy_id)
                    
                    # Record to database
                    record_strategy_pnl(strategy_id, strategy_name, pnl, drawdown)
                    
                    # Emit real-time update
                    socketio.emit('strategy_pnl_update', {
                        'strategy_id': strategy_id,
                        'strategy_name': strategy_name,
                        'pnl': pnl,
                        'drawdown': drawdown,
                        'timestamp': datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.error(f"Error processing strategy {strategy_id}: {e}")
                
        except Exception as e:
            logger.error(f"Error recording strategy P&L: {e}")
        time.sleep(1)  # Every second

# Start background threads
update_thread = threading.Thread(target=emit_realtime_updates, daemon=True)
update_thread.start()

pnl_recording_thread = threading.Thread(target=record_strategy_pnl_continuously, daemon=True)
pnl_recording_thread.start()

# Start Tradovate market data WebSocket
if WEBSOCKETS_AVAILABLE:
    start_market_data_websocket()
    logger.info("✅ Market data WebSocket thread started")
else:
    logger.warning("websockets library not installed. Market data WebSocket will not work. Install with: pip install websockets")

# Configure logging for production
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == '__main__':
    # For local development
    parser = argparse.ArgumentParser(description='Start the trading webhook server.')
    parser.add_argument('--port', type=int, default=8082, help='Port to run the server on.')
    args = parser.parse_args()

    port = args.port
    logger.info(f"Starting Just.Trades. server on 0.0.0.0:{port}")
    logger.info("WebSocket support enabled (like Trade Manager)")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
