"""
007: Add client_applications table and rename clients.tenant_id → gateway_tenant_ref

- client_applications: junction table for application-level licensing (Tier 2)
  A client that buys a whole application gets access to all its modules.
- Rename clients.tenant_id → clients.gateway_tenant_ref to eliminate the
  naming confusion where "tenant_id" on the clients table actually refers
  to the gateway routing record, not the client itself.

Revision ID: 007
Revises: 006
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create client_applications junction table
    op.create_table(
        "client_applications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "client_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clients.client_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_id",
            UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("assigned_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("client_id", "application_id", name="uq_client_application"),
    )
    op.create_index("ix_client_applications_client_id", "client_applications", ["client_id"])
    op.create_index("ix_client_applications_application_id", "client_applications", ["application_id"])

    # 2. Rename clients.tenant_id → clients.gateway_tenant_ref
    #    This makes it explicit that this column is a cross-service reference to
    #    the gateway's tenants.id, NOT the primary org identifier.
    op.alter_column(
        "clients",
        "tenant_id",
        new_column_name="gateway_tenant_ref",
    )


def downgrade() -> None:
    op.alter_column(
        "clients",
        "gateway_tenant_ref",
        new_column_name="tenant_id",
    )

    op.drop_index("ix_client_applications_application_id", table_name="client_applications")
    op.drop_index("ix_client_applications_client_id", table_name="client_applications")
    op.drop_table("client_applications")
