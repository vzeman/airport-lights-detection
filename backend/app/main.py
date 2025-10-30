from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from contextlib import asynccontextmanager
import logging
import sys
import os
import stat
import traceback
from pathlib import Path
from alembic.config import Config
from alembic import command

from app.core.config import settings
from app.api import auth, users, airports, airport_import, airspace, item_types, missions, papi_measurements, runways, reference_points
from app.db.base import engine, Base, AsyncSessionLocal

# Configure logging with force=True to override any existing configuration
import logging.config

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

# First, do basic config
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(logs_dir / "backend.log", mode='a')
    ]
)

# Set root logger to INFO
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Ensure app logger and all subloggers use INFO
app_logger = logging.getLogger('app')
app_logger.setLevel(logging.INFO)
app_logger.propagate = True

# CRITICAL FIX: Ensure ALL child loggers inherit handlers
# This makes logger.info() work in all app.* modules
for logger_name in ['app.api', 'app.services', 'app.models', 'app.core']:
    child_logger = logging.getLogger(logger_name)
    child_logger.setLevel(logging.INFO)
    child_logger.propagate = True

# Get the main logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# CRITICAL FIX: Ensure uvicorn doesn't filter our logs
# We need to add our handler to uvicorn's loggers too
uvicorn_error_logger = logging.getLogger("uvicorn.error")
uvicorn_error_logger.setLevel(logging.INFO)

uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup

    # CRITICAL FIX: Re-configure logging AFTER uvicorn has started
    # Uvicorn replaces handlers during startup, so we need to fix it here
    # ONLY configure root logger - all children will inherit via propagation
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    file_handler = logging.FileHandler(logs_dir / "backend.log", mode='a')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # Configure ONLY the root logger - all child loggers will inherit these handlers
    root_logger.handlers.clear()
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)

    # Ensure all child loggers propagate to root (this is default, but let's be explicit)
    for logger_name in logging.root.manager.loggerDict:
        child_logger = logging.getLogger(logger_name)
        child_logger.setLevel(logging.NOTSET)  # Inherit from parent
        child_logger.propagate = True  # Propagate to parent
        child_logger.handlers = []  # Don't add handlers to children

    logger.info("Starting up...")
    logger.info("Logger handlers configured: %s", [type(h).__name__ for h in logger.handlers])
    logger.info("File logging enabled to: backend/logs/backend.log")

    # Run Alembic migrations
    logger.info("Running database migrations...")
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        # Continue startup even if migrations fail (tables might already exist)
        logger.warning("Continuing startup despite migration error...")

    # Create database tables (fallback for new installations without migrations)
    logger.info("Verifying database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    # Note: Default admin user is now created via Alembic migration (0294ac82fb27)
    # This ensures it's only created once during database setup, not on every startup

    logger.info("Application startup complete")
    yield

    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Middleware to ensure logging is configured in all processes (including uvicorn child processes)
@app.middleware("http")
async def configure_logging_middleware(request: Request, call_next):
    """Ensure logging is configured in child processes spawned by uvicorn --reload"""
    # Check if file handler is configured in root logger
    root = logging.getLogger()
    has_file_handler = any(isinstance(h, logging.FileHandler) for h in root.handlers)

    if not has_file_handler:
        # Re-configure logging in this process
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

        file_handler = logging.FileHandler(logs_dir / "backend.log", mode='a')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

        root.handlers.clear()
        root.addHandler(stdout_handler)
        root.addHandler(file_handler)
        root.setLevel(logging.INFO)

        # Also configure app.main logger
        main_logger = logging.getLogger("app.main")
        main_logger.handlers.clear()
        main_logger.addHandler(stdout_handler)
        main_logger.addHandler(file_handler)
        main_logger.setLevel(logging.INFO)

    response = await call_next(request)
    return response

# Add global exception handler for better error logging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log full stacktrace for all unhandled exceptions"""
    logger.error(f"Unhandled exception on {request.method} {request.url}")
    logger.error(f"Exception type: {type(exc).__name__}")
    logger.error(f"Exception message: {str(exc)}")
    logger.error(f"Full traceback:\n{traceback.format_exc()}")

    # Return 500 error to client
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc),
            "type": type(exc).__name__
        }
    )

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add session middleware for OAuth
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=3600,  # Session expires after 1 hour
    same_site="lax",
    https_only=False,  # Set to True in production
    session_cookie="session",  # Explicit cookie name
    path="/"  # Cookie available for all paths
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(airports.router, prefix="/api/v1")
app.include_router(airport_import.router, prefix="/api/v1")
app.include_router(airspace.router, prefix="/api/v1")
app.include_router(item_types.router, prefix="/api/v1")
app.include_router(missions.router, prefix="/api/v1")
app.include_router(papi_measurements.router, prefix="/api/v1")
app.include_router(runways.router, prefix="/api/v1")
app.include_router(reference_points.router, prefix="/api/v1")

