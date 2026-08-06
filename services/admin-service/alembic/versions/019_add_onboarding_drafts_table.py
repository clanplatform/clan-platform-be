"""add onboarding_drafts table

Auto-saves the onboarding step-form payload when POST /onboarding/ fails
partway (validation error, duplicate client, etc.), keyed by a
client-generated draft_id, so the form can be resumed instead of losing
what was entered.

Revision ID: 019
Revises: 018
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "onboarding_drafts",
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("draft_id"),
    )
    op.create_index("ix_onboarding_drafts_status", "onboarding_drafts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_onboarding_drafts_status", table_name="onboarding_drafts")
    op.drop_table("onboarding_drafts")
