from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import UUID
from typing import List, Optional, Dict, Any

from app.audit_logs.models.audit_logs import AuditLog
from app.audit_logs.schemas.audit_logs import AuditLogCreate


def _serialize(values: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert UUID / datetime values to JSON-safe strings."""
    if not values:
        return {}
    result = {}
    for k, v in values.items():
        if isinstance(v, UUID):
            result[k] = str(v)
        elif hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


# ── Write ──────────────────────────────────────────────────────────────────────

def create_audit_log(db: Session, payload: AuditLogCreate) -> AuditLog:
    """Create and persist a new audit log entry."""
    log = AuditLog(
        user_id=payload.user_id,
        client_id=payload.client_id,
        entity_id=payload.entity_id,
        action=payload.action,
        object_type=payload.object_type,
        object_id=payload.object_id,
        old_values=_serialize(payload.old_values),
        new_values=_serialize(payload.new_values),
        ip_address=payload.ip_address,
        user_agent=payload.user_agent,
        session_id=payload.session_id,
        risk_score=payload.risk_score,
        compliance_tags=payload.compliance_tags or [],
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def log_user_action(
    db: Session,
    *,
    action: str,
    object_type: str,
    client_id: UUID,
    object_id: Optional[str] = None,
    user_id: Optional[UUID] = None,
    entity_id: Optional[UUID] = None,
    old_values: Optional[Dict[str, Any]] = None,
    new_values: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
    risk_score: Optional[str] = None,
    compliance_tags: Optional[List[str]] = None,
) -> None:
    """
    Fire-and-forget audit log writer for use inside service functions.

    Swallows its own errors so a log failure never rolls back the main operation.

    Standard action values:
        CREATE | UPDATE | DELETE | RESTORE | LOGIN | LOGOUT | VIEW
    """
    try:
        log = AuditLog(
            user_id=user_id,
            client_id=client_id,
            entity_id=entity_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            old_values=_serialize(old_values),
            new_values=_serialize(new_values),
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            risk_score=risk_score,
            compliance_tags=compliance_tags or [],
        )
        db.add(log)
        db.commit()
    except Exception as exc:
        print(f"[audit] log_user_action failed: {exc}")
        db.rollback()


# ── Read ───────────────────────────────────────────────────────────────────────

def get_audit_log_by_id(db: Session, log_id: UUID) -> AuditLog:
    log = db.query(AuditLog).filter(AuditLog.log_id == log_id).first()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log not found")
    return log


def get_audit_logs(
    db: Session,
    *,
    client_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    action: Optional[str] = None,
    object_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[AuditLog]:
    """Generic filtered query — all params are optional."""
    q = db.query(AuditLog)
    if client_id:
        q = q.filter(AuditLog.client_id == client_id)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action.upper())
    if object_type:
        q = q.filter(AuditLog.object_type == object_type)
    return q.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()


def get_audit_logs_by_client(
    db: Session,
    client_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> List[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.client_id == client_id)
        .order_by(AuditLog.timestamp.desc())
        .offset(skip).limit(limit).all()
    )


def get_audit_logs_by_user(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> List[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user_id)
        .order_by(AuditLog.timestamp.desc())
        .offset(skip).limit(limit).all()
    )


def get_audit_logs_by_object(
    db: Session,
    object_type: str,
    object_id: str,
) -> List[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.object_type == object_type,
            AuditLog.object_id == object_id,
        )
        .order_by(AuditLog.timestamp.desc())
        .all()
    )
