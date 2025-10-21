"""
Runway model for airports
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base


class Runway(Base):
    __tablename__ = "runways"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airport_id = Column(CHAR(36), ForeignKey("airports.id"), nullable=False)
    name = Column(String(10), nullable=False)  # e.g., "04", "22", "09L", "27R"
    heading_1 = Column(Integer, nullable=False)  # First runway heading in degrees (e.g., 40)
    heading_2 = Column(Integer, nullable=False)  # Opposite runway heading in degrees (e.g., 220)
    opposite_runway_id = Column(CHAR(36), ForeignKey("runways.id"), nullable=True)  # Reference to opposite runway end
    length = Column(Integer, nullable=False)  # Length in meters
    width = Column(Integer, nullable=False)  # Width in meters
    surface_type = Column(String(50), default="asphalt")  # asphalt, concrete, grass, etc.
    threshold_elevation = Column(Float, nullable=True)  # Elevation at threshold in meters
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    airport = relationship("Airport", back_populates="runways")
    reference_points = relationship("ReferencePoint", back_populates="runway", cascade="all, delete-orphan")
    opposite_runway = relationship("Runway", remote_side=[id], foreign_keys=[opposite_runway_id])