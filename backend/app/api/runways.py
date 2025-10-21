"""
API endpoints for runway management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from pydantic import BaseModel
import uuid
from datetime import datetime

from app.db.session import get_db
from app.api.auth import get_current_user
from app.models import User, Airport, Runway

router = APIRouter()


class RunwayCreate(BaseModel):
    name: str
    heading: float
    length: int
    width: int
    surface_type: str = "asphalt"
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    is_active: bool = True


class RunwayUpdate(BaseModel):
    name: Optional[str] = None
    heading: Optional[float] = None
    length: Optional[int] = None
    width: Optional[int] = None
    surface_type: Optional[str] = None
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    is_active: Optional[bool] = None


class RunwayResponse(BaseModel):
    id: str
    airport_id: str
    name: str
    heading: float
    length: int
    width: int
    surface_type: str
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/airports/{airport_id}/runways", response_model=dict)
async def get_airport_runways(
    airport_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all runways for an airport"""
    # Check if airport exists
    result = await db.execute(
        select(Airport).where(Airport.id == airport_id)
    )
    airport = result.scalar_one_or_none()
    
    if not airport:
        raise HTTPException(status_code=404, detail="Airport not found")
    
    # Get runways
    result = await db.execute(
        select(Runway).where(Runway.airport_id == airport_id).order_by(Runway.name)
    )
    runways = result.scalars().all()
    
    return {
        "runways": [RunwayResponse.model_validate(r) for r in runways],
        "total": len(runways)
    }


@router.post("/airports/{airport_id}/runways", response_model=RunwayResponse)
async def create_runway(
    airport_id: str,
    runway_data: RunwayCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new runway for an airport"""
    # Check if user is admin
    if not current_user.is_superuser:
        # Check if user has permission for this airport
        user_airports = [a.id for a in current_user.airports]
        if airport_id not in user_airports:
            raise HTTPException(status_code=403, detail="Not authorized for this airport")
    
    # Check if airport exists
    result = await db.execute(
        select(Airport).where(Airport.id == airport_id)
    )
    airport = result.scalar_one_or_none()
    
    if not airport:
        raise HTTPException(status_code=404, detail="Airport not found")
    
    # Check if runway with same name already exists
    result = await db.execute(
        select(Runway).where(
            and_(Runway.airport_id == airport_id, Runway.name == runway_data.name)
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Runway with this name already exists")
    
    # Create runway
    # Exclude calculated properties (end_lat and end_lon are computed from start_lat, start_lon, heading, and length)
    runway_dict = runway_data.dict(exclude={'end_lat', 'end_lon'})
    runway = Runway(
        id=str(uuid.uuid4()),
        airport_id=airport_id,
        **runway_dict
    )
    
    db.add(runway)
    
    # Update airport runway count
    airport.runway_count = (airport.runway_count or 0) + 1
    
    await db.commit()
    await db.refresh(runway)
    
    return RunwayResponse.model_validate(runway)


@router.put("/airports/{airport_id}/runways/{runway_id}", response_model=RunwayResponse)
async def update_runway(
    airport_id: str,
    runway_id: str,
    runway_data: RunwayUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a runway"""
    # Check if user is admin
    if not current_user.is_superuser:
        # Check if user has permission for this airport
        user_airports = [a.id for a in current_user.airports]
        if airport_id not in user_airports:
            raise HTTPException(status_code=403, detail="Not authorized for this airport")
    
    # Get runway
    result = await db.execute(
        select(Runway).where(
            and_(Runway.id == runway_id, Runway.airport_id == airport_id)
        )
    )
    runway = result.scalar_one_or_none()
    
    if not runway:
        raise HTTPException(status_code=404, detail="Runway not found")
    
    # Update runway
    update_data = runway_data.dict(exclude_unset=True)
    # Exclude calculated properties (end_lat and end_lon are computed from start_lat, start_lon, heading, and length)
    calculated_fields = {'end_lat', 'end_lon'}
    for field, value in update_data.items():
        if field not in calculated_fields:
            setattr(runway, field, value)
    
    runway.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(runway)
    
    return RunwayResponse.model_validate(runway)


@router.delete("/airports/{airport_id}/runways/{runway_id}")
async def delete_runway(
    airport_id: str,
    runway_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a runway"""
    # Check if user is admin
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only administrators can delete runways")
    
    # Get runway
    result = await db.execute(
        select(Runway).where(
            and_(Runway.id == runway_id, Runway.airport_id == airport_id)
        )
    )
    runway = result.scalar_one_or_none()
    
    if not runway:
        raise HTTPException(status_code=404, detail="Runway not found")
    
    # Get airport to update runway count
    result = await db.execute(
        select(Airport).where(Airport.id == airport_id)
    )
    airport = result.scalar_one_or_none()
    
    # Delete runway
    await db.delete(runway)
    await db.flush()
    
    # Update airport runway count
    if airport:
        airport.runway_count = max(0, (airport.runway_count or 1) - 1)
    
    await db.commit()
    
    return {"status": "success", "message": "Runway deleted"}


@router.get("/airports/{airport_id}/runways/{runway_id}", response_model=RunwayResponse)
async def get_runway(
    airport_id: str,
    runway_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific runway"""
    result = await db.execute(
        select(Runway).where(
            and_(Runway.id == runway_id, Runway.airport_id == airport_id)
        )
    )
    runway = result.scalar_one_or_none()
    
    if not runway:
        raise HTTPException(status_code=404, detail="Runway not found")
    
    return RunwayResponse.model_validate(runway)