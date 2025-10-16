"""
Maintenance Task and Mission Planning Models
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Integer, Enum, Table
from sqlalchemy.dialects.mysql import CHAR, DECIMAL, LONGTEXT
from sqlalchemy.orm import relationship
# from geoalchemy2 import Geometry  # Commented out for SQLite compatibility
from datetime import datetime
import uuid
import enum

from app.db.base import Base


class TaskType(str, enum.Enum):
    """Types of maintenance tasks"""
    VISUAL_INSPECTION = "visual_inspection"
    LIGHT_MEASUREMENT = "light_measurement"
    PAPI_CALIBRATION = "papi_calibration"
    ILS_VERIFICATION = "ils_verification"
    MARKING_CHECK = "marking_check"
    SURFACE_INSPECTION = "surface_inspection"
    OBSTRUCTION_SURVEY = "obstruction_survey"
    THERMAL_INSPECTION = "thermal_inspection"
    PHOTOGRAMMETRY = "photogrammetry"
    LIDAR_SCAN = "lidar_scan"


class TaskPriority(str, enum.Enum):
    """Task priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ROUTINE = "routine"


class MissionType(str, enum.Enum):
    """Types of flight missions"""
    WAYPOINT = "waypoint"  # Simple waypoint navigation
    ORBIT = "orbit"  # Circular orbit around target
    GRID = "grid"  # Grid pattern scanning
    CORRIDOR = "corridor"  # Linear corridor following
    SPIRAL = "spiral"  # Spiral pattern
    CUSTOM = "custom"  # Custom path


class FlightMode(str, enum.Enum):
    """Drone flight modes"""
    MANUAL = "manual"
    STABILIZE = "stabilize"
    ALTITUDE_HOLD = "altitude_hold"
    POSITION_HOLD = "position_hold"
    AUTO = "auto"
    RTL = "return_to_launch"
    LAND = "land"


# Association table for task prerequisites
task_prerequisites = Table(
    'task_prerequisites',
    Base.metadata,
    Column('task_id', CHAR(36), ForeignKey('maintenance_tasks.id')),
    Column('prerequisite_id', CHAR(36), ForeignKey('maintenance_tasks.id'))
)


