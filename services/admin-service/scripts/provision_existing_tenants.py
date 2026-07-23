"""
One-time script: provision a dedicated database for every existing tenant
that does not yet have a tenant_db_name set.

Run from the admin-service directory:
    python scripts/provision_existing_tenants.py

It will:
  1. Read all tenants WHERE tenant_db_name IS NULL from the master DB
  2. Derive a db name from tenant_code  (clan_platform_<slug>)
  3. CREATE DATABASE if it doesn't exist
  4. Create all application tables inside that database
  5. Update the tenants row with the new tenant_db_name
"""

import sys
import os

# Allow imports from the service root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env.local before importing app modules
from dotenv import load_dotenv
env_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "config", "environments", ".env.local"
)
load_dotenv(dotenv_path=env_path, override=False)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.infrastructure.database.tenant_db_manager import TenantDatabaseManager

manager = TenantDatabaseManager()

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


def run():
    db = Session()
    try:
        rows = db.execute(
            text("SELECT tenant_id, tenant_name, tenant_code FROM tenants WHERE tenant_db_name IS NULL")
        ).fetchall()

        if not rows:
            print("No tenants without a tenant_db_name found. Nothing to do.")
            return

        print(f"Found {len(rows)} tenant(s) to provision:\n")

        used_names = set()

        for row in rows:
            tenant_id   = str(row.tenant_id)
            tenant_name = row.tenant_name
            tenant_code = (row.tenant_code or "").strip()

            # Prefer tenant_code; fall back to tenant_id slug on collision or blank
            candidate = TenantDatabaseManager.make_db_name(tenant_code) if tenant_code else None
            if not candidate or candidate in used_names:
                candidate = TenantDatabaseManager.make_db_name(tenant_id)
            db_name = candidate
            used_names.add(db_name)

            print(f"  Tenant: {tenant_name!r}  (id={tenant_id})")
            print(f"    → database name : {db_name}")

            ok = manager.provision(db_name, settings.DATABASE_URL)

            if ok:
                db.execute(
                    text("UPDATE tenants SET tenant_db_name = :db_name WHERE tenant_id = :tid"),
                    {"db_name": db_name, "tid": tenant_id},
                )
                db.commit()
                print(f"    ✓ Provisioned and updated.\n")
            else:
                print(f"    ✗ Provisioning FAILED — check logs above.\n")

        print("Done.")

    except Exception as exc:
        db.rollback()
        print(f"Error: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
