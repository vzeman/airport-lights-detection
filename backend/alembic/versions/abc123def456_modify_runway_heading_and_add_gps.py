"""modify runway heading and add gps coordinates

Revision ID: abc123def456
Revises: 7f154f6e78b8
Create Date: 2025-10-21 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'abc123def456'
down_revision = '7f154f6e78b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column('runways', sa.Column('heading', sa.Float(), nullable=True))
    op.add_column('runways', sa.Column('start_lat', sa.Float(), nullable=True))
    op.add_column('runways', sa.Column('start_lon', sa.Float(), nullable=True))
    op.add_column('runways', sa.Column('end_lat', sa.Float(), nullable=True))
    op.add_column('runways', sa.Column('end_lon', sa.Float(), nullable=True))

    # Copy heading_1 to heading (convert from integer to float)
    op.execute('UPDATE runways SET heading = CAST(heading_1 AS FLOAT)')

    # Make heading non-nullable after data migration
    op.alter_column('runways', 'heading',
                    existing_type=sa.Float(),
                    nullable=False)

    # Drop old heading columns
    op.drop_column('runways', 'heading_1')
    op.drop_column('runways', 'heading_2')


def downgrade() -> None:
    # Add back old columns
    op.add_column('runways', sa.Column('heading_1', sa.Integer(), nullable=True))
    op.add_column('runways', sa.Column('heading_2', sa.Integer(), nullable=True))

    # Copy heading back to heading_1 (convert from float to integer)
    op.execute('UPDATE runways SET heading_1 = CAST(heading AS SIGNED)')

    # Calculate heading_2 as opposite direction (heading + 180, modulo 360)
    op.execute('UPDATE runways SET heading_2 = CAST(MOD(heading + 180, 360) AS SIGNED)')

    # Make heading_1 and heading_2 non-nullable
    op.alter_column('runways', 'heading_1',
                    existing_type=sa.Integer(),
                    nullable=False)
    op.alter_column('runways', 'heading_2',
                    existing_type=sa.Integer(),
                    nullable=False)

    # Drop new columns
    op.drop_column('runways', 'end_lon')
    op.drop_column('runways', 'end_lat')
    op.drop_column('runways', 'start_lon')
    op.drop_column('runways', 'start_lat')
    op.drop_column('runways', 'heading')
