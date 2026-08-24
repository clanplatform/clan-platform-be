"""
Reset a tenant-admin's password to a fresh temp password.

Targets the seeded admin (email = tenants.owner_email, falling back to
contact_email only when no owner_email is set — same precedence as
_seed_tenant_db / auth-service's first-login tenant resolution) in each
given tenant DB, sets a new temp password, and re-enables the first-login
password-change flow (is_password_change=false, can_change_password=true).
Also updates tenants.owner_password_hash (master DB) to the same hash, so
the two stay in sync exactly like every other seeding path in this service.

Usage (inside the admin-service container):
    python scripts/reset_tenant_admin_password.py <tenant_db_name> [<tenant_db_name> ...]

Prints the new temp password for each tenant.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.config import settings
from app.core.security import get_password_hash, generate_temp_password as _generate_temp_password
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.tenant_db_manager import tenant_db_manager

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

master = SessionLocal()
try:
    # Plain SQL (not the Tenant ORM class) — tenant_db_name is a computed
    # property (derived from tenant_code via tenant_db_manager.make_db_name),
    # not a real column, so it can't be filtered in SQL either way; querying
    # the ORM class here would additionally require importing every related
    # model just to satisfy SQLAlchemy's mapper configuration (see
    # reprovision_tenant_dbs.py), which this small script has no other need for.
    rows = master.execute(
        text("SELECT tenant_id, tenant_name, tenant_code, owner_email, contact_email FROM tenants")
    ).fetchall()
    tenants_by_db_name = {
        tenant_db_manager.make_db_name(row.tenant_code): row
        for row in rows if row.tenant_code
    }

    for db_name in sys.argv[1:]:
        tenant = tenants_by_db_name.get(db_name)
        if not tenant:
            print(f"SKIP {db_name}: no tenant with this tenant_db_name")
            continue

        login_email = tenant.owner_email or tenant.contact_email
        temp_password = _generate_temp_password()
        new_hash = get_password_hash(temp_password)

        tdb = tenant_db_manager.get_session(db_name, settings.DATABASE_URL)
        try:
            result = tdb.execute(
                text(
                    "UPDATE usersetup_basic "
                    "SET password_hash = :h, is_password_change = false, "
                    "    can_change_password = true "
                    "WHERE email = :email"
                ),
                {"h": new_hash, "email": login_email},
            )
            tdb.commit()
            if result.rowcount:
                master.execute(
                    text("UPDATE tenants SET owner_password_hash = :h WHERE tenant_id = :tid"),
                    {"h": new_hash, "tid": str(tenant.tenant_id)},
                )
                master.commit()
                print(f"{tenant.tenant_name} ({db_name})")
                print(f"    login email:   {login_email}")
                print(f"    temp password: {temp_password}")
            else:
                print(f"SKIP {db_name}: no user with email {login_email}")
        finally:
            tdb.close()
finally:
    master.close()
