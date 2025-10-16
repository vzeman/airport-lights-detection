from typing import Optional, List
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.db.base import get_db
from app.core.config import settings
from app.models import User, UserRole

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    return user


async def get_current_active_superuser(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current superuser"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def require_role(allowed_roles: List[UserRole]):
    """Dependency to check user role"""
    async def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if current_user.role not in allowed_roles and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker


class PermissionChecker:
    """Check if user has specific permission"""
    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action
    
    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        # Superusers have all permissions
        if current_user.is_superuser:
            return current_user
        
        # Check user's direct permissions and role permissions
        has_permission = False
        
        for permission in current_user.permissions:
            if permission.resource == self.resource and permission.action == self.action:
                has_permission = True
                break
        
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No permission to {self.action} {self.resource}"
            )
        
        return current_user


# Common permission dependencies
can_manage_users = PermissionChecker("user", "manage")
can_manage_airports = PermissionChecker("airport", "manage")
can_view_airports = PermissionChecker("airport", "view")