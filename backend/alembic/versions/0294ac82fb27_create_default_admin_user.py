"""create_default_admin_user

Revision ID: 0294ac82fb27
Revises: add_s3_storage
Create Date: 2025-10-27 02:20:29.386188

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.mysql import CHAR
import uuid
from datetime import datetime
from passlib.context import CryptContext


# revision identifiers, used by Alembic.
revision = '0294ac82fb27'
down_revision = 'add_s3_storage'  # add S3 storage fields
branch_labels = None
depends_on = None

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    """Create default admin user if no users exist."""

    # Define table structure for the operation
    users = table('users',
        column('id', CHAR(36)),
        column('email', String),
        column('username', String),
        column('first_name', String),
        column('last_name', String),
        column('hashed_password', String),
        column('is_active', Boolean),
        column('is_superuser', Boolean),
        column('role', String),
        column('phone', String),
        column('organization', String),
        column('created_at', DateTime),
        column('updated_at', DateTime),
    )

    # Check if any users exist
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT COUNT(*) FROM users"))
    user_count = result.scalar()

    # Only create admin if no users exist
    if user_count == 0:
        # Hash the default password
        hashed_password = pwd_context.hash("admin123")

        # Insert default admin user
        op.bulk_insert(users, [
            {
                'id': str(uuid.uuid4()),
                'email': 'admin@example.com',
                'username': 'admin',
                'first_name': 'Admin',
                'last_name': 'User',
                'hashed_password': hashed_password,
                'is_active': True,
                'is_superuser': True,
                'role': 'SUPER_ADMIN',
                'phone': None,
                'organization': 'System',
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
            }
        ])
        print("✓ Default admin user created (username: admin, password: admin123)")
        print("  IMPORTANT: Please change the default password after first login!")


def downgrade() -> None:
    """Remove default admin user."""
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM users WHERE username = 'admin' AND email = 'admin@example.com'"))