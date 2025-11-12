#!/bin/bash
# Quick status check script

echo "🔍 Checking Trade Manager Replica Status..."
echo ""

# Check backend
echo "📡 Backend Status:"
if lsof -i :5001 > /dev/null 2>&1; then
    echo "   ✅ Backend running on port 5001"
else
    echo "   ❌ Backend NOT running"
    echo "   Run: cd '/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica' && python3 app.py"
fi
echo ""

# Check frontend
echo "🎨 Frontend Status:"
if lsof -i :5173 > /dev/null 2>&1; then
    echo "   ✅ Frontend running on port 5173"
else
    echo "   ❌ Frontend NOT running"
    echo "   Run: cd '/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend' && npm run dev"
fi
echo ""

# Check database
echo "💾 Database Status:"
if [ -f "trade_manager.db" ]; then
    echo "   ✅ Database exists"
    SIZE=$(du -h trade_manager.db | cut -f1)
    echo "   Size: $SIZE"
else
    echo "   ❌ Database NOT found"
    echo "   Run: python3 SETUP_TEST_USER.py"
fi
echo ""

# Check frontend build
echo "📦 Frontend Build:"
if [ -d "frontend/dist" ]; then
    echo "   ✅ Production build exists"
else
    echo "   ⚠️  No production build (use dev mode: npm run dev)"
fi
echo ""

echo "✅ Status check complete!"
echo ""
echo "📋 Next Steps:"
echo "   1. Open browser console (F12)"
echo "   2. Check for errors"
echo "   3. Share errors with me for fixes"

