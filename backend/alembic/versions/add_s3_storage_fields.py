"""add S3 storage fields

Revision ID: add_s3_storage
Revises:
Create Date: 2025-10-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_s3_storage'
down_revision = '3f9e61502dff'  # OAuth fields migration
branch_labels = None
depends_on = None


def upgrade():
    # Add S3 storage columns to measurement_sessions table
    op.add_column('measurement_sessions',
                  sa.Column('storage_type', sa.String(length=10), nullable=True, server_default='local'))
    op.add_column('measurement_sessions',
                  sa.Column('original_video_s3_key', sa.String(length=500), nullable=True))
    op.add_column('measurement_sessions',
                  sa.Column('enhanced_video_s3_key', sa.String(length=500), nullable=True))
    op.add_column('measurement_sessions',
                  sa.Column('enhanced_audio_video_s3_key', sa.String(length=500), nullable=True))
    op.add_column('measurement_sessions',
                  sa.Column('frame_measurements_s3_key', sa.String(length=500), nullable=True))
    op.add_column('measurement_sessions',
                  sa.Column('preview_image_s3_key', sa.String(length=500), nullable=True))
    op.add_column('measurement_sessions',
                  sa.Column('papi_a_video_s3_key', sa.String(length=500), nullable=True))
    op.add_column('measurement_sessions',
                  sa.Column('papi_b_video_s3_key', sa.String(length=500), nullable=True))
    op.add_column('measurement_sessions',
                  sa.Column('papi_c_video_s3_key', sa.String(length=500), nullable=True))
    op.add_column('measurement_sessions',
                  sa.Column('papi_d_video_s3_key', sa.String(length=500), nullable=True))

    # Update existing rows to have storage_type='local'
    op.execute("UPDATE measurement_sessions SET storage_type='local' WHERE storage_type IS NULL")


def downgrade():
    # Remove S3 storage columns
    op.drop_column('measurement_sessions', 'papi_d_video_s3_key')
    op.drop_column('measurement_sessions', 'papi_c_video_s3_key')
    op.drop_column('measurement_sessions', 'papi_b_video_s3_key')
    op.drop_column('measurement_sessions', 'papi_a_video_s3_key')
    op.drop_column('measurement_sessions', 'preview_image_s3_key')
    op.drop_column('measurement_sessions', 'frame_measurements_s3_key')
    op.drop_column('measurement_sessions', 'enhanced_audio_video_s3_key')
    op.drop_column('measurement_sessions', 'enhanced_video_s3_key')
    op.drop_column('measurement_sessions', 'original_video_s3_key')
    op.drop_column('measurement_sessions', 'storage_type')
