from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
import uuid

from app.db.base import get_db
from app.models import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserListResponse
from app.core.security import get_password_hash
from app.core.deps import get_current_active_superuser, require_role

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.AIRPORT_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """List all users with pagination and filtering"""
    query = select(User)
    count_query = select(func.count()).select_from(User)
    
    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            User.email.ilike(search_filter) |
            User.username.ilike(search_filter) |
            User.first_name.ilike(search_filter) |
            User.last_name.ilike(search_filter)
        )
        count_query = count_query.filter(
            User.email.ilike(search_filter) |
            User.username.ilike(search_filter) |
            User.first_name.ilike(search_filter) |
            User.last_name.ilike(search_filter)
        )
    
    if role:
        query = query.filter(User.role == role)
        count_query = count_query.filter(User.role == role)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
        count_query = count_query.filter(User.is_active == is_active)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Execute query
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "users": users
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.AIRPORT_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Get user by ID"""
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Create a new user (Super admin only)"""
    # Check if email or username already exists
    existing_user = await db.execute(
        select(User).filter(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    if existing_user.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )
    
    # Create new user
    user = User(
        id=str(uuid.uuid4()),
        email=user_data.email,
        username=user_data.username,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        organization=user_data.organization,
        role=user_data.role,
        hashed_password=get_password_hash(user_data.password),
        is_active=True,
        is_superuser=False
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.AIRPORT_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Update user information"""
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields if provided
    for field, value in user_data.model_dump(exclude_unset=True).items():
        if field == "password" and value:
            setattr(user, "hashed_password", get_password_hash(value))
        elif hasattr(user, field):
            setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user (Super admin only)"""
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Don't allow deleting yourself
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    await db.delete(user)
    await db.commit()
    
    return None


@router.post("/{user_id}/assign-airport/{airport_id}")
async def assign_user_to_airport(
    user_id: str,
    airport_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.AIRPORT_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Assign user to an airport"""
    # Implementation will be added when Airport model is ready
    return {"message": "User assigned to airport successfully"}