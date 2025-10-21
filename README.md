# Airport Management System

A comprehensive multi-tenant application for automated airport maintenance and quality management, leveraging drone technology and AI-powered analysis to ensure safety compliance and optimize maintenance operations.

./docs/specification/airport_mgmt_description.md contains all details we want to implement in the app.

## Features

### Core Functionality
- **Multi-tenant Architecture**: Support for multiple airports with complete data isolation
- **User Management**: Role-based access control (Super Admin, Airport Admin, Maintenance Manager, Drone Operator, Viewer)
- **Airport Management**: Complete airport profile management with ICAO/IATA codes, location, and compliance frameworks
- **Item Management**: Track and manage all airport infrastructure items (lights, markings, navigation aids)
- **2D/3D Map Visualization**: Interactive map interface for viewing and editing airport items using Mapbox
- **Task Scheduling**: Automated task creation and scheduling with Celery
- **Real-time Processing**: Background task processing for inspections and maintenance

### Technical Features
- **FastAPI Backend**: High-performance async REST API with automatic documentation
- **JWT Authentication**: Secure token-based authentication with refresh tokens
- **Spatial Data Support**: GeoJSON and PostGIS integration for geographic data
- **Docker Containerization**: Complete Docker setup for easy deployment
- **React Frontend**: Modern responsive UI with Material-UI components

## Tech Stack

### Backend
- **FastAPI**: REST API framework
- **SQLAlchemy**: ORM with async support
- **Celery**: Distributed task queue
- **Redis**: Cache and message broker
- **MySQL**: Primary database
- **Alembic**: Database migrations
- **GeoAlchemy2**: Spatial data support

### Frontend
- **React**: UI framework with TypeScript
- **Material-UI**: Component library
- **Mapbox GL**: 2D/3D map visualization
- **React Router**: Client-side routing
- **Axios**: HTTP client
- **React Hook Form**: Form management

## Installation

### 🚀 Quick Start (Recommended)

**Want to get started fast?** Use our automated installation script:

```bash
bash install.sh
```

This single command will automatically install all required dependencies and set up your development environment. See [INSTALL.md](INSTALL.md) for details.

---

### Manual Installation

If you prefer manual installation or the automated script doesn't work for your system, follow the detailed instructions below.

### Prerequisites

This application can be run using Docker (recommended) or locally without Docker. Below are the requirements for each approach:

**For Docker-based setup (Recommended)**:
- Docker Desktop (includes Docker and Docker Compose)
- Git
- (Optional) Mapbox Access Token for map features

**For local development setup**:
- Docker Desktop (for MySQL and Redis)
- Node.js 18+ and npm
- Python 3.11+
- Git
- (Optional) Mapbox Access Token for map features

### Platform-Specific Prerequisites Installation

#### Windows

1. **Install Git**:
   - Download from https://git-scm.com/download/win
   - Run the installer and follow the wizard
   - Accept default settings

2. **Install Docker Desktop**:
   - Download from https://www.docker.com/products/docker-desktop
   - Run the installer (requires Windows 10 64-bit: Pro, Enterprise, or Education)
   - Enable WSL 2 during installation if prompted
   - Restart your computer when installation completes
   - Start Docker Desktop from the Start menu
   - Wait for Docker to start (check system tray icon)

3. **Install Node.js** (for local development):
   - Download LTS version from https://nodejs.org/
   - Run the installer and follow the wizard
   - Verify installation:
     ```cmd
     node --version
     npm --version
     ```

4. **Install Python** (for local development):
   - Download Python 3.11 or higher from https://www.python.org/downloads/
   - Run the installer
   - **IMPORTANT**: Check "Add Python to PATH" during installation
   - Verify installation:
     ```cmd
     python --version
     pip --version
     ```

#### macOS

1. **Install Git**:
   Git is included with Xcode Command Line Tools:
   ```bash
   xcode-select --install
   ```

2. **Install Docker Desktop**:
   - Download from https://www.docker.com/products/docker-desktop
   - Open the .dmg file and drag Docker to Applications
   - Open Docker from Applications folder
   - Follow the setup wizard and grant necessary permissions
   - Wait for Docker to start (check menu bar icon)

