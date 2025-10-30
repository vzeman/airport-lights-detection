#!/usr/bin/env python3
"""
Initialize database with default data
Run this script after migrations to create initial super admin user
"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

# Add parent directory to path
sys.path.append('.')

from app.db.base import engine, Base
from app.db.base import AsyncSessionLocal
from app.models import User, UserRole, Permission
from app.core.security import get_password_hash


async def create_default_user():
    """Create default super admin user"""
    async with AsyncSessionLocal() as session:
        # Check if super admin already exists
        result = await session.execute(
            select(User).filter(User.username == "admin")
        )
        existing_user = result.scalars().first()
        
        if existing_user:
            print("Super admin user already exists")
            return
        
        # Create super admin user
        admin_user = User(
            id=str(uuid.uuid4()),
            email="admin@airport-mgmt.com",
            username="admin",
            first_name="System",
            last_name="Administrator",
            hashed_password=get_password_hash("admin123"),  # Change this password!
            is_active=True,
            is_superuser=True,
            role=UserRole.SUPER_ADMIN,
        )
        
        session.add(admin_user)
        await session.commit()
        
        print("Created super admin user:")
        print(f"  Username: admin")
        print(f"  Password: admin123")
        print(f"  Email: admin@airport-mgmt.com")
        print("\n⚠️  IMPORTANT: Change the default password after first login!")


async def create_default_permissions():
    """Create default permissions"""
    async with AsyncSessionLocal() as session:
        resources = ['user', 'airport', 'task', 'item', 'measurement']
        actions = ['create', 'read', 'update', 'delete', 'manage']
        
        for resource in resources:
            for action in actions:
                # Check if permission exists
                name = f"{resource}:{action}"
                result = await session.execute(
                    select(Permission).filter(Permission.name == name)
                )
                existing = result.scalars().first()
                
                if not existing:
                    permission = Permission(
                        id=str(uuid.uuid4()),
                        name=name,
                        resource=resource,
                        action=action,
                        description=f"Permission to {action} {resource}"
                    )
                    session.add(permission)
        
        await session.commit()
        print("Created default permissions")


async def create_sample_data():
    """Create sample airport and users for testing"""
    async with AsyncSessionLocal() as session:
        # Check if sample data exists
        result = await session.execute(
            select(User).filter(User.username == "john.doe")
        )
        if result.scalars().first():
            print("Sample data already exists")
            return
        
        # Create sample users
        users_data = [
            {
                "username": "john.doe",
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": UserRole.AIRPORT_ADMIN,
                "password": "password123"
            },
            {
                "username": "jane.smith",
                "email": "jane.smith@example.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "role": UserRole.MAINTENANCE_MANAGER,
                "password": "password123"
            },
            {
                "username": "bob.pilot",
                "email": "bob.pilot@example.com",
                "first_name": "Bob",
                "last_name": "Pilot",
                "role": UserRole.DRONE_OPERATOR,
                "password": "password123"
            }
        ]
        
        for user_data in users_data:
            user = User(
                id=str(uuid.uuid4()),
                email=user_data["email"],
                username=user_data["username"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                hashed_password=get_password_hash(user_data["password"]),
                is_active=True,
                is_superuser=False,
                role=user_data["role"],
            )
            session.add(user)
        
        await session.commit()
        print("Created sample users")


async def main():
    """Main initialization function"""
    print("Initializing database...")
    
    # Create tables (if not using Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create default data
    await create_default_permissions()
    await create_default_user()
    
    # Optionally create sample data
    response = input("\nCreate sample data for testing? (y/n): ")
    if response.lower() == 'y':
        await create_sample_data()
    
    print("\nDatabase initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())