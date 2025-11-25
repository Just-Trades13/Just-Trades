#!/bin/bash
# Start Recorder Backend Service
# This can be run in a new terminal/context window

cd "/Users/mylesjadwin/Trading Projects"
source venv/bin/activate

# Load .env file if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Initialize database if needed
python3 recorder_backend.py --init-db --port 8083

# Start the recorder backend service
python3 recorder_backend.py --port 8083

