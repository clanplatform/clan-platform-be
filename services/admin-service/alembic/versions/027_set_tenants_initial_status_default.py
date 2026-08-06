"""set default 'Active' on tenants.initial_status

initial_status is repurposed to hold the account-status step's business
value (Active / Trial / Pending setup) rather than onboarding-process
tracking (in_progress/completed/failed, now dropped — see
create_onboarding()). Default matches the dropdown's default selection.

Revision ID: 027
Revises: 026
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE tenants ALTER COLUMN initial_status SET DEFAULT 'Active'")


def downgrade() -> None:
    op.execute("ALTER TABLE tenants ALTER COLUMN initial_status DROP DEFAULT")
