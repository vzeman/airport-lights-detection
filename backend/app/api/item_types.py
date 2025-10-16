"""
Item Types API endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from app.db.base import get_db
from app.models import User
from app.models.airport import ItemType
from app.core.deps import get_current_user

router = APIRouter(prefix="/item-types", tags=["Item Types"])


@router.get("/")
async def get_item_types(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name and ICAO reference"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get list of item types"""
    query = select(ItemType)
    
    if category:
        query = query.filter(ItemType.category == category)
    
    if search:
        query = query.filter(
            ItemType.name.contains(search) | 
            ItemType.icao_reference.contains(search)
        )
    
    result = await db.execute(query)
    item_types = result.scalars().all()
    
    return {
        "item_types": [{
            "id": item_type.id,
            "name": item_type.name,
            "category": item_type.category,
            "subcategory": item_type.subcategory,
            "icao_reference": item_type.icao_reference,
            "requirements": item_type.requirements,
            "default_properties": item_type.default_properties,
            "inspection_frequency_days": item_type.inspection_frequency_days,
            "inspection_procedures": item_type.inspection_procedures,
            "icon": item_type.icon,
            "default_color": item_type.default_color,
            "flight_template": item_type.flight_template,
        } for item_type in item_types],
        "total": len(item_types)
    }


