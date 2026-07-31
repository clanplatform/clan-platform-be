"""
Security API endpoints — CRUD for a tenant's SSO / MFA and session & password
policy (the onboarding "Security" step).

tenant_id is taken from the caller's JWT (None for master-DB users), never the
request body, and is not returned in responses.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_tenant_db
from app.core.security import get_current_user
from app.infrastructure.audit_helpers import get_user_id
from app.security.services import security as security_service
from app.security.exceptions import SecurityNotFoundError
from app.security.schemas.security import (
    SecurityCreate,
    SecurityUpdate,
    SecurityResponse,
    SecurityListResponse,
)

router = APIRouter()


def _creator_uuid(current_user) -> Optional[UUID]:
    uid = get_user_id(current_user)
    try:
        return UUID(str(uid)) if uid else None
    except (ValueError, TypeError):
        return None


def _tenant_from_token(current_user) -> Optional[UUID]:
    return current_user.get("tenant_id") if isinstance(current_user, dict) else None


@router.post(
    "/",
    response_model=SecurityResponse,
    status_code=201,
    summary="Create security settings",
    description="Create a client's security settings. tenant_id is taken from the JWT (None for master-DB users).",
)
def create_security(
    security: SecurityCreate,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    return security_service.create_security(
        db,
        security,
        tenant_id=_tenant_from_token(current_user),
        user_id=_creator_uuid(current_user),
    )


@router.get(
    "/",
    response_model=SecurityListResponse,
    summary="List security settings",
    description="Paginated list of security-settings rows (newest first).",
)
def list_security(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    total = security_service.get_securities_count(db)
    items = security_service.get_securities(db, skip=(page - 1) * size, limit=size)
    return SecurityListResponse(
        security=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if size else 0,
    )


@router.get(
    "/{security_id}",
    response_model=SecurityResponse,
    summary="Get security settings",
)
def get_security(
    security_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    sec = security_service.get_security(db, security_id)
    if not sec:
        raise SecurityNotFoundError()
    return sec


@router.put(
    "/{security_id}",
    response_model=SecurityResponse,
    summary="Update security settings",
)
def update_security(
    security_id: UUID,
    security: SecurityUpdate,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    return security_service.update_security(
        db, security_id, security, user_id=_creator_uuid(current_user)
    )


@router.delete(
    "/{security_id}",
    summary="Delete security settings",
    description="Soft delete (sets is_active = False).",
)
def delete_security(
    security_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    if not security_service.delete_security(db, security_id, user_id=_creator_uuid(current_user)):
        raise SecurityNotFoundError()
    return {"message": "Security settings deleted successfully"}
