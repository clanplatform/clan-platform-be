from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import logging

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user_id
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

router = APIRouter(prefix="/user-roles", tags=["User Roles"])
logger = logging.getLogger(__name__)


# ============================================================================
# UserRoleBasic Endpoints
# ============================================================================

@router.post("/", response_model=UserRoleBasicResponse, status_code=status.HTTP_201_CREATED)
def create_user_role(
    role_data: UserRoleBasicCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a new user role zonix"""
    return UserRoleService.create_user_role(db, role_data)


@router.post("/menu-details", response_model=UserRoleWithDetails, status_code=status.HTTP_201_CREATED)
def create_user_role_with_details(
    role_data: UserRoleCreateWithDetails,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a user role with permissions and conditionals in one request"""
    return UserRoleService.create_user_role_with_details(db, role_data)


@router.get("/", response_model=List[UserRoleBasicResponse])
def get_all_user_roles(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    active_only: bool = Query(False, description="Filter to only active roles"),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get all user roles"""
    return UserRoleService.get_all_user_roles(db, skip=skip, limit=limit, active_only=active_only)


@router.get("/{role_id}", response_model=UserRoleBasicResponse)
def get_user_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get a specific user role by ID"""
    role = UserRoleService.get_user_role(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User role with ID {role_id} not found"
        )
    return role


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
    return role


@router.put("/{role_id}", response_model=UserRoleBasicResponse)
def update_user_role(
    role_id: UUID,
    role_data: UserRoleBasicUpdate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Update a user role"""
    role = UserRoleService.update_user_role(db, role_id, role_data)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User role with ID {role_id} not found"
        )
    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_role(
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
    return None


