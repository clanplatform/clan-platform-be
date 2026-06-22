from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
import logging

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user_id
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip
from app.infrastructure.audit_client import fire_audit_log
from app.user_role.services.user_role import UserRoleService
from app.user_role.models.user_role import UserRoleBasic, UserRoleConditional, UserRoleMain, UserRolePermission
from app.user_role.schemas.user_role import (
    UserRoleBasicCreate,
    UserRoleBasicUpdate,
    UserRoleBasicResponse,
    UserRolePermissionCreate,
    UserRolePermissionUpdate,
    UserRolePermissionResponse,
    UserRoleConditionalCreate,
    UserRoleConditionalUpdate,
    UserRoleConditionalResponse,
    UserRoleWithDetails,
    UserRoleCreateWithDetails,
    UserRoleUpdateWithDetails,
    AvailableEntitiesResponse
)


logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# UserRoleBasic Endpoints
# ============================================================================

# @router.post("/", response_model=UserRoleBasicResponse, status_code=status.HTTP_201_CREATED)
# def create_user_role(
#     role_data: UserRoleBasicCreate,
#     db: Session = Depends(get_db),
#     current_user_id: str = Depends(get_current_user_id)
# ):
#     """Create a new user role zonix"""
#     return UserRoleService.create_user_role(db, role_data)


@router.post("/menu-details", response_model=UserRoleWithDetails, status_code=status.HTTP_201_CREATED)
def create_user_role_with_details(
    request: Request,
    role_data: UserRoleCreateWithDetails,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a user role with permissions and conditionals in one request"""
    role = UserRoleService.create_user_role_with_details(db, role_data)

    # Audit log: user role created
    try:
        role_id = str(role.basic.id) if hasattr(role, 'basic') and role.basic else str(getattr(role, 'id', ''))
        fire_audit_log(
            action="CREATE",
            object_type="UserRole",
            object_id=role_id,
            user_id=current_user_id,
            session_id=None,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["CREATE"],
            new_values={"role_name": str(getattr(getattr(role, 'basic', role), 'role_name', ''))},
        )
    except Exception:
        pass

    return role


@router.get("/", response_model=List[UserRoleBasicResponse])
def get_all_user_roles(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    active_only: bool = Query(False, description="Filter to only active roles"),
    client_id: Optional[UUID] = Query(None, description="Filter roles by client"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get all user roles, optionally filtered by client"""
    return UserRoleService.get_all_user_roles(db, skip=skip, limit=limit, active_only=active_only, client_id=client_id)


# @router.get("/{role_id}", response_model=UserRoleBasicResponse)
# def get_user_role(
#     role_id: UUID,
#     db: Session = Depends(get_db),
#     current_user_id: str = Depends(get_current_user_id)
# ):
#     """Get a specific user role by ID"""
#     role = UserRoleService.get_user_role(db, role_id)
#     if not role:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"User role with ID {role_id} not found"
#         )
#     return role


@router.get("/{role_id}/details", response_model=UserRoleWithDetails)
def get_user_role_with_details(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get a user role with all permissions and conditionals"""
    role = UserRoleService.get_user_role_with_details(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User role with ID {role_id} not found"
        )
    return role


@router.put("/{role_id}/details", response_model=UserRoleWithDetails)
def update_user_role_with_details(
    request: Request,
    role_id: UUID,
    role_data: UserRoleUpdateWithDetails,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Update a user role with all permissions and conditionals in one request"""
    role = UserRoleService.update_user_role_with_details(db, role_id, role_data)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User role with ID {role_id} not found"
        )

    # Audit log: user role updated
    try:
        fire_audit_log(
            action="UPDATE",
            object_type="UserRole",
            object_id=str(role_id),
            user_id=current_user_id,
            session_id=None,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            new_values={"role_name": str(getattr(getattr(role, 'basic', role), 'role_name', ''))},
        )
    except Exception:
        pass

    return role


# @router.put("/{role_id}", response_model=UserRoleBasicResponse)
# def update_user_role(
#     role_id: UUID,
#     role_data: UserRoleBasicUpdate,
#     db: Session = Depends(get_db),
#     current_user_id: str = Depends(get_current_user_id)
# ):
#     """Update a user role"""
#     role = UserRoleService.update_user_role(db, role_id, role_data)
#     if not role:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"User role with ID {role_id} not found"
#         )
#     return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_role(
    request: Request,
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Delete a user role (cascades to permissions and conditionals)"""
    success = UserRoleService.delete_user_role(db, role_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User role with ID {role_id} not found"
        )

    # Audit log: user role deleted
    try:
        fire_audit_log(
            action="DELETE",
            object_type="UserRole",
            object_id=str(role_id),
            user_id=current_user_id,
            session_id=None,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"id": str(role_id)},
        )
    except Exception:
        pass

    return None


