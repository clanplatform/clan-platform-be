"""
JobCode API endpoints
Provides CRUD operations for JobCode management with nested relationships
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.job_code import JobCode
from app.services.job_code import job_codes as job_code_service
from app.schemas.job_code import (
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
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    search: Optional[str] = Query(None, description="Search term"),
    category: Optional[str] = Query(None, description="Filter by category"),
    active_status: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get paginated list of job codes with optional filtering and all nested relationships"""
    
    job_codes, total = job_code_service.get_job_codes_paginated(
        db, page=page, size=size, search=search, category=category, active_status=active_status
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

    return JobCodeListResponse(
        data=[JobCodeRead.model_validate(item) for item in items],
        total=total,
        page=page,
        per_page=size
    )


@router.get("/{job_code_id}", response_model=JobCodeResponse)
async def get_job_code(
    job_code_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific job code with all nested relationships"""
    
    job_code = job_code_service.get_job_code_by_id(db, job_code_id=job_code_id, load_relationships=True)
    
    if not job_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job code with ID {job_code_id} not found"
        )
    
    return JobCodeResponse(
        data=JobCodeRead.model_validate(job_code)
    )


@router.post("/", response_model=JobCodeCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_job_code(
    job_code_data: JobCodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new job code with optional nested relationships"""
    
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code = job_code_service.create_job_code(db, job_code_data=job_code_data, user_id=user_id)
    
    return JobCodeCreateResponse(
        data=JobCodeRead.model_validate(job_code)
    )


@router.put("/{job_code_id}", response_model=JobCodeUpdateResponse)
async def update_job_code(
    job_code_id: UUID,
    job_code_data: JobCodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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

    return JobCodeUpdateResponse(
        data=JobCodeRead.model_validate(job_code)
    )


@router.delete("/{job_code_id}", response_model=JobCodeDeleteResponse)
async def delete_job_code(
    job_code_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a job code and all its nested relationships"""
    
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code_service.delete_job_code(db, job_code_id=job_code_id, user_id=user_id)
    
    return JobCodeDeleteResponse(
        deleted_id=job_code_id
    )


@router.post("/bulk", response_model=JobCodeBulkCreateResponse)
async def bulk_create_job_codes(
    bulk_data: JobCodeBulkCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk create multiple job codes"""
    
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    created, failed = job_code_service.bulk_create_job_codes(
        db, job_codes_data=bulk_data.job_codes, user_id=user_id
    )
    
    return JobCodeBulkCreateResponse(
        created=[JobCodeRead.model_validate(jc) for jc in created],
        failed=failed
    )


# Complete endpoints - work with job_code strings instead of IDs
@router.get("/complete/{job_code}", response_model=JobCodeResponse)
async def get_job_code_complete(
    job_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific job code by job_code string with all nested relationships"""
    
    job_code_obj = job_code_service.get_job_code_by_code(db, job_code=job_code, load_relationships=True)
    
    if not job_code_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job code '{job_code}' not found"
        )
    
    return JobCodeResponse(
        data=JobCodeRead.model_validate(job_code_obj)
    )


@router.post("/complete", response_model=JobCodeCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_job_code_complete(
    job_code_data: JobCodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new job code with all nested relationships (alias for main create endpoint)"""
    
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code = job_code_service.create_job_code(db, job_code_data=job_code_data, user_id=user_id)
    
    return JobCodeCreateResponse(
        data=JobCodeRead.model_validate(job_code)
    )


@router.put("/complete/{job_code}", response_model=JobCodeUpdateResponse)
async def update_job_code_complete(
    job_code: str,
    job_code_data: JobCodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a job code by job_code string and its nested relationships"""
    
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code_obj = job_code_service.update_job_code_by_code(
        db, job_code_str=job_code, job_code_data=job_code_data, user_id=user_id
    )
    
    return JobCodeUpdateResponse(
        data=JobCodeRead.model_validate(job_code_obj)
    )


@router.delete("/complete/{job_code}", response_model=JobCodeDeleteResponse)
async def delete_job_code_complete(
    job_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a job code by job_code string and all its nested relationships"""
    
    user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
    job_code_id = job_code_service.delete_job_code_by_code(db, job_code_str=job_code, user_id=user_id)
    
    return JobCodeDeleteResponse(
        deleted_id=job_code_id
    )