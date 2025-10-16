from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Integer, Enum
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.db.base import Base


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, enum.Enum):
    INSPECTION = "inspection"
    MAINTENANCE = "maintenance"
    CALIBRATION = "calibration"
    SURVEY = "survey"
    EMERGENCY = "emergency"


class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    airport_id = Column(CHAR(36), ForeignKey('airports.id', ondelete='CASCADE'), nullable=False)
    item_id = Column(CHAR(36), ForeignKey('airport_items.id', ondelete='SET NULL'), nullable=True)
    assigned_user_id = Column(CHAR(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Task details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    task_type = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    
    # Scheduling
    scheduled_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Execution details
    celery_task_id = Column(String(255), nullable=True)  # For background task tracking
    execution_params = Column(JSON, nullable=True)  # Parameters for task execution
    result = Column(JSON, nullable=True)  # Task result data
    
    # Compliance
    icao_requirement_ref = Column(String(255), nullable=True)
    compliance_deadline = Column(DateTime, nullable=True)
    
    # Recurrence
    is_recurring = Column(Boolean, default=False, nullable=False)
    recurrence_pattern = Column(JSON, nullable=True)  # Cron-like pattern or custom rules
    parent_task_id = Column(CHAR(36), ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True)
    
    # Notes and attachments
    notes = Column(Text, nullable=True)
    attachments = Column(JSON, nullable=True)  # List of file paths/URLs
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    airport = relationship("Airport", back_populates="tasks")
    item = relationship("AirportItem", back_populates="tasks")
    assigned_user = relationship("User", back_populates="tasks")
    parent_task = relationship("Task", remote_side=[id])
    measurements = relationship("Measurement", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Task {self.title} - {self.status}>"


class Measurement(Base):
    __tablename__ = 'measurements'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(CHAR(36), ForeignKey('tasks.id', ondelete='CASCADE'), nullable=True)
    item_id = Column(CHAR(36), ForeignKey('airport_items.id', ondelete='CASCADE'), nullable=False)
    
    # Measurement details
    measurement_type = Column(String(100), nullable=False)  # e.g., 'intensity', 'color', 'dimension'
    value = Column(Float, nullable=True)
    unit = Column(String(50), nullable=True)
    
    # Additional measurement data
    data = Column(JSON, nullable=True)  # Complex measurement data (arrays, objects)
    
    # Location of measurement
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    
    # Media attachments
    image_path = Column(String(500), nullable=True)
    video_path = Column(String(500), nullable=True)
    
    # Compliance
    is_compliant = Column(Boolean, nullable=True)
    tolerance_min = Column(Float, nullable=True)
    tolerance_max = Column(Float, nullable=True)
    
    # Environmental conditions during measurement
    weather_conditions = Column(JSON, nullable=True)
    temperature = Column(Float, nullable=True)  # in Celsius
    humidity = Column(Float, nullable=True)  # percentage
    wind_speed = Column(Float, nullable=True)  # m/s
    
    # Timestamps
    measured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    task = relationship("Task", back_populates="measurements")
    item = relationship("AirportItem", back_populates="measurements")
    
    def __repr__(self):
        return f"<Measurement {self.measurement_type}: {self.value} {self.unit}>"


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Action details
    action = Column(String(50), nullable=False)  # create, update, delete, login, etc.
    resource_type = Column(String(100), nullable=False)  # user, airport, task, etc.
    resource_id = Column(CHAR(36), nullable=True)
    
    # Change details
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    # Request context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(255), nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog {self.action} on {self.resource_type} by {self.user_id}>"