#!/bin/bash
# ============================================================================
# Start Both Services: Main Server + Recorder Service
# ============================================================================
# 
# Usage: ./start_services.sh
#
# This starts:
#   - ultra_simple_server.py on port 8082 (main server)
#   - recorder_service.py on port 8083 (recording engine)
#
# Both share the same database (just_trades.db)
# ============================================================================

cd "$(dirname "$0")"

echo "=============================================="
echo "🚀 Starting Just.Trades Services"
echo "=============================================="

# Kill any existing services
echo "Stopping any existing services..."
pkill -f "python.*ultra_simple_server" 2>/dev/null || true
pkill -f "python.*recorder_service" 2>/dev/null || true
sleep 1

# Start main server
echo ""
echo "Starting main server (port 8082)..."
nohup python3 ultra_simple_server.py > /tmp/main_server.log 2>&1 &
MAIN_PID=$!
echo "  Main server PID: $MAIN_PID"

# Start recorder service
echo ""
echo "Starting recorder service (port 8083)..."
nohup python3 recorder_service.py > /tmp/recorder_service.log 2>&1 &
RECORDER_PID=$!
echo "  Recorder service PID: $RECORDER_PID"

# Wait a moment for services to start
sleep 3

# Check if services are running
echo ""
echo "Checking services..."

if ps -p $MAIN_PID > /dev/null 2>&1; then
    echo "  ✅ Main server running (PID: $MAIN_PID)"
else
    echo "  ❌ Main server failed to start!"
    echo "  Check: tail /tmp/main_server.log"
fi

if ps -p $RECORDER_PID > /dev/null 2>&1; then
    echo "  ✅ Recorder service running (PID: $RECORDER_PID)"
else
    echo "  ❌ Recorder service failed to start!"
    echo "  Check: tail /tmp/recorder_service.log"
fi

echo ""
echo "=============================================="
echo "Services Started!"
echo "=============================================="
echo ""
echo "Main Server:     http://localhost:8082"
echo "Recorder Service: http://localhost:8083"
echo ""
echo "Logs:"
echo "  Main:     tail -f /tmp/main_server.log"
echo "  Recorder: tail -f /tmp/recorder_service.log"
echo ""
echo "Health Checks:"
echo "  curl http://localhost:8082/health"
echo "  curl http://localhost:8083/health"
echo ""
