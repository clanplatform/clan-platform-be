"""add job_code_id to usersetup_basic

job_code_id references job_codes.id. department_id/division_id (added in
018) are no longer accepted/returned on the schema — they're now derived
server-side from this job code's jobcode_basicinfo row.

Revision ID: 020
Revises: 019
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usersetup_basic",
        sa.Column("job_code_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_usersetup_basic_job_code_id",
        "usersetup_basic", "job_codes",
        ["job_code_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_usersetup_basic_job_code_id", "usersetup_basic", type_="foreignkey")
    op.drop_column("usersetup_basic", "job_code_id")
