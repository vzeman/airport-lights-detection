"""
API endpoints for managing PAPI reference points
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_serializer
from decimal import Decimal
import uuid
from datetime import datetime

from app.db.base import get_db
from app.api.auth import get_current_user
from app.models import User, Runway, ReferencePoint, ReferencePointType

router = APIRouter()


class ReferencePointCreate(BaseModel):
    point_type: ReferencePointType
    latitude: Decimal  # DECIMAL for centimeter precision
    longitude: Decimal  # DECIMAL for centimeter precision
    altitude: Optional[float] = None
    nominal_angle: Optional[float] = None
    tolerance: Optional[float] = None


class ReferencePointUpdate(BaseModel):
    latitude: Optional[Decimal] = None  # DECIMAL for centimeter precision
    longitude: Optional[Decimal] = None  # DECIMAL for centimeter precision
    altitude: Optional[float] = None
    nominal_angle: Optional[float] = None
    tolerance: Optional[float] = None


class ReferencePointResponse(BaseModel):
    id: str
    runway_id: str
    point_type: ReferencePointType
    latitude: Decimal  # DECIMAL for centimeter precision
    longitude: Decimal  # DECIMAL for centimeter precision
    altitude: Optional[float]
    nominal_angle: Optional[float]
    tolerance: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('latitude', 'longitude')
    def serialize_decimal(self, value: Optional[Decimal]) -> Optional[str]:
        """Serialize Decimal to string to preserve precision"""
        return str(value) if value is not None else None


@router.get("/runways/{runway_id}/reference-points", response_model=dict)
async def get_runway_reference_points(
    runway_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all reference points for a runway"""
    # Check if runway exists
    result = await db.execute(
        select(Runway).where(Runway.id == runway_id)
    )
    runway = result.scalar_one_or_none()
    
    if not runway:
        raise HTTPException(status_code=404, detail="Runway not found")
    
    # Get reference points
    result = await db.execute(
        select(ReferencePoint).where(ReferencePoint.runway_id == runway_id)
    )
    points = result.scalars().all()
    
    return {
        "reference_points": [ReferencePointResponse.model_validate(p) for p in points],
        "total": len(points)
    }


@router.post("/runways/{runway_id}/reference-points", response_model=ReferencePointResponse)
async def create_reference_point(
    runway_id: str,
    point_data: ReferencePointCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new reference point for a runway"""
    # Get runway first
    result = await db.execute(
        select(Runway).where(Runway.id == runway_id)
    )
    runway = result.scalar_one_or_none()

    if not runway:
        raise HTTPException(status_code=404, detail="Runway not found")

    # Check if user is admin
    if not current_user.is_superuser:
        user_airports = [a.id for a in current_user.airports]
        if runway.airport_id not in user_airports:
            raise HTTPException(status_code=403, detail="Not authorized for this airport")

    # Get airport for ICAO code
    from app.models import Airport
    result = await db.execute(
        select(Airport).where(Airport.id == runway.airport_id)
    )
    airport = result.scalar_one_or_none()

    if not airport:
        raise HTTPException(status_code=404, detail="Airport not found")

    # Check if this point type already exists for this runway
    result = await db.execute(
        select(ReferencePoint).where(
            and_(
                ReferencePoint.runway_id == runway_id,
                ReferencePoint.point_type == point_data.point_type
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Reference point {point_data.point_type} already exists for this runway"
        )

    # Create reference point
    ref_point = ReferencePoint(
        id=str(uuid.uuid4()),
        point_id=f"{runway_id}_{point_data.point_type}",
        runway_id=runway_id,
        airport_icao_code=airport.icao_code,
        runway_code=runway.name,
        **point_data.dict()
    )

    db.add(ref_point)
    await db.commit()
    await db.refresh(ref_point)

    return ReferencePointResponse.model_validate(ref_point)


@router.put("/runways/{runway_id}/reference-points/{point_id}", response_model=ReferencePointResponse)
async def update_reference_point(
    runway_id: str,
    point_id: str,
    point_data: ReferencePointUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a reference point"""
    # Check if user is admin
    if not current_user.is_superuser:
        # Check runway's airport
        result = await db.execute(
            select(Runway).where(Runway.id == runway_id)
        )
        runway = result.scalar_one_or_none()
        
        if not runway:
            raise HTTPException(status_code=404, detail="Runway not found")
        
        user_airports = [a.id for a in current_user.airports]
        if runway.airport_id not in user_airports:
            raise HTTPException(status_code=403, detail="Not authorized for this airport")
    
    # Get reference point
    result = await db.execute(
        select(ReferencePoint).where(
            and_(
                ReferencePoint.id == point_id,
                ReferencePoint.runway_id == runway_id
            )
        )
    )
    ref_point = result.scalar_one_or_none()
    
    if not ref_point:
        raise HTTPException(status_code=404, detail="Reference point not found")
    
    # Update reference point
    update_data = point_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ref_point, field, value)
    
    ref_point.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(ref_point)
    
    return ReferencePointResponse.model_validate(ref_point)


@router.delete("/runways/{runway_id}/reference-points/{point_id}")
async def delete_reference_point(
    runway_id: str,
    point_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a reference point"""
    # Check if user is admin
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only administrators can delete reference points")
    
    # Get reference point
    result = await db.execute(
        select(ReferencePoint).where(
            and_(
                ReferencePoint.id == point_id,
                ReferencePoint.runway_id == runway_id
            )
        )
    )
    ref_point = result.scalar_one_or_none()
    
    if not ref_point:
        raise HTTPException(status_code=404, detail="Reference point not found")
    
    await db.delete(ref_point)
    await db.commit()
    
    return {"status": "success", "message": "Reference point deleted"}


@router.post("/runways/{runway_id}/reference-points/bulk", response_model=dict)
async def bulk_update_reference_points(
    runway_id: str,
    points: List[ReferencePointCreate],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk create/update reference points for a runway"""
    # Get runway first (we need it for denormalized fields)
    result = await db.execute(
        select(Runway).where(Runway.id == runway_id)
    )
    runway = result.scalar_one_or_none()

    if not runway:
        raise HTTPException(status_code=404, detail="Runway not found")

    # Check if user is admin
    if not current_user.is_superuser:
        user_airports = [a.id for a in current_user.airports]
        if runway.airport_id not in user_airports:
            raise HTTPException(status_code=403, detail="Not authorized for this airport")

    # Get airport ICAO code
    from app.models import Airport
    result = await db.execute(
        select(Airport).where(Airport.id == runway.airport_id)
    )
    airport = result.scalar_one_or_none()

    if not airport:
        raise HTTPException(status_code=404, detail="Airport not found")

    # Delete existing reference points
    result = await db.execute(
        select(ReferencePoint).where(ReferencePoint.runway_id == runway_id)
    )
    existing_points = result.scalars().all()

    for point in existing_points:
        await db.delete(point)

    # Create new reference points
    created_points = []
    for point_data in points:
        ref_point = ReferencePoint(
            id=str(uuid.uuid4()),
            point_id=f"{runway_id}_{point_data.point_type}",
            runway_id=runway_id,
            airport_icao_code=airport.icao_code,
            runway_code=runway.name,
            **point_data.dict()
        )
        db.add(ref_point)
        created_points.append(ref_point)

    await db.commit()

    # Refresh all points
    for point in created_points:
        await db.refresh(point)

    return {
        "reference_points": [ReferencePointResponse.model_validate(p) for p in created_points],
        "total": len(created_points)
    }