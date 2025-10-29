#!/bin/bash

# Stop Airport Lights Detection - Local Development

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}=== Stopping Airport Lights Detection ===${NC}"
echo ""

# Stop Backend
if [ -f backend.pid ]; then
    BACKEND_PID=$(cat backend.pid)
    echo "Stopping Backend (PID: $BACKEND_PID)..."
    kill $BACKEND_PID 2>/dev/null || echo "Backend already stopped"
    rm backend.pid
    echo -e "${GREEN}✓ Backend stopped${NC}"
else
    echo "Backend PID file not found"
fi
echo ""

# Stop Frontend
if [ -f frontend.pid ]; then
    FRONTEND_PID=$(cat frontend.pid)
    echo "Stopping Frontend (PID: $FRONTEND_PID)..."
    kill $FRONTEND_PID 2>/dev/null || echo "Frontend already stopped"
    rm frontend.pid
    echo -e "${GREEN}✓ Frontend stopped${NC}"
else
    echo "Frontend PID file not found"
fi
echo ""

# Ask about MySQL
echo -e "${YELLOW}Keep MySQL running? (y/n)${NC}"
read -r response
if [[ "$response" =~ ^([nN][oO]|[nN])$ ]]; then
    echo "Stopping MySQL..."
    docker compose stop mysql
    echo -e "${GREEN}✓ MySQL stopped${NC}"
else
    echo -e "${GREEN}✓ MySQL still running${NC}"
fi

echo ""
echo -e "${GREEN}=== Cleanup complete ===${NC}"
echo ""
