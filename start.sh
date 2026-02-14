#!/bin/bash
set -e

echo "=========================================="
echo "STARTING JUST-TRADES"
echo "VERSION: 2026-02-13-architecture-split"
echo "=========================================="
echo "Time: $(date)"
echo "PORT: $PORT"
echo "DATABASE_URL set: $(if [ -n "$DATABASE_URL" ]; then echo 'yes'; else echo 'no'; fi)"
echo "EXTERNAL_TRADING_ENGINE: ${EXTERNAL_TRADING_ENGINE:-not set}"

echo ""
echo "Step 1: Initialize database (timeout 15s)..."
timeout 15 python init_db.py || echo "⚠️ init_db timed out or failed - continuing anyway"

# Step 2: Start trading engine in background (if enabled)
if [ "$EXTERNAL_TRADING_ENGINE" = "1" ]; then
    echo ""
    echo "Step 2: Starting trading engine (background process)..."
    python trading_engine.py &
    TRADING_PID=$!
    echo "Trading engine PID: $TRADING_PID"
    echo "Time: $(date)"

    # Give it a moment to connect to Redis
    sleep 2

    # Verify it's still running
    if kill -0 $TRADING_PID 2>/dev/null; then
        echo "✅ Trading engine is running"
    else
        echo "❌ Trading engine died! Check logs above."
        echo "Continuing with web server anyway (broker tasks will queue in Redis)..."
    fi
else
    echo ""
    echo "Step 2: Skipping trading engine (single process mode)"
fi

echo ""
echo "Step 3: Starting web server on port $PORT..."
echo "Time: $(date)"
exec python ultra_simple_server.py
