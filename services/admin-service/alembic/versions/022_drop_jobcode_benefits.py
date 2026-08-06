"""drop jobcode_benefits table

Benefits is not part of the final Job codes screen (no benefits section in
the UI) — model, schema, and service references removed; this drops the
table itself.

Revision ID: 022
Revises: 021
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("jobcode_benefits")


def downgrade() -> None:
    op.create_table(
        "jobcode_benefits",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_code_id", UUID(as_uuid=True), nullable=False),
        sa.Column("benefits_package", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["job_code_id"], ["job_codes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_code_id"),
    )
