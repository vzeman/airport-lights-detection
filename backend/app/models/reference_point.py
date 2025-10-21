"""
Reference Point model for runway PAPI lights and touch points
"""
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.db.base import Base
import uuid


class ReferencePointType(str, enum.Enum):
    PAPI_A = "PAPI_A"
    PAPI_B = "PAPI_B"
    PAPI_C = "PAPI_C"
    PAPI_D = "PAPI_D"
    TOUCH_POINT = "TOUCH_POINT"


class ReferencePoint(Base):
    __tablename__ = "runway_reference_points"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    point_id = Column(String(100), nullable=False)  # Alternative identifier
    runway_id = Column(CHAR(36), ForeignKey("runways.id"), nullable=False)
    airport_icao_code = Column(String(4), nullable=False)  # Denormalized for easier queries
    runway_code = Column(String(20), nullable=False)  # Denormalized runway name
    point_type = Column(SQLEnum(ReferencePointType), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=True)
    elevation_wgs84 = Column(Float, nullable=True)  # WGS84 elevation
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    runway = relationship("Runway", back_populates="reference_points")