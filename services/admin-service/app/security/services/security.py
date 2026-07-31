"""Security service — CRUD over the security table."""
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import logging

from app.security.models.security import Security
from app.security.schemas.security import SecurityCreate, SecurityUpdate
from app.security.exceptions import SecurityNotFoundError
from app.infrastructure.audit_tenant import fire_audit_log

logger = logging.getLogger(__name__)


def _audit(action: str, sec: Security, user_id: Optional[UUID], **kw) -> None:
    """Best-effort audit — never breaks the caller."""
    try:
        fire_audit_log(
            action=action,
            object_type="Security",
            object_id=str(sec.security_id),
            tenant_id=str(sec.tenant_id) if sec.tenant_id else None,
            user_id=str(user_id) if user_id else None,
            **kw,
        )
    except Exception:  # pragma: no cover - audit must not fail the request
        pass


def get_security(db: Session, security_id: UUID) -> Optional[Security]:
    """Get a security-settings row by id."""
    return db.query(Security).filter(Security.security_id == security_id).first()


def get_securities(db: Session, skip: int = 0, limit: int = 100) -> List[Security]:
    """List security-settings rows (newest first)."""
    return (
        db.query(Security)
        .order_by(Security.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_securities_count(db: Session) -> int:
    return db.query(Security).count()


def create_security(
    db: Session,
    security: SecurityCreate,
    tenant_id: Optional[UUID],
    user_id: Optional[UUID] = None,
) -> Security:
    """Create a security-settings row.

    tenant_id is not part of the request body — it is derived from the caller's
    JWT (None for master-DB users, a tenant UUID for tenant-DB users).
    """
    db_sec = Security(
        **security.model_dump(),
        tenant_id=tenant_id,
        created_by=user_id,
    )
    db.add(db_sec)
    db.commit()
    db.refresh(db_sec)
    _audit("CREATE", db_sec, user_id, new_values={"enable_sso": db_sec.enable_sso, "require_mfa": db_sec.require_mfa})
    return db_sec


def update_security(
    db: Session,
    security_id: UUID,
    security: SecurityUpdate,
    user_id: Optional[UUID] = None,
) -> Security:
    """Update a security-settings row."""
    db_sec = get_security(db, security_id)
    if not db_sec:
        raise SecurityNotFoundError()

    update_data = security.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_sec, field, value)

    db.add(db_sec)
    db.commit()
    db.refresh(db_sec)
    _audit("UPDATE", db_sec, user_id, new_values=update_data)
    return db_sec


def delete_security(db: Session, security_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """Soft delete a security-settings row (is_active = False)."""
    db_sec = get_security(db, security_id)
    if not db_sec:
        return False

    db_sec.is_active = False
    db.add(db_sec)
    db.commit()
    _audit("DELETE", db_sec, user_id, old_values={"is_active": True}, new_values={"is_active": False})
    return True
