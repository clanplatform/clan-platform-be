"""drop requirements/education_level/certifications/performance_metrics from jobcode_skills

These were already excluded from the API schema (schema-only removal earlier
this session, keeping the columns) — now aligning the model/table with the
schema exactly (only key_responsibilities/required_skills remain).

Revision ID: 024
Revises: 023
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_jobcode_skills_education_level", table_name="jobcode_skills")
    op.drop_column("jobcode_skills", "requirements")
    op.drop_column("jobcode_skills", "education_level")
    op.drop_column("jobcode_skills", "certifications")
    op.drop_column("jobcode_skills", "performance_metrics")


def downgrade() -> None:
    op.add_column("jobcode_skills", sa.Column("requirements", sa.Text(), nullable=True))
    op.add_column("jobcode_skills", sa.Column("education_level", sa.String(100), nullable=True))
    op.add_column("jobcode_skills", sa.Column("certifications", sa.Text(), nullable=True))
    op.add_column("jobcode_skills", sa.Column("performance_metrics", sa.Text(), nullable=True))
    op.create_index("ix_jobcode_skills_education_level", "jobcode_skills", ["education_level"])
