# Quick Installation Guide

This guide provides the fastest way to install all required dependencies for the Airport Management System.

## One-Command Installation

### macOS and Linux

Open Terminal and run:

```bash
bash install.sh
```

That's it! The script will automatically:
- Detect your operating system
- Check what's already installed
- Install only missing dependencies
- Set up the project environment
- Create virtual environments and install packages

### Windows

1. Open PowerShell as Administrator (Right-click → "Run as Administrator")
2. Run:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; .\install.ps1
```

## What Gets Installed

The installation script will check for and install the following if missing:

### Core Tools
- **Git** - Version control
- **Docker Desktop** - Container platform (required)
- **Node.js 18+** - Frontend runtime
- **Python 3.11+** - Backend runtime

### Platform-Specific Tools
- **macOS**: Homebrew (package manager)
- **Linux**: Docker Compose plugin

### Project Dependencies
- Python packages (FastAPI, SQLAlchemy, Celery, etc.)
- Node.js packages (React, TypeScript, etc.)
- Virtual environments for backend

## After Installation

Once the installation script completes, follow these steps:

### 1. Review Configuration

Edit the `.env` file to customize your setup:

```bash
# macOS/Linux
nano .env

# Windows
notepad .env
```

### 2. Start the Application

```bash
docker compose up -d
```

Wait about 30 seconds for all services to start.

### 3. Initialize Database

```bash
docker compose exec backend alembic upgrade head
```

### 4. Access the Application

Open your browser and navigate to:

- **Frontend**: http://localhost:3001
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **Flower (Task Monitor)**: http://localhost:5555

### 5. Login

Use the default admin credentials:

- **Username**: `admin`
- **Password**: `admin123`

**IMPORTANT**: Change this password immediately after your first login!

## Troubleshooting

### Script Permissions (macOS/Linux)

If you get a "Permission denied" error:

```bash
chmod +x install.sh
bash install.sh
```

### Docker Not Running

If you see Docker errors:

1. Make sure Docker Desktop is installed and running
2. Check the system tray (Windows/macOS) or run `docker ps` (Linux)
3. Restart Docker Desktop if needed

### Re-running the Script

The installation script is **idempotent** - you can safely run it multiple times. It will:
- Skip already installed components
- Only install what's missing
- Update outdated versions when needed

### Manual Installation

If the automated script doesn't work for your system, see the detailed manual installation instructions in [README.md](README.md).

## System Requirements

### Minimum Hardware
- **CPU**: 2 cores (4 cores recommended)
- **RAM**: 4 GB (8 GB recommended)
- **Disk**: 10 GB free space

### Supported Operating Systems
- macOS 10.15 (Catalina) or later
- Ubuntu 20.04 or later
- Debian 10 or later
- Fedora 35 or later
- RHEL/CentOS 8 or later
- Windows 10 64-bit (Pro, Enterprise, or Education) or Windows 11

### Required Privileges
- **macOS/Linux**: Sudo access for system package installation
- **Windows**: Administrator privileges

## Getting Help

If you encounter issues:

1. Check the error messages from the installation script
2. See the comprehensive troubleshooting section in [README.md](README.md)
3. Review the logs: `docker compose logs -f`
4. Check that your system meets the minimum requirements

## What's Next?

After successful installation:

1. Read the [README.md](README.md) for detailed documentation
2. Check [docs/specification/airport_mgmt_description.md](docs/specification/airport_mgmt_description.md) for feature details
3. Explore the API at http://localhost:8001/docs
4. Start building your airport management solution!

---

**Pro Tip**: The installation script can be run again anytime to update dependencies or fix missing packages. It's safe to run multiple times.
