#!/bin/bash
# Simple test server for React frontend only

cd "$(dirname "$0")"

echo "🚀 Starting Simple Test Server..."
echo ""

# Check if frontend is built
if [ ! -d "frontend/dist" ]; then
    echo "❌ Frontend not built!"
    echo "Building frontend..."
    cd frontend
    npm run build
    cd ..
fi

echo "✅ Frontend built"
echo ""
echo "🌐 Starting server on http://localhost:8080"
echo "📝 Test: http://localhost:8080/dashboard"
echo ""
echo "NOTE: This serves ONLY the frontend."
echo "      Backend APIs won't work - but you can see the UI!"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 test_server.py

