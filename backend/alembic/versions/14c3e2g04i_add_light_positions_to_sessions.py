"""add light_positions to measurement sessions

Revision ID: 14c3e2g04i
Revises: 13c2d1f03h
Create Date: 2025-10-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '14c3e2g04i'
down_revision = '13c2d1f03h'  # add_notes_to_measurement_sessions
branch_labels = None
depends_on = None


def upgrade():
    # Add light_positions column to measurement_sessions table
    # This column stores the manually adjusted PAPI light rectangle positions (x, y, size)
    # Format: {"PAPI_A": {"x": 20, "y": 50, "size": 8}, "PAPI_B": {...}, ...}
    # Values are in percentages of image dimensions

    # Check if column already exists before adding
    # This is safe because MySQL will error if column already exists
    from sqlalchemy import inspect
    from app.db.session import engine

    # For safety, we'll use a conditional add that won't fail if column exists
    # Use raw SQL with IF NOT EXISTS pattern
    op.execute("""
        SELECT COUNT(*) INTO @col_exists FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'measurement_sessions'
        AND COLUMN_NAME = 'light_positions'
    """)

    # Only add if doesn't exist
    op.execute("""
        SET @ddl = IF(@col_exists = 0,
            'ALTER TABLE measurement_sessions ADD COLUMN light_positions JSON NULL COMMENT "Manually adjusted PAPI light positions: {PAPI_A: {x: %, y: %, size: %}, ...}"',
            'SELECT "Column light_positions already exists" AS message'
        )
    """)

    op.execute("PREPARE stmt FROM @ddl")
    op.execute("EXECUTE stmt")
    op.execute("DEALLOCATE PREPARE stmt")


def downgrade():
    # Remove light_positions column from measurement_sessions table
    op.drop_column('measurement_sessions', 'light_positions')
