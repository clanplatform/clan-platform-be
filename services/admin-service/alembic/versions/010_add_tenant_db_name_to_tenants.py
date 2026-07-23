"""
010: Add tenant_db_name column to tenants table.

Each tenant gets a dedicated PostgreSQL database.
This column stores its name (e.g. clan_platform_rajeshnero).
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("tenant_db_name", sa.String(150), nullable=True, unique=True),
    )
    op.create_index(
        "ix_tenants_tenant_db_name", "tenants", ["tenant_db_name"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_tenants_tenant_db_name", table_name="tenants")
    op.drop_column("tenants", "tenant_db_name")