@router.get("/{item_type_id}")
async def get_item_type(
    item_type_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get item type details"""
    result = await db.execute(
        select(ItemType).filter(ItemType.id == item_type_id)
    )
    item_type = result.scalars().first()
    
    if not item_type:
        raise HTTPException(status_code=404, detail="Item type not found")
    
    return {
        "id": item_type.id,
        "name": item_type.name,
        "category": item_type.category,
        "subcategory": item_type.subcategory,
        "icao_reference": item_type.icao_reference,
        "requirements": item_type.requirements,
        "default_properties": item_type.default_properties,
        "inspection_frequency_days": item_type.inspection_frequency_days,
        "inspection_procedures": item_type.inspection_procedures,
        "icon": item_type.icon,
        "default_color": item_type.default_color,
        "flight_template": item_type.flight_template,
        "created_at": item_type.created_at.isoformat() if item_type.created_at else None,
        "updated_at": item_type.updated_at.isoformat() if item_type.updated_at else None,
    }


@router.post("/")
async def create_item_type(
    item_type_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new item type"""
    
    # Check if user has permission (admin only)
    if not current_user.is_superuser and current_user.role not in ['super_admin', 'airport_admin']:
        raise HTTPException(status_code=403, detail="Not authorized to create item types")
    
    item_type = ItemType(
        id=str(uuid.uuid4()),
        name=item_type_data["name"],
        category=item_type_data["category"],
        subcategory=item_type_data.get("subcategory"),
        icao_reference=item_type_data.get("icao_reference"),
        requirements=item_type_data.get("requirements", {}),
        default_properties=item_type_data.get("default_properties", {}),
        inspection_frequency_days=item_type_data.get("inspection_frequency_days", 30),
        inspection_procedures=item_type_data.get("inspection_procedures", {}),
        icon=item_type_data.get("icon"),
        default_color=item_type_data.get("default_color", "#FFFFFF"),
        flight_template=item_type_data.get("flight_template"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(item_type)
    await db.commit()
    await db.refresh(item_type)
    
    return {
        "message": "Item type created successfully",
        "item_type_id": item_type.id
    }


@router.put("/{item_type_id}")
async def update_item_type(
    item_type_id: str,
    item_type_data: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an item type"""
    
    # Check if user has permission
    if not current_user.is_superuser and current_user.role not in ['super_admin', 'airport_admin']:
        raise HTTPException(status_code=403, detail="Not authorized to update item types")
    
    result = await db.execute(
        select(ItemType).filter(ItemType.id == item_type_id)
    )
    item_type = result.scalars().first()
    
    if not item_type:
        raise HTTPException(status_code=404, detail="Item type not found")
    
    # Update fields
    for field, value in item_type_data.items():
        if hasattr(item_type, field):
            setattr(item_type, field, value)
    
    item_type.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(item_type)
    
    return {
        "message": "Item type updated successfully",
        "item_type_id": item_type.id
    }


@router.delete("/{item_type_id}")
async def delete_item_type(
    item_type_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an item type"""
    
    # Check if user has permission
    if not current_user.is_superuser and current_user.role not in ['super_admin', 'airport_admin']:
        raise HTTPException(status_code=403, detail="Not authorized to delete item types")
    
    result = await db.execute(
        select(ItemType).filter(ItemType.id == item_type_id)
    )
    item_type = result.scalars().first()
    
    if not item_type:
        raise HTTPException(status_code=404, detail="Item type not found")
    
    # Check if any items are using this type
    # This would require checking AirportItem references
    # For now, we'll allow deletion
    
    await db.delete(item_type)
    await db.commit()
    
    return {"message": "Item type deleted successfully"}


@router.get("/categories/list")
async def get_categories(
    current_user: User = Depends(get_current_user)
):
    """Get list of available categories and subcategories"""
    
    categories = {
        "lighting": {
            "name": "Lighting Systems",
            "subcategories": ["approach", "runway", "taxiway", "apron", "obstruction"],
            "icon": "💡"
        },
        "marking": {
            "name": "Markings",
            "subcategories": ["runway", "taxiway", "apron", "holding_position", "guidance"],
            "icon": "🎨"
        },
        "navigation": {
            "name": "Navigation Aids",
            "subcategories": ["radio", "visual", "satellite", "ground"],
            "icon": "📡"
        },
        "infrastructure": {
            "name": "Infrastructure",
            "subcategories": ["signs", "fencing", "buildings", "roads"],
            "icon": "🏗️"
        },
        "obstruction": {
            "name": "Obstructions",
            "subcategories": ["permanent", "temporary", "natural"],
            "icon": "⚠️"
        },
        "surface": {
            "name": "Surface",
            "subcategories": ["runway", "taxiway", "apron", "shoulder"],
            "icon": "🛤️"
        }
    }
    
    return categories


@router.post("/import/batch")
async def import_item_types_batch(
    item_types_data: List[Dict[str, Any]] = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Import multiple item types at once"""
    
    # Check if user has permission
    if not current_user.is_superuser and current_user.role not in ['super_admin', 'airport_admin']:
        raise HTTPException(status_code=403, detail="Not authorized to import item types")
    
    created_count = 0
    skipped_count = 0
    errors = []
    
    for item_data in item_types_data:
        try:
            # Check if already exists
            result = await db.execute(
                select(ItemType).filter(
                    ItemType.name == item_data["name"]
                )
            )
            existing = result.scalars().first()
            
            if existing:
                skipped_count += 1
                continue
            
            item_type = ItemType(
                id=str(uuid.uuid4()),
                name=item_data["name"],
                category=item_data["category"],
                subcategory=item_data.get("subcategory"),
                icao_reference=item_data.get("icao_reference"),
                requirements=item_data.get("requirements", {}),
                default_properties=item_data.get("default_properties", {}),
                inspection_frequency_days=item_data.get("inspection_frequency_days", 30),
                inspection_procedures=item_data.get("inspection_procedures", {}),
                icon=item_data.get("icon"),
                default_color=item_data.get("default_color", "#FFFFFF"),
                flight_template=item_data.get("flight_template"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(item_type)
            created_count += 1
            
        except Exception as e:
            errors.append({
                "item": item_data.get("name", "Unknown"),
                "error": str(e)
            })
    
    await db.commit()
    
    return {
        "message": f"Import completed. Created: {created_count}, Skipped: {skipped_count}",
        "created": created_count,
        "skipped": skipped_count,
        "errors": errors
    }