class MaintenanceTask(Base):
    """Maintenance task definition for item types"""
    __tablename__ = 'maintenance_tasks'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_type_id = Column(CHAR(36), ForeignKey('item_types.id'), nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    
    # Task details
    task_type = Column(Enum(TaskType), nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM)
    description = Column(Text, nullable=True)
    
    # Frequency and scheduling
    frequency_days = Column(Integer, nullable=False)  # How often to perform
    duration_minutes = Column(Integer, default=30)  # Expected duration
    weather_constraints = Column(JSON, nullable=True)  # Wind, visibility requirements
    time_constraints = Column(JSON, nullable=True)  # Day/night, specific hours
    
    # Equipment requirements
    required_sensors = Column(JSON, nullable=True)  # Camera, LIDAR, thermal, etc.
    required_accuracy_m = Column(DECIMAL(5, 3), default=0.1)  # Position accuracy needed
    
    # Measurement specifications
    measurement_specs = Column(JSON, nullable=True)  # Detailed specs for measurements
    acceptance_criteria = Column(JSON, nullable=True)  # Pass/fail criteria
    
    # Regulatory compliance
    compliance_standard = Column(String(100), nullable=True)  # ICAO, FAA reference
    documentation_required = Column(Boolean, default=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    item_type = relationship("ItemType", back_populates="maintenance_tasks")
    mission_templates = relationship("MissionTemplate", back_populates="task", cascade="all, delete-orphan")
    prerequisites = relationship(
        "MaintenanceTask",
        secondary=task_prerequisites,
        primaryjoin=(id == task_prerequisites.c.task_id),
        secondaryjoin=(id == task_prerequisites.c.prerequisite_id),
        backref="dependent_tasks"
    )
    
    def __repr__(self):
        return f"<MaintenanceTask {self.code}: {self.name}>"


class MissionTemplate(Base):
    """Mission path template for specific tasks"""
    __tablename__ = 'mission_templates'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(CHAR(36), ForeignKey('maintenance_tasks.id'), nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(Integer, default=1)
    
    # Mission configuration
    mission_type = Column(Enum(MissionType), nullable=False)
    is_default = Column(Boolean, default=False)  # Default template for this task
    
    # Flight parameters
    altitude_agl_m = Column(DECIMAL(6, 2), nullable=False)  # Altitude above ground
    speed_ms = Column(DECIMAL(5, 2), default=5.0)  # Speed in m/s
    heading_mode = Column(String(50), default='auto')  # auto, fixed, poi
    gimbal_pitch = Column(DECIMAL(5, 2), default=-90)  # Camera gimbal pitch
    
    # Pattern parameters (depends on mission_type)
    pattern_params = Column(JSON, nullable=True)
    """
    Examples:
    - GRID: {"spacing_m": 10, "angle_deg": 0, "overlap_pct": 70}
    - ORBIT: {"radius_m": 50, "points": 36, "clockwise": true}
    - CORRIDOR: {"width_m": 20, "overlap_pct": 60}
    - SPIRAL: {"start_radius_m": 10, "end_radius_m": 100, "pitch_m": 5}
    """
    
    # Waypoints and path
    waypoints = Column(JSON, nullable=True)  # List of waypoints with actions
    """
    Example waypoint:
    {
        "seq": 1,
        "lat": 48.1234,
        "lon": 17.5678,
        "alt_m": 50,
        "speed_ms": 5,
        "actions": [
            {"type": "photo", "count": 3, "interval_s": 2},
            {"type": "hover", "duration_s": 10},
            {"type": "gimbal", "pitch": -45}
        ]
    }
    """
    
    # Path geometry (computed from waypoints or pattern)
    # path_geometry = Column(Geometry('LINESTRING', dimension=3), nullable=True)
    path_geometry = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    
    # Safety parameters
    obstacle_avoidance = Column(Boolean, default=True)
    # geofence = Column(Geometry('POLYGON'), nullable=True)
    geofence = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    min_altitude_m = Column(DECIMAL(6, 2), default=10)
    max_altitude_m = Column(DECIMAL(6, 2), default=120)
    return_to_home_altitude_m = Column(DECIMAL(6, 2), default=50)
    
    # Sensor settings
    sensor_configs = Column(JSON, nullable=True)
    """
    Example:
    {
        "camera": {
            "resolution": "4K",
            "fps": 30,
            "exposure": "auto",
            "iso": 100
        },
        "lidar": {
            "points_per_second": 300000,
            "scan_angle": 40
        }
    }
    """
    
    # Mission statistics (computed)
    total_distance_m = Column(DECIMAL(10, 2), nullable=True)
    estimated_duration_s = Column(Integer, nullable=True)
    coverage_area_sqm = Column(DECIMAL(12, 2), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    task = relationship("MaintenanceTask", back_populates="mission_templates")
    
    def __repr__(self):
        return f"<MissionTemplate {self.name} for task {self.task_id}>"


class FlightPlan(Base):
    """Generated flight plan combining multiple missions"""
    __tablename__ = 'flight_plans'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airport_id = Column(CHAR(36), ForeignKey('airports.id'), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Planning details
    planned_date = Column(DateTime, nullable=False)
    planned_by = Column(CHAR(36), ForeignKey('users.id'), nullable=False)
    
    # Drone and operator
    drone_id = Column(String(100), nullable=True)  # Drone identifier
    operator_id = Column(CHAR(36), ForeignKey('users.id'), nullable=True)
    
    # Combined mission data
    mission_sequence = Column(JSON, nullable=False)
    """
    List of missions in sequence:
    [
        {
            "seq": 1,
            "item_id": "uuid",
            "task_id": "uuid",
            "template_id": "uuid",
            "transition_path": {...}  # Path to next mission
        }
    ]
    """
    
    # Optimized path
    # optimized_path = Column(Geometry('LINESTRING', dimension=3), nullable=True)
    optimized_path = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    optimization_params = Column(JSON, nullable=True)  # Algorithm parameters used
    
    # Flight statistics
    total_distance_m = Column(DECIMAL(10, 2), nullable=True)
    total_duration_s = Column(Integer, nullable=True)
    total_items = Column(Integer, default=0)
    total_tasks = Column(Integer, default=0)
    
    # Battery management
    battery_changes = Column(JSON, nullable=True)  # Planned battery change points
    estimated_batteries = Column(Integer, default=1)
    
    # Weather window
    weather_window_start = Column(DateTime, nullable=True)
    weather_window_end = Column(DateTime, nullable=True)
    weather_constraints = Column(JSON, nullable=True)
    
    # Execution status
    status = Column(String(50), default='draft')  # draft, approved, executing, completed, cancelled
    approved_by = Column(CHAR(36), ForeignKey('users.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Execution details
    actual_start = Column(DateTime, nullable=True)
    actual_end = Column(DateTime, nullable=True)
    execution_log = Column(JSON, nullable=True)  # Detailed execution log
    
    # Results
    completed_items = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    issues_found = Column(Integer, default=0)
    
    # Export formats
    mavlink_file = Column(Text, nullable=True)  # MAVLink mission file
    kml_file = Column(Text, nullable=True)  # KML for Google Earth
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    airport = relationship("Airport", backref="flight_plans")
    planner = relationship("User", foreign_keys=[planned_by], backref="planned_flights")
    operator = relationship("User", foreign_keys=[operator_id], backref="operated_flights")
    approver = relationship("User", foreign_keys=[approved_by], backref="approved_flights")
    plan_items = relationship("FlightPlanItem", back_populates="flight_plan", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<FlightPlan {self.name} - {self.status}>"


class FlightPlanItem(Base):
    """Individual items and tasks in a flight plan"""
    __tablename__ = 'flight_plan_items'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flight_plan_id = Column(CHAR(36), ForeignKey('flight_plans.id'), nullable=False)
    sequence = Column(Integer, nullable=False)  # Order in flight plan
    
    # Target item and task
    airport_item_id = Column(CHAR(36), ForeignKey('airport_items.id'), nullable=False)
    task_id = Column(CHAR(36), ForeignKey('maintenance_tasks.id'), nullable=False)
    template_id = Column(CHAR(36), ForeignKey('mission_templates.id'), nullable=False)
    
    # Customizations for this instance
    custom_params = Column(JSON, nullable=True)  # Override template params
    skip_transition = Column(Boolean, default=False)  # Skip optimization to next item
    
    # Computed mission details
    mission_waypoints = Column(JSON, nullable=True)  # Final waypoints
    # mission_path = Column(Geometry('LINESTRING', dimension=3), nullable=True)
    mission_path = Column(JSON, nullable=True)  # Using JSON instead of Geometry for SQLite
    estimated_duration_s = Column(Integer, nullable=True)
    
    # Execution status
    status = Column(String(50), default='pending')  # pending, executing, completed, skipped, failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Results
    measurements = Column(JSON, nullable=True)  # Measurement results
    issues = Column(JSON, nullable=True)  # Issues found
    media_files = Column(JSON, nullable=True)  # Photos/videos captured
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    flight_plan = relationship("FlightPlan", back_populates="plan_items")
    airport_item = relationship("AirportItem", backref="flight_plan_items")
    task = relationship("MaintenanceTask", backref="flight_plan_items")
    template = relationship("MissionTemplate", backref="flight_plan_items")
    
    def __repr__(self):
        return f"<FlightPlanItem seq={self.sequence} for plan {self.flight_plan_id}>"


class MissionOptimization(Base):
    """Mission path optimization records"""
    __tablename__ = 'mission_optimizations'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flight_plan_id = Column(CHAR(36), ForeignKey('flight_plans.id'), nullable=False)
    
    # Optimization parameters
    algorithm = Column(String(50), nullable=False)  # tsp, genetic, dijkstra, custom
    objective = Column(String(50), nullable=False)  # min_distance, min_time, max_coverage
    constraints = Column(JSON, nullable=True)
    
    # Input
    input_items = Column(Integer, nullable=False)
    input_distance_m = Column(DECIMAL(10, 2), nullable=True)
    
    # Output
    optimized_sequence = Column(JSON, nullable=False)  # Optimized order
    optimized_distance_m = Column(DECIMAL(10, 2), nullable=True)
    improvement_pct = Column(DECIMAL(5, 2), nullable=True)
    
    # Performance
    computation_time_ms = Column(Integer, nullable=True)
    iterations = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<MissionOptimization for plan {self.flight_plan_id}>"