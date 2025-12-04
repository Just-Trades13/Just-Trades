# WebSocket Implementation Guide

**Based on your Trade Manager findings**

---

## Step 1: Install Dependency

```bash
pip install flask-socketio
```

---

## Step 2: Add to ultra_simple_server.py

### 2.1 Add Import (after line 24)

```python
from flask_socketio import SocketIO, emit
```

### 2.2 Initialize SocketIO (after line 36, where app is created)

```python
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
```

### 2.3 Add WebSocket Handlers (add before the `if __name__ == '__main__':` section)

```python
# ============================================================================
# WebSocket Handlers
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
# Background Thread for Real-Time Updates (Every Second)
# ============================================================================

def emit_realtime_updates():
    """Emit real-time updates every second (like Trade Manager)"""
    while True:
        try:
            # Calculate current metrics
            total_pnl = 0.0  # TODO: Calculate from database
            today_pnl = 0.0  # TODO: Calculate from database
            active_positions = 0  # TODO: Get from database
            
            # Emit P&L updates
            socketio.emit('pnl_update', {
                'total_pnl': total_pnl,
                'today_pnl': today_pnl,
                'active_positions': active_positions,
                'timestamp': datetime.now().isoformat()
            })
            
            # Emit position updates
            positions = []  # TODO: Get positions from database
            socketio.emit('position_update', {
                'positions': positions,
                'count': len(positions),
                'timestamp': datetime.now().isoformat()
            })
            
            # Emit market data (if you have it)
            # socketio.emit('market_data', {
            #     'type': 'DATA',
            #     'data': {
            #         'ticker': 'NQ1!',
            #         'prices': {'ask': 0, 'bid': 0},
            #         'tickinfo': {'step': 0.25, 'amnt': 5.0}
            #     }
            # })
            
        except Exception as e:
            logger.error(f"Error emitting real-time updates: {e}")
        time.sleep(1)  # Every second, like Trade Manager

# Start background thread
update_thread = threading.Thread(target=emit_realtime_updates, daemon=True)
update_thread.start()
```

### 2.4 Change app.run to socketio.run (line 2348)

**Change this:**
```python
app.run(host='0.0.0.0', port=port, debug=False)
```

**To this:**
```python
socketio.run(app, host='0.0.0.0', port=port, debug=False)
```

---

## Step 3: Add Strategy P&L Recording

### 3.1 Add Database Table (in init_db function or create new function)

```python
def init_strategy_pnl_db():
    """Initialize strategy P&L history database"""
    conn = sqlite3.connect('trading_webhook.db')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS strategy_pnl_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER,
            strategy_name TEXT,
            pnl REAL,
            drawdown REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES strategies(id)
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_strategy_pnl_timestamp 
        ON strategy_pnl_history(strategy_id, timestamp)
    ''')
    conn.commit()
    conn.close()
```

### 3.2 Add P&L Recording Function

```python
def record_strategy_pnl(strategy_id, strategy_name, pnl, drawdown=0.0):
    """Record strategy P&L to database"""
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
```

### 3.3 Add Background Service to Record P&L

```python
def record_strategy_pnl_continuously():
    """Record P&L for all active strategies every second"""
    while True:
        try:
            # Get all active strategies
            conn = sqlite3.connect('trading_webhook.db')
            cursor = conn.execute('''
                SELECT id, name FROM strategies WHERE enabled = 1
            ''')
            strategies = cursor.fetchall()
            conn.close()
            
            for strategy_id, strategy_name in strategies:
                # Calculate current P&L for strategy
                pnl = calculate_strategy_pnl(strategy_id)  # TODO: Implement this
                drawdown = calculate_strategy_drawdown(strategy_id)  # TODO: Implement this
                
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
            logger.error(f"Error recording strategy P&L: {e}")
        time.sleep(1)  # Every second

# Start P&L recording thread
pnl_recording_thread = threading.Thread(target=record_strategy_pnl_continuously, daemon=True)
pnl_recording_thread.start()
```

---

## Step 4: Add Dashboard APIs

### 4.1 P&L Calendar API

```python
@app.route('/api/dashboard/pnl-calendar', methods=['GET'])
def api_pnl_calendar():
    """Get P&L data for calendar view"""
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).isoformat())
    end_date = request.args.get('end_date', datetime.now().isoformat())
    
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.execute('''
        SELECT DATE(timestamp) as date, SUM(pnl) as daily_pnl
        FROM strategy_pnl_history
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY DATE(timestamp)
        ORDER BY date
    ''', (start_date, end_date))
    
    data = [{'date': row[0], 'pnl': row[1]} for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'calendar_data': data})
```

