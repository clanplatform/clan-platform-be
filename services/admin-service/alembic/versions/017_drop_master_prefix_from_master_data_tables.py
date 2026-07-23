"""
017: Drop the master_ prefix from master-data table names.

master_countries -> countries, master_states -> states,
master_cities -> cities, master_languages -> languages,
master_locales -> locales.

These are master-DB-only reference tables (not in tenant_db_manager.py's
table list, so they're never replicated into a tenant DB) — this migration
only needs to run against the master DB.

Plain ALTER TABLE RENAME: data, FKs, and existing indexes/constraints carry
over unchanged (Postgres tracks them by OID, not name), so this is a
metadata-only rename with no backfill or data movement. Order doesn't matter
for renames the way it would for CREATE — FKs follow the table by OID.
"""
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

RENAMES = [
    ("master_countries", "countries"),
    ("master_states", "states"),
    ("master_cities", "cities"),
    ("master_languages", "languages"),
    ("master_locales", "locales"),
]


def upgrade() -> None:
    for old_name, new_name in RENAMES:
        op.rename_table(old_name, new_name)


def downgrade() -> None:
    for old_name, new_name in RENAMES:
        op.rename_table(new_name, old_name)
