@echo off
REM Airport Lights Detection - Development Server Startup Script (Windows Batch)
REM This script starts both backend and frontend development servers

echo.
echo ================================================================
echo   Airport Lights Detection - Development Server Startup
echo ================================================================
echo.

REM Check if running in project directory
if not exist "README.md" (
    echo [ERROR] Please run this script from the project root directory
    exit /b 1
)

REM Check Docker and start services
echo [INFO] Checking Docker services...
docker ps >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Docker is not running. Please start Docker Desktop.
    echo [INFO] Attempting to start services with Docker Compose...
    docker compose up -d mysql redis
    timeout /t 5 /nobreak >nul
)

REM Start MySQL and Redis if not running
docker ps --filter "name=mysql" --filter "status=running" -q | findstr . >nul
if %errorlevel% neq 0 (
    echo [INFO] Starting MySQL and Redis...
    docker compose up -d mysql redis
    echo [INFO] Waiting for services to be ready...
    timeout /t 10 /nobreak >nul
)

echo [SUCCESS] Docker services are running

REM Start Backend Server
echo [INFO] Starting backend server...
cd backend

REM Check if virtual environment exists
if not exist "venv\" (
    echo [WARNING] Virtual environment not found. Creating one...
    python -m venv venv
    echo [SUCCESS] Virtual environment created
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies if needed
if not exist "venv\.dependencies_installed" (
    echo [INFO] Installing Python dependencies...
    pip install -r requirements.txt >nul 2>&1
    echo. > venv\.dependencies_installed
    echo [SUCCESS] Dependencies installed
)

REM Start backend in new window
echo [INFO] Starting backend on http://localhost:8002...
start "Airport Backend" cmd /c "venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 0.0.0.0 --port 8002"
cd ..

timeout /t 3 /nobreak >nul
echo [SUCCESS] Backend server started

REM Start Frontend Server
echo [INFO] Starting frontend server...
cd frontend

REM Check if node_modules exists
if not exist "node_modules\" (
    echo [WARNING] Node modules not found. Installing...
    call npm install
    echo [SUCCESS] Dependencies installed
)

REM Start frontend in new window
echo [INFO] Starting frontend on http://localhost:3000...
start "Airport Frontend" cmd /c "npm start"
cd ..

timeout /t 3 /nobreak >nul
echo [SUCCESS] Frontend server started

REM Print status
echo.
echo ================================================================
echo               Servers are running!
echo ================================================================
echo.
echo [SUCCESS] Backend API:  http://localhost:8002
echo [SUCCESS] API Docs:     http://localhost:8002/docs
echo [SUCCESS] Frontend:     http://localhost:3000
echo.
echo [INFO] Backend and Frontend are running in separate windows
echo [INFO] Close those windows to stop the servers
echo.

pause
