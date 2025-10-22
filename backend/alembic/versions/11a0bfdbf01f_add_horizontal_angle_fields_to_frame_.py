"""add_horizontal_angle_fields_to_frame_measurements

Revision ID: 11a0bfdbf01f
Revises: e5f4a2a0c63d
Create Date: 2025-10-22 08:13:01.863374

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '11a0bfdbf01f'
down_revision = 'e5f4a2a0c63d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add horizontal angle columns for each PAPI light
    op.add_column('frame_measurements', sa.Column('papi_a_horizontal_angle', sa.Float(), nullable=True))
    op.add_column('frame_measurements', sa.Column('papi_b_horizontal_angle', sa.Float(), nullable=True))
    op.add_column('frame_measurements', sa.Column('papi_c_horizontal_angle', sa.Float(), nullable=True))
    op.add_column('frame_measurements', sa.Column('papi_d_horizontal_angle', sa.Float(), nullable=True))


def downgrade() -> None:
    # Remove horizontal angle columns for each PAPI light
    op.drop_column('frame_measurements', 'papi_d_horizontal_angle')
    op.drop_column('frame_measurements', 'papi_c_horizontal_angle')
    op.drop_column('frame_measurements', 'papi_b_horizontal_angle')
    op.drop_column('frame_measurements', 'papi_a_horizontal_angle')