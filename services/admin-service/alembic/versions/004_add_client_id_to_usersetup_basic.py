"""Add client_id to usersetup_basic

Revision ID: 004
Revises: 003
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'usersetup_basic',
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.client_id'), nullable=True)
    )
    op.create_index('ix_usersetup_basic_client_id', 'usersetup_basic', ['client_id'])


def downgrade():
    op.drop_index('ix_usersetup_basic_client_id', table_name='usersetup_basic')
    op.drop_column('usersetup_basic', 'client_id')
