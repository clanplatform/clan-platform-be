"""Add tenant_id to clients, client_id FK to modules, buttons table

Revision ID: 005
Revises: 004
Create Date: 2026-06-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Add tenant_id (UUID) to clients
    client_columns = [col['name'] for col in inspector.get_columns('clients')]
    if 'tenant_id' not in client_columns:
        op.add_column(
            'clients',
            sa.Column('tenant_id', UUID(as_uuid=True), nullable=True)
        )
        # Back-fill existing rows with a unique UUID each
        op.execute("UPDATE clients SET tenant_id = gen_random_uuid() WHERE tenant_id IS NULL")
        op.alter_column('clients', 'tenant_id', nullable=False)
        op.create_unique_constraint('uq_clients_tenant_id', 'clients', ['tenant_id'])
    client_indexes = [idx['name'] for idx in inspector.get_indexes('clients')]
    if 'ix_clients_tenant_id' not in client_indexes:
        op.create_index('ix_clients_tenant_id', 'clients', ['tenant_id'])

    # 2. Create buttons table
    if 'buttons' not in existing_tables:
        op.create_table(
            'buttons',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('menu_id', UUID(as_uuid=True), sa.ForeignKey('menus.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('label', sa.String(150), nullable=False),
            sa.Column('key', sa.String(100), nullable=True),
            sa.Column('icon', sa.String(100), nullable=True),
            sa.Column('tooltip', sa.String(255), nullable=True),
            sa.Column('variant', sa.String(50), nullable=True),
            sa.Column('action_type', sa.String(100), nullable=True),
            sa.Column('action_payload', sa.JSON, nullable=True),
            sa.Column('order_index', sa.Integer, server_default='0'),
            sa.Column('is_active', sa.Boolean, server_default='true', nullable=False),
            sa.Column('is_visible', sa.Boolean, server_default='true', nullable=False),
            sa.Column('is_deleted', sa.Boolean, server_default='false', nullable=False),
            sa.Column('access', ARRAY(sa.String), server_default='{"read"}', nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('created_by', sa.String(50), nullable=True),
            sa.Column('updated_by', sa.String(50), nullable=True),
        )
        op.create_index('ix_buttons_menu_id', 'buttons', ['menu_id'])


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'buttons' in existing_tables:
        op.drop_index('ix_buttons_menu_id', table_name='buttons')
        op.drop_table('buttons')

    client_indexes = [idx['name'] for idx in inspector.get_indexes('clients')]
    if 'ix_clients_tenant_id' in client_indexes:
        op.drop_index('ix_clients_tenant_id', table_name='clients')
    client_columns = [col['name'] for col in inspector.get_columns('clients')]
    if 'tenant_id' in client_columns:
        op.drop_column('clients', 'tenant_id')
