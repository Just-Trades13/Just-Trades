# Recorder Backend Service

Standalone backend service for managing recorder operations. This service runs independently and can be started in a new terminal/context window.

## Overview

The Recorder Backend Service handles:
- Starting/stopping position recording for strategies
- Polling Tradovate demo accounts for positions
- Recording position entries and exits
- Tracking P&L and position status
- Logging strategy events

## Quick Start

### Option 1: Using the startup script
```bash
./start_recorder_backend.sh
```

### Option 2: Manual start
```bash
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3 recorder_backend.py --port 8083
```

### Initialize database (first time only)
```bash
python3 recorder_backend.py --init-db --port 8083
```

## Configuration

### Environment Variables
Create a `.env` file in the project root:
```bash
DB_PATH=just_trades.db  # Path to your database file
```

### Command Line Options
```bash
python3 recorder_backend.py --help

Options:
  --port PORT        Port to run on (default: 8083)
  --host HOST        Host to bind to (default: 127.0.0.1)
  --db DB_PATH       Database path (default: just_trades.db)
  --init-db          Initialize database tables
```

## API Endpoints

### Health Check
```bash
GET http://localhost:8083/health
```
Returns service status and active recordings count.

### Start Recording
```bash
POST http://localhost:8083/api/recorders/start/<strategy_id>
Content-Type: application/json

{
  "poll_interval": 30  # Optional, seconds between polls (default: 30)
}
```

### Stop Recording
```bash
POST http://localhost:8083/api/recorders/stop/<strategy_id>
```

### Get Recording Status
```bash
GET http://localhost:8083/api/recorders/status
```
Returns list of all active recordings.

### Get Recorded Positions
```bash
GET http://localhost:8083/api/recorders/positions/<strategy_id>
```
Returns last 100 recorded positions for a strategy.

## How It Works

1. **Start Recording**: When you start recording for a strategy, the service:
   - Verifies the strategy exists and has recording enabled
   - Checks that a demo account is configured
   - Starts a background thread that polls Tradovate every 30 seconds (or custom interval)

2. **Position Polling**: The recording loop:
   - Connects to Tradovate using account credentials
   - Fetches current positions for the demo account
   - Filters positions by the strategy's symbol
   - Detects new positions, position changes, and position closures

3. **Position Recording**: When a position is detected:
   - **Entry**: Records entry price, quantity, side, stop loss, take profit
   - **Exit**: Records exit price, calculates P&L, updates status
   - **Logs**: Creates strategy log entries for all events

4. **Database**: All data is stored in SQLite:
   - `recorded_positions` - Position entries and exits
   - `strategy_logs` - Event logs
   - `strategies` - Strategy configuration
   - `accounts` - Account credentials

## Running in Production

### As a Background Service
```bash
nohup python3 recorder_backend.py --port 8083 > recorder_backend.log 2>&1 &
```

### With systemd (Linux)
Create `/etc/systemd/system/recorder-backend.service`:
```ini
[Unit]
Description=Recorder Backend Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/Users/mylesjadwin/Trading Projects
Environment="PATH=/Users/mylesjadwin/Trading Projects/venv/bin"
ExecStart=/Users/mylesjadwin/Trading Projects/venv/bin/python3 recorder_backend.py --port 8083
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable recorder-backend
sudo systemctl start recorder-backend
```

## Troubleshooting

### Service won't start
- Check if port 8083 is already in use: `lsof -i :8083`
- Verify database file exists and is writable
- Check logs in `recorder_backend.log`

### Positions not recording
- Verify strategy has `recording_enabled = 1` in database
- Check that demo account is configured (`demo_account_id` is set)
- Verify Tradovate credentials are correct in `accounts` table
- Check Tradovate integration is available (see logs)

### Database errors
- Run `--init-db` to create missing tables
- Check database file permissions
- Verify database path in `.env` or `--db` argument

## Integration with Main Server

The recorder backend runs independently but can be integrated with the main Flask server:

1. **From main server**, call recorder backend API:
```python
import requests

# Start recording
response = requests.post('http://localhost:8083/api/recorders/start/1', 
                        json={'poll_interval': 30})

# Get positions
response = requests.get('http://localhost:8083/api/recorders/positions/1')
```

2. **Or use the recorder backend directly** from your frontend/API

## Next Steps

- Add WebSocket support for real-time position updates
- Add Discord notifications for position events
- Implement position matching logic (match positions to strategies)
- Add performance metrics calculation
- Add support for multiple accounts per strategy

