#!/usr/bin/env python
"""
Script to create a default admin user
"""
import asyncio
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import AsyncSessionLocal
from app.models.user import User
from app.core.security import get_password_hash
import uuid

async def create_admin_user():
    async with AsyncSessionLocal() as session:
        try:
            # Check if admin already exists
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print("Admin user already exists")
                return
            
            # Create admin user
            admin_user = User(
                id=str(uuid.uuid4()),
                username="admin",
                email="admin@example.com",
                first_name="Admin",
                last_name="User",
                hashed_password=get_password_hash("admin123"),
                is_active=True,
                is_superuser=True,
                role="admin"
            )
            
            session.add(admin_user)
            await session.commit()
            
            print("Admin user created successfully!")
            print("Username: admin")
            print("Password: admin123")
            print("\nPLEASE CHANGE THE PASSWORD AFTER FIRST LOGIN!")
            
        except Exception as e:
            print(f"Error creating admin user: {e}")
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(create_admin_user())