"""add_nominal_angle_and_tolerance_to_reference_points

Revision ID: 2b7563098595
Revises: d762f2f90e75
Create Date: 2025-10-21 21:21:04.202517

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2b7563098595'
down_revision = 'd762f2f90e75'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add nominal_angle and tolerance columns to runway_reference_points table
    op.add_column('runway_reference_points', sa.Column('nominal_angle', sa.Float(), nullable=True))
    op.add_column('runway_reference_points', sa.Column('tolerance', sa.Float(), nullable=True))

    # Set default values based on point_type
    # PAPI_A: 2.5, PAPI_B: 2.83, PAPI_C: 3.17, PAPI_D: 3.5
    # All PAPI lights get tolerance of 0.1
    # TOUCH_POINT doesn't get these values (remains NULL)
    op.execute("""
        UPDATE runway_reference_points
        SET nominal_angle = 2.5, tolerance = 0.1
        WHERE point_type = 'PAPI_A'
    """)
    op.execute("""
        UPDATE runway_reference_points
        SET nominal_angle = 2.83, tolerance = 0.1
        WHERE point_type = 'PAPI_B'
    """)
    op.execute("""
        UPDATE runway_reference_points
        SET nominal_angle = 3.17, tolerance = 0.1
        WHERE point_type = 'PAPI_C'
    """)
    op.execute("""
        UPDATE runway_reference_points
        SET nominal_angle = 3.5, tolerance = 0.1
        WHERE point_type = 'PAPI_D'
    """)
    # For PAPI_E through PAPI_H, use progressive values
    op.execute("""
        UPDATE runway_reference_points
        SET nominal_angle = 2.5, tolerance = 0.1
        WHERE point_type = 'PAPI_E'
    """)
    op.execute("""
        UPDATE runway_reference_points
        SET nominal_angle = 2.83, tolerance = 0.1
        WHERE point_type = 'PAPI_F'
    """)
    op.execute("""
        UPDATE runway_reference_points
        SET nominal_angle = 3.17, tolerance = 0.1
        WHERE point_type = 'PAPI_G'
    """)
    op.execute("""
        UPDATE runway_reference_points
        SET nominal_angle = 3.5, tolerance = 0.1
        WHERE point_type = 'PAPI_H'
    """)


def downgrade() -> None:
    # Remove the columns
    op.drop_column('runway_reference_points', 'tolerance')
    op.drop_column('runway_reference_points', 'nominal_angle')