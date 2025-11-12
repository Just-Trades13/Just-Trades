#!/bin/bash
echo "🔍 Trade Manager Replica - Quick Status Check"
echo "=============================================="
echo ""

echo "📄 Checking pages..."
PAGES=$(ls frontend/src/pages/*.jsx 2>/dev/null | wc -l | tr -d ' ')
echo "   Found: $PAGES page files"
ls frontend/src/pages/*.jsx 2>/dev/null | sed 's/.*\///' | sed 's/^/   - /'

echo ""
echo "🔗 Checking routes..."
if [ -f frontend/src/App.jsx ]; then
  ROUTES=$(grep -c "path=" frontend/src/App.jsx 2>/dev/null | tr -d ' ')
  echo "   Found: $ROUTES routes"
else
  echo "   ❌ App.jsx not found"
fi

echo ""
echo "📁 Checking handoff tasks..."
COMPLETE_TASKS=$(grep -l "COMPLETE\|✅" HANDOFF*.md 2>/dev/null | wc -l | tr -d ' ')
TOTAL_TASKS=$(ls HANDOFF*.md 2>/dev/null | wc -l | tr -d ' ')
echo "   Completed: $COMPLETE_TASKS/$TOTAL_TASKS tasks"

echo ""
echo "🎨 Checking CSS files..."
CSS_FILES=$(find frontend/src -name "*.css" | wc -l | tr -d ' ')
echo "   Found: $CSS_FILES CSS files"

echo ""
echo "🔨 Backend status..."
if curl -s http://localhost:5000/api/system/health > /dev/null 2>&1; then
  echo "   ✅ Backend is running on port 5000"
else
  echo "   ⚠️  Backend not running (run: python3 app.py)"
fi

echo ""
echo "🌐 Frontend build..."
if [ -d frontend/dist ]; then
  BUILD_FILES=$(ls frontend/dist/assets/*.js 2>/dev/null | wc -l | tr -d ' ')
  if [ "$BUILD_FILES" -gt 0 ]; then
    echo "   ✅ Build exists ($BUILD_FILES JS files)"
  else
    echo "   ⚠️  Build directory empty (run: cd frontend && npm run build)"
  fi
else
  echo "   ⚠️  No build directory (run: cd frontend && npm run build)"
fi

echo ""
echo "=============================================="
echo "✅ Status check complete!"
echo ""
echo "Next steps:"
echo "1. Start backend: python3 app.py"
echo "2. Start frontend: cd frontend && npm run dev"
echo "3. Open: http://localhost:5173"
echo "4. See STATUS_CHECK.md for detailed testing"
