"""extend_papi_lights_to_8

Revision ID: d762f2f90e75
Revises: remove_end_coords
Create Date: 2025-10-21 15:58:08.987638

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd762f2f90e75'
down_revision = 'remove_end_coords'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend the ReferencePointType enum to include E, F, G, H
    op.execute("""
        ALTER TABLE runway_reference_points
        MODIFY COLUMN point_type ENUM('PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D',
                                      'PAPI_E', 'PAPI_F', 'PAPI_G', 'PAPI_H',
                                      'TOUCH_POINT') NOT NULL
    """)


def downgrade() -> None:
    # Revert back to original 4 PAPI lights (A-D)
    # Note: This will fail if there are any E, F, G, or H points in the database
    op.execute("""
        ALTER TABLE runway_reference_points
        MODIFY COLUMN point_type ENUM('PAPI_A', 'PAPI_B', 'PAPI_C', 'PAPI_D',
                                      'TOUCH_POINT') NOT NULL
    """)