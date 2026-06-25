from fastapi import APIRouter, Depends, status, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_client import fire_audit_log
from app.user_setup.services.user_setup import UserSetupService
from app.user_setup.schemas.user_setup import (
    UserSetupBasicCreate,
    UserSetupBasicUpdate,
    UserSetupBasicResponse,
    UserSetupRolesEntityCreate,
    UserSetupRolesEntityUpdate,
    UserSetupRolesEntityResponse,
    UserSetupPreferenceCreate,
    UserSetupPreferenceUpdate,
    UserSetupPreferenceResponse,
    UserSetupWithDetails,
    UserSetupCreateWithDetails,
    UserSetupListResponse,
    AvailableUsersResponse
)

router = APIRouter()





@router.post("/with-details", response_model=UserSetupWithDetails, status_code=status.HTTP_201_CREATED)
async def create_user_setup_with_details(
    request: Request,
    user_data: UserSetupCreateWithDetails,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a user setup with roles, entities, and preferences in one request.
    Also syncs the user to the identity-domain auth-service."""
    result = await UserSetupService.create_user_setup_with_details(db, user_data)

    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="CREATE",
            object_type="UserSetup",
            object_id=str(result.id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["CREATE"],
            new_values={"email": user_data.basic.email, "username": user_data.basic.username},
        )
    except Exception:
        pass

    return result





@router.get("/{user_id}/details", response_model=UserSetupWithDetails)
def get_user_setup_with_details(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a user setup with all related data (roles, entities, preferences)"""
    result = UserSetupService.get_user_setup_with_details(db, user_id)
    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="UserSetup",
            object_id=str(user_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score="LOW",
        )
    except Exception:
        pass
    return result


@router.put("/{user_id}", response_model=UserSetupBasicResponse)
async def update_user_setup(
    request: Request,
    user_id: UUID,
    user_data: UserSetupBasicUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a user setup"""
    result = await UserSetupService.update_user_setup(db, user_id, user_data)

    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="UPDATE",
            object_type="UserSetup",
            object_id=str(user_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
        )
    except Exception:
        pass

    return result


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user_setup(
    request: Request,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a user setup (cascades to roles_entities and preferences)"""
    result = await UserSetupService.delete_user_setup(db, user_id)

    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="UserSetup",
            object_id=str(user_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"id": str(user_id)},
        )
    except Exception:
        pass

    return result
