#!/bin/bash
# Start server with Finnhub API key

cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate

export FINNHUB_API_KEY="cuaspapr01qof06jal0gcuaspapr01qof06jal10"

python3 ultra_simple_server.py --port 8082

