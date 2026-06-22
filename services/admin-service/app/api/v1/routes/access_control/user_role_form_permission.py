from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from math import ceil

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_client import fire_audit_log
from app.user_role_form_permission.schemas.user_role_form_permission import (
    RoleFormPermissionCreate,
    RoleFormPermissionUpdate,
    RoleFormPermissionResponse,
    RoleFormPermissionListResponse
)
from app.user_role_form_permission.services.user_role_form_permission import RoleFormPermissionService

router = APIRouter()


@router.post(
    "/",
    response_model=RoleFormPermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Role Form Permission",
    description="Create form permissions based on selected menus from userrole_permission table"
)
async def create_role_form_permission(
    request: Request,
    permission_data: RoleFormPermissionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new role form permission based on selected menus.
    
    - **userrole_permission_id**: UUID of the user role permission (required - to get menu selections)
    - **form_permissions**: Array of form permission items with:
      - **id**: Form UUID
      - **menu_id**: Menu ID (must be from the selected menus in userrole_permission)
      - **form_access**: Access levels (read, write, disable)
    
    The system will:
    1. Fetch the userrole_permission record
    2. Get the selected menu IDs from menu_permissions
    3. Validate that all form permissions reference only selected menus
    4. Automatically set user_role_id and userrole_basic_id from the permission record
    
    Returns the created role form permission record.
    """
    try:
        created_permission = RoleFormPermissionService.create_role_form_permission(
            db,
            permission_data
        )

        # Audit log: role form permission created
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="RoleFormPermission",
                object_id=str(created_permission.id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={"id": str(created_permission.id)},
            )
        except Exception:
            pass

        return created_permission
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create role form permission: {str(e)}"
        )


@router.get(
    "/{permission_id}",
    response_model=RoleFormPermissionResponse,
    summary="Get Role Form Permission by ID",
    description="Retrieve a specific role form permission by its ID"
)
async def get_role_form_permission(
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get a role form permission by ID.
    
    - **permission_id**: UUID of the role form permission
    
    Returns the role form permission record.
    """
    permission = RoleFormPermissionService.get_role_form_permission(db, permission_id)
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role form permission with ID {permission_id} not found"
        )
    
    return permission




@router.get(
    "/",
    response_model=RoleFormPermissionListResponse,
    summary="Get All Role Form Permissions",
    description="Retrieve all role form permissions with optional filtering"
)
async def get_all_role_form_permissions(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=1000, description="Page size"),
    user_role_id: Optional[UUID] = Query(None, description="Filter by user role ID"),
    userrole_basic_id: Optional[UUID] = Query(None, description="Filter by user role basic ID"),
    form_access: Optional[str] = Query(None, description="Filter by form access level (read, write, disable)"),
    sort_by: str = Query("created_at", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all role form permissions with optional filtering and pagination.
    
    - **page**: Page number (default: 1)
    - **size**: Page size (default: 100, max: 1000)
    - **user_role_id**: Optional filter by user role ID
    - **userrole_basic_id**: Optional filter by user role basic ID
    - **form_access**: Optional filter by form access level
    - **sort_by**: Field to sort by (default: created_at)
    - **sort_order**: Sort order - asc or desc (default: desc)
    
    Returns paginated list of role form permissions.
    """
    skip = (page - 1) * size
    permissions, total = RoleFormPermissionService.get_all_role_form_permissions(
        db,
        skip=skip,
        limit=size,
        user_role_id=user_role_id,
        userrole_basic_id=userrole_basic_id,
        form_access=form_access,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    total_pages = ceil(total / size) if size > 0 else 0
    
    return RoleFormPermissionListResponse(
        items=permissions,
        total=total,
        page=page,
        size=size,
        total_pages=total_pages
    )


@router.put(
    "/{permission_id}",
    response_model=RoleFormPermissionResponse,
    summary="Update Role Form Permission",
    description="Update form permissions (must reference selected menus from userrole_permission)"
)
async def update_role_form_permission(
    request: Request,
    permission_id: UUID,
    permission_data: RoleFormPermissionUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update a role form permission.
    
    - **permission_id**: UUID of the role form permission to update
    - **form_permissions**: Array of form permission items to update
      - Each form must reference a menu_id that exists in the userrole_permission.menu_permissions
    
    Returns the updated role form permission record.
    """
    try:
        updated_permission = RoleFormPermissionService.update_role_form_permission(
            db,
            permission_id,
            permission_data
        )

        if not updated_permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role form permission with ID {permission_id} not found"
            )

        # Audit log: role form permission updated
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="UPDATE",
                object_type="RoleFormPermission",
                object_id=str(permission_id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["UPDATE"],
                new_values={"id": str(permission_id)},
            )
        except Exception:
            pass

        return updated_permission
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update role form permission: {str(e)}"
        )


@router.delete(
    "/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Role Form Permission",
    description="Delete a specific role form permission"
)
async def delete_role_form_permission(
    request: Request,
    permission_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a role form permission.

    - **permission_id**: UUID of the role form permission to delete
    """
    deleted = RoleFormPermissionService.delete_role_form_permission(db, permission_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role form permission with ID {permission_id} not found"
        )

    # Audit log: role form permission deleted
    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="RoleFormPermission",
            object_id=str(permission_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={},
        )
    except Exception:
        pass

    return None

