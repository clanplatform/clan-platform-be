"""add localization columns to entities

Branches (entities) need default_language/default_currency/fiscal_year_start/
week_starts_on alongside the existing time_zone/date_format, so a branch can
either set its own locale or inherit the tenant's when
tenants.use_default_localization=true — see create_entity()'s
use_default_localization check.

entities also lives in every tenant DB (created fresh via create_all() at
provisioning time, so new tenants get these columns automatically) — any
already-provisioned tenant DB needs this same ALTER run against it directly,
e.g. via scripts/migrations/add_entity_localization_columns.sql.

Revision ID: 032
Revises: 031
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("entities", sa.Column("default_language", sa.String(50), nullable=True))
    op.add_column("entities", sa.Column("default_currency", sa.String(10), nullable=True))
    op.add_column("entities", sa.Column("fiscal_year_start", sa.String(20), nullable=True))
    op.add_column("entities", sa.Column("week_starts_on", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("entities", "week_starts_on")
    op.drop_column("entities", "fiscal_year_start")
    op.drop_column("entities", "default_currency")
    op.drop_column("entities", "default_language")
