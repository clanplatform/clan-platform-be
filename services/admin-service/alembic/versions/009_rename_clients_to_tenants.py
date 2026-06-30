"""
009: Rename clients → tenants, client_modules → tenant_modules,
     client_applications → tenant_applications; rename all client_id
     columns to tenant_id across every affected table.

Handles two real-world scenarios safely:

  Path A (fresh DB): old table exists, new one doesn't → rename columns
                     then rename table.
  Path B (hybrid DB): both old and new tables exist because create_all()
                      ran after the model rename, creating the new table
                      while the old one still held data.
                      → copy missing rows old→new, then drop the old table.

Revision ID: 009
Revises: 008
Create Date: 2026-06-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _col(inspector, table, col):
    if table not in inspector.get_table_names():
        return False
    return col in [c["name"] for c in inspector.get_columns(table)]


def _fk_exists(inspector, table, local_cols, ref_table, ref_cols):
    if table not in inspector.get_table_names():
        return False
    for fk in inspector.get_foreign_keys(table):
        if (fk["referred_table"] == ref_table
                and fk["constrained_columns"] == local_cols
                and fk["referred_columns"] == ref_cols):
            return True
    return False


def _rename_idx(old, new):
    """Safe rename: only acts when old exists and new does not."""
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_class WHERE relname = '{old}' AND relkind = 'i')
               AND NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = '{new}' AND relkind = 'i') THEN
                ALTER INDEX {old} RENAME TO {new};
            END IF;
        END $$;
    """)


def _rename_constraint(table, old, new):
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{old}') THEN
                ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new};
            END IF;
        END $$;
    """)


def _drop_all_fks_to(conn, ref_table):
    """Drop every FK constraint in the public schema that references *ref_table*."""
    rows = conn.execute(text("""
        SELECT tc.table_name, tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.constraint_column_usage AS ccu
            ON  ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema    = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name     = :ref
          AND tc.table_schema    = 'public'
    """), {"ref": ref_table}).fetchall()
    for table_name, constraint_name in rows:
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def _copy_old_to_new(conn, old_table, new_table, col_renames, pk_col):
    """
    INSERT INTO new_table ... SELECT ... FROM old_table ON CONFLICT DO NOTHING.
    col_renames: dict of old_col_name → new_col_name for renamed columns.
    Skips old columns that don't have a matching column in new_table.
    """
    ins = inspect(conn)
    old_cols = [c["name"] for c in ins.get_columns(old_table)]
    new_col_set = {c["name"] for c in ins.get_columns(new_table)}

    sel = []  # SELECT list (from old_table)
    ins_list = []  # INSERT list (into new_table)
    for c in old_cols:
        mapped = col_renames.get(c, c)
        if mapped in new_col_set:
            sel.append(c)
            ins_list.append(mapped)

    if not sel:
        return

    sql = (
        f"INSERT INTO {new_table} ({', '.join(ins_list)}) "
        f"SELECT {', '.join(sel)} FROM {old_table} "
        f"ON CONFLICT ({pk_col}) DO NOTHING"
    )
    conn.execute(text(sql))


# ─────────────────────────────────────────────────────────────────────────────
# UPGRADE
# ─────────────────────────────────────────────────────────────────────────────

def upgrade() -> None:
    conn = op.get_bind()
    ins = inspect(conn)
    existing = set(ins.get_table_names())

    clients_exists             = "clients"             in existing
    tenants_exists             = "tenants"             in existing
    client_modules_exists      = "client_modules"      in existing
    tenant_modules_exists      = "tenant_modules"      in existing
    client_applications_exists = "client_applications" in existing
    tenant_applications_exists = "tenant_applications" in existing

    # ── 1. Drop ALL FK constraints that reference clients ────────────────────
    if clients_exists:
        _drop_all_fks_to(conn, "clients")

    # ── 2. clients table ─────────────────────────────────────────────────────
    if clients_exists:
        if tenants_exists:
            # Path B: tenants was already created empty by create_all().
            # Copy any rows from clients that are not yet in tenants, then drop clients.
            _copy_old_to_new(
                conn, "clients", "tenants",
                {"client_id": "tenant_id", "client_name": "tenant_name", "client_code": "tenant_code"},
                pk_col="tenant_id",
            )
            op.drop_table("clients")
        else:
            # Path A: rename columns then rename table.
            if _col(ins, "clients", "client_id"):
                op.alter_column("clients", "client_id",   new_column_name="tenant_id")
            if _col(ins, "clients", "client_name"):
                op.alter_column("clients", "client_name", new_column_name="tenant_name")
            if _col(ins, "clients", "client_code"):
                op.alter_column("clients", "client_code", new_column_name="tenant_code")

            _rename_idx("ix_clients_client_id",       "ix_tenants_tenant_id")
            _rename_idx("ix_clients_allowed_origins",  "ix_tenants_allowed_origins")
            _rename_idx("ix_clients_tenant_id",        "ix_tenants_gateway_tenant_ref")

            _rename_constraint("clients", "uq_clients_tenant_id", "uq_tenants_gateway_tenant_ref")
            _rename_constraint("clients", "clients_pkey",          "tenants_pkey")

            op.rename_table("clients", "tenants")

    # ── 3. client_modules table ───────────────────────────────────────────────
    if client_modules_exists:
        if tenant_modules_exists:
            # Path B: copy missing rows then drop old table.
            _copy_old_to_new(
                conn, "client_modules", "tenant_modules",
                {"client_id": "tenant_id"},
                pk_col="id",
            )
            op.drop_table("client_modules")
        else:
            # Path A: rename.
            if _col(ins, "client_modules", "client_id"):
                op.alter_column("client_modules", "client_id", new_column_name="tenant_id")

            _rename_idx("ix_client_modules_client_id", "ix_tenant_modules_tenant_id")
            _rename_idx("ix_client_modules_module_id", "ix_tenant_modules_module_id")
            _rename_constraint("client_modules", "uq_client_module", "uq_tenant_module")

            op.rename_table("client_modules", "tenant_modules")

    # ── 4. client_applications table ─────────────────────────────────────────
    if client_applications_exists:
        if tenant_applications_exists:
            # Path B: copy then drop.
            _copy_old_to_new(
                conn, "client_applications", "tenant_applications",
                {"client_id": "tenant_id"},
                pk_col="id",
            )
            op.drop_table("client_applications")
        else:
            # Path A: rename.
            if _col(ins, "client_applications", "client_id"):
                op.alter_column("client_applications", "client_id", new_column_name="tenant_id")

            _rename_idx("ix_client_applications_client_id",
                        "ix_tenant_applications_tenant_id")
            _rename_idx("ix_client_applications_application_id",
                        "ix_tenant_applications_application_id")
            _rename_constraint("client_applications", "uq_client_application", "uq_tenant_application")

            op.rename_table("client_applications", "tenant_applications")

    # ── 5. Rename client_id → tenant_id in all dependent tables ──────────────
    # Re-inspect: the table renames above are live on the connection.
    ins = inspect(conn)

    if _col(ins, "entities", "client_id"):
        op.alter_column("entities", "client_id", new_column_name="tenant_id")
        _rename_idx("ix_entities_client_id", "ix_entities_tenant_id")

    if _col(ins, "departments", "client_id"):
        op.alter_column("departments", "client_id", new_column_name="tenant_id")
        _rename_idx("ix_departments_client_id", "ix_departments_tenant_id")

    if _col(ins, "divisions", "client_id"):
        op.alter_column("divisions", "client_id", new_column_name="tenant_id")
        _rename_idx("ix_divisions_client_id", "ix_divisions_tenant_id")

    if _col(ins, "userrole_basic", "client_id"):
        op.alter_column("userrole_basic", "client_id", new_column_name="tenant_id")
        _rename_idx("ix_userrole_basic_client_id", "ix_userrole_basic_tenant_id")
        _rename_constraint("userrole_basic",
                           "uq_userrole_basic_client_role_name",
                           "uq_userrole_basic_tenant_role_name")
        _rename_constraint("userrole_basic",
                           "uq_userrole_basic_client_role_code",
                           "uq_userrole_basic_tenant_role_code")

    if _col(ins, "usersetup_basic", "client_id"):
        op.alter_column("usersetup_basic", "client_id", new_column_name="tenant_id")
        _rename_idx("ix_usersetup_basic_client_id", "ix_usersetup_basic_tenant_id")

    if _col(ins, "usersetup_roles_entity", "assigned_client_id"):
        op.alter_column("usersetup_roles_entity", "assigned_client_id",
                        new_column_name="assigned_tenant_id")
        _rename_idx("ix_usersetup_roles_entity_assigned_client_id",
                    "ix_usersetup_roles_entity_assigned_tenant_id")

    if _col(ins, "jobcode_basicinfo", "client_id"):
        op.alter_column("jobcode_basicinfo", "client_id", new_column_name="tenant_id")
        _rename_idx("ix_jobcode_basicinfo_client_id", "ix_jobcode_basicinfo_tenant_id")

    # ── 6. Recreate FK constraints pointing to tenants.tenant_id ─────────────
    ins2 = inspect(conn)
    existing2 = set(ins2.get_table_names())

    def _add_fk(name, src_table, src_cols, ref_cols, **kw):
        if (src_table in existing2
                and not _fk_exists(ins2, src_table, src_cols, "tenants", ref_cols)):
            op.create_foreign_key(name, src_table, "tenants", src_cols, ref_cols, **kw)

    _add_fk("entities_tenant_id_fkey",
            "entities",    ["tenant_id"], ["tenant_id"])
    _add_fk("departments_tenant_id_fkey",
            "departments", ["tenant_id"], ["tenant_id"])
    _add_fk("divisions_tenant_id_fkey",
            "divisions",   ["tenant_id"], ["tenant_id"])
    _add_fk("tenant_modules_tenant_id_fkey",
            "tenant_modules", ["tenant_id"], ["tenant_id"], ondelete="CASCADE")
    _add_fk("tenant_applications_tenant_id_fkey",
            "tenant_applications", ["tenant_id"], ["tenant_id"], ondelete="CASCADE")
    _add_fk("userrole_basic_tenant_id_fkey",
            "userrole_basic", ["tenant_id"], ["tenant_id"], ondelete="CASCADE")
    _add_fk("usersetup_basic_tenant_id_fkey",
            "usersetup_basic", ["tenant_id"], ["tenant_id"])

    if _col(ins2, "usersetup_roles_entity", "assigned_tenant_id"):
        _add_fk("usersetup_roles_entity_assigned_tenant_id_fkey",
                "usersetup_roles_entity",
                ["assigned_tenant_id"], ["tenant_id"], ondelete="SET NULL")

    if _col(ins2, "jobcode_basicinfo", "tenant_id"):
        _add_fk("jobcode_basicinfo_tenant_id_fkey",
                "jobcode_basicinfo", ["tenant_id"], ["tenant_id"], ondelete="CASCADE")


# ─────────────────────────────────────────────────────────────────────────────
# DOWNGRADE
# ─────────────────────────────────────────────────────────────────────────────

def downgrade() -> None:
    conn = op.get_bind()
    ins = inspect(conn)

    # ── 1. Drop ALL FK constraints that reference tenants ────────────────────
    _drop_all_fks_to(conn, "tenants")

    # ── 2. tenants → clients ─────────────────────────────────────────────────
    if "tenants" in ins.get_table_names():
        if _col(ins, "tenants", "tenant_id"):
            op.alter_column("tenants", "tenant_id",   new_column_name="client_id")
        if _col(ins, "tenants", "tenant_name"):
            op.alter_column("tenants", "tenant_name", new_column_name="client_name")
        if _col(ins, "tenants", "tenant_code"):
            op.alter_column("tenants", "tenant_code", new_column_name="client_code")

        _rename_idx("ix_tenants_tenant_id",         "ix_clients_client_id")
        _rename_idx("ix_tenants_allowed_origins",    "ix_clients_allowed_origins")
        _rename_idx("ix_tenants_gateway_tenant_ref", "ix_clients_tenant_id")

        _rename_constraint("tenants", "uq_tenants_gateway_tenant_ref", "uq_clients_tenant_id")
        _rename_constraint("tenants", "tenants_pkey",                   "clients_pkey")

        op.rename_table("tenants", "clients")

    # ── 3. tenant_modules → client_modules ────────────────────────────────────
    if "tenant_modules" in ins.get_table_names():
        if _col(ins, "tenant_modules", "tenant_id"):
            op.alter_column("tenant_modules", "tenant_id", new_column_name="client_id")

        _rename_idx("ix_tenant_modules_tenant_id", "ix_client_modules_client_id")
        _rename_idx("ix_tenant_modules_module_id", "ix_client_modules_module_id")
        _rename_constraint("tenant_modules", "uq_tenant_module", "uq_client_module")

        op.rename_table("tenant_modules", "client_modules")

    # ── 4. tenant_applications → client_applications ─────────────────────────
    if "tenant_applications" in ins.get_table_names():
        if _col(ins, "tenant_applications", "tenant_id"):
            op.alter_column("tenant_applications", "tenant_id", new_column_name="client_id")

        _rename_idx("ix_tenant_applications_tenant_id",
                    "ix_client_applications_client_id")
        _rename_idx("ix_tenant_applications_application_id",
                    "ix_client_applications_application_id")
        _rename_constraint("tenant_applications", "uq_tenant_application", "uq_client_application")

        op.rename_table("tenant_applications", "client_applications")

    # ── 5. Rename tenant_id → client_id in dependent tables ──────────────────
    ins = inspect(conn)

    if _col(ins, "entities", "tenant_id"):
        op.alter_column("entities", "tenant_id", new_column_name="client_id")
        _rename_idx("ix_entities_tenant_id", "ix_entities_client_id")

    if _col(ins, "departments", "tenant_id"):
        op.alter_column("departments", "tenant_id", new_column_name="client_id")
        _rename_idx("ix_departments_tenant_id", "ix_departments_client_id")

    if _col(ins, "divisions", "tenant_id"):
        op.alter_column("divisions", "tenant_id", new_column_name="client_id")
        _rename_idx("ix_divisions_tenant_id", "ix_divisions_client_id")

    if _col(ins, "userrole_basic", "tenant_id"):
        op.alter_column("userrole_basic", "tenant_id", new_column_name="client_id")
        _rename_idx("ix_userrole_basic_tenant_id", "ix_userrole_basic_client_id")
        _rename_constraint("userrole_basic",
                           "uq_userrole_basic_tenant_role_name",
                           "uq_userrole_basic_client_role_name")
        _rename_constraint("userrole_basic",
                           "uq_userrole_basic_tenant_role_code",
                           "uq_userrole_basic_client_role_code")

    if _col(ins, "usersetup_basic", "tenant_id"):
        op.alter_column("usersetup_basic", "tenant_id", new_column_name="client_id")
        _rename_idx("ix_usersetup_basic_tenant_id", "ix_usersetup_basic_client_id")

    if _col(ins, "usersetup_roles_entity", "assigned_tenant_id"):
        op.alter_column("usersetup_roles_entity", "assigned_tenant_id",
                        new_column_name="assigned_client_id")
        _rename_idx("ix_usersetup_roles_entity_assigned_tenant_id",
                    "ix_usersetup_roles_entity_assigned_client_id")

    if _col(ins, "jobcode_basicinfo", "tenant_id"):
        op.alter_column("jobcode_basicinfo", "tenant_id", new_column_name="client_id")
        _rename_idx("ix_jobcode_basicinfo_tenant_id", "ix_jobcode_basicinfo_client_id")

    # ── 6. Recreate old FK constraints pointing back to clients.client_id ─────
    ins2 = inspect(conn)
    existing2 = set(ins2.get_table_names())

    def _add_fk_back(name, src_table, src_cols, ref_cols, **kw):
        if (src_table in existing2
                and not _fk_exists(ins2, src_table, src_cols, "clients", ref_cols)):
            op.create_foreign_key(name, src_table, "clients", src_cols, ref_cols, **kw)

    _add_fk_back("entities_client_id_fkey",
                 "entities",    ["client_id"], ["client_id"])
    _add_fk_back("departments_client_id_fkey",
                 "departments", ["client_id"], ["client_id"])
    _add_fk_back("divisions_client_id_fkey",
                 "divisions",   ["client_id"], ["client_id"])
    _add_fk_back("client_modules_client_id_fkey",
                 "client_modules", ["client_id"], ["client_id"], ondelete="CASCADE")
    _add_fk_back("client_applications_client_id_fkey",
                 "client_applications", ["client_id"], ["client_id"], ondelete="CASCADE")
    _add_fk_back("userrole_basic_client_id_fkey",
                 "userrole_basic", ["client_id"], ["client_id"], ondelete="CASCADE")
    _add_fk_back("usersetup_basic_client_id_fkey",
                 "usersetup_basic", ["client_id"], ["client_id"])

    if _col(ins2, "usersetup_roles_entity", "assigned_client_id"):
        _add_fk_back("usersetup_roles_entity_assigned_client_id_fkey",
                     "usersetup_roles_entity",
                     ["assigned_client_id"], ["client_id"], ondelete="SET NULL")

    if _col(ins2, "jobcode_basicinfo", "client_id"):
        _add_fk_back("jobcode_basicinfo_client_id_fkey",
                     "jobcode_basicinfo", ["client_id"], ["client_id"], ondelete="CASCADE")
