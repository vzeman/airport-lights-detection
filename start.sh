#!/bin/bash

# Start Airport Lights Detection - Local Development
# MySQL in Docker, Backend & Frontend locally

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}=== Starting Airport Lights Detection ===${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Step 1: Start MySQL in Docker
echo -e "${YELLOW}Starting MySQL...${NC}"
if ! docker ps | grep -q airport_mysql; then
    docker compose up -d mysql
    echo "Waiting for MySQL to be ready..."
    sleep 5
fi
echo -e "${GREEN}✓ MySQL running on localhost:3307${NC}"
echo ""

# Step 2: Start Backend
echo -e "${YELLOW}Starting Backend...${NC}"
cd backend

if [ ! -d "venv" ]; then
    echo -e "${RED}Virtual environment not found. Run ./local-dev-setup.sh first${NC}"
    exit 1
fi

# Activate venv and start backend
source venv/bin/activate
echo "Starting FastAPI server on port 8001..."

# Start with tee to log to both file and console
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001 2>&1 | tee ../backend.log &
BACKEND_PID=$!
echo $BACKEND_PID > ../backend.pid

echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"
echo "  Logs: tail -f backend.log"
cd ..
echo ""

sleep 3

# Step 3: Start Frontend
echo -e "${YELLOW}Starting Frontend...${NC}"
cd frontend

if [ ! -d "node_modules" ]; then
    echo -e "${RED}node_modules not found. Run ./local-dev-setup.sh first${NC}"
    exit 1
fi

echo "Starting React dev server..."
nohup npm start > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > ../frontend.pid

echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
echo "  Logs: tail -f frontend.log"
cd ..
echo ""

sleep 3

# Final status
echo -e "${GREEN}=== All components started! ===${NC}"
echo ""
echo "Access Points:"
echo "  Frontend:  ${GREEN}http://localhost:5173${NC}"
echo "  Backend:   ${GREEN}http://localhost:8001${NC}"
echo "  API Docs:  ${GREEN}http://localhost:8001/docs${NC}"
echo "  MySQL:     ${GREEN}localhost:3307${NC}"
echo ""
echo "View Logs:"
echo "  Backend:  ${GREEN}tail -f backend.log${NC}"
echo "  Frontend: ${GREEN}tail -f frontend.log${NC}"
echo ""
echo "Stop All:"
echo "  ${GREEN}./stop.sh${NC}"
echo ""
