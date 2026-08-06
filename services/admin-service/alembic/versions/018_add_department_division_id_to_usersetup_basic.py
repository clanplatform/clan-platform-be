"""add department_id/division_id arrays to usersetup_basic

Same shape as entity_id: a user can be assigned specific departments/
divisions, used to resolve a role's access_scope of "department" or
"division" (see user_role's ACCESS_SCOPE_VALUES).

Revision ID: 018
Revises: 017
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usersetup_basic",
        sa.Column("department_id", sa.ARRAY(UUID(as_uuid=True)), nullable=True),
    )
    op.add_column(
        "usersetup_basic",
        sa.Column("division_id", sa.ARRAY(UUID(as_uuid=True)), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usersetup_basic", "division_id")
    op.drop_column("usersetup_basic", "department_id")
