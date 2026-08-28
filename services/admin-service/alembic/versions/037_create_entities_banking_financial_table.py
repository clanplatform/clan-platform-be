"""create entities_banking_financial table

The branch form's "Financial services & regulation" + "Financial services
compliance documents" sections — one row per branch (entities row), holding the
uploaded compliance-document references plus the regulator / licensing / AML
fields. Carried in the branch payload as the nested
``entities_banking_financial`` list (see EntityBase / OnboardingBranch),
upserted onto the single unique ``entity_id`` row.

entities_banking_financial also lives in every tenant DB (created fresh via
create_all() at provisioning time, so new tenants get it automatically) — any
already-provisioned tenant DB needs
scripts/migrations/create_entities_banking_financial_table.sql run against it
directly.

Defensive: the live master DB schema is kept in sync via create_all() from the
models, so this table may already exist before `alembic upgrade` runs — the
create is guarded by an existence check.

Revision ID: 037
Revises: 036
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "entities_banking_financial"


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
        # Financial services compliance documents (file references / URLs)
        sa.Column("regulatory_license_doc", sa.String(500), nullable=True),
        sa.Column("aml_kyc_policy_doc", sa.String(500), nullable=True),
        sa.Column("pci_dss_attestation_doc", sa.String(500), nullable=True),
        # Financial services & regulation
        sa.Column("primary_regulator", sa.String(100), nullable=True),
        sa.Column("license_type", sa.String(100), nullable=True),
        sa.Column("license_number", sa.String(100), nullable=True),
        sa.Column("aml_compliance_officer", sa.String(200), nullable=True),
        sa.Column("kyc_level", sa.String(50), nullable=True),
        sa.Column("pci_dss_in_scope", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", name="uq_entities_banking_financial_entity"),
    )
    op.create_index("ix_entities_banking_financial_id", _TABLE, ["id"])
    op.create_index("ix_entities_banking_financial_entity_id", _TABLE, ["entity_id"])
    op.create_index("ix_entities_banking_financial_tenant_id", _TABLE, ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _TABLE not in inspector.get_table_names():
        return
    op.drop_index("ix_entities_banking_financial_tenant_id", table_name=_TABLE)
    op.drop_index("ix_entities_banking_financial_entity_id", table_name=_TABLE)
    op.drop_index("ix_entities_banking_financial_id", table_name=_TABLE)
    op.drop_table(_TABLE)
