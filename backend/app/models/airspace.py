"""
Airspace Model for comprehensive airspace management
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Integer, Enum, DECIMAL
from sqlalchemy.dialects.mysql import CHAR, LONGTEXT
from sqlalchemy.orm import relationship
# from geoalchemy2 import Geometry  # Commented out for SQLite compatibility
from datetime import datetime
import uuid
import enum

from app.db.base import Base


class AirspaceClass(str, enum.Enum):
    """ICAO Airspace Classifications"""
    CLASS_A = "A"  # IFR only, ATC clearance required
    CLASS_B = "B"  # IFR and VFR, ATC clearance required
    CLASS_C = "C"  # IFR and VFR, ATC clearance for IFR, two-way radio for VFR
    CLASS_D = "D"  # IFR and VFR, ATC clearance for IFR, two-way radio for VFR
    CLASS_E = "E"  # IFR and VFR, ATC clearance for IFR only
    CLASS_F = "F"  # IFR and VFR, ATC advisory service
    CLASS_G = "G"  # Uncontrolled airspace
    SPECIAL_USE = "SUA"  # Special use airspace


class AirspaceType(str, enum.Enum):
    """Types of airspace"""
    # Controlled Airspace
    CTR = "CTR"  # Control Zone
    TMA = "TMA"  # Terminal Control Area
    CTA = "CTA"  # Control Area
    ATZ = "ATZ"  # Aerodrome Traffic Zone
    
    # Special Use Airspace
    PROHIBITED = "P"     # Prohibited Area
    RESTRICTED = "R"     # Restricted Area
    DANGER = "D"         # Danger Area
    MOA = "MOA"         # Military Operations Area
    TSA = "TSA"         # Temporary Segregated Area
    TRA = "TRA"         # Temporary Reserved Area
    
    # Other Types
    FIR = "FIR"         # Flight Information Region
    UIR = "UIR"         # Upper Information Region
    ADIZ = "ADIZ"       # Air Defense Identification Zone
    TFR = "TFR"         # Temporary Flight Restriction
    GLIDING = "GLIDING" # Gliding Area
    PARACHUTE = "PARA"  # Parachute Jump Area
    AERIAL_WORK = "AWY" # Aerial Work Area
    
    # Navigation
    AWY = "AIRWAY"      # Airway
    NAV_WARN = "NAV_WARN" # Navigation Warning Area


class AltitudeReference(str, enum.Enum):
    """Altitude reference systems"""
    MSL = "MSL"    # Mean Sea Level
    AGL = "AGL"    # Above Ground Level
    FL = "FL"      # Flight Level
    SFC = "SFC"    # Surface
    UNL = "UNL"    # Unlimited
    NOTAM = "NOTAM" # As specified in NOTAM


class Airspace(Base):
    """Comprehensive airspace model"""
    __tablename__ = 'airspaces'
    
    # Primary identification
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airport_id = Column(CHAR(36), ForeignKey('airports.id', ondelete='CASCADE'), nullable=True)
    
    # Basic Information
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)  # e.g., "EDP123" for Prohibited area
    icao_designator = Column(String(50), nullable=True)
    country = Column(String(100), nullable=False)
    
    # Classification
    airspace_class = Column(Enum(AirspaceClass), nullable=False)
    airspace_type = Column(Enum(AirspaceType), nullable=False)
    
    # Vertical Limits
    lower_limit_value = Column(Float, nullable=False)  # Altitude value
    lower_limit_reference = Column(Enum(AltitudeReference), nullable=False)
    lower_limit_unit = Column(String(10), default='FT')  # FT or M
    
    upper_limit_value = Column(Float, nullable=False)  # Altitude value
    upper_limit_reference = Column(Enum(AltitudeReference), nullable=False)
    upper_limit_unit = Column(String(10), default='FT')  # FT or M
    
    # Computed values in meters for consistency
    lower_limit_meters = Column(Float, nullable=True)  # Computed lower limit in meters MSL
    upper_limit_meters = Column(Float, nullable=True)  # Computed upper limit in meters MSL
    
    # Geometry (2D boundary polygon)
    # geometry = Column(Geometry('POLYGON'), nullable=False)
    geometry = Column(JSON, nullable=False)  # Using JSON instead of Geometry for SQLite
    area_sq_km = Column(Float, nullable=True)  # Computed area
    
    # Center point for map display
    center_latitude = Column(DECIMAL(precision=10, scale=7), nullable=True)
    center_longitude = Column(DECIMAL(precision=10, scale=7), nullable=True)
    
    # Operating Hours
    active_times = Column(JSON, nullable=True)
    # Format: {
    #   "schedule": "H24" | "HJ" | "DAILY 0800-1700",
    #   "days": ["MON", "TUE", "WED", "THU", "FRI"],
    #   "timezone": "UTC",
    #   "seasonal": {"from": "APR", "to": "OCT"}
    # }
    
    # Communications
    frequencies = Column(JSON, nullable=True)
    # Format: [
    #   {"type": "PRIMARY", "frequency": 121.5, "callsign": "BRATISLAVA APPROACH"},
    #   {"type": "SECONDARY", "frequency": 127.725, "callsign": "BRATISLAVA RADAR"}
    # ]
    
    controlling_authority = Column(String(255), nullable=True)
    contact_info = Column(JSON, nullable=True)
    
    # Restrictions and Requirements
    restrictions = Column(JSON, nullable=True)
    # Format: {
    #   "entry_requirements": ["ATC_CLEARANCE", "TRANSPONDER", "RADIO"],
    #   "prohibited_activities": ["AEROBATICS", "GLIDING"],
    #   "speed_limit": {"value": 250, "unit": "KIAS"},
    #   "equipment_required": ["MODE_S", "8.33_RADIO"]
    # }
    
    # Additional Properties
    properties = Column(JSON, nullable=True)  # Additional airspace-specific properties
    notes = Column(Text, nullable=True)  # Human-readable notes
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_temporary = Column(Boolean, default=False, nullable=False)
    
    # Validity Period (for temporary airspaces)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    
    # Regulatory References
    regulation_reference = Column(String(255), nullable=True)
    aip_reference = Column(String(255), nullable=True)  # Aeronautical Information Publication
    
    # Data Source
    source = Column(String(100), nullable=True)  # e.g., "OpenAIP", "National_AIP", "NOTAM"
    source_updated = Column(DateTime, nullable=True)
    
    # Visualization Properties
    border_color = Column(String(7), nullable=True)  # Hex color for border
    fill_color = Column(String(7), nullable=True)   # Hex color for fill
    opacity = Column(Float, default=0.3, nullable=True)  # Fill opacity
    display_priority = Column(Integer, default=50)  # Higher priority displays on top
    
    # Relationships
    parent_airspace_id = Column(CHAR(36), ForeignKey('airspaces.id'), nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(CHAR(36), ForeignKey('users.id'), nullable=True)
    
    # Relationships (commented out for now - airport relationship not yet established)
    # airport = relationship("Airport", back_populates="airspaces")
    parent_airspace = relationship("Airspace", remote_side=[id])
    child_airspaces = relationship("Airspace", back_populates="parent_airspace")
    
    def __repr__(self):
        return f"<Airspace {self.name} ({self.airspace_type})>"


class AirspaceSegment(Base):
    """For complex airspaces with multiple segments at different altitudes"""
    __tablename__ = 'airspace_segments'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airspace_id = Column(CHAR(36), ForeignKey('airspaces.id', ondelete='CASCADE'), nullable=False)
    
    segment_name = Column(String(100), nullable=True)
    segment_number = Column(Integer, nullable=False)
    
    # Vertical limits for this segment
    lower_limit_value = Column(Float, nullable=False)
    lower_limit_reference = Column(Enum(AltitudeReference), nullable=False)
    upper_limit_value = Column(Float, nullable=False)
    upper_limit_reference = Column(Enum(AltitudeReference), nullable=False)
    
    # Geometry for this segment (may differ from main airspace)
    # geometry = Column(Geometry('POLYGON'), nullable=True)
    geometry = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    
    # Specific restrictions for this segment
    segment_restrictions = Column(JSON, nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    airspace = relationship("Airspace")
    
    def __repr__(self):
        return f"<AirspaceSegment {self.segment_number} of {self.airspace_id}>"


class AirspaceIntersection(Base):
    """Track intersections between airspaces for conflict detection"""
    __tablename__ = 'airspace_intersections'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airspace1_id = Column(CHAR(36), ForeignKey('airspaces.id'), nullable=False)
    airspace2_id = Column(CHAR(36), ForeignKey('airspaces.id'), nullable=False)
    
    # Type of intersection
    intersection_type = Column(String(50), nullable=False)  # VERTICAL, HORIZONTAL, FULL
    
    # Overlapping altitude range
    overlap_lower_meters = Column(Float, nullable=True)
    overlap_upper_meters = Column(Float, nullable=True)
    
    # Intersection geometry
    # intersection_geometry = Column(Geometry('GEOMETRY'), nullable=True)
    intersection_geometry = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    intersection_area_sq_km = Column(Float, nullable=True)
    
    # Conflict assessment
    is_conflict = Column(Boolean, default=False)
    conflict_notes = Column(Text, nullable=True)
    
    # Relationships
    airspace1 = relationship("Airspace", foreign_keys=[airspace1_id])
    airspace2 = relationship("Airspace", foreign_keys=[airspace2_id])


class NOTAMAirspace(Base):
    """Temporary airspace changes via NOTAM"""
    __tablename__ = 'notam_airspaces'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airspace_id = Column(CHAR(36), ForeignKey('airspaces.id'), nullable=True)
    
    notam_id = Column(String(100), nullable=False)
    notam_series = Column(String(10), nullable=True)
    
    # NOTAM details
    subject = Column(String(255), nullable=False)
    condition = Column(Text, nullable=False)
    
    # Temporal validity
    valid_from = Column(DateTime, nullable=False)
    valid_until = Column(DateTime, nullable=False)
    
    # Schedule within validity period
    schedule = Column(String(255), nullable=True)  # e.g., "DAILY 0800-1700"
    
    # Geometry (if different from base airspace)
    # temporary_geometry = Column(Geometry('GEOMETRY'), nullable=True)
    temporary_geometry = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    
    # Modified limits
    temporary_lower_limit = Column(String(100), nullable=True)
    temporary_upper_limit = Column(String(100), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    airspace = relationship("Airspace")


class AirspaceWeather(Base):
    """Current weather conditions affecting airspace"""
    __tablename__ = 'airspace_weather'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airspace_id = Column(CHAR(36), ForeignKey('airspaces.id'), nullable=False)
    
    observation_time = Column(DateTime, nullable=False)
    
    # Weather data
    visibility_meters = Column(Float, nullable=True)
    ceiling_meters = Column(Float, nullable=True)
    wind_speed_kt = Column(Float, nullable=True)
    wind_direction = Column(Integer, nullable=True)
    
    # Conditions
    weather_conditions = Column(JSON, nullable=True)  # ["IMC", "TURBULENCE", "ICING"]
    
    # Impact on operations
    operational_impact = Column(String(50), nullable=True)  # CLOSED, RESTRICTED, NORMAL
    
    # Relationships
    airspace = relationship("Airspace")