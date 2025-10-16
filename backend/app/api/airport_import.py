"""
Airport Import API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.db.base import get_db
from app.models import User
from app.schemas.airport import AirportResponse
from app.services.openaip import OpenAIPService, AirportDataService
from app.core.deps import get_current_user, require_role

router = APIRouter(prefix="/airport-import", tags=["Airport Import"])


@router.get("/search")
async def search_airports(
    query: str = Query(..., min_length=2, description="Search query"),
    search_type: str = Query("name", description="Search type: name, icao, iata, city, country"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    current_user: User = Depends(get_current_user)
):
    """Search for airports in global database"""
    
    if search_type not in ['name', 'icao', 'iata', 'city', 'country']:
        raise HTTPException(status_code=400, detail="Invalid search type")
    
    results = await AirportDataService.search_global_airports(
        query=query,
        search_type=search_type,
        limit=limit
    )
    
    return {
        "results": results,
        "count": len(results)
    }


@router.get("/search/icao/{icao_code}")
async def search_airport_by_icao(
    icao_code: str,
    current_user: User = Depends(get_current_user)
):
    """Get airport details by ICAO code"""
    
    if len(icao_code) != 4:
        raise HTTPException(status_code=400, detail="ICAO code must be 4 characters")
    
    airport = await OpenAIPService.search_airports_by_icao(icao_code.upper())
    
    if not airport:
        raise HTTPException(status_code=404, detail="Airport not found")
    
    return airport


@router.get("/search/nearby")
async def search_nearby_airports(
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius: int = Query(100, ge=1, le=500, description="Radius in kilometers"),
    current_user: User = Depends(get_current_user)
):
    """Search for airports near a location"""
    
    results = await OpenAIPService.search_airports_nearby(lat, lon, radius)
    
    return {
        "results": results,
        "count": len(results),
        "center": {"lat": lat, "lon": lon},
        "radius_km": radius
    }


@router.get("/search/country/{country_code}")
async def search_airports_by_country(
    country_code: str,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user)
):
    """Get all airports in a country"""
    
    if len(country_code) != 2:
        raise HTTPException(status_code=400, detail="Country code must be 2 characters (ISO)")
    
    results = await OpenAIPService.search_airports_by_country(
        country_code.upper(),
        limit
    )
    
    return {
        "results": results,
        "count": len(results),
        "country": country_code.upper()
    }


@router.post("/import/{icao_code}")
async def import_airport(
    icao_code: str,
    include_items: bool = Query(False, description="Auto-create airport items based on runway data"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['SUPER_ADMIN', 'AIRPORT_ADMIN']))
):
    """Import an airport from global database into our system"""
    
    if len(icao_code) != 4:
        raise HTTPException(status_code=400, detail="ICAO code must be 4 characters")
    
    # For super admins, no owner. For airport admins, they become the owner
    owner_id = None if current_user.is_superuser else current_user.id
    
    airport = await AirportDataService.import_airport(
        db=db,
        icao_code=icao_code.upper(),
        owner_id=owner_id
    )
    
    if not airport:
        raise HTTPException(
            status_code=404,
            detail=f"Airport {icao_code} not found in global database"
        )
    
    # Count imported runways
    from sqlalchemy import select, func
    from app.models import Runway
    
    runway_count_result = await db.execute(
        select(func.count(Runway.id)).filter(Runway.airport_id == airport.id)
    )
    runway_count = runway_count_result.scalar() or 0
    
    # Auto-create airport items if requested
    items_created = 0
    if include_items and runway_count > 0:
        from app.services.airport_items import AirportItemsService
        from app.models import Runway
        
        # Get runways
        result = await db.execute(
            select(Runway).filter(Runway.airport_id == airport.id)
        )
        runways = result.scalars().all()
        
        airport_data = await OpenAIPService.search_airports_by_icao(icao_code.upper())
        
        if airport_data and airport_data.get('runways'):
            for runway, runway_data in zip(runways, airport_data['runways']):
                items_created += await AirportItemsService.create_runway_items(
                    db=db,
                    airport_id=airport.id,
                    runway=runway,
                    runway_data=runway_data
                )
    
    return {
        "message": f"Airport {airport.name} imported successfully",
        "airport": {
            "id": airport.id,
            "icao_code": airport.icao_code,
            "iata_code": airport.iata_code,
            "name": airport.name,
            "country": airport.country,
            "city": airport.city,
            "latitude": airport.latitude,
            "longitude": airport.longitude,
            "elevation": airport.elevation
        },
        "runways_imported": runway_count,
        "items_created": items_created,
        "frequencies": airport.settings.get('frequencies', []) if airport.settings else [],
        "navaids": airport.settings.get('navaids', []) if airport.settings else []
    }


@router.get("/major-airports")
async def get_major_airports(
    current_user: User = Depends(get_current_user)
):
    """Get a list of major international airports"""
    
    airports = await OpenAIPService.fetch_major_airports()
    
    return {
        "results": airports,
        "count": len(airports)
    }