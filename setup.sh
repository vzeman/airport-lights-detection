#!/bin/bash

# Local Development Setup Script
# This script sets up the project to run backend and frontend locally with MySQL in Docker

set -e

echo "=== Airport Lights Detection - Local Development Setup ==="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Stop any running Docker containers
echo -e "${YELLOW}Step 1: Stopping existing Docker containers...${NC}"
docker compose down 2>/dev/null || true
echo -e "${GREEN}✓ Docker containers stopped${NC}"
echo ""

# Step 2: Start MySQL in Docker
echo -e "${YELLOW}Step 2: Starting MySQL in Docker...${NC}"
docker compose -f docker-compose-db-only.yml up -d
echo "Waiting for MySQL to be ready..."
sleep 5
echo -e "${GREEN}✓ MySQL is running on localhost:3306${NC}"
echo ""

# Step 3: Setup Backend
echo -e "${YELLOW}Step 3: Setting up Backend...${NC}"
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create/update .env file
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << 'EOF'
# Database
DATABASE_URL=mysql+aiomysql://airport_user:airport_pass@localhost:3307/airport_lights

# AWS S3 (use your credentials)
AWS_ACCESS_KEY_ID=your_aws_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_here
AWS_S3_BUCKET=your_bucket_name
AWS_REGION=us-east-1

# Google OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Security
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
EOF
    echo -e "${GREEN}✓ Created .env file - PLEASE UPDATE AWS CREDENTIALS!${NC}"
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Run migrations
echo "Running database migrations..."
alembic upgrade head

echo -e "${GREEN}✓ Backend setup complete${NC}"
cd ..
echo ""

# Step 4: Setup Frontend
echo -e "${YELLOW}Step 4: Setting up Frontend...${NC}"
cd frontend

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    npm install
fi

# Create/update .env file
if [ ! -f ".env" ]; then
    echo "Creating frontend .env file..."
    cat > .env << 'EOF'
VITE_API_URL=http://localhost:8001
EOF
    echo -e "${GREEN}✓ Created frontend .env file${NC}"
else
    echo -e "${GREEN}✓ Frontend .env file already exists${NC}"
fi

echo -e "${GREEN}✓ Frontend setup complete${NC}"
cd ..
echo ""

# Final instructions
echo "=== Setup Complete! ==="
echo ""
echo "To start the application:"
echo ""
echo "1. Start Backend (in terminal 1):"
echo "   ${GREEN}cd backend${NC}"
echo "   ${GREEN}source venv/bin/activate${NC}"
echo "   ${GREEN}uvicorn app.main:app --reload --host 0.0.0.0 --port 8001${NC}"
echo ""
echo "2. Start Frontend (in terminal 2):"
echo "   ${GREEN}cd frontend${NC}"
echo "   ${GREEN}npm run dev${NC}"
echo ""
echo "3. Access the application:"
echo "   Frontend: ${GREEN}http://localhost:5173${NC} (or port shown by Vite)"
echo "   Backend API: ${GREEN}http://localhost:8001${NC}"
echo "   API Docs: ${GREEN}http://localhost:8001/docs${NC}"
echo ""
echo "4. To stop MySQL:"
echo "   ${GREEN}docker compose -f docker-compose-db-only.yml down${NC}"
echo ""
echo "⚠️  IMPORTANT: Update AWS credentials in backend/.env before processing videos!"
echo ""
