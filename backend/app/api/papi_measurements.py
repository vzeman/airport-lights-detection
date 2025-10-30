"""
API endpoints for PAPI light measurement workflow
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Body
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete, text
from sqlalchemy.orm.attributes import flag_modified
from typing import List, Optional, Dict, Any
import json
import os
import uuid
from datetime import datetime
from pydantic import ValidationError

from app.db.base import get_db
from app.api.auth import get_current_user
from app.core.deps import require_airport_access, require_session_access
from app.models import User, Airport, Runway, ReferencePoint, MeasurementSession
from app.models.papi_measurement import PAPIReferencePointType, LightStatus
from app.schemas.light_position import LightPositions, validate_and_normalize_light_positions
from app.services.video_processor import VideoProcessor, PAPIReportGenerator, calculate_angle, GPSExtractor
from app.services.video_s3_handler import get_video_s3_handler
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
    """Get measurement sessions - super admins see all, others see sessions from their assigned airports"""
    offset = (page - 1) * page_size

    # Build query based on user permissions
    query = select(MeasurementSession)
    count_query = select(func.count(MeasurementSession.id))

    # Filter by airport access for non-super admins
    if not current_user.is_superuser:
        # Get list of airport ICAO codes user has access to
        airport_icao_codes = [a.icao_code for a in current_user.airports]
        if not airport_icao_codes:
            # User has no airport assignments - return empty result
            return {
                "sessions": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }
        query = query.where(MeasurementSession.airport_icao_code.in_(airport_icao_codes))
        count_query = count_query.where(MeasurementSession.airport_icao_code.in_(airport_icao_codes))

    # Get total count
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
        
        # Prepare notes preview (first 100 chars)
        notes_preview = None
        if session.notes:
            notes_preview = session.notes[:100]
            if len(session.notes) > 100:
                notes_preview += "..."

        sessions_data.append({
            "id": session.id,
            "airport_icao_code": session.airport_icao_code,
            "runway_code": session.runway_code,
            "status": session.status,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "recording_date": session.recording_date.isoformat() if session.recording_date else None,
            "original_video_filename": session.original_video_filename,
            "duration_seconds": duration,
            "error_message": session.error_message,
            "has_results": session.status == "completed",
            "notes_preview": notes_preview
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

    # Check airport access - super admins can access all, others must be assigned
    if not current_user.is_superuser:
        airport_result = await db.execute(
            select(Airport).filter(Airport.icao_code == airport_icao)
        )
        airport = airport_result.scalars().first()

        if not airport:
            raise HTTPException(404, "Airport not found")

        if airport not in current_user.airports:
            raise HTTPException(403, "You do not have access to this airport")

    # Read video content
    video_content = await video.read()

    # Create session first to get session ID
    session = MeasurementSession(
        airport_icao_code=airport_icao,
        runway_code=runway_code,
        video_file_path="",  # Will be updated below
        user_id=current_user.id,
        status="pending",
        original_video_filename=video.filename
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Save video locally ONLY (fast - returns immediately)
    from pathlib import Path
    temp_dir = Path(settings.TEMP_PATH) / session.id
    temp_dir.mkdir(parents=True, exist_ok=True)
    local_path = str(temp_dir / video.filename)

    with open(local_path, 'wb') as f:
        f.write(video_content)

    logger.info(f"Saved video locally to {local_path} (size: {len(video_content) / 1024 / 1024:.2f} MB)")

    # Update session with local path
    session.video_file_path = local_path
    session.storage_type = "s3"  # Will be uploaded in background
    await db.commit()

    # Start background processing (includes S3 upload + first frame extraction)
    background_tasks.add_task(process_video_initial_with_s3_upload, session.id, local_path)

    return {
        "session_id": session.id,
        "status": "uploaded",
        "message": "Video uploaded successfully. Processing will begin shortly."
    }


@router.get("/session/{session_id}/preview")
async def get_session_preview(
    session_id: str,
    session_access: tuple = Depends(require_session_access),
    db: AsyncSession = Depends(get_db)
):
    """Get first frame preview with detected lights"""
    _, session = session_access

    # Preview images are now only in S3
    if not session.preview_image_s3_key:
        raise HTTPException(404, "Preview not yet available")

    # TEMPORARY WORKAROUND: Return backend URL instead of S3 presigned URL
    # This works around the S3 403 Forbidden issue until AWS permissions are fixed
    backend_url = f"{settings.API_BASE_URL}/api/v1/papi-measurements/preview-image/{session_id}"

    return {
        "session_id": session_id,
        "preview_url": backend_url,  # Backend proxy URL instead of S3 presigned URL
        "detected_lights": session.light_positions or {},
        "status": session.status
    }


@router.get("/preview-image/{session_id}")
async def get_preview_image(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Serve preview image directly from backend (downloads from S3 and streams)

    NOTE: This endpoint does NOT require authentication because it needs to be accessible
    from <img> tags which don't send Authorization headers. The session_id itself acts
    as an authorization token (it's a UUID that's hard to guess).
    """

    # Get session from database
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, "Session not found")

    if not session.preview_image_s3_key:
        raise HTTPException(404, "Preview image not available")

    try:
        from app.services.s3_storage import get_s3_storage
        from fastapi.responses import StreamingResponse
        import io

        s3_storage = get_s3_storage()

        # Download image from S3
        response = s3_storage.s3_client.get_object(
            Bucket=s3_storage.bucket,
            Key=session.preview_image_s3_key
        )

        # Stream the image data
        image_data = response['Body'].read()

        return StreamingResponse(
            io.BytesIO(image_data),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Disposition": f"inline; filename=preview-{session_id}.jpg"
            }
        )
    except Exception as e:
        logger.error(f"Failed to serve preview image: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(500, f"Failed to load preview image: {str(e)}")


@router.post("/session/{session_id}/confirm-lights")
async def confirm_light_positions(
    session_id: str,
    background_tasks: BackgroundTasks,
    session_access: tuple = Depends(require_session_access),
    db: AsyncSession = Depends(get_db),
    light_positions: Dict[str, Dict[str, Any]] = Body(...)
):
    """Confirm or adjust light positions and start processing"""
    _, session = session_access

    # Update light positions
    logger.info(f"=== CONFIRM LIGHTS REQUEST RECEIVED ===")
    logger.info(f"Session ID: {session_id}")
    logger.info(f"Light positions received: {light_positions}")
    logger.info(f"Current session status: {session.status}")
    logger.info(f"Current light_positions in session: {session.light_positions}")

    # Validate and normalize light positions
    try:
        normalized_positions = validate_and_normalize_light_positions(light_positions)
        logger.info(f"Light positions validated and normalized successfully")
        logger.info(f"NORMALIZED POSITIONS: {json.dumps(normalized_positions, indent=2)}")
    except ValidationError as e:
        logger.error(f"Invalid light positions format: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid light positions: {e}")

    # Update the session - use a fresh session object to ensure proper tracking
    logger.info(f"Updating session {session_id} with new light positions")
    logger.info(f"BEFORE UPDATE - session.light_positions: {session.light_positions}")

    # Create a dict copy to avoid any reference issues
    light_positions_copy = json.loads(json.dumps(normalized_positions))
    logger.info(f"Created copy of normalized positions: {json.dumps(light_positions_copy, indent=2)}")

    session.light_positions = light_positions_copy
    session.status = "processing"
    logger.info(f"AFTER ASSIGNMENT - session.light_positions: {session.light_positions}")

    # Mark JSON field as modified so SQLAlchemy knows to save it
    flag_modified(session, "light_positions")
    logger.info(f"FLAG_MODIFIED called for light_positions")

    # Commit changes
    try:
        logger.info(f"About to flush...")
        await db.flush()
        logger.info(f"AFTER FLUSH - session.light_positions: {session.light_positions}")
    except Exception as flush_error:
        logger.error(f"FLUSH FAILED: {flush_error}")
        await db.rollback()
        raise

    try:
        logger.info(f"About to commit...")
        await db.commit()
        logger.info(f"COMMIT COMPLETED")
    except Exception as commit_error:
        logger.error(f"COMMIT FAILED: {commit_error}")
        await db.rollback()
        raise

    # CRITICAL: Verify with a completely fresh database query using raw SQL
    try:
        logger.info(f"Executing RAW SQL verification query...")
        raw_query = f"SELECT light_positions FROM measurement_sessions WHERE id = '{session_id}'"
        raw_result = await db.execute(text(raw_query))
        raw_data = raw_result.fetchone()
        if raw_data and raw_data[0]:
            logger.info(f"RAW SQL VERIFICATION - light_positions from DB: {json.dumps(raw_data[0], indent=2)}")
        else:
            logger.error(f"RAW SQL VERIFICATION - No data found or NULL!")
    except Exception as raw_error:
        logger.error(f"RAW SQL VERIFICATION FAILED: {raw_error}")

    logger.info(f"Session {session_id} update process completed, starting background processing")

    # Start full video processing
    background_tasks.add_task(process_video_full, session_id)

    return {"status": "processing", "message": "Video processing started"}


@router.post("/session/{session_id}/reprocess")
async def reprocess_video(
    session_id: str,
    background_tasks: BackgroundTasks,
    session_access: tuple = Depends(require_session_access),
    db: AsyncSession = Depends(get_db)
):
    """Reprocess an existing session's video"""
    _, session = session_access

    # Reset session status
    session.status = "processing"
    session.error_message = None
    session.processed_frames = 0
    session.progress_percentage = 0.0
    session.current_phase = "initializing"

    # Clear all processed data S3 keys so frontend doesn't load old data
    session.frame_measurements_s3_key = None
    session.enhanced_video_s3_key = None
    session.enhanced_audio_video_s3_key = None
    session.papi_a_video_s3_key = None
    session.papi_b_video_s3_key = None
    session.papi_c_video_s3_key = None
    session.papi_d_video_s3_key = None

    await db.commit()

    logger.info(f"Reprocessing video for session {session_id}")

    # Start full video processing in background
    background_tasks.add_task(process_video_full, session_id)

    return {"status": "processing", "message": "Video reprocessing started"}


@router.post("/session/{session_id}/regenerate-preview")
async def regenerate_preview(
    session_id: str,
    session_access: tuple = Depends(require_session_access),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate preview image with geometric visualization"""
    _, session = session_access

    logger.warning(f"=== REGENERATE PREVIEW REQUEST RECEIVED ===")
    logger.warning(f"Session ID: {session_id}")
    logger.warning(f"Session status: {session.status}")
    logger.warning(f"Storage type: {session.storage_type}")
    logger.warning(f"Current light_positions BEFORE regeneration: {session.light_positions}")

    try:
        from pathlib import Path

        # Determine video path (local or download from S3)
        video_path = None
        cleanup_video = False

        if settings.USE_S3_STORAGE and session.original_video_s3_key:
            # Download video from S3 to temp location
            from app.services.s3_storage import get_s3_storage
            s3_storage = get_s3_storage()

            temp_video_dir = Path(settings.TEMP_PATH) / "temp-videos"
            temp_video_dir.mkdir(parents=True, exist_ok=True)
            video_path = str(temp_video_dir / f"{session_id}.mp4")

            logger.info(f"Downloading video from S3: {session.original_video_s3_key}")
            await s3_storage.download_video(session.original_video_s3_key, video_path)
            cleanup_video = True
        else:
            # Use local video path
            video_path = os.path.join(settings.DATA_PATH, "measurements", "videos", f"{session_id}.mp4")
            if not os.path.exists(video_path):
                raise HTTPException(status_code=404, detail="Video file not found")

        # Extract first frame to temp location
        preview_dir = Path(settings.TEMP_PATH) / "airport-previews"
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = str(preview_dir / f"{session_id}.jpg")

        # Extract first frame
        metadata = VideoProcessor.extract_first_frame(video_path, preview_path)

        if not metadata:
            raise HTTPException(status_code=500, detail="Failed to extract first frame")

        # ALWAYS re-extract GPS data from video to ensure we have gimbal angles
        # (session.video_metadata may have old GPS data without gimbal angles)
        gps_extractor = GPSExtractor()
        gps_data_objs = gps_extractor.extract_gps_data(video_path)
        if gps_data_objs:
            gps_data = [gp.to_dict() for gp in gps_data_objs]
            logger.info(f"Re-extracted GPS data with {len(gps_data)} points from video")
        else:
            # Fallback to session metadata if extraction fails
            gps_data = session.video_metadata.get('gps_data', []) if session.video_metadata else []
            logger.warning(f"Using GPS data from session metadata ({len(gps_data)} points)")

        # Clean up temp video if we downloaded it
        if cleanup_video and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to delete temp video: {cleanup_error}")

        # Fetch reference points for geometric matching
        ref_points_query = select(ReferencePoint).where(
            and_(
                ReferencePoint.airport_icao_code == session.airport_icao_code,
                ReferencePoint.runway_code == session.runway_code
            )
        )
        ref_points_result = await db.execute(ref_points_query)
        ref_points = ref_points_result.scalars().all()

        # Convert reference points to dict format
        ref_points_list = [
            {
                "point_id": rp.point_id,
                "latitude": float(rp.latitude),
                "longitude": float(rp.longitude),
                "elevation": float(rp.elevation_wgs84) if rp.elevation_wgs84 is not None else float(rp.altitude),
                "point_type": rp.point_type.value
            }
            for rp in ref_points
        ]

        # DEBUG: Log the reference points being passed
        logger.warning(f">>> DEBUG papi_measurements.py:440 - Passing ref_points_list to VideoProcessor.detect_lights:")
        for rp in ref_points_list:
            logger.warning(f"  {rp['point_type']}: lat={rp['latitude']}, lon={rp['longitude']}, elevation={rp['elevation']}")

        # Detect lights with geometric matching (this will add visualization)
        detected_lights = VideoProcessor.detect_lights(
            preview_path,
            ref_points_list
        )

        # Upload new preview to S3 if enabled
        if settings.USE_S3_STORAGE and os.path.exists(preview_path):
            try:
                from app.services.s3_storage import get_s3_storage
                s3_storage = get_s3_storage()
                preview_s3_key = await s3_storage.upload_preview_image(session_id, preview_path)
                session.preview_image_s3_key = preview_s3_key
                logger.info(f"Uploaded new preview image to S3: {preview_s3_key}")

                # Delete local preview after upload
                try:
                    os.remove(preview_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to delete local preview: {cleanup_error}")
            except Exception as e:
                logger.error(f"Failed to upload preview to S3: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to upload preview: {str(e)}")

        # DO NOT update light_positions here!
        # The regenerate_preview endpoint should only update the preview IMAGE, not the stored positions.
        # Manual user adjustments to light positions should be preserved for reprocessing.
        # If no positions exist yet, use the detected ones; otherwise keep existing manual positions.
        if not session.light_positions or len(session.light_positions) == 0:
            session.light_positions = detected_lights
            flag_modified(session, "light_positions")
            logger.info(f"No existing light positions - using detected positions: {detected_lights}")
        else:
            logger.info(f"Preserving existing manual light positions (not overwriting with auto-detected)")

        await db.commit()

        logger.info(f"✓ Regenerated preview for session {session_id}")
        logger.info(f"Stored light_positions preserved: {session.light_positions}")

        return {
            "status": "success",
            "message": "Preview regenerated with visualization",
            "light_positions": session.light_positions  # Return stored positions, not detected ones
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating preview: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to regenerate preview: {str(e)}")


@router.get("/session/{session_id}/status")
async def get_processing_status(
    session_id: str,
    session_access: tuple = Depends(require_session_access),
    db: AsyncSession = Depends(get_db)
):
    """Get processing status and results"""
    _, session = session_access

    # Refresh session fields to get latest progress without losing loaded attributes
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    fresh_session = result.scalar_one()

    # Use fresh_session for latest progress data
    # Update session object with fresh data for use below
    session.status = fresh_session.status
    session.processed_frames = fresh_session.processed_frames
    session.progress_percentage = fresh_session.progress_percentage
    session.current_phase = fresh_session.current_phase
    session.error_message = fresh_session.error_message

    response = {
        "session_id": session_id,
        "status": session.status,
        "total_frames": session.total_frames or 0,
        "progress_percentage": session.progress_percentage or 0.0,
        "current_phase": session.current_phase or "initializing"
    }

    if session.status == "completed":
        # Initialize S3 handler and generate presigned URLs
        s3_handler = get_video_s3_handler()

        video_type_mapping = {
            "PAPI_A": "papi_a",
            "PAPI_B": "papi_b",
            "PAPI_C": "papi_c",
            "PAPI_D": "papi_d"
        }

        video_urls = {}
        for key, video_type in video_type_mapping.items():
            video_url = s3_handler.get_video_url(session, video_type)
            if video_url:
                video_urls[key] = video_url

        response["video_urls"] = video_urls
    elif session.status == "error" and session.error_message:
        response["error_message"] = session.error_message

    return response


@router.get("/preview-image/{session_id}")
async def get_preview_image(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Serve preview image for a measurement session - returns presigned URL redirect if in S3"""
    from fastapi.responses import RedirectResponse

    # Get session from database
    result = await db.execute(
        select(MeasurementSession).where(MeasurementSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(404, "Session not found")

    # Preview images are now only in S3
    if not session.preview_image_s3_key:
        raise HTTPException(404, "Preview image not found")

    if not settings.USE_S3_STORAGE:
        raise HTTPException(500, "S3 storage is not enabled")

    from app.services.s3_storage import get_s3_storage
    s3_storage = get_s3_storage()

    try:
        presigned_url = s3_storage.generate_presigned_url(session.preview_image_s3_key)
        return RedirectResponse(url=presigned_url, status_code=307)
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for preview image: {e}")
        raise HTTPException(500, "Failed to generate preview image URL")


@router.get("/session/{session_id}/report")
async def get_measurement_report(
    session_id: str,
    session_access: tuple = Depends(require_session_access),
    db: AsyncSession = Depends(get_db)
):
    """Get measurement report data"""
    _, session = session_access

    # Get all frame measurements
    frames = []
    
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
    session_access: tuple = Depends(require_session_access)
):
    """Serve the generated HTML report for a session for download"""
    _, session = session_access
    
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
    session_access: tuple = Depends(require_session_access)
):
    """Return the HTML report content directly for embedding in the application"""
    _, session = session_access
    
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
    session_access: tuple = Depends(require_session_access)
):
    """Serve individual PAPI light video for a session - returns presigned URL redirect"""
    from fastapi.responses import RedirectResponse

    _, session = session_access

    # Validate light name
    if light_name.upper() not in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
        raise HTTPException(400, "Invalid light name")

    # Initialize S3 handler
    s3_handler = get_video_s3_handler()

    # Get presigned URL from S3
    video_url = s3_handler.get_video_url(session, light_name.lower())
    if video_url:
        return RedirectResponse(url=video_url, status_code=307)  # Temporary redirect
    else:
        raise HTTPException(404, f"PAPI light video not found: {light_name}")


@router.get("/session/{session_id}/enhanced-video")
async def get_enhanced_video(
    session_id: str,
    session_access: tuple = Depends(require_session_access)
):
    """Serve the enhanced video file for a session - returns presigned URL redirect"""
    from fastapi.responses import RedirectResponse

    _, session = session_access

    # Initialize S3 handler
    s3_handler = get_video_s3_handler()

    # Get presigned URL from S3
    video_url = s3_handler.get_video_url(session, "enhanced")
    if video_url:
        return RedirectResponse(url=video_url, status_code=307)  # Temporary redirect
    else:
        raise HTTPException(404, "Enhanced video not found in S3")


@router.get("/session/{session_id}/original-video")
async def get_original_video(
    session_id: str,
    session_access: tuple = Depends(require_session_access)
):
    """Serve the original video file for a session - returns presigned URL redirect"""
    from fastapi.responses import RedirectResponse

    _, session = session_access

    # Initialize S3 handler
    s3_handler = get_video_s3_handler()

    # Get presigned URL from S3
    video_url = s3_handler.get_video_url(session, "original")
    if video_url:
        return RedirectResponse(url=video_url, status_code=307)  # Temporary redirect
    else:
        raise HTTPException(404, "Original video not found in S3")


@router.put("/session/{session_id}/notes")
async def update_session_notes(
    session_id: str,
    request_body: Dict[str, str],
    session_access: tuple = Depends(require_session_access),
    db: AsyncSession = Depends(get_db)
):
    """Update measurement session notes (markdown supported)"""
    logger.info(f"=== PUT /session/{session_id}/notes endpoint called ===")
    logger.info(f"Request body: {request_body}")
    try:
        logger.info("Extracting session_access...")
        current_user, session_from_access = session_access
        logger.info(f"User: {current_user.email}")

        # Get notes from request body
        notes = request_body.get("notes", "")
        logger.info(f"Updating notes for session {session_id}, length: {len(notes)}")

        # Re-query the session in the current db context to avoid session persistence issues
        from app.models.papi_measurement import MeasurementSession
        from sqlalchemy import select
        result = await db.execute(
            select(MeasurementSession).filter(MeasurementSession.id == session_id)
        )
        session = result.scalars().first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Update notes
        session.notes = notes
        await db.commit()
        await db.refresh(session)

        logger.info(f"Notes updated successfully for session {session_id}")

        # Return simple response
        return {
            "status": "success",
            "message": "Notes updated successfully"
        }
    except Exception as e:
        logger.error(f"Error updating notes for session {session_id}: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to update notes: {str(e)}")


@router.get("/session/{session_id}/measurements-data")
async def get_measurements_data(
    session_id: str,
    session_access: tuple = Depends(require_session_access),
    db: AsyncSession = Depends(get_db)
):
    """Get measurement data directly in JSON format for display in the app"""
    _, session = session_access

    logger.info(f"Getting measurements data for session {session_id}")
    
    logger.info(f"Session found with status: {session.status}")

    # Initialize S3 handler
    s3_handler = get_video_s3_handler()

    # Load frame measurements from S3
    frames = []
    logger.info(f"Loading frame measurements from S3: {session.frame_measurements_s3_key}")
    measurements_data = await s3_handler.get_frame_measurements(session_id)
    if measurements_data:
        # Convert dict measurements to FrameMeasurement-like objects for compatibility
        from app.schemas.frame_measurement import parse_frame_measurements
        frames = parse_frame_measurements(measurements_data)
        logger.info(f"Loaded {len(frames)} measurements from S3")
    else:
        logger.error(f"Failed to load measurements from S3 for session {session_id}")

    # If session is not completed or has no frame measurements, return basic info with video URLs
    if session.status != "completed" or not frames:
        logger.info(f"Session {session_id} not completed or no frame data - returning basic info with video URLs")

        # Generate presigned URLs from S3
        video_type_mapping = {
            "original": "original",
            "PAPI_A": "papi_a",
            "PAPI_B": "papi_b",
            "PAPI_C": "papi_c",
            "PAPI_D": "papi_d",
            "enhanced_main": "enhanced"
        }

        video_urls = {}
        for key, video_type in video_type_mapping.items():
            video_url = s3_handler.get_video_url(session, video_type)
            if video_url:
                video_urls[key] = video_url

        summary = {
            "total_frames": 0,
            "duration": 0.0,
            "session_info": {
                "id": session.id,
                "airport_code": session.airport_icao_code,
                "runway_code": session.runway_code,
                "created_at": session.created_at.isoformat(),
                "video_file": os.path.basename(session.video_file_path),
                "recording_date": session.recording_date.isoformat() if session.recording_date else None,
                "original_video_filename": session.original_video_filename,
                "status": session.status
            }
        }
        
        logger.info(f"Returning basic info for session {session_id} with video URLs: {video_urls}")

        return {
            "summary": summary,
            "papi_data": {},
            "drone_positions": [],
            "reference_points": [],
            "runway": None,
            "video_urls": video_urls,
            "message": f"Session status: {session.status}. Video processing may still be in progress."
        }
    
    # Get runway information
    from app.models.runway import Runway
    runway_result = await db.execute(
        select(Runway).where(
            and_(
                Runway.airport_id == select(Airport.id).where(Airport.icao_code == session.airport_icao_code).scalar_subquery(),
                Runway.name == session.runway_code
            )
        )
    )
    runway_db = runway_result.scalar_one_or_none()

    # Format runway data
    runway_data = None
    if runway_db:
        runway_data = {
            "name": runway_db.name,
            "heading": runway_db.heading,
            "length": runway_db.length,
            "width": runway_db.width,
            "start_lat": runway_db.start_lat,
            "start_lon": runway_db.start_lon,
            "threshold_elevation": runway_db.threshold_elevation,
            "end_lat": runway_db.end_lat,
            "end_lon": runway_db.end_lon
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
        # Use elevation_wgs84 if available, otherwise fall back to altitude
        elevation = ref_point.elevation_wgs84 if ref_point.elevation_wgs84 is not None else ref_point.altitude
        reference_points[ref_point.point_id] = {
            "latitude": float(ref_point.latitude),  # Convert Decimal to float
            "longitude": float(ref_point.longitude),  # Convert Decimal to float
            "elevation": elevation,
            "point_type": ref_point.point_type.value,
            "nominal_angle": ref_point.nominal_angle,
            "tolerance": ref_point.tolerance
        }
    
    # Format PAPI data by grouping measurements by light
    papi_data = {
        "PAPI_A": {"timestamps": [], "statuses": [], "angles": [], "horizontal_angles": [], "distances": [], "rgb_values": [], "intensities": [], "area_values": []},
        "PAPI_B": {"timestamps": [], "statuses": [], "angles": [], "horizontal_angles": [], "distances": [], "rgb_values": [], "intensities": [], "area_values": []},
        "PAPI_C": {"timestamps": [], "statuses": [], "angles": [], "horizontal_angles": [], "distances": [], "rgb_values": [], "intensities": [], "area_values": []},
        "PAPI_D": {"timestamps": [], "statuses": [], "angles": [], "horizontal_angles": [], "distances": [], "rgb_values": [], "intensities": [], "area_values": []}
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
        
        # Add PAPI measurements (accessing nested Pydantic objects)
        papi_lights = [
            ("PAPI_A", frame.papi_a),
            ("PAPI_B", frame.papi_b),
            ("PAPI_C", frame.papi_c),
            ("PAPI_D", frame.papi_d)
        ]

        for light_name, papi_light_data in papi_lights:
            papi_data[light_name]["timestamps"].append(timestamp)

            # Extract values from nested PAPILightData object
            if papi_light_data:
                papi_data[light_name]["statuses"].append(papi_light_data.status if papi_light_data.status else "not_visible")
                papi_data[light_name]["angles"].append(papi_light_data.angle if papi_light_data.angle is not None else 0.0)
                papi_data[light_name]["horizontal_angles"].append(papi_light_data.horizontal_angle if papi_light_data.horizontal_angle is not None else 0.0)
                papi_data[light_name]["distances"].append(papi_light_data.distance_ground if papi_light_data.distance_ground is not None else 0.0)

                # Convert RGB object to array format for frontend
                if papi_light_data.rgb is not None and isinstance(papi_light_data.rgb, dict):
                    rgb_array = [papi_light_data.rgb.get('r', 0), papi_light_data.rgb.get('g', 0), papi_light_data.rgb.get('b', 0)]
                else:
                    rgb_array = [0, 0, 0]
                papi_data[light_name]["rgb_values"].append(rgb_array)
                papi_data[light_name]["intensities"].append(papi_light_data.intensity if papi_light_data.intensity is not None else 0.0)
                papi_data[light_name]["area_values"].append(papi_light_data.area_pixels if papi_light_data.area_pixels is not None else 0)
            else:
                # No data for this light
                papi_data[light_name]["statuses"].append("not_visible")
                papi_data[light_name]["angles"].append(0.0)
                papi_data[light_name]["horizontal_angles"].append(0.0)
                papi_data[light_name]["distances"].append(0.0)
                papi_data[light_name]["rgb_values"].append([0, 0, 0])
                papi_data[light_name]["intensities"].append(0.0)
                papi_data[light_name]["area_values"].append(0)
    
    # Calculate glide path angles
    # 1. Average glide path angle: average of all PAPI lights
    # 2. Middle lights glide path angle: average of middle PAPI lights
    # 3. Transition-based glide path angle: average angle when specific lights show white on left and red on right

    glide_path_angles_avg = []
    glide_path_angles_middle = []
    glide_path_angles_transition = []

    # Determine which PAPI lights are present
    papi_lights_present = [light for light in ["PAPI_A", "PAPI_B", "PAPI_C", "PAPI_D"] if light in papi_data]
    num_lights = len(papi_lights_present)

    if num_lights > 0:
        for frame_idx in range(len(frames)):
            # Collect angles for this frame
            frame_angles = []
            for light in papi_lights_present:
                angle = papi_data[light]["angles"][frame_idx]
                if angle is not None and angle != 0.0:  # Only include valid angles
                    frame_angles.append(angle)

            # Calculate average glide path angle (all lights)
            if frame_angles:
                avg_angle = sum(frame_angles) / len(frame_angles)
                glide_path_angles_avg.append(avg_angle)
            else:
                glide_path_angles_avg.append(0.0)

            # Calculate middle lights glide path angle based on number of lights
            middle_angles = []
            if num_lights == 4:
                # 4 lights: average of PAPI_B and PAPI_C
                if "PAPI_B" in papi_data and "PAPI_C" in papi_data:
                    angle_b = papi_data["PAPI_B"]["angles"][frame_idx]
                    angle_c = papi_data["PAPI_C"]["angles"][frame_idx]
                    if angle_b is not None and angle_b != 0.0:
                        middle_angles.append(angle_b)
                    if angle_c is not None and angle_c != 0.0:
                        middle_angles.append(angle_c)
            elif num_lights == 2:
                # 2 lights: average of PAPI_A and PAPI_B
                if "PAPI_A" in papi_data and "PAPI_B" in papi_data:
                    angle_a = papi_data["PAPI_A"]["angles"][frame_idx]
                    angle_b = papi_data["PAPI_B"]["angles"][frame_idx]
                    if angle_a is not None and angle_a != 0.0:
                        middle_angles.append(angle_a)
                    if angle_b is not None and angle_b != 0.0:
                        middle_angles.append(angle_b)
            elif num_lights >= 8:
                # 8 lights: average of PAPI_B, PAPI_C, PAPI_F, PAPI_G
                for light in ["PAPI_B", "PAPI_C", "PAPI_F", "PAPI_G"]:
                    if light in papi_data:
                        angle = papi_data[light]["angles"][frame_idx]
                        if angle is not None and angle != 0.0:
                            middle_angles.append(angle)

            if middle_angles:
                middle_avg = sum(middle_angles) / len(middle_angles)
                glide_path_angles_middle.append(middle_avg)
            else:
                glide_path_angles_middle.append(0.0)

            # Calculate transition-based glide path angle
            # Look for frames where left light is white and right light is red
            transition_angle = None

            if num_lights == 2:
                # 2 lights: PAPI_A white and PAPI_B red
                if "PAPI_A" in papi_data and "PAPI_B" in papi_data:
                    status_a = papi_data["PAPI_A"]["statuses"][frame_idx]
                    status_b = papi_data["PAPI_B"]["statuses"][frame_idx]
                    if status_a == "WHITE" and status_b == "RED":
                        angle_a = papi_data["PAPI_A"]["angles"][frame_idx]
                        angle_b = papi_data["PAPI_B"]["angles"][frame_idx]
                        if angle_a and angle_b and angle_a != 0.0 and angle_b != 0.0:
                            transition_angle = (angle_a + angle_b) / 2

            elif num_lights == 4:
                # 4 lights: PAPI_B white and PAPI_C red
                if "PAPI_B" in papi_data and "PAPI_C" in papi_data:
                    status_b = papi_data["PAPI_B"]["statuses"][frame_idx]
                    status_c = papi_data["PAPI_C"]["statuses"][frame_idx]
                    if status_b == "WHITE" and status_c == "RED":
                        angle_b = papi_data["PAPI_B"]["angles"][frame_idx]
                        angle_c = papi_data["PAPI_C"]["angles"][frame_idx]
                        if angle_b and angle_c and angle_b != 0.0 and angle_c != 0.0:
                            transition_angle = (angle_b + angle_c) / 2

            elif num_lights >= 8:
                # 8 lights: (PAPI_B white and PAPI_C red) AND (PAPI_F white and PAPI_G red)
                if all(light in papi_data for light in ["PAPI_B", "PAPI_C", "PAPI_F", "PAPI_G"]):
                    status_b = papi_data["PAPI_B"]["statuses"][frame_idx]
                    status_c = papi_data["PAPI_C"]["statuses"][frame_idx]
                    status_f = papi_data["PAPI_F"]["statuses"][frame_idx]
                    status_g = papi_data["PAPI_G"]["statuses"][frame_idx]

                    if (status_b == "WHITE" and status_c == "RED" and
                        status_f == "WHITE" and status_g == "RED"):
                        angles = []
                        for light in ["PAPI_B", "PAPI_C", "PAPI_F", "PAPI_G"]:
                            angle = papi_data[light]["angles"][frame_idx]
                            if angle and angle != 0.0:
                                angles.append(angle)
                        if angles:
                            transition_angle = sum(angles) / len(angles)

            glide_path_angles_transition.append(transition_angle if transition_angle else 0.0)

    # Find touch point by point_type (not by point_id)
    touch_point_ref = None
    for point_id, point_data in reference_points.items():
        if point_data.get('point_type') == 'TOUCH_POINT':
            touch_point_ref = point_data
            break

    # Calculate touch point angles at specific positions for each algorithm
    touch_point_at_avg_all = 0.0
    touch_point_at_avg_middle = 0.0
    touch_point_at_transition = 0.0

    if touch_point_ref and len(frames) > 0:
        # For "All Lights" algorithm: find frame where avg angle is closest to nominal (typically 3.0°)
        nominal_gp = 3.0
        if glide_path_angles_avg:
            valid_avg_angles = [(idx, angle) for idx, angle in enumerate(glide_path_angles_avg) if angle != 0.0]
            if valid_avg_angles:
                # Find frame closest to nominal angle
                closest_idx = min(valid_avg_angles, key=lambda x: abs(x[1] - nominal_gp))[0]
                frame = frames[closest_idx]
                drone_data = {
                    'latitude': frame.drone_latitude,
                    'longitude': frame.drone_longitude,
                    'elevation': frame.drone_elevation
                }
                touch_point_at_avg_all = calculate_angle(drone_data, touch_point_ref)

        # For "Middle Lights" algorithm: find frame where middle avg angle is closest to nominal
        if glide_path_angles_middle:
            valid_middle_angles = [(idx, angle) for idx, angle in enumerate(glide_path_angles_middle) if angle != 0.0]
            if valid_middle_angles:
                closest_idx = min(valid_middle_angles, key=lambda x: abs(x[1] - nominal_gp))[0]
                frame = frames[closest_idx]
                drone_data = {
                    'latitude': frame.drone_latitude,
                    'longitude': frame.drone_longitude,
                    'elevation': frame.drone_elevation
                }
                touch_point_at_avg_middle = calculate_angle(drone_data, touch_point_ref)

        # For "Transition-Based" algorithm: find frame where transition occurs
        if glide_path_angles_transition:
            valid_transition_angles = [(idx, angle) for idx, angle in enumerate(glide_path_angles_transition) if angle != 0.0]
            if valid_transition_angles:
                # Use the first transition frame (or middle if multiple)
                transition_idx = valid_transition_angles[len(valid_transition_angles) // 2][0]
                frame = frames[transition_idx]
                drone_data = {
                    'latitude': frame.drone_latitude,
                    'longitude': frame.drone_longitude,
                    'elevation': frame.drone_elevation
                }
                touch_point_at_transition = calculate_angle(drone_data, touch_point_ref)

    # Format summary data
    summary = {
        "total_frames": len(frames),
        "duration": frames[-1].timestamp - frames[0].timestamp if len(frames) > 1 else 0.0,
        "session_info": {
            "id": session.id,
            "airport_code": session.airport_icao_code,
            "runway_code": session.runway_code,
            "created_at": session.created_at.isoformat(),
            "video_file": os.path.basename(session.video_file_path),
            "recording_date": session.recording_date.isoformat() if session.recording_date else None,
            "original_video_filename": session.original_video_filename,
            "notes": session.notes  # Full notes for detail view
        },
        "glide_path_angles": {
            "average_all_lights": glide_path_angles_avg,
            "average_middle_lights": glide_path_angles_middle,
            "transition_based": glide_path_angles_transition,
            "touch_point_at_avg_all": touch_point_at_avg_all,
            "touch_point_at_avg_middle": touch_point_at_avg_middle,
            "touch_point_at_transition": touch_point_at_transition,
            "num_lights": num_lights
        }
    }
    
    # Generate presigned URLs from S3 for completed sessions
    video_type_mapping = {
        "original": "original",
        "PAPI_A": "papi_a",
        "PAPI_B": "papi_b",
        "PAPI_C": "papi_c",
        "PAPI_D": "papi_d",
        "enhanced_main": "enhanced"
    }

    video_urls = {}
    for key, video_type in video_type_mapping.items():
        video_url = s3_handler.get_video_url(session, video_type)
        if video_url:
            video_urls[key] = video_url

    logger.info(f"Returning video URLs for completed session {session_id}: {video_urls}")

    return {
        "summary": summary,
        "papi_data": papi_data,
        "drone_positions": drone_positions,
        "reference_points": reference_points,
        "runway": runway_data,
        "video_urls": video_urls
    }


# Background processing functions (these would be in a separate service file)
async def process_video_initial_with_s3_upload(session_id: str, video_path: str):
    """Upload video to S3, then extract first frame and detect lights"""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.base import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            # Get session from database
            result = await db.execute(
                select(MeasurementSession).where(MeasurementSession.id == session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                return

            # Update progress: uploading to S3
            session.current_phase = "uploading_to_s3"
            session.progress_percentage = 5.0
            await db.commit()

            # Upload to S3 in background (non-blocking for user)
            logger.info(f"Starting S3 upload for session {session_id}")
            s3_handler = get_video_s3_handler()
            s3_key = await s3_handler.s3.upload_video(
                session_id=session_id,
                file_path=video_path,
                video_type="original"
            )

            # Update session with S3 key
            if s3_key:
                session.original_video_s3_key = s3_key
                session.storage_type = "s3"
                await db.commit()
                logger.info(f"Uploaded video to S3: {s3_key}")

        except Exception as e:
            logger.error(f"Error uploading to S3: {e}")
            # Continue processing even if S3 upload fails
            import traceback
            logger.error(traceback.format_exc())

    # Continue with first frame extraction
    await process_video_initial(session_id, video_path)


async def process_video_initial(session_id: str, video_path: str):
    """Extract first frame and detect lights (called after S3 upload)"""
    import asyncio
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.base import AsyncSessionLocal
    from app.services.video_processor import GPSExtractor

    async with AsyncSessionLocal() as db:
        try:
            # Get session from database
            result = await db.execute(
                select(MeasurementSession).where(MeasurementSession.id == session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                return

            # Extract first frame and save preview to tmp folder
            from pathlib import Path
            preview_dir = Path(settings.TEMP_PATH) / "airport-previews"
            preview_dir.mkdir(parents=True, exist_ok=True)
            preview_path = str(preview_dir / f"{session_id}.jpg")

            # Update progress: extracting first frame
            session.current_phase = "extracting_first_frame"
            session.progress_percentage = 10.0
            await db.commit()

            metadata = VideoProcessor.extract_first_frame(video_path, preview_path)

            if metadata:
                # Extract and store recording date
                recording_date = VideoProcessor.extract_recording_date(video_path)
                if recording_date:
                    session.recording_date = recording_date
                    logger.info(f"Extracted recording date: {recording_date}")

                # Update progress: extracting GPS data
                session.current_phase = "extracting_gps_data"
                session.progress_percentage = 30.0
                await db.commit()

                # Extract GPS data from video and store in metadata
                gps_extractor = GPSExtractor()
                gps_data = gps_extractor.extract_gps_data(video_path)

                if gps_data:
                    logger.info(f"Extracted {len(gps_data)} GPS points during initial processing")
                    # Convert GPS data to serializable format
                    metadata['gps_data'] = [gp.to_dict() for gp in gps_data]
                else:
                    logger.warning("No GPS data found in video during initial processing")
                    metadata['gps_data'] = []

                # Update progress: detecting lights
                session.current_phase = "detecting_lights"
                session.progress_percentage = 60.0
                session.total_frames = metadata.get('total_frames', 0)
                await db.commit()

                # Fetch reference points for this runway to enable geometric matching
                ref_points_query = select(ReferencePoint).where(
                    and_(
                        ReferencePoint.airport_icao_code == session.airport_icao_code,
                        ReferencePoint.runway_code == session.runway_code
                    )
                )
                ref_points_result = await db.execute(ref_points_query)
                ref_points = ref_points_result.scalars().all()

                # Convert reference points to dict format
                ref_points_list = [
                    {
                        "point_id": rp.point_id,
                        "latitude": float(rp.latitude),
                        "longitude": float(rp.longitude),
                        "elevation": float(rp.elevation_wgs84) if rp.elevation_wgs84 is not None else float(rp.altitude),
                        "point_type": rp.point_type.value
                    }
                    for rp in ref_points
                ]

                # Detect lights in the first frame
                detected_lights = VideoProcessor.detect_lights(
                    preview_path,
                    ref_points_list
                )

                # Upload preview image to S3 if enabled (after light detection is complete)
                if settings.USE_S3_STORAGE and os.path.exists(preview_path):
                    try:
                        from app.services.s3_storage import get_s3_storage
                        s3_storage = get_s3_storage()
                        preview_s3_key = await s3_storage.upload_preview_image(session_id, preview_path)
                        session.preview_image_s3_key = preview_s3_key
                        logger.info(f"Uploaded preview image to S3: {preview_s3_key}")

                        # Delete local preview image after successful S3 upload
                        try:
                            os.remove(preview_path)
                            logger.info(f"Deleted local preview image: {preview_path}")
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to delete local preview image: {cleanup_error}")
                    except Exception as e:
                        logger.error(f"Failed to upload preview image to S3: {e}")

                # Update session with metadata (including GPS) and detected lights
                session.video_metadata = metadata
                session.light_positions = detected_lights
                flag_modified(session, "light_positions")
                session.status = "preview_ready"
                session.current_phase = "preview_ready"
                session.progress_percentage = 100.0

                await db.commit()
        except Exception as e:
            logger.error(f"Error processing video initial: {e}")
            import traceback
            logger.error(traceback.format_exc())
            if session:
                session.status = "error"
                session.error_message = f"Failed to process video: {str(e)}"
                await db.commit()


async def process_video_full(session_id: str):
    """Process entire video and extract measurements"""
    import asyncio
    import cv2
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.db.base import AsyncSessionLocal
    from app.services.video_processor import GPSExtractor

    async with AsyncSessionLocal() as db:
        try:
            # Get session from database with manually confirmed light positions
            logger.info(f"========== process_video_full STARTED ==========")
            logger.info(f"Creating NEW database session to load session_id: {session_id}")

            result = await db.execute(
                select(MeasurementSession).where(MeasurementSession.id == session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                logger.error(f"Session {session_id} not found in database!")
                return

            if not session.light_positions:
                logger.error(f"Session {session_id} has NO light positions!")
                return

            # Log the manually confirmed light positions that will be used
            logger.info(f"========== LOADED SESSION FROM DATABASE ==========")
            logger.info(f"Session ID: {session_id}")
            logger.info(f"FULL light_positions JSON from DB: {json.dumps(session.light_positions, indent=2)}")
            logger.info(f"Using MANUALLY CONFIRMED light positions from database:")
            for light_name, pos in session.light_positions.items():
                if light_name in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                    logger.info(f"  {light_name}: x={pos.get('x', 'N/A')}%, y={pos.get('y', 'N/A')}%, width={pos.get('width', 'N/A')}%, height={pos.get('height', 'N/A')}%")
            logger.info(f"=================================================")

            # Initialize progress tracking
            session.current_phase = "processing_frames"
            session.progress_percentage = 0.0
            session.processed_frames = 0
            await db.commit()

            # Determine video path - download from S3 if needed
            video_path = session.video_file_path
            temp_video_path = None

            if session.storage_type == "s3" and session.original_video_s3_key:
                # Video is in S3, download to temp location for processing
                import os
                import tempfile
                from pathlib import Path
                from app.services.s3_storage import get_s3_storage

                s3_storage = get_s3_storage()
                temp_dir = Path(settings.TEMP_PATH) / session_id
                temp_dir.mkdir(parents=True, exist_ok=True)
                temp_video_path = str(temp_dir / "original_video.mp4")

                logger.info(f"Downloading video from S3: {session.original_video_s3_key}")
                try:
                    await s3_storage.download_video(session.original_video_s3_key, temp_video_path)
                    video_path = temp_video_path
                    logger.info(f"Video downloaded to temporary path: {video_path}")
                except Exception as e:
                    logger.error(f"Failed to download video from S3: {e}")
                    raise ValueError(f"Failed to download video from S3 for processing: {e}")

            # Open video file
            cap = cv2.VideoCapture(video_path)
            total_frames = session.total_frames or int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Initialize PAPI light tracker with manually selected positions
            # The tracker will START from manual positions and TRACK them as they move through frames
            from app.services.video_processor import PAPILightTracker
            logger.info(f"Initializing PAPI light tracker with manually selected positions")
            logger.info(f"Manual light positions (percentage): {session.light_positions}")

            light_tracker = PAPILightTracker(session.light_positions, frame_width, frame_height)
            logger.info(f"Light tracker initialized - will track manually selected lights across frames")

            # Get GPS data from session metadata (extracted during initial processing)
            real_gps_data = []
            if session.video_metadata and 'gps_data' in session.video_metadata:
                # Reconstruct GPSData objects from stored dictionaries
                from app.services.video_processor import GPSData
                real_gps_data = [
                    GPSData(
                        timestamp_ms=gp['timestamp_ms'],
                        latitude=gp['latitude'],
                        longitude=gp['longitude'],
                        altitude=gp['altitude'],
                        speed=gp.get('speed'),
                        heading=gp.get('heading'),
                        satellites=gp.get('satellites'),
                        accuracy=gp.get('accuracy'),
                        frame_number=gp.get('frame_number')
                    )
                    for gp in session.video_metadata['gps_data']
                ]
                logger.info(f"Loaded {len(real_gps_data)} GPS data points from session metadata")

            fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30  # Get FPS for GPS interpolation

            if not real_gps_data:
                raise ValueError(
                    "No GPS data found in video. Video must contain GPS telemetry data for PAPI measurement processing. "
                    "Supported formats: DJI SRT file, embedded GPS metadata (via exiftool), or standard GPS tags. "
                    f"Video path: {session.video_file_path}"
                )

            # Fetch reference points ONCE before processing (includes PAPI lights and TOUCH_POINT)
            from app.models import Airport, Runway

            # Fetch runway information including heading
            runway_query = select(Runway).join(
                Airport, Runway.airport_id == Airport.id
            ).where(
                and_(
                    Airport.icao_code == session.airport_icao_code,
                    Runway.name == session.runway_code
                )
            )
            runway_result = await db.execute(runway_query)
            runway = runway_result.scalar_one_or_none()

            if not runway:
                raise ValueError(
                    f"Runway {session.runway_code} not found for airport {session.airport_icao_code}. "
                    "Please ensure the runway is configured in the database."
                )

            runway_heading = float(runway.heading)
            logger.info(f"Loaded runway {session.runway_code} with heading: {runway_heading}°")

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
                    "elevation": float(rp.elevation_wgs84) if rp.elevation_wgs84 else (float(rp.altitude) if rp.altitude else 0.0),
                    "nominal_angle": float(rp.nominal_angle) if rp.nominal_angle is not None else None,
                    "tolerance": float(rp.tolerance) if rp.tolerance is not None else None
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

            # Initialize S3 handler for storing results
            s3_handler = get_video_s3_handler()

            # Collect frame measurements in memory (not database)
            frame_measurements_list = []

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
                            "ref_points": ref_points_dict,
                            "runway_heading": runway_heading
                        }
                
                # Raise exception if no real GPS data is available
                if not drone_data:
                    raise ValueError(f"No GPS data available for frame {frame_number}. Video must contain GPS telemetry data for processing.")

                # Update light positions using tracking
                # Tracker starts from manually selected positions and follows lights across frames
                tracked_positions = light_tracker.update_frame(frame, frame_number)

                # Save refined positions back to database after first frame (frame 0)
                if frame_number == 0:
                    # Extract refined positions from tracker
                    refined_positions = {}
                    for light_name in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                        if light_name in tracked_positions:
                            pos = tracked_positions[light_name]
                            # Convert pixel coordinates back to percentages
                            refined_positions[light_name] = {
                                'x': (pos['x'] / frame.shape[1]) * 100,
                                'y': (pos['y'] / frame.shape[0]) * 100,
                                'size': (pos['size'] / frame.shape[1]) * 100,
                                'confidence': pos.get('confidence', 1.0)
                            }

                    # Update session with refined positions
                    session.light_positions = refined_positions
                    flag_modified(session, "light_positions")
                    await db.commit()
                    logger.info(f"Saved refined PAPI light positions to database for session {session_id}")

                # Process frame with tracked positions (which started from manual positions)
                measurements = VideoProcessor.process_frame(
                    frame, tracked_positions, drone_data, ref_points_dict
                )

                # Collect frame measurement in memory (will be saved to S3/DB later)
                frame_data = {
                    "session_id": session_id,
                    "frame_number": frame_number,
                    "timestamp": frame_number / 30.0,  # Assuming 30fps
                    "drone_latitude": float(drone_data["latitude"]),
                    "drone_longitude": float(drone_data["longitude"]),
                    "drone_elevation": drone_data["elevation"]
                }

                # Add PAPI measurements
                for light_name in ["papi_a", "papi_b", "papi_c", "papi_d"]:
                    light_key = light_name.upper().replace("_", "_")
                    if light_key in measurements:
                        data = measurements[light_key]
                        frame_data[f"{light_name}_status"] = data["status"]
                        frame_data[f"{light_name}_rgb"] = data["rgb"]
                        frame_data[f"{light_name}_intensity"] = data["intensity"]
                        frame_data[f"{light_name}_angle"] = data["angle"]
                        frame_data[f"{light_name}_horizontal_angle"] = data.get("horizontal_angle")
                        frame_data[f"{light_name}_distance_ground"] = data["distance_ground"]
                        frame_data[f"{light_name}_distance_direct"] = data["distance_direct"]

                        # Extract area_pixels from tracked_positions evaluation_area
                        if light_key in tracked_positions:
                            eval_area = tracked_positions[light_key].get('evaluation_area', {})
                            frame_data[f"{light_name}_area_pixels"] = eval_area.get('area_pixels', 0)
                        else:
                            frame_data[f"{light_name}_area_pixels"] = 0

                frame_measurements_list.append(frame_data)
                frame_number += 1

                # Update progress every 10 frames
                if frame_number % 10 == 0:
                    session.processed_frames = frame_number
                    if total_frames > 0:
                        session.progress_percentage = min(80.0, (frame_number / total_frames) * 75.0)  # Reserve 20% for video generation and finalization
                    await db.commit()
            
            cap.release()

            logger.info(f"Collected {len(frame_measurements_list)} frame measurements in memory")

            # Save frame measurements to S3 as compressed JSON
            session.current_phase = "uploading_measurements_to_s3"
            session.progress_percentage = 80.0
            await db.commit()

            s3_key = await s3_handler.save_frame_measurements(session_id, frame_measurements_list)
            if s3_key:
                session.frame_measurements_s3_key = s3_key
                logger.info(f"Saved {len(frame_measurements_list)} measurements to S3: {s3_key}")
            else:
                raise Exception("Failed to upload frame measurements to S3")
            await db.commit()

            # Update progress: preparing data
            session.current_phase = "preparing_data"
            session.progress_percentage = 82.0
            await db.commit()

            # Convert to format expected by video processor and report generator
            measurements_data = []
            drone_telemetry = []

            for m in frame_measurements_list:
                frame_data = {
                    'timestamp': m['timestamp'] * 1000,  # Convert to milliseconds
                    'PAPI_A': {
                        'status': m.get('papi_a_status'),
                        'rgb': m.get('papi_a_rgb'),
                        'intensity': m.get('papi_a_intensity'),
                        'angle': m.get('papi_a_angle'),
                        'horizontal_angle': m.get('papi_a_horizontal_angle'),
                        'distance_ground': m.get('papi_a_distance_ground'),
                        'distance_direct': m.get('papi_a_distance_direct')
                    },
                    'PAPI_B': {
                        'status': m.get('papi_b_status'),
                        'rgb': m.get('papi_b_rgb'),
                        'intensity': m.get('papi_b_intensity'),
                        'angle': m.get('papi_b_angle'),
                        'horizontal_angle': m.get('papi_b_horizontal_angle'),
                        'distance_ground': m.get('papi_b_distance_ground'),
                        'distance_direct': m.get('papi_b_distance_direct')
                    },
                    'PAPI_C': {
                        'status': m.get('papi_c_status'),
                        'rgb': m.get('papi_c_rgb'),
                        'intensity': m.get('papi_c_intensity'),
                        'angle': m.get('papi_c_angle'),
                        'horizontal_angle': m.get('papi_c_horizontal_angle'),
                        'distance_ground': m.get('papi_c_distance_ground'),
                        'distance_direct': m.get('papi_c_distance_direct')
                    },
                    'PAPI_D': {
                        'status': m.get('papi_d_status'),
                        'rgb': m.get('papi_d_rgb'),
                        'intensity': m.get('papi_d_intensity'),
                        'angle': m.get('papi_d_angle'),
                        'horizontal_angle': m.get('papi_d_horizontal_angle'),
                        'distance_ground': m.get('papi_d_distance_ground'),
                        'distance_direct': m.get('papi_d_distance_direct')
                    }
                }
                measurements_data.append(frame_data)

                # Extract real drone telemetry data for each frame
                drone_frame_data = {
                    'frame_number': m['frame_number'],
                    'timestamp': m['timestamp'],
                    'latitude': m['drone_latitude'],
                    'longitude': m['drone_longitude'],
                    'elevation': m['drone_elevation'],
                    'altitude': m['drone_elevation'],  # Alias for compatibility
                    'gimbal_pitch': m.get('gimbal_pitch'),
                    'gimbal_roll': m.get('gimbal_roll'),
                    'gimbal_yaw': m.get('gimbal_yaw'),
                    'heading': m.get('gimbal_yaw') if m.get('gimbal_yaw') else 0.0,
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

                # Use tmp folder for video generation
                video_output_dir = Path(settings.TEMP_PATH) / "videos" / session_id
                video_generator = PAPIVideoGenerator(str(video_output_dir), progress_callback=update_progress)

                # Log light positions being passed to video generators
                logger.info(f"========== GENERATING PAPI VIDEOS ==========")
                logger.info(f"Passing manually confirmed light positions to video generator:")
                for light_name, pos in session.light_positions.items():
                    if light_name in ['PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D']:
                        logger.info(f"  {light_name}: {pos}")
                logger.info(f"============================================")

                # Generate individual PAPI light videos with angle information
                # Use video_path which is either the original local path or the S3 downloaded temp path
                papi_video_paths = video_generator.generate_papi_videos(
                    video_path, session_id, session.light_positions, measurements_data, ref_points_dict
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

                    # Use video_path which is either the original local path or the S3 downloaded temp path
                    enhanced_main_video_path = video_generator.generate_enhanced_main_video(
                        video_path, session_id, session.light_positions, measurements_data,
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

                # Update progress: videos generated, uploading to S3
                session.current_phase = "uploading_videos_to_s3"
                session.progress_percentage = 93.0
                await db.commit()

                # Upload enhanced videos to S3
                if enhanced_main_video_path:
                    enhanced_s3_key = await s3_handler.save_processed_video(
                        session_id=session_id,
                        video_path=enhanced_main_video_path,
                        video_type="enhanced"
                    )
                    if enhanced_s3_key:
                        session.enhanced_video_s3_key = enhanced_s3_key
                        logger.info(f"Uploaded enhanced video to S3: {enhanced_s3_key}")
                    else:
                        raise Exception("Failed to upload enhanced video to S3")

                # Upload individual PAPI light videos to S3
                for papi_name, papi_video_path in papi_video_paths.items():
                    if papi_video_path:
                        try:
                            papi_s3_key = await s3_handler.save_processed_video(
                                session_id=session_id,
                                video_path=papi_video_path,
                                video_type=papi_name.lower()  # "papi_a", "papi_b", etc.
                            )
                            if papi_s3_key:
                                # Store S3 key in session
                                setattr(session, f"{papi_name.lower()}_video_s3_key", papi_s3_key)
                                logger.info(f"Uploaded {papi_name} video to S3: {papi_s3_key}")
                        except Exception as papi_upload_error:
                            logger.warning(f"Failed to upload {papi_name} video to S3: {papi_upload_error}")

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

            # Clean up local files (all videos now in S3)
            session.current_phase = "cleaning_up_local_files"
            session.progress_percentage = 99.0
            await db.commit()

            # Collect all video files to clean up
            files_to_delete = [session.video_file_path]  # Original video
            if temp_video_path:  # Add temporary S3 download if it exists
                files_to_delete.append(temp_video_path)
            if enhanced_main_video_path:
                files_to_delete.append(enhanced_main_video_path)
            # Add PAPI light videos
            for papi_video_path in papi_video_paths.values():
                if papi_video_path:
                    files_to_delete.append(papi_video_path)

            s3_handler.cleanup_local_files(session_id, *files_to_delete)
            logger.info(f"Cleaned up {len(files_to_delete)} local video files for session {session_id}")

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

            # Clean up temp video file if it was downloaded from S3
            if temp_video_path:
                try:
                    import os
                    if os.path.exists(temp_video_path):
                        os.remove(temp_video_path)
                        logger.info(f"Cleaned up temporary video file: {temp_video_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up temporary video file: {cleanup_error}")

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