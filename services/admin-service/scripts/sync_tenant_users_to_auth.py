"""
Backfill every TENANT user into the auth-service auth_users directory.

Why this exists
---------------
Onboarding (POST /onboarding/?finalize=true) creates each user in that
tenant's own database (clan_platform_<code>), with usersetup_basic.tenant_id
set. The identity service's login flow, however, resolves a login by looking
the email up in auth_users FIRST — and only a tenant's OWNER (owner_email) is
reachable any other way. So a regular tenant user that was never synced to
auth_users gets "Incorrect email or password" (HTTP 401) even with the right
credentials. Onboarding only started eager-syncing users on 2026-09-04
(commit 4dd9aa2); anything onboarded before that, or by a deploy without the
fix, needs this backfill.

sync_existing_users.py is NOT a substitute — it only reads the MASTER
usersetup_basic, so it never sees tenant users, and it doesn't pass tenant_id
to the sync (so login still can't route them).

What it does
------------
For every active tenant (or one, with --tenant CODE) it connects to that
tenant's DB, reads usersetup_basic, and calls the same
AuthServiceSync.create_auth_user the direct user-create path uses — with
tenant_id, user_setup_id, is_password_change and can_change_password included.
The auth-service upserts (create if new; a row already there is left alone /
reported). Safe to re-run.

Usage
-----
    # dry run — list what would be synced
    python -B scripts/sync_tenant_users_to_auth.py --all --dry-run

    # backfill every active tenant
    python -B scripts/sync_tenant_users_to_auth.py --all

    # just one tenant
    python -B scripts/sync_tenant_users_to_auth.py --tenant NST001

Requires IDENTITY_SERVICE_URL to point at the identity service that owns the
auth_users table (e.g. https://clan-identity-be.onrender.com), and
DATABASE_URL / POSTGRES_* to point at the same Postgres the tenants live in.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.config import settings
from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.tenant_db_manager import tenant_db_manager
from app.user_setup.services.auth_service_sync import AuthServiceSync, AuthServiceSyncError

# Raw SQL, not the ORM — this runs against per-tenant DBs and we don't want to
# pull in every model just to satisfy UserSetupBasic's relationship mappers
# (same approach as scripts/force_sync_user.py).
_USER_SQL = text(
    """
    SELECT id, user_setup_id, username, email, password_hash, firstname,
           lastname, phone_number, status, employee_id, is_password_change,
           can_change_password, tenant_id
    FROM usersetup_basic
    ORDER BY created_at
    """
)


def _active_tenants(tenant_code: str | None):
    """(tenant_id, tenant_code) for the active tenants to process."""
    master = SessionLocal()
    try:
        sql = "SELECT tenant_id, tenant_code FROM tenants WHERE is_active = true AND tenant_code IS NOT NULL"
        params = {}
        if tenant_code:
            sql += " AND tenant_code = :tc"
            params["tc"] = tenant_code
        return [(str(r.tenant_id), r.tenant_code) for r in master.execute(text(sql), params).fetchall()]
    finally:
        master.close()


async def _sync_one(u, tenant_id: str, dry_run: bool) -> str:
    """u is a SQLAlchemy Row mapping from _USER_SQL. Returns 'synced' | 'exists' | 'failed'."""
    label = f"{u['email']} ({u['username']})"
    if dry_run:
        print(f"    [dry-run] would sync {label}  tenant_id={u['tenant_id'] or tenant_id}")
        return "synced"
    try:
        result = await AuthServiceSync.create_auth_user(
            user_id=u["id"],
            user_setup_id=u["user_setup_id"],
            username=u["username"],
            email=u["email"],
            password_hash=u["password_hash"],
            firstname=u["firstname"],
            lastname=u["lastname"],
            phone_number=u["phone_number"],
            is_active=(u["status"] == "active"),
            employee_id=u["employee_id"],
            is_password_change=bool(u["is_password_change"]),
            tenant_id=u["tenant_id"] or tenant_id,
            can_change_password=bool(u["can_change_password"]) if u["can_change_password"] is not None else True,
        )
        if isinstance(result, dict) and result.get("status") == "already_exists":
            print(f"    - exists  {label}")
            return "exists"
        print(f"    ✓ synced  {label}")
        return "synced"
    except AuthServiceSyncError as exc:
        print(f"    ✗ failed  {label}: {exc}")
        return "failed"
    except Exception as exc:  # noqa: BLE001 — report and continue
        print(f"    ✗ error   {label}: {exc}")
        return "failed"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="Process every active tenant")
    parser.add_argument("--tenant", metavar="CODE", help="Process only this tenant_code")
    parser.add_argument("--dry-run", action="store_true", help="List without syncing")
    args = parser.parse_args()

    if not args.all and not args.tenant:
        parser.error("pass --all or --tenant CODE")

    if not AuthServiceSync.sync_enabled():
        print("ERROR: IDENTITY_SERVICE_URL is not set — nothing to sync to.")
        return 1
    print(f"identity: {settings.IDENTITY_SERVICE_URL}")
    print(f"postgres: {settings.DATABASE_URL.split('@')[-1]}\n")

    tenants = _active_tenants(args.tenant)
    if not tenants:
        print("No matching active tenants.")
        return 0

    totals = {"synced": 0, "exists": 0, "failed": 0, "tenants": 0, "users": 0}
    for tenant_id, code in tenants:
        db_name = tenant_db_manager.make_db_name(code)
        print(f"tenant {code}  ({db_name})  tenant_id={tenant_id}")
        try:
            session = tenant_db_manager.get_session(db_name, settings.DATABASE_URL)
        except Exception as exc:  # noqa: BLE001
            print(f"    ✗ cannot open {db_name}: {exc}\n")
            continue
        try:
            users = session.execute(_USER_SQL).mappings().all()
        finally:
            session.close()
        totals["tenants"] += 1
        for u in users:
            totals["users"] += 1
            totals[await _sync_one(u, tenant_id, args.dry_run)] += 1
        print()

    print("=" * 60)
    print(f"tenants processed : {totals['tenants']}")
    print(f"users seen        : {totals['users']}")
    print(f"synced            : {totals['synced']}")
    print(f"already existed   : {totals['exists']}")
    print(f"failed            : {totals['failed']}")
    print("=" * 60)
    return 1 if totals["failed"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
