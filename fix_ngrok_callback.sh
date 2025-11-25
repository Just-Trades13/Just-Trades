#!/bin/bash
# Fix ngrok callback issue

echo "🔧 Fixing ngrok Callback Issue"
echo ""

# Check if ngrok is running
if ! pgrep -x ngrok > /dev/null; then
    echo "❌ ngrok is not running!"
    echo ""
    echo "Starting ngrok..."
    ngrok http 8082 --log=stdout > ngrok.log 2>&1 &
    sleep 5
    echo "✅ ngrok started"
else
    echo "✅ ngrok is running"
fi

# Get current ngrok URL
echo ""
echo "Getting current ngrok URL..."
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    for tunnel in tunnels:
        if tunnel.get('proto') == 'https':
            print(tunnel.get('public_url', ''))
            break
except:
    pass
" 2>/dev/null)

if [ -z "$NGROK_URL" ]; then
    echo "❌ Could not get ngrok URL"
    echo "Check ngrok.log for errors"
    exit 1
fi

echo "✅ Current ngrok URL: $NGROK_URL"
echo ""

# Update ngrok URL file
echo "$NGROK_URL" > ngrok_url.txt
echo "✅ Updated ngrok_url.txt"

# Show callback URL
CALLBACK_URL="${NGROK_URL}/auth/tradovate/callback"
echo ""
echo "Callback URL: $CALLBACK_URL"
echo ""

# Test callback route
echo "Testing callback route..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8082/auth/tradovate/callback")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "400" ]; then
    echo "✅ Callback route is accessible (HTTP $HTTP_CODE)"
else
    echo "⚠️  Callback route returned HTTP $HTTP_CODE"
fi

echo ""
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo ""
echo "1. Update OAuth app redirect URI in Tradovate:"
echo "   - Go to: Application Settings → API Access → OAuth Registration"
echo "   - Edit your OAuth app"
echo "   - Change redirect URI to:"
echo "     $CALLBACK_URL"
echo "   - Save"
echo ""
echo "2. Test OAuth flow again:"
echo "   - Visit: http://localhost:8082/api/accounts/4/connect"
echo "   - Log in and authorize"
echo "   - Should redirect to: $CALLBACK_URL"
echo ""
echo "3. Verify token was stored:"
echo "   python3 verify_oauth_success.py"
echo ""

