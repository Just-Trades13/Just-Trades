#!/bin/bash
# ============================================================================
# Start Both Services: Main Server + Trading Engine
# ============================================================================
# 
# Usage: ./start_services.sh
#
# This starts:
#   - Trading Engine (port 8083) - MUST START FIRST
#     Handles: Webhooks, TP/SL, Drawdown, Position Tracking
#
#   - Main Server (port 8082)
#     Handles: OAuth, Copy Trading, Dashboard UI, Account Management
#     Proxies webhooks to Trading Engine
#
# Both share the same database (just_trades.db)
# ============================================================================

cd "$(dirname "$0")"

echo "=============================================="
echo "🚀 Starting Just.Trades Services"
echo "=============================================="
echo ""
echo "Architecture:"
echo "  Trading Engine (8083) ← Webhooks, TP/SL, Drawdown"
echo "  Main Server (8082)    ← OAuth, Dashboard, Copy Trading"
echo "  Shared DB             ← just_trades.db"
echo "=============================================="

# Kill any existing services
echo ""
echo "Stopping any existing services..."
pkill -f "python.*ultra_simple_server" 2>/dev/null || true
pkill -f "python.*recorder_service" 2>/dev/null || true
pkill -f "python.*insider_service" 2>/dev/null || true
sleep 2

# ============================================================================
# IMPORTANT: Trading Engine MUST start FIRST
# The Main Server proxies webhooks to it
# ============================================================================

# Start Trading Engine first
echo ""
echo "1️⃣  Starting Trading Engine (port 8083)..."
nohup python3 recorder_service.py > /tmp/trading_engine.log 2>&1 &
TRADING_ENGINE_PID=$!
echo "    PID: $TRADING_ENGINE_PID"

# Wait for Trading Engine to be ready
echo "    Waiting for Trading Engine to initialize..."
sleep 3

# Verify Trading Engine is running
if curl -s http://localhost:8083/health > /dev/null 2>&1; then
    echo "    ✅ Trading Engine is healthy"
else
    echo "    ⚠️  Trading Engine may not be ready yet"
fi

# Start Insider Service second
echo ""
echo "2️⃣  Starting Insider Service (port 8084)..."
nohup python3 insider_service.py > /tmp/insider_service.log 2>&1 &
INSIDER_PID=$!
echo "    PID: $INSIDER_PID"

# Wait for Insider Service to initialize
echo "    Waiting for Insider Service to initialize..."
sleep 2

# Verify Insider Service is running
if curl -s http://localhost:8084/status > /dev/null 2>&1; then
    echo "    ✅ Insider Service is healthy"
else
    echo "    ⚠️  Insider Service may not be ready yet"
fi

# Start Main Server third
echo ""
echo "3️⃣  Starting Main Server (port 8082)..."
nohup python3 ultra_simple_server.py > /tmp/main_server.log 2>&1 &
MAIN_PID=$!
echo "    PID: $MAIN_PID"

# Wait for Main Server to be ready
sleep 4

# Final status check
echo ""
echo "=============================================="
echo "Checking Services..."
echo "=============================================="

# Check Trading Engine
TRADING_ENGINE_STATUS="❌ NOT RUNNING"
if ps -p $TRADING_ENGINE_PID > /dev/null 2>&1; then
    if curl -s http://localhost:8083/health > /dev/null 2>&1; then
        TRADING_ENGINE_STATUS="✅ HEALTHY"
    else
        TRADING_ENGINE_STATUS="⚠️  RUNNING (not responding)"
    fi
fi

# Check Insider Service
INSIDER_STATUS="❌ NOT RUNNING"
if ps -p $INSIDER_PID > /dev/null 2>&1; then
    if curl -s http://localhost:8084/status > /dev/null 2>&1; then
        INSIDER_STATUS="✅ HEALTHY"
    else
        INSIDER_STATUS="⚠️  RUNNING (not responding)"
    fi
fi

# Check Main Server  
MAIN_STATUS="❌ NOT RUNNING"
if ps -p $MAIN_PID > /dev/null 2>&1; then
    if curl -s http://localhost:8082/ > /dev/null 2>&1; then
        MAIN_STATUS="✅ HEALTHY"
    else
        MAIN_STATUS="⚠️  RUNNING (not responding)"
    fi
fi

echo ""
echo "Trading Engine (8083):  $TRADING_ENGINE_STATUS"
echo "Insider Service (8084): $INSIDER_STATUS"
echo "Main Server (8082):     $MAIN_STATUS"

echo ""
echo "=============================================="
echo "🎉 Services Started!"
echo "=============================================="
echo ""
echo "URLs:"
echo "  Dashboard:        http://localhost:8082/dashboard"
echo "  Recorders:        http://localhost:8082/recorders"
echo "  Insider Signals:  http://localhost:8082/insider-signals"
echo "  Trading Engine:   http://localhost:8083/status"
echo "  Insider Service:  http://localhost:8084/status"
echo ""
echo "Test Webhook (via proxy):"
echo "  curl -X POST http://localhost:8082/webhook/YOUR_TOKEN \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"action\":\"buy\",\"ticker\":\"MNQ1!\",\"price\":\"21500\"}'"
echo ""
echo "Logs:"
echo "  Trading Engine:   tail -f /tmp/trading_engine.log"
echo "  Insider Service:  tail -f /tmp/insider_service.log"
echo "  Main Server:      tail -f /tmp/main_server.log"
echo ""
echo "Health Checks:"
echo "  curl http://localhost:8083/health  # Trading Engine"
echo "  curl http://localhost:8083/status  # Trading Engine Status"
echo ""
