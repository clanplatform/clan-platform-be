"""drop category/level/description from jobcode_basicinfo

These were already excluded from the API schema (schema-only removal earlier
this session, keeping the columns) — now aligning the model/table with the
schema exactly.

Revision ID: 023
Revises: 022
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_jobcode_basicinfo_category_level", table_name="jobcode_basicinfo")
    op.drop_column("jobcode_basicinfo", "category")
    op.drop_column("jobcode_basicinfo", "level")
    op.drop_column("jobcode_basicinfo", "description")


def downgrade() -> None:
    op.add_column("jobcode_basicinfo", sa.Column("category", sa.String(100), nullable=True))
    op.add_column("jobcode_basicinfo", sa.Column("level", sa.String(50), nullable=True))
    op.add_column("jobcode_basicinfo", sa.Column("description", sa.Text(), nullable=True))
    op.create_index("ix_jobcode_basicinfo_category_level", "jobcode_basicinfo", ["category", "level"])
