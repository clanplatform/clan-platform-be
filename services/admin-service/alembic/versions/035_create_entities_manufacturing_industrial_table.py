"""create entities_manufacturing_industrial table

The branch form's "Manufacturing plant & production" + "Manufacturing
compliance documents" sections — one row per branch (entities row), holding
the uploaded compliance-document references plus the plant / production fields.
Carried in the branch payload as the nested
``entities_manufacturing_industrial`` list (see EntityBase / OnboardingBranch),
upserted onto the single unique ``entity_id`` row.

entities_manufacturing_industrial also lives in every tenant DB (created fresh
via create_all() at provisioning time, so new tenants get it automatically) —
any already-provisioned tenant DB needs
scripts/migrations/create_entities_manufacturing_industrial_table.sql run
against it directly.

Defensive: the live master DB schema is kept in sync via create_all() from the
models, so this table may already exist before `alembic upgrade` runs — the
create is guarded by an existence check.

Revision ID: 035
Revises: 034
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "entities_manufacturing_industrial"


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
        # Manufacturing compliance documents (file references / URLs)
        sa.Column("iso_certificates_doc", sa.String(500), nullable=True),
        sa.Column("safety_osha_compliance_doc", sa.String(500), nullable=True),
        sa.Column("environmental_permit_doc", sa.String(500), nullable=True),
        # Manufacturing plant & production
        sa.Column("plant_type", sa.String(100), nullable=True),
        sa.Column("production_lines", sa.Integer(), nullable=True),
        sa.Column("shift_pattern", sa.String(100), nullable=True),
        sa.Column("production_capacity", sa.String(100), nullable=True),
        sa.Column("iso_certifications", ARRAY(sa.Text()), nullable=True),
        sa.Column("erp_mes_system", sa.String(150), nullable=True),
        sa.Column("handles_hazardous_materials", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("unionized_workforce", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", name="uq_entities_manufacturing_industrial_entity"),
    )
    op.create_index("ix_entities_manufacturing_industrial_id", _TABLE, ["id"])
    op.create_index("ix_entities_manufacturing_industrial_entity_id", _TABLE, ["entity_id"])
    op.create_index("ix_entities_manufacturing_industrial_tenant_id", _TABLE, ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    op.drop_index("ix_entities_manufacturing_industrial_tenant_id", table_name=_TABLE)
    op.drop_index("ix_entities_manufacturing_industrial_entity_id", table_name=_TABLE)
    op.drop_index("ix_entities_manufacturing_industrial_id", table_name=_TABLE)
    op.drop_table(_TABLE)
