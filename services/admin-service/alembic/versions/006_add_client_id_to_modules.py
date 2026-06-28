"""Create client_modules junction table (many-to-many: clients <-> modules)

Revision ID: 006
Revises: 005
Create Date: 2026-06-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'client_modules' not in existing_tables:
        op.create_table(
            'client_modules',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('client_id', UUID(as_uuid=True),
                      sa.ForeignKey('clients.client_id', ondelete='CASCADE'), nullable=False),
            sa.Column('module_id', UUID(as_uuid=True),
                      sa.ForeignKey('modules.id', ondelete='CASCADE'), nullable=False),
            sa.Column('is_active', sa.Boolean, server_default='true', nullable=False),
            sa.Column('notes', sa.Text, nullable=True),
            sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('assigned_by', UUID(as_uuid=True), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_by', UUID(as_uuid=True), nullable=True),
            sa.UniqueConstraint('client_id', 'module_id', name='uq_client_module'),
        )
        op.create_index('ix_client_modules_client_id', 'client_modules', ['client_id'])
        op.create_index('ix_client_modules_module_id', 'client_modules', ['module_id'])


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'client_modules' in existing_tables:
        op.drop_index('ix_client_modules_module_id', table_name='client_modules')
        op.drop_index('ix_client_modules_client_id', table_name='client_modules')
        op.drop_table('client_modules')
