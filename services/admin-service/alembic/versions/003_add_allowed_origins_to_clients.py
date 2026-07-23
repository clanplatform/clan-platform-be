"""Add allowed_origins to clients for dynamic CORS

Revision ID: 003
Revises: 002
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'clients',
        sa.Column('allowed_origins', ARRAY(sa.Text()), nullable=True)
    )
    op.create_index(
        'ix_clients_allowed_origins',
        'clients',
        ['allowed_origins'],
        postgresql_using='gin',
    )


def downgrade() -> None:
    op.drop_index('ix_clients_allowed_origins', table_name='clients')
    op.drop_column('clients', 'allowed_origins')