3. **Install Node.js** (for local development):

   Using Homebrew (recommended):
   ```bash
   # Install Homebrew if not already installed
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

   # Install Node.js
   brew install node@18

   # Verify installation
   node --version
   npm --version
   ```

   Or download from https://nodejs.org/

4. **Install Python** (for local development):
   ```bash
   # Using Homebrew
   brew install python@3.11

   # Verify installation
   python3 --version
   pip3 --version
   ```

#### Linux (Ubuntu/Debian)

1. **Install Git**:
   ```bash
   sudo apt update
   sudo apt install git -y
   ```

2. **Install Docker and Docker Compose**:
   ```bash
   # Update package index
   sudo apt update

   # Install prerequisites
   sudo apt install apt-transport-https ca-certificates curl software-properties-common -y

   # Add Docker's official GPG key
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

   # Add Docker repository
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

   # Install Docker
   sudo apt update
   sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y

   # Add your user to docker group (to run without sudo)
   sudo usermod -aG docker $USER

   # Log out and log back in for group changes to take effect
   # Or run: newgrp docker

   # Verify installation
   docker --version
   docker compose version
   ```

3. **Install Node.js** (for local development):
   ```bash
   # Using NodeSource repository for latest LTS
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt install nodejs -y

   # Verify installation
   node --version
   npm --version
   ```

4. **Install Python** (for local development):
   ```bash
   # Install Python 3.11
   sudo apt update
   sudo apt install python3.11 python3.11-venv python3-pip -y

   # Verify installation
   python3.11 --version
   pip3 --version
   ```

#### Linux (Fedora/RHEL/CentOS)

1. **Install Git**:
   ```bash
   sudo dnf install git -y
   ```

2. **Install Docker and Docker Compose**:
   ```bash
   # Install Docker
   sudo dnf install dnf-plugins-core -y
   sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
   sudo dnf install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y

   # Start and enable Docker
   sudo systemctl start docker
   sudo systemctl enable docker

   # Add your user to docker group
   sudo usermod -aG docker $USER
   newgrp docker

   # Verify installation
   docker --version
   docker compose version
   ```

3. **Install Node.js**:
   ```bash
   sudo dnf install nodejs npm -y

   # Verify installation
   node --version
   npm --version
   ```

4. **Install Python**:
   ```bash
   sudo dnf install python3.11 python3-pip -y

   # Verify installation
   python3.11 --version
   pip3 --version
   ```

### Quick Start with Docker (All Platforms)

1. **Clone the repository**:

   ```bash
   # Using HTTPS
   git clone https://github.com/your-username/airport-lights-detection.git
   cd airport-lights-detection
   ```

   Or use SSH if you have SSH keys set up:
   ```bash
   git clone git@github.com:your-username/airport-lights-detection.git
   cd airport-lights-detection
   ```

