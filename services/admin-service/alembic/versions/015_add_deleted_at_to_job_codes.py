"""
015: Add deleted_at to job_codes for soft delete with retention.

DELETE on a job code now soft-deletes (active_status=False + deleted_at
stamped) instead of hard-deleting. Rows older than the 30-day retention are
permanently purged opportunistically by the service layer.

Run against the master DB and every existing tenant DB; freshly provisioned
tenant DBs pick the column up via create_all.
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_codes",
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_job_codes_deleted_at", "job_codes", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_job_codes_deleted_at", table_name="job_codes")
    op.drop_column("job_codes", "deleted_at")
