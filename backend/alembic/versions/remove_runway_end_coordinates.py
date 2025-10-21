"""remove runway end coordinates

Revision ID: remove_end_coords
Revises: abc123def456
Create Date: 2025-10-21 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_end_coords'
down_revision = 'abc123def456'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove end_lat and end_lon columns as they will be calculated from start position, heading, and length
    op.drop_column('runways', 'end_lat')
    op.drop_column('runways', 'end_lon')


def downgrade() -> None:
    # Add back end_lat and end_lon columns
    op.add_column('runways', sa.Column('end_lat', sa.Float(), nullable=True))
    op.add_column('runways', sa.Column('end_lon', sa.Float(), nullable=True))
