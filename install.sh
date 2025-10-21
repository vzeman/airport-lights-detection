#!/bin/bash

###############################################################################
# Airport Management System - Automated Installation Script
#
# This script automatically installs all required dependencies for the project
# Supports: macOS and Linux (Ubuntu/Debian, Fedora/RHEL/CentOS)
#
# Usage: bash install.sh
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo ""
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        log_info "Detected operating system: macOS"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            if [[ "$ID" == "ubuntu" ]] || [[ "$ID" == "debian" ]]; then
                OS="debian"
                log_info "Detected operating system: Ubuntu/Debian"
            elif [[ "$ID" == "fedora" ]] || [[ "$ID" == "rhel" ]] || [[ "$ID" == "centos" ]]; then
                OS="fedora"
                log_info "Detected operating system: Fedora/RHEL/CentOS"
            else
                log_warning "Unsupported Linux distribution. Attempting Debian-based installation..."
                OS="debian"
            fi
        else
            log_warning "Cannot detect Linux distribution. Attempting Debian-based installation..."
            OS="debian"
        fi
    else
        log_error "Unsupported operating system: $OSTYPE"
        log_info "This script supports macOS and Linux only."
        log_info "For Windows, please use install.ps1 with PowerShell."
        exit 1
    fi
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check and install Git
install_git() {
    log_section "Checking Git Installation"

    if command_exists git; then
        GIT_VERSION=$(git --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log_success "Git is already installed (version $GIT_VERSION)"
        return 0
    fi

    log_warning "Git is not installed. Installing..."

    case $OS in
        macos)
            log_info "Installing Xcode Command Line Tools (includes Git)..."
            xcode-select --install 2>/dev/null || log_info "Xcode Command Line Tools may already be installed"
            # Wait for installation
            until command_exists git; do
                sleep 2
            done
            ;;
        debian)
            log_info "Installing Git using apt..."
            sudo apt update
            sudo apt install -y git
            ;;
        fedora)
            log_info "Installing Git using dnf..."
            sudo dnf install -y git
            ;;
    esac

    if command_exists git; then
        log_success "Git installed successfully"
    else
        log_error "Failed to install Git"
        exit 1
    fi
}

# Check and install Homebrew (macOS only)
install_homebrew() {
    if [[ "$OS" != "macos" ]]; then
        return 0
    fi

    log_section "Checking Homebrew Installation"

    if command_exists brew; then
        log_success "Homebrew is already installed"
        return 0
    fi

    log_warning "Homebrew is not installed. Installing..."
    log_info "You may be prompted for your password..."

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi

    if command_exists brew; then
        log_success "Homebrew installed successfully"
    else
        log_error "Failed to install Homebrew"
        exit 1
    fi
}

