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
    Look up client_id and entity_id for the acting user.

    The JWT carries usersetup_basic.id as the user identifier, so we query
    UserSetupBasic.id directly.

    Returns (client_id, entity_id) as strings, or (None, None) if not found.
    """
    if not user_id:
        return None, None
    try:
        from app.user_setup.models.user_setup import UserSetupBasic
        basic = db.query(UserSetupBasic).filter(
            UserSetupBasic.id == user_id
        ).first()
        if not basic:
            return None, None

        client_id = str(basic.client_id) if basic.client_id else None

        entity_id = None
        if basic.default_entity:
            entity_id = str(basic.default_entity)
        elif basic.roles_entities:
            for re in basic.roles_entities:
                if re.assigned_entities:
                    entity_id = str(re.assigned_entities[0])
                    break

        return client_id, entity_id
    except Exception:
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
