#!/bin/bash
# Run Signal-Based Tracking Accuracy Test
# This script sets up and runs the long-term accuracy test

set -e

echo "🧪 Signal-Based Tracking Accuracy Test"
echo "========================================"
echo ""

# Check if server is running
if ! pgrep -f "recorder_service.py" > /dev/null; then
    echo "⚠️  Server is not running"
    echo "   Starting server in test mode..."
    echo ""
    
    # Start server in background with test mode
    export SIGNAL_BASED_TEST=true
    nohup python3 recorder_service.py > /tmp/recorder_test.log 2>&1 &
    SERVER_PID=$!
    echo "   Server started (PID: $SERVER_PID)"
    echo "   Waiting for server to initialize..."
    sleep 5
    
    # Check if server started successfully
    if ! kill -0 $SERVER_PID 2>/dev/null; then
        echo "❌ Server failed to start. Check /tmp/recorder_test.log"
        exit 1
    fi
else
    echo "✅ Server is already running"
    SERVER_PID=$(pgrep -f "recorder_service.py" | head -1)
    echo "   PID: $SERVER_PID"
    echo ""
    echo "⚠️  Make sure SIGNAL_BASED_TEST=true is set for the running server"
    echo "   If not, restart with: SIGNAL_BASED_TEST=true python3 recorder_service.py"
    echo ""
fi

# Setup test environment
echo "📋 Setting up test environment..."
python3 setup_test_environment.py

if [ $? -ne 0 ]; then
    echo "❌ Failed to setup test environment"
    exit 1
fi

echo ""
echo "🧪 Starting long-term accuracy test..."
echo "   This will run for 60 minutes (or until interrupted)"
echo "   Press Ctrl+C to stop early"
echo ""

# Run the test
python3 test_long_term_accuracy.py

# Cleanup
if [ ! -z "$SERVER_PID" ] && kill -0 $SERVER_PID 2>/dev/null; then
    echo ""
    echo "⚠️  Test server is still running (PID: $SERVER_PID)"
    echo "   To stop: kill $SERVER_PID"
fi
