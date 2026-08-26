"""move use_default_localization from tenants to entities

The "use the tenant's own localization defaults" choice moves from being a
tenant-wide flag to a per-branch one: each branch (entity) now opts in
individually, so different branches of the same tenant can each decide
whether to inherit the tenant's default_language/time_zone/default_currency/
date_format/fiscal_year_start/week_starts_on or set their own — see
create_entity()'s use_default_localization check.

Revision ID: 033
Revises: 032
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column("use_default_localization", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.drop_column("tenants", "use_default_localization")


def downgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("use_default_localization", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.drop_column("entities", "use_default_localization")
