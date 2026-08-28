"""create logistics_supply_chain table

The branch form's "Logistics & supply chain" section — one row per branch
(entities row), holding the fleet / warehouse / transport fields. Carried in the
branch payload as the nested ``logistics_supply_chain`` list (see EntityBase /
OnboardingBranch), upserted onto the single unique ``entity_id`` row.

logistics_supply_chain also lives in every tenant DB (created fresh via
create_all() at provisioning time, so new tenants get it automatically) — any
already-provisioned tenant DB needs
scripts/migrations/create_logistics_supply_chain_table.sql run against it
directly.

Defensive: the live master DB schema is kept in sync via create_all() from the
models, so this table may already exist before `alembic upgrade` runs — the
create is guarded by an existence check.

Revision ID: 038
Revises: 037
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "logistics_supply_chain"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE in inspector.get_table_names():
        return

    op.create_table(
        _TABLE,
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        # Logistics & supply chain
        sa.Column("fleet_size", sa.String(100), nullable=True),
        sa.Column("warehouses_dcs", sa.Integer(), nullable=True),
        sa.Column("transport_modes", ARRAY(sa.Text()), nullable=True),
        sa.Column("wms_tms_system", sa.String(150), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", name="uq_logistics_supply_chain_entity"),
    )
    op.create_index("ix_logistics_supply_chain_id", _TABLE, ["id"])
    op.create_index("ix_logistics_supply_chain_entity_id", _TABLE, ["entity_id"])
    op.create_index("ix_logistics_supply_chain_tenant_id", _TABLE, ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    op.drop_index("ix_logistics_supply_chain_tenant_id", table_name=_TABLE)
    op.drop_index("ix_logistics_supply_chain_entity_id", table_name=_TABLE)
    op.drop_index("ix_logistics_supply_chain_id", table_name=_TABLE)
    op.drop_table(_TABLE)
