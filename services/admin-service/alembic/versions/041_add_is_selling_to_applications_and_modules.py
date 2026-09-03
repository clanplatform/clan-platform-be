"""add is_selling to applications and modules

Applications and modules need an ``is_selling`` flag so the store / navigation
UI can tell which ones are offered for sale, independently of ``is_active``
(licensed / enabled) and ``nav_group`` (which section they render in).

Both tables also live in every tenant DB (created fresh via create_all() at
provisioning time, so new tenant DBs get the column automatically) — any
already-provisioned tenant DB needs the same ALTER run against it directly,
via scripts/migrations/add_is_selling_to_applications_modules.sql.

Defensive: the live master DB drifts from the alembic chain (tables rebuilt
via create_all), so every step is guarded by an existence check.

Revision ID: 041
Revises: 040
Create Date: 2026-09-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(inspector, table):
    return {c["name"] for c in inspector.get_columns(table)} if table in inspector.get_table_names() else set()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table in ("applications", "modules"):
        if table in insp.get_table_names() and "is_selling" not in _cols(insp, table):
            op.add_column(
                table,
                sa.Column(
                    "is_selling",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table in ("modules", "applications"):
        if table in insp.get_table_names() and "is_selling" in _cols(insp, table):
            op.drop_column(table, "is_selling")
