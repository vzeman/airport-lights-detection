"""
Runway model for airports
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import math

from app.db.base import Base


class Runway(Base):
    __tablename__ = "runways"
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airport_id = Column(CHAR(36), ForeignKey("airports.id"), nullable=False)
    name = Column(String(10), nullable=False)  # e.g., "04", "22", "09L", "27R"
    heading = Column(Float, nullable=False)  # Runway heading in degrees (0-360, can include decimals)
    opposite_runway_id = Column(CHAR(36), ForeignKey("runways.id"), nullable=True)  # Reference to opposite runway end
    length = Column(Integer, nullable=False)  # Length in meters
    width = Column(Integer, nullable=False)  # Width in meters
    surface_type = Column(String(50), default="asphalt")  # asphalt, concrete, grass, etc.
    threshold_elevation = Column(Float, nullable=True)  # Elevation at threshold in meters
    start_lat = Column(Float, nullable=True)  # GPS latitude of runway start point
    start_lon = Column(Float, nullable=True)  # GPS longitude of runway start point
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    airport = relationship("Airport", back_populates="runways")
    reference_points = relationship("ReferencePoint", back_populates="runway", cascade="all, delete-orphan")
    opposite_runway = relationship("Runway", remote_side=[id], foreign_keys=[opposite_runway_id])

    @property
    def end_lat(self) -> float | None:
        """Calculate end latitude from start position, heading, and length"""
        if self.start_lat is None or self.start_lon is None or self.length is None:
            return None
        return self._calculate_end_coordinates()[0]

    @property
    def end_lon(self) -> float | None:
        """Calculate end longitude from start position, heading, and length"""
        if self.start_lat is None or self.start_lon is None or self.length is None:
            return None
        return self._calculate_end_coordinates()[1]

    def _calculate_end_coordinates(self) -> tuple[float, float]:
        """
        Calculate end coordinates from start position, heading, and length.
        Uses the Haversine formula to compute the destination point.

        Returns:
            tuple[float, float]: (end_latitude, end_longitude)
        """
        # Earth's radius in meters
        R = 6371000

        # Convert to radians
        lat1 = math.radians(self.start_lat)
        lon1 = math.radians(self.start_lon)
        bearing = math.radians(self.heading)

        # Distance in meters
        d = self.length

        # Calculate end latitude
        lat2 = math.asin(
            math.sin(lat1) * math.cos(d / R) +
            math.cos(lat1) * math.sin(d / R) * math.cos(bearing)
        )

        # Calculate end longitude
        lon2 = lon1 + math.atan2(
            math.sin(bearing) * math.sin(d / R) * math.cos(lat1),
            math.cos(d / R) - math.sin(lat1) * math.sin(lat2)
        )

        # Convert back to degrees
        return (math.degrees(lat2), math.degrees(lon2))