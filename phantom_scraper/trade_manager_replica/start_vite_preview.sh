#!/bin/bash
# Use Vite's built-in preview server (better SPA support)

cd "$(dirname "$0")/frontend"

echo "🚀 Starting Vite Preview Server..."
echo ""
echo "This uses Vite's preview mode to test the production build"
echo ""
echo "Building frontend first..."
npm run build

echo ""
echo "✅ Starting preview server..."
echo "🌐 Will be available at: http://localhost:4173"
echo ""
echo "Press Ctrl+C to stop"
echo ""

npm run preview

