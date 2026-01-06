#!/bin/bash
set -e

echo "=========================================="
echo "STARTING JUST-TRADES"
echo "VERSION: 2026-01-06-datetime-fix-v2"
echo "=========================================="
echo "Time: $(date)"
echo "PORT: $PORT"
echo "DATABASE_URL set: $(if [ -n \"$DATABASE_URL\" ]; then echo 'yes'; else echo 'no'; fi)"

echo ""
echo "Step 1: Initialize database (timeout 15s)..."
timeout 15 python init_db.py || echo "⚠️ init_db timed out or failed - continuing anyway"

echo ""
echo "Step 2: Starting server on port $PORT..."
echo "Time: $(date)"
exec python ultra_simple_server.py
