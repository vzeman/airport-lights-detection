"""
Enhanced Airport Item Model with comprehensive support for all airport elements
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Integer, Enum, DECIMAL
from sqlalchemy.dialects.mysql import CHAR, LONGTEXT
from sqlalchemy.orm import relationship
# from geoalchemy2 import Geometry  # Commented out for SQLite compatibility
from datetime import datetime
import uuid
import enum

from app.db.base import Base


class PrecisionLevel(str, enum.Enum):
    """Precision requirements for different element types"""
    SURVEY_GRADE = "survey_grade"      # ±1cm (critical runway markings, ILS equipment)
    HIGH = "high"                      # ±2-5cm (runway lights, PAPI)
    MEDIUM = "medium"                  # ±10cm (taxiway lights, signs)
    LOW = "low"                        # ±50cm (general infrastructure)


class GeometryType(str, enum.Enum):
    """Supported geometry types for airport items"""
    POINT = "POINT"                    # Single location (lights, signs)
    LINESTRING = "LINESTRING"          # Linear features (centerlines, edges)
    POLYGON = "POLYGON"                # Areas (runways, restricted zones)
    MULTIPOINT = "MULTIPOINT"          # Multiple related points (light arrays)
    MULTIPOLYGON = "MULTIPOLYGON"      # Complex areas with holes


class ItemStatus(str, enum.Enum):
    """Operational status of airport items"""
    OPERATIONAL = "operational"
    MAINTENANCE = "maintenance"
    INACTIVE = "inactive"
    PLANNED = "planned"
    DECOMMISSIONED = "decommissioned"


class CoordinateAccuracy(str, enum.Enum):
    """Source and accuracy of coordinate data"""
    SURVEY_GPS = "survey_gps"          # Professional GPS survey
    LIDAR = "lidar"                    # LiDAR scanning
    PHOTOGRAMMETRY = "photogrammetry"  # Aerial/drone photography
    CAD_IMPORT = "cad_import"          # Imported from CAD drawings
    MANUAL_ENTRY = "manual_entry"      # Manually entered
    ESTIMATED = "estimated"            # Estimated position


class EnhancedAirportItem(Base):
    """Enhanced airport item model with comprehensive positioning and metadata"""
    __tablename__ = 'enhanced_airport_items'
    
    # Primary identification
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airport_id = Column(CHAR(36), ForeignKey('airports.id', ondelete='CASCADE'), nullable=False)
    item_type_id = Column(CHAR(36), ForeignKey('enhanced_item_types.id'), nullable=False)
    runway_id = Column(CHAR(36), ForeignKey('runways.id', ondelete='SET NULL'), nullable=True)
    
    # Basic information
    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=True)  # Internal identifier/asset number
    serial_number = Column(String(255), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    model = Column(String(255), nullable=True)
    part_number = Column(String(255), nullable=True)
    
    # Precise positioning (using DECIMAL for exact precision)
    latitude = Column(DECIMAL(precision=12, scale=9), nullable=True)  # 9 decimal places = ~1cm precision
    longitude = Column(DECIMAL(precision=12, scale=9), nullable=True) # 9 decimal places = ~1cm precision
    elevation_msl = Column(DECIMAL(precision=8, scale=3), nullable=True)  # Meters above sea level
    height_agl = Column(DECIMAL(precision=8, scale=3), nullable=True)     # Meters above ground level
    
    # Orientation and positioning
    orientation = Column(DECIMAL(precision=6, scale=3), nullable=True)  # Degrees from north (0-359.999)
    tilt = Column(DECIMAL(precision=5, scale=3), nullable=True)         # Degrees from horizontal
    roll = Column(DECIMAL(precision=5, scale=3), nullable=True)         # Roll angle for complex items
    
    # Coordinate metadata
    coordinate_accuracy = Column(Enum(CoordinateAccuracy), default=CoordinateAccuracy.MANUAL_ENTRY)
    precision_level = Column(Enum(PrecisionLevel), default=PrecisionLevel.MEDIUM)
    survey_date = Column(DateTime, nullable=True)
    survey_reference = Column(String(255), nullable=True)  # Survey job number/reference
    
    # Geometry for complex shapes
    # geometry = Column(Geometry('GEOMETRY'), nullable=True)
    geometry = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    geometry_type = Column(Enum(GeometryType), nullable=True)
    
    # Physical properties
    dimensions = Column(JSON, nullable=True)  # {"length": 10.5, "width": 2.0, "height": 3.5}
    weight = Column(Float, nullable=True)     # Kilograms
    material = Column(String(100), nullable=True)
    color = Column(String(50), nullable=True)
    
    # Electrical properties (for lights and electronic equipment)
    electrical_properties = Column(JSON, nullable=True)  
    # {"voltage": 240, "current": 5.2, "power": 150, "circuit_id": "C-12A"}
    
    # Operational properties
    properties = Column(JSON, nullable=True)  # Item-specific properties
    specifications = Column(JSON, nullable=True)  # Technical specifications
    configuration = Column(JSON, nullable=True)  # Configuration settings
    
    # Status and lifecycle
    status = Column(Enum(ItemStatus), default=ItemStatus.OPERATIONAL)
    is_active = Column(Boolean, default=True, nullable=False)
    is_critical = Column(Boolean, default=False)  # Critical for airport operations
    is_monitored = Column(Boolean, default=False)  # Under remote monitoring
    
    # Installation and maintenance
    installation_date = Column(DateTime, nullable=True)
    last_maintenance_date = Column(DateTime, nullable=True)
    next_maintenance_date = Column(DateTime, nullable=True)
    maintenance_history = Column(JSON, nullable=True)
    warranty_expiry = Column(DateTime, nullable=True)
    
    # Compliance and inspection
    compliance_status = Column(String(50), default='compliant')
    last_inspection_date = Column(DateTime, nullable=True)
    next_inspection_date = Column(DateTime, nullable=True)
    inspection_history = Column(JSON, nullable=True)
    
    # ICAO/regulatory references
    icao_reference = Column(String(255), nullable=True)
    regulatory_notes = Column(Text, nullable=True)
    
    # Environmental conditions
    operating_conditions = Column(JSON, nullable=True)
    # {"temperature_range": [-40, 70], "humidity_max": 95, "wind_resistance": 150}
    
    # Relationships and dependencies
    parent_item_id = Column(CHAR(36), ForeignKey('enhanced_airport_items.id'), nullable=True)
    related_items = Column(JSON, nullable=True)  # Array of related item IDs
    
    # Documentation
    documentation = Column(JSON, nullable=True)
    # {"manuals": ["url1", "url2"], "certificates": ["cert1"], "photos": ["photo1"]}
    
    # Custom fields for extensibility
    custom_fields = Column(JSON, nullable=True)
    
    # Audit trail
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    created_by = Column(CHAR(36), ForeignKey('users.id'), nullable=True)
    updated_by = Column(CHAR(36), ForeignKey('users.id'), nullable=True)
    
    # Relationships
    airport = relationship("Airport", back_populates="enhanced_items")
    item_type = relationship("EnhancedItemType", back_populates="items")
    runway = relationship("Runway", back_populates="enhanced_items")
    parent_item = relationship("EnhancedAirportItem", remote_side=[id])
    child_items = relationship("EnhancedAirportItem", back_populates="parent_item")
    
    def __repr__(self):
        return f"<EnhancedAirportItem {self.name} at {self.airport_id}>"


class EnhancedItemType(Base):
    """Enhanced item type with comprehensive categorization"""
    __tablename__ = 'enhanced_item_types'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(100), nullable=False)
    subcategory = Column(String(100), nullable=True)
    
    # Classification
    icao_classification = Column(String(100), nullable=True)
    regulatory_category = Column(String(100), nullable=True)
    safety_category = Column(String(50), nullable=True)  # critical, important, standard
    
    # Default properties
    default_precision = Column(Enum(PrecisionLevel), default=PrecisionLevel.MEDIUM)
    default_geometry_type = Column(Enum(GeometryType), default=GeometryType.POINT)
    requires_orientation = Column(Boolean, default=False)
    requires_height = Column(Boolean, default=False)
    
    # Physical defaults
    default_dimensions = Column(JSON, nullable=True)
    default_properties = Column(JSON, nullable=True)
    default_specifications = Column(JSON, nullable=True)
    
    # Maintenance and inspection
    inspection_frequency_days = Column(Integer, default=30)
    maintenance_frequency_days = Column(Integer, default=365)
    inspection_procedures = Column(JSON, nullable=True)
    maintenance_procedures = Column(JSON, nullable=True)
    
    # ICAO compliance
    icao_reference = Column(String(255), nullable=True)
    icao_requirements = Column(JSON, nullable=True)
    regulatory_requirements = Column(JSON, nullable=True)
    
    # Visualization
    icon = Column(String(100), nullable=True)
    default_color = Column(String(7), nullable=True)
    map_symbol = Column(String(50), nullable=True)
    
    # 3D representation
    model_3d_url = Column(String(500), nullable=True)
    symbol_3d = Column(JSON, nullable=True)
    
    # Templates and automation
    auto_generation_rules = Column(JSON, nullable=True)  # Rules for automatic item creation
    positioning_templates = Column(JSON, nullable=True)  # Standard positioning patterns
    
    # Relationships
    items = relationship("EnhancedAirportItem", back_populates="item_type")
    
    def __repr__(self):
        return f"<EnhancedItemType {self.category}:{self.subcategory}:{self.name}>"


class ItemSearchIndex(Base):
    """Search index for fast full-text search of airport items"""
    __tablename__ = 'item_search_index'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(CHAR(36), ForeignKey('enhanced_airport_items.id', ondelete='CASCADE'), nullable=False)
    airport_id = Column(CHAR(36), ForeignKey('airports.id', ondelete='CASCADE'), nullable=False)
    
    # Searchable text content
    search_text = Column(Text, nullable=False)  # Combined searchable content
    keywords = Column(JSON, nullable=True)     # Array of keywords
    tags = Column(JSON, nullable=True)         # User-defined tags
    
    # Spatial search optimization
    grid_reference = Column(String(20), nullable=True)  # Grid square reference
    zone = Column(String(50), nullable=True)           # Airport zone/area
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    item = relationship("EnhancedAirportItem")
    airport = relationship("Airport")