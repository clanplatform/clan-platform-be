from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
# Modules, tenant_modules live only in the master DB; tenant scoping is done by
# filtering tenant_modules.tenant_id, not by switching databases.
from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.modules.services.module import ModuleService
from app.modules.schemas.module import (
    ModuleCreate,
    ModuleUpdate,
    ModuleResponse,
    ModuleListResponse
)
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
import math

router = APIRouter()


@router.post(
    "/",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new module",
    description="Create a new module with the provided details"
)
async def create_module(
    request: Request,
    module_data: ModuleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    created_by: Optional[int] = Query(None, description="User ID who is creating the module")
):
    """
    Create a new module.
    
    - **application_id**: UUID of the application this module belongs to
    - **name**: Internal name of the module (required)
    - **code**: Unique identifier code (optional, e.g., CLIENT_MGMT)
    - **key**: Module key for navigation (optional, e.g., analytics-module)
    - **label**: Display name (optional, e.g., Analytics Module)
    - **section_title**: Group title in UI (optional)
    - **description**: Module description (optional)
    - **icon**: Icon class/name (optional)
    - **badge**: Badge text (optional)
    - **route**: Route path (optional)
    - **level**: Hierarchy level (default: 1)
    - **order_index**: Ordering index (default: 0)
    - **is_active**: Whether module is active (default: true)
    """
    
    # Check for duplicate code
    if module_data.code:
        existing_module = ModuleService.get_module_by_code(db, module_data.code)
        if existing_module:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Module with code '{module_data.code}' already exists"
            )
    
    # Check for duplicate key
    if module_data.key:
        existing_module = ModuleService.get_module_by_key(db, module_data.key)
        if existing_module:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Module with key '{module_data.key}' already exists"
            )
    
    try:
        module = ModuleService.create_module(db, module_data, created_by)

        # Sync so the new (possibly empty) module appears in the MongoDB navigation
        try:
            from app.menus.services.menu_sync import sync_application_menus_to_mongodb
            await sync_application_menus_to_mongodb(db, module.application_id)
        except Exception as sync_error:
            print(f"[Module Create] ⚠️ MongoDB sync failed: {sync_error}")

        # Audit log: module created
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Module",
                object_id=str(module.id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={"name": module.name},
            )
        except Exception:
            pass

        return module
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create module: {str(e)}"
        )

@router.get(
    "/",
    response_model=ModuleListResponse,
    summary="Get modules with filtering and pagination",
    description="Retrieve modules with optional filtering, searching, and pagination"
)
async def get_modules(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    application_id: Optional[str] = Query(None, description="Filter by application ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name, label, description, code, or key"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order (asc or desc)")
):
    """
    Get modules with filtering and pagination.
    
    - **page**: Page number (starts from 1)
    - **size**: Number of items per page (1-100)
    - **application_id**: Filter by application ID
    - **is_active**: Filter by active status
    - **search**: Search in name, label, description, code, or key
    - **sort_by**: Field to sort by (default: created_at)
    - **sort_order**: Sort order - asc or desc (default: desc)
    """
    
    skip = (page - 1) * size

    # Resolve the requesting user's tenant_id for tenant isolation.
    # Platform admins (no tenant_id in token) see all modules.
    requester_tenant_id = current_user.get("tenant_id") if current_user else None

    try:
        modules, total = ModuleService.get_modules(
            db=db,
            skip=skip,
            limit=size,
            application_id=application_id,
            is_active=is_active,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            tenant_id=requester_tenant_id,
        )
        
        total_pages = math.ceil(total / size) if total > 0 else 0

        result = ModuleListResponse(
            modules=modules,
            total=total,
            page=page,
            size=size,
            total_pages=total_pages
        )
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="Module",
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
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve modules: {str(e)}"
        )

@router.get(
    "/application/{application_id}",
    response_model=List[ModuleResponse],
    summary="Get modules by application ID",
    description="Retrieve all modules for a specific application"
)
async def get_modules_by_application(
    request: Request,
    application_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    is_active: Optional[bool] = Query(None, description="Filter by active status")
):
    """
    Get all modules for a specific application.

    - **application_id**: The UUID of the application
    - **is_active**: Filter by active status (optional)
    """

    try:
        modules = ModuleService.get_modules_by_application(db, application_id, is_active)
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="Module",
                object_id=application_id,
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
        return modules
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve modules for application: {str(e)}"
        )


@router.put(
    "/{module_id}",
    response_model=ModuleResponse,
    summary="Update a module",
    description="Update an existing module with the provided details"
)
async def update_module(
    request: Request,
    module_id: str,
    module_data: ModuleUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update an existing module.
    
    - **module_id**: The UUID of the module to update
    - All fields are optional and only provided fields will be updated
    """
    
    # Check if module exists
    existing_module = ModuleService.get_module(db, module_id)
    if not existing_module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module with ID {module_id} not found"
        )
    
    # Check for duplicate code (if being updated)
    if module_data.code and module_data.code != existing_module.code:
        duplicate_module = ModuleService.get_module_by_code(db, module_data.code)
        if duplicate_module:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Module with code '{module_data.code}' already exists"
            )
    
    # Check for duplicate key (if being updated)
    if module_data.key and module_data.key != existing_module.key:
        duplicate_module = ModuleService.get_module_by_key(db, module_data.key)
        if duplicate_module:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Module with key '{module_data.key}' already exists"
            )
    
    try:
        updated_module = ModuleService.update_module(db, module_id, module_data)

        # Sync the application's navigation document so module changes
        # (label, icon, order, ...) reach MongoDB
        try:
            from app.menus.services.menu_sync import sync_application_menus_to_mongodb
            await sync_application_menus_to_mongodb(db, updated_module.application_id)
        except Exception as sync_error:
            print(f"[Module Update] ⚠️ MongoDB sync failed: {sync_error}")

        # Audit log: module updated
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="UPDATE",
                object_type="Module",
                object_id=str(module_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["UPDATE"],
                new_values={"name": updated_module.name},
            )
        except Exception:
            pass

        return updated_module
    except HTTPException:
        # Let intended HTTP errors (e.g. 403 read-only lock) surface unchanged
        # instead of being masked as a 500 by the generic handler below.
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update module: {str(e)}"
        )

@router.delete(
    "/{module_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a module",
    description="Soft delete a module (marks as deleted but keeps in database)"
)
async def delete_module(
    request: Request,
    module_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    deleted_by: Optional[int] = Query(None, description="User ID who is deleting the module")
):
    """
    Soft delete a module.

    - **module_id**: The UUID of the module to delete
    - **deleted_by**: User ID who is performing the deletion

    This performs a soft delete - the module is marked as deleted but remains in the database.
    """

    # Fetch module before delete for audit snapshot
    existing_module = ModuleService.get_module(db, module_id)
    old_module_name = existing_module.name if existing_module else None

    success = ModuleService.delete_module(db, module_id, deleted_by)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module with ID {module_id} not found"
        )

    # Sync so the deleted module disappears from the MongoDB navigation
    if existing_module:
        try:
            from app.menus.services.menu_sync import sync_application_menus_to_mongodb
            await sync_application_menus_to_mongodb(db, existing_module.application_id)
        except Exception as sync_error:
            print(f"[Module Delete] ⚠️ MongoDB sync failed: {sync_error}")

    # Audit log: module deleted
    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="Module",
            object_id=str(module_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"name": old_module_name, "id": str(module_id)},
        )
    except Exception:
        pass

    # Soft delete succeeded — 204 No Content (no body).