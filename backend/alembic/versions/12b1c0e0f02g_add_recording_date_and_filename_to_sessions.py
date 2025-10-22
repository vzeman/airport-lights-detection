"""add_recording_date_and_filename_to_sessions

Revision ID: 12b1c0e0f02g
Revises: 11a0bfdbf01f
Create Date: 2025-10-22 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '12b1c0e0f02g'
down_revision = '11a0bfdbf01f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add recording_date and original_video_filename columns to measurement_sessions table
    op.add_column('measurement_sessions', sa.Column('recording_date', sa.DateTime(), nullable=True))
    op.add_column('measurement_sessions', sa.Column('original_video_filename', sa.String(500), nullable=True))


def downgrade() -> None:
    # Remove recording_date and original_video_filename columns from measurement_sessions table
    op.drop_column('measurement_sessions', 'original_video_filename')
    op.drop_column('measurement_sessions', 'recording_date')
