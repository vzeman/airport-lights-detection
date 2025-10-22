from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Integer, Enum, Numeric
from sqlalchemy.dialects.mysql import CHAR, LONGTEXT
from sqlalchemy.orm import relationship
# from geoalchemy2 import Geometry  # Commented out for SQLite compatibility
from datetime import datetime
import uuid
import enum

from app.db.base import Base


class ComplianceFramework(str, enum.Enum):
    ICAO = "ICAO"
    FAA = "FAA"
    EASA = "EASA"
    LOCAL = "LOCAL"


class Airport(Base):
    __tablename__ = 'airports'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    icao_code = Column(String(4), unique=True, nullable=False, index=True)
    iata_code = Column(String(3), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    full_name = Column(String(500), nullable=True)
    
    # Location
    latitude = Column(Numeric(precision=11, scale=8, asdecimal=True), nullable=False)  # ±90°, 8 decimals = ~1.1mm precision
    longitude = Column(Numeric(precision=12, scale=8, asdecimal=True), nullable=False)  # ±180°, 8 decimals = ~1.1mm precision
    elevation = Column(Float, nullable=True)  # in meters
    timezone = Column(String(50), nullable=False, default='UTC')
    country = Column(String(100), nullable=False)
    city = Column(String(100), nullable=True)
    
    # Operational details
    operational_hours = Column(JSON, nullable=True)  # JSON with daily schedules
    runway_count = Column(Integer, default=0)
    terminal_count = Column(Integer, default=0)
    
    # Compliance
    compliance_framework = Column(Enum(ComplianceFramework), default=ComplianceFramework.ICAO)
    
    # Configuration
    settings = Column(JSON, nullable=True)  # Airport-specific settings
    inspection_schedule = Column(JSON, nullable=True)  # Default inspection schedules
    notification_settings = Column(JSON, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Geometry (boundary polygon)
    # boundary = Column(Geometry('POLYGON'), nullable=True)  # Commented out for SQLite compatibility
    boundary = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(CHAR(36), ForeignKey('users.id'), nullable=True)
    
    # Relationships
    users = relationship("User", secondary="user_airports", back_populates="airports")
    created_by_user = relationship("User", back_populates="created_airports", foreign_keys=[created_by])
    items = relationship("AirportItem", back_populates="airport", cascade="all, delete-orphan")
    runways = relationship("Runway", back_populates="airport", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="airport", cascade="all, delete-orphan")
    measurement_sessions = relationship("MeasurementSession", back_populates="airport", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Airport {self.icao_code}: {self.name}>"


class ItemType(Base):
    __tablename__ = 'item_types'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(100), nullable=False)  # e.g., 'lighting', 'marking', 'navigation', 'infrastructure'
    subcategory = Column(String(100), nullable=True)
    
    # ICAO compliance reference
    icao_reference = Column(String(255), nullable=True)
    requirements = Column(JSON, nullable=True)  # Inspection requirements, tolerances, etc.
    
    # Default properties for this type
    default_properties = Column(JSON, nullable=True)
    
    # Inspection configuration
    inspection_frequency_days = Column(Integer, default=30)
    inspection_procedures = Column(JSON, nullable=True)
    
    # Visualization
    icon = Column(String(100), nullable=True)
    default_color = Column(String(7), nullable=True)  # Hex color for map display
    
    # Templates
    flight_template = Column(JSON, nullable=True)  # Default flight path template for this item type
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    items = relationship("AirportItem", back_populates="item_type")
    maintenance_tasks = relationship("MaintenanceTask", back_populates="item_type")
    
    def __repr__(self):
        return f"<ItemType {self.category}:{self.name}>"


class AirportItem(Base):
    __tablename__ = 'airport_items'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airport_id = Column(CHAR(36), ForeignKey('airports.id', ondelete='CASCADE'), nullable=False)
    item_type_id = Column(CHAR(36), ForeignKey('item_types.id'), nullable=False)
    runway_id = Column(CHAR(36), ForeignKey('runways.id', ondelete='SET NULL'), nullable=True)
    
    # Identification
    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=True)  # Internal identifier
    serial_number = Column(String(255), nullable=True)
    
    # Location and geometry
    latitude = Column(Numeric(precision=11, scale=8, asdecimal=True), nullable=True)  # ±90°, 8 decimals = ~1.1mm precision
    longitude = Column(Numeric(precision=12, scale=8, asdecimal=True), nullable=True)  # ±180°, 8 decimals = ~1.1mm precision
    elevation = Column(Float, nullable=True)
    # geometry = Column(Geometry('GEOMETRY'), nullable=True)  # Can be POINT, LINESTRING, or POLYGON
    geometry = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    
    # Properties
    properties = Column(JSON, nullable=True)  # Item-specific properties
    specifications = Column(JSON, nullable=True)  # Technical specifications
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(50), default='operational')  # operational, maintenance, inactive
    
    # Maintenance
    installation_date = Column(DateTime, nullable=True)
    last_maintenance_date = Column(DateTime, nullable=True)
    next_maintenance_date = Column(DateTime, nullable=True)
    maintenance_history = Column(JSON, nullable=True)
    
    # Compliance
    compliance_status = Column(String(50), default='compliant')  # compliant, non-compliant, pending
    last_inspection_date = Column(DateTime, nullable=True)
    next_inspection_date = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    airport = relationship("Airport", back_populates="items")
    item_type = relationship("ItemType", back_populates="items")
    runway = relationship("Runway")
    tasks = relationship("Task", back_populates="item")
    measurements = relationship("Measurement", back_populates="item", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<AirportItem {self.name} at {self.airport_id}>"