2. **Set up environment variables**:

   The application uses environment variables for configuration. A sample `.env.example` file is provided.

   **On Linux/macOS**:
   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit with your preferred editor (nano, vim, or any text editor)
   nano .env
   ```

   **On Windows (Command Prompt)**:
   ```cmd
   copy .env.example .env
   notepad .env
   ```

   **On Windows (PowerShell)**:
   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   **Optional**: If you want to use Mapbox features, set your Mapbox token:
   - Get a free token from https://www.mapbox.com/
   - Add it to your environment or frontend configuration

3. **Start the application**:

   **On Linux/macOS**:
   ```bash
   docker compose up -d
   ```

   **On Windows**:
   ```cmd
   docker compose up -d
   ```

   This command will:
   - Download all required Docker images (first run only)
   - Create and start all containers (MySQL, Redis, Backend, Frontend, Celery, Flower)
   - Set up the network and volumes

   **Note**: The first run will take several minutes to download images and build containers.

4. **Initialize the database**:

   Wait for all services to be healthy (about 30 seconds), then run:

   **On Linux/macOS**:
   ```bash
   # Apply database migrations
   docker compose exec backend alembic upgrade head
   ```

   **On Windows**:
   ```cmd
   docker compose exec backend alembic upgrade head
   ```

5. **Access the application**:

   Once all services are running, you can access:

   - **Frontend**: http://localhost:3001
   - **Backend API**: http://localhost:8001
   - **API Documentation (Swagger)**: http://localhost:8001/docs
   - **API Documentation (ReDoc)**: http://localhost:8001/redoc
   - **Flower (Celery Task Monitor)**: http://localhost:5555

6. **Login with default admin credentials**:

   When the application starts for the first time, a default admin user is automatically created:

   - **Username**: `admin`
   - **Password**: `admin123`
   - **Email**: `admin@example.com`

   You can now login to the frontend application using these credentials.

   **IMPORTANT**: For security reasons, please change the default password immediately after your first login!

   To create additional users:
   - Login as the admin user
   - Go to http://localhost:8001/docs (API documentation)
   - Find the `POST /api/v1/users` endpoint
   - Click "Try it out" and enter user details

### Checking Service Status

To verify all services are running correctly:

**On Linux/macOS**:
```bash
docker compose ps
```

**On Windows**:
```cmd
docker compose ps
```

You should see all services in "Up" state:
- mysql
- redis
- backend
- frontend
- celery_worker
- celery_beat
- flower

### Viewing Logs

To view logs from all services:

**On Linux/macOS**:
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
```

**On Windows**:
```cmd
REM All services
docker compose logs -f

REM Specific service
docker compose logs -f backend
docker compose logs -f frontend
```

### Stopping the Application

**On Linux/macOS**:
```bash
# Stop all services
docker compose down

# Stop and remove all data (WARNING: deletes database)
docker compose down -v
```

**On Windows**:
```cmd
REM Stop all services
docker compose down

REM Stop and remove all data (WARNING: deletes database)
docker compose down -v
```

## Local Development (Without Docker Containers)

If you prefer to run the application locally without Docker containers (useful for development and debugging):

### Backend Development

**On Linux/macOS**:
```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Make sure MySQL and Redis are running (via Docker)
docker compose up mysql redis -d

# Set environment variables
export DATABASE_URL="mysql+aiomysql://airport_user:airport_pass@localhost:3307/airport_mgmt"
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="your-secret-key-change-in-production"

# Run database migrations
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**On Windows (Command Prompt)**:
```cmd
cd backend

REM Create virtual environment
python -m venv venv
venv\Scripts\activate

REM Install dependencies
pip install -r requirements.txt

REM Make sure MySQL and Redis are running (via Docker)
docker compose up mysql redis -d

REM Set environment variables
set DATABASE_URL=mysql+aiomysql://airport_user:airport_pass@localhost:3307/airport_mgmt
set REDIS_URL=redis://localhost:6379/0
set SECRET_KEY=your-secret-key-change-in-production

REM Run database migrations
alembic upgrade head

REM Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**On Windows (PowerShell)**:
```powershell
cd backend

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Make sure MySQL and Redis are running (via Docker)
docker compose up mysql redis -d

# Set environment variables
$env:DATABASE_URL="mysql+aiomysql://airport_user:airport_pass@localhost:3307/airport_mgmt"
$env:REDIS_URL="redis://localhost:6379/0"
$env:SECRET_KEY="your-secret-key-change-in-production"

# Run database migrations
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development

**On Linux/macOS**:
```bash
cd frontend

# Install dependencies
npm install

# Set API URL (optional, has default)
export REACT_APP_API_URL=http://localhost:8000/api/v1

# Start development server
npm start
```

**On Windows (Command Prompt)**:
```cmd
cd frontend

REM Install dependencies
npm install

REM Set API URL (optional, has default)
set REACT_APP_API_URL=http://localhost:8000/api/v1

REM Start development server
npm start
```

**On Windows (PowerShell)**:
```powershell
cd frontend

# Install dependencies
npm install

# Set API URL (optional, has default)
$env:REACT_APP_API_URL="http://localhost:8000/api/v1"

