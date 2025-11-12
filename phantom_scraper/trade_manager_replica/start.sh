#!/bin/bash
# Simple startup script for Just.Trades

echo "🚀 Starting Just.Trades..."
echo ""

# Check if frontend is built
if [ ! -d "frontend/dist" ]; then
    echo "📦 Building frontend..."
    cd frontend
    npm run build
    cd ..
    echo "✅ Frontend built!"
    echo ""
fi

# Start Flask server
echo "🌐 Starting Flask server on port 5001..."
echo "📱 Open: http://localhost:5001"
echo ""
python3 app.py

