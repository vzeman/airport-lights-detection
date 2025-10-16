"""
Airspace Service for importing and managing airspace data
"""

import httpx
import json
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
# from geoalchemy2 import WKTElement  # Commented out for SQLite compatibility
from datetime import datetime
import math

from app.models.airspace import (
    Airspace, AirspaceClass, AirspaceType, 
    AltitudeReference, AirspaceSegment
)
from app.core.config import settings


class AirspaceService:
    """Service for managing airspace data from various sources"""
    
    # Standard colors for different airspace types
    AIRSPACE_COLORS = {
        AirspaceType.CTR: {"border": "#FF0000", "fill": "#FF0000"},  # Red
        AirspaceType.TMA: {"border": "#FF6600", "fill": "#FF6600"},  # Orange
        AirspaceType.CTA: {"border": "#0066FF", "fill": "#0066FF"},  # Blue
        AirspaceType.ATZ: {"border": "#9900FF", "fill": "#9900FF"},  # Purple
        AirspaceType.PROHIBITED: {"border": "#CC0000", "fill": "#CC0000"},  # Dark Red
        AirspaceType.RESTRICTED: {"border": "#FF3333", "fill": "#FF3333"},  # Light Red
        AirspaceType.DANGER: {"border": "#FF9900", "fill": "#FF9900"},  # Orange
        AirspaceType.FIR: {"border": "#00AA00", "fill": "#00AA00"},  # Green
        AirspaceType.GLIDING: {"border": "#00CCCC", "fill": "#00CCCC"},  # Cyan
    }
    
    # Display priorities (higher = on top)
    AIRSPACE_PRIORITIES = {
        AirspaceType.PROHIBITED: 100,
        AirspaceType.RESTRICTED: 90,
        AirspaceType.DANGER: 85,
        AirspaceType.CTR: 80,
        AirspaceType.ATZ: 75,
        AirspaceType.TMA: 70,
        AirspaceType.CTA: 60,
        AirspaceType.FIR: 30,
    }
    
    @staticmethod
    async def import_airspaces_from_openaip(
        db: AsyncSession,
        center_lat: float,
        center_lon: float,
        radius_km: float = 100
    ) -> List[Airspace]:
        """Import airspaces from OpenAIP within radius of a point"""
        
        airspaces = []
        
        # Try OpenAIP API if we have a key
        if settings.OPENAIP_API_KEY:
            airspaces = await AirspaceService._fetch_openaip_airspaces(
                center_lat, center_lon, radius_km
            )
        
        # Fallback to local data
        if not airspaces:
            airspaces = await AirspaceService._load_local_airspaces(
                center_lat, center_lon, radius_km
            )
        
        # Import to database
        imported = []
        for airspace_data in airspaces:
            airspace = await AirspaceService._import_airspace_to_db(
                db, airspace_data
            )
            if airspace:
                imported.append(airspace)
        
        return imported
    
    @staticmethod
    async def _fetch_openaip_airspaces(
        center_lat: float,
        center_lon: float,
        radius_km: float
    ) -> List[Dict[str, Any]]:
        """Fetch airspaces from OpenAIP API"""
        
        async with httpx.AsyncClient() as client:
            try:
                headers = {
                    "x-openaip-api-key": settings.OPENAIP_API_KEY,
                    "Accept": "application/json"
                }
                
                # OpenAIP endpoint for airspaces
                response = await client.get(
                    f"https://api.core.openaip.net/api/airspaces",
                    params={
                        "lat": center_lat,
                        "lon": center_lon,
                        "radius": radius_km
                    },
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return [AirspaceService._format_openaip_airspace(a) 
                           for a in data.get('airspaces', [])]
                           
            except Exception as e:
                print(f"Error fetching from OpenAIP: {e}")
                
        return []
    
    @staticmethod
    async def _load_local_airspaces(
        center_lat: float,
        center_lon: float,
        radius_km: float
    ) -> List[Dict[str, Any]]:
        """Load airspaces from local data file"""
        
        # Load from local JSON file
        from pathlib import Path
        import json
        
        try:
            current_dir = Path(__file__).parent.parent
            json_path = current_dir / "data" / "airspaces.json"
            
            if json_path.exists():
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    
                # Filter by distance
                filtered = []
                for airspace in data.get('airspaces', []):
                    if AirspaceService._is_within_radius(
                        airspace, center_lat, center_lon, radius_km
                    ):
                        filtered.append(airspace)
                
                return filtered
                
        except Exception as e:
            print(f"Error loading local airspaces: {e}")
            
        return []
    
    @staticmethod
    def _format_openaip_airspace(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format OpenAIP airspace data to our model"""
        
        # Map OpenAIP types to our types
        type_mapping = {
            'CTR': AirspaceType.CTR,
            'TMA': AirspaceType.TMA,
            'CTA': AirspaceType.CTA,
            'ATZ': AirspaceType.ATZ,
            'PROHIBITED': AirspaceType.PROHIBITED,
            'RESTRICTED': AirspaceType.RESTRICTED,
            'DANGER': AirspaceType.DANGER,
            'FIR': AirspaceType.FIR,
            'UIR': AirspaceType.UIR,
            'GLIDING': AirspaceType.GLIDING,
            'WAVE': AirspaceType.GLIDING,
            'TMZ': AirspaceType.TMA,
            'RMZ': AirspaceType.TMA,
        }
        
        # Map airspace classes
        class_mapping = {
            'A': AirspaceClass.CLASS_A,
            'B': AirspaceClass.CLASS_B,
            'C': AirspaceClass.CLASS_C,
            'D': AirspaceClass.CLASS_D,
            'E': AirspaceClass.CLASS_E,
            'F': AirspaceClass.CLASS_F,
            'G': AirspaceClass.CLASS_G,
            'UNCLASSIFIED': AirspaceClass.CLASS_G,
        }
        
        airspace_type = type_mapping.get(
            raw_data.get('type', 'CTR').upper(),
            AirspaceType.CTR
        )
        
        return {
            'name': raw_data.get('name'),
            'code': raw_data.get('code'),
            'icao_designator': raw_data.get('icaoCode'),
            'country': raw_data.get('country'),
            'airspace_class': class_mapping.get(
                raw_data.get('class', 'G'),
                AirspaceClass.CLASS_G
            ),
            'airspace_type': airspace_type,
            'lower_limit': raw_data.get('lowerLimit', {}),
            'upper_limit': raw_data.get('upperLimit', {}),
            'geometry': raw_data.get('geometry'),
            'frequencies': raw_data.get('frequencies', []),
            'active_times': raw_data.get('activeTimes'),
            'notes': raw_data.get('remarks'),
        }
    
    @staticmethod
    async def _import_airspace_to_db(
        db: AsyncSession,
        airspace_data: Dict[str, Any]
    ) -> Optional[Airspace]:
        """Import airspace data into database"""
        
        try:
            # Parse altitude limits
            lower_value, lower_ref, lower_meters = AirspaceService._parse_altitude(
                airspace_data.get('lower_limit', {})
            )
            upper_value, upper_ref, upper_meters = AirspaceService._parse_altitude(
                airspace_data.get('upper_limit', {})
            )
            
            # Create geometry from coordinates
            geometry_wkt = AirspaceService._create_polygon_wkt(
                airspace_data.get('geometry', {})
            )
            
            if not geometry_wkt:
                return None
            
            # Calculate center point
            center_lat, center_lon = AirspaceService._calculate_center(
                airspace_data.get('geometry', {})
            )
            
            # Get colors and priority
            airspace_type = airspace_data.get('airspace_type', AirspaceType.CTR)
            colors = AirspaceService.AIRSPACE_COLORS.get(
                airspace_type, 
                {"border": "#666666", "fill": "#666666"}
            )
            priority = AirspaceService.AIRSPACE_PRIORITIES.get(airspace_type, 50)
            
            # Check if airspace exists
            existing = await db.execute(
                select(Airspace).filter(
                    and_(
                        Airspace.name == airspace_data['name'],
                        Airspace.airspace_type == airspace_type
                    )
                )
            )
            if existing.scalars().first():
                return None  # Skip if already exists
            
            # Create airspace
            airspace = Airspace(
                name=airspace_data['name'],
                code=airspace_data.get('code'),
                icao_designator=airspace_data.get('icao_designator'),
                country=airspace_data.get('country', 'Unknown'),
                airspace_class=airspace_data.get('airspace_class', AirspaceClass.CLASS_G),
                airspace_type=airspace_type,
                lower_limit_value=lower_value,
                lower_limit_reference=lower_ref,
                lower_limit_meters=lower_meters,
                upper_limit_value=upper_value,
                upper_limit_reference=upper_ref,
                upper_limit_meters=upper_meters,
                geometry=geometry_wkt,  # Store as WKT string for SQLite compatibility
                center_latitude=center_lat,
                center_longitude=center_lon,
                frequencies=airspace_data.get('frequencies'),
                active_times=airspace_data.get('active_times'),
                notes=airspace_data.get('notes'),
                border_color=colors['border'],
                fill_color=colors['fill'],
                opacity=0.3,
                display_priority=priority,
                source='OpenAIP',
                source_updated=datetime.utcnow(),
                is_active=True
            )
            
            db.add(airspace)
            await db.commit()
            await db.refresh(airspace)
            
            return airspace
            
        except Exception as e:
            print(f"Error importing airspace {airspace_data.get('name')}: {e}")
            await db.rollback()
            return None
    
    @staticmethod
    def _parse_altitude(altitude_data: Dict[str, Any]) -> Tuple[float, AltitudeReference, float]:
        """Parse altitude data and convert to meters"""
        
        value = altitude_data.get('value', 0)
        unit = altitude_data.get('unit', 'FT')
        reference = altitude_data.get('reference', 'MSL')
        
        # Map references
        ref_mapping = {
            'MSL': AltitudeReference.MSL,
            'AGL': AltitudeReference.AGL,
            'FL': AltitudeReference.FL,
            'SFC': AltitudeReference.SFC,
            'GND': AltitudeReference.SFC,
            'UNL': AltitudeReference.UNL,
            'UNLIMITED': AltitudeReference.UNL,
        }
        
        altitude_ref = ref_mapping.get(reference.upper(), AltitudeReference.MSL)
        
        # Convert to meters
        if altitude_ref == AltitudeReference.SFC:
            meters = 0
        elif altitude_ref == AltitudeReference.UNL:
            meters = 99999  # Unlimited
        elif altitude_ref == AltitudeReference.FL:
            meters = value * 100 * 0.3048  # FL to feet to meters
        else:
            if unit.upper() == 'M':
                meters = value
            else:  # Assume feet
                meters = value * 0.3048
        
        return value, altitude_ref, meters
    
    @staticmethod
    def _create_polygon_wkt(geometry_data: Any) -> Optional[str]:
        """Create WKT polygon from geometry data"""
        
        if isinstance(geometry_data, dict):
            if geometry_data.get('type') == 'Polygon':
                coords = geometry_data.get('coordinates', [[]])[0]
                if coords:
                    points = ', '.join([f"{lon} {lat}" for lon, lat in coords])
                    return f"POLYGON(({points}))"
        
        elif isinstance(geometry_data, list):
            # Assume it's a list of coordinates
            if geometry_data:
                points = ', '.join([f"{point.get('lon', point.get('longitude', 0))} "
                                 f"{point.get('lat', point.get('latitude', 0))}" 
                                 for point in geometry_data])
                return f"POLYGON(({points}))"
        
        return None
    
    @staticmethod
    def _calculate_center(geometry_data: Any) -> Tuple[float, float]:
        """Calculate center point of geometry"""
        
        coords = []
        
        if isinstance(geometry_data, dict):
            if geometry_data.get('type') == 'Polygon':
                coords = geometry_data.get('coordinates', [[]])[0]
        elif isinstance(geometry_data, list):
            coords = [(point.get('lon', point.get('longitude', 0)),
                      point.get('lat', point.get('latitude', 0))) 
                     for point in geometry_data]
        
        if coords:
            lats = [c[1] for c in coords]
            lons = [c[0] for c in coords]
            return sum(lats) / len(lats), sum(lons) / len(lons)
        
        return 0, 0
    
    @staticmethod
    def _is_within_radius(
        airspace: Dict[str, Any],
        center_lat: float,
        center_lon: float,
        radius_km: float
    ) -> bool:
        """Check if airspace is within radius of a point"""
        
        # Get airspace center
        geometry = airspace.get('geometry', {})
        airspace_lat, airspace_lon = AirspaceService._calculate_center(geometry)
        
        # Calculate distance
        from math import radians, cos, sin, sqrt, atan2
        
        R = 6371  # Earth radius in km
        dlat = radians(airspace_lat - center_lat)
        dlon = radians(airspace_lon - center_lon)
        a = sin(dlat/2)**2 + cos(radians(center_lat)) * cos(radians(airspace_lat)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance <= radius_km
    
    @staticmethod
    async def get_airspaces_for_display(
        db: AsyncSession,
        bounds: Dict[str, float],  # {"north": lat, "south": lat, "east": lon, "west": lon}
        min_altitude_m: Optional[float] = None,
        max_altitude_m: Optional[float] = None,
        types: Optional[List[AirspaceType]] = None
    ) -> List[Dict[str, Any]]:
        """Get airspaces for map display with filtering"""
        
        query = select(Airspace).filter(Airspace.is_active == True)
        
        # Filter by bounds (simple bbox check on center point)
        if bounds:
            query = query.filter(
                and_(
                    Airspace.center_latitude.between(bounds['south'], bounds['north']),
                    Airspace.center_longitude.between(bounds['west'], bounds['east'])
                )
            )
        
        # Filter by altitude
        if min_altitude_m is not None:
            query = query.filter(Airspace.upper_limit_meters >= min_altitude_m)
        if max_altitude_m is not None:
            query = query.filter(Airspace.lower_limit_meters <= max_altitude_m)
        
        # Filter by types
        if types:
            query = query.filter(Airspace.airspace_type.in_(types))
        
        # Order by display priority
        query = query.order_by(Airspace.display_priority.desc())
        
        result = await db.execute(query)
        airspaces = result.scalars().all()
        
        # Format for frontend display
        return [AirspaceService._format_for_display(a) for a in airspaces]
    
    @staticmethod
    def _format_for_display(airspace: Airspace) -> Dict[str, Any]:
        """Format airspace for map display"""
        
        # Convert geometry to GeoJSON for frontend
        # from geoalchemy2.shape import to_shape  # Commented out for SQLite compatibility
        import json
        
        geometry_geojson = None
        if airspace.geometry:
            try:
                # For SQLite compatibility, geometry is stored as WKT string
                # Parse WKT POLYGON string to GeoJSON format
                wkt_str = str(airspace.geometry)
                if wkt_str.startswith('POLYGON'):
                    # Extract coordinates from WKT POLYGON((x1 y1, x2 y2, ...))
                    coords_str = wkt_str[wkt_str.find('((')+2:wkt_str.rfind('))')]
                    coords_pairs = coords_str.split(', ')
                    coordinates = []
                    for pair in coords_pairs:
                        lon, lat = pair.split(' ')
                        coordinates.append([float(lon), float(lat)])
                    
                    geometry_geojson = {
                        'type': 'Polygon',
                        'coordinates': [coordinates]
                    }
                else:
                    geometry_geojson = wkt_str
            except Exception as e:
                print(f"Error converting geometry: {e}")
                geometry_geojson = str(airspace.geometry)
        
        return {
            'id': airspace.id,
            'name': airspace.name,
            'type': airspace.airspace_type.value,
            'class': airspace.airspace_class.value,
            'lower_limit': f"{airspace.lower_limit_value} {airspace.lower_limit_reference.value}",
            'upper_limit': f"{airspace.upper_limit_value} {airspace.upper_limit_reference.value}",
            'geometry': geometry_geojson,  # Now in GeoJSON format
            'center': {
                'lat': float(airspace.center_latitude),
                'lon': float(airspace.center_longitude)
            },
            'colors': {
                'border': airspace.border_color,
                'fill': airspace.fill_color,
                'opacity': airspace.opacity
            },
            'priority': airspace.display_priority,
            'frequencies': airspace.frequencies or [],
            'active_times': airspace.active_times or {'schedule': 'H24'},
            'notes': airspace.notes
        }