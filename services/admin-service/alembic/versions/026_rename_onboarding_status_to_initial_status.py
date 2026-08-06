"""rename tenants.onboarding_status to initial_status

Matches the "Initial status" label/field used across the tenants and
onboarding schemas.

Revision ID: 026
Revises: 025
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("tenants", "onboarding_status", new_column_name="initial_status")


def downgrade() -> None:
    op.alter_column("tenants", "initial_status", new_column_name="onboarding_status")
