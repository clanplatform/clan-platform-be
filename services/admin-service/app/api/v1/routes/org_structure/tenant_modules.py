from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import math
import uuid

from app.infrastructure.database.session import get_db, get_tenant_db
from app.core.security import get_current_user
from app.tenant_modules.services.tenant_module import TenantModuleService
from app.tenant_modules.schemas.tenant_module import (
    TenantModuleCreate, TenantModuleUpdate, TenantModuleResponse, TenantModuleListResponse,
)
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_client import fire_audit_log

router = APIRouter()


def _to_uuid(value) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None


@router.post("/", response_model=TenantModuleResponse, status_code=status.HTTP_201_CREATED,
             summary="Assign a module to a tenant")
async def assign_module(
    request: Request, data: TenantModuleCreate,
    db: Session = Depends(get_tenant_db), current_user: dict = Depends(get_current_user),
):
    if TenantModuleService.get_assignment_by_tenant_module(db, str(data.tenant_id), str(data.module_id)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Module already assigned to this tenant")
    try:
        assignment = TenantModuleService.assign_module(db, data, assigned_by=_to_uuid(get_user_id(current_user)))
        try:
            cid, eid = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(action="CREATE", object_type="TenantModule", object_id=str(assignment.id),
                           user_id=get_user_id(current_user), client_id=cid, entity_id=eid,
                           session_id=get_session_id(current_user), ip_address=get_client_ip(request),
                           user_agent=request.headers.get("user-agent"), risk_score=RISK_SCORE["CREATE"],
                           new_values={"tenant_id": str(data.tenant_id), "module_id": str(data.module_id)})
        except Exception:
            pass
        return assignment
    except IntegrityError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Module already assigned to this tenant")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/", response_model=TenantModuleListResponse, summary="List all tenant-module assignments")
async def list_assignments(
    request: Request, db: Session = Depends(get_tenant_db), current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100),
    tenant_id: Optional[str] = Query(None), module_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    sort_by: str = Query("assigned_at"), sort_order: str = Query("desc", regex="^(asc|desc)$"),
):
    results, total = TenantModuleService.get_assignments(
        db=db, skip=(page - 1) * size, limit=size,
        tenant_id=tenant_id, module_id=module_id, is_active=is_active,
        sort_by=sort_by, sort_order=sort_order,
    )
    return TenantModuleListResponse(
        tenant_modules=results, total=total, page=page, size=size,
        total_pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get("/tenant/{tenant_id}", response_model=List[TenantModuleResponse],
            summary="Get all modules assigned to a tenant")
async def get_modules_for_tenant(
    tenant_id: str, db: Session = Depends(get_tenant_db), current_user: dict = Depends(get_current_user),
    is_active: Optional[bool] = Query(None),
):
    return TenantModuleService.get_modules_for_tenant(db, tenant_id, is_active)


@router.get("/module/{module_id}", response_model=List[TenantModuleResponse],
            summary="Get all tenants a module is assigned to")
async def get_tenants_for_module(
    module_id: str, db: Session = Depends(get_tenant_db), current_user: dict = Depends(get_current_user),
    is_active: Optional[bool] = Query(None),
):
    return TenantModuleService.get_tenants_for_module(db, module_id, is_active)


@router.get("/{assignment_id}", response_model=TenantModuleResponse, summary="Get a specific assignment")
async def get_assignment(
    assignment_id: str, db: Session = Depends(get_tenant_db), current_user: dict = Depends(get_current_user),
):
    assignment = TenantModuleService.get_assignment(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assignment {assignment_id} not found")
    return assignment


@router.put("/{assignment_id}", response_model=TenantModuleResponse,
            summary="Update assignment (activate / deactivate)")
async def update_assignment(
    request: Request, assignment_id: str, data: TenantModuleUpdate,
    db: Session = Depends(get_tenant_db), current_user: dict = Depends(get_current_user),
):
    if not TenantModuleService.get_assignment(db, assignment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assignment {assignment_id} not found")
    updated = TenantModuleService.update_assignment(db, assignment_id, data, updated_by=_to_uuid(get_user_id(current_user)))
    try:
        cid, eid = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(action="UPDATE", object_type="TenantModule", object_id=assignment_id,
                       user_id=get_user_id(current_user), client_id=cid, entity_id=eid,
                       session_id=get_session_id(current_user), ip_address=get_client_ip(request),
                       user_agent=request.headers.get("user-agent"), risk_score=RISK_SCORE["UPDATE"])
    except Exception:
        pass
    return updated


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a module from a tenant")
async def remove_assignment(
    request: Request, assignment_id: str,
    db: Session = Depends(get_tenant_db), current_user: dict = Depends(get_current_user),
):
    if not TenantModuleService.remove_assignment(db, assignment_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Assignment {assignment_id} not found")
    try:
        cid, eid = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(action="DELETE", object_type="TenantModule", object_id=assignment_id,
                       user_id=get_user_id(current_user), client_id=cid, entity_id=eid,
                       session_id=get_session_id(current_user), ip_address=get_client_ip(request),
                       user_agent=request.headers.get("user-agent"), risk_score=RISK_SCORE["DELETE"])
    except Exception:
        pass
