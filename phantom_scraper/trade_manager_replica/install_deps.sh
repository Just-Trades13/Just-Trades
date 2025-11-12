#!/bin/bash
# Install dependencies for Just.Trades

echo "📦 Installing Backend Dependencies..."
pip3 install --break-system-packages -r requirements.txt

echo ""
echo "📦 Installing Frontend Dependencies..."
cd frontend
npm install
cd ..

echo ""
echo "✅ Dependencies installed!"
echo ""
echo "Next steps:"
echo "1. Run: python3 setup_test_user.py (creates test user)"
echo "2. Run: python3 app.py (starts backend)"
echo "3. In another terminal: cd frontend && npm run dev (starts frontend)"

