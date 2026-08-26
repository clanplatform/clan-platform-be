"""add use_default_localization to tenants

Lets the account-status/localization step (OnboardingCompany.
use_default_localization) opt a tenant into having new branches (entities)
inherit its default_language/time_zone/default_currency/date_format/
fiscal_year_start/week_starts_on instead of setting their own per branch —
see create_entity()'s use_default_localization check.

Revision ID: 031
Revises: 030
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("use_default_localization", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "use_default_localization")
