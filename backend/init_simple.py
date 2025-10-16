#!/usr/bin/env python3
"""
Simple database initialization script
"""

import asyncio
import sys
import uuid
import bcrypt

sys.path.append('.')

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.base import AsyncSessionLocal, engine, Base
from app.models import User, UserRole


def hash_password_simple(password: str) -> str:
    """Simple password hashing using bcrypt directly"""
    password_bytes = password.encode('utf-8')
    # Truncate to 72 bytes if necessary (bcrypt limitation)
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


async def create_admin_user():
    """Create default super admin user"""
    async with AsyncSessionLocal() as session:
        # Check if admin exists
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
            hashed_password=hash_password_simple("admin123"),
            is_active=True,
            is_superuser=True,
            role=UserRole.SUPER_ADMIN,
        )
        
        session.add(admin_user)
        await session.commit()
        
        print("Created admin user:")
        print("  Username: admin")
        print("  Password: admin123")
        print("  Email: admin@airport-mgmt.com")
        print("\n⚠️  IMPORTANT: Change the default password after first login!")


async def main():
    """Main initialization"""
    print("Initializing database...")
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create admin user
    await create_admin_user()
    
    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())