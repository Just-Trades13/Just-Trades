#!/bin/bash
# Start Just.Trades Frontend Development Server

echo "🎨 Starting Just.Trades Frontend..."
echo ""

cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

echo ""
echo "🌐 Starting Vite dev server..."
echo "   Frontend will be available at http://localhost:5173 (or next available port)"
echo "   Press Ctrl+C to stop"
echo ""

npm run dev

