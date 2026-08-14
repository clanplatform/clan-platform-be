"""
One-off backfill: copy the full tenant profile from the master DB into each
tenant database's own tenants table (previously only 7 columns were seeded).

Run inside the admin-service container:  python scripts/backfill_tenant_copy.py
Safe to re-run — it updates existing rows and inserts missing ones.
"""
import sys
import os

# Add the admin-service root to the path so `app.*` imports resolve
# regardless of the directory the script is launched from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.tenant_db_manager import tenant_db_manager
from app.tenants.models.tenants import Tenant

# Register every model so SQLAlchemy can resolve Tenant's relationships
from app.domains.models.domain import Domain                                        # noqa: F401
from app.applications.models.application import Application                          # noqa: F401
from app.modules.models.module import Module                                         # noqa: F401
from app.menus.models.menu import Menu                                               # noqa: F401
from app.forms.models.forms import Form                                              # noqa: F401
from app.entities.models.entity import Entity                                        # noqa: F401
from app.departments.models.departments import Department                             # noqa: F401
from app.divisions.models.divisions import Division                                   # noqa: F401
from app.job_codes.models.job_codes import JobCode                                   # noqa: F401
from app.user_role.models.user_role import (                                         # noqa: F401
    UserRoleMain, UserRoleBasic, UserRolePermission
)
from app.user_setup.models.user_setup import (                                       # noqa: F401
    UserSetup, UserSetupBasic, UserSetupPreference
)
from app.buttons.models.button import Button                                         # noqa: F401
from app.tenant_modules.models.tenant_module import TenantModule                     # noqa: F401

COLUMNS = [c.name for c in Tenant.__table__.columns]


def ensure_tenant_table_columns(tdb) -> None:
    """Add any tenants-table columns the tenant DB is missing (schema drift)."""
    from sqlalchemy import text

    engine = tdb.get_bind()
    existing = {
        r[0]
        for r in tdb.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'tenants'"
        ))
    }
    for col in Tenant.__table__.columns:
        if col.name not in existing:
            col_type = col.type.compile(dialect=engine.dialect)
            tdb.execute(text(
                f'ALTER TABLE tenants ADD COLUMN IF NOT EXISTS "{col.name}" {col_type}'
            ))
            print(f"  added missing column {col.name} ({col_type})")
    tdb.commit()


master = SessionLocal()
# tenant_db_name is a computed @property (derived from tenant_code), not a
# mapped column, so the SQL-level filter has to go through tenant_code.
tenants = [
    t for t in master.query(Tenant).filter(Tenant.tenant_code.isnot(None)).all()
    if t.tenant_db_name
]
print(f"Found {len(tenants)} tenants with a dedicated DB")

for t in tenants:
    try:
        tdb = tenant_db_manager.get_session(t.tenant_db_name, settings.DATABASE_URL)
    except Exception as exc:
        print(f"SKIP {t.tenant_name} ({t.tenant_db_name}): cannot connect — {exc}")
        continue
    try:
        ensure_tenant_table_columns(tdb)
        row = tdb.query(Tenant).filter(Tenant.tenant_id == t.tenant_id).first()
        if row is None:
            tdb.add(Tenant(**{c: getattr(t, c) for c in COLUMNS}))
            action = "INSERTED"
        else:
            for c in COLUMNS:
                if c != "tenant_id":
                    setattr(row, c, getattr(t, c))
            action = "UPDATED"
        tdb.commit()
        print(f"{action}: {t.tenant_name} -> {t.tenant_db_name}")
    except Exception as exc:
        tdb.rollback()
        print(f"FAILED {t.tenant_name} ({t.tenant_db_name}): {exc}")
    finally:
        tdb.close()

master.close()
print("Done.")