# Check and install Docker
install_docker() {
    log_section "Checking Docker Installation"

    if command_exists docker; then
        DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log_success "Docker is already installed (version $DOCKER_VERSION)"

        # Check if Docker is running
        if docker ps >/dev/null 2>&1; then
            log_success "Docker daemon is running"
        else
            log_warning "Docker is installed but not running"
            log_info "Please start Docker Desktop and run this script again"

            if [[ "$OS" == "macos" ]]; then
                log_info "Starting Docker Desktop..."
                open -a Docker
                log_info "Waiting for Docker to start (this may take a minute)..."

                # Wait up to 60 seconds for Docker to start
                for i in {1..30}; do
                    if docker ps >/dev/null 2>&1; then
                        log_success "Docker is now running"
                        break
                    fi
                    sleep 2
                done

                if ! docker ps >/dev/null 2>&1; then
                    log_error "Docker failed to start. Please start Docker Desktop manually"
                    exit 1
                fi
            fi
        fi
        return 0
    fi

    log_warning "Docker is not installed. Installing..."

    case $OS in
        macos)
            log_info "Please install Docker Desktop manually from:"
            log_info "https://www.docker.com/products/docker-desktop"
            log_info ""
            log_info "After installation:"
            log_info "1. Open Docker Desktop from Applications"
            log_info "2. Wait for Docker to start"
            log_info "3. Run this script again"
            exit 1
            ;;
        debian)
            log_info "Installing Docker using official Docker repository..."

            # Install prerequisites
            sudo apt update
            sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

            # Add Docker's official GPG key
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

            # Add Docker repository
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

            # Install Docker
            sudo apt update
            sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

            # Add user to docker group
            sudo usermod -aG docker $USER

            # Start Docker
            sudo systemctl start docker
            sudo systemctl enable docker

            log_warning "You need to log out and log back in for Docker group changes to take effect"
            log_info "Or run: newgrp docker"
            ;;
        fedora)
            log_info "Installing Docker using official Docker repository..."

            # Install Docker
            sudo dnf install -y dnf-plugins-core
            sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
            sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

            # Start and enable Docker
            sudo systemctl start docker
            sudo systemctl enable docker

            # Add user to docker group
            sudo usermod -aG docker $USER

            log_warning "You need to log out and log back in for Docker group changes to take effect"
            log_info "Or run: newgrp docker"
            ;;
    esac

    if command_exists docker; then
        log_success "Docker installed successfully"
    else
        log_error "Failed to install Docker"
        exit 1
    fi
}

# Check and install Node.js
install_nodejs() {
    log_section "Checking Node.js Installation"

    if command_exists node; then
        NODE_VERSION=$(node --version | grep -oE '[0-9]+' | head -1)
        log_success "Node.js is already installed (version $(node --version))"

        if [ "$NODE_VERSION" -ge 18 ]; then
            log_success "Node.js version is 18 or higher ✓"
            return 0
        else
            log_warning "Node.js version is below 18. Upgrading..."
        fi
    else
        log_warning "Node.js is not installed. Installing Node.js 18 LTS..."
    fi

    case $OS in
        macos)
            if command_exists brew; then
                log_info "Installing Node.js using Homebrew..."
                brew install node@18 || brew upgrade node@18

                # Link Node.js 18
                brew link --overwrite node@18 --force
            else
                log_error "Homebrew is required to install Node.js on macOS"
                exit 1
            fi
            ;;
        debian)
            log_info "Installing Node.js using NodeSource repository..."
            curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
            sudo apt install -y nodejs
            ;;
        fedora)
            log_info "Installing Node.js using dnf..."
            sudo dnf install -y nodejs npm
            ;;
    esac

    if command_exists node && command_exists npm; then
        log_success "Node.js and npm installed successfully"
        log_info "Node.js version: $(node --version)"
        log_info "npm version: $(npm --version)"
    else
        log_error "Failed to install Node.js"
        exit 1
    fi
}

# Check and install Python
install_python() {
    log_section "Checking Python Installation"

    # Check for python3.11 or higher
    for py_cmd in python3.11 python3.12 python3.13 python3; do
        if command_exists $py_cmd; then
            PY_VERSION=$($py_cmd --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
            PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
            PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)

            if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 11 ]; then
                log_success "Python $PY_VERSION is already installed ($py_cmd)"
                PYTHON_CMD=$py_cmd
                return 0
            fi
        fi
    done

    log_warning "Python 3.11+ is not installed. Installing Python 3.11..."

    case $OS in
        macos)
            if command_exists brew; then
                log_info "Installing Python 3.11 using Homebrew..."
                brew install python@3.11 || brew upgrade python@3.11
                PYTHON_CMD=python3.11
            else
                log_error "Homebrew is required to install Python on macOS"
                exit 1
            fi
            ;;
        debian)
            log_info "Installing Python 3.11 using apt..."
            sudo apt update
            sudo apt install -y python3.11 python3.11-venv python3-pip
            PYTHON_CMD=python3.11
            ;;
        fedora)
            log_info "Installing Python 3.11 using dnf..."
            sudo dnf install -y python3.11 python3-pip
            PYTHON_CMD=python3.11
            ;;
    esac

    if command_exists $PYTHON_CMD; then
        log_success "Python installed successfully"
        log_info "Python version: $($PYTHON_CMD --version)"
    else
        log_error "Failed to install Python"
        exit 1
    fi
}

