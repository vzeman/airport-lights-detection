#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║        Airport Lights Detection - System Status           ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check Docker
echo -n "Checking Docker Desktop... "
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
    echo -e "${YELLOW}   Please start Docker Desktop${NC}"
    echo ""
    exit 1
fi

# Check MySQL
echo -n "Checking MySQL... "
MYSQL_RUNNING=$(docker ps --filter "name=mysql" --filter "status=running" -q)
if [ -n "$MYSQL_RUNNING" ]; then
    if docker exec airport_mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
        echo -e "${GREEN}✓ Running and Ready${NC}"
    else
        echo -e "${YELLOW}⚠ Running but not ready${NC}"
    fi
else
    echo -e "${RED}✗ Not Running${NC}"
    echo -e "${YELLOW}   Run: docker compose up -d mysql${NC}"
fi

# Check Redis
echo -n "Checking Redis... "
REDIS_RUNNING=$(docker ps --filter "name=redis" --filter "status=running" -q)
if [ -n "$REDIS_RUNNING" ]; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
    echo -e "${YELLOW}   Run: docker compose up -d redis${NC}"
fi

# Check Backend
echo -n "Checking Backend (port 8002)... "
if lsof -i :8002 -sTCP:LISTEN > /dev/null 2>&1; then
    # Check if it's actually responding
    HEALTH=$(curl -s -m 2 http://localhost:8002/health 2>/dev/null)
    if echo "$HEALTH" | grep -q "healthy"; then
        echo -e "${GREEN}✓ Running and Healthy${NC}"
    else
        echo -e "${YELLOW}⚠ Running but not responding${NC}"
    fi
else
    echo -e "${RED}✗ Not Running${NC}"
fi

# Check Frontend
echo -n "Checking Frontend (port 3000)... "
if lsof -i :3000 -sTCP:LISTEN > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not Running${NC}"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo ""

# Port usage
echo "Port Usage:"
echo -n "  Port 8002 (Backend): "
if lsof -i :8002 > /dev/null 2>&1; then
    PID=$(lsof -ti :8002)
    echo -e "${GREEN}In use by PID $PID${NC}"
else
    echo -e "${BLUE}Available${NC}"
fi

echo -n "  Port 3000 (Frontend): "
if lsof -i :3000 > /dev/null 2>&1; then
    PID=$(lsof -ti :3000)
    echo -e "${GREEN}In use by PID $PID${NC}"
else
    echo -e "${BLUE}Available${NC}"
fi

echo -n "  Port 3307 (MySQL): "
if lsof -i :3307 > /dev/null 2>&1; then
    echo -e "${GREEN}In use${NC}"
else
    echo -e "${BLUE}Available${NC}"
fi

echo -n "  Port 6379 (Redis): "
if lsof -i :6379 > /dev/null 2>&1; then
    echo -e "${GREEN}In use${NC}"
else
    echo -e "${BLUE}Available${NC}"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo ""

# Test backend connectivity
if lsof -i :8002 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "Testing Backend API..."
    echo -n "  Health endpoint: "
    if curl -s -m 2 http://localhost:8002/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Responding${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
        echo -e "${YELLOW}   Backend may still be starting up${NC}"
    fi

    echo -n "  Root endpoint: "
    if curl -s -m 2 http://localhost:8002/ > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Responding${NC}"
    else
        echo -e "${RED}✗ Not responding${NC}"
    fi
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo ""

# Summary
ALL_GOOD=true

if ! docker info > /dev/null 2>&1; then
    ALL_GOOD=false
fi

if [ -z "$MYSQL_RUNNING" ] || [ -z "$REDIS_RUNNING" ]; then
    ALL_GOOD=false
fi

if $ALL_GOOD; then
    echo -e "${GREEN}✓ System is ready!${NC}"
    echo ""
    echo "Access your application at:"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend:  http://localhost:8002"
    echo "  API Docs: http://localhost:8002/docs"
    echo ""
    echo "Default login: admin / admin123"
else
    echo -e "${YELLOW}⚠ System is not ready${NC}"
    echo ""
    echo "Next steps:"
    if ! docker info > /dev/null 2>&1; then
        echo "  1. Start Docker Desktop"
        echo "     macOS: open -a Docker"
    fi
    if [ -z "$MYSQL_RUNNING" ] || [ -z "$REDIS_RUNNING" ]; then
        echo "  2. Start database services"
        echo "     docker compose up -d mysql redis"
    fi
    echo "  3. Run the startup script"
    echo "     ./start.sh"
fi

echo ""
