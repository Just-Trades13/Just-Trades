#!/bin/bash
# Quick script to start Flask + ngrok for sharing

echo "🚀 Starting Flask server on port 8082..."
cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate
python3 ultra_simple_server.py --port 8082 > flask_output.log 2>&1 &
FLASK_PID=$!

echo "⏳ Waiting for Flask to start..."
sleep 3

echo "🌐 Starting ngrok tunnel..."
ngrok http 8082

# Cleanup on exit
trap "kill $FLASK_PID 2>/dev/null" EXIT