### 4.2 P&L vs Drawdown Chart API

```python
@app.route('/api/dashboard/pnl-drawdown-chart', methods=['GET'])
def api_pnl_drawdown_chart():
    """Get P&L and drawdown data for chart"""
    strategy_id = request.args.get('strategy_id', None)
    
    query = '''
        SELECT timestamp, pnl, drawdown
        FROM strategy_pnl_history
    '''
    params = []
    
    if strategy_id:
        query += ' WHERE strategy_id = ?'
        params.append(strategy_id)
    
    query += ' ORDER BY timestamp LIMIT 1000'
    
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.execute(query, params)
    
    data = [{
        'timestamp': row[0],
        'pnl': row[1],
        'drawdown': row[2]
    } for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'chart_data': data})
```

---

## Step 5: Update Frontend

### 5.1 Add to Control Center (templates/control_center.html)

Add before closing `</body>` tag:

```html
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
const socket = io();

socket.on('connect', () => {
    console.log('Connected to WebSocket');
    const statusDot = document.querySelector('.status-dot');
    if (statusDot) {
        statusDot.textContent = 'Connected';
        statusDot.classList.add('connected');
    }
});

socket.on('disconnect', () => {
    console.log('Disconnected from WebSocket');
    const statusDot = document.querySelector('.status-dot');
    if (statusDot) {
        statusDot.textContent = 'Disconnected';
        statusDot.classList.remove('connected');
    }
});

// P&L updates
socket.on('pnl_update', (data) => {
    console.log('P&L update:', data);
    // Update P&L in Live Trading Panel
    updatePnLInTable(data);
});

// Position updates
socket.on('position_update', (data) => {
    console.log('Position update:', data);
    // Update positions in table
    updatePositionsInTable(data.positions);
});

// Strategy P&L updates
socket.on('strategy_pnl_update', (data) => {
    console.log('Strategy P&L update:', data);
    // Update specific strategy P&L
    updateStrategyPnL(data.strategy_id, data.pnl);
});

// Log entries
socket.on('log_entry', (data) => {
    console.log('Log entry:', data);
    addLogEntry(data.type, data.message, data.time);
});

function updatePnLInTable(data) {
    // Update P&L cells in Live Trading Panel
    const rows = document.querySelectorAll('.live-trading tbody tr');
    // Implementation depends on your table structure
}

function updatePositionsInTable(positions) {
    // Update position counts
    // Implementation depends on your table structure
}

function updateStrategyPnL(strategyId, pnl) {
    // Find row by strategy ID and update P&L
    const row = document.querySelector(`[data-strategy-id="${strategyId}"]`);
    if (row) {
        const pnlCell = row.querySelector('.pl-cell');
        if (pnlCell) {
            pnlCell.textContent = pnl.toFixed(2);
            pnlCell.className = `pl-cell ${pnl >= 0 ? 'positive' : 'negative'}`;
        }
    }
}

function addLogEntry(type, message, time) {
    const logFeed = document.querySelector('.log-feed');
    if (logFeed) {
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.innerHTML = `
            <span class="log-type ${type}">[${type.toUpperCase()}]</span>
            <span class="log-content">${message}</span>
            <span class="log-time">${new Date(time).toLocaleTimeString()}</span>
        `;
        logFeed.appendChild(logEntry);
        logFeed.scrollTop = logFeed.scrollHeight;
    }
}
</script>
```

---

## Step 6: Emit Events After Trades

In your trade execution functions, after a successful trade:

```python
# After trade is executed
socketio.emit('log_entry', {
    'type': 'trade',
    'message': f'Trade executed: {side} {quantity} {symbol} @ {price}',
    'time': datetime.now().isoformat()
})

socketio.emit('position_update', {
    'strategy': strategy_name,
    'symbol': symbol,
    'quantity': quantity,
    'side': side,
    'price': price,
    'timestamp': datetime.now().isoformat()
})
```

---

## Testing

1. **Start server**: `python ultra_simple_server.py`
2. **Open browser console**: Check for "Connected to WebSocket"
3. **Check Network tab**: Should see WebSocket connection
4. **Watch console**: Should see update messages every second

---

**Ready to implement?** I can add these changes directly to your files!

