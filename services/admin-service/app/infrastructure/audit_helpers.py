"""
Shared audit helpers — imported by every route that calls fire_audit_log.
"""
from typing import Optional, Tuple
from fastapi import Request
from sqlalchemy.orm import Session

RISK_SCORE = {"CREATE": "LOW", "UPDATE": "MEDIUM", "DELETE": "HIGH"}


def get_client_ip(request: Request) -> Optional[str]:
    """Return the real client IP, honouring X-Forwarded-For when behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_audit_org_context(db: Session, user_id: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Look up tenant_id and entity_id for the acting user.

    The JWT carries usersetup_basic.id as the user identifier, so we query
    UserSetupBasic.id directly.

    Returns (tenant_id, entity_id) as strings, or (None, None) if not found.
    Master-DB users legitimately have tenant_id NULL.
    """
    if not user_id:
        return None, None
    try:
        from app.user_setup.models.user_setup import UserSetupBasic
        # Select only the needed columns — tenant DBs lag behind the master
        # schema (e.g. no allowed_origins), so a full-model SELECT can fail.
        row = db.query(
            UserSetupBasic.tenant_id,
            UserSetupBasic.entity_id,
        ).filter(UserSetupBasic.id == user_id).first()
        if not row:
            return None, None

        tenant_id = str(row.tenant_id) if row.tenant_id else None
        # entity_id holds every branch the user is assigned to; the first is
        # treated as their default/primary branch for audit context.
        entity_id = str(row.entity_id[0]) if row.entity_id else None

        return tenant_id, entity_id
    except Exception:
        db.rollback()
        return None, None


def get_user_id(current_user) -> Optional[str]:
    """Extract user_id whether current_user is a dict or a bare string."""
    if isinstance(current_user, dict):
        return current_user.get("id")
    if isinstance(current_user, str):
        return current_user
    return None


def get_session_id(current_user) -> Optional[str]:
    """Extract session_id from current_user dict (None for string-only auth)."""
    if isinstance(current_user, dict):
        return current_user.get("session_id")
    return None
