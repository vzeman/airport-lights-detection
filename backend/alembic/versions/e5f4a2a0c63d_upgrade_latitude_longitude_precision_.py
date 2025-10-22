"""upgrade_latitude_longitude_precision_for_centimeter_accuracy

Revision ID: e5f4a2a0c63d
Revises: 2b7563098595
Create Date: 2025-10-22 04:41:22.735075

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5f4a2a0c63d'
down_revision = '2b7563098595'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Upgrade latitude/longitude columns to DECIMAL for centimeter-level precision.

    DECIMAL(11, 8) for latitude: -90 to +90 with 8 decimal places (~1.1mm precision)
    DECIMAL(12, 8) for longitude: -180 to +180 with 8 decimal places (~1.1mm precision)
    """

    # 1. Airports table
    op.alter_column('airports', 'latitude',
                    type_=sa.DECIMAL(precision=11, scale=8),
                    existing_type=sa.Float(),
                    nullable=False)
    op.alter_column('airports', 'longitude',
                    type_=sa.DECIMAL(precision=12, scale=8),
                    existing_type=sa.Float(),
                    nullable=False)

    # 2. Airport items table
    op.alter_column('airport_items', 'latitude',
                    type_=sa.DECIMAL(precision=11, scale=8),
                    existing_type=sa.Float(),
                    nullable=True)
    op.alter_column('airport_items', 'longitude',
                    type_=sa.DECIMAL(precision=12, scale=8),
                    existing_type=sa.Float(),
                    nullable=True)

    # 3. Runways table
    op.alter_column('runways', 'start_lat',
                    type_=sa.DECIMAL(precision=11, scale=8),
                    existing_type=sa.Float(),
                    nullable=True)
    op.alter_column('runways', 'start_lon',
                    type_=sa.DECIMAL(precision=12, scale=8),
                    existing_type=sa.Float(),
                    nullable=True)

    # 4. Runway reference points table
    op.alter_column('runway_reference_points', 'latitude',
                    type_=sa.DECIMAL(precision=11, scale=8),
                    existing_type=sa.Float(),
                    nullable=False)
    op.alter_column('runway_reference_points', 'longitude',
                    type_=sa.DECIMAL(precision=12, scale=8),
                    existing_type=sa.Float(),
                    nullable=False)

    # 5. PAPI reference points table
    op.alter_column('reference_points', 'latitude',
                    type_=sa.DECIMAL(precision=11, scale=8),
                    existing_type=sa.Float(),
                    nullable=False)
    op.alter_column('reference_points', 'longitude',
                    type_=sa.DECIMAL(precision=12, scale=8),
                    existing_type=sa.Float(),
                    nullable=False)

    # 6. Frame measurements table (drone positions)
    op.alter_column('frame_measurements', 'drone_latitude',
                    type_=sa.DECIMAL(precision=11, scale=8),
                    existing_type=sa.Float(),
                    nullable=False)
    op.alter_column('frame_measurements', 'drone_longitude',
                    type_=sa.DECIMAL(precision=12, scale=8),
                    existing_type=sa.Float(),
                    nullable=False)

    # 7. Measurements table
    op.alter_column('measurements', 'latitude',
                    type_=sa.DECIMAL(precision=11, scale=8),
                    existing_type=sa.Float(),
                    nullable=True)
    op.alter_column('measurements', 'longitude',
                    type_=sa.DECIMAL(precision=12, scale=8),
                    existing_type=sa.Float(),
                    nullable=True)

    # 8. Airspaces table (upgrade from DECIMAL(10,7) to DECIMAL(11,8) and DECIMAL(12,8))
    op.alter_column('airspaces', 'center_latitude',
                    type_=sa.DECIMAL(precision=11, scale=8),
                    existing_type=sa.DECIMAL(precision=10, scale=7),
                    nullable=True)
    op.alter_column('airspaces', 'center_longitude',
                    type_=sa.DECIMAL(precision=12, scale=8),
                    existing_type=sa.DECIMAL(precision=10, scale=7),
                    nullable=True)


def downgrade() -> None:
    """
    Downgrade latitude/longitude columns back to Float.
    WARNING: This will result in precision loss!
    """

    # 1. Airports table
    op.alter_column('airports', 'latitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=11, scale=8),
                    nullable=False)
    op.alter_column('airports', 'longitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=12, scale=8),
                    nullable=False)

    # 2. Airport items table
    op.alter_column('airport_items', 'latitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=11, scale=8),
                    nullable=True)
    op.alter_column('airport_items', 'longitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=12, scale=8),
                    nullable=True)

    # 3. Runways table
    op.alter_column('runways', 'start_lat',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=11, scale=8),
                    nullable=True)
    op.alter_column('runways', 'start_lon',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=12, scale=8),
                    nullable=True)

    # 4. Runway reference points table
    op.alter_column('runway_reference_points', 'latitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=11, scale=8),
                    nullable=False)
    op.alter_column('runway_reference_points', 'longitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=12, scale=8),
                    nullable=False)

    # 5. PAPI reference points table
    op.alter_column('reference_points', 'latitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=11, scale=8),
                    nullable=False)
    op.alter_column('reference_points', 'longitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=12, scale=8),
                    nullable=False)

    # 6. Frame measurements table (drone positions)
    op.alter_column('frame_measurements', 'drone_latitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=11, scale=8),
                    nullable=False)
    op.alter_column('frame_measurements', 'drone_longitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=12, scale=8),
                    nullable=False)

    # 7. Measurements table
    op.alter_column('measurements', 'latitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=11, scale=8),
                    nullable=True)
    op.alter_column('measurements', 'longitude',
                    type_=sa.Float(),
                    existing_type=sa.DECIMAL(precision=12, scale=8),
                    nullable=True)

    # 8. Airspaces table (downgrade to original DECIMAL(10,7))
    op.alter_column('airspaces', 'center_latitude',
                    type_=sa.DECIMAL(precision=10, scale=7),
                    existing_type=sa.DECIMAL(precision=11, scale=8),
                    nullable=True)
    op.alter_column('airspaces', 'center_longitude',
                    type_=sa.DECIMAL(precision=10, scale=7),
                    existing_type=sa.DECIMAL(precision=12, scale=8),
                    nullable=True)