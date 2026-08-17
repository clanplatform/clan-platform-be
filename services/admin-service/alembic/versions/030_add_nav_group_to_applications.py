"""add nav_group to applications

Applications need to be grouped in the navigation UI under one of three
buckets - 'tools', 'apps', or 'store' - so the frontend can render separate
sections instead of a single flat list.

Revision ID: 030
Revises: 029
Create Date: 2026-08-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column("nav_group", sa.String(20), nullable=True, server_default="apps"),
    )
    op.create_check_constraint(
        "ck_applications_nav_group",
        "applications",
        "nav_group IN ('tools', 'apps', 'store')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_applications_nav_group", "applications", type_="check")
    op.drop_column("applications", "nav_group")
