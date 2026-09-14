"""
Direct lookups against the identity-service's own `auth_users` table.

admin-service and clan-identity-be's auth-service currently share the SAME
physical Postgres server, but `auth_users` lives only in the master
`clan_platform` database — never in a per-tenant database (each tenant gets
its own separate database, see Postgres DB consolidation). This module
always opens its own master-DB session for that reason: a caller's `db` may
be tenant-scoped (get_tenant_db), and querying a table that doesn't exist
there would raise and poison that session's transaction.

This is an implementation-detail shortcut, not a stable service contract —
if the two services are ever split onto separate physical databases, this
needs to become an HTTP call to auth-service instead (e.g. a new
GET /api/v1/auth/users/exists endpoint).

Used to fail fast with a clear "already exists" error AT CREATION TIME
(tenant owner, onboarding users[], direct user_setup creation), instead of
the vaguer UniqueViolation this would otherwise only surface later, at sync
time (see SyncService.sync_user in auth-service, and
AuthServiceSync.create_auth_user here).
"""
import logging
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


def auth_user_email_exists(email: Optional[str]) -> bool:
    """Whether `email` (case-insensitive) already belongs to a row in
    auth_users — the identity-service's own login table, authoritative for
    "does this email already have login credentials anywhere on the
    platform". Opens its own master-DB session (auth_users only lives
    there). Never raises — a lookup failure returns False (fail open, same
    convention as compliance_registry.resolve_branch_compliance_key) so an
    infra hiccup on this check never blocks the primary create flow."""
    if not email:
        return False
    from app.infrastructure.database.session import SessionLocal

    master_db = SessionLocal()
    try:
        row = master_db.execute(
            text("SELECT 1 FROM auth_users WHERE lower(email) = lower(:email) LIMIT 1"),
            {"email": email},
        ).first()
        return row is not None
    except Exception as exc:
        logger.warning("[AUTH_USERS_LOOKUP] email existence check failed for %s: %s", email, exc)
        return False
    finally:
        master_db.close()
