"""create entities_healthcare table

The branch form's "Healthcare facility & compliance" section — one row per
branch (entities row), holding the uploaded compliance-document references
plus the facility / HIPAA fields. Carried in the branch payload as the nested
``entities_healthcare`` list (see EntityBase / OnboardingBranch), upserted
onto the single unique ``entity_id`` row.

entities_healthcare also lives in every tenant DB (created fresh via
create_all() at provisioning time, so new tenants get it automatically) — any
already-provisioned tenant DB needs
scripts/migrations/create_entities_healthcare_table.sql run against it directly.

Defensive: the live master DB schema is kept in sync via create_all() from the
models, so this table may already exist before `alembic upgrade` runs — the
create is guarded by an existence check.

Revision ID: 034
Revises: 033
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "entities_healthcare" in inspector.get_table_names():
        return

    op.create_table(
        "entities_healthcare",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        # Healthcare compliance documents (file references / URLs)
        sa.Column("facility_license_doc", sa.String(500), nullable=True),
        sa.Column("accreditation_certificate_doc", sa.String(500), nullable=True),
        sa.Column("dea_registration_doc", sa.String(500), nullable=True),
        sa.Column("hipaa_compliance_attestation_doc", sa.String(500), nullable=True),
        # Healthcare facility & compliance
        sa.Column("facility_type", sa.String(100), nullable=True),
        sa.Column("npi_number", sa.String(50), nullable=True),
        sa.Column("facility_license_no", sa.String(100), nullable=True),
        sa.Column("license_expiry", sa.Date(), nullable=True),
        sa.Column("accreditation", sa.String(100), nullable=True),
        sa.Column("bed_capacity", sa.Integer(), nullable=True),
        sa.Column("licensed_practitioners", sa.Integer(), nullable=True),
        sa.Column("ehr_emr_system", sa.String(150), nullable=True),
        sa.Column("hipaa_privacy_officer", sa.String(200), nullable=True),
        sa.Column("officer_email", sa.String(255), nullable=True),
        sa.Column("telehealth_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("handles_phi", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.entity_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", name="uq_entities_healthcare_entity"),
    )
    op.create_index("ix_entities_healthcare_id", "entities_healthcare", ["id"])
    op.create_index("ix_entities_healthcare_entity_id", "entities_healthcare", ["entity_id"])
    op.create_index("ix_entities_healthcare_tenant_id", "entities_healthcare", ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "entities_healthcare" not in inspector.get_table_names():
        return
    op.drop_index("ix_entities_healthcare_tenant_id", table_name="entities_healthcare")
    op.drop_index("ix_entities_healthcare_entity_id", table_name="entities_healthcare")
    op.drop_index("ix_entities_healthcare_id", table_name="entities_healthcare")
    op.drop_table("entities_healthcare")
