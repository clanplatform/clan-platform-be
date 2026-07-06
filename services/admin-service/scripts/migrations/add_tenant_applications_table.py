"""
Create the tenant_applications table (whole-application licensing, Tier 2)
in the master DB and every provisioned tenant DB, wherever it's missing.

Uses TenantApplication.__table__.create(checkfirst=True) instead of hand
written DDL so the schema can never drift from app/tenant_applications/models.

Run inside the admin-service container:
    python scripts/migrations/add_tenant_applications_table.py

Safe to re-run.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text

from app.core.config import settings
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.tenant_db_manager import tenant_db_manager
from app.tenants.models.tenants import Tenant                                        # noqa: F401 (FK target)
from app.applications.models.application import Application                          # noqa: F401 (FK target)
from app.tenant_applications.models.tenant_application import TenantApplication


def create_table(engine, label: str) -> None:
    TenantApplication.__table__.create(bind=engine, checkfirst=True)
    print(f"OK: {label}")


master = SessionLocal()
try:
    create_table(master.get_bind(), "master DB (tenant_applications)")

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
            create_table(tdb.get_bind(), f"{tenant_name} ({tenant_db_name})")
        except Exception as exc:
            print(f"FAILED {tenant_name} ({tenant_db_name}): {exc}")
        finally:
            tdb.close()
finally:
    master.close()

print("Done.")
