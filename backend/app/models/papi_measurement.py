"""
Database models for PAPI light measurements
"""
from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, Text, JSON, Enum as SQLEnum, Numeric
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.db.base import Base
import uuid


class PAPIReferencePointType(str, enum.Enum):
    PAPI_A = "PAPI_A"
    PAPI_B = "PAPI_B"
    PAPI_C = "PAPI_C"
    PAPI_D = "PAPI_D"
    TOUCH_POINT = "TOUCH_POINT"


class LightStatus(str, enum.Enum):
    NOT_VISIBLE = "not_visible"
    RED = "red"
    WHITE = "white"
    TRANSITION = "transition"


class PAPIReferencePoint(Base):
    __tablename__ = "reference_points"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airport_icao_code = Column(String(4), ForeignKey("airports.icao_code"), nullable=False)
    runway_code = Column(String(10), nullable=False)
    point_id = Column(String(50), nullable=False)
    latitude = Column(Numeric(precision=11, scale=8, asdecimal=True), nullable=False)  # ±90°, 8 decimals = ~1.1mm precision
    longitude = Column(Numeric(precision=12, scale=8, asdecimal=True), nullable=False)  # ±180°, 8 decimals = ~1.1mm precision
    elevation_wgs84 = Column(Float, nullable=False)
    point_type = Column(SQLEnum(PAPIReferencePointType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    airport = relationship("Airport")
    

class MeasurementSession(Base):
    __tablename__ = "measurement_sessions"

    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airport_icao_code = Column(String(4), ForeignKey("airports.icao_code"), nullable=False)
    runway_code = Column(String(10), nullable=False)
    video_file_path = Column(String(500), nullable=False)
    video_metadata = Column(JSON)  # Store drone metadata from video
    user_id = Column(CHAR(36), ForeignKey("users.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, processing, completed, error
    error_message = Column(Text)  # Store detailed error information
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    recording_date = Column(DateTime, nullable=True)  # Date when the video was recorded
    original_video_filename = Column(String(500), nullable=True)  # Original video file name

    # Progress tracking
    total_frames = Column(Integer, default=0)  # Total frames in video
    processed_frames = Column(Integer, default=0)  # Frames processed so far
    progress_percentage = Column(Float, default=0.0)  # Progress as percentage (0-100)
    current_phase = Column(String(100), default="initializing")  # current processing phase

    # Store user-adjusted light positions (x, y in %, size in % of image width for square boxes)
    # Format: {"PAPI_A": {"x": 20, "y": 50, "size": 8}, "PAPI_B": {...}, ...}
    # These positions are preserved across reprocessing operations
    light_positions = Column(JSON)

    # Markdown formatted notes about the measurement
    notes = Column(Text, nullable=True)

    # S3 Storage keys (nullable for backwards compatibility)
    storage_type = Column(String(10), default="local")  # "local" or "s3"
    original_video_s3_key = Column(String(500), nullable=True)  # S3 key for original video
    enhanced_video_s3_key = Column(String(500), nullable=True)  # S3 key for enhanced video
    enhanced_audio_video_s3_key = Column(String(500), nullable=True)  # S3 key for enhanced video with audio
    frame_measurements_s3_key = Column(String(500), nullable=True)  # S3 key for frame measurements JSON
    preview_image_s3_key = Column(String(500), nullable=True)  # S3 key for preview image
    papi_a_video_s3_key = Column(String(500), nullable=True)  # S3 key for PAPI A light video
    papi_b_video_s3_key = Column(String(500), nullable=True)  # S3 key for PAPI B light video
    papi_c_video_s3_key = Column(String(500), nullable=True)  # S3 key for PAPI C light video
    papi_d_video_s3_key = Column(String(500), nullable=True)  # S3 key for PAPI D light video

    # Relationships
    airport = relationship("Airport", back_populates="measurement_sessions")
    user = relationship("User", back_populates="measurement_sessions")
    frame_measurements = relationship("FrameMeasurement", back_populates="session", cascade="all, delete-orphan")
    

class FrameMeasurement(Base):
    __tablename__ = "frame_measurements"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(CHAR(36), ForeignKey("measurement_sessions.id"), nullable=False)
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)  # Time in seconds from video start
    
    # Drone position data
    drone_latitude = Column(Numeric(precision=11, scale=8, asdecimal=True), nullable=False)  # ±90°, 8 decimals = ~1.1mm precision
    drone_longitude = Column(Numeric(precision=12, scale=8, asdecimal=True), nullable=False)  # ±180°, 8 decimals = ~1.1mm precision
    drone_elevation = Column(Float, nullable=False)
    gimbal_pitch = Column(Float)
    gimbal_roll = Column(Float)
    gimbal_yaw = Column(Float)
    
    # Measurements for each PAPI light
    papi_a_status = Column(SQLEnum(LightStatus))
    papi_a_rgb = Column(JSON)  # {"r": 255, "g": 0, "b": 0}
    papi_a_intensity = Column(Float)
    papi_a_angle = Column(Float)  # Vertical angle from ground
    papi_a_horizontal_angle = Column(Float)  # Horizontal angle from runway centerline
    papi_a_distance_ground = Column(Float)  # Distance on ground
    papi_a_distance_direct = Column(Float)  # Direct distance to drone

    papi_b_status = Column(SQLEnum(LightStatus))
    papi_b_rgb = Column(JSON)
    papi_b_intensity = Column(Float)
    papi_b_angle = Column(Float)  # Vertical angle from ground
    papi_b_horizontal_angle = Column(Float)  # Horizontal angle from runway centerline
    papi_b_distance_ground = Column(Float)
    papi_b_distance_direct = Column(Float)

    papi_c_status = Column(SQLEnum(LightStatus))
    papi_c_rgb = Column(JSON)
    papi_c_intensity = Column(Float)
    papi_c_angle = Column(Float)  # Vertical angle from ground
    papi_c_horizontal_angle = Column(Float)  # Horizontal angle from runway centerline
    papi_c_distance_ground = Column(Float)
    papi_c_distance_direct = Column(Float)

    papi_d_status = Column(SQLEnum(LightStatus))
    papi_d_rgb = Column(JSON)
    papi_d_intensity = Column(Float)
    papi_d_angle = Column(Float)  # Vertical angle from ground
    papi_d_horizontal_angle = Column(Float)  # Horizontal angle from runway centerline
    papi_d_distance_ground = Column(Float)
    papi_d_distance_direct = Column(Float)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("MeasurementSession", back_populates="frame_measurements")


class MeasurementReport(Base):
    __tablename__ = "measurement_reports"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(CHAR(36), ForeignKey("measurement_sessions.id"), nullable=False)
    report_type = Column(String(10), nullable=False)  # "html", "pdf", "csv"
    file_path = Column(String(500), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    # Summary data
    summary_data = Column(JSON)  # Store calculated angles, transition points, etc.
    
    # Relationships
    session = relationship("MeasurementSession")