#!/usr/bin/env python3
"""Recreate database tables"""

import asyncio
import sys
sys.path.append('.')

from sqlalchemy import text
from app.db.base import engine, Base
from app.models import *  # Import all models

async def recreate_tables():
    """Drop and recreate all database tables"""
    print("🗑️  Dropping all tables...")
    async with engine.begin() as conn:
        # Disable foreign key checks for MySQL
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        print("✅ All tables dropped")
    
    print("🏗️  Creating all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("✅ All tables created")
    
    print("🎉 Database recreation complete!")

if __name__ == "__main__":
    asyncio.run(recreate_tables())