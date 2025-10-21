"""
API endpoints for PAPI light measurement workflow
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional, Dict, Any
import json
import os
import uuid
from datetime import datetime

from app.db.session import get_db
from app.api.auth import get_current_user
from app.models import User, Airport, Runway, ReferencePoint, MeasurementSession, FrameMeasurement
from app.models.papi_measurement import PAPIReferencePointType, LightStatus
from app.services.video_processor import VideoProcessor, PAPIReportGenerator
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/papi-measurements", tags=["PAPI Measurements"])


@router.get("/sessions")
async def get_measurement_sessions(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all measurement sessions for the current user"""
    offset = (page - 1) * page_size
    
    query = select(MeasurementSession).where(MeasurementSession.user_id == current_user.id)
    
    # Get total count
    count_query = select(func.count(MeasurementSession.id)).where(MeasurementSession.user_id == current_user.id)
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Get sessions with pagination, ordered by creation date (newest first)
    sessions_query = query.order_by(MeasurementSession.created_at.desc()).offset(offset).limit(page_size)
    sessions_result = await db.execute(sessions_query)
    sessions = sessions_result.scalars().all()
    
    sessions_data = []
    for session in sessions:
        # Calculate video duration from metadata if available
        duration = None
        if session.video_metadata:
            try:
                fps = session.video_metadata.get('fps')
                total_frames = session.video_metadata.get('total_frames')
                if fps and total_frames and fps > 0:
                    duration = total_frames / fps
            except (TypeError, KeyError, ZeroDivisionError):
                # Fallback to processing duration if video metadata is invalid
                if session.completed_at and session.created_at:
                    duration = (session.completed_at - session.created_at).total_seconds()
        elif session.completed_at and session.created_at:
            # Fallback to processing duration if no video metadata
            duration = (session.completed_at - session.created_at).total_seconds()
        
        sessions_data.append({
            "id": session.id,
            "airport_icao_code": session.airport_icao_code,
            "runway_code": session.runway_code,
            "status": session.status,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "duration_seconds": duration,
            "error_message": session.error_message,
            "has_results": session.status == "completed"
        })
    
    return {
        "sessions": sessions_data,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/airports-with-runways")
async def get_airports_with_runways(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all airports with their runways for measurement selection"""
    query = select(Airport).where(Airport.is_active == True)
    
    # Filter by user's airports if not superuser
    if not current_user.is_superuser:
        user_airport_ids = [a.id for a in current_user.airports]
        query = query.where(Airport.id.in_(user_airport_ids))
    
    result = await db.execute(query)
    airports = result.scalars().all()
    
    airport_data = []
    for airport in airports:
        runways_query = select(Runway).where(
            and_(Runway.airport_id == airport.id, Runway.is_active == True)
        )
        runways_result = await db.execute(runways_query)
        runways = runways_result.scalars().all()
        
        airport_data.append({
            "icao_code": airport.icao_code,
            "name": airport.name,
            "runways": [{"code": r.name, "id": r.id} for r in runways]
        })
    
    return airport_data


@router.get("/reference-points/{airport_icao}/{runway_code}")
async def get_reference_points(
    airport_icao: str,
    runway_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get reference points for a specific runway"""
    result = await db.execute(
        select(ReferencePoint).where(
            and_(
                ReferencePoint.airport_icao_code == airport_icao,
                ReferencePoint.runway_code == runway_code
            )
        )
    )
    points = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "point_id": p.point_id,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "elevation": p.elevation_wgs84,
            "type": p.point_type
        }
        for p in points
    ]


@router.post("/reference-points")
async def create_or_update_reference_points(
    airport_icao: str = Form(...),
    runway_code: str = Form(...),
    points: str = Form(...),  # JSON string of points
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update reference points for a runway"""
    points_data = json.loads(points)
    
    # Delete existing points for this runway
    await db.execute(
        select(ReferencePoint).where(
            and_(
                ReferencePoint.airport_icao_code == airport_icao,
                ReferencePoint.runway_code == runway_code
            )
        ).delete()
    )
    
    # Create new points
    for point in points_data:
        ref_point = ReferencePoint(
            airport_icao_code=airport_icao,
            runway_code=runway_code,
            point_id=point["point_id"],
            latitude=point["latitude"],
            longitude=point["longitude"],
            elevation_wgs84=point["elevation"],
            point_type=PAPIReferencePointType(point["type"])
        )
        db.add(ref_point)
    
    await db.commit()
    return {"status": "success", "message": "Reference points updated"}


@router.post("/upload-video")
async def upload_measurement_video(
    background_tasks: BackgroundTasks,
    airport_icao: str = Form(...),
    runway_code: str = Form(...),
    video: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload video for PAPI measurement"""
    
    # Validate file type
    if not video.filename.lower().endswith(('.mp4', '.mov', '.avi')):
        raise HTTPException(400, "Invalid video format")
    
    # Create upload directory
    upload_dir = f"data/measurements/{airport_icao}/{runway_code}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save video file
    file_id = str(uuid.uuid4())
    file_ext = video.filename.split('.')[-1]
    file_path = f"{upload_dir}/{file_id}.{file_ext}"
    
    with open(file_path, "wb") as f:
        content = await video.read()
        f.write(content)
    
    # Create measurement session
    session = MeasurementSession(
        airport_icao_code=airport_icao,
        runway_code=runway_code,
        video_file_path=file_path,
        user_id=current_user.id,
        status="pending"
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    # Start background processing
    background_tasks.add_task(process_video_initial, session.id, file_path)
    
    return {
        "session_id": session.id,
        "status": "uploaded",
        "message": "Video uploaded successfully. Processing will begin shortly."
    }


@router.get("/session/{session_id}/preview")
async def get_session_preview(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get first frame preview with detected lights"""
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Check authorization
    if not current_user.is_superuser and session.user_id != current_user.id:
        raise HTTPException(403, "Not authorized")
    
    # Get preview data - check both relative and absolute paths
    preview_path = f"data/measurements/previews/{session_id}.jpg"
    if not os.path.exists(preview_path):
        backend_preview_path = f"backend/data/measurements/previews/{session_id}.jpg"
        if os.path.exists(backend_preview_path):
            preview_path = backend_preview_path
        else:
            raise HTTPException(404, "Preview not yet available")
    
    return {
        "session_id": session_id,
        "preview_url": f"/papi-measurements/preview-image/{session_id}",
        "detected_lights": session.light_positions or {},
        "status": session.status
    }


@router.post("/session/{session_id}/confirm-lights")
async def confirm_light_positions(
    session_id: str,
    light_positions: Dict[str, Dict[str, Any]],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Confirm or adjust light positions and start processing"""
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Update light positions
    session.light_positions = light_positions
    session.status = "processing"
    await db.commit()
    
    # Start full video processing
    background_tasks.add_task(process_video_full, session_id)
    
    return {"status": "processing", "message": "Video processing started"}


@router.get("/session/{session_id}/status")
async def get_processing_status(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get processing status and results"""
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Get frame count if processing
    frame_count = 0
    if session.status in ["processing", "completed"]:
        count_result = await db.execute(
            select(func.count(FrameMeasurement.id)).where(FrameMeasurement.session_id == session_id)
        )
        frame_count = count_result.scalar()
    
    response = {
        "session_id": session_id,
        "status": session.status,
        "frames_processed": frame_count,
        "total_frames": session.total_frames or 0,
        "progress_percentage": session.progress_percentage or 0.0,
        "current_phase": session.current_phase or "initializing"
    }
    
    if session.status == "completed":
        response["video_urls"] = {
            "PAPI_A": f"{settings.API_BASE_URL}/api/v1/videos/{session_id}_papi_a_light.mp4",
            "PAPI_B": f"{settings.API_BASE_URL}/api/v1/videos/{session_id}_papi_b_light.mp4", 
            "PAPI_C": f"{settings.API_BASE_URL}/api/v1/videos/{session_id}_papi_c_light.mp4",
            "PAPI_D": f"{settings.API_BASE_URL}/api/v1/videos/{session_id}_papi_d_light.mp4",
        }
    elif session.status == "error" and session.error_message:
        response["error_message"] = session.error_message
    
    return response


@router.get("/preview-image/{session_id}")
async def get_preview_image(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Serve preview image for a measurement session"""
    preview_path = f"data/measurements/previews/{session_id}.jpg"
    
    if not os.path.exists(preview_path):
        backend_preview_path = f"backend/data/measurements/previews/{session_id}.jpg"
        if os.path.exists(backend_preview_path):
            preview_path = backend_preview_path
        else:
            raise HTTPException(404, "Preview image not found")
    
    return FileResponse(preview_path, media_type="image/jpeg")


@router.get("/session/{session_id}/report")
async def get_measurement_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get measurement report data"""
    # Get all frame measurements
    result = await db.execute(
        select(FrameMeasurement)
        .where(FrameMeasurement.session_id == session_id)
        .order_by(FrameMeasurement.frame_number)
    )
    frames = result.scalars().all()
    
    if not frames:
        raise HTTPException(404, "No measurement data found")
    
    # Prepare report data
    report_data = {
        "session_id": session_id,
        "total_frames": len(frames),
        "papi_a": [],
        "papi_b": [],
        "papi_c": [],
        "papi_d": [],
        "timestamps": []
    }
    
    for frame in frames:
        report_data["timestamps"].append(frame.timestamp)
        
        for light in ["papi_a", "papi_b", "papi_c", "papi_d"]:
            light_data = {
                "status": getattr(frame, f"{light}_status"),
                "rgb": getattr(frame, f"{light}_rgb"),
                "intensity": getattr(frame, f"{light}_intensity"),
                "angle": getattr(frame, f"{light}_angle"),
                "distance_ground": getattr(frame, f"{light}_distance_ground"),
                "distance_direct": getattr(frame, f"{light}_distance_direct")
            }
            report_data[light].append(light_data)
    
    return report_data


@router.get("/session/{session_id}/html-report")
async def get_html_report(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Serve the generated HTML report for a session for download"""
    # Verify session exists
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Check if session is completed
    if session.status != "completed":
        raise HTTPException(400, "Report not yet available")
    
    # Look for HTML report file (find the most recent one for this session)
    import glob
    report_pattern = f"data/measurements/reports/papi_report_{session_id}_*.html"
    report_files = glob.glob(report_pattern)
    
    if not report_files:
        raise HTTPException(404, "HTML report not found")
    
    # Get the most recent report file
    report_path = max(report_files, key=os.path.getctime)
    
    return FileResponse(
        report_path, 
        media_type="text/html",
        filename=f"papi_measurement_report_{session_id}.html"
    )


@router.get("/session/{session_id}/html-report-content")
async def get_html_report_content(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Return the HTML report content directly for embedding in the application"""
    # Verify session exists
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Check if session is completed
    if session.status != "completed":
        raise HTTPException(400, "Report not yet available")
    
    # Look for HTML report file (find the most recent one for this session)
    import glob
    report_pattern = f"data/measurements/reports/papi_report_{session_id}_*.html"
    report_files = glob.glob(report_pattern)
    
    if not report_files:
        raise HTTPException(404, "HTML report not found")
    
    # Get the most recent report file
    report_path = max(report_files, key=os.path.getctime)
    
    # Read the HTML content
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Return the HTML content directly
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content, status_code=200)
    except Exception as e:
        raise HTTPException(500, f"Error reading report file: {str(e)}")



@router.get("/session/{session_id}/papi-video/{light_name}")
async def get_papi_light_video(
    session_id: str,
    light_name: str,
    db: AsyncSession = Depends(get_db)
):
    """Serve individual PAPI light video for a session"""
    # Verify session exists
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Validate light name
    if light_name.upper() not in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
        raise HTTPException(400, "Invalid light name")
    
    # Look for video file - check both relative and absolute paths
    video_filename = f"{session_id}_{light_name.lower()}_light.mp4"
    video_path = f"data/measurements/videos/{video_filename}"
    
    # Try absolute path from current directory first
    if not os.path.exists(video_path):
        # Try relative to backend directory
        backend_video_path = f"backend/data/measurements/videos/{video_filename}"
        if os.path.exists(backend_video_path):
            video_path = backend_video_path
        else:
            raise HTTPException(404, f"PAPI light video not found: {video_filename}")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=video_filename
    )


@router.get("/session/{session_id}/enhanced-video")
async def get_enhanced_video(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Serve the enhanced video file for a session"""
    # Look for enhanced video file - check both relative and absolute paths
    enhanced_video_filename = f"{session_id}_enhanced_main_video.mp4"
    enhanced_video_path = f"data/measurements/videos/{enhanced_video_filename}"
    
    # Try relative to backend directory if not found
    if not os.path.exists(enhanced_video_path):
        backend_enhanced_path = f"backend/data/measurements/videos/{enhanced_video_filename}"
        if os.path.exists(backend_enhanced_path):
            enhanced_video_path = backend_enhanced_path
    
    if os.path.exists(enhanced_video_path):
        return FileResponse(
            enhanced_video_path,
            media_type="video/mp4",
            filename=enhanced_video_filename
        )
    else:
        # Fallback to original video
        result = await db.execute(
            select(MeasurementSession).where(MeasurementSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(404, "Session not found")
        
        video_path = session.video_file_path
        
        if not os.path.exists(video_path):
            raise HTTPException(404, "Video file not found")
        
        video_filename = os.path.basename(video_path)
        
        return FileResponse(
            video_path,
            media_type="video/mp4", 
            filename=video_filename
        )


@router.get("/session/{session_id}/original-video")
async def get_original_video(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Serve the original video file for a session"""
    # Verify session exists
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    # Get the original video path from the session
    video_path = session.video_file_path
    
    if not os.path.exists(video_path):
        raise HTTPException(404, "Original video file not found")
    
    # Extract filename from path for the response
    video_filename = os.path.basename(video_path)
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=video_filename
    )


@router.get("/session/{session_id}/measurements-data")
async def get_measurements_data(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get measurement data directly in JSON format for display in the app"""
    
    logger.info(f"Getting measurements data for session {session_id}, user {current_user.id}")
    
    # Verify session exists and belongs to current user
    result = await db.execute(
        select(MeasurementSession).where(
            and_(
                MeasurementSession.id == session_id,
                MeasurementSession.user_id == current_user.id
            )
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        logger.warning(f"Session {session_id} not found for user {current_user.id}")
        raise HTTPException(404, "Session not found")
    
    logger.info(f"Session found with status: {session.status}")
    
    # Get all frame measurements for this session
    frames_result = await db.execute(
        select(FrameMeasurement)
        .where(FrameMeasurement.session_id == session_id)
        .order_by(FrameMeasurement.frame_number)
    )
    frames = frames_result.scalars().all()
    
    # If session is not completed or has no frame measurements, return basic info with video URLs
    if session.status != "completed" or not frames:
        logger.info(f"Session {session_id} not completed or no frame data - returning basic info with video URLs")
        
        # Check which video files actually exist
        videos_dir = os.path.join(os.getcwd(), "data", "measurements", "videos")
        video_files = {
            "PAPI_A": f"{session_id}_papi_a_light.mp4",
            "PAPI_B": f"{session_id}_papi_b_light.mp4", 
            "PAPI_C": f"{session_id}_papi_c_light.mp4",
            "PAPI_D": f"{session_id}_papi_d_light.mp4",
            "enhanced_main": f"{session_id}_enhanced_main_video.mp4"
        }
        
        video_urls = {}
        for key, filename in video_files.items():
            file_path = os.path.join(videos_dir, filename)
            if os.path.exists(file_path):
                video_urls[key] = f"{settings.API_BASE_URL}/api/v1/videos/{filename}"
        
        summary = {
            "total_frames": 0,
            "duration": 0.0,
            "session_info": {
                "id": session.id,
                "airport_code": session.airport_icao_code,
                "runway_code": session.runway_code,
                "created_at": session.created_at.isoformat(),
                "video_file": os.path.basename(session.video_file_path),
                "status": session.status
            }
        }
        
        logger.info(f"Returning basic info for session {session_id} with video URLs: {video_urls}")
        
        return {
            "summary": summary,
            "papi_data": {},
            "drone_positions": [],
            "reference_points": [],
            "video_urls": video_urls,
            "message": f"Session status: {session.status}. Video processing may still be in progress."
        }
    
    # Get reference points
    ref_result = await db.execute(
        select(ReferencePoint).where(
            and_(
                ReferencePoint.airport_icao_code == session.airport_icao_code,
                ReferencePoint.runway_code == session.runway_code
            )
        )
    )
    reference_points_db = ref_result.scalars().all()
    
    # Format reference points
    reference_points = {}
    for ref_point in reference_points_db:
        reference_points[ref_point.point_id] = {
            "latitude": ref_point.latitude,
            "longitude": ref_point.longitude,
            "elevation": ref_point.elevation_wgs84,
            "point_type": ref_point.point_type.value
        }
    
    # Format PAPI data by grouping measurements by light
    papi_data = {
        "PAPI_A": {"timestamps": [], "statuses": [], "angles": [], "distances": [], "rgb_values": []},
        "PAPI_B": {"timestamps": [], "statuses": [], "angles": [], "distances": [], "rgb_values": []},
        "PAPI_C": {"timestamps": [], "statuses": [], "angles": [], "distances": [], "rgb_values": []},
        "PAPI_D": {"timestamps": [], "statuses": [], "angles": [], "distances": [], "rgb_values": []}
    }
    
    # Format drone positions
    drone_positions = []
    
    for frame in frames:
        timestamp = frame.timestamp
        
        # Add drone position
        drone_positions.append({
            "frame": frame.frame_number,
            "timestamp": timestamp,
            "latitude": frame.drone_latitude,
            "longitude": frame.drone_longitude,
            "elevation": frame.drone_elevation,
            "gimbal_pitch": frame.gimbal_pitch,
            "gimbal_roll": frame.gimbal_roll,
            "gimbal_yaw": frame.gimbal_yaw
        })
        
        # Add PAPI measurements
        papi_lights = [
            ("PAPI_A", frame.papi_a_status, frame.papi_a_angle, frame.papi_a_distance_ground, frame.papi_a_rgb),
            ("PAPI_B", frame.papi_b_status, frame.papi_b_angle, frame.papi_b_distance_ground, frame.papi_b_rgb),
            ("PAPI_C", frame.papi_c_status, frame.papi_c_angle, frame.papi_c_distance_ground, frame.papi_c_rgb),
            ("PAPI_D", frame.papi_d_status, frame.papi_d_angle, frame.papi_d_distance_ground, frame.papi_d_rgb)
        ]
        
        for light_name, status, angle, distance, rgb in papi_lights:
            papi_data[light_name]["timestamps"].append(timestamp)
            papi_data[light_name]["statuses"].append(status.value if status else "not_visible")
            papi_data[light_name]["angles"].append(angle if angle is not None else 0.0)
            papi_data[light_name]["distances"].append(distance if distance is not None else 0.0)
            # Convert RGB object to array format for frontend
            if rgb is not None and isinstance(rgb, dict):
                rgb_array = [rgb.get('r', 0), rgb.get('g', 0), rgb.get('b', 0)]
            else:
                rgb_array = [0, 0, 0]
            papi_data[light_name]["rgb_values"].append(rgb_array)
    
    # Format summary data
    summary = {
        "total_frames": len(frames),
        "duration": frames[-1].timestamp - frames[0].timestamp if len(frames) > 1 else 0.0,
        "session_info": {
            "id": session.id,
            "airport_code": session.airport_icao_code,
            "runway_code": session.runway_code,
            "created_at": session.created_at.isoformat(),
            "video_file": os.path.basename(session.video_file_path)
        }
    }
    
    # Check which video files actually exist for completed sessions
    videos_dir = os.path.join(os.getcwd(), "data", "measurements", "videos")
    video_files = {
        "PAPI_A": f"{session_id}_papi_a_light.mp4",
        "PAPI_B": f"{session_id}_papi_b_light.mp4", 
        "PAPI_C": f"{session_id}_papi_c_light.mp4",
        "PAPI_D": f"{session_id}_papi_d_light.mp4",
        "enhanced_main": f"{session_id}_enhanced_main_video.mp4"
    }
    
    video_urls = {}
    for key, filename in video_files.items():
        file_path = os.path.join(videos_dir, filename)
        if os.path.exists(file_path):
            video_urls[key] = f"{settings.API_BASE_URL}/api/v1/videos/{filename}"
    
    logger.info(f"Returning video URLs for completed session {session_id}: {video_urls}")
    
    return {
        "summary": summary,
        "papi_data": papi_data,
        "drone_positions": drone_positions,
        "reference_points": reference_points,
        "video_urls": video_urls
    }


# Background processing functions (these would be in a separate service file)
async def process_video_initial(session_id: str, video_path: str):
    """Extract first frame and detect lights"""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.session import async_session
    
    async with async_session() as db:
        try:
            # Get session from database
            result = await db.execute(
                select(MeasurementSession).where(MeasurementSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                return
            
            # Extract first frame and save preview
            preview_dir = "data/measurements/previews"
            os.makedirs(preview_dir, exist_ok=True)
            preview_path = f"{preview_dir}/{session_id}.jpg"
            
            # Update progress: extracting first frame
            session.current_phase = "extracting_first_frame"
            session.progress_percentage = 10.0
            await db.commit()
            
            metadata = VideoProcessor.extract_first_frame(video_path, preview_path)
            
            if metadata:
                # Update progress: detecting lights
                session.current_phase = "detecting_lights"
                session.progress_percentage = 50.0
                session.total_frames = metadata.get('total_frames', 0)
                await db.commit()
                
                # Detect lights in the first frame
                detected_lights = VideoProcessor.detect_lights(preview_path, [])
                
                # Update session with metadata and detected lights
                session.video_metadata = metadata
                session.light_positions = detected_lights
                session.status = "preview_ready"
                session.current_phase = "preview_ready"
                session.progress_percentage = 100.0
                
                await db.commit()
        except Exception as e:
            logger.error(f"Error processing video initial: {e}")
            if session:
                session.status = "error"
                session.error_message = f"Failed to extract first frame: {str(e)}"
                await db.commit()


async def process_video_full(session_id: str):
    """Process entire video and extract measurements"""
    import asyncio
    import cv2
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.session import async_session
    from app.services.video_processor import GPSExtractor
    
    async with async_session() as db:
        try:
            # Get session from database
            result = await db.execute(
                select(MeasurementSession).where(MeasurementSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session or not session.light_positions:
                return
            
            # Initialize progress tracking
            session.current_phase = "processing_frames"
            session.progress_percentage = 0.0
            session.processed_frames = 0
            await db.commit()
            
            # Open video file
            cap = cv2.VideoCapture(session.video_file_path)
            total_frames = session.total_frames or int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Initialize PAPI light tracker for dynamic position tracking
            from app.services.video_processor import PAPILightTracker
            light_tracker = PAPILightTracker(session.light_positions, frame_width, frame_height)
            
            # Extract real GPS data from video file
            gps_extractor = GPSExtractor()
            real_gps_data = gps_extractor.extract_gps_data(session.video_file_path)
            fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30  # Get FPS for GPS interpolation
            
            if real_gps_data:
                logger.info(f"Successfully extracted {len(real_gps_data)} GPS data points from video")
            else:
                raise ValueError("No GPS data found in video. Video must contain GPS telemetry data for PAPI measurement processing.")

            # Fetch reference points ONCE before processing (includes PAPI lights and TOUCH_POINT)
            from app.models import Airport, Runway
            ref_points_query = select(ReferencePoint).join(
                Runway, ReferencePoint.runway_id == Runway.id
            ).join(
                Airport, Runway.airport_id == Airport.id
            ).where(
                and_(
                    Airport.icao_code == session.airport_icao_code,
                    Runway.name == session.runway_code
                )
            )
            ref_points_result = await db.execute(ref_points_query)
            ref_points = ref_points_result.scalars().all()

            # Create reference points lookup (includes PAPI_A, PAPI_B, PAPI_C, PAPI_D, TOUCH_POINT)
            ref_points_dict = {}
            for rp in ref_points:
                ref_points_dict[rp.point_type.value] = {
                    "latitude": float(rp.latitude),
                    "longitude": float(rp.longitude),
                    "elevation": float(rp.elevation_wgs84) if rp.elevation_wgs84 else (float(rp.altitude) if rp.altitude else 0.0)
                }

            # Validate that we have the required reference points
            required_points = ["PAPI_A", "PAPI_B", "PAPI_C", "PAPI_D"]
            missing_points = [pt for pt in required_points if pt not in ref_points_dict]
            if missing_points:
                raise ValueError(
                    f"Missing required reference points: {', '.join(missing_points)}. "
                    f"Please configure GPS coordinates for all PAPI lights in the database."
                )

            logger.info(f"Loaded {len(ref_points_dict)} reference points: {list(ref_points_dict.keys())}")

            frame_number = 0

            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Extract real GPS data for this frame
                drone_data = None
                if real_gps_data:
                    gps_extractor = GPSExtractor()
                    interpolated_gps = gps_extractor.interpolate_gps_for_frame(real_gps_data, frame_number, fps)
                    if interpolated_gps:
                        drone_data = {
                            "elevation": interpolated_gps.altitude,
                            "latitude": interpolated_gps.latitude,
                            "longitude": interpolated_gps.longitude,
                            "speed": interpolated_gps.speed or 0.0,
                            "heading": interpolated_gps.heading or 0.0,
                            "ref_points": ref_points_dict
                        }
                
                # Raise exception if no real GPS data is available
                if not drone_data:
                    raise ValueError(f"No GPS data available for frame {frame_number}. Video must contain GPS telemetry data for processing.")
                
                # Update light positions using dynamic tracking (same as PAPI videos)
                tracked_positions = light_tracker.update_frame(frame, frame_number)
                
                # Process frame with dynamically tracked positions
                measurements = VideoProcessor.process_frame(
                    frame, tracked_positions, drone_data, ref_points_dict
                )
                
                # Save frame measurements to database
                frame_measurement = FrameMeasurement(
                    session_id=session_id,
                    frame_number=frame_number,
                    timestamp=frame_number / 30.0,  # Assuming 30fps
                    drone_latitude=drone_data["latitude"],
                    drone_longitude=drone_data["longitude"],
                    drone_elevation=drone_data["elevation"]
                )
                
                # Add PAPI measurements
                for light_name in ["papi_a", "papi_b", "papi_c", "papi_d"]:
                    light_key = light_name.upper().replace("_", "_")
                    if light_key in measurements:
                        data = measurements[light_key]
                        setattr(frame_measurement, f"{light_name}_status", data["status"])
                        setattr(frame_measurement, f"{light_name}_rgb", data["rgb"])
                        setattr(frame_measurement, f"{light_name}_intensity", data["intensity"])
                        setattr(frame_measurement, f"{light_name}_angle", data["angle"])
                        setattr(frame_measurement, f"{light_name}_distance_ground", data["distance_ground"])
                        setattr(frame_measurement, f"{light_name}_distance_direct", data["distance_direct"])
                
                db.add(frame_measurement)
                frame_number += 1
                
                # Update progress every 10 frames
                if frame_number % 10 == 0:
                    session.processed_frames = frame_number
                    if total_frames > 0:
                        session.progress_percentage = min(80.0, (frame_number / total_frames) * 75.0)  # Reserve 20% for video generation and finalization
                    await db.commit()
            
            cap.release()
            
            # Get all frame measurements for this session (needed for both video generation and reporting)
            measurements_query = select(FrameMeasurement).where(
                FrameMeasurement.session_id == session_id
            ).order_by(FrameMeasurement.frame_number)
            measurements_result = await db.execute(measurements_query)
            measurements = measurements_result.scalars().all()

            # Update progress: preparing data
            session.current_phase = "preparing_data"
            session.progress_percentage = 82.0
            await db.commit()

            # Convert to format expected by video processor and report generator
            measurements_data = []
            drone_telemetry = []
            
            for m in measurements:
                frame_data = {
                    'timestamp': m.timestamp * 1000,  # Convert to milliseconds
                    'PAPI_A': {
                        'status': m.papi_a_status,
                        'rgb': m.papi_a_rgb,
                        'intensity': m.papi_a_intensity,
                        'angle': m.papi_a_angle,
                        'distance_ground': m.papi_a_distance_ground,
                        'distance_direct': m.papi_a_distance_direct
                    },
                    'PAPI_B': {
                        'status': m.papi_b_status,
                        'rgb': m.papi_b_rgb,
                        'intensity': m.papi_b_intensity,
                        'angle': m.papi_b_angle,
                        'distance_ground': m.papi_b_distance_ground,
                        'distance_direct': m.papi_b_distance_direct
                    },
                    'PAPI_C': {
                        'status': m.papi_c_status,
                        'rgb': m.papi_c_rgb,
                        'intensity': m.papi_c_intensity,
                        'angle': m.papi_c_angle,
                        'distance_ground': m.papi_c_distance_ground,
                        'distance_direct': m.papi_c_distance_direct
                    },
                    'PAPI_D': {
                        'status': m.papi_d_status,
                        'rgb': m.papi_d_rgb,
                        'intensity': m.papi_d_intensity,
                        'angle': m.papi_d_angle,
                        'distance_ground': m.papi_d_distance_ground,
                        'distance_direct': m.papi_d_distance_direct
                    }
                }
                measurements_data.append(frame_data)
                
                # Extract real drone telemetry data for each frame
                drone_frame_data = {
                    'frame_number': m.frame_number,
                    'timestamp': m.timestamp,
                    'latitude': m.drone_latitude,
                    'longitude': m.drone_longitude,
                    'elevation': m.drone_elevation,
                    'altitude': m.drone_elevation,  # Alias for compatibility
                    'gimbal_pitch': m.gimbal_pitch,
                    'gimbal_roll': m.gimbal_roll,
                    'gimbal_yaw': m.gimbal_yaw,
                    'heading': m.gimbal_yaw if m.gimbal_yaw else 0.0,  # Use gimbal yaw as heading approximation
                    'speed': 0.0  # Speed not available in current data model
                }
                drone_telemetry.append(drone_frame_data)

            # Update progress: preparing videos
            session.current_phase = "preparing_videos"
            session.progress_percentage = 85.0
            await db.commit()

            # Update progress: generating PAPI light videos
            session.current_phase = "generating_papi_videos"
            session.progress_percentage = 87.0
            await db.commit()
            
            # Generate individual PAPI light videos and enhanced main video
            papi_video_paths = {}
            enhanced_main_video_path = ""
            try:
                from app.services.video_processor import PAPIVideoGenerator

                # Define progress callback to update database
                async def update_progress_async(percentage: float, message: str):
                    """Update session progress in database"""
                    try:
                        session.progress_percentage = percentage
                        session.current_phase = message
                        await db.flush()  # Use flush() instead of commit() to avoid transaction conflicts
                        logger.info(f"Progress update: {percentage:.1f}% - {message}")
                    except Exception as e:
                        logger.warning(f"Failed to update progress: {e}")

                def update_progress(percentage: float, message: str):
                    """Synchronous wrapper for progress updates"""
                    # Schedule the async update
                    import asyncio
                    try:
                        asyncio.create_task(update_progress_async(percentage, message))
                    except RuntimeError:
                        # If no event loop, just log
                        logger.info(f"Progress: {percentage:.1f}% - {message}")

                video_generator = PAPIVideoGenerator("data/measurements/videos", progress_callback=update_progress)
                
                # Generate individual PAPI light videos with angle information
                papi_video_paths = video_generator.generate_papi_videos(
                    session.video_file_path, session_id, session.light_positions, measurements_data
                )
                logger.info(f"Generated {len(papi_video_paths)} PAPI light videos")

                # Update progress: PAPI videos generated
                session.current_phase = "generating_enhanced_video"
                session.progress_percentage = 92.0
                await db.commit()

                # Generate enhanced main video with drone position overlays and PAPI light rectangles
                try:
                    logger.info(f"Starting enhanced video generation for session {session_id}")
                    logger.info(f"Reference points available: {list(ref_points_dict.keys())}")
                    logger.info(f"Measurements data frames: {len(measurements_data) if measurements_data else 0}")

                    enhanced_main_video_path = video_generator.generate_enhanced_main_video(
                        session.video_file_path, session_id, session.light_positions, measurements_data,
                        drone_telemetry, ref_points_dict  # real drone telemetry, reference_points
                    )
                    if enhanced_main_video_path:
                        logger.info(f"Generated enhanced main video: {enhanced_main_video_path}")
                    else:
                        error_msg = "Enhanced main video generation returned empty path"
                        logger.error(error_msg)
                        session.error_message = error_msg
                        await db.commit()
                except Exception as enhanced_error:
                    error_msg = f"Enhanced video generation failed: {str(enhanced_error)}"
                    logger.error(error_msg)
                    import traceback
                    logger.error(f"Enhanced video traceback: {traceback.format_exc()}")
                    session.error_message = error_msg
                    await db.commit()

                # Update progress: videos generated, storing to database
                session.current_phase = "storing_results"
                session.progress_percentage = 95.0
                await db.commit()

            except Exception as video_error:
                logger.warning(f"Failed to generate PAPI videos: {video_error}")
                import traceback
                logger.warning(f"Video generation traceback: {traceback.format_exc()}")

            # Update progress: finalizing
            session.current_phase = "completing"
            session.progress_percentage = 98.0
            await db.commit()
            
            # HTML report generation removed - data is now displayed directly in the app
            logger.info(f"Video processing completed for session {session_id}. Data available via API.")
            
            # Update session status
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            session.current_phase = "completed"
            session.progress_percentage = 100.0
            session.processed_frames = frame_number
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error processing video full: {e}")
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Full traceback: {error_details}")
            if session:
                try:
                    await db.rollback()
                    session.status = "error"
                    session.error_message = f"Video processing failed: {str(e)}\n\nDetails:\n{error_details}"
                    await db.commit()
                except Exception as commit_error:
                    logger.error(f"Failed to update session error status: {commit_error}")
                    try:
                        await db.rollback()
                    except Exception:
                        pass