# Airport Lights Detection - Development Server Startup Script (Windows)
# This script starts both backend and frontend development servers

# Requires -Version 5.1

# Function to print colored output
function Write-Info {
    param([string]$Message)
    Write-Host "ℹ " -ForegroundColor Blue -NoNewline
    Write-Host $Message
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "✗ " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

# Function to cleanup background processes on exit
function Cleanup {
    Write-Info "Shutting down servers..."

    # Kill backend process if running
    if ($null -ne $script:BackendProcess -and !$script:BackendProcess.HasExited) {
        Write-Info "Stopping backend server..."
        Stop-Process -Id $script:BackendProcess.Id -Force
    }

    # Kill frontend process if running
    if ($null -ne $script:FrontendProcess -and !$script:FrontendProcess.HasExited) {
        Write-Info "Stopping frontend server..."
        Stop-Process -Id $script:FrontendProcess.Id -Force
    }

    Write-Success "Servers stopped"
}

# Set up trap to call cleanup on script exit
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup }

# Print header
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗"
Write-Host "║  Airport Lights Detection - Development Server Startup    ║"
Write-Host "╚════════════════════════════════════════════════════════════╝"
Write-Host ""

# Check if running in project directory
if (!(Test-Path "README.md") -or !(Test-Path "backend") -or !(Test-Path "frontend")) {
    Write-Error-Custom "Please run this script from the project root directory"
    exit 1
}

# Check if Docker Desktop is running
Write-Info "Checking Docker status..."
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker not running"
    }
} catch {
    Write-Warning "Docker is not running. Please start Docker Desktop and try again."
    Write-Info "Starting required services with Docker Compose..."
    docker compose up -d mysql redis
    Start-Sleep -Seconds 5
}

# Check if MySQL and Redis are running
Write-Info "Checking required services..."
$mysqlRunning = docker ps --filter "name=mysql" --filter "status=running" -q
$redisRunning = docker ps --filter "name=redis" --filter "status=running" -q

if ([string]::IsNullOrEmpty($mysqlRunning) -or [string]::IsNullOrEmpty($redisRunning)) {
    Write-Warning "Required services not running. Starting MySQL and Redis..."
    docker compose up -d mysql redis
    Write-Info "Waiting for services to be ready..."
    Start-Sleep -Seconds 10
}

Write-Success "Docker services are running"

# Start Backend Server
Write-Info "Starting backend server..."
Set-Location backend

# Check if virtual environment exists
if (!(Test-Path "venv")) {
    Write-Warning "Virtual environment not found. Creating one..."
    python -m venv venv
    Write-Success "Virtual environment created"
}

# Activate virtual environment
& "venv\Scripts\Activate.ps1"

# Install dependencies if needed
if (!(Test-Path "venv\.dependencies_installed")) {
    Write-Info "Installing Python dependencies..."
    pip install -r requirements.txt | Out-Null
    New-Item -Path "venv\.dependencies_installed" -ItemType File | Out-Null
    Write-Success "Dependencies installed"
}

# Start backend in background
Write-Info "Starting backend on http://localhost:8002..."
$script:BackendProcess = Start-Process -FilePath "uvicorn" -ArgumentList "app.main:app","--reload","--host","0.0.0.0","--port","8002" -PassThru -RedirectStandardOutput "..\backend.log" -RedirectStandardError "..\backend_error.log" -NoNewWindow
Set-Location ..

Start-Sleep -Seconds 3

# Check if backend started successfully
if ($null -ne $script:BackendProcess -and !$script:BackendProcess.HasExited) {
    Write-Success "Backend server started (PID: $($script:BackendProcess.Id))"
} else {
    Write-Error-Custom "Failed to start backend server"
    Write-Info "Check backend.log and backend_error.log for details"
    exit 1
}

# Start Frontend Server
Write-Info "Starting frontend server..."
Set-Location frontend

# Check if node_modules exists
if (!(Test-Path "node_modules")) {
    Write-Warning "Node modules not found. Installing..."
    npm install
    Write-Success "Dependencies installed"
}

# Start frontend
Write-Info "Starting frontend on http://localhost:3000..."
$script:FrontendProcess = Start-Process -FilePath "npm" -ArgumentList "start" -PassThru -RedirectStandardOutput "..\frontend.log" -RedirectStandardError "..\frontend_error.log" -NoNewWindow
Set-Location ..

Start-Sleep -Seconds 3

# Check if frontend started successfully
if ($null -ne $script:FrontendProcess -and !$script:FrontendProcess.HasExited) {
    Write-Success "Frontend server started (PID: $($script:FrontendProcess.Id))"
} else {
    Write-Error-Custom "Failed to start frontend server"
    Write-Info "Check frontend.log and frontend_error.log for details"
    exit 1
}

# Print status
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗"
Write-Host "║              🚀 Servers are running!                       ║"
Write-Host "╚════════════════════════════════════════════════════════════╝"
Write-Host ""
Write-Success "Backend API:  http://localhost:8002"
Write-Success "API Docs:     http://localhost:8002/docs"
Write-Success "Frontend:     http://localhost:3000"
Write-Host ""
Write-Info "Logs are being written to:"
Write-Host "  - backend.log / backend_error.log"
Write-Host "  - frontend.log / frontend_error.log"
Write-Host ""
Write-Warning "Press Ctrl+C to stop all servers"
Write-Host ""

# Keep script running and wait for user interrupt
try {
    while ($true) {
        Start-Sleep -Seconds 1

        # Check if processes are still running
        if ($script:BackendProcess.HasExited) {
            Write-Error-Custom "Backend server has stopped unexpectedly!"
            break
        }
        if ($script:FrontendProcess.HasExited) {
            Write-Error-Custom "Frontend server has stopped unexpectedly!"
            break
        }
    }
} finally {
    Cleanup
}
