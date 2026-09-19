"""create user_invitations table

Invitation-email tracking for user_setup users (POST /api/v1/user_setup/
{user_id}/send-invitation and the bulk/selected variants). One row per
invitation attempt (a resend adds a new row rather than overwriting the old
one, keeping a full history per user). user_id references user_setup.id
(the parent table's own PK, not usersetup_basic.id). token_hash stores a
SHA-256 digest only — the raw token is never persisted.

Lives in every tenant DB (created fresh via create_all() at provisioning
time, so new tenant DBs get it automatically) and in the master DB — any
already-provisioned tenant DB needs the same table added directly via
scripts/migrations/create_user_invitations_table.sql.

Defensive: the live master DB drifts from the alembic chain (tables rebuilt
via create_all()), so the create is guarded by an existence check.

Revision ID: 042
Revises: 041
Create Date: 2026-09-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_invitations" in inspector.get_table_names():
        return

    op.create_table(
        "user_invitations",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_setup.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_user_invitations_token_hash"),
    )
    op.create_index("ix_user_invitations_user_id", "user_invitations", ["user_id"])
    op.create_index("ix_user_invitations_tenant_id", "user_invitations", ["tenant_id"])
    op.create_index("ix_user_invitations_status", "user_invitations", ["status"])
    op.create_index("ix_user_invitations_token_hash", "user_invitations", ["token_hash"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_invitations" not in inspector.get_table_names():
        return
    op.drop_index("ix_user_invitations_token_hash", table_name="user_invitations")
    op.drop_index("ix_user_invitations_status", table_name="user_invitations")
    op.drop_index("ix_user_invitations_tenant_id", table_name="user_invitations")
    op.drop_index("ix_user_invitations_user_id", table_name="user_invitations")
    op.drop_table("user_invitations")
