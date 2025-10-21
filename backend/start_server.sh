#!/bin/bash

# Airport Management Backend Server Startup Script
echo "🚀 Starting Airport Management Backend Server..."

# Check if virtual environment exists
if [ ! -d "../venv_lights" ]; then
    echo "❌ Virtual environment not found. Please create it first:"
    echo "   python -m venv ../venv_lights"
    echo "   source ../venv_lights/bin/activate"
    echo "   pip install -r requirements-sqlite.txt"
    exit 1
fi

# Activate virtual environment
source ../venv_lights/bin/activate

# Check if required packages are installed
echo "🔍 Checking dependencies..."
python -c "import fastapi, uvicorn, sqlalchemy, aiosqlite; print('✅ Core dependencies installed')" 2>/dev/null || {
    echo "❌ Missing dependencies. Installing..."
    pip install fastapi uvicorn sqlalchemy aiosqlite pydantic python-dotenv \
                "python-jose[cryptography]" "passlib[bcrypt]" python-multipart \
                alembic pydantic-settings email-validator httpx greenlet
}

# Check if database exists
if [ ! -f "airport_mgmt.db" ]; then
    echo "⚠️  Database not found. You may need to initialize it:"
    echo "   python init_db.py"
fi

# Start the server
echo "✅ Starting server on http://localhost:8002"
echo "📋 Admin credentials:"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "🔗 Important endpoints:"
echo "   Health check: http://localhost:8002/health"
echo "   API docs: http://localhost:8002/docs"
echo "   Login: http://localhost:8002/api/v1/auth/login"
echo ""
echo "Press Ctrl+C to stop the server"
echo "----------------------------------------"

python -m uvicorn app.main:app --reload --port 8002 --host 0.0.0.0