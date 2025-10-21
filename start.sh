#!/bin/bash

# Airport Lights Detection - Docker Startup Script
# This script starts all services using Docker Compose

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Print header
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Airport Lights Detection - Docker Services Startup      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if running in project directory
if [ ! -f "README.md" ] || [ ! -f "docker-compose.yml" ]; then
    print_error "Please run this script from the project root directory"
    exit 1
fi

# Check if Docker is running
print_info "Checking Docker status..."
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running!"
    echo ""
    print_warning "Please start Docker Desktop and wait for it to fully start"
    print_info "You'll see a whale icon in your menu bar when it's ready"
    echo ""
    print_info "On macOS, you can run: open -a Docker"
    echo ""
    print_info "After Docker is running, run this script again"
    exit 1
fi

print_success "Docker is running"
echo ""

# Start all services
print_info "Starting all services with Docker Compose..."
docker compose up -d

echo ""
print_info "Waiting for services to start..."
sleep 5

echo ""
print_info "Checking service status..."
echo ""

# Check MySQL
print_info "Checking MySQL..."
for i in {1..30}; do
    if docker exec airport_mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
        print_success "MySQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        print_error "MySQL failed to start within 30 seconds"
        print_info "Check logs: docker logs airport_mysql"
        exit 1
    fi
    echo -n "."
    sleep 1
done
echo ""

# Check Redis
print_info "Checking Redis..."
if docker exec airport_redis redis-cli ping > /dev/null 2>&1; then
    print_success "Redis is ready!"
else
    print_warning "Redis may not be ready yet"
fi

echo ""

# Check Backend
print_info "Checking Backend..."
for i in {1..20}; do
    if curl -s -m 2 http://localhost:8001/health > /dev/null 2>&1; then
        print_success "Backend is ready!"
        break
    fi
    if [ $i -eq 20 ]; then
        print_warning "Backend is not responding yet (may still be starting)"
        print_info "Check logs: docker logs -f airport_backend"
    fi
    echo -n "."
    sleep 1
done
echo ""

# Check Frontend
print_info "Checking Frontend..."
if docker ps | grep -q "airport_frontend.*Up"; then
    print_success "Frontend container is running"
else
    print_warning "Frontend container may have issues"
    print_info "Check logs: docker logs -f airport_frontend"
fi

echo ""

# Print status
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              🚀 Docker Services Status                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Show all containers
docker compose ps

echo ""
echo "─────────────────────────────────────────────────────────────"
echo ""

print_success "Access your application at:"
echo ""
echo "  Frontend:     http://localhost:3001"
echo "  Backend API:  http://localhost:8001"
echo "  API Docs:     http://localhost:8001/docs"
echo "  Flower:       http://localhost:5555"
echo ""
echo "  MySQL:        localhost:3307"
echo "  Redis:        localhost:6379"
echo ""

print_info "Default login:"
echo "  Username: admin"
echo "  Password: admin123"
echo ""

print_info "Useful commands:"
echo "  View all logs:       docker compose logs -f"
echo "  View backend logs:   docker logs -f airport_backend"
echo "  View frontend logs:  docker logs -f airport_frontend"
echo "  Stop all services:   docker compose down"
echo "  Restart a service:   docker compose restart backend"
echo "  Check status:        ./check-status.sh"
echo ""

print_warning "To stop all services, run: docker compose down"
echo ""
