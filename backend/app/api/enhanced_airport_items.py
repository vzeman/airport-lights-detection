"""
Enhanced Airport Items API with comprehensive search and management
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from typing import List, Optional, Dict, Any
import json
from decimal import Decimal

from app.db.base import get_db
from app.models import User
from app.models.enhanced_airport_item import (
    EnhancedAirportItem, 
    EnhancedItemType, 
    ItemSearchIndex,
    PrecisionLevel,
    ItemStatus,
    CoordinateAccuracy
)
from app.core.deps import get_current_user
from app.schemas.enhanced_airport_item import (
    EnhancedAirportItemCreate,
    EnhancedAirportItemUpdate,
    EnhancedAirportItemResponse,
    ItemSearchRequest,
    ItemSearchResponse,
    BulkImportRequest
)

router = APIRouter(prefix="/enhanced-airport-items", tags=["Enhanced Airport Items"])


@router.get("/search")
async def search_airport_items(
    airport_id: str = Query(..., description="Airport ID"),
    q: Optional[str] = Query(None, description="Search query"),
    category: Optional[str] = Query(None, description="Item category"),
    subcategory: Optional[str] = Query(None, description="Item subcategory"),
    status: Optional[ItemStatus] = Query(None, description="Item status"),
    precision: Optional[PrecisionLevel] = Query(None, description="Precision level"),
    bbox: Optional[str] = Query(None, description="Bounding box: lat1,lon1,lat2,lon2"),
    near_point: Optional[str] = Query(None, description="Search near point: lat,lon,radius_m"),
    runway_id: Optional[str] = Query(None, description="Filter by runway"),
    is_critical: Optional[bool] = Query(None, description="Critical items only"),
    maintenance_due: Optional[bool] = Query(None, description="Items with maintenance due"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    installed_after: Optional[str] = Query(None, description="Installed after date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Comprehensive search for airport items with multiple filters and spatial queries
    """
    
    # Build base query
    query = select(EnhancedAirportItem).filter(
        EnhancedAirportItem.airport_id == airport_id
    )
    
    # Text search
    if q:
        # Join with search index for full-text search
        search_query = select(ItemSearchIndex.item_id).filter(
            and_(
                ItemSearchIndex.airport_id == airport_id,
                or_(
                    ItemSearchIndex.search_text.contains(q),
                    func.json_contains(ItemSearchIndex.keywords, f'"{q}"'),
                    func.json_contains(ItemSearchIndex.tags, f'"{q}"')
                )
            )
        )
        search_item_ids = await db.execute(search_query)
        item_ids = [row[0] for row in search_item_ids]
        
        if item_ids:
            query = query.filter(EnhancedAirportItem.id.in_(item_ids))
        else:
            # No results found
            return {"items": [], "total": 0, "page": page, "limit": limit}
    
    # Category filters
    if category or subcategory:
        query = query.join(EnhancedItemType)
        if category:
            query = query.filter(EnhancedItemType.category == category)
        if subcategory:
            query = query.filter(EnhancedItemType.subcategory == subcategory)
    
    # Status and flags
    if status:
        query = query.filter(EnhancedAirportItem.status == status)
    if precision:
        query = query.filter(EnhancedAirportItem.precision_level == precision)
    if runway_id:
        query = query.filter(EnhancedAirportItem.runway_id == runway_id)
    if is_critical is not None:
        query = query.filter(EnhancedAirportItem.is_critical == is_critical)
    
    # Spatial filters
    if bbox:
        try:
            lat1, lon1, lat2, lon2 = map(float, bbox.split(','))
            query = query.filter(
                and_(
                    EnhancedAirportItem.latitude.between(min(lat1, lat2), max(lat1, lat2)),
                    EnhancedAirportItem.longitude.between(min(lon1, lon2), max(lon1, lon2))
                )
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid bbox format")
    
    if near_point:
        try:
            lat, lon, radius_m = map(float, near_point.split(','))
            # Use Haversine formula for distance calculation
            distance_query = func.ST_Distance_Sphere(
                func.Point(EnhancedAirportItem.longitude, EnhancedAirportItem.latitude),
                func.Point(lon, lat)
            )
            query = query.filter(distance_query <= radius_m)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid near_point format")
    
    # Maintenance filter
    if maintenance_due:
        from datetime import datetime
        today = datetime.utcnow().date()
        query = query.filter(
            or_(
                EnhancedAirportItem.next_maintenance_date <= today,
                EnhancedAirportItem.next_inspection_date <= today
            )
        )
    
    # Date filters
    if installed_after:
        try:
            from datetime import datetime
            date_filter = datetime.strptime(installed_after, "%Y-%m-%d")
            query = query.filter(EnhancedAirportItem.installation_date >= date_filter)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Count total results
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply sorting
    if hasattr(EnhancedAirportItem, sort_by):
        sort_column = getattr(EnhancedAirportItem, sort_by)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    
    # Apply pagination
    query = query.offset((page - 1) * limit).limit(limit)
    
    # Execute query
    result = await db.execute(query)
    items = result.scalars().all()
    
    return {
        "items": [format_item_response(item) for item in items],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.post("/bulk-import")
async def bulk_import_items(
    airport_id: str,
    import_data: BulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bulk import airport items from various sources
    """
    created_items = []
    errors = []
    
    for item_data in import_data.items:
        try:
            # Validate coordinates precision
            if item_data.coordinate_accuracy == CoordinateAccuracy.SURVEY_GPS:
                if not item_data.latitude or not item_data.longitude:
                    raise ValueError("Survey-grade items require precise coordinates")
            
            # Create item
            new_item = EnhancedAirportItem(
                airport_id=airport_id,
                **item_data.dict(exclude_unset=True),
                created_by=current_user.id
            )
            
            db.add(new_item)
            await db.flush()  # Get ID without committing
            
            # Create search index entry
            search_text = f"{new_item.name} {new_item.code or ''} {new_item.serial_number or ''}"
            search_index = ItemSearchIndex(
                item_id=new_item.id,
                airport_id=airport_id,
                search_text=search_text,
                keywords=item_data.keywords or [],
                tags=item_data.tags or []
            )
            db.add(search_index)
            
            created_items.append(new_item.id)
            
        except Exception as e:
            errors.append(f"Item {item_data.name}: {str(e)}")
    
    if not errors:
        await db.commit()
        return {
            "message": f"Successfully imported {len(created_items)} items",
            "created_items": created_items,
            "errors": []
        }
    else:
        await db.rollback()
        return {
            "message": f"Import failed with {len(errors)} errors",
            "created_items": [],
            "errors": errors
        }


@router.post("/upload-survey")
async def upload_survey_data(
    airport_id: str,
    survey_file: UploadFile = File(...),
    file_format: str = Query("csv", regex="^(csv|dxf|dwg|json)$"),
    coordinate_system: str = Query("WGS84", description="Source coordinate system"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload and process survey data files
    """
    try:
        content = await survey_file.read()
        
        if file_format == "csv":
            # Process CSV survey data
            import csv
            import io
            
            csv_data = io.StringIO(content.decode('utf-8'))
            reader = csv.DictReader(csv_data)
            
            processed_items = []
            for row in reader:
                # Map CSV columns to item fields
                item_data = {
                    "name": row.get("name"),
                    "latitude": Decimal(row.get("latitude", 0)),
                    "longitude": Decimal(row.get("longitude", 0)),
                    "elevation_msl": Decimal(row.get("elevation", 0)),
                    "coordinate_accuracy": CoordinateAccuracy.SURVEY_GPS,
                    "precision_level": PrecisionLevel.SURVEY_GRADE
                }
                processed_items.append(item_data)
            
            return {
                "message": f"Processed {len(processed_items)} items from survey file",
                "preview": processed_items[:5],  # Show first 5 items
                "total_items": len(processed_items)
            }
        
        elif file_format == "json":
            # Process JSON format
            import json
            data = json.loads(content.decode('utf-8'))
            
            return {
                "message": f"Processed JSON file with {len(data.get('items', []))} items",
                "preview": data.get('items', [])[:5]
            }
        
        else:
            return {
                "message": f"File format {file_format} processing not yet implemented",
                "supported_formats": ["csv", "json"]
            }
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


@router.get("/precision-analysis/{airport_id}")
async def analyze_coordinate_precision(
    airport_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyze coordinate precision and accuracy across all airport items
    """
    
    # Get precision statistics
    precision_query = select(
        EnhancedAirportItem.precision_level,
        EnhancedAirportItem.coordinate_accuracy,
        func.count().label('count')
    ).filter(
        EnhancedAirportItem.airport_id == airport_id
    ).group_by(
        EnhancedAirportItem.precision_level,
        EnhancedAirportItem.coordinate_accuracy
    )
    
    precision_result = await db.execute(precision_query)
    precision_stats = precision_result.all()
    
    # Get items needing survey
    survey_needed_query = select(EnhancedAirportItem).filter(
        and_(
            EnhancedAirportItem.airport_id == airport_id,
            EnhancedAirportItem.coordinate_accuracy.in_([
                CoordinateAccuracy.ESTIMATED,
                CoordinateAccuracy.MANUAL_ENTRY
            ]),
            EnhancedAirportItem.precision_level.in_([
                PrecisionLevel.SURVEY_GRADE,
                PrecisionLevel.HIGH
            ])
        )
    )
    
    survey_needed_result = await db.execute(survey_needed_query)
    survey_needed = survey_needed_result.scalars().all()
    
    return {
        "precision_statistics": [
            {
                "precision_level": stat.precision_level,
                "coordinate_accuracy": stat.coordinate_accuracy,
                "count": stat.count
            }
            for stat in precision_stats
        ],
        "survey_needed": [
            {
                "id": item.id,
                "name": item.name,
                "precision_level": item.precision_level,
                "coordinate_accuracy": item.coordinate_accuracy
            }
            for item in survey_needed
        ],
        "summary": {
            "total_items": sum(stat.count for stat in precision_stats),
            "survey_grade_count": sum(stat.count for stat in precision_stats 
                                    if stat.precision_level == PrecisionLevel.SURVEY_GRADE),
            "items_needing_survey": len(survey_needed)
        }
    }


def format_item_response(item: EnhancedAirportItem) -> Dict[str, Any]:
    """Format enhanced airport item for API response"""
    return {
        "id": item.id,
        "name": item.name,
        "code": item.code,
        "type": item.item_type.name if item.item_type else None,
        "category": item.item_type.category if item.item_type else None,
        "subcategory": item.item_type.subcategory if item.item_type else None,
        "coordinates": {
            "latitude": float(item.latitude) if item.latitude else None,
            "longitude": float(item.longitude) if item.longitude else None,
            "elevation_msl": float(item.elevation_msl) if item.elevation_msl else None,
            "height_agl": float(item.height_agl) if item.height_agl else None,
            "orientation": float(item.orientation) if item.orientation else None,
        },
        "precision": {
            "level": item.precision_level,
            "accuracy": item.coordinate_accuracy,
            "survey_date": item.survey_date.isoformat() if item.survey_date else None
        },
        "status": item.status,
        "is_critical": item.is_critical,
        "is_monitored": item.is_monitored,
        "properties": item.properties,
        "last_maintenance": item.last_maintenance_date.isoformat() if item.last_maintenance_date else None,
        "next_maintenance": item.next_maintenance_date.isoformat() if item.next_maintenance_date else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat()
    }