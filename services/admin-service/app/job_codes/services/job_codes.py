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
from datetime import datetime

from app.job_codes.models.job_codes import JobCode, JobCodeBasicInfo, JobCodeSkills, JobCodeBenefits
from app.job_codes.schemas.job_codes import JobCodeCreate, JobCodeUpdate


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
    
    return query.filter(JobCode.id == job_code_id).first()


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
    
    return query.filter(JobCode.job_code == job_code).first()


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
    # Base query with relationships
    query = db.query(JobCode).options(
        joinedload(JobCode.basic_info),
        joinedload(JobCode.skills),
        joinedload(JobCode.benefits)
    )
    
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


def create_job_code(db: Session, job_code_data: JobCodeCreate, user_id: Optional[UUID] = None) -> JobCode:
    """
    Create a new job code with optional nested relationships
    
    Args:
        db: Database session
        job_code_data: Job code creation data
        user_id: ID of user creating the record (for audit)
    
    Returns:
        Created JobCode object with all relationships
    
    Raises:
        HTTPException: If job_code already exists or creation fails
    """
    # Check if job_code already exists
    existing = db.query(JobCode).filter(JobCode.job_code == job_code_data.job_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job code '{job_code_data.job_code}' already exists"
        )
    
    try:
        # Create main JobCode
        job_code = JobCode(
            job_code=job_code_data.job_code,
            job_title=job_code_data.job_title,
            active_status=job_code_data.active_status
        )
        
        db.add(job_code)
        db.flush()  # Get the ID for nested relationships
        
        # Create nested relationships if provided
        if job_code_data.basic_info:
            basic_info = JobCodeBasicInfo(
                job_code_id=job_code.id,
                **job_code_data.basic_info.model_dump()
            )
            db.add(basic_info)
        
        if job_code_data.skills:
            skills = JobCodeSkills(
                job_code_id=job_code.id,
                **job_code_data.skills.model_dump()
            )
            db.add(skills)
        
        if job_code_data.benefits:
            benefits = JobCodeBenefits(
                job_code_id=job_code.id,
                **job_code_data.benefits.model_dump()
            )
            db.add(benefits)
        
        db.commit()
        db.refresh(job_code)
        
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job code with ID {job_code_id} not found"
        )
    
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
                # Create new
                basic_info = JobCodeBasicInfo(
                    job_code_id=job_code_id,
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

        # Update or create benefits
        if job_code_data.benefits is not None:
            benefits = db.query(JobCodeBenefits).filter(
                JobCodeBenefits.job_code_id == job_code_id
            ).first()
            
            if benefits:
                # Update existing
                benefits_data = job_code_data.benefits.model_dump(exclude_unset=True)
                for field, value in benefits_data.items():
                    setattr(benefits, field, value)
                benefits.updated_at = datetime.utcnow()
            else:
                # Create new
                benefits = JobCodeBenefits(
                    job_code_id=job_code_id,
                    **job_code_data.benefits.model_dump()
                )
                db.add(benefits)

        db.flush()
        db.commit()
        db.refresh(job_code)

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
    job_code = db.query(JobCode).filter(JobCode.job_code == job_code_str).first()
    if not job_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job code '{job_code_str}' not found"
        )
    
    return update_job_code(db, job_code.id, job_code_data, user_id)


def delete_job_code(db: Session, job_code_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """
    Delete a job code and all its nested relationships (cascade delete)
    
    Args:
        db: Database session
        job_code_id: UUID of job code to delete
        user_id: ID of user deleting the record (for audit)
    
    Returns:
        True if successful
    
    Raises:
        HTTPException: If job code not found or deletion fails
    """
    job_code = db.query(JobCode).filter(JobCode.id == job_code_id).first()
    if not job_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job code with ID {job_code_id} not found"
        )
    
    try:
        db.delete(job_code)  # Cascade delete handles nested relationships
        db.commit()
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
    job_code = db.query(JobCode).filter(JobCode.job_code == job_code_str).first()
    if not job_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job code '{job_code_str}' not found"
        )
    
    job_code_id = job_code.id
    delete_job_code(db, job_code_id, user_id)
    return job_code_id


def bulk_create_job_codes(
    db: Session,
    job_codes_data: List[JobCodeCreate],
    user_id: Optional[UUID] = None
) -> Tuple[List[JobCode], List[dict]]:
    """
    Bulk create multiple job codes
    
    Args:
        db: Database session
        job_codes_data: List of job code creation data
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
            
            # Create main JobCode
            job_code = JobCode(
                job_code=job_code_data.job_code,
                job_title=job_code_data.job_title,
                active_status=job_code_data.active_status
            )
            
            db.add(job_code)
            db.flush()  # Get the ID
            
            # Create nested relationships if provided
            if job_code_data.basic_info:
                basic_info = JobCodeBasicInfo(
                    job_code_id=job_code.id,
                    **job_code_data.basic_info.model_dump()
                )
                db.add(basic_info)
            
            if job_code_data.skills:
                skills = JobCodeSkills(
                    job_code_id=job_code.id,
                    **job_code_data.skills.model_dump()
                )
                db.add(skills)
            
            if job_code_data.benefits:
                benefits = JobCodeBenefits(
                    job_code_id=job_code.id,
                    **job_code_data.benefits.model_dump()
                )
                db.add(benefits)
            
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
    query = db.query(JobCode)
    
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