# Start development server
npm start
```

### Running Celery Workers (Optional)

For background task processing:

**On Linux/macOS**:
```bash
# In a new terminal, from backend directory with venv activated
celery -A app.celery_app worker --loglevel=info

# In another terminal for scheduled tasks
celery -A app.celery_app beat --loglevel=info
```

**On Windows**:
```cmd
REM Celery on Windows requires eventlet
pip install eventlet

REM Worker
celery -A app.celery_app worker --loglevel=info -P eventlet

REM Beat scheduler
celery -A app.celery_app beat --loglevel=info
```

### Running Tests

**Backend Tests**:

**On Linux/macOS**:
```bash
# Using Docker
docker compose exec backend pytest

# Or locally with venv activated
cd backend
pytest
```

**On Windows**:
```cmd
REM Using Docker
docker compose exec backend pytest

REM Or locally with venv activated
cd backend
pytest
```

**Frontend Tests**:

**On Linux/macOS**:
```bash
cd frontend
npm test
```

**On Windows**:
```cmd
cd frontend
npm test
```

## Troubleshooting

### Common Issues and Solutions

#### Docker Issues

**Problem**: "Cannot connect to Docker daemon"
- **Solution**: Make sure Docker Desktop is running
- **Windows**: Check system tray for Docker icon
- **macOS**: Check menu bar for Docker icon
- **Linux**: Run `sudo systemctl start docker`

**Problem**: Port already in use (e.g., "port 3001 is already allocated")
- **Solution**: Stop the service using that port or change the port in `docker-compose.yml`
- **Find process on Linux/macOS**: `lsof -i :3001`
- **Find process on Windows**: `netstat -ano | findstr :3001`

**Problem**: Containers keep restarting
- **Solution**: Check logs: `docker compose logs [service-name]`
- Common cause: Database not ready. Wait 30-60 seconds for MySQL to initialize

**Problem**: "no space left on device"
- **Solution**: Clean up Docker resources:
  ```bash
  docker system prune -a
  docker volume prune
  ```

#### Database Issues

**Problem**: "Can't connect to MySQL server"
- **Solution**:
  - Wait for MySQL to be fully started (check with `docker compose ps`)
  - Verify MySQL is healthy: `docker compose exec mysql mysqladmin ping -h localhost`

**Problem**: Migration errors
- **Solution**:
  ```bash
  # Reset migrations (WARNING: deletes all data)
  docker compose down -v
  docker compose up -d
  docker compose exec backend alembic upgrade head
  ```

#### Frontend Issues

**Problem**: Blank page or "Failed to fetch"
- **Solution**:
  - Check if backend is running: Visit http://localhost:8001/docs
  - Check browser console for errors (F12)
  - Verify REACT_APP_API_URL is set correctly

**Problem**: Map not displaying
- **Solution**:
  - Make sure you have a valid Mapbox token
  - Check browser console for Mapbox errors

#### Performance Issues

**Problem**: Application is slow
- **Solution**:
  - Increase Docker Desktop resources (Memory & CPU)
  - **Windows/macOS**: Docker Desktop → Settings → Resources
  - Close other applications to free up resources

#### Windows-Specific Issues

**Problem**: WSL 2 installation error
- **Solution**:
  1. Enable WSL: Run PowerShell as Administrator:
     ```powershell
     wsl --install
     ```
  2. Restart computer
  3. Reinstall Docker Desktop

**Problem**: Line ending issues (CRLF vs LF)
- **Solution**: Configure Git to use LF:
  ```bash
  git config --global core.autocrlf false
  git config --global core.eol lf
  ```

#### macOS-Specific Issues

**Problem**: Permission denied errors
- **Solution**:
  ```bash
  sudo chown -R $USER:$USER /Users/viktorzeman/work/airport-lights-detection
  ```

#### Linux-Specific Issues

**Problem**: Permission denied when running docker commands
- **Solution**:
  ```bash
  sudo usermod -aG docker $USER
  newgrp docker
  # Or log out and log back in
  ```

### Getting Help

If you encounter issues not covered here:

1. Check the logs: `docker compose logs -f`
2. Check individual service logs: `docker compose logs -f [service-name]`
3. Verify all environment variables are set correctly
4. Check Docker Desktop has sufficient resources allocated
5. Try rebuilding containers: `docker compose up -d --build`
6. As a last resort, completely reset: `docker compose down -v && docker compose up -d --build`

### Useful Commands Reference

**Docker Management**:
```bash
# View running containers
docker compose ps

