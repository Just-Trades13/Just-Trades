#!/bin/bash
set -e

echo "=========================================="
echo "STARTING JUST-TRADES"
echo "=========================================="

echo "Step 1: Initialize database..."
python init_db.py

echo "Step 2: Starting server..."
exec python ultra_simple_server.py
