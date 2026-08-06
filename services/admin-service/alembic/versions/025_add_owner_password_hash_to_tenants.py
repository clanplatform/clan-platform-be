"""add owner_password_hash to tenants

owner_password (accepted on TenantCreate, write-only) is hashed and stored
here — same as onboarding's OnboardingCompany.owner_password, which already
seeds the owner's usersetup_basic.password_hash. This is a denormalized,
bcrypt-hashed convenience copy on the tenant row itself; never the raw
value, never returned by the API.

Revision ID: 025
Revises: 024
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("owner_password_hash", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "owner_password_hash")
