#!/bin/bash
# Restart the server to load new routes

echo "🔄 Restarting server to load new routes..."

# Find and kill existing server
pkill -f "ultra_simple_server.py"

# Wait a moment
sleep 2

# Start server in background
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
nohup python3 ultra_simple_server.py > server.log 2>&1 &

echo "✅ Server restarted!"
echo "   Logs: server.log"
echo "   Test: python3 test_traderspost_connection.py 4"
echo ""
echo "To view logs: tail -f server.log"

