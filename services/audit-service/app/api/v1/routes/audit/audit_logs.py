from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.infrastructure.database.session import get_db
from app.audit_logs.schemas.audit_logs import AuditLogCreate, AuditLogResponse
from app.audit_logs.services.audit_logs import (
    create_audit_log,
    get_audit_log_by_id,
    get_audit_logs,
    get_audit_logs_by_client,
    get_audit_logs_by_user,
    get_audit_logs_by_object,
)
from app.core.security import get_current_user

router = APIRouter()


# ── Write ──────────────────────────────────────────────────────────────────────

@router.post("", response_model=AuditLogResponse, status_code=201)
def write_log(
    payload: AuditLogCreate,
    db: Session = Depends(get_db),
):
    """Create a new audit log entry — no auth required (internal service endpoint)."""
    return create_audit_log(db, payload)


# ── Read – generic list ────────────────────────────────────────────────────────

@router.get("", response_model=List[AuditLogResponse])
def list_logs(
    client_id: Optional[UUID] = Query(None),
    user_id: Optional[UUID] = Query(None),
    action: Optional[str] = Query(None, max_length=100),
    object_type: Optional[str] = Query(None, max_length=100),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    List audit logs with optional filters.

    Query params:
    - client_id   – filter by client
    - user_id     – filter by the user who acted
    - action      – CREATE / UPDATE / DELETE / RESTORE / LOGIN / LOGOUT
    - object_type – Department / Entity / Client / …
    """
    return get_audit_logs(
        db,
        client_id=client_id,
        user_id=user_id,
        action=action,
        object_type=object_type,
        skip=skip,
        limit=limit,
    )


# ── Read – single log ──────────────────────────────────────────────────────────

@router.get("/{log_id}", response_model=AuditLogResponse)
def get_log(
    log_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Retrieve a single audit log entry by its ID."""
    return get_audit_log_by_id(db, log_id=log_id)


# ── Read – scoped queries ─────────────────────────────────────────────────────

@router.get("/client/{client_id}", response_model=List[AuditLogResponse])
def logs_by_client(
    client_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """All audit logs for a client, newest first."""
    return get_audit_logs_by_client(db, client_id=client_id, skip=skip, limit=limit)


@router.get("/user/{user_id}", response_model=List[AuditLogResponse])
def logs_by_user(
    user_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """All audit logs for actions performed by a specific user, newest first."""
    return get_audit_logs_by_user(db, user_id=user_id, skip=skip, limit=limit)


@router.get("/history/{object_type}/{object_id}", response_model=List[AuditLogResponse])
def logs_by_object(
    object_type: str,
    object_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Full change history for a specific record.

    Example:  GET /api/v1/logs/history/Department/uuid-here
    """
    return get_audit_logs_by_object(db, object_type=object_type, object_id=object_id)
