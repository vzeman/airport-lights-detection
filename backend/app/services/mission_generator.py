"""
Mission Generator Service for automated flight path creation
Includes PAPI measurement patterns based on ICAO standards
"""

import math
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
# from geoalchemy2 import WKTElement  # Commented out for SQLite compatibility

from app.models.maintenance_task import (
    MaintenanceTask, MissionTemplate, FlightPlan, 
    FlightPlanItem, MissionType, TaskType
)
from app.models.airport import AirportItem


@dataclass
class Waypoint:
    """Waypoint in 3D space"""
    lat: float
    lon: float
    alt_m: float
    speed_ms: float = 5.0
    actions: List[Dict[str, Any]] = None
    gimbal_pitch: float = -90
    hover_time_s: float = 0
    

@dataclass
class MissionSegment:
    """Segment of a mission path"""
    item_id: str
    task_id: str
    waypoints: List[Waypoint]
    estimated_duration_s: float
    distance_m: float


class PAPIMeasurementPattern:
    """
    PAPI measurement pattern generator based on UAV measurement methodology
    Reference: UAV_Based-PAPI-Measurement_Post-Processing-Method
    """
    
    # PAPI standard angles (ICAO Annex 14)
    STANDARD_ANGLES = {
        'A': 3.5,  # degrees - 3 white, 1 red
        'B': 3.17, # degrees - 2 white, 2 red  
        'C': 2.83, # degrees - 1 white, 3 red
        'D': 2.5   # degrees - all red
    }
    
    # Measurement parameters
    HORIZONTAL_SPACING_M = 9  # Standard spacing between PAPI units
    MEASUREMENT_DISTANCE_M = 300  # Distance from threshold for measurements
    VERTICAL_SCAN_HEIGHT_M = 50  # Height range to scan
    HORIZONTAL_SCAN_WIDTH_M = 100  # Width to scan across PAPI
    
    @staticmethod
    def generate_papi_waypoints(
        papi_position: Tuple[float, float, float],  # lat, lon, elevation
        runway_heading: float,  # degrees
        papi_side: str = 'left',  # left or right of runway
        measurement_points: int = 5,  # vertical measurement points
    ) -> List[Waypoint]:
        """
        Generate waypoints for PAPI measurement pattern
        
        The pattern includes:
        1. Approach to measurement position
        2. Vertical scan at different heights
        3. Horizontal scan across PAPI lights
        4. Angular verification points
        """
        waypoints = []
        lat, lon, elev = papi_position
        
        # Calculate measurement positions relative to PAPI
        # Perpendicular to runway, at measurement distance
        perpendicular_heading = (runway_heading + 90) % 360 if papi_side == 'left' else (runway_heading - 90) % 360
        
        # Starting position - approach point
        approach_lat, approach_lon = PAPIMeasurementPattern._calculate_position(
            lat, lon, perpendicular_heading, PAPIMeasurementPattern.MEASUREMENT_DISTANCE_M + 50
        )
        waypoints.append(Waypoint(
            lat=approach_lat,
            lon=approach_lon,
            alt_m=elev + 30,
            speed_ms=8.0,
            gimbal_pitch=0
        ))
        
        # Vertical scan pattern - measure at different heights
        for i in range(measurement_points):
            height_offset = (i - measurement_points // 2) * (PAPIMeasurementPattern.VERTICAL_SCAN_HEIGHT_M / measurement_points)
            scan_lat, scan_lon = PAPIMeasurementPattern._calculate_position(
                lat, lon, perpendicular_heading, PAPIMeasurementPattern.MEASUREMENT_DISTANCE_M
            )
            
            # Add hover point for measurement
            waypoints.append(Waypoint(
                lat=scan_lat,
                lon=scan_lon,
                alt_m=elev + 20 + height_offset,
                speed_ms=2.0,
                hover_time_s=5,
                gimbal_pitch=0,
                actions=[
                    {"type": "photo", "count": 3, "interval_s": 1},
                    {"type": "measure_light", "duration_s": 3}
                ]
            ))
        
        # Horizontal scan - across PAPI array
        for offset in [-30, -15, 0, 15, 30]:  # meters from center
            scan_lat, scan_lon = PAPIMeasurementPattern._calculate_position(
                lat, lon, perpendicular_heading, PAPIMeasurementPattern.MEASUREMENT_DISTANCE_M
            )
            # Offset perpendicular to measurement line
            offset_lat, offset_lon = PAPIMeasurementPattern._calculate_position(
                scan_lat, scan_lon, runway_heading, offset
            )
            
            waypoints.append(Waypoint(
                lat=offset_lat,
                lon=offset_lon,
                alt_m=elev + 25,
                speed_ms=3.0,
                hover_time_s=3,
                gimbal_pitch=-15,  # Slight angle toward PAPI
                actions=[
                    {"type": "photo", "count": 2, "interval_s": 1},
                    {"type": "video", "duration_s": 2}
                ]
            ))
        
        # Angular verification - check transition angles
        for angle_name, angle_deg in PAPIMeasurementPattern.STANDARD_ANGLES.items():
            # Calculate position for specific angle
            angle_height = PAPIMeasurementPattern.MEASUREMENT_DISTANCE_M * math.tan(math.radians(angle_deg))
            angle_lat, angle_lon = PAPIMeasurementPattern._calculate_position(
                lat, lon, perpendicular_heading, PAPIMeasurementPattern.MEASUREMENT_DISTANCE_M
            )
            
            waypoints.append(Waypoint(
                lat=angle_lat,
                lon=angle_lon,
                alt_m=elev + angle_height,
                speed_ms=1.0,
                hover_time_s=10,
                gimbal_pitch=0,
                actions=[
                    {"type": "photo", "count": 5, "interval_s": 1},
                    {"type": "measure_light", "duration_s": 5},
                    {"type": "log", "data": f"PAPI_angle_{angle_name}_{angle_deg}deg"}
                ]
            ))
        
        return waypoints
    
    @staticmethod
    def _calculate_position(lat: float, lon: float, heading: float, distance_m: float) -> Tuple[float, float]:
        """Calculate new position given heading and distance"""
        # Earth radius in meters
        R = 6371000
        
        # Convert to radians
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        heading_rad = math.radians(heading)
        
        # Calculate new position
        lat2_rad = math.asin(
            math.sin(lat_rad) * math.cos(distance_m / R) +
            math.cos(lat_rad) * math.sin(distance_m / R) * math.cos(heading_rad)
        )
        
        lon2_rad = lon_rad + math.atan2(
            math.sin(heading_rad) * math.sin(distance_m / R) * math.cos(lat_rad),
            math.cos(distance_m / R) - math.sin(lat_rad) * math.sin(lat2_rad)
        )
        
        return math.degrees(lat2_rad), math.degrees(lon2_rad)


class MissionGenerator:
    """Service for generating and optimizing flight missions"""
    
    @staticmethod
    async def generate_grid_pattern(
        center: Tuple[float, float],
        width_m: float,
        height_m: float,
        spacing_m: float,
        altitude_m: float,
        angle_deg: float = 0,
        overlap_pct: float = 70
    ) -> List[Waypoint]:
        """Generate grid pattern for area coverage"""
        waypoints = []
        lat, lon = center
        
        # Calculate number of lines based on overlap
        effective_spacing = spacing_m * (1 - overlap_pct / 100)
        num_lines = int(width_m / effective_spacing) + 1
        
        # Generate parallel lines
        for i in range(num_lines):
            offset = (i - num_lines // 2) * effective_spacing
            
            # Start and end points of line
            start_lat, start_lon = PAPIMeasurementPattern._calculate_position(
                lat, lon, angle_deg, -height_m / 2
            )
            end_lat, end_lon = PAPIMeasurementPattern._calculate_position(
                lat, lon, angle_deg, height_m / 2
            )
            
            # Offset perpendicular to flight direction
            start_lat, start_lon = PAPIMeasurementPattern._calculate_position(
                start_lat, start_lon, angle_deg + 90, offset
            )
            end_lat, end_lon = PAPIMeasurementPattern._calculate_position(
                end_lat, end_lon, angle_deg + 90, offset
            )
            
            # Alternate direction for efficiency
            if i % 2 == 0:
                waypoints.append(Waypoint(start_lat, start_lon, altitude_m, speed_ms=5.0))
                waypoints.append(Waypoint(end_lat, end_lon, altitude_m, speed_ms=5.0))
            else:
                waypoints.append(Waypoint(end_lat, end_lon, altitude_m, speed_ms=5.0))
                waypoints.append(Waypoint(start_lat, start_lon, altitude_m, speed_ms=5.0))
        
        return waypoints
    
    @staticmethod
    async def generate_orbit_pattern(
        center: Tuple[float, float],
        radius_m: float,
        altitude_m: float,
        points: int = 36,
        clockwise: bool = True
    ) -> List[Waypoint]:
        """Generate circular orbit pattern"""
        waypoints = []
        lat, lon = center
        
        for i in range(points):
            angle = (360 / points) * i
            if not clockwise:
                angle = 360 - angle
            
            wp_lat, wp_lon = PAPIMeasurementPattern._calculate_position(
                lat, lon, angle, radius_m
            )
            waypoints.append(Waypoint(
                wp_lat, wp_lon, altitude_m, 
                speed_ms=3.0,
                gimbal_pitch=-45  # Point toward center
            ))
        
        # Close the orbit
        waypoints.append(waypoints[0])
        
        return waypoints
    
    @staticmethod
    async def optimize_flight_path(
        segments: List[MissionSegment],
        optimization_method: str = 'tsp'
    ) -> List[MissionSegment]:
        """
        Optimize the order of mission segments to minimize travel distance
        Uses Traveling Salesman Problem (TSP) solver
        """
        if len(segments) <= 2:
            return segments
        
        # Build distance matrix
        n = len(segments)
        distances = np.zeros((n, n))
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    # Use last waypoint of segment i and first waypoint of segment j
                    wp1 = segments[i].waypoints[-1] if segments[i].waypoints else None
                    wp2 = segments[j].waypoints[0] if segments[j].waypoints else None
                    
                    if wp1 and wp2:
                        distances[i][j] = MissionGenerator._calculate_distance(
                            (wp1.lat, wp1.lon), (wp2.lat, wp2.lon)
                        )
        
        # Simple nearest neighbor heuristic for TSP
        unvisited = set(range(1, n))  # Start from segment 0
        current = 0
        path = [0]
        
        while unvisited:
            nearest = min(unvisited, key=lambda x: distances[current][x])
            path.append(nearest)
            unvisited.remove(nearest)
            current = nearest
        
        # Reorder segments
        return [segments[i] for i in path]
    
    @staticmethod
    def _calculate_distance(pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate distance between two positions in meters"""
        lat1, lon1 = pos1
        lat2, lon2 = pos2
        
        R = 6371000  # Earth radius in meters
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    @staticmethod
    async def generate_transition_path(
        from_wp: Waypoint,
        to_wp: Waypoint,
        obstacle_avoidance: bool = True,
        max_climb_rate_ms: float = 3.0
    ) -> List[Waypoint]:
        """Generate smooth transition between mission segments"""
        transition = []
        
        # Calculate required altitude change
        alt_change = to_wp.alt_m - from_wp.alt_m
        distance = MissionGenerator._calculate_distance(
            (from_wp.lat, from_wp.lon),
            (to_wp.lat, to_wp.lon)
        )
        
        # Add intermediate waypoint if significant altitude change
        if abs(alt_change) > 20:
            # Climb/descend point
            mid_lat = (from_wp.lat + to_wp.lat) / 2
            mid_lon = (from_wp.lon + to_wp.lon) / 2
            mid_alt = from_wp.alt_m + alt_change / 2
            
            transition.append(Waypoint(
                mid_lat, mid_lon, mid_alt,
                speed_ms=5.0,
                gimbal_pitch=-90
            ))
        
        return transition
    
    @staticmethod
    async def create_flight_plan(
        db: AsyncSession,
        airport_id: str,
        selected_items: List[Dict[str, str]],  # [{"item_id": "...", "task_id": "..."}]
        user_id: str,
        optimization: bool = True
    ) -> FlightPlan:
        """
        Create a complete flight plan from selected items and tasks
        """
        segments = []
        
        # Generate mission segments for each item-task pair
        for selection in selected_items:
            item_id = selection['item_id']
            task_id = selection['task_id']
            
            # Get item details
            item_result = await db.execute(
                select(AirportItem).filter(AirportItem.id == item_id)
            )
            item = item_result.scalars().first()
            
            # Get task and template
            task_result = await db.execute(
                select(MaintenanceTask).filter(MaintenanceTask.id == task_id)
            )
            task = task_result.scalars().first()
            
            template_result = await db.execute(
                select(MissionTemplate).filter(
                    and_(
                        MissionTemplate.task_id == task_id,
                        MissionTemplate.is_default == True
                    )
                )
            )
            template = template_result.scalars().first()
            
            if not item or not task:
                continue
            
            # Generate waypoints based on task type
            waypoints = []
            if task.task_type == TaskType.PAPI_CALIBRATION:
                waypoints = PAPIMeasurementPattern.generate_papi_waypoints(
                    (item.latitude, item.longitude, item.elevation_msl or 0),
                    runway_heading=0,  # TODO: Get from runway data
                    papi_side='left'
                )
            elif template and template.mission_type == MissionType.GRID:
                params = template.pattern_params or {}
                waypoints = await MissionGenerator.generate_grid_pattern(
                    (item.latitude, item.longitude),
                    params.get('width_m', 100),
                    params.get('height_m', 100),
                    params.get('spacing_m', 10),
                    template.altitude_agl_m,
                    params.get('angle_deg', 0),
                    params.get('overlap_pct', 70)
                )
            elif template and template.mission_type == MissionType.ORBIT:
                params = template.pattern_params or {}
                waypoints = await MissionGenerator.generate_orbit_pattern(
                    (item.latitude, item.longitude),
                    params.get('radius_m', 50),
                    template.altitude_agl_m,
                    params.get('points', 36),
                    params.get('clockwise', True)
                )
            
            # Create mission segment
            if waypoints:
                segments.append(MissionSegment(
                    item_id=item_id,
                    task_id=task_id,
                    waypoints=waypoints,
                    estimated_duration_s=len(waypoints) * 10,  # Simple estimate
                    distance_m=sum([
                        MissionGenerator._calculate_distance(
                            (waypoints[i].lat, waypoints[i].lon),
                            (waypoints[i+1].lat, waypoints[i+1].lon)
                        ) for i in range(len(waypoints)-1)
                    ])
                ))
        
        # Optimize path if requested
        if optimization and segments:
            segments = await MissionGenerator.optimize_flight_path(segments)
        
        # Add transitions between segments
        final_waypoints = []
        for i, segment in enumerate(segments):
            final_waypoints.extend(segment.waypoints)
            
            # Add transition to next segment
            if i < len(segments) - 1:
                transition = await MissionGenerator.generate_transition_path(
                    segment.waypoints[-1],
                    segments[i+1].waypoints[0]
                )
                final_waypoints.extend(transition)
        
        # Calculate statistics
        total_distance = sum(s.distance_m for s in segments)
        total_duration = sum(s.estimated_duration_s for s in segments)
        
        # Create flight plan
        flight_plan = FlightPlan(
            airport_id=airport_id,
            name=f"Inspection Plan - {len(segments)} tasks",
            planned_date=datetime.utcnow(),
            planned_by=user_id,
            mission_sequence=[{
                "seq": i,
                "item_id": s.item_id,
                "task_id": s.task_id,
                "waypoints": [
                    {
                        "lat": wp.lat,
                        "lon": wp.lon,
                        "alt_m": wp.alt_m,
                        "speed_ms": wp.speed_ms,
                        "actions": wp.actions
                    } for wp in s.waypoints
                ]
            } for i, s in enumerate(segments)],
            total_distance_m=total_distance,
            total_duration_s=total_duration,
            total_items=len(set(s.item_id for s in segments)),
            total_tasks=len(segments),
            status='draft'
        )
        
        db.add(flight_plan)
        await db.commit()
        await db.refresh(flight_plan)
        
        return flight_plan
    
    @staticmethod
    def export_to_mavlink(flight_plan: FlightPlan) -> str:
        """Export flight plan to MAVLink format for drone autopilot"""
        # MAVLink mission format
        mission_items = []
        seq = 0
        
        for mission in flight_plan.mission_sequence:
            for wp in mission.get('waypoints', []):
                mission_items.append({
                    "seq": seq,
                    "frame": 3,  # MAV_FRAME_GLOBAL_RELATIVE_ALT
                    "command": 16,  # MAV_CMD_NAV_WAYPOINT
                    "current": 1 if seq == 0 else 0,
                    "autocontinue": 1,
                    "param1": wp.get('hover_time_s', 0),
                    "param2": 0,
                    "param3": 0,
                    "param4": 0,
                    "x": wp['lat'],
                    "y": wp['lon'],
                    "z": wp['alt_m']
                })
                seq += 1
        
        return {
            "version": "1.0",
            "items": mission_items
        }
    
    @staticmethod
    def export_to_kml(flight_plan: FlightPlan) -> str:
        """Export flight plan to KML format for visualization"""
        kml_template = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>
    <Style id="flightPath">
      <LineStyle>
        <color>ff00ff00</color>
        <width>2</width>
      </LineStyle>
    </Style>
    <Placemark>
      <name>Flight Path</name>
      <styleUrl>#flightPath</styleUrl>
      <LineString>
        <altitudeMode>relativeToGround</altitudeMode>
        <coordinates>
          {coordinates}
        </coordinates>
      </LineString>
    </Placemark>
    {waypoint_marks}
  </Document>
</kml>"""
        
        coordinates = []
        waypoint_marks = []
        wp_num = 0
        
        for mission in flight_plan.mission_sequence:
            for wp in mission.get('waypoints', []):
                coordinates.append(f"{wp['lon']},{wp['lat']},{wp['alt_m']}")
                
                # Add waypoint marker
                if wp.get('actions'):
                    waypoint_marks.append(f"""
    <Placemark>
      <name>WP{wp_num}</name>
      <Point>
        <coordinates>{wp['lon']},{wp['lat']},{wp['alt_m']}</coordinates>
      </Point>
    </Placemark>""")
                wp_num += 1
        
        return kml_template.format(
            name=flight_plan.name,
            coordinates="\n          ".join(coordinates),
            waypoint_marks="".join(waypoint_marks)
        )