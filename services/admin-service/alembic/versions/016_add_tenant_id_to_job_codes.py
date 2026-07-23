"""
016: Add tenant_id to job_codes (NOT NULL, backfilled from jobcode_basicinfo).

job_codes had no tenant scoping of its own — the tenant was denormalized one
level down on jobcode_basicinfo (1:1 with job_codes). This promotes it onto
the parent row directly.

Backfill source: jobcode_basicinfo.tenant_id via job_code_id. Any job_codes
row with no matching jobcode_basicinfo (and therefore no tenant to backfill
from) fails the migration with an explicit list of offending IDs rather than
letting the later NOT NULL / SET fail with a generic constraint error —
those rows need to be fixed (assign a tenant, or delete if orphaned) before
this migration can proceed.

Run against the master DB and every existing tenant DB; freshly provisioned
tenant DBs pick the column up via create_all.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column(
        "job_codes",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
    )

    op.execute(
        """
        UPDATE job_codes jc
        SET tenant_id = jcb.tenant_id
        FROM jobcode_basicinfo jcb
        WHERE jcb.job_code_id = jc.id
        """
    )

    orphans = conn.execute(
        sa.text("SELECT id, job_code FROM job_codes WHERE tenant_id IS NULL")
    ).fetchall()
    if orphans:
        details = ", ".join(f"{row.id} ({row.job_code})" for row in orphans)
        raise RuntimeError(
            "016_add_tenant_id_to_job_codes: cannot backfill tenant_id for "
            f"{len(orphans)} job_codes row(s) with no matching jobcode_basicinfo: "
            f"{details}. Assign a tenant (insert/repair jobcode_basicinfo, or set "
            "tenant_id manually) or delete the orphaned row(s), then re-run."
        )

    op.alter_column("job_codes", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_job_codes_tenant_id",
        "job_codes",
        "tenants",
        ["tenant_id"],
        ["tenant_id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_job_codes_tenant_id", "job_codes", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_job_codes_tenant_id", table_name="job_codes")
    op.drop_constraint("fk_job_codes_tenant_id", "job_codes", type_="foreignkey")
    op.drop_column("job_codes", "tenant_id")
