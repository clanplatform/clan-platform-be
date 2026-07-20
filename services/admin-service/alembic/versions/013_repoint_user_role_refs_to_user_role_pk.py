"""
013: Repoint user role references from userrole_basic.id to user_role.id.

usersetup_roles_entity.assigned_roles and usersetup_basic.manage_roles stored
userrole_basic.id values. They now store user_role.id (the parent role PK),
which is what userrole_permission.user_role_id already keys on.

userrole_basic.user_role_id is UNIQUE, so the mapping is 1:1 and reversible.

Both directions remap element-by-element with a LEFT JOIN + COALESCE: an element
that resolves is rewritten, one that does not is left untouched. That keeps the
migration idempotent (re-running finds nothing to map and is a no-op) and avoids
silently dropping IDs that point at roles which no longer exist.
"""
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


# basic.id -> basic.user_role_id
_TO_PARENT_PK = """
UPDATE {table} u
SET {column} = (
    SELECT array_agg(COALESCE(b.user_role_id, t.old_id) ORDER BY t.ord)
    FROM unnest(u.{column}) WITH ORDINALITY AS t(old_id, ord)
    LEFT JOIN userrole_basic b ON b.id = t.old_id
)
WHERE u.{column} IS NOT NULL
  AND array_length(u.{column}, 1) > 0;
"""

# basic.user_role_id -> basic.id
_TO_BASIC_PK = """
UPDATE {table} u
SET {column} = (
    SELECT array_agg(COALESCE(b.id, t.new_id) ORDER BY t.ord)
    FROM unnest(u.{column}) WITH ORDINALITY AS t(new_id, ord)
    LEFT JOIN userrole_basic b ON b.user_role_id = t.new_id
)
WHERE u.{column} IS NOT NULL
  AND array_length(u.{column}, 1) > 0;
"""

_TARGETS = (
    ("usersetup_roles_entity", "assigned_roles"),
    ("usersetup_basic", "manage_roles"),
)


def upgrade() -> None:
    for table, column in _TARGETS:
        op.execute(_TO_PARENT_PK.format(table=table, column=column))


def downgrade() -> None:
    for table, column in _TARGETS:
        op.execute(_TO_BASIC_PK.format(table=table, column=column))
