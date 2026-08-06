"""
JobCode API endpoints
Provides CRUD operations for JobCode management with nested relationships
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db, get_tenant_db
from app.core.security import get_current_user
from app.job_codes.models.job_codes import JobCode
from app.job_codes.services import job_codes as job_code_service
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.job_codes.schemas.job_codes import (
    JobCodeCreate,
    JobCodeUpdate,
    JobCodeRead,
    JobCodeReadSimple,
    JobCodeResponse,
    JobCodeListResponse,
    JobCodeCreateResponse,
    JobCodeUpdateResponse,
    JobCodeDeleteResponse,
    JobCodeSearchParams,
    JobCodeBulkCreateRequest,
    JobCodeBulkCreateResponse
)

router = APIRouter()


@router.get("/", response_model=JobCodeListResponse)
async def get_job_codes(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search term"),
    active_status: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_tenant_db),
    current_user = Depends(get_current_user)
):
    """Get paginated list of job codes with optional filtering and all nested relationships"""

    job_codes, total = job_code_service.get_job_codes_paginated(
        db, page=page, size=size, search=search, active_status=active_status
    )

    # Build minimal response objects without nested relationships to avoid validation issues
    items = [{
        "id": jc.id,
        "job_code": jc.job_code,
        "job_title": jc.job_title,
        "active_status": jc.active_status,
        "created_at": jc.created_at,
        "updated_at": jc.updated_at
    } for jc in job_codes]

    result = JobCodeListResponse(
        data=[JobCodeRead.model_validate(item) for item in items],
        total=total,
        page=page,
        per_page=size
    )
    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="JobCode",
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


@router.get("/{job_code_id}", response_model=JobCodeResponse)
async def get_job_code(
    request: Request,
    job_code_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user = Depends(get_current_user)
):
    """Get a specific job code with all nested relationships"""

    job_code = job_code_service.get_job_code_by_id(db, job_code_id=job_code_id, load_relationships=True)

    if not job_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job code with ID {job_code_id} not found"
        )

    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="JobCode",
            object_id=str(job_code_id),
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
    return JobCodeResponse(
        data=JobCodeRead.model_validate(job_code)
    )


@router.post("/", response_model=JobCodeCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_job_code(
    request: Request,
    job_code_data: JobCodeCreate,
    db: Session = Depends(get_tenant_db),
    current_user = Depends(get_current_user)
):
    """Create a new job code with optional nested relationships"""

    # tenant_id is taken from the JWT, never the body. None => master-DB user.
    tenant_id = current_user.get("tenant_id") if isinstance(current_user, dict) else None

    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code = job_code_service.create_job_code(
        db, job_code_data=job_code_data, tenant_id=tenant_id, user_id=user_id
    )

    # Audit log: job code created
    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="CREATE",
            object_type="JobCode",
            object_id=str(job_code.id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["CREATE"],
            new_values={
                "job_code": job_code.job_code,
                "job_title": job_code.job_title,
            },
        )
    except Exception:
        pass

    return JobCodeCreateResponse(
        data=JobCodeRead.model_validate(job_code)
    )


@router.put("/{job_code_id}", response_model=JobCodeUpdateResponse)
async def update_job_code(
    request: Request,
    job_code_id: UUID,
    job_code_data: JobCodeUpdate,
    db: Session = Depends(get_tenant_db),
    current_user = Depends(get_current_user)
):
    """Update a job code and its nested relationships"""

    print(f"[JobCode Update] Starting update for job_code_id: {job_code_id}")
    print(f"[JobCode Update] Update data: {job_code_data.model_dump(exclude_unset=True)}")

    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code = job_code_service.update_job_code(
        db, job_code_id=job_code_id, job_code_data=job_code_data, user_id=user_id
    )

    print(f"[JobCode Update] Successfully updated job code: {job_code.job_code}")
    print(f"[JobCode Update] Updated at: {job_code.updated_at}")

    # Audit log: job code updated
    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="UPDATE",
            object_type="JobCode",
            object_id=str(job_code_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            new_values={
                "job_code": job_code.job_code,
                "job_title": job_code.job_title,
            },
        )
    except Exception:
        pass

    return JobCodeUpdateResponse(
        data=JobCodeRead.model_validate(job_code)
    )


@router.delete("/{job_code_id}", response_model=JobCodeDeleteResponse)
async def delete_job_code(
    request: Request,
    job_code_id: UUID,
    db: Session = Depends(get_tenant_db),
    current_user = Depends(get_current_user)
):
    """Delete a job code and all its nested relationships"""

    # Query before delete for audit snapshot
    job_code_snapshot = job_code_service.get_job_code_by_id(db, job_code_id=job_code_id)
    old_job_code = job_code_snapshot.job_code if job_code_snapshot else None
    old_job_title = job_code_snapshot.job_title if job_code_snapshot else None

    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code_service.delete_job_code(db, job_code_id=job_code_id, user_id=user_id)

    # Audit log: job code deleted
    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="JobCode",
            object_id=str(job_code_id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"job_code": old_job_code, "job_title": old_job_title, "id": str(job_code_id)},
        )
    except Exception:
        pass

    return JobCodeDeleteResponse(
        deleted_id=job_code_id
    )





    """Create a new job code with all nested relationships (alias for main create endpoint)"""
    
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code = job_code_service.create_job_code(db, job_code_data=job_code_data, user_id=user_id)
    
    return JobCodeCreateResponse(
        data=JobCodeRead.model_validate(job_code)
    )




    """Delete a job code by job_code string and all its nested relationships"""
    
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code_id = job_code_service.delete_job_code_by_code(db, job_code_str=job_code, user_id=user_id)
    
    return JobCodeDeleteResponse(
        deleted_id=job_code_id
    )