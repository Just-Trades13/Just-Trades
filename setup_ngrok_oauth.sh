#!/bin/bash
# Setup ngrok for OAuth (Tradovate doesn't accept localhost)

echo "🔧 Setting up ngrok for OAuth..."
echo ""

# Start ngrok in background
echo "Starting ngrok..."
ngrok http 8082 --log=stdout > ngrok.log 2>&1 &
NGROK_PID=$!

# Wait for ngrok to start
sleep 5

# Get ngrok URL
echo "Getting ngrok URL..."
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

echo "✅ ngrok is running!"
echo ""
echo "Public URL: $NGROK_URL"
echo ""
echo "Next steps:"
echo "1. Update redirect URI in Tradovate OAuth app:"
echo "   - Log into Tradovate"
echo "   - Go to Application Settings → API Access → OAuth Registration"
echo "   - Edit OAuth app (Client ID: 8552)"
echo "   - Change redirect URI to: $NGROK_URL"
echo "   - Save"
echo ""
echo "2. Test OAuth flow:"
echo "   http://localhost:8082/api/accounts/4/connect"
echo ""
echo "3. You should now see OAuth authorization page!"
echo ""
echo "ngrok is running in background (PID: $NGROK_PID)"
echo "To stop: kill $NGROK_PID"
echo "To view logs: tail -f ngrok.log"

# Save ngrok URL to file
echo "$NGROK_URL" > ngrok_url.txt
echo ""
echo "✅ ngrok URL saved to: ngrok_url.txt"

