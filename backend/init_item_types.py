#!/usr/bin/env python3
"""
Initialize item types for the airport management system
"""

import asyncio
import sys
import uuid

sys.path.append('.')

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.base import AsyncSessionLocal
from app.models import ItemType


ITEM_TYPES = [
    {
        "name": "PAPI Lights",
        "code": "PAPI_LIGHTS",
        "category": "lighting",
        "icon": "🔴",
        "color": "#FF0000",
        "description": "Precision Approach Path Indicator lights"
    },
    {
        "name": "Runway Edge Lights",
        "code": "RUNWAY_LIGHTS",
        "category": "lighting",
        "icon": "💡",
        "color": "#FFFF00",
        "description": "Runway edge lighting system"
    },
    {
        "name": "Taxiway Lights",
        "code": "TAXIWAY_LIGHTS",
        "category": "lighting",
        "icon": "🟢",
        "color": "#00FF00",
        "description": "Taxiway edge and centerline lights"
    },
    {
        "name": "Runway",
        "code": "RUNWAY",
        "category": "infrastructure",
        "icon": "🛫",
        "color": "#333333",
        "description": "Airport runway surface"
    },
    {
        "name": "Taxiway",
        "code": "TAXIWAY",
        "category": "infrastructure",
        "icon": "🛤️",
        "color": "#666666",
        "description": "Aircraft taxiway"
    },
    {
        "name": "Apron",
        "code": "APRON",
        "category": "infrastructure",
        "icon": "🅿️",
        "color": "#999999",
        "description": "Aircraft parking area"
    },
    {
        "name": "Runway Marking",
        "code": "MARKING",
        "category": "marking",
        "icon": "⬜",
        "color": "#FFFFFF",
        "description": "Runway and taxiway markings"
    },
    {
        "name": "Restricted Area",
        "code": "RESTRICTED_AREA",
        "category": "zone",
        "icon": "⛔",
        "color": "#FF6600",
        "description": "No-fly or restricted access zone"
    },
    {
        "name": "Terminal Building",
        "code": "BUILDING",
        "category": "infrastructure",
        "icon": "🏢",
        "color": "#8B4513",
        "description": "Airport buildings and terminals"
    },
    {
        "name": "Navigation Aid",
        "code": "NAVIGATION_AID",
        "category": "equipment",
        "icon": "📡",
        "color": "#0000FF",
        "description": "ILS, VOR, NDB and other navigation equipment"
    },
    {
        "name": "Wind Sock",
        "code": "WIND_SOCK",
        "category": "equipment",
        "icon": "🎯",
        "color": "#FFA500",
        "description": "Wind direction indicator"
    },
    {
        "name": "Approach Lights",
        "code": "APPROACH_LIGHTS",
        "category": "lighting",
        "icon": "✨",
        "color": "#FFD700",
        "description": "Approach lighting system"
    }
]


async def create_item_types():
    """Create default item types"""
    async with AsyncSessionLocal() as session:
        for item_type_data in ITEM_TYPES:
            # Check if item type exists
            result = await session.execute(
                select(ItemType).filter(ItemType.name == item_type_data["name"])
            )
            existing = result.scalars().first()
            
            if not existing:
                item_type = ItemType(
                    id=str(uuid.uuid4()),
                    name=item_type_data["name"],
                    category=item_type_data["category"],
                    subcategory=item_type_data.get("subcategory"),
                    icao_reference=item_type_data.get("description"),
                    icon=item_type_data.get("icon"),
                    default_color=item_type_data.get("color"),
                    default_properties={"code": item_type_data["code"]}
                )
                session.add(item_type)
                print(f"Created item type: {item_type_data['name']}")
            else:
                print(f"Item type already exists: {item_type_data['name']}")
        
        await session.commit()
        print("\nItem types initialization complete!")


async def main():
    """Main initialization"""
    print("Initializing item types...")
    await create_item_types()


if __name__ == "__main__":
    asyncio.run(main())