from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.infrastructure.database.session import get_db
from app.domain_controls.models.domains import Domain
from app.schemas.domains import DomainCreate, DomainUpdate, DomainResponse
from app.core.security import get_current_user_id
from app.core.config import settings
from app.infrastructure.cache.redis_cache import redis_cache

# Disable internal trailing-slash redirects for this router
router = APIRouter(redirect_slashes=False)

# List domains without trailing slash to avoid redirects
@router.get("", response_model=List[DomainResponse])
async def get_domains(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get all domains with pagination, sorted by newest first (FILO)"""
    # Create cache key based on query parameters
    cache_key = f"domains:list:skip={skip}:limit={limit}:search={search}:is_active={is_active}"

    # Try to get from cache
    cached_domains = redis_cache.get(cache_key)
    if cached_domains:
        return cached_domains

    # Query database if not in cache
    query = db.query(Domain).filter(Domain.is_deleted == False)

    if search:
        query = query.filter(Domain.name.ilike(f"%{search}%"))

    if is_active is not None:
        query = query.filter(Domain.is_active == is_active)

    # Sort by created_at in descending order (newest first - FILO)
    query = query.order_by(Domain.created_at.desc())

    domains = query.offset(skip).limit(limit).all()

    # Convert to dict for caching
    domains_list = [
        {
            "id": str(d.id),
            "code": d.code,
            "name": d.name,
            "description": d.description,
            "domain_metadata": d.domain_metadata,
            "is_active": d.is_active,
            "is_deleted": d.is_deleted,
            "deleted_at": str(d.deleted_at) if d.deleted_at else None,
            "created_at": str(d.created_at),
            "updated_at": str(d.updated_at)
        }
        for d in domains
    ]

    # Cache the result for 30 minutes
    redis_cache.set(cache_key, domains_list, ttl=settings.CACHE_DEFAULT_TTL)

    return domains

@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get a specific domain by ID"""
    # Try to get from cache
    cached_domain = redis_cache.get_cached_domain(str(domain_id))
    if cached_domain:
        return cached_domain

    # Query database if not in cache
    domain = db.query(Domain).filter(Domain.id == domain_id, Domain.is_deleted == False).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )

    # Cache the domain
    domain_dict = {
        "id": str(domain.id),
        "code": domain.code,
        "name": domain.name,
        "description": domain.description,
        "domain_metadata": domain.domain_metadata,
        "is_active": domain.is_active,
        "is_deleted": domain.is_deleted,
        "deleted_at": str(domain.deleted_at) if domain.deleted_at else None,
        "created_at": str(domain.created_at),
        "updated_at": str(domain.updated_at)
    }
    redis_cache.cache_domain(str(domain_id), domain_dict, ttl=settings.CACHE_DEFAULT_TTL)

    return domain

@router.post("", response_model=DomainResponse)
async def create_domain(
    domain: DomainCreate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a new domain"""
    # Check if domain name already exists
    existing_domain = db.query(Domain).filter(
        Domain.name == domain.name,
        Domain.is_deleted == False
    ).first()

    if existing_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain with this name already exists"
        )

    # Check if domain code already exists
    existing_code = db.query(Domain).filter(
        Domain.code == domain.code,
        Domain.is_deleted == False
    ).first()

    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain with this code already exists"
        )

    # Create new domain
    db_domain = Domain(**domain.dict())
    db.add(db_domain)
    db.commit()
    db.refresh(db_domain)

    # Cache the created domain in Redis
    domain_dict = {
        "id": str(db_domain.id),
        "code": db_domain.code,
        "name": db_domain.name,
        "description": db_domain.description,
        "domain_metadata": db_domain.domain_metadata,
        "is_active": db_domain.is_active,
        "is_deleted": db_domain.is_deleted,
        "deleted_at": str(db_domain.deleted_at) if db_domain.deleted_at else None,
        "created_at": str(db_domain.created_at),
        "updated_at": str(db_domain.updated_at)
    }
    redis_cache.cache_domain(str(db_domain.id), domain_dict, ttl=settings.CACHE_DEFAULT_TTL)

    # Invalidate domains list cache
    redis_cache.delete_pattern("domains:list:*")

    return db_domain

@router.put("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: UUID,
    domain: DomainUpdate,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Update a domain"""
    # Get existing domain
    db_domain = db.query(Domain).filter(
        Domain.id == domain_id,
        Domain.is_deleted == False
    ).first()
    
    if not db_domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    # Check if new name already exists (if name is being updated)
    if domain.name and domain.name != db_domain.name:
        existing_domain = db.query(Domain).filter(
            Domain.name == domain.name,
            Domain.id != domain_id,
            Domain.is_deleted == False
        ).first()
        
        if existing_domain:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain with this name already exists"
            )
    
    # Check if new code already exists (if code is being updated)
    if domain.code and domain.code != db_domain.code:
        existing_code = db.query(Domain).filter(
            Domain.code == domain.code,
            Domain.id != domain_id,
            Domain.is_deleted == False
        ).first()
        
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain with this code already exists"
            )
    
    # Update domain fields
    update_data = domain.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_domain, field, value)

    db.commit()
    db.refresh(db_domain)

    # Invalidate cache for this domain
    redis_cache.delete(f"domain:{domain_id}")

    # Invalidate domains list cache
    redis_cache.delete_pattern("domains:list:*")

    return db_domain

@router.delete("/{domain_id}")
async def delete_domain(
    domain_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Soft delete a domain and all related applications"""
    domain = db.query(Domain).filter(Domain.id == domain_id, Domain.is_deleted == False).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )
    
    try:
        # Import Application model and datetime for soft delete
        from app.domain_controls.models.applications import Application
        from datetime import datetime
        
        # First, soft delete all applications that reference this domain
        applications = db.query(Application).filter(
            Application.domain_id == domain_id,
            Application.is_deleted == False
        ).all()
        
        deletion_time = datetime.utcnow()
        
        for application in applications:
            application.is_active = False
            application.is_deleted = True
            application.deleted_at = deletion_time
        
        # Then soft delete the domain itself
        domain.is_active = False
        domain.is_deleted = True
        domain.deleted_at = deletion_time

        db.commit()

        # Invalidate cache for this domain
        redis_cache.delete(f"domain:{domain_id}")

        # Invalidate domains list cache
        redis_cache.delete_pattern("domains:list:*")

        # Invalidate domain applications cache
        redis_cache.delete(f"domain:{domain_id}:applications")

        return {"message": f"Domain and {len(applications)} related applications deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete domain: {str(e)}"
        )
