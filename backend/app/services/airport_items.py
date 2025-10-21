"""
Service for automatically creating airport items based on imported data
"""

import uuid
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import AirportItem, ItemType, Runway, Airport


class AirportItemsService:
    """Service for managing airport items"""
    
    @staticmethod
    async def create_runway_items(
        db: AsyncSession,
        airport_id: str,
        runway: Runway,
        runway_data: Dict[str, Any]
    ):
        """Create airport items based on runway configuration"""
        
        # Get item types
        item_types = {}
        result = await db.execute(select(ItemType))
        for item_type in result.scalars().all():
            item_types[item_type.name] = item_type.id
        
        items_to_create = []
        
        # Calculate runway endpoints based on heading and length
        # This is simplified - in reality would need proper geodesic calculations
        import math
        
        # Get airport coordinates
        from sqlalchemy import select
        result = await db.execute(
            select(Airport).filter(Airport.id == airport_id)
        )
        airport = result.scalars().first()
        center_lat = airport.latitude if airport else 0
        center_lon = airport.longitude if airport else 0
        
        # Length in meters
        length_m = runway.length * 0.3048  # Convert feet to meters
        
        # Calculate endpoints
        heading_rad = math.radians(runway.heading)
        opposite_heading = (runway.heading + 180) % 360
        opposite_heading_rad = math.radians(opposite_heading)

        # Use stored GPS coordinates if available, otherwise calculate
        if runway.start_lat and runway.start_lon and runway.end_lat and runway.end_lon:
            end1_lat = runway.start_lat
            end1_lon = runway.start_lon
            end2_lat = runway.end_lat
            end2_lon = runway.end_lon
        else:
            # Approximate calculation (works for small distances)
            lat_offset = (length_m / 2) / 111111  # degrees latitude per meter
            lon_offset = (length_m / 2) / (111111 * math.cos(math.radians(center_lat)))

            # Runway end positions
            end1_lat = center_lat + lat_offset * math.cos(heading_rad)
            end1_lon = center_lon + lon_offset * math.sin(heading_rad)
            end2_lat = center_lat - lat_offset * math.cos(heading_rad)
            end2_lon = center_lon - lon_offset * math.sin(heading_rad)
        
        # Create PAPI lights if runway has them
        if 'PAPI' in runway_data.get('lighting', []):
            # PAPI lights are typically 300m from threshold on left side
            for end_num, (end_lat, end_lon, heading) in enumerate([
                (end1_lat, end1_lon, runway.heading),
                (end2_lat, end2_lon, opposite_heading)
            ], 1):
                if item_types.get('PAPI Lights'):
                    papi_item = AirportItem(
                        id=str(uuid.uuid4()),
                        airport_id=airport_id,
                        runway_id=runway.id,
                        item_type_id=item_types['PAPI Lights'],
                        name=f"PAPI RWY {runway.name} End {end_num}",
                        latitude=end_lat,
                        longitude=end_lon,
                        status='operational',
                        properties={
                            'angle': 3.0,  # Standard 3-degree glide path
                            'lights_count': 4,
                            'side': 'left'
                        },
                        is_active=True
                    )
                    items_to_create.append(papi_item)
        
        # Create runway edge lights
        if 'EDGE' in runway_data.get('lighting', []):
            if item_types.get('Runway Edge Lights'):
                # Edge lights every 60m along runway
                spacing_m = 60
                num_lights = int(length_m / spacing_m)
                
                for i in range(num_lights + 1):
                    distance_from_end1 = i * spacing_m
                    fraction = distance_from_end1 / length_m
                    
                    # Left and right edge positions
                    for side in ['left', 'right']:
                        lat = end1_lat + fraction * (end2_lat - end1_lat)
                        lon = end1_lon + fraction * (end2_lon - end1_lon)
                        
                        # Offset perpendicular to runway
                        width_offset = runway.width * 0.3048 / 2  # Half width in meters
                        perpendicular_heading = runway.heading + (90 if side == 'right' else -90)
                        perpendicular_rad = math.radians(perpendicular_heading)
                        
                        lat += (width_offset / 111111) * math.cos(perpendicular_rad)
                        lon += (width_offset / (111111 * math.cos(math.radians(lat)))) * math.sin(perpendicular_rad)
                        
                        edge_light = AirportItem(
                            id=str(uuid.uuid4()),
                            airport_id=airport_id,
                            runway_id=runway.id,
                            item_type_id=item_types['Runway Edge Lights'],
                            name=f"Edge Light RWY {runway.name} {side} #{i+1}",
                            latitude=lat,
                            longitude=lon,
                            status='operational',
                            properties={
                                'color': 'white',
                                'intensity': 'high',
                                'side': side,
                                'position': i
                            },
                            is_active=True
                        )
                        items_to_create.append(edge_light)
        
        # Create approach lights
        if 'ALS' in runway_data.get('lighting', []):
            if item_types.get('Approach Lights'):
                # Approach lights extend 900m from threshold
                approach_distance = 900  # meters
                num_bars = 15  # Number of light bars
                
                for end_num, (end_lat, end_lon, heading) in enumerate([
                    (end1_lat, end1_lon, opposite_heading),  # Approach to end 1
                    (end2_lat, end2_lon, runway.heading)     # Approach to end 2
                ], 1):
                    for i in range(num_bars):
                        distance = (i + 1) * (approach_distance / num_bars)
                        
                        # Calculate position along approach path
                        approach_rad = math.radians(heading)
                        lat = end_lat + (distance / 111111) * math.cos(approach_rad)
                        lon = end_lon + (distance / (111111 * math.cos(math.radians(lat)))) * math.sin(approach_rad)
                        
                        approach_light = AirportItem(
                            id=str(uuid.uuid4()),
                            airport_id=airport_id,
                            runway_id=runway.id,
                            item_type_id=item_types['Approach Lights'],
                            name=f"Approach Light RWY {runway.name} End {end_num} #{i+1}",
                            latitude=lat,
                            longitude=lon,
                            status='operational',
                            properties={
                                'type': 'ALSF-2',  # Approach Lighting System with Sequenced Flashers
                                'bar_number': i + 1
                            },
                            is_active=True
                        )
                        items_to_create.append(approach_light)
        
        # Add all items to database
        for item in items_to_create:
            db.add(item)
        
        await db.commit()
        
        return len(items_to_create)