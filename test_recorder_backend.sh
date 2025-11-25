#!/bin/bash
# Test script for recorder backend

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Recorder Backend Test Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if API key is set
if [ -z "$RECORDER_API_KEY" ]; then
    echo -e "${RED}❌ RECORDER_API_KEY not set!${NC}"
    echo "Set it in .env file or export it:"
    echo "  export RECORDER_API_KEY=your-api-key-here"
    exit 1
fi

API_KEY="$RECORDER_API_KEY"
BASE_URL="http://localhost:8083"
USER_ID=1  # Default test user ID

echo -e "${GREEN}✅ API Key: ${API_KEY:0:10}...${NC}"
echo ""

# Test 1: Health Check
echo -e "${BLUE}Test 1: Health Check${NC}"
curl -s "$BASE_URL/health" | python3 -m json.tool
echo ""
echo ""

# Test 2: Get Recording Status
echo -e "${BLUE}Test 2: Get Recording Status${NC}"
curl -s -H "X-API-Key: $API_KEY" \
     -H "X-User-ID: $USER_ID" \
     "$BASE_URL/api/recorders/status" | python3 -m json.tool
echo ""
echo ""

# Test 3: Start Recording (if strategy ID provided)
if [ -n "$1" ]; then
    STRATEGY_ID=$1
    echo -e "${BLUE}Test 3: Start Recording for Strategy $STRATEGY_ID${NC}"
    curl -s -X POST "$BASE_URL/api/recorders/start/$STRATEGY_ID" \
         -H "X-API-Key: $API_KEY" \
         -H "Content-Type: application/json" \
         -d "{\"user_id\": $USER_ID, \"poll_interval\": 30}" | python3 -m json.tool
    echo ""
    echo ""
    
    # Wait a bit
    echo "Waiting 5 seconds..."
    sleep 5
    echo ""
    
    # Test 4: Get Positions
    echo -e "${BLUE}Test 4: Get Recorded Positions${NC}"
    curl -s -H "X-API-Key: $API_KEY" \
         -H "X-User-ID: $USER_ID" \
         "$BASE_URL/api/recorders/positions/$STRATEGY_ID" | python3 -m json.tool
    echo ""
    echo ""
    
    # Test 5: Stop Recording
    echo -e "${BLUE}Test 5: Stop Recording${NC}"
    read -p "Press Enter to stop recording..."
    curl -s -X POST "$BASE_URL/api/recorders/stop/$STRATEGY_ID" \
         -H "X-API-Key: $API_KEY" \
         -H "X-User-ID: $USER_ID" | python3 -m json.tool
    echo ""
else
    echo -e "${BLUE}Test 3: Start Recording${NC}"
    echo "Usage: $0 <strategy_id>"
    echo "Example: $0 1"
fi

echo ""
echo -e "${GREEN}✅ Tests Complete!${NC}"