# Setup project environment
setup_project() {
    log_section "Setting Up Project Environment"

    # Check if .env exists
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            log_info "Creating .env file from .env.example..."
            cp .env.example .env
            log_success ".env file created"
            log_warning "Please review and update .env file with your configuration"
        else
            log_warning ".env.example not found. Skipping .env creation"
        fi
    else
        log_success ".env file already exists"
    fi

    # Install backend dependencies
    if [ -d "backend" ]; then
        log_info "Setting up backend Python environment..."
        cd backend

        # Create virtual environment if it doesn't exist
        if [ ! -d "venv" ]; then
            log_info "Creating Python virtual environment..."
            $PYTHON_CMD -m venv venv
            log_success "Virtual environment created"
        else
            log_success "Virtual environment already exists"
        fi

        # Activate virtual environment and install dependencies
        log_info "Installing Python dependencies..."
        source venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
        deactivate
        log_success "Backend dependencies installed"

        cd ..
    fi

    # Install frontend dependencies
    if [ -d "frontend" ]; then
        log_info "Setting up frontend Node.js environment..."
        cd frontend

        if [ ! -d "node_modules" ]; then
            log_info "Installing npm dependencies (this may take a few minutes)..."
            npm install
            log_success "Frontend dependencies installed"
        else
            log_success "Frontend dependencies already installed"
            log_info "Run 'npm install' in frontend directory to update dependencies if needed"
        fi

        cd ..
    fi
}

# Display next steps
show_next_steps() {
    log_section "Installation Complete!"

    echo ""
    log_success "All dependencies have been installed successfully!"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Next Steps:${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo "1️⃣  Review and update the .env file with your configuration:"
    echo "   ${YELLOW}nano .env${NC}"
    echo ""
    echo "2️⃣  Start the application using Docker:"
    echo "   ${YELLOW}docker compose up -d${NC}"
    echo ""
    echo "3️⃣  Wait for services to start (about 30 seconds), then initialize the database:"
    echo "   ${YELLOW}docker compose exec backend alembic upgrade head${NC}"
    echo ""
    echo "4️⃣  Access the application:"
    echo "   • Frontend:  ${BLUE}http://localhost:3001${NC}"
    echo "   • Backend:   ${BLUE}http://localhost:8001${NC}"
    echo "   • API Docs:  ${BLUE}http://localhost:8001/docs${NC}"
    echo "   • Flower:    ${BLUE}http://localhost:5555${NC}"
    echo ""
    echo "5️⃣  Login with default credentials:"
    echo "   • Username:  ${YELLOW}admin${NC}"
    echo "   • Password:  ${YELLOW}admin123${NC}"
    echo "   ${RED}⚠ Change the password after first login!${NC}"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo ""
    echo "📚 For more information, see README.md"
    echo ""

    if [[ "$OS" != "macos" ]] && groups | grep -q docker; then
        log_warning "You may need to log out and log back in for Docker permissions to take effect"
        log_info "Or run: newgrp docker"
    fi
}

# Main installation flow
main() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                       ║${NC}"
    echo -e "${GREEN}║    Airport Management System - Auto Installer        ║${NC}"
    echo -e "${GREEN}║                                                       ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""

    log_info "Starting automated installation..."
    log_warning "You may be prompted for your password during installation"
    echo ""

    # Detect OS
    detect_os

    # Install components
    install_git

    if [[ "$OS" == "macos" ]]; then
        install_homebrew
    fi

    install_docker
    install_nodejs
    install_python

    # Setup project
    setup_project

    # Show next steps
    show_next_steps
}

# Run main function
main
