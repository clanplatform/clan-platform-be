"""
012: Add allowed_origins column to usersetup_basic.

Tenant users resolve their application origin from tenants.allowed_origins;
master-DB users (tenant_id NULL) have no tenant row, so this column stores
their allowed origins per user (e.g. post-login redirect target for
platform users).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usersetup_basic",
        sa.Column("allowed_origins", ARRAY(sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usersetup_basic", "allowed_origins")