# View all containers (including stopped)
docker ps -a

# Restart a specific service
docker compose restart backend

# Rebuild a specific service
docker compose up -d --build backend

# View resource usage
docker stats

# Access container shell
docker compose exec backend bash
docker compose exec frontend sh
```

**Database Management**:
```bash
# Access MySQL shell
docker compose exec mysql mysql -u airport_user -pairport_pass airport_mgmt

# Backup database
docker compose exec mysql mysqldump -u airport_user -pairport_pass airport_mgmt > backup.sql

# Restore database
docker compose exec -T mysql mysql -u airport_user -pairport_pass airport_mgmt < backup.sql
```

## API Documentation

The API documentation is automatically generated and available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key API Endpoints

#### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user

#### Users
- `GET /api/v1/users` - List users
- `POST /api/v1/users` - Create user
- `PATCH /api/v1/users/{id}` - Update user
- `DELETE /api/v1/users/{id}` - Delete user

#### Airports
- `GET /api/v1/airports` - List airports
- `POST /api/v1/airports` - Create airport
- `GET /api/v1/airports/{id}` - Get airport details
- `PATCH /api/v1/airports/{id}` - Update airport
- `DELETE /api/v1/airports/{id}` - Delete airport

#### Airport Items
- `GET /api/v1/airports/{id}/items` - List airport items
- `POST /api/v1/airports/{id}/items` - Create item
- `PATCH /api/v1/airports/{id}/items/{item_id}` - Update item
- `DELETE /api/v1/airports/{id}/items/{item_id}` - Delete item

... etc

## Database Schema

### Main Tables
- **users**: User accounts with authentication
- **airports**: Airport profiles with location data
- **airport_items**: Infrastructure items (lights, markings, etc.)
- **item_types**: Categories of airport items
- **runways**: Runway definitions with geometry
- **tasks**: Scheduled and completed tasks
- **measurements**: Inspection measurements and results
- **audit_logs**: System audit trail

## Project Structure

```
airport-lights-detection/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── core/         # Core configuration
│   │   ├── db/           # Database configuration
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── tasks/        # Celery tasks
│   ├── alembic/          # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/   # Reusable components
│   │   ├── contexts/     # React contexts
│   │   ├── pages/        # Page components
│   │   ├── services/     # API services
│   │   └── App.tsx       # Main app component
│   ├── package.json
│   └── Dockerfile
├── docs/
│   └── specification/    # Project specifications
├── data/                 # Local data storage
└── docker-compose.yml    # Docker configuration
```

## User Roles

1. **Super Admin**: Full system access, user management, all airports
2. **Airport Admin**: Manage specific airports and their users
3. **Maintenance Manager**: Schedule and manage maintenance tasks
4. **Drone Operator**: Execute drone missions and upload data
5. **Viewer**: Read-only access to assigned airports

## Security Features

- JWT-based authentication with refresh tokens
- Role-based access control (RBAC)
- Password hashing with bcrypt
- CORS configuration
- SQL injection prevention via ORM
- Input validation with Pydantic

### Default Credentials Security

**IMPORTANT SECURITY NOTICE**:

The application creates a default admin user on first startup with the following credentials:
- Username: `admin`
- Password: `admin123`

This is **only intended for initial setup and testing**. For production deployments:

1. Change the default admin password immediately after first login
2. Consider disabling or deleting the default admin user after creating your own admin account
3. Use strong, unique passwords for all user accounts
4. Enable MFA (Multi-Factor Authentication) when available
5. Regularly audit user accounts and permissions
6. Use environment variables to configure secure SECRET_KEY values
7. Never commit sensitive credentials to version control
