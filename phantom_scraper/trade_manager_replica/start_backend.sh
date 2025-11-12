#!/bin/bash
# Start Just.Trades Backend Server

echo "🚀 Starting Just.Trades Backend..."
echo ""

# Create test user if it doesn't exist
python3 setup_test_user.py

echo ""
echo "📡 Starting Flask server on http://localhost:5000"
echo "   Press Ctrl+C to stop"
echo ""

python3 app.py

