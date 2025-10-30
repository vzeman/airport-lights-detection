"""drop frame_measurements table

Revision ID: 15e4g3h06k
Revises: 14c3e2g04i
Create Date: 2025-10-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '15e4g3h06k'
down_revision = '14c3e2g04i'  # add_light_positions_to_sessions
branch_labels = None
depends_on = None


def upgrade():
    # Drop frame_measurements table - all measurements now stored in S3 as JSON
    op.drop_table('frame_measurements')


def downgrade():
    # Recreate frame_measurements table structure
    op.create_table(
        'frame_measurements',
        sa.Column('id', mysql.CHAR(36), nullable=False),
        sa.Column('session_id', mysql.CHAR(36), nullable=False),
        sa.Column('frame_number', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('drone_latitude', sa.Numeric(precision=11, scale=8), nullable=False),
        sa.Column('drone_longitude', sa.Numeric(precision=12, scale=8), nullable=False),
        sa.Column('drone_elevation', sa.Float(), nullable=False),
        sa.Column('gimbal_pitch', sa.Float(), nullable=True),
        sa.Column('gimbal_roll', sa.Float(), nullable=True),
        sa.Column('gimbal_yaw', sa.Float(), nullable=True),
        sa.Column('papi_a_status', sa.Enum('not_visible', 'red', 'white', 'transition', name='lightstatus'), nullable=True),
        sa.Column('papi_a_rgb', sa.JSON(), nullable=True),
        sa.Column('papi_a_intensity', sa.Float(), nullable=True),
        sa.Column('papi_a_angle', sa.Float(), nullable=True),
        sa.Column('papi_a_horizontal_angle', sa.Float(), nullable=True),
        sa.Column('papi_a_distance_ground', sa.Float(), nullable=True),
        sa.Column('papi_a_distance_direct', sa.Float(), nullable=True),
        sa.Column('papi_b_status', sa.Enum('not_visible', 'red', 'white', 'transition', name='lightstatus'), nullable=True),
        sa.Column('papi_b_rgb', sa.JSON(), nullable=True),
        sa.Column('papi_b_intensity', sa.Float(), nullable=True),
        sa.Column('papi_b_angle', sa.Float(), nullable=True),
        sa.Column('papi_b_horizontal_angle', sa.Float(), nullable=True),
        sa.Column('papi_b_distance_ground', sa.Float(), nullable=True),
        sa.Column('papi_b_distance_direct', sa.Float(), nullable=True),
        sa.Column('papi_c_status', sa.Enum('not_visible', 'red', 'white', 'transition', name='lightstatus'), nullable=True),
        sa.Column('papi_c_rgb', sa.JSON(), nullable=True),
        sa.Column('papi_c_intensity', sa.Float(), nullable=True),
        sa.Column('papi_c_angle', sa.Float(), nullable=True),
        sa.Column('papi_c_horizontal_angle', sa.Float(), nullable=True),
        sa.Column('papi_c_distance_ground', sa.Float(), nullable=True),
        sa.Column('papi_c_distance_direct', sa.Float(), nullable=True),
        sa.Column('papi_d_status', sa.Enum('not_visible', 'red', 'white', 'transition', name='lightstatus'), nullable=True),
        sa.Column('papi_d_rgb', sa.JSON(), nullable=True),
        sa.Column('papi_d_intensity', sa.Float(), nullable=True),
        sa.Column('papi_d_angle', sa.Float(), nullable=True),
        sa.Column('papi_d_horizontal_angle', sa.Float(), nullable=True),
        sa.Column('papi_d_distance_ground', sa.Float(), nullable=True),
        sa.Column('papi_d_distance_direct', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['measurement_sessions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