# WORKAROUND: Include papi_measurements router again without /api prefix 
# to handle proxy requests that strip the /api prefix
app.include_router(papi_measurements.router, prefix="/v1")

# Mount static files for videos
videos_path = os.path.join(os.getcwd(), "data", "measurements", "videos")
if os.path.exists(videos_path):
    app.mount("/videos", StaticFiles(directory=videos_path), name="videos")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    import sys
    sys.stderr.write("=== HEALTH CHECK CALLED VIA STDERR ===\n")
    sys.stderr.flush()
    print("=== HEALTH CHECK CALLED VIA PRINT ===")
    sys.stdout.flush()
    logger.info("Health check endpoint called")
    return {"status": "healthy"}


def iterfile(file_path: str, start: int, end: int):
    """Generator to yield file chunks for streaming"""
    with open(file_path, 'rb') as file_like:
        file_like.seek(start)
        remaining = end - start + 1
        while remaining:
            chunk_size = min(8192, remaining)
            chunk = file_like.read(chunk_size)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@app.api_route("/api/v1/videos/{filename}", methods=["GET", "HEAD", "OPTIONS"])
async def stream_video(filename: str, request: Request):
    """Stream video files with proper CORS and range request support"""
    # Construct the full file path
    videos_path = os.path.join(os.getcwd(), "data", "measurements", "videos")
    file_path = os.path.join(videos_path, filename)
    
    # Security check: ensure the file is within the videos directory
    if not os.path.commonpath([videos_path, file_path]) == videos_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if file exists
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Get file size
    file_size = os.path.getsize(file_path)
    
    # Handle OPTIONS requests for CORS preflight
    if request.method == "OPTIONS":
        headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Content-Type, Authorization',
            'Access-Control-Max-Age': '86400',
        }
        return Response(content="", headers=headers)
    
    # Handle HEAD requests - return headers without body
    if request.method == "HEAD":
        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size),
            'Content-Type': 'video/mp4',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Content-Type',
        }
        return Response(content="", headers=headers, media_type='video/mp4')
    
    # Handle range requests (essential for video streaming)
    range_header = request.headers.get('range')
    
    if range_header:
        # Parse range header
        range_match = range_header.replace('bytes=', '').split('-')
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if range_match[1] else file_size - 1
        
        # Ensure valid range
        if start >= file_size or end >= file_size:
            raise HTTPException(status_code=416, detail="Range not satisfiable")
        
        # Create streaming response with partial content
        content_length = end - start + 1
        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Range': f'bytes {start}-{end}/{file_size}',
            'Content-Length': str(content_length),
            'Content-Type': 'video/mp4',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Content-Type',
        }
        
        return StreamingResponse(
            iterfile(file_path, start, end),
            status_code=206,
            headers=headers,
            media_type='video/mp4'
        )
    else:
        # Return full file
        headers = {
            'Accept-Ranges': 'bytes',
            'Content-Length': str(file_size),
            'Content-Type': 'video/mp4',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Content-Type',
        }
        
        return StreamingResponse(
            iterfile(file_path, 0, file_size - 1),
            status_code=200,
            headers=headers,
            media_type='video/mp4'
        )


# WORKAROUND: Duplicate video endpoint without /api prefix
# to handle proxy requests that strip the /api prefix
@app.api_route("/v1/videos/{filename}", methods=["GET", "HEAD", "OPTIONS"])
async def stream_video_no_api_prefix(filename: str, request: Request):
    """Stream video files with proper CORS and range request support (no /api prefix)"""
    # Reuse the same logic as stream_video
    return await stream_video(filename, request)