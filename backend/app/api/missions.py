"""
Mission Planning and Flight Plan API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import io

from app.db.base import get_db
from app.models import User
from app.models.maintenance_task import (
    MaintenanceTask, MissionTemplate, FlightPlan, 
    FlightPlanItem, TaskType, TaskPriority, MissionType
)
from app.models.airport import AirportItem, ItemType
from app.services.mission_generator import MissionGenerator, PAPIMeasurementPattern
from app.core.deps import get_current_user

router = APIRouter(prefix="/missions", tags=["Mission Planning"])


# --- Maintenance Tasks ---

@router.get("/tasks")
async def get_maintenance_tasks(
    item_type_id: Optional[str] = Query(None, description="Filter by item type"),
    task_type: Optional[TaskType] = Query(None, description="Filter by task type"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of maintenance tasks"""
    query = select(MaintenanceTask).filter(MaintenanceTask.is_active == True)
    
    if item_type_id:
        query = query.filter(MaintenanceTask.item_type_id == item_type_id)
    if task_type:
        query = query.filter(MaintenanceTask.task_type == task_type)
    if priority:
        query = query.filter(MaintenanceTask.priority == priority)
    
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return {
        "tasks": [{
            "id": task.id,
            "item_type_id": task.item_type_id,
            "name": task.name,
            "code": task.code,
            "task_type": task.task_type.value,
            "priority": task.priority.value,
            "description": task.description,
            "frequency_days": task.frequency_days,
            "duration_minutes": task.duration_minutes,
            "required_sensors": task.required_sensors,
            "measurement_specs": task.measurement_specs
        } for task in tasks],
        "total": len(tasks)
    }


