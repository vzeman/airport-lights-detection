from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from contextlib import asynccontextmanager
import logging
import os
import stat
from pathlib import Path

from app.core.config import settings
from app.api import auth, users, airports, airport_import, airspace, item_types, missions, papi_measurements, runways, reference_points
from app.db.base import engine, Base

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting up...")
    # Create tables (in production, use Alembic migrations instead)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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