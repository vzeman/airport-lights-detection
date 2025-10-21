# Airport Management System - Automated Installation Script for Windows
#
# This script automatically installs all required dependencies for the project
# Supports: Windows 10/11 with PowerShell
#
# Usage: Run PowerShell as Administrator and execute:
#        Set-ExecutionPolicy Bypass -Scope Process -Force; .\install.ps1

#Requires -RunAsAdministrator

# Enable strict mode
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Colors for output
function Write-InfoMsg {
    param($Message)
    Write-Host "ℹ $Message" -ForegroundColor Blue
}

function Write-SuccessMsg {
    param($Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-WarningMsg {
    param($Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-ErrorMsg {
    param($Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

function Write-SectionHeader {
    param($Message)
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Blue
    Write-Host ""
}

# Check if running as administrator
function Test-Administrator {
    $currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Check if a command exists
function Test-CommandExists {
    param($Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

# Install Chocolatey
function Install-Chocolatey {
    Write-SectionHeader "Checking Chocolatey Installation"

    if (Test-CommandExists choco) {
        $chocoVersion = (choco --version)
        Write-SuccessMsg "Chocolatey is already installed (version $chocoVersion)"
        return
    }

    Write-WarningMsg "Chocolatey is not installed. Installing..."
    Write-InfoMsg "Chocolatey is a package manager for Windows that simplifies software installation"

    try {
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

        # Refresh environment variables
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

        if (Test-CommandExists choco) {
            Write-SuccessMsg "Chocolatey installed successfully"
        } else {
            Write-ErrorMsg "Failed to install Chocolatey"
            exit 1
        }
    }
    catch {
        Write-ErrorMsg "Error installing Chocolatey: $_"
        exit 1
    }
}

# Install Git
function Install-Git {
    Write-SectionHeader "Checking Git Installation"

    if (Test-CommandExists git) {
        $gitVersion = (git --version)
        Write-SuccessMsg "Git is already installed ($gitVersion)"
        return
    }

    Write-WarningMsg "Git is not installed. Installing..."

    try {
        choco install git -y

        # Refresh environment variables
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

        if (Test-CommandExists git) {
            Write-SuccessMsg "Git installed successfully"

            # Configure Git line endings
            git config --global core.autocrlf false
            git config --global core.eol lf
            Write-InfoMsg "Git configured to use LF line endings"
        } else {
            Write-ErrorMsg "Failed to install Git"
            exit 1
        }
    }
    catch {
        Write-ErrorMsg "Error installing Git: $_"
        exit 1
    }
}

# Install Docker Desktop
function Install-Docker {
    Write-SectionHeader "Checking Docker Installation"

    if (Test-CommandExists docker) {
        $dockerVersion = (docker --version)
        Write-SuccessMsg "Docker is already installed ($dockerVersion)"

        # Check if Docker is running
        try {
            docker ps | Out-Null
            Write-SuccessMsg "Docker daemon is running"
        }
        catch {
            Write-WarningMsg "Docker is installed but not running"
            Write-InfoMsg "Starting Docker Desktop..."

            # Try to start Docker Desktop
            $dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
            if (Test-Path $dockerPath) {
                Start-Process $dockerPath
                Write-InfoMsg "Waiting for Docker to start (this may take a minute)..."

                $maxAttempts = 30
                $attempt = 0
                while ($attempt -lt $maxAttempts) {
                    try {
                        docker ps | Out-Null
                        Write-SuccessMsg "Docker is now running"
                        break
                    }
                    catch {
                        Start-Sleep -Seconds 2
                        $attempt++
                    }
                }

                if ($attempt -eq $maxAttempts) {
                    Write-ErrorMsg "Docker failed to start. Please start Docker Desktop manually"
                    exit 1
                }
            }
        }
        return
    }

    Write-WarningMsg "Docker Desktop is not installed."
    Write-InfoMsg "Docker Desktop requires manual installation on Windows."
    Write-InfoMsg ""
    Write-InfoMsg "Please follow these steps:"
    Write-InfoMsg "1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop"
    Write-InfoMsg "2. Run the installer"
    Write-InfoMsg "3. Enable WSL 2 if prompted"
    Write-InfoMsg "4. Restart your computer after installation"
    Write-InfoMsg "5. Start Docker Desktop"
    Write-InfoMsg "6. Run this script again"
    Write-InfoMsg ""

    $response = Read-Host "Do you want to open the Docker Desktop download page now? (Y/N)"
    if ($response -eq 'Y' -or $response -eq 'y') {
        Start-Process "https://www.docker.com/products/docker-desktop"
    }

    exit 1
}

# Install Node.js
function Install-NodeJS {
    Write-SectionHeader "Checking Node.js Installation"

    if (Test-CommandExists node) {
        $nodeVersion = (node --version)
        $nodeVersionNumber = [int]($nodeVersion -replace 'v(\d+)\..*','$1')
        Write-SuccessMsg "Node.js is already installed ($nodeVersion)"

        if ($nodeVersionNumber -ge 18) {
            Write-SuccessMsg "Node.js version is 18 or higher ✓"
            return
        } else {
            Write-WarningMsg "Node.js version is below 18. Upgrading..."
        }
    } else {
        Write-WarningMsg "Node.js is not installed. Installing Node.js 18 LTS..."
    }

    try {
        choco install nodejs-lts --version=18.20.5 -y --force

        # Refresh environment variables
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

        if (Test-CommandExists node) {
            Write-SuccessMsg "Node.js and npm installed successfully"
            Write-InfoMsg "Node.js version: $(node --version)"
            Write-InfoMsg "npm version: $(npm --version)"
        } else {
            Write-ErrorMsg "Failed to install Node.js"
            exit 1
        }
    }
    catch {
        Write-ErrorMsg "Error installing Node.js: $_"
        exit 1
    }
}

# Install Python
function Install-Python {
    Write-SectionHeader "Checking Python Installation"

    # Check for Python 3.11 or higher
    if (Test-CommandExists python) {
        $pythonVersion = (python --version 2>&1)
        if ($pythonVersion -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]

            if ($major -eq 3 -and $minor -ge 11) {
                Write-SuccessMsg "Python $pythonVersion is already installed"
                return
            } else {
                Write-WarningMsg "Python version is below 3.11. Upgrading..."
            }
        }
    } else {
        Write-WarningMsg "Python is not installed. Installing Python 3.11..."
    }

    try {
        choco install python311 -y

        # Refresh environment variables
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

        if (Test-CommandExists python) {
            Write-SuccessMsg "Python installed successfully"
            Write-InfoMsg "Python version: $(python --version)"
            Write-InfoMsg "pip version: $(pip --version)"
        } else {
            Write-ErrorMsg "Failed to install Python"
            exit 1
        }
    }
    catch {
        Write-ErrorMsg "Error installing Python: $_"
        exit 1
    }
}

# Setup project environment
function Setup-Project {
    Write-SectionHeader "Setting Up Project Environment"

    # Check if .env exists
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Write-InfoMsg "Creating .env file from .env.example..."
            Copy-Item ".env.example" ".env"
            Write-SuccessMsg ".env file created"
            Write-WarningMsg "Please review and update .env file with your configuration"
        } else {
            Write-WarningMsg ".env.example not found. Skipping .env creation"
        }
    } else {
        Write-SuccessMsg ".env file already exists"
    }

    # Install backend dependencies
    if (Test-Path "backend") {
        Write-InfoMsg "Setting up backend Python environment..."
        Push-Location backend

        # Create virtual environment if it doesn't exist
        if (-not (Test-Path "venv")) {
            Write-InfoMsg "Creating Python virtual environment..."
            python -m venv venv
            Write-SuccessMsg "Virtual environment created"
        } else {
            Write-SuccessMsg "Virtual environment already exists"
        }

        # Activate virtual environment and install dependencies
        Write-InfoMsg "Installing Python dependencies..."
        .\venv\Scripts\Activate.ps1
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        deactivate
        Write-SuccessMsg "Backend dependencies installed"

        Pop-Location
    }

    # Install frontend dependencies
    if (Test-Path "frontend") {
        Write-InfoMsg "Setting up frontend Node.js environment..."
        Push-Location frontend

        if (-not (Test-Path "node_modules")) {
            Write-InfoMsg "Installing npm dependencies (this may take a few minutes)..."
            npm install
            Write-SuccessMsg "Frontend dependencies installed"
        } else {
            Write-SuccessMsg "Frontend dependencies already installed"
            Write-InfoMsg "Run 'npm install' in frontend directory to update dependencies if needed"
        }

        Pop-Location
    }
}

# Display next steps
function Show-NextSteps {
    Write-SectionHeader "Installation Complete!"

    Write-Host ""
    Write-SuccessMsg "All dependencies have been installed successfully!"
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Blue
    Write-Host "Next Steps:" -ForegroundColor Green
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Blue
    Write-Host ""
    Write-Host "1️⃣  Review and update the .env file with your configuration:"
    Write-Host "   " -NoNewline; Write-Host "notepad .env" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "2️⃣  Start the application using Docker:"
    Write-Host "   " -NoNewline; Write-Host "docker compose up -d" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "3️⃣  Wait for services to start (about 30 seconds), then initialize the database:"
    Write-Host "   " -NoNewline; Write-Host "docker compose exec backend alembic upgrade head" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "4️⃣  Access the application:"
    Write-Host "   • Frontend:  " -NoNewline; Write-Host "http://localhost:3001" -ForegroundColor Blue
    Write-Host "   • Backend:   " -NoNewline; Write-Host "http://localhost:8001" -ForegroundColor Blue
    Write-Host "   • API Docs:  " -NoNewline; Write-Host "http://localhost:8001/docs" -ForegroundColor Blue
    Write-Host "   • Flower:    " -NoNewline; Write-Host "http://localhost:5555" -ForegroundColor Blue
    Write-Host ""
    Write-Host "5️⃣  Login with default credentials:"
    Write-Host "   • Username:  " -NoNewline; Write-Host "admin" -ForegroundColor Yellow
    Write-Host "   • Password:  " -NoNewline; Write-Host "admin123" -ForegroundColor Yellow
    Write-Host "   " -NoNewline; Write-Host "⚠ Change the password after first login!" -ForegroundColor Red
    Write-Host ""
    Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Blue
    Write-Host ""
    Write-Host "📚 For more information, see README.md"
    Write-Host ""
}

# Main installation flow
function Main {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                                                       ║" -ForegroundColor Green
    Write-Host "║    Airport Management System - Auto Installer        ║" -ForegroundColor Green
    Write-Host "║                   (Windows)                           ║" -ForegroundColor Green
    Write-Host "║                                                       ║" -ForegroundColor Green
    Write-Host "╚═══════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""

    # Check if running as administrator
    if (-not (Test-Administrator)) {
        Write-ErrorMsg "This script must be run as Administrator"
        Write-InfoMsg "Please right-click PowerShell and select 'Run as Administrator'"
        exit 1
    }

    Write-InfoMsg "Starting automated installation..."
    Write-InfoMsg "Detected operating system: Windows"
    Write-Host ""

    try {
        # Install components
        Install-Chocolatey
        Install-Git
        Install-Docker
        Install-NodeJS
        Install-Python

        # Setup project
        Setup-Project

        # Show next steps
        Show-NextSteps
    }
    catch {
        Write-ErrorMsg "Installation failed: $_"
        Write-InfoMsg "Please check the error message above and try again"
        exit 1
    }
}

# Run main function
Main
