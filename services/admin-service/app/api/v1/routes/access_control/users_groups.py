from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from uuid import UUID

from app.infrastructure.database.session import get_tenant_db
from app.core.security import get_current_user
from app.users_groups.models.users_groups import UserGroup
from app.users_groups.schemas.users_groups import UserGroupCreate, UserGroupUpdate, UserGroupResponse
from app.users_groups.services import users_groups as user_group_service
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.infrastructure.scope_helpers import require_whole_org_admin

router = APIRouter()


@router.get("/", response_model=List[UserGroupResponse])
def get_user_groups(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    tenant_id: Optional[UUID] = None,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all user groups with pagination and optional tenant filtering, sorted by newest first"""
    try:
        groups = user_group_service.get_all_user_groups(db, tenant_id=tenant_id, skip=skip, limit=limit)
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="UserGroup",
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score="LOW",
            )
        except Exception:
            pass
        return groups

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user groups: {str(e)}"
        )


@router.get("/{group_id}", response_model=UserGroupResponse)
def get_user_group(
    request: Request,
    group_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a single user group by ID"""
    try:
        group = user_group_service.get_user_group(db, group_id=group_id)
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="UserGroup",
                object_id=str(group_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score="LOW",
            )
        except Exception:
            pass
        return group

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user group: {str(e)}"
        )


@router.post("/", response_model=UserGroupResponse, status_code=status.HTTP_201_CREATED)
def create_user_group(
    request: Request,
    group_data: UserGroupCreate,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin),
):
    """Create a new user group"""
    # tenant_id is taken from the JWT, never the body. None => master-DB user.
    tenant_id = current_user.get("tenant_id") if isinstance(current_user, dict) else None
    try:
        group = user_group_service.create_user_group(db, group=group_data, tenant_id=tenant_id)

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="UserGroup",
                object_id=str(group.id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={"group_name": group.group_name},
            )
        except Exception:
            pass

        return group

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user group: {str(e)}"
        )


@router.put("/{group_id}", response_model=UserGroupResponse)
def update_user_group(
    request: Request,
    group_id: UUID,
    group_data: UserGroupUpdate,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin),
):
    """Update a user group"""
    try:
        group = user_group_service.update_user_group(db, group_id=group_id, group=group_data)

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="UPDATE",
                object_type="UserGroup",
                object_id=str(group_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["UPDATE"],
                new_values={"group_name": group.group_name},
            )
        except Exception:
            pass

        return group

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user group: {str(e)}"
        )


@router.delete("/{group_id}")
def delete_user_group(
    request: Request,
    group_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin),
):
    """Soft delete a user group"""
    try:
        # Query before delete to capture snapshot for audit
        group_snapshot = db.query(UserGroup).filter(UserGroup.id == group_id).first()
        old_group_name = group_snapshot.group_name if group_snapshot else None

        user_group_service.delete_user_group(db, group_id=group_id)

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="DELETE",
                object_type="UserGroup",
                object_id=str(group_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["DELETE"],
                old_values={"group_name": old_group_name, "id": str(group_id)},
            )
        except Exception:
            pass

        return {"message": "User group deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user group: {str(e)}"
        )
