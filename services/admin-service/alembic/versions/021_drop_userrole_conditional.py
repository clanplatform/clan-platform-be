"""drop userrole_conditional table

Time-based / IP-based conditional access on roles is not part of the final
Roles screen (no time/IP fields in the UI) — model, schema, and service CRUD
removed; this drops the table itself.

Revision ID: 021
Revises: 020
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("userrole_conditional")


def downgrade() -> None:
    op.create_table(
        "userrole_conditional",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_role_id", UUID(as_uuid=True), nullable=False),
        sa.Column("userrole_permission_id", UUID(as_uuid=True), nullable=False),
        sa.Column("userrole_basic_id", UUID(as_uuid=True), nullable=False),
        sa.Column("enable_time", sa.Boolean(), nullable=False),
        sa.Column("allowtime_start", sa.Time(), nullable=True),
        sa.Column("allowtime_end", sa.Time(), nullable=True),
        sa.Column("allow_days", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("ip_restric", sa.Boolean(), nullable=False),
        sa.Column("aip", sa.String(45), nullable=True),
        sa.Column("bip", sa.String(45), nullable=True),
        sa.Column("enable_restric", sa.Boolean(), nullable=False),
        sa.Column("required_reg", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_role_id"], ["user_role.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["userrole_permission_id"], ["userrole_permission.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["userrole_basic_id"], ["userrole_basic.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
