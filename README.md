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

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)
- Mapbox Access Token (for map features)

### Quick Start

1. **Clone the repository**:
```bash
git clone <repository-url>
cd airport-lights-detection
```

2. **Set up environment variables**:
```bash
# Create .env file in backend directory
cp backend/.env.example backend/.env
# Edit the file with your configuration

# For frontend, set your Mapbox token
export REACT_APP_MAPBOX_TOKEN=your_mapbox_token_here
```

3. **Start the application with Docker**:
```bash
docker-compose up -d
```

4. **Initialize the database**:
```bash
# Create initial migration
docker-compose exec backend alembic revision --autogenerate -m "Initial migration"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Create superuser (optional - via API or manual DB insert)
```

5. **Access the application**:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs
- Flower (Celery monitoring): http://localhost:5555

## Development

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

### Running Tests

```bash
# Backend tests
docker-compose exec backend pytest

# Frontend tests
cd frontend && npm test
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
