from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, Text, Enum
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from app.db.base import Base


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    AIRPORT_ADMIN = "airport_admin"
    MAINTENANCE_MANAGER = "maintenance_manager"
    DRONE_OPERATOR = "drone_operator"
    VIEWER = "viewer"


# Association tables for many-to-many relationships
user_airports = Table(
    'user_airports',
    Base.metadata,
    Column('user_id', CHAR(36), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('airport_id', CHAR(36), ForeignKey('airports.id', ondelete='CASCADE'), primary_key=True)
)

user_permissions = Table(
    'user_permissions',
    Base.metadata,
    Column('user_id', CHAR(36), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', CHAR(36), ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
)

role_permissions = Table(
    'role_permissions',
    Base.metadata,
    Column('role_id', CHAR(36), ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', CHAR(36), ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
)


class User(Base):
    __tablename__ = 'users'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    phone = Column(String(50), nullable=True)
    organization = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # Multi-factor authentication
    mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String(255), nullable=True)
    
    # Profile
    avatar_url = Column(String(500), nullable=True)
    preferences = Column(Text, nullable=True)  # JSON string for user preferences
    
    # Relationships
    airports = relationship("Airport", secondary=user_airports, back_populates="users")
    permissions = relationship("Permission", secondary=user_permissions, back_populates="users")
    created_airports = relationship("Airport", back_populates="created_by_user", foreign_keys="Airport.created_by")
    tasks = relationship("Task", back_populates="assigned_user")
    audit_logs = relationship("AuditLog", back_populates="user")
    measurement_sessions = relationship("MeasurementSession", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.email}>"


class Role(Base):
    __tablename__ = 'roles'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)  # System roles cannot be deleted
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    
    def __repr__(self):
        return f"<Role {self.name}>"


class Permission(Base):
    __tablename__ = 'permissions'
    
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), unique=True, nullable=False)
    resource = Column(String(100), nullable=False)  # e.g., 'airport', 'user', 'task'
    action = Column(String(50), nullable=False)  # e.g., 'create', 'read', 'update', 'delete'
    description = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    users = relationship("User", secondary=user_permissions, back_populates="permissions")
    
    def __repr__(self):
        return f"<Permission {self.resource}:{self.action}>"