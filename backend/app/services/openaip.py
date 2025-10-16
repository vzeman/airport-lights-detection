"""
OpenAIP Integration Service
Fetches airport data from OpenAIP database
"""

import httpx
import json
import os
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from pathlib import Path

from app.models import Airport
from app.core.config import settings


class OpenAIPService:
    """Service for fetching airport data from OpenAIP"""
    
    # OpenAIP API endpoints
    OPENAIP_URL = "https://api.core.openaip.net/api"
    # Fallback to free airportdb.io API
    AIRPORTDB_URL = "https://api.airportdb.io/v1"
    # OurAirports API for comprehensive data
    OURAIRPORTS_URL = "https://ourairports.com/api"
    
    @staticmethod
    def _load_local_airports() -> List[Dict[str, Any]]:
        """Load local airport data from JSON file"""
        try:
            # Try to find the airports.json file
            current_dir = Path(__file__).parent.parent
            json_path = current_dir / "data" / "airports.json"
            
            if not json_path.exists():
                # Try alternative path
                json_path = Path("/app/app/data/airports.json")
            
            if json_path.exists():
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    return data.get('airports', [])
        except Exception as e:
            print(f"Error loading local airports: {e}")
        
        return []
    
    @staticmethod
    def _get_headers():
        """Get headers with API key for OpenAIP"""
        if settings.OPENAIP_API_KEY:
            return {
                "x-openaip-api-key": settings.OPENAIP_API_KEY,
                "Accept": "application/json"
            }
        return {}
    
    @staticmethod
    async def search_airports_by_icao(icao_code: str) -> Optional[Dict[str, Any]]:
        """Search for an airport by ICAO code"""
        async with httpx.AsyncClient() as client:
            # Try OpenAIP first if we have an API key
            if settings.OPENAIP_API_KEY:
                try:
                    response = await client.get(
                        f"{OpenAIPService.OPENAIP_URL}/airports/{icao_code}",
                        headers=OpenAIPService._get_headers(),
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return OpenAIPService._format_openaip_data(data)
                except Exception as e:
                    print(f"Error fetching from OpenAIP: {e}")
            
            # Fallback to airportdb.io (free, no API key required)
            try:
                response = await client.get(
                    f"{OpenAIPService.AIRPORTDB_URL}/airports/icao/{icao_code}",
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return OpenAIPService._format_airport_data(data)
            except Exception as e:
                print(f"Error fetching from airportdb.io: {e}")
            
            # Fallback to local data
            local_airports = OpenAIPService._load_local_airports()
            for airport in local_airports:
                if airport.get('icao_code') == icao_code:
                    return OpenAIPService._format_airport_data(airport)
            
            return None
    
    @staticmethod
    async def search_airports_by_country(country_code: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Search for airports by country code"""
        # For now, filter from local data
        local_airports = OpenAIPService._load_local_airports()
        filtered = [
            OpenAIPService._format_airport_data(airport) 
            for airport in local_airports 
            if airport.get('country_code', '').upper() == country_code.upper()
        ]
        return filtered[:limit]
    
    @staticmethod
    async def search_airports_nearby(lat: float, lon: float, radius_km: int = 100) -> List[Dict[str, Any]]:
        """Search for airports near a location"""
        # For now, use local data and simple distance calculation
        import math
        
        def haversine_distance(lat1, lon1, lat2, lon2):
            R = 6371  # Earth radius in km
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            return R * c
        
        local_airports = OpenAIPService._load_local_airports()
        nearby = []
        
        for airport in local_airports:
            airport_lat = airport.get('latitude')
            airport_lon = airport.get('longitude')
            if airport_lat and airport_lon:
                distance = haversine_distance(lat, lon, airport_lat, airport_lon)
                if distance <= radius_km:
                    formatted = OpenAIPService._format_airport_data(airport)
                    formatted['distance_km'] = round(distance, 2)
                    nearby.append(formatted)
        
        return sorted(nearby, key=lambda x: x.get('distance_km', 0))
    
    @staticmethod
    def _format_openaip_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format OpenAIP data to match our model"""
        return {
            'icao_code': raw_data.get('icaoCode'),
            'iata_code': raw_data.get('iataCode'),
            'name': raw_data.get('name'),
            'full_name': raw_data.get('longName') or raw_data.get('name'),
            'country': raw_data.get('country'),
            'country_code': raw_data.get('countryCode'),
            'city': raw_data.get('city'),
            'latitude': raw_data.get('geometry', {}).get('coordinates', [None, None])[1] if raw_data.get('geometry') else raw_data.get('latitude'),
            'longitude': raw_data.get('geometry', {}).get('coordinates', [None, None])[0] if raw_data.get('geometry') else raw_data.get('longitude'),
            'elevation': raw_data.get('elevation'),
            'type': raw_data.get('type', 'airport'),
            'runways': raw_data.get('runways', []),
            'frequencies': raw_data.get('frequencies', []),
        }
    
    @staticmethod
    def _format_airport_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format raw airport data to match our model"""
        return {
            'icao_code': raw_data.get('icao_code') or raw_data.get('icao'),
            'iata_code': raw_data.get('iata_code') or raw_data.get('iata'),
            'name': raw_data.get('name'),
            'full_name': raw_data.get('full_name') or raw_data.get('name'),
            'country': raw_data.get('country', {}).get('name') if isinstance(raw_data.get('country'), dict) else raw_data.get('country'),
            'country_code': raw_data.get('country', {}).get('code') if isinstance(raw_data.get('country'), dict) else raw_data.get('country_code'),
            'city': raw_data.get('municipality') or raw_data.get('city'),
            'latitude': raw_data.get('latitude') or raw_data.get('latitude_deg') or raw_data.get('lat'),
            'longitude': raw_data.get('longitude') or raw_data.get('longitude_deg') or raw_data.get('lon'),
            'elevation': raw_data.get('elevation') or raw_data.get('elevation_ft'),
            'type': raw_data.get('type', 'airport'),
            'website': raw_data.get('home_link'),
            'wikipedia': raw_data.get('wikipedia_link'),
            'runways': raw_data.get('runways', []),
            'frequencies': raw_data.get('frequencies', []),
        }
    
    @staticmethod
    async def import_runways_to_db(
        db: AsyncSession,
        airport_id: str,
        runways_data: List[Dict[str, Any]]
    ):
        """Import runway data into database"""
        from app.models import Runway, Airport
        # from geoalchemy2 import WKTElement  # Commented out for SQLite compatibility
        from math import radians, cos, sin
        
        # Get airport coordinates
        result = await db.execute(
            select(Airport).filter(Airport.id == airport_id)
        )
        airport = result.scalars().first()
        if not airport:
            return
            
        for runway_data in runways_data:
            try:
                # Parse runway designator (e.g., "04L/22R" -> two headings)
                designator = runway_data.get('designator', '')
                headings = designator.split('/')
                
                heading_1 = runway_data.get('heading_1', 0)
                heading_2 = runway_data.get('heading_2', 0)
                
                # If headings not provided, try to extract from designator
                if not heading_1 and len(headings) > 0:
                    try:
                        heading_1 = int(''.join(filter(str.isdigit, headings[0]))) * 10
                    except:
                        heading_1 = 0
                
                if not heading_2 and len(headings) > 1:
                    try:
                        heading_2 = int(''.join(filter(str.isdigit, headings[1]))) * 10
                    except:
                        heading_2 = 0
                
                # Check if runway exists
                result = await db.execute(
                    select(Runway).filter(
                        Runway.airport_id == airport_id,
                        Runway.name == designator
                    )
                )
                existing = result.scalars().first()
                
                if not existing:
                    # Create simple runway geometry (centerline)
                    length_m = float(runway_data.get('length', 1000)) * 0.3048  # Convert feet to meters
                    width_m = float(runway_data.get('width', 50)) * 0.3048
                    
                    # Calculate endpoints based on heading
                    lat = airport.latitude
                    lon = airport.longitude
                    heading_rad = radians(heading_1)
                    
                    # Simplified calculation for small distances
                    km_to_deg_lat = 1 / 111.0  
                    km_to_deg_lon = 1 / (111.0 * cos(radians(lat)))
                    
                    # Endpoints
                    lat1 = lat - (length_m / 2000) * km_to_deg_lat * cos(heading_rad)
                    lon1 = lon - (length_m / 2000) * km_to_deg_lon * sin(heading_rad)
                    lat2 = lat + (length_m / 2000) * km_to_deg_lat * cos(heading_rad)
                    lon2 = lon + (length_m / 2000) * km_to_deg_lon * sin(heading_rad)
                    
                    # Create centerline geometry
                    centerline_wkt = f'LINESTRING({lon1} {lat1}, {lon2} {lat2})'
                    
                    # Create boundary polygon (rectangle around centerline)
                    perpendicular = heading_rad + 1.5708  # 90 degrees
                    width_offset_lat = (width_m / 2000) * km_to_deg_lat * cos(perpendicular)
                    width_offset_lon = (width_m / 2000) * km_to_deg_lon * sin(perpendicular)
                    
                    # Four corners of runway
                    p1 = f"{lon1 - width_offset_lon} {lat1 - width_offset_lat}"
                    p2 = f"{lon1 + width_offset_lon} {lat1 + width_offset_lat}"
                    p3 = f"{lon2 + width_offset_lon} {lat2 + width_offset_lat}"
                    p4 = f"{lon2 - width_offset_lon} {lat2 - width_offset_lat}"
                    boundary_wkt = f'POLYGON(({p1}, {p2}, {p3}, {p4}, {p1}))'
                    
                    runway = Runway(
                        id=str(uuid.uuid4()),
                        airport_id=airport_id,
                        name=designator,
                        heading_1=heading_1,
                        heading_2=heading_2,
                        length=float(runway_data.get('length', 0)),
                        width=float(runway_data.get('width', 0)),
                        surface_type=runway_data.get('surface', 'UNKNOWN'),
                        geometry=centerline_wkt,  # Store as WKT string for SQLite compatibility
                        boundary=boundary_wkt,    # Store as WKT string for SQLite compatibility
                        is_active=True
                    )
                    db.add(runway)
                    
                    # Store additional runway data in the Runway model if needed
                    if runway_data.get('ils'):
                        # Store ILS info in properties or create related records
                        pass
                    
                    if runway_data.get('lighting'):
                        # Store lighting info
                        pass
                        
            except Exception as e:
                print(f"Error importing runway {runway_data.get('designator')}: {e}")
        
        await db.commit()
    
    @staticmethod
    async def import_airport_to_db(
        db: AsyncSession,
        airport_data: Dict[str, Any],
        owner_id: Optional[str] = None
    ) -> Airport:
        """Import airport data into our database"""
        # from geoalchemy2 import WKTElement  # Commented out for SQLite compatibility
        from math import radians, cos
        
        # Check if airport already exists
        result = await db.execute(
            select(Airport).filter(Airport.icao_code == airport_data['icao_code'])
        )
        existing = result.scalars().first()
        
        if existing:
            # Convert elevation from feet to meters
            elevation_ft = airport_data.get('elevation')
            if elevation_ft is not None:
                existing.elevation = elevation_ft * 0.3048  # Convert feet to meters
            
            # Update existing airport settings
            existing.settings = {
                'country_code': airport_data.get('country_code'),
                'frequencies': airport_data.get('frequencies', []),
                'navaids': airport_data.get('navaids', []),
                'magnetic_declination': airport_data.get('magnetic_declination'),
                'type': airport_data.get('type', 'airport'),
                'wikipedia': airport_data.get('wikipedia'),
                'website': airport_data.get('website')
            }
            await db.commit()
            
            # Import/update runways if available
            if airport_data.get('runways'):
                await OpenAIPService.import_runways_to_db(
                    db=db,
                    airport_id=existing.id,
                    runways_data=airport_data['runways']
                )
            
            return existing
        
        # Create a simple boundary polygon around the airport (5km square)
        lat = airport_data['latitude']
        lon = airport_data['longitude']
        km_to_deg_lat = 1 / 111.0  
        km_to_deg_lon = 1 / (111.0 * cos(radians(lat)))
        offset = 2.5  # km
        n = lat + offset * km_to_deg_lat
        s = lat - offset * km_to_deg_lat
        e = lon + offset * km_to_deg_lon
        w = lon - offset * km_to_deg_lon
        boundary_wkt = f'POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))'
        
        # Convert elevation from feet to meters
        elevation_ft = airport_data.get('elevation')
        elevation_m = None
        if elevation_ft is not None:
            elevation_m = elevation_ft * 0.3048  # Convert feet to meters
        
        # Create new airport
        airport = Airport(
            id=str(uuid.uuid4()),
            icao_code=airport_data['icao_code'],
            iata_code=airport_data.get('iata_code'),
            name=airport_data['name'],
            full_name=airport_data.get('full_name'),
            country=airport_data['country'],
            city=airport_data.get('city'),
            latitude=airport_data['latitude'],
            longitude=airport_data['longitude'],
            elevation=elevation_m,
            timezone=airport_data.get('timezone', 'UTC'),
            created_by=owner_id,
            compliance_framework='ICAO',
            is_active=True,
            boundary=boundary_wkt  # Store as WKT string for SQLite compatibility
        )
        
        # Store extended data in airport settings field
        airport.settings = {
            'country_code': airport_data.get('country_code'),
            'frequencies': airport_data.get('frequencies', []),
            'navaids': airport_data.get('navaids', []),
            'magnetic_declination': airport_data.get('magnetic_declination'),
            'type': airport_data.get('type', 'airport'),
            'wikipedia': airport_data.get('wikipedia'),
            'website': airport_data.get('website')
        }
        
        db.add(airport)
        await db.commit()
        await db.refresh(airport)
        
        # Import runways if available
        if airport_data.get('runways'):
            await OpenAIPService.import_runways_to_db(
                db=db,
                airport_id=airport.id,
                runways_data=airport_data['runways']
            )
        
        return airport
    
    @staticmethod
    async def fetch_major_airports() -> List[Dict[str, Any]]:
        """Fetch a list of major international airports"""
        # Try to use local data first
        local_airports = OpenAIPService._load_local_airports()
        if local_airports:
            # Format all airports from local data
            return [OpenAIPService._format_airport_data(airport) for airport in local_airports[:20]]
        
        # If no local data, try to fetch from API
        major_airports = [
            'KJFK',  # JFK New York
            'KLAX',  # Los Angeles
            'KORD',  # Chicago O'Hare
            'KATL',  # Atlanta
            'EGLL',  # London Heathrow
            'LFPG',  # Paris Charles de Gaulle
            'EDDF',  # Frankfurt
            'EHAM',  # Amsterdam Schiphol
            'OMDB',  # Dubai
            'VHHH',  # Hong Kong
            'RJTT',  # Tokyo Haneda
            'WSSS',  # Singapore Changi
            'YSSY',  # Sydney
            'ZBAA',  # Beijing Capital
        ]
        
        airports = []
        for icao in major_airports:
            airport = await OpenAIPService.search_airports_by_icao(icao)
            if airport:
                airports.append(airport)
        
        return airports


class AirportDataService:
    """Service for managing airport data from various sources"""
    
    @staticmethod
    async def search_global_airports(
        query: str,
        search_type: str = 'name',
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for airports globally
        search_type: 'name', 'icao', 'iata', 'city', 'country'
        """
        results = []
        query_lower = query.lower()
        
        if search_type == 'icao' and len(query) == 4:
            # Direct ICAO lookup
            airport = await OpenAIPService.search_airports_by_icao(query.upper())
            if airport:
                results.append(airport)
        
        elif search_type == 'country' and len(query) == 2:
            # Country code search
            results = await OpenAIPService.search_airports_by_country(query.upper(), limit)
        
        else:
            # Search through local data for other types
            local_airports = OpenAIPService._load_local_airports()
            
            for airport in local_airports:
                matched = False
                
                if search_type == 'name':
                    name = (airport.get('name') or '').lower()
                    if query_lower in name:
                        matched = True
                        
                elif search_type == 'iata':
                    iata = (airport.get('iata_code') or '').lower()
                    if iata == query_lower:
                        matched = True
                        
                elif search_type == 'city':
                    city = (airport.get('city') or '').lower()
                    if query_lower in city:
                        matched = True
                
                if matched:
                    results.append(OpenAIPService._format_airport_data(airport))
                    if len(results) >= limit:
                        break
        
        return results[:limit]
    
    @staticmethod
    async def import_airport(
        db: AsyncSession,
        icao_code: str,
        owner_id: Optional[str] = None
    ) -> Optional[Airport]:
        """Import an airport from external data source"""
        airport_data = await OpenAIPService.search_airports_by_icao(icao_code)
        
        if airport_data:
            return await OpenAIPService.import_airport_to_db(db, airport_data, owner_id)
        
        return None