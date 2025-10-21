"""
Database initialization functions
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
import logging

from app.models.user import User, UserRole
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)


async def init_default_admin(db: AsyncSession) -> None:
    """
    Initialize default admin user if no users exist in the database.

    Creates a default super admin with credentials:
    - Username: admin
    - Password: admin123
    - Email: admin@example.com
    """
    try:
        # Check if any users exist
        result = await db.execute(select(User))
        existing_users = result.scalars().first()

        if existing_users:
            logger.info("Users already exist. Skipping default admin creation.")
            return

        # Create default admin user
        default_admin = User(
            id=str(uuid.uuid4()),
            email="admin@example.com",
            username="admin",
            first_name="Admin",
            last_name="User",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_superuser=True,
            role=UserRole.SUPER_ADMIN,
            phone=None,
            organization="System"
        )

        db.add(default_admin)
        await db.commit()

        logger.info("✓ Default admin user created successfully")
        logger.info("  Username: admin")
        logger.info("  Password: admin123")
        logger.info("  Email: admin@example.com")
        logger.info("  IMPORTANT: Please change the default password after first login!")

    except Exception as e:
        logger.error(f"Error creating default admin user: {e}")
        await db.rollback()
        raise
