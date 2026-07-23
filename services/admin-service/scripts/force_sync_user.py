"""
Force-sync a single user (master OR tenant DB) into auth-service auth_users.

Why this exists: the app keeps usersetup_basic and auth_users in sync only
through its own endpoints (create user, update user, change-password) and
during login's auto-sync. A row edited directly in Postgres (e.g. via
pgAdmin) is invisible to that mechanism until the user manages to log in —
which they usually can't, because auth_users still holds the stale
password_hash used for authentication. This script closes that gap by
pushing one user's current row straight to auth-service.

The underlying auth-service endpoint (/api/v1/auth/users/sync) is a true
upsert keyed by id/user_setup_id, so this is safe to re-run.

Usage (inside the admin-service container):
    python scripts/force_sync_user.py <email>
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.config import settings
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.tenant_db_manager import tenant_db_manager
from app.user_setup.services.auth_service_sync import AuthServiceSync, AuthServiceSyncError

if len(sys.argv) != 2:
    print(__doc__)
    sys.exit(1)

email = sys.argv[1]

USER_QUERY = text("""
    SELECT id, user_setup_id, username, email, password_hash, firstname,
           lastname, phone_number, status, employee_id, is_password_change,
           can_change_password, tenant_id
    FROM usersetup_basic
    WHERE email = :email
""")


def find_user():
    """Search master DB first, then every provisioned tenant DB."""
    master = SessionLocal()
    try:
        row = master.execute(USER_QUERY, {"email": email}).fetchone()
        if row:
            return row, "master DB"

        tenants = master.execute(
            text("SELECT tenant_name, tenant_db_name FROM tenants WHERE tenant_db_name IS NOT NULL")
        ).fetchall()
    finally:
        master.close()

    for tenant_name, tenant_db_name in tenants:
        try:
            tdb = tenant_db_manager.get_session(tenant_db_name, settings.DATABASE_URL)
            try:
                row = tdb.execute(USER_QUERY, {"email": email}).fetchone()
                if row:
                    return row, f"{tenant_name} ({tenant_db_name})"
            finally:
                tdb.close()
        except Exception as exc:
            print(f"  (skipping {tenant_name} [{tenant_db_name}]: {exc.__class__.__name__})")
            continue
    return None, None


async def main():
    row, source = find_user()
    if not row:
        print(f"NOT FOUND: no usersetup_basic row for {email} in master DB or any tenant DB")
        sys.exit(1)

    print(f"Found {email} in {source}")
    try:
        result = await AuthServiceSync.create_auth_user(
            user_id=row.id,
            user_setup_id=row.user_setup_id,
            username=row.username,
            email=row.email,
            password_hash=row.password_hash,
            firstname=row.firstname,
            lastname=row.lastname,
            phone_number=row.phone_number,
            is_active=(row.status == "active"),
            employee_id=row.employee_id,
            is_password_change=row.is_password_change,
            can_change_password=row.can_change_password,
            tenant_id=row.tenant_id,
        )
        print(f"SYNCED: {result}")
    except AuthServiceSyncError as exc:
        print(f"SYNC FAILED: {exc}")
        sys.exit(1)


asyncio.run(main())
