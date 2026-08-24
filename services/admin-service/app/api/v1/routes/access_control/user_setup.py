from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
import logging

from app.infrastructure.database.session import get_db, get_tenant_db
from app.core.security import get_current_user
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.infrastructure.scope_helpers import resolve_scope_filter, require_whole_org_admin
from app.user_setup.services.user_setup import UserSetupService
from app.user_setup.schemas.user_setup import (
    UserSetupBasicCreate,
    UserSetupBasicUpdate,
    UserSetupBasicResponse,
    UserSetupPreferenceCreate,
    UserSetupPreferenceUpdate,
    UserSetupPreferenceResponse,
    UserSetupWithDetails,
    UserSetupCreateWithDetails,
    UserSetupListResponse,
    AvailableUsersResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# POST — Create user with full details
# ============================================================================

@router.post("/with-details", response_model=UserSetupWithDetails, status_code=status.HTTP_201_CREATED)
async def create_user_setup_with_details(
    request: Request,
    user_data: UserSetupCreateWithDetails,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin)
):
    """Create a user setup with roles, entities, and preferences in one request."""
    # tenant_id is taken from the JWT, never the body. None => master-DB user.
    tenant_id = current_user.get("tenant_id") if isinstance(current_user, dict) else None
    result = await UserSetupService.create_user_setup_with_details(db, user_data, tenant_id=tenant_id)

    try:
        uid = get_user_id(current_user)
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, uid)
        fire_audit_log(
            action="CREATE",
            object_type="UserSetup",
            object_id=str(result.id),
            user_id=uid,
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["CREATE"],
            new_values={
                "email": str(user_data.basic.email),
                "username": user_data.basic.username,
                "firstname": user_data.basic.firstname,
                "lastname": user_data.basic.lastname,
                "tenant_id": str(tenant_id) if tenant_id else None,
            },
        )
        logger.info(f"Audit log fired: CREATE UserSetup {result.id} by user {uid}")
    except Exception as e:
        logger.error(f"Failed to fire audit log for CREATE UserSetup: {e}", exc_info=True)

    return result


# ============================================================================
# GET — List all users
# ============================================================================

@router.get("/", response_model=UserSetupListResponse)
def get_all_user_setups(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all user setups with pagination and optional filters."""
    scope_filter = resolve_scope_filter(db, get_user_id(current_user))
    result = UserSetupService.get_all_user_setups(
        db,
        skip=skip,
        limit=limit,
        status_filter=status_filter,
        scope_filter=scope_filter,
    )

    try:
        uid = get_user_id(current_user)
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, uid)
        fire_audit_log(
            action="READ",
            object_type="UserSetup",
            user_id=uid,
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score="LOW",
            new_values={"filters": {"status": status_filter}},
        )
        logger.info(f"Audit log fired: READ ALL UserSetup by user {uid}")
    except Exception as e:
        logger.error(f"Failed to fire audit log for READ ALL UserSetup: {e}", exc_info=True)

    return result


# ============================================================================
# GET — Single user (basic)
# ============================================================================

@router.get("/{user_id}", response_model=UserSetupBasicResponse)
def get_user_setup(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a single user setup (basic info)."""
    result = UserSetupService.get_user_setup(db, user_id)

    try:
        uid = get_user_id(current_user)
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, uid)
        fire_audit_log(
            action="READ",
            object_type="UserSetup",
            object_id=str(user_id),
            user_id=uid,
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score="LOW",
        )
        logger.info(f"Audit log fired: READ UserSetup {user_id} by user {uid}")
    except Exception as e:
        logger.error(f"Failed to fire audit log for READ UserSetup {user_id}: {e}", exc_info=True)

    return result


# ============================================================================
# GET — Single user with full details
# ============================================================================

@router.get("/{user_id}/details", response_model=UserSetupWithDetails)
def get_user_setup_with_details(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a user setup with roles, entities, and preferences."""
    result = UserSetupService.get_user_setup_with_details(db, user_id)

    try:
        uid = get_user_id(current_user)
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, uid)
        fire_audit_log(
            action="READ",
            object_type="UserSetup",
            object_id=str(user_id),
            user_id=uid,
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score="LOW",
        )
        logger.info(f"Audit log fired: READ DETAILS UserSetup {user_id} by user {uid}")
    except Exception as e:
        logger.error(f"Failed to fire audit log for READ DETAILS UserSetup {user_id}: {e}", exc_info=True)

    return result


# ============================================================================
# PUT — Update user
# ============================================================================

@router.put("/{user_id}", response_model=UserSetupBasicResponse)
async def update_user_setup(
    request: Request,
    user_id: UUID,
    user_data: UserSetupBasicUpdate,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin)
):
    """Update a user setup."""
    result = await UserSetupService.update_user_setup(db, user_id, user_data)

    try:
        uid = get_user_id(current_user)
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, uid)
        changed_fields = {k: v for k, v in user_data.model_dump(exclude_unset=True).items() if k != "password"}
        fire_audit_log(
            action="UPDATE",
            object_type="UserSetup",
            object_id=str(user_id),
            user_id=uid,
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            new_values=changed_fields,
        )
        logger.info(f"Audit log fired: UPDATE UserSetup {user_id} by user {uid} fields={list(changed_fields.keys())}")
    except Exception as e:
        logger.error(f"Failed to fire audit log for UPDATE UserSetup {user_id}: {e}", exc_info=True)

    return result


# ============================================================================
# DELETE — Remove user
# ============================================================================

@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user_setup(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin)
):
    """Delete a user setup (cascades to preferences)."""
    result = await UserSetupService.delete_user_setup(db, user_id)

    try:
        uid = get_user_id(current_user)
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, uid)
        fire_audit_log(
            action="DELETE",
            object_type="UserSetup",
            object_id=str(user_id),
            user_id=uid,
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"id": str(user_id)},
        )
        logger.info(f"Audit log fired: DELETE UserSetup {user_id} by user {uid}")
    except Exception as e:
        logger.error(f"Failed to fire audit log for DELETE UserSetup {user_id}: {e}", exc_info=True)

    return result
