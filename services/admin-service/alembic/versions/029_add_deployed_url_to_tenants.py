"""add deployed_url to tenants

Onboarding's "Company" step (OnboardingCompany.deployed_url) needs somewhere
to store the URL of the tenant's deployed application instance — a distinct
field from tenants.website (the client's own marketing/company site).

Revision ID: 029
Revises: 028
Create Date: 2026-08-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("deployed_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "deployed_url")
