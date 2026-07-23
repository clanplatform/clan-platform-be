"""
011: Add table_permission column to tenants table.

Stores the list of table names allocated in a tenant's dedicated database,
allowing fine-grained control over which tables are provisioned per tenant.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("table_permission", ARRAY(sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "table_permission")
