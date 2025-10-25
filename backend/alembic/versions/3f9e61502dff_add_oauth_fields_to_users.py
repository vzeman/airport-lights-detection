"""add_oauth_fields_to_users

Revision ID: 3f9e61502dff
Revises: 12b1c0e0f02g
Create Date: 2025-10-25 15:53:35.712049

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3f9e61502dff'
down_revision = '12b1c0e0f02g'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make hashed_password nullable for OAuth users
    op.alter_column('users', 'hashed_password',
                    existing_type=sa.String(255),
                    nullable=True)

    # Add OAuth fields
    op.add_column('users', sa.Column('oauth_provider', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('oauth_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('oauth_access_token', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('oauth_refresh_token', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('oauth_token_expires_at', sa.DateTime(), nullable=True))

    # Add indexes
    op.create_index('idx_users_oauth_id', 'users', ['oauth_id'], unique=False)
    op.create_index('idx_users_oauth_provider_id', 'users', ['oauth_provider', 'oauth_id'], unique=True)


def downgrade() -> None:
    # Remove indexes
    op.drop_index('idx_users_oauth_provider_id', table_name='users')
    op.drop_index('idx_users_oauth_id', table_name='users')

    # Remove OAuth fields
    op.drop_column('users', 'oauth_token_expires_at')
    op.drop_column('users', 'oauth_refresh_token')
    op.drop_column('users', 'oauth_access_token')
    op.drop_column('users', 'oauth_id')
    op.drop_column('users', 'oauth_provider')

    # Make hashed_password NOT NULL again
    op.alter_column('users', 'hashed_password',
                    existing_type=sa.String(255),
                    nullable=False)