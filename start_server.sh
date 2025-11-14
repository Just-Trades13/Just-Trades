#!/bin/bash
# Start server with environment variables from .env file

cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate

# Load .env file if it exists (contains FINNHUB_API_KEY)
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

python3 ultra_simple_server.py --port 8082

