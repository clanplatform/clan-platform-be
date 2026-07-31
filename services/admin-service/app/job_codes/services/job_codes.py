"""
JobCode Service Layer

This module contains all business logic for JobCode operations including
CRUD operations with nested relationships (basic_info, skills, benefits).
"""

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from fastapi import HTTPException, status
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta, timezone
import logging

from app.job_codes.models.job_codes import JobCode, JobCodeBasicInfo, JobCodeSkills, JobCodeBenefits
from app.job_codes.schemas.job_codes import JobCodeCreate, JobCodeUpdate
from app.job_codes.exceptions import JobCodeNotFoundError, DuplicateJobCodeError
from app.infrastructure.audit_tenant import fire_audit_log

logger = logging.getLogger(__name__)

# Soft-deleted job codes are permanently removed after this many days.
JOB_CODE_RETENTION_DAYS = 30


def purge_expired_job_codes(db: Session, retention_days: int = JOB_CODE_RETENTION_DAYS) -> int:
    """
    Permanently delete job codes that were soft-deleted more than
    retention_days ago (cascade removes basic_info/skills/benefits).

    Called opportunistically from delete/list operations so no scheduler is
    needed. Best-effort: failures are logged and never break the caller.
    Returns the number of job codes purged.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    try:
        expired = db.query(JobCode).filter(
            JobCode.deleted_at.isnot(None),
            JobCode.deleted_at <= cutoff,
        ).all()
        if not expired:
            return 0
        for job_code in expired:
            db.delete(job_code)  # ORM delete so cascade handles child rows
        db.commit()
        logger.info("[JOB_CODE_PURGE] Permanently deleted %d job code(s) past %d-day retention",
                    len(expired), retention_days)
        return len(expired)
    except Exception as exc:
        db.rollback()
        logger.warning("[JOB_CODE_PURGE] Purge failed: %s", exc)
        return 0


def get_job_code_by_id(db: Session, job_code_id: UUID, load_relationships: bool = True) -> Optional[JobCode]:
    """
    Get a job code by ID with optional relationship loading
    
    Args:
        db: Database session
        job_code_id: UUID of the job code
        load_relationships: Whether to eagerly load relationships
    
    Returns:
        JobCode object or None if not found
    """
    query = db.query(JobCode)
    
    if load_relationships:
        query = query.options(
            joinedload(JobCode.basic_info),
            joinedload(JobCode.skills),
            joinedload(JobCode.benefits)
        )
    
    return query.filter(
        JobCode.id == job_code_id,
        JobCode.deleted_at.is_(None),
    ).first()


def get_job_code_by_code(db: Session, job_code: str, load_relationships: bool = True) -> Optional[JobCode]:
    """
    Get a job code by job_code string with optional relationship loading
    
    Args:
        db: Database session
        job_code: Job code string (unique identifier)
        load_relationships: Whether to eagerly load relationships
    
    Returns:
        JobCode object or None if not found
    """
    query = db.query(JobCode)
    
    if load_relationships:
        query = query.options(
            joinedload(JobCode.basic_info),
            joinedload(JobCode.skills),
            joinedload(JobCode.benefits)
        )
    
    return query.filter(
        JobCode.job_code == job_code,
        JobCode.deleted_at.is_(None),
    ).first()


def get_job_codes_paginated(
    db: Session,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None,
    category: Optional[str] = None,
    active_status: Optional[bool] = None
) -> Tuple[List[JobCode], int]:
    """
    Get paginated list of job codes with optional filtering
    
    Args:
        db: Database session
        page: Page number (1-indexed)
        size: Number of items per page
        search: Search term for job_code or job_title
        category: Filter by category
        active_status: Filter by active status
    
    Returns:
        Tuple of (job_codes list, total count)
    """
    # Opportunistic purge of job codes past the retention window
    purge_expired_job_codes(db)

    # Base query with relationships (soft-deleted rows excluded)
    query = db.query(JobCode).options(
        joinedload(JobCode.basic_info),
        joinedload(JobCode.skills),
        joinedload(JobCode.benefits)
    ).filter(JobCode.deleted_at.is_(None))

    # Apply filters
    if search:
        query = query.filter(
            or_(
                JobCode.job_code.ilike(f"%{search}%"),
                JobCode.job_title.ilike(f"%{search}%")
            )
        )
    
    if category:
        query = query.join(JobCodeBasicInfo).filter(
            JobCodeBasicInfo.category.ilike(f"%{category}%")
        )
    
    if active_status is not None:
        query = query.filter(JobCode.active_status == active_status)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * size
    job_codes = query.offset(offset).limit(size).all()
    
    return job_codes, total


def create_job_code(
    db: Session,
    job_code_data: JobCodeCreate,
    tenant_id: Optional[UUID],
    user_id: Optional[UUID] = None,
) -> JobCode:
    """
    Create a new job code with optional nested relationships

    Args:
        db: Database session
        job_code_data: Job code creation data
        tenant_id: Owning tenant, derived from the caller's JWT (not the body).
            Persisted onto both job_codes and jobcode_basicinfo. None for
            master-DB users (token without a tenant_id).
        user_id: ID of user creating the record (for audit)

    Returns:
        Created JobCode object with all relationships

    Raises:
        HTTPException: If job_code already exists or creation fails
    """
    # Check if job_code already exists
    existing = db.query(JobCode).filter(JobCode.job_code == job_code_data.job_code).first()
    if existing:
        raise DuplicateJobCodeError(job_code_data.job_code)
    
    try:
        # Create main JobCode. tenant_id comes from the token, not the payload.
        # active_status is backend-operational (not in the schema) — always active
        # on create; delete/restore toggle it later.
        job_code = JobCode(
            job_code=job_code_data.job_code,
            job_title=job_code_data.job_title,
            active_status=True,
            tenant_id=tenant_id
        )

        db.add(job_code)
        db.flush()  # Get the ID for nested relationships

        # Create nested relationships (tenant_id injected from the token, since
        # it is no longer part of the basic_info payload)
        basic_info = JobCodeBasicInfo(
            job_code_id=job_code.id,
            tenant_id=tenant_id,
            **job_code_data.basic_info.model_dump()
        )
        db.add(basic_info)

        if job_code_data.skills:
            skills = JobCodeSkills(
                job_code_id=job_code.id,
                **job_code_data.skills.model_dump()
            )
            db.add(skills)

        db.commit()
        db.refresh(job_code)

        fire_audit_log(
            action="CREATE", object_type="JobCode",
            object_id=str(job_code.id),
            user_id=str(user_id) if user_id else None,
            new_values={"job_code": job_code.job_code, "job_title": job_code.job_title},
        )
        # Return with relationships loaded
        return get_job_code_by_id(db, job_code.id, load_relationships=True)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job code: {str(e)}"
        )


def update_job_code(
    db: Session,
    job_code_id: UUID,
    job_code_data: JobCodeUpdate,
    user_id: Optional[UUID] = None
) -> JobCode:
    """
    Update a job code and its nested relationships
    
    Args:
        db: Database session
        job_code_id: UUID of job code to update
        job_code_data: Update data
        user_id: ID of user updating the record (for audit)
    
    Returns:
        Updated JobCode object with all relationships
    
    Raises:
        HTTPException: If job code not found or update fails
    """
    job_code = db.query(JobCode).filter(JobCode.id == job_code_id).first()
    if not job_code:
        raise JobCodeNotFoundError(job_code_id=str(job_code_id))
    
    try:
        # Update main JobCode fields
        update_data = job_code_data.model_dump(
            exclude_unset=True,
            exclude={'basic_info', 'skills', 'benefits'}
        )
        for field, value in update_data.items():
            setattr(job_code, field, value)

        # Explicitly set updated_at to trigger the update
        job_code.updated_at = datetime.utcnow()

        # Update or create basic_info
        if job_code_data.basic_info is not None:
            basic_info = db.query(JobCodeBasicInfo).filter(
                JobCodeBasicInfo.job_code_id == job_code_id
            ).first()
            
            if basic_info:
                # Update existing
                basic_info_data = job_code_data.basic_info.model_dump(exclude_unset=True)
                for field, value in basic_info_data.items():
                    setattr(basic_info, field, value)
                basic_info.updated_at = datetime.utcnow()
            else:
                # Create new — tenant_id is immutable and inherited from the
                # parent job code (set from the token at creation time).
                basic_info = JobCodeBasicInfo(
                    job_code_id=job_code_id,
                    tenant_id=job_code.tenant_id,
                    **job_code_data.basic_info.model_dump()
                )
                db.add(basic_info)

        # Update or create skills
        if job_code_data.skills is not None:
            skills = db.query(JobCodeSkills).filter(
                JobCodeSkills.job_code_id == job_code_id
            ).first()
            
            if skills:
                # Update existing
                skills_data = job_code_data.skills.model_dump(exclude_unset=True)
                for field, value in skills_data.items():
                    setattr(skills, field, value)
                skills.updated_at = datetime.utcnow()
            else:
                # Create new
                skills = JobCodeSkills(
                    job_code_id=job_code_id,
                    **job_code_data.skills.model_dump()
                )
                db.add(skills)

        db.flush()
        db.commit()
        db.refresh(job_code)

        fire_audit_log(
            action="UPDATE", object_type="JobCode",
            object_id=str(job_code_id),
            user_id=str(user_id) if user_id else None,
        )
        # Return with relationships loaded
        return get_job_code_by_id(db, job_code_id, load_relationships=True)

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update job code: {str(e)}"
        )


def update_job_code_by_code(
    db: Session,
    job_code_str: str,
    job_code_data: JobCodeUpdate,
    user_id: Optional[UUID] = None
) -> JobCode:
    """
    Update a job code by job_code string and its nested relationships
    
    Args:
        db: Database session
        job_code_str: Job code string identifier
        job_code_data: Update data
        user_id: ID of user updating the record (for audit)
    
    Returns:
        Updated JobCode object with all relationships
    
    Raises:
        HTTPException: If job code not found or update fails
    """
    job_code = db.query(JobCode).filter(
        JobCode.job_code == job_code_str,
        JobCode.deleted_at.is_(None),
    ).first()
    if not job_code:
        raise JobCodeNotFoundError(code=job_code_str)
    
    return update_job_code(db, job_code.id, job_code_data, user_id)


def delete_job_code(db: Session, job_code_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """
    Soft delete a job code: sets active_status=False and stamps deleted_at.
    The row (and its nested relationships) is permanently removed by the
    purge once it has been soft-deleted for JOB_CODE_RETENTION_DAYS (30) days.

    Args:
        db: Database session
        job_code_id: UUID of job code to delete
        user_id: ID of user deleting the record (for audit)

    Returns:
        True if successful

    Raises:
        HTTPException: If job code not found or deletion fails
    """
    # Opportunistic purge of job codes past the retention window
    purge_expired_job_codes(db)

    job_code = db.query(JobCode).filter(
        JobCode.id == job_code_id,
        JobCode.deleted_at.is_(None),
    ).first()
    if not job_code:
        raise JobCodeNotFoundError(job_code_id=str(job_code_id))

    try:
        job_code.active_status = False
        job_code.deleted_at = datetime.now(timezone.utc)
        db.commit()
        fire_audit_log(
            action="DELETE", object_type="JobCode",
            object_id=str(job_code_id),
            user_id=str(user_id) if user_id else None,
            old_values={"active_status": True},
            new_values={"active_status": False, "deleted_at": job_code.deleted_at.isoformat()},
        )
        return True

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete job code: {str(e)}"
        )


def delete_job_code_by_code(db: Session, job_code_str: str, user_id: Optional[UUID] = None) -> UUID:
    """
    Delete a job code by job_code string and all its nested relationships
    
    Args:
        db: Database session
        job_code_str: Job code string identifier
        user_id: ID of user deleting the record (for audit)
    
    Returns:
        UUID of deleted job code
    
    Raises:
        HTTPException: If job code not found or deletion fails
    """
    job_code = db.query(JobCode).filter(
        JobCode.job_code == job_code_str,
        JobCode.deleted_at.is_(None),
    ).first()
    if not job_code:
        raise JobCodeNotFoundError(code=job_code_str)
    
    job_code_id = job_code.id
    delete_job_code(db, job_code_id, user_id)
    return job_code_id


def bulk_create_job_codes(
    db: Session,
    job_codes_data: List[JobCodeCreate],
    tenant_id: Optional[UUID],
    user_id: Optional[UUID] = None
) -> Tuple[List[JobCode], List[dict]]:
    """
    Bulk create multiple job codes

    Args:
        db: Database session
        job_codes_data: List of job code creation data
        tenant_id: Owning tenant, derived from the caller's JWT (not the body).
            None for master-DB users (token without a tenant_id).
        user_id: ID of user creating the records (for audit)

    Returns:
        Tuple of (created job codes list, failed items list)
    """
    created = []
    failed = []
    
    for job_code_data in job_codes_data:
        try:
            # Check if job_code already exists
            existing = db.query(JobCode).filter(
                JobCode.job_code == job_code_data.job_code
            ).first()
            if existing:
                failed.append({
                    "job_code": job_code_data.job_code,
                    "error": f"Job code '{job_code_data.job_code}' already exists"
                })
                continue
            
            # Create main JobCode. tenant_id comes from the token, not the payload.
            # active_status is backend-operational (not in the schema) — always
            # active on create.
            job_code = JobCode(
                job_code=job_code_data.job_code,
                job_title=job_code_data.job_title,
                active_status=True,
                tenant_id=tenant_id
            )

            db.add(job_code)
            db.flush()  # Get the ID

            # Create nested relationships (tenant_id injected from the token)
            basic_info = JobCodeBasicInfo(
                job_code_id=job_code.id,
                tenant_id=tenant_id,
                **job_code_data.basic_info.model_dump()
            )
            db.add(basic_info)

            if job_code_data.skills:
                skills = JobCodeSkills(
                    job_code_id=job_code.id,
                    **job_code_data.skills.model_dump()
                )
                db.add(skills)

            db.commit()
            
            # Load with relationships
            job_code = get_job_code_by_id(db, job_code.id, load_relationships=True)
            created.append(job_code)
            
        except Exception as e:
            db.rollback()
            failed.append({
                "job_code": job_code_data.job_code,
                "error": str(e)
            })
    
    return created, failed


def get_job_codes_count(
    db: Session,
    search: Optional[str] = None,
    category: Optional[str] = None,
    active_status: Optional[bool] = None
) -> int:
    """
    Get count of job codes with optional filtering
    
    Args:
        db: Database session
        search: Search term for job_code or job_title
        category: Filter by category
        active_status: Filter by active status
    
    Returns:
        Count of job codes matching filters
    """
    query = db.query(JobCode).filter(JobCode.deleted_at.is_(None))

    if search:
        query = query.filter(
            or_(
                JobCode.job_code.ilike(f"%{search}%"),
                JobCode.job_title.ilike(f"%{search}%")
            )
        )
    
    if category:
        query = query.join(JobCodeBasicInfo).filter(
            JobCodeBasicInfo.category.ilike(f"%{category}%")
        )
    
    if active_status is not None:
        query = query.filter(JobCode.active_status == active_status)
    
    return query.count()


def search_job_codes(
    db: Session,
    search_term: str,
    skip: int = 0,
    limit: int = 100
) -> List[JobCode]:
    """
    Search job codes by job_code or job_title
    
    Args:
        db: Database session
        search_term: Search term
        skip: Number of records to skip
        limit: Maximum number of records to return
    
    Returns:
        List of matching JobCode objects
    """
    query = db.query(JobCode).options(
        joinedload(JobCode.basic_info),
        joinedload(JobCode.skills),
        joinedload(JobCode.benefits)
    ).filter(
        JobCode.deleted_at.is_(None),
        or_(
            JobCode.job_code.ilike(f"%{search_term}%"),
            JobCode.job_title.ilike(f"%{search_term}%")
        )
    )

    return query.offset(skip).limit(limit).all()


def get_job_codes_by_category(db: Session, category: str, skip: int = 0, limit: int = 100) -> List[JobCode]:
    """
    Get job codes filtered by category
    
    Args:
        db: Database session
        category: Category to filter by
        skip: Number of records to skip
        limit: Maximum number of records to return
    
    Returns:
        List of JobCode objects in the category
    """
    query = db.query(JobCode).options(
        joinedload(JobCode.basic_info),
        joinedload(JobCode.skills),
        joinedload(JobCode.benefits)
    ).join(JobCodeBasicInfo).filter(
        JobCode.deleted_at.is_(None),
        JobCodeBasicInfo.category.ilike(f"%{category}%")
    )

    return query.offset(skip).limit(limit).all()


def get_active_job_codes(db: Session, skip: int = 0, limit: int = 100) -> List[JobCode]:
    """
    Get all active job codes
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
    
    Returns:
        List of active JobCode objects
    """
    query = db.query(JobCode).options(
        joinedload(JobCode.basic_info),
        joinedload(JobCode.skills),
        joinedload(JobCode.benefits)
    ).filter(JobCode.active_status == True)
    
    return query.offset(skip).limit(limit).all()
