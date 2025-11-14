#!/usr/bin/env python3
import sqlite3
import logging
import asyncio
import argparse
import sys
import os
import requests
from flask import Flask, request, jsonify, render_template, redirect, url_for
from datetime import datetime

app = Flask(__name__)
logger = logging.getLogger(__name__)

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

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/accounts')
def accounts():
    return render_template('account_management.html')

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
                
                if current_price > 0 and previous_close > 0:
                    change_pct = ((current_price - previous_close) / previous_close) * 100
                    
                    # Get market cap from company profile
                    profile_url = f'https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={api_key}'
                    profile_response = requests.get(profile_url, timeout=2)
                    real_market_cap = market_cap  # Default
                    
                    if profile_response.status_code == 200:
                        profile = profile_response.json()
                        if 'marketCapitalization' in profile:
                            real_market_cap = profile['marketCapitalization'] / 1_000_000_000  # Convert to billions
                    
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
                            # Try to get real market cap from Yahoo Finance
                            real_market_cap = meta.get('marketCap', None)
                            if real_market_cap:
                                # Convert to billions for easier comparison
                                market_cap_billions = real_market_cap / 1_000_000_000
                            else:
                                # Fallback to provided market cap
                                market_cap_billions = market_cap
                            
                            if current_price > 0 and previous_close > 0:
                                change_pct = ((current_price - previous_close) / previous_close) * 100
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
