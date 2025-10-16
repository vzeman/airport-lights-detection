"""
Airspace API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from datetime import datetime

from app.db.base import get_db
from app.models import User
from app.models.airspace import Airspace, AirspaceType, AirspaceClass
from app.services.airspace_service import AirspaceService
from app.core.deps import get_current_user

router = APIRouter(prefix="/airspaces", tags=["Airspaces"])


@router.post("/import")
async def import_airspaces(
    center_lat: float = Query(..., description="Center latitude"),
    center_lon: float = Query(..., description="Center longitude"),
    radius_km: float = Query(100, description="Radius in kilometers"),
    airport_id: Optional[str] = Query(None, description="Associated airport ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Import airspaces from OpenAIP or local data within radius of a point
    """
    
    try:
        # Import airspaces
        imported_airspaces = await AirspaceService.import_airspaces_from_openaip(
            db=db,
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius_km
        )
        
        # Associate with airport if provided
        if airport_id and imported_airspaces:
            for airspace in imported_airspaces:
                airspace.airport_id = airport_id
            await db.commit()
        
        return {
            "message": f"Successfully imported {len(imported_airspaces)} airspaces",
            "airspaces": [
                {
                    "id": a.id,
                    "name": a.name,
                    "type": a.airspace_type.value,
                    "class": a.airspace_class.value,
                    "lower_limit": f"{a.lower_limit_value} {a.lower_limit_reference.value}",
                    "upper_limit": f"{a.upper_limit_value} {a.upper_limit_reference.value}"
                }
                for a in imported_airspaces
            ],
            "center": {"lat": center_lat, "lon": center_lon},
            "radius_km": radius_km
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing airspaces: {str(e)}")


@router.get("/")
async def get_airspaces(
    bbox: Optional[str] = Query(None, description="Bounding box: north,south,east,west"),
    min_altitude_m: Optional[float] = Query(None, description="Minimum altitude in meters"),
    max_altitude_m: Optional[float] = Query(None, description="Maximum altitude in meters"),
    types: Optional[str] = Query(None, description="Comma-separated airspace types"),
    airport_id: Optional[str] = Query(None, description="Filter by airport"),
    active_only: bool = Query(True, description="Only active airspaces"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get airspaces with filtering options for map display
    """
    
    # Parse bounding box
    bounds = None
    if bbox:
        try:
            parts = bbox.split(',')
            if len(parts) == 4:
                bounds = {
                    'north': float(parts[0]),
                    'south': float(parts[1]),
                    'east': float(parts[2]),
                    'west': float(parts[3])
                }
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bbox format")
    
    # Parse types
    type_list = None
    if types:
        type_list = []
        for t in types.split(','):
            try:
                type_list.append(AirspaceType(t))
            except ValueError:
                pass  # Skip invalid types
    
    # Get airspaces
    airspaces = await AirspaceService.get_airspaces_for_display(
        db=db,
        bounds=bounds,
        min_altitude_m=min_altitude_m,
        max_altitude_m=max_altitude_m,
        types=type_list
    )
    
    return {
        "airspaces": airspaces,
        "total": len(airspaces),
        "filters": {
            "bbox": bounds,
            "min_altitude_m": min_altitude_m,
            "max_altitude_m": max_altitude_m,
            "types": types
        }
    }


@router.get("/{airspace_id}")
async def get_airspace_detail(
    airspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed information about a specific airspace"""
    
    result = await db.execute(
        select(Airspace).filter(Airspace.id == airspace_id)
    )
    airspace = result.scalars().first()
    
    if not airspace:
        raise HTTPException(status_code=404, detail="Airspace not found")
    
    return {
        "id": airspace.id,
        "name": airspace.name,
        "code": airspace.code,
        "icao_designator": airspace.icao_designator,
        "country": airspace.country,
        "type": airspace.airspace_type.value,
        "class": airspace.airspace_class.value,
        "vertical_limits": {
            "lower": {
                "value": airspace.lower_limit_value,
                "reference": airspace.lower_limit_reference.value,
                "unit": airspace.lower_limit_unit,
                "meters": airspace.lower_limit_meters
            },
            "upper": {
                "value": airspace.upper_limit_value,
                "reference": airspace.upper_limit_reference.value,
                "unit": airspace.upper_limit_unit,
                "meters": airspace.upper_limit_meters
            }
        },
        "geometry": str(airspace.geometry),
        "area_sq_km": airspace.area_sq_km,
        "center": {
            "lat": float(airspace.center_latitude) if airspace.center_latitude else None,
            "lon": float(airspace.center_longitude) if airspace.center_longitude else None
        },
        "frequencies": airspace.frequencies or [],
        "active_times": airspace.active_times or {"schedule": "H24"},
        "controlling_authority": airspace.controlling_authority,
        "restrictions": airspace.restrictions or {},
        "notes": airspace.notes,
        "visualization": {
            "border_color": airspace.border_color,
            "fill_color": airspace.fill_color,
            "opacity": airspace.opacity,
            "priority": airspace.display_priority
        },
        "metadata": {
            "source": airspace.source,
            "source_updated": airspace.source_updated.isoformat() if airspace.source_updated else None,
            "created_at": airspace.created_at.isoformat(),
            "updated_at": airspace.updated_at.isoformat()
        }
    }


@router.get("/types/list")
async def get_airspace_types(
    current_user: User = Depends(get_current_user)
):
    """Get list of available airspace types and classes"""
    
    return {
        "types": [
            {
                "value": t.value,
                "name": t.name,
                "description": {
                    AirspaceType.CTR: "Control Zone",
                    AirspaceType.TMA: "Terminal Control Area",
                    AirspaceType.CTA: "Control Area",
                    AirspaceType.ATZ: "Aerodrome Traffic Zone",
                    AirspaceType.PROHIBITED: "Prohibited Area",
                    AirspaceType.RESTRICTED: "Restricted Area",
                    AirspaceType.DANGER: "Danger Area",
                    AirspaceType.FIR: "Flight Information Region",
                    AirspaceType.GLIDING: "Gliding Area",
                }.get(t, t.name)
            }
            for t in AirspaceType
        ],
        "classes": [
            {
                "value": c.value,
                "name": c.name,
                "description": {
                    AirspaceClass.CLASS_A: "IFR only, ATC clearance required",
                    AirspaceClass.CLASS_B: "IFR and VFR, ATC clearance required",
                    AirspaceClass.CLASS_C: "IFR and VFR, ATC clearance for IFR",
                    AirspaceClass.CLASS_D: "IFR and VFR, ATC clearance for IFR",
                    AirspaceClass.CLASS_E: "IFR and VFR, ATC clearance for IFR only",
                    AirspaceClass.CLASS_F: "IFR and VFR, ATC advisory service",
                    AirspaceClass.CLASS_G: "Uncontrolled airspace",
                }.get(c, c.name)
            }
            for c in AirspaceClass
        ]
    }


@router.delete("/{airspace_id}")
async def delete_airspace(
    airspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an airspace"""
    
    result = await db.execute(
        select(Airspace).filter(Airspace.id == airspace_id)
    )
    airspace = result.scalars().first()
    
    if not airspace:
        raise HTTPException(status_code=404, detail="Airspace not found")
    
    await db.delete(airspace)
    await db.commit()
    
    return {"message": f"Airspace {airspace.name} deleted successfully"}