#!/usr/bin/env python3
"""Create admin user directly"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

# Add parent directory to path
sys.path.append('.')

from app.db.base import AsyncSessionLocal
from app.models import User, UserRole
from app.core.security import get_password_hash


async def create_admin_user():
    """Create admin user"""
    async with AsyncSessionLocal() as session:
        # Check if admin already exists
        result = await session.execute(
            select(User).filter(User.username == "admin")
        )
        existing_user = result.scalars().first()
        
        if existing_user:
            print("Admin user already exists")
            return
        
        # Create admin user
        admin_user = User(
            id=str(uuid.uuid4()),
            email="admin@airport-mgmt.com",
            username="admin",
            first_name="System",
            last_name="Administrator",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True,
            role=UserRole.SUPER_ADMIN,
        )
        
        session.add(admin_user)
        await session.commit()
        
        print("Created admin user:")
        print(f"  Username: admin")
        print(f"  Password: admin123")
        print(f"  Email: admin@airport-mgmt.com")


async def main():
    """Main function"""
    print("Creating admin user...")
    await create_admin_user()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
