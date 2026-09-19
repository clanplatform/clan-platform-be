"""
CRUD for user_invitations — the invitation-email record resource.

Sending (POST here, and the single/selected/bulk convenience endpoints
under /api/v1/user_setup/) is documented in app.user_invitations.services
.user_invitations — bulk/selected sends never run inline; see that module's
docstring and BULK_SEND_CONCURRENCY for how they avoid sending hundreds of
emails synchronously.
"""
from typing import Optional
from uuid import UUID
import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_tenant_db
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.infrastructure.scope_helpers import require_whole_org_admin
from app.user_invitations.services.user_invitations import UserInvitationService
from app.user_invitations.schemas.user_invitations import (
    UserInvitationCreate,
    UserInvitationUpdate,
    UserInvitationResponse,
    UserInvitationListResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=UserInvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_and_send_invitation(
    request: Request,
    payload: UserInvitationCreate,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin),
):
    """Create and immediately send an invitation to one user_setup user.

    Equivalent to POST /user_setup/{user_id}/send-invitation — kept here too
    so user_invitations has a normal CRUD create alongside its GET/PUT/DELETE.
    """
    tenant_id = current_user.get("tenant_id") if isinstance(current_user, dict) else None
    tenant_id_uuid = UUID(str(tenant_id)) if tenant_id else None
    tenant_name, tenant_app_url = UserInvitationService.resolve_tenant_branding(tenant_id_uuid)

    invitation = await UserInvitationService.send_single(
        db, payload.user_id, tenant_id_uuid, tenant_name=tenant_name, tenant_app_url=tenant_app_url,
    )

    try:
        user_id = get_user_id(current_user)
        audit_tenant_id, entity_id = get_audit_org_context(db, user_id)
        fire_audit_log(
            action="CREATE", object_type="UserInvitation", object_id=str(invitation.id),
            user_id=user_id, tenant_id=audit_tenant_id, entity_id=entity_id,
            session_id=get_session_id(current_user), ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"), risk_score=RISK_SCORE["CREATE"],
            new_values={"user_id": str(payload.user_id), "status": invitation.status},
        )
    except Exception:
        pass

    return invitation


@router.get("/", response_model=UserInvitationListResponse)
async def list_invitations(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    user_id: Optional[UUID] = Query(None, description="Filter to one user's invitations"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by invitation status"),
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin),
):
    """List invitation records, newest first."""
    rows, total = UserInvitationService.list_invitations(
        db, skip=skip, limit=limit, user_id=user_id, status_filter=status_filter,
    )
    return UserInvitationListResponse(
        invitations=rows, total=total,
        page=(skip // limit) + 1 if limit else 1, size=limit,
        total_pages=math.ceil(total / limit) if limit else 1,
    )


@router.get("/{invitation_id}", response_model=UserInvitationResponse)
async def get_invitation(
    request: Request,
    invitation_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin),
):
    """Get one invitation record by id."""
    invitation = UserInvitationService.get_invitation(db, invitation_id)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invitation {invitation_id} not found")
    return invitation


@router.put("/{invitation_id}", response_model=UserInvitationResponse)
async def update_invitation(
    request: Request,
    invitation_id: UUID,
    payload: UserInvitationUpdate,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin),
):
    """Update an invitation's status (e.g. manually mark accepted/failed).

    email/token/expiry are fixed at send time and not editable here — resend
    via POST /user_setup/{user_id}/send-invitation instead, which creates a
    fresh row with its own token rather than mutating this one.
    """
    if payload.status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status is required")

    invitation = UserInvitationService.update_invitation_status(db, invitation_id, payload.status)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invitation {invitation_id} not found")

    try:
        user_id = get_user_id(current_user)
        audit_tenant_id, entity_id = get_audit_org_context(db, user_id)
        fire_audit_log(
            action="UPDATE", object_type="UserInvitation", object_id=str(invitation_id),
            user_id=user_id, tenant_id=audit_tenant_id, entity_id=entity_id,
            session_id=get_session_id(current_user), ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"), risk_score=RISK_SCORE["UPDATE"],
            new_values={"status": payload.status},
        )
    except Exception:
        pass

    return invitation


@router.delete("/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(
    request: Request,
    invitation_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin),
):
    """Cancel an invitation — a SaaS-appropriate soft delete: the row is kept
    with status transitioned to 'cancelled', never physically removed."""
    invitation = UserInvitationService.cancel_invitation(db, invitation_id)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Invitation {invitation_id} not found")

    try:
        user_id = get_user_id(current_user)
        audit_tenant_id, entity_id = get_audit_org_context(db, user_id)
        fire_audit_log(
            action="DELETE", object_type="UserInvitation", object_id=str(invitation_id),
            user_id=user_id, tenant_id=audit_tenant_id, entity_id=entity_id,
            session_id=get_session_id(current_user), ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"), risk_score=RISK_SCORE["DELETE"],
            old_values={"id": str(invitation_id)},
        )
    except Exception:
        pass

    return None
