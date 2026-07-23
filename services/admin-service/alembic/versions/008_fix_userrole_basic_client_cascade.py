"""
008: Fix userrole_basic.client_id FK — SET NULL → CASCADE

Previously, when a Client was deleted the client_id on all its roles was
silently set to NULL, creating orphaned "global" roles that belonged to no
one. This migration changes the FK to CASCADE so that deleting a client
also deletes its roles, preventing orphaned permission records.

Note: system_role=True roles should use client_id=NULL intentionally;
those are unaffected by this change because they have no client FK row
to cascade from.

Revision ID: 008
Revises: 007
Create Date: 2026-06-29
"""

from alembic import op


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old SET NULL constraint and add CASCADE
    op.drop_constraint(
        "userrole_basic_client_id_fkey",
        "userrole_basic",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "userrole_basic_client_id_fkey",
        "userrole_basic",
        "clients",
        ["client_id"],
        ["client_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "userrole_basic_client_id_fkey",
        "userrole_basic",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "userrole_basic_client_id_fkey",
        "userrole_basic",
        "clients",
        ["client_id"],
        ["client_id"],
        ondelete="SET NULL",
    )
