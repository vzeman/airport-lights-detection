from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from app.models.user import UserRole

if TYPE_CHECKING:
    from app.schemas.airport import AirportResponse


class UserBase(BaseModel):
    email: EmailStr
    username: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    organization: Optional[str] = None
    role: UserRole = UserRole.VIEWER


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(UserBase):
    id: str
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    mfa_enabled: bool
    avatar_url: Optional[str] = None
    airports: List['AirportResponse'] = []

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    users: List[UserResponse]


class LoginRequest(BaseModel):
    username: str  # Can be username or email
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class RoleBase(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleResponse(RoleBase):
    id: str
    is_system: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PermissionBase(BaseModel):
    name: str
    resource: str
    action: str
    description: Optional[str] = None


class PermissionResponse(PermissionBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Resolve forward references
from app.schemas.airport import AirportResponse
UserResponse.model_rebuild()