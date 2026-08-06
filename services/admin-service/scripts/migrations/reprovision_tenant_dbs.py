"""
Repair script: provision every tenant database recorded in the master
tenants table that does not actually exist (or is missing its schema),
then seed the tenant row and the initial tenant-admin user.

For each tenant with a tenant_db_name it:
  1. CREATE DATABASE + tables (honours table_permission) — skipped if present
  2. Copies the full tenant profile row into the tenant DB
  3. Seeds the tenant-admin user (can_change_password=True,
     is_password_change=False → forced password change on first login)
     with a NEW temp password, printed to the console

No invitation emails are sent — hand the printed temp passwords out manually
or re-create the tenant to trigger the normal email flow.

Run inside the admin-service container:
    python scripts/migrations/reprovision_tenant_dbs.py

Safe to re-run — existing DBs/rows/users are left untouched.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text

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
    UserSetup, UserSetupBasic, UserSetupRolesEntity, UserSetupPreference
)
from app.user_role_form_permission.models.user_role_form_permission import (         # noqa: F401
    RoleFormPermission
)
from app.buttons.models.button import Button                                         # noqa: F401
from app.tenant_modules.models.tenant_module import TenantModule                     # noqa: F401
from app.tenant_applications.models.tenant_application import TenantApplication      # noqa: F401

from app.api.v1.routes.org_structure.tenants import _seed_tenant_db
from app.core.security import generate_temp_password as _generate_temp_password

# Tables the login/seeding flow depends on — always provisioned even when
# the tenant's table_permission list doesn't mention them.
REQUIRED_TABLES = ["tenants", "user_setup", "usersetup_basic", "audit_logs"]

master = SessionLocal()
tenants = master.query(Tenant).filter(Tenant.tenant_db_name.isnot(None)).all()
print(f"Found {len(tenants)} tenants with a tenant_db_name\n")

results = []
for t in tenants:
    label = f"{t.tenant_name} ({t.tenant_db_name})"
    try:
        allowed = t.table_permission or None
        if allowed:
            allowed = list({*allowed, *REQUIRED_TABLES})
        ok = tenant_db_manager.provision(
            t.tenant_db_name,
            settings.DATABASE_URL,
            allowed,
        )
        if not ok:
            results.append((label, "PROVISION FAILED", None))
            continue

        tdb = tenant_db_manager.get_session(t.tenant_db_name, settings.DATABASE_URL)
        try:
            seeded = tdb.execute(
                text("SELECT 1 FROM usersetup_basic WHERE tenant_id = :tid LIMIT 1"),
                {"tid": str(t.tenant_id)},
            ).fetchone()
            if seeded:
                results.append((label, "OK (already seeded)", None))
                continue

            temp_password = _generate_temp_password()
            _seed_tenant_db(tdb, t, temp_password)
            results.append((label, "PROVISIONED + SEEDED", temp_password))
        finally:
            tdb.close()
    except Exception as exc:
        results.append((label, f"FAILED: {exc}", None))

print("\n===== SUMMARY =====")
for label, status_msg, temp_password in results:
    line = f"{status_msg:24} {label}"
    if temp_password:
        line += f"\n{'':24} login email: see tenants.contact_email — temp password: {temp_password}"
    print(line)

master.close()
print("\nDone.")