@router.post("/tasks")
async def create_maintenance_task(
    task_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new maintenance task"""
    task = MaintenanceTask(
        item_type_id=task_data["item_type_id"],
        name=task_data["name"],
        code=task_data["code"],
        task_type=TaskType(task_data["task_type"]),
        priority=TaskPriority(task_data.get("priority", "medium")),
        description=task_data.get("description"),
        frequency_days=task_data["frequency_days"],
        duration_minutes=task_data.get("duration_minutes", 30),
        weather_constraints=task_data.get("weather_constraints"),
        time_constraints=task_data.get("time_constraints"),
        required_sensors=task_data.get("required_sensors"),
        required_accuracy_m=task_data.get("required_accuracy_m", 0.1),
        measurement_specs=task_data.get("measurement_specs"),
        acceptance_criteria=task_data.get("acceptance_criteria"),
        compliance_standard=task_data.get("compliance_standard"),
        documentation_required=task_data.get("documentation_required", True)
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    return {
        "message": "Maintenance task created successfully",
        "task_id": task.id
    }


# --- Mission Templates ---

@router.get("/templates")
async def get_mission_templates(
    task_id: Optional[str] = Query(None, description="Filter by task"),
    mission_type: Optional[MissionType] = Query(None, description="Filter by mission type"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get mission templates"""
    query = select(MissionTemplate)
    
    if task_id:
        query = query.filter(MissionTemplate.task_id == task_id)
    if mission_type:
        query = query.filter(MissionTemplate.mission_type == mission_type)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return {
        "templates": [{
            "id": template.id,
            "task_id": template.task_id,
            "name": template.name,
            "version": template.version,
            "mission_type": template.mission_type.value,
            "is_default": template.is_default,
            "altitude_agl_m": float(template.altitude_agl_m),
            "speed_ms": float(template.speed_ms),
            "pattern_params": template.pattern_params,
            "waypoints": template.waypoints,
            "total_distance_m": float(template.total_distance_m) if template.total_distance_m else None,
            "estimated_duration_s": template.estimated_duration_s
        } for template in templates],
        "total": len(templates)
    }


@router.post("/templates")
async def create_mission_template(
    template_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a mission template"""
    template = MissionTemplate(
        task_id=template_data["task_id"],
        name=template_data["name"],
        version=template_data.get("version", 1),
        mission_type=MissionType(template_data["mission_type"]),
        is_default=template_data.get("is_default", False),
        altitude_agl_m=template_data["altitude_agl_m"],
        speed_ms=template_data.get("speed_ms", 5.0),
        heading_mode=template_data.get("heading_mode", "auto"),
        gimbal_pitch=template_data.get("gimbal_pitch", -90),
        pattern_params=template_data.get("pattern_params"),
        waypoints=template_data.get("waypoints"),
        obstacle_avoidance=template_data.get("obstacle_avoidance", True),
        min_altitude_m=template_data.get("min_altitude_m", 10),
        max_altitude_m=template_data.get("max_altitude_m", 120),
        return_to_home_altitude_m=template_data.get("return_to_home_altitude_m", 50),
        sensor_configs=template_data.get("sensor_configs")
    )
    
    # Calculate statistics
    if template.waypoints:
        total_distance = 0
        for i in range(len(template.waypoints) - 1):
            wp1 = template.waypoints[i]
            wp2 = template.waypoints[i + 1]
            distance = MissionGenerator._calculate_distance(
                (wp1['lat'], wp1['lon']),
                (wp2['lat'], wp2['lon'])
            )
            total_distance += distance
        template.total_distance_m = total_distance
        template.estimated_duration_s = int(total_distance / (template.speed_ms or 5))
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    return {
        "message": "Mission template created successfully",
        "template_id": template.id
    }


# --- Mission Generation ---

@router.post("/generate/papi")
async def generate_papi_mission(
    item_id: str = Body(..., embed=True),
    measurement_points: int = Body(5, embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate PAPI measurement mission for a specific PAPI light"""
    
    # Get PAPI item
    result = await db.execute(
        select(AirportItem).filter(AirportItem.id == item_id)
    )
    item = result.scalars().first()
    
    if not item:
        raise HTTPException(status_code=404, detail="PAPI item not found")
    
    # Generate waypoints
    waypoints = PAPIMeasurementPattern.generate_papi_waypoints(
        papi_position=(float(item.latitude), float(item.longitude), float(item.elevation_msl or 0)),
        runway_heading=item.properties.get("runway_heading", 0) if item.properties else 0,
        papi_side=item.properties.get("papi_side", "left") if item.properties else "left",
        measurement_points=measurement_points
    )
    
    # Convert waypoints to dict format
    waypoint_dicts = [{
        "lat": wp.lat,
        "lon": wp.lon,
        "alt_m": wp.alt_m,
        "speed_ms": wp.speed_ms,
        "gimbal_pitch": wp.gimbal_pitch,
        "hover_time_s": wp.hover_time_s,
        "actions": wp.actions
    } for wp in waypoints]
    
    return {
        "item_id": item_id,
        "item_name": item.name,
        "mission_type": "PAPI_CALIBRATION",
        "waypoints": waypoint_dicts,
        "estimated_duration_s": len(waypoints) * 10,
        "total_waypoints": len(waypoints)
    }


@router.post("/generate/grid")
async def generate_grid_mission(
    center_lat: float = Body(...),
    center_lon: float = Body(...),
    width_m: float = Body(...),
    height_m: float = Body(...),
    altitude_m: float = Body(...),
    spacing_m: float = Body(10),
    angle_deg: float = Body(0),
    overlap_pct: float = Body(70),
    current_user: User = Depends(get_current_user)
):
    """Generate grid pattern mission for area coverage"""
    
    waypoints = await MissionGenerator.generate_grid_pattern(
        center=(center_lat, center_lon),
        width_m=width_m,
        height_m=height_m,
        spacing_m=spacing_m,
        altitude_m=altitude_m,
        angle_deg=angle_deg,
        overlap_pct=overlap_pct
    )
    
    waypoint_dicts = [{
        "lat": wp.lat,
        "lon": wp.lon,
        "alt_m": wp.alt_m,
        "speed_ms": wp.speed_ms
    } for wp in waypoints]
    
    return {
        "mission_type": "GRID",
        "waypoints": waypoint_dicts,
        "coverage_area_sqm": width_m * height_m,
        "total_waypoints": len(waypoints),
        "parameters": {
            "width_m": width_m,
            "height_m": height_m,
            "spacing_m": spacing_m,
            "overlap_pct": overlap_pct,
            "angle_deg": angle_deg
        }
    }


# --- Flight Plans ---

@router.get("/flight-plans")
async def get_flight_plans(
    airport_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get flight plans"""
    query = select(FlightPlan)
    
    if airport_id:
        query = query.filter(FlightPlan.airport_id == airport_id)
    if status:
        query = query.filter(FlightPlan.status == status)
    if start_date:
        query = query.filter(FlightPlan.planned_date >= start_date)
    if end_date:
        query = query.filter(FlightPlan.planned_date <= end_date)
    
    # Filter by user role
    if not current_user.is_superuser:
        query = query.filter(
            or_(
                FlightPlan.planned_by == current_user.id,
                FlightPlan.operator_id == current_user.id
            )
        )
    
    result = await db.execute(query.order_by(FlightPlan.created_at.desc()))
    plans = result.scalars().all()
    
    return {
        "flight_plans": [{
            "id": plan.id,
            "airport_id": plan.airport_id,
            "name": plan.name,
            "description": plan.description,
            "planned_date": plan.planned_date.isoformat(),
            "status": plan.status,
            "total_distance_m": float(plan.total_distance_m) if plan.total_distance_m else None,
            "total_duration_s": plan.total_duration_s,
            "total_items": plan.total_items,
            "total_tasks": plan.total_tasks,
            "created_at": plan.created_at.isoformat()
        } for plan in plans],
        "total": len(plans)
    }


@router.post("/flight-plans/create")
async def create_flight_plan(
    plan_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new flight plan from selected items and tasks"""
    
    selected_items = plan_data["selected_items"]  # [{"item_id": "...", "task_id": "..."}]
    airport_id = plan_data["airport_id"]
    optimization = plan_data.get("optimization", True)
    
    # Generate flight plan
    flight_plan = await MissionGenerator.create_flight_plan(
        db=db,
        airport_id=airport_id,
        selected_items=selected_items,
        user_id=current_user.id,
        optimization=optimization
    )
    
    return {
        "message": "Flight plan created successfully",
        "flight_plan_id": flight_plan.id,
        "total_distance_m": float(flight_plan.total_distance_m) if flight_plan.total_distance_m else None,
        "total_duration_s": flight_plan.total_duration_s,
        "total_items": flight_plan.total_items,
        "total_tasks": flight_plan.total_tasks
    }


@router.get("/flight-plans/{plan_id}")
async def get_flight_plan_detail(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get detailed flight plan with all missions"""
    
    result = await db.execute(
        select(FlightPlan).filter(FlightPlan.id == plan_id)
    )
    plan = result.scalars().first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found")
    
    # Check permissions
    if not current_user.is_superuser and plan.planned_by != current_user.id and plan.operator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "id": plan.id,
        "airport_id": plan.airport_id,
        "name": plan.name,
        "description": plan.description,
        "planned_date": plan.planned_date.isoformat(),
        "status": plan.status,
        "mission_sequence": plan.mission_sequence,
        "total_distance_m": float(plan.total_distance_m) if plan.total_distance_m else None,
        "total_duration_s": plan.total_duration_s,
        "total_items": plan.total_items,
        "total_tasks": plan.total_tasks,
        "battery_changes": plan.battery_changes,
        "estimated_batteries": plan.estimated_batteries,
        "weather_constraints": plan.weather_constraints,
        "created_at": plan.created_at.isoformat(),
        "planner": {
            "id": plan.planned_by,
            "name": plan.planner.first_name + " " + plan.planner.last_name if plan.planner else None
        } if plan.planner else None,
        "operator": {
            "id": plan.operator_id,
            "name": plan.operator.first_name + " " + plan.operator.last_name if plan.operator else None
        } if plan.operator else None
    }


@router.post("/flight-plans/{plan_id}/approve")
async def approve_flight_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve a flight plan for execution"""
    
    result = await db.execute(
        select(FlightPlan).filter(FlightPlan.id == plan_id)
    )
    plan = result.scalars().first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found")
    
    if plan.status != 'draft':
        raise HTTPException(status_code=400, detail="Only draft plans can be approved")
    
    plan.status = 'approved'
    plan.approved_by = current_user.id
    plan.approved_at = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Flight plan approved successfully"}


@router.post("/flight-plans/{plan_id}/execute")
async def start_flight_execution(
    plan_id: str,
    operator_id: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start execution of a flight plan"""
    
    result = await db.execute(
        select(FlightPlan).filter(FlightPlan.id == plan_id)
    )
    plan = result.scalars().first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found")
    
    if plan.status != 'approved':
        raise HTTPException(status_code=400, detail="Only approved plans can be executed")
    
    plan.status = 'executing'
    plan.operator_id = operator_id or current_user.id
    plan.actual_start = datetime.utcnow()
    
    await db.commit()
    
    return {"message": "Flight execution started"}


# --- Export Functions ---

@router.get("/flight-plans/{plan_id}/export/mavlink")
async def export_flight_plan_mavlink(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export flight plan to MAVLink format"""
    
    result = await db.execute(
        select(FlightPlan).filter(FlightPlan.id == plan_id)
    )
    plan = result.scalars().first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found")
    
    mavlink_data = MissionGenerator.export_to_mavlink(plan)
    
    return StreamingResponse(
        io.BytesIO(json.dumps(mavlink_data).encode()),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=flight_plan_{plan_id}.waypoints"
        }
    )


@router.get("/flight-plans/{plan_id}/export/kml")
async def export_flight_plan_kml(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export flight plan to KML format for Google Earth"""
    
    result = await db.execute(
        select(FlightPlan).filter(FlightPlan.id == plan_id)
    )
    plan = result.scalars().first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Flight plan not found")
    
    kml_data = MissionGenerator.export_to_kml(plan)
    
    return StreamingResponse(
        io.BytesIO(kml_data.encode()),
        media_type="application/vnd.google-earth.kml+xml",
        headers={
            "Content-Disposition": f"attachment; filename=flight_plan_{plan_id}.kml"
        }
    )