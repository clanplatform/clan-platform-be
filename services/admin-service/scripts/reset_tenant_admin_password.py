"""
Reset a tenant-admin's password to a fresh temp password.

Targets the seeded admin (email = tenants.contact_email) in each given
tenant DB, sets a new temp password, and re-enables the first-login
password-change flow (is_password_change=false, can_change_password=true).

Usage (inside the admin-service container):
    python scripts/reset_tenant_admin_password.py <tenant_db_name> [<tenant_db_name> ...]

Prints the new temp password for each tenant.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.config import settings
from app.core.security import get_password_hash
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.tenant_db_manager import tenant_db_manager
from app.api.v1.routes.org_structure.tenants import _generate_temp_password

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

master = SessionLocal()
try:
    for db_name in sys.argv[1:]:
        row = master.execute(
            text("SELECT tenant_name, contact_email FROM tenants WHERE tenant_db_name = :n"),
            {"n": db_name},
        ).fetchone()
        if not row:
            print(f"SKIP {db_name}: no tenant with this tenant_db_name")
            continue

        temp_password = _generate_temp_password()
        tdb = tenant_db_manager.get_session(db_name, settings.DATABASE_URL)
        try:
            result = tdb.execute(
                text(
                    "UPDATE usersetup_basic "
                    "SET password_hash = :h, is_password_change = false, "
                    "    can_change_password = true "
                    "WHERE email = :email"
                ),
                {"h": get_password_hash(temp_password), "email": row.contact_email},
            )
            tdb.commit()
            if result.rowcount:
                print(f"{row.tenant_name} ({db_name})")
                print(f"    login email:   {row.contact_email}")
                print(f"    temp password: {temp_password}")
            else:
                print(f"SKIP {db_name}: no user with email {row.contact_email}")
        finally:
            tdb.close()
finally:
    master.close()
