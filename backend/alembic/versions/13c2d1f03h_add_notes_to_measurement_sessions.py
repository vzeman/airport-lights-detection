"""add notes to measurement sessions

Revision ID: 13c2d1f03h
Revises: add_s3_storage
Create Date: 2025-10-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '13c2d1f03h'
down_revision = '0294ac82fb27'  # create_default_admin_user
branch_labels = None
depends_on = None


def upgrade():
    # Add notes column to measurement_sessions table
    op.add_column('measurement_sessions',
        sa.Column('notes', sa.Text(), nullable=True, comment='Markdown formatted notes about the measurement')
    )


def downgrade():
    # Remove notes column from measurement_sessions table
    op.drop_column('measurement_sessions', 'notes')
