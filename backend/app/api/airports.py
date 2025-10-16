from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional, List
import uuid

from app.db.base import get_db
from app.models import Airport, User, UserRole, AirportItem, ItemType, Runway
from app.schemas.airport import (
    AirportCreate, AirportUpdate, AirportResponse, AirportListResponse,
    ItemTypeCreate, ItemTypeUpdate, ItemTypeResponse,
    AirportItemCreate, AirportItemUpdate, AirportItemResponse,
    RunwayCreate, RunwayUpdate, RunwayResponse
)
from app.core.deps import get_current_user, require_role
# from shapely.geometry import Point, Polygon, LineString  # Commented out for SQLite compatibility
# from geoalchemy2.shape import from_shape, to_shape  # Commented out for SQLite compatibility
import json

router = APIRouter(prefix="/airports", tags=["Airports"])


@router.get("", response_model=AirportListResponse)
async def list_airports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    country: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List airports accessible to the current user"""
    query = select(Airport)
    count_query = select(func.count()).select_from(Airport)
    
    # If not superuser, filter by assigned airports
    if not current_user.is_superuser:
        query = query.join(Airport.users).filter(User.id == current_user.id)
        count_query = count_query.join(Airport.users).filter(User.id == current_user.id)
    
    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            Airport.name.ilike(search_filter) |
            Airport.icao_code.ilike(search_filter) |
            Airport.iata_code.ilike(search_filter)
        )
        count_query = count_query.filter(
            Airport.name.ilike(search_filter) |
            Airport.icao_code.ilike(search_filter) |
            Airport.iata_code.ilike(search_filter)
        )
    
    if country:
        query = query.filter(Airport.country == country)
        count_query = count_query.filter(Airport.country == country)
    
    if is_active is not None:
        query = query.filter(Airport.is_active == is_active)
        count_query = count_query.filter(Airport.is_active == is_active)
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # Execute query
    result = await db.execute(query)
    airports = result.scalars().all()
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "airports": airports
    }


@router.get("/{airport_id}", response_model=AirportResponse)
async def get_airport(
    airport_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get airport by ID"""
    query = select(Airport).filter(Airport.id == airport_id)
    
    # Check access
    if not current_user.is_superuser:
        query = query.join(Airport.users).filter(User.id == current_user.id)
    
    result = await db.execute(query)
    airport = result.scalars().first()
    
    if not airport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airport not found or access denied"
        )
    
    return airport


@router.post("", response_model=AirportResponse, status_code=status.HTTP_201_CREATED)
async def create_airport(
    airport_data: AirportCreate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.AIRPORT_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Create a new airport"""
    # Check if ICAO code already exists
    existing = await db.execute(
        select(Airport).filter(Airport.icao_code == airport_data.icao_code)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Airport with this ICAO code already exists"
        )
    
    # Create airport
    airport = Airport(
        id=str(uuid.uuid4()),
        **airport_data.model_dump(),
        created_by=current_user.id
    )
    
    # Add creating user to airport users
    airport.users.append(current_user)
    
    db.add(airport)
    await db.commit()
    await db.refresh(airport)
    
    return airport


@router.patch("/{airport_id}", response_model=AirportResponse)
async def update_airport(
    airport_id: str,
    airport_data: AirportUpdate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.AIRPORT_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Update airport information"""
    query = select(Airport).filter(Airport.id == airport_id)
    
    # Check access
    if not current_user.is_superuser:
        query = query.join(Airport.users).filter(User.id == current_user.id)
    
    result = await db.execute(query)
    airport = result.scalars().first()
    
    if not airport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airport not found or access denied"
        )
    
    # Update fields
    for field, value in airport_data.model_dump(exclude_unset=True).items():
        if hasattr(airport, field):
            setattr(airport, field, value)
    
    await db.commit()
    await db.refresh(airport)
    
    return airport


@router.delete("/{airport_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_airport(
    airport_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: AsyncSession = Depends(get_db)
):
    """Delete an airport (Super admin only)"""
    result = await db.execute(select(Airport).filter(Airport.id == airport_id))
    airport = result.scalars().first()
    
    if not airport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airport not found"
        )
    
    await db.delete(airport)
    await db.commit()
    
    return None


# Airport Items endpoints
@router.get("/{airport_id}/items", response_model=List[AirportItemResponse])
async def list_airport_items(
    airport_id: str,
    item_type_id: Optional[str] = None,
    runway_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all items in an airport"""
    # Check airport access
    airport_query = select(Airport).filter(Airport.id == airport_id)
    if not current_user.is_superuser:
        airport_query = airport_query.join(Airport.users).filter(User.id == current_user.id)
    
    airport_result = await db.execute(airport_query)
    if not airport_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airport not found or access denied"
        )
    
    # Query items
    query = select(AirportItem).filter(AirportItem.airport_id == airport_id)
    
    if item_type_id:
        query = query.filter(AirportItem.item_type_id == item_type_id)
    if runway_id:
        query = query.filter(AirportItem.runway_id == runway_id)
    if status:
        query = query.filter(AirportItem.status == status)
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    # Convert geometry to GeoJSON
    response_items = []
    for item in items:
        item_dict = {
            "id": item.id,
            "airport_id": item.airport_id,
            "item_type_id": item.item_type_id,
            "runway_id": item.runway_id,
            "name": item.name,
            "code": item.code,
            "serial_number": item.serial_number,
            "latitude": item.latitude,
            "longitude": item.longitude,
            "elevation": item.elevation,
            "geometry": item.geometry if item.geometry else None,  # Direct JSON storage
            "properties": item.properties,
            "specifications": item.specifications,
            "status": item.status,
            "is_active": item.is_active,
            "compliance_status": item.compliance_status,
            "installation_date": item.installation_date,
            "last_inspection_date": item.last_inspection_date,
            "next_inspection_date": item.next_inspection_date,
            "last_maintenance_date": item.last_maintenance_date,
            "next_maintenance_date": item.next_maintenance_date,
            "created_at": item.created_at,
            "updated_at": item.updated_at
        }
        response_items.append(AirportItemResponse(**item_dict))
    
    return response_items


@router.post("/{airport_id}/items", response_model=AirportItemResponse, status_code=status.HTTP_201_CREATED)
async def create_airport_item(
    airport_id: str,
    item_data: AirportItemCreate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.AIRPORT_ADMIN, UserRole.MAINTENANCE_MANAGER])),
    db: AsyncSession = Depends(get_db)
):
    """Create a new item in an airport"""
    # Verify airport access
    airport_query = select(Airport).filter(Airport.id == airport_id)
    if not current_user.is_superuser:
        airport_query = airport_query.join(Airport.users).filter(User.id == current_user.id)
    
    airport_result = await db.execute(airport_query)
    if not airport_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Airport not found or access denied"
        )
    
    # Create item
    item_dict = item_data.model_dump()
    geometry_data = item_dict.pop("geometry", None)
    
    item = AirportItem(
        id=str(uuid.uuid4()),
        **item_dict
    )
    
    # Set geometry if provided (storing as JSON directly for SQLite)
    if geometry_data:
        item.geometry = geometry_data  # Store GeoJSON directly
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    # Convert geometry back to GeoJSON for response
    item_response = {
        **item.__dict__,
        "geometry": to_shape(item.geometry).__geo_interface__ if item.geometry else None
    }
    
    return AirportItemResponse(**item_response)