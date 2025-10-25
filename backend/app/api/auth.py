from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from starlette.requests import Request
from starlette.responses import RedirectResponse
import uuid

from app.db.base import get_db
from app.models import User
from app.models.user import UserRole
from app.schemas.user import LoginRequest, TokenResponse, RefreshTokenRequest, ChangePasswordRequest, UserResponse
from app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from app.core.config import settings
from app.core.deps import get_current_user
from app.core.oauth import oauth
from jose import JWTError, jwt

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login with username or email"""
    # Find user by username or email
    result = await db.execute(
        select(User).filter(
            or_(
                User.username == login_data.username,
                User.email == login_data.username
            )
        )
    )
    user = result.scalars().first()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    try:
        payload = jwt.decode(
            refresh_data.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid refresh token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid refresh token",
        )
    
    # Get user
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
            detail="User account is disabled"
        )
    
    # Create new tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return current_user


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change current user's password"""
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )

    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()

    return {"message": "Password changed successfully"}


@router.get("/{provider}/login")
async def oauth_login(provider: str, request: Request):
    """Initiate OAuth login with Google"""
    if provider != 'google':
        raise HTTPException(status_code=400, detail="Only Google OAuth is supported")

    client = oauth.create_client(provider)
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/auth/{provider}/callback"
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle OAuth callback and create/login user"""
    if provider != 'google':
        raise HTTPException(status_code=400, detail="Only Google OAuth is supported")

    try:
        client = oauth.create_client(provider)
        token = await client.authorize_access_token(request)

        # Get user info from Google
        user_info = token.get('userinfo')
        oauth_id = user_info['sub']
        email = user_info['email']
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')

        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")

        # Find or create user
        result = await db.execute(
            select(User).filter(
                User.oauth_provider == provider,
                User.oauth_id == oauth_id
            )
        )
        user = result.scalars().first()

        if not user:
            # Check if email already exists
            result = await db.execute(select(User).filter(User.email == email))
            existing_user = result.scalars().first()

            if existing_user:
                # Link OAuth to existing user
                existing_user.oauth_provider = provider
                existing_user.oauth_id = oauth_id
                existing_user.oauth_access_token = token.get('access_token')
                existing_user.oauth_refresh_token = token.get('refresh_token')
                if token.get('expires_at'):
                    existing_user.oauth_token_expires_at = datetime.fromtimestamp(token.get('expires_at'))
                user = existing_user
            else:
                # Create new user with VIEWER role and no airports
                username = email.split('@')[0] + '_' + provider
                user = User(
                    id=str(uuid.uuid4()),
                    email=email,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    oauth_provider=provider,
                    oauth_id=oauth_id,
                    oauth_access_token=token.get('access_token'),
                    oauth_refresh_token=token.get('refresh_token'),
                    oauth_token_expires_at=datetime.fromtimestamp(token.get('expires_at')) if token.get('expires_at') else None,
                    role=UserRole.VIEWER,
                    is_active=True,
                    is_superuser=False
                )
                db.add(user)
        else:
            # Update OAuth tokens and last login
            user.oauth_access_token = token.get('access_token')
            user.oauth_refresh_token = token.get('refresh_token')
            if token.get('expires_at'):
                user.oauth_token_expires_at = datetime.fromtimestamp(token.get('expires_at'))
            user.last_login = datetime.utcnow()

        await db.commit()
        await db.refresh(user)

        # Create JWT tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        # Redirect to frontend with tokens
        redirect_url = f"{settings.FRONTEND_URL}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        # Redirect to frontend with error
        error_url = f"{settings.FRONTEND_URL}/login?error=oauth_failed&message={str(e)}"
        return RedirectResponse(url=error_url)