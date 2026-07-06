"""
One-off backfill: add the can_change_password column to usersetup_basic in
the master DB and in every provisioned tenant database.

  true  -> forced password change on first login (tenant-admin style)
  false -> user logs straight in and is redirected to the tenant app

Existing rows get DEFAULT true, which preserves the pre-column behavior
(forced change until the password is changed once).

Run inside the admin-service container:
    python scripts/migrations/backfill_can_change_password.py

Safe to re-run — uses ADD COLUMN IF NOT EXISTS.

NOTE: the auth-service database (auth_users table) belongs to
clan-identity-be and is NOT touched here. Run there separately:
    ALTER TABLE auth_users
        ADD COLUMN IF NOT EXISTS can_change_password BOOLEAN NOT NULL DEFAULT true;
"""
import sys
from pathlib import Path

# Allow running from the service root or the migrations folder
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import text

from app.core.config import settings
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.tenant_db_manager import tenant_db_manager

ALTER_SQL = text(
    "ALTER TABLE usersetup_basic "
    "ADD COLUMN IF NOT EXISTS can_change_password BOOLEAN NOT NULL DEFAULT true"
)


def add_column(db, label: str) -> None:
    db.execute(ALTER_SQL)
    db.commit()
    print(f"OK: {label}")


master = SessionLocal()
try:
    add_column(master, "master DB (usersetup_basic)")

    rows = master.execute(text(
        "SELECT tenant_name, tenant_db_name FROM tenants "
        "WHERE tenant_db_name IS NOT NULL"
    )).fetchall()
    print(f"Found {len(rows)} tenants with a dedicated DB")

    for tenant_name, tenant_db_name in rows:
        try:
            tdb = tenant_db_manager.get_session(tenant_db_name, settings.DATABASE_URL)
        except Exception as exc:
            print(f"SKIP {tenant_name} ({tenant_db_name}): cannot connect — {exc}")
            continue
        try:
            add_column(tdb, f"{tenant_name} ({tenant_db_name})")
        except Exception as exc:
            tdb.rollback()
            print(f"FAILED {tenant_name} ({tenant_db_name}): {exc}")
        finally:
            tdb.close()
finally:
    master.close()

print("Done. Remember to also ALTER auth_users in the auth-service DB.")